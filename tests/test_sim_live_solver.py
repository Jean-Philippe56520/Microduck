"""P0d: exact-process live native solver tap and fail-closed offline analysis."""
import contextlib
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from microduck_companion.sim_flat_zone import (
    FLAT_SCENE_BLOB, GroundTruthError, RL_COMMIT,
)
from microduck_companion.sim_live_solver_tap import (
    EXPECTED_BODY_ARGS, EVERY_N_STEPS, JOINT_NAMES, TapError,
    activate_if_exact_body_server, capture_solver_step, install_solver_tap,
    matching_body_argv,
)
from microduck_companion.sim_live_solver_analyze import (
    _read_solver_trace, analyze_live_solver, main,
)
from microduck_companion.sim_walk_compare import REST_SAMPLES
from microduck_companion.sim_walk_trial import WALK_SPEED_MPS, WALK_TICKS


class FakeModel:
    def __init__(self):
        self.opt = types.SimpleNamespace(timestep=.005)
        self.names = {
            ("geom", "floor"): 0,
            ("geom", "left_foot_collision"): 1,
            ("geom", "right_foot_collision"): 2,
            ("site", "left_foot"): 0,
            ("site", "right_foot"): 1,
            ("joint", "trunk_base_freejoint"): 0,
        }
        self.jnt_qposadr = [0]
        self.actuator_trnid = []
        for i, name in enumerate(JOINT_NAMES):
            joint_id = i + 1
            self.names[("joint", name)] = joint_id
            self.names[("actuator", name)] = i
            self.jnt_qposadr.append(7 + i)
            self.actuator_trnid.append([joint_id, 0])


class FakeData:
    def __init__(self):
        self.time = 0.0
        self.qpos = [0.0] * 21
        self.ctrl = [0.3] * 14
        self.actuator_force = [0.1] * 14
        self.ncon = 2
        self.contact = [
            types.SimpleNamespace(geom1=0, geom2=1, dist=-.0004),
            types.SimpleNamespace(geom1=2, geom2=0, dist=-.0003),
        ]
        self.site_xpos = [[.01, .02, .0], [.01, -.02, .0]]


class FakeMuJoCo:
    mjtObj = types.SimpleNamespace(
        mjOBJ_GEOM="geom", mjOBJ_SITE="site",
        mjOBJ_JOINT="joint", mjOBJ_ACTUATOR="actuator",
    )
    calls = []

    @classmethod
    def mj_name2id(cls, model, kind, name):
        return model.names.get((kind, name), -1)

    @classmethod
    def mj_contactForce(cls, model, data, index, out):
        cls.calls.append("mj_contactForce")
        out[:] = [1.5 if index == 0 else .75, .08, .06, 0., 0., 0.]

    @classmethod
    def mj_step(cls, model, data):
        cls.calls.append("original_mj_step")
        data.time += .005
        return None


class FakeWriter:
    def __init__(self, *, fail_after=None):
        self.rows = []
        self.fail_after = fail_after

    def submit(self, row):
        if self.fail_after is not None and len(self.rows) >= self.fail_after:
            raise TapError("simulated full queue")
        self.rows.append(row)


def fake_snapshot(step=4):
    controls = {name: (i*.01) for i, name in enumerate(JOINT_NAMES)}
    angles = {name: i*.015 for i, name in enumerate(JOINT_NAMES)}
    effort = {name: .02 for name in JOINT_NAMES}
    return {
        "kind": "frame", "step": step, "sim_time_s": .005*step,
        "trunk_xyz_after_integration_m": [.001*step, 0.001, .12],
        "foot_sites_solver_cache_xyz_m": {
            "left": [.01 + .0001*step, .02, .0],
            "right": [.01, -.02, .0],
        },
        "contacts_original_solver": {
            "left": {
                "pair_count": 1, "normal_force_n": 1.5,
                "tangent_force_norm_n": .1,
                "min_signed_distance_m": -.0004,
            },
            "right": {
                "pair_count": 1, "normal_force_n": .75,
                "tangent_force_norm_n": .1,
                "min_signed_distance_m": -.0003,
            },
        },
        "actuator_position_controls_rad": controls,
        "joint_angles_post_integration_rad": angles,
        "actuator_force_simulated_nm": effort,
        "capture_us": 25.,
        "live_solver_source": True,
    }


def synthetic_p0b():
    def frame(t, phase):
        v = WALK_SPEED_MPS if phase == "walk" else 0.0
        return {
            "sim_time_s": t,
            "flat_scene_safe_area": True,
            "trunk_xyz_m": [0., 0., .12],
            "trunk_quat_wxyz": [1., 0., 0., 0.],
            "positions_rad": [0.] * 15,
            "foot_contacts": None,
            "joint_targets_rad": None,
            "robotd": {
                "policy": phase,
                "applied_vx_vy_mps_vyaw_rad_s": [v, 0., 0.],
            },
        }
    rest = [frame(.4 + i*.1, "stand") for i in range(REST_SAMPLES)]
    moving = [frame(2.4 + i*.1, "walk") for i in range(WALK_TICKS)]
    moving[0]["robotd"]["policy"] = "stand"
    moving[0]["robotd"]["applied_vx_vy_mps_vyaw_rad_s"] = [0., 0., 0.]
    return {
        "schema_version": 1,
        "environment": "pinned_official_mujoco_only",
        "comparison": "same_simulator_session_stand_then_single_bounded_walk",
        "stop_confirmed": True,
        "gait_validated": False,
        "foot_contacts_available": False,
        "joint_targets_available": False,
        "read_only_joint_samples": REST_SAMPLES + WALK_TICKS,
        "motion_commands_sent_by_existing_j2e_trial": WALK_TICKS,
        "requested_walk_speed_mps": WALK_SPEED_MPS,
        "motion_memory_outcome": "no_progress_observed",
        "walk_policy_sampled": True,
        "motor_authority": "official_robotd",
        "measured_walk_displacement_m": .002,
        "rest_trace": {
            "mode": "passive_read_only",
            "source": "pinned_official_mujoco_body_and_robotd",
            "rl_commit": RL_COMMIT,
            "flat_scene_git_blob": FLAT_SCENE_BLOB,
            "foot_contacts_available": False,
            "joint_targets_available": False,
            "joint_names_wire_order": [
                "left_hip_yaw", "left_hip_roll", "left_hip_pitch",
                "left_knee", "left_ankle", "neck_pitch", "head_pitch",
                "head_yaw", "head_roll", "mouth", "right_hip_yaw",
                "right_hip_roll", "right_hip_pitch", "right_knee",
                "right_ankle",
            ],
            "observations": rest,
        },
        "walk_trace": {"observations": moving},
    }


def synthetic_rows():
    rows = []
    for idx in range(1, 261):
        row = fake_snapshot(step=idx*EVERY_N_STEPS)
        row["sim_time_s"] = .02*idx
        row["trunk_xyz_after_integration_m"][0] = .001*idx
        if idx > 120:
            row["actuator_position_controls_rad"]["left_knee"] = .05 * (
                idx % 4
            )
            row["joint_angles_post_integration_rad"]["left_knee"] = .01 * (
                idx % 3
            )
        rows.append(row)
    return rows


def header():
    return {
        "kind": "header", "schema_version": 1,
        "source": "live_pinned_oem_mujoco_mj_step_tap",
        "rl_commit": RL_COMMIT,
        "flat_scene_git_blob": FLAT_SCENE_BLOB,
        "sample_every_n_physics_steps": EVERY_N_STEPS,
        "model_timestep_s": .005,
        "capture_is_not_actuator_authority": True,
    }


class NativeSolverTests(unittest.TestCase):
    def setUp(self):
        # Python companion unit tests intentionally require no native MuJoCo
        # or NumPy installation; the pinned runtime does include both.
        fake_numpy = types.SimpleNamespace(
            zeros=lambda n, dtype=float: [0.0] * n
        )
        patcher = patch.dict(sys.modules, {"numpy": fake_numpy})
        patcher.start()
        self.addCleanup(patcher.stop)
        FakeMuJoCo.calls = []
        FakeMuJoCo.mj_step = lambda model, data: (
            FakeMuJoCo.calls.append("original_mj_step"),
            setattr(data, "time", data.time + .005),
        )[-1]

    def test_original_physics_is_never_skipped_repeated_or_commanded(self):
        model, data, writer = FakeModel(), FakeData(), FakeWriter()
        tap = install_solver_tap(Path("/fake/never-opened"), mj=FakeMuJoCo,
                                 writer=writer)
        for _ in range(12):
            FakeMuJoCo.mj_step(model, data)
        self.assertEqual(12, FakeMuJoCo.calls.count("original_mj_step"))
        self.assertEqual(6, FakeMuJoCo.calls.count("mj_contactForce"))
        self.assertEqual(12, tap.count)
        self.assertEqual(1, len([r for r in writer.rows
                                 if r["kind"] == "header"]))
        frames = [r for r in writer.rows if r["kind"] == "frame"]
        self.assertEqual([4, 8, 12], [f["step"] for f in frames])
        self.assertAlmostEqual(.02, frames[0]["sim_time_s"])
        self.assertEqual(14, len(frames[0]["actuator_position_controls_rad"]))
        self.assertEqual(1.5, frames[0]["contacts_original_solver"]["left"]
                         ["normal_force_n"])
        self.assertAlmostEqual(.1, frames[0]["contacts_original_solver"]
                               ["right"]["tangent_force_norm_n"])
        self.assertEqual([0.3] * 14, data.ctrl)
        self.assertFalse(tap.disabled)

    def test_live_bad_geometry_disables_tap_without_blocking_original_solver(self):
        model, data, writer = FakeModel(), FakeData(), FakeWriter()
        model.names.pop(("geom", "floor"))
        tap = install_solver_tap(Path("/fake/never-opened"), mj=FakeMuJoCo,
                                 writer=writer)
        for _ in range(8):
            FakeMuJoCo.mj_step(model, data)
        self.assertEqual(8, FakeMuJoCo.calls.count("original_mj_step"))
        self.assertTrue(tap.disabled)
        self.assertEqual(["error"], [x["kind"] for x in writer.rows])
        self.assertIn("floor", writer.rows[0]["reason"])

    def test_bounded_writer_failure_is_visible_and_physics_unchanged(self):
        model, data, writer = FakeModel(), FakeData(), FakeWriter(fail_after=1)
        tap = install_solver_tap(Path("/fake"), mj=FakeMuJoCo, writer=writer)
        for _ in range(12):
            FakeMuJoCo.mj_step(model, data)
        self.assertEqual(12, FakeMuJoCo.calls.count("original_mj_step"))
        self.assertTrue(tap.disabled)
        self.assertEqual(["header"], [row["kind"] for row in writer.rows])

    def test_exact_process_required_for_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary = Path(tmp) / "python"
            binary.write_bytes(b"")
            args = [str(binary), *EXPECTED_BODY_ARGS]
            self.assertTrue(matching_body_argv(args, binary))
            self.assertFalse(matching_body_argv(args[:-1], binary))
            self.assertFalse(matching_body_argv(
                [str(binary), *EXPECTED_BODY_ARGS[:-1], "--viewer"], binary
            ))
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(activate_if_exact_body_server())

    def test_installer_rejects_double_wrap(self):
        writer = FakeWriter()
        install_solver_tap(Path("/fake"), mj=FakeMuJoCo, writer=writer)
        with self.assertRaisesRegex(TapError, "already"):
            install_solver_tap(Path("/fake"), mj=FakeMuJoCo, writer=writer)


class LiveAnalysisTests(unittest.TestCase):
    def _write(self, directory, records):
        path = Path(directory) / "live.jsonl"
        path.write_text(
            "\n".join(json.dumps(x, allow_nan=False) for x in records) + "\n"
        )
        return path

    def test_native_stream_and_phases_are_measured_not_assumed_gait(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write(tmp, [header(), *synthetic_rows()])
            rows = _read_solver_trace(path)
        result = analyze_live_solver(synthetic_p0b(), rows)
        self.assertTrue(result["original_solver_foot_contacts_observed"])
        self.assertTrue(result["original_solver_contact_forces_observed"])
        self.assertTrue(result["original_actuator_controls_observed"])
        self.assertFalse(result["gait_validated"])
        self.assertFalse(result["traction_validated"])
        self.assertEqual("unknown", result["locomotion_root_cause"])
        self.assertGreaterEqual(result["stand"]["frames"], 20)
        self.assertGreaterEqual(result["walk"]["frames"], 20)
        self.assertEqual(result["walk"]["frames"], result["walk"]
                         ["original_solver_contacts"]["left"]
                         ["frames_with_normal_force_gt_0_1n"])
        self.assertGreater(
            result["walk"]["actuator_control_range_rad"]["left_knee"], 0.0,
        )
        self.assertGreater(
            result["walk"]["original_solver_contacts"]["left"]
            ["max_foot_site_world_xy_speed_during_consecutive_load_mps"], 0.0,
        )

    def test_stream_rejects_gaps_tampering_and_invalid_target_values(self):
        for mode in ("missing_header", "bad_commit", "step_gap",
                     "nan_force", "missing_actuator"):
            rows = [header(), *synthetic_rows()]
            if mode == "missing_header":
                rows.pop(0)
            elif mode == "bad_commit":
                rows[0]["rl_commit"] = "unverified"
            elif mode == "step_gap":
                rows.pop(43)
            elif mode == "nan_force":
                rows[10]["contacts_original_solver"]["left"][
                    "normal_force_n"] = "not measured"
            elif mode == "missing_actuator":
                rows[11]["actuator_position_controls_rad"].pop("left_knee")
            with tempfile.TemporaryDirectory() as tmp:
                path = self._write(tmp, rows)
                with self.subTest(mode=mode), self.assertRaises(GroundTruthError):
                    _read_solver_trace(path)

    def test_p0b_must_confirm_negative_result_and_original_motor_authority(self):
        frames = synthetic_rows()
        for name, value in (
            ("stop_confirmed", False),
            ("motor_authority", "independent_script"),
            ("motion_memory_outcome", "translation_observed"),
        ):
            p0b = synthetic_p0b()
            p0b[name] = value
            with self.subTest(name=name), self.assertRaises(GroundTruthError):
                analyze_live_solver(p0b, frames)

    def test_cli_emits_json_only_for_full_native_trace(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = self._write(tmp, [header(), *synthetic_rows()])
            p0b = Path(tmp) / "p0b.json"
            p0b.write_text(json.dumps(synthetic_p0b()))
            out = Path(tmp) / "result.json"
            with contextlib.redirect_stdout(io.StringIO()):
                result = main([
                    "--input", str(stream), "--p0b", str(p0b),
                    "--output", str(out),
                ])
            self.assertEqual(0, result)
            value = json.loads(out.read_text())
            self.assertFalse(value["gait_validated"])
            self.assertEqual(260, value["all_frames"])

    def test_cli_rejects_partial_trace_without_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "truncated.jsonl"
            input_path.write_text('{"kind":"header"}\n')
            p0b = Path(tmp) / "p0b.json"
            p0b.write_text(json.dumps(synthetic_p0b()))
            output = Path(tmp) / "report.json"
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(["--input", str(input_path),
                             "--p0b", str(p0b), "--output", str(output)])
            self.assertEqual(1, code)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
