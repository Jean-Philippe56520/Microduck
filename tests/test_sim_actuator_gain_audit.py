"""P0e: audit effective native actuator gains without changing the OEM solver."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

# Existing P0d fixtures are deliberately imported as test helpers; they use
# fabricated, non-personal data and no actual motor or network connection.
from test_sim_live_solver import synthetic_p0b, synthetic_rows, header

from microduck_companion.sim_actuator_gain_audit import (
    NOMINAL_STAND_RATIO, NOMINAL_WALK_GAIN, _force_expectation,
    audit_native_actuators, main, validate_pre_step_audit,
)
from microduck_companion.sim_flat_zone import GroundTruthError
from microduck_companion.sim_live_solver_tap import (
    JOINT_NAMES, capture_actuators_before_step, install_solver_tap,
)


class Matrix:
    def __init__(self, rows):
        self.rows = rows

    def __getitem__(self, key):
        if isinstance(key, tuple):
            i, j = key
            return self.rows[i][j]
        return self.rows[key]


class Model:
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
        self.jnt_dofadr = [0]
        self.actuator_trnid = []
        for i, name in enumerate(JOINT_NAMES):
            joint_id = i + 1
            self.names[("joint", name)] = joint_id
            self.names[("actuator", name)] = i
            self.jnt_qposadr.append(7 + i)
            self.jnt_dofadr.append(6 + i)
            self.actuator_trnid.append([joint_id, 0])
        self.actuator_gainprm = Matrix([[.55, 0., 0.] for _ in JOINT_NAMES])
        self.actuator_biasprm = Matrix([[0., -.55, 0.] for _ in JOINT_NAMES])
        self.actuator_forcelimited = [True] * len(JOINT_NAMES)
        self.actuator_forcerange = [[-.96, .96] for _ in JOINT_NAMES]
        self.actuator_gear = Matrix([[1., 0., 0.] for _ in JOINT_NAMES])
        self.dof_damping = [0.] * 6 + [.053] * len(JOINT_NAMES)
        self.dof_frictionloss = [0.] * 6 + [.0048] * len(JOINT_NAMES)


class Data:
    def __init__(self):
        self.time = 0.
        self.ctrl = [.3] * len(JOINT_NAMES)
        self.qpos = [0.] * 7 + [.02] * len(JOINT_NAMES)
        self.qvel = [0.] * 6 + [.01] * len(JOINT_NAMES)
        self.actuator_force = [0.] * len(JOINT_NAMES)
        self.ncon = 2
        self.contact = [
            types.SimpleNamespace(geom1=0, geom2=1, dist=-.0002),
            types.SimpleNamespace(geom1=0, geom2=2, dist=-.0002),
        ]
        self.site_xpos = [[0., .05, -.001], [0., -.05, -.001]]


class Sink:
    def __init__(self):
        self.rows = []
    def submit(self, row):
        self.rows.append(row)


def make_mj(steps):
    class MJ:
        mjtObj = types.SimpleNamespace(
            mjOBJ_GEOM="geom", mjOBJ_SITE="site", mjOBJ_JOINT="joint",
            mjOBJ_ACTUATOR="actuator",
        )
        @staticmethod
        def mj_name2id(model, kind, name):
            return model.names.get((kind, name), -1)
        @staticmethod
        def mj_contactForce(model, data, idx, out):
            out[:] = [1., .05, .05, 0., 0., 0.]
        @staticmethod
        def mj_step(model, data):
            steps.append("native_step")
            # Genuine solver force at PRE-INTEGRATION pose; later qpos is not
            # the input to this force. No real physical robot.
            for i in range(len(JOINT_NAMES)):
                data.actuator_force[i] = (
                    model.actuator_gainprm[i, 0] * data.ctrl[i]
                    + model.actuator_biasprm[i, 1] * data.qpos[7 + i]
                )
                data.qpos[7 + i] += .003
            data.time += .005
    return MJ


def audited_rows():
    rows = synthetic_rows()
    for row in rows:
        phase = "stand" if row["sim_time_s"] < 2.1 else "walk"
        gain = NOMINAL_WALK_GAIN * (
            NOMINAL_STAND_RATIO if phase == "stand" else 1.)
        actuator = {}
        for name in JOINT_NAMES:
            ctrl = row["actuator_position_controls_rad"][name]
            pre_qpos = row["joint_angles_post_integration_rad"][name] - .003
            row["actuator_force_simulated_nm"][name] = gain * (ctrl - pre_qpos)
            actuator[name] = {
                "control_rad": ctrl,
                "position_rad": pre_qpos,
                "velocity_rad_s": .02,
                "gain_p_nm_per_rad": gain,
                "bias_position_nm_per_rad": -gain,
                "bias_velocity_nm_s_per_rad": 0.,
                "gear": 1.,
                "force_limited": True,
                "force_min_nm": -.96,
                "force_max_nm": .96,
                "joint_damping_nm_s": .053,
                "joint_frictionloss_nm": .0048,
            }
        row["pre_step_actuators"] = {
            "time_before_step_s": row["sim_time_s"] - .005,
            "actuators": actuator,
        }
    return rows


def write_stream(tmp, rows, *, audit=True):
    h = header()
    h["p0e_active_gain_pre_step"] = audit
    path = Path(tmp) / "solver.jsonl"
    path.write_text("\n".join(json.dumps(x) for x in [h, *rows]) + "\n")
    return path


class P0eCaptureTests(unittest.TestCase):
    def setUp(self):
        # The regular Python-only CI environment has no NumPy; the official
        # pinned MuJoCo environment does. Fake only the array constructor.
        mock_numpy = types.SimpleNamespace(
            zeros=lambda n, dtype=float: [0.] * n
        )
        patcher = patch.dict(sys.modules, {"numpy": mock_numpy})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_pre_step_epochs_capture_parameters_but_never_control_actuators(self):
        model, data, sink, original_calls = Model(), Data(), Sink(), []
        original_ctrl = list(data.ctrl)
        original_model_gain = [list(row) for row in model.actuator_gainprm.rows]
        mj = make_mj(original_calls)
        tap = install_solver_tap(Path("/fake"), mj=mj, writer=sink, audit=True)
        for _ in range(8):
            mj.mj_step(model, data)
        self.assertEqual(8, len(original_calls))
        self.assertEqual(8, tap.count)
        self.assertFalse(tap.disabled)
        self.assertEqual(original_ctrl, data.ctrl)
        self.assertEqual(original_model_gain, model.actuator_gainprm.rows)
        self.assertEqual(["header", "frame", "frame"],
                         [entry["kind"] for entry in sink.rows])
        self.assertTrue(sink.rows[0]["p0e_active_gain_pre_step"])
        for f in sink.rows[1:]:
            self.assertAlmostEqual(.005, f["sim_time_s"] -
                                   f["pre_step_actuators"]["time_before_step_s"])
            left = f["pre_step_actuators"]["actuators"]["left_knee"]
            self.assertEqual(.55, left["gain_p_nm_per_rad"])
            self.assertEqual(-.55, left["bias_position_nm_per_rad"])
            self.assertAlmostEqual(.55 * (
                left["control_rad"] - left["position_rad"]),
                f["actuator_force_simulated_nm"]["left_knee"])
            self.assertGreater(
                abs(f["joint_angles_post_integration_rad"]["left_knee"] -
                    left["position_rad"]), 0.002)

    def test_pre_step_probe_failure_never_prevents_native_physics(self):
        model, data, sink, calls = Model(), Data(), Sink(), []
        del model.actuator_gainprm
        mj = make_mj(calls)
        # Don't rely on the native-step stub's own actuator model when
        # injecting a missing-parameter failure in the diagnostic.
        native = mj.mj_step
        mj.mj_step = lambda model, data: (calls.append("native_step"),
                                          setattr(data, "time", data.time + .005))
        tap = install_solver_tap(Path("/fake"), mj=mj, writer=sink, audit=True)
        for _ in range(8):
            mj.mj_step(model, data)
        self.assertEqual(8, len(calls))
        self.assertTrue(tap.disabled)
        self.assertEqual(["error"], [x["kind"] for x in sink.rows])

    def test_p0d_unmodified_mode_never_reads_p0e_parameters(self):
        model, data, sink, calls = Model(), Data(), Sink(), []
        del model.actuator_gainprm
        mj = make_mj(calls)
        mj.mj_step = lambda model, data: (calls.append("native_step"),
                                          setattr(data, "time", data.time + .005))
        tap = install_solver_tap(Path("/fake"), mj=mj, writer=sink)
        for _ in range(4):
            mj.mj_step(model, data)
        self.assertFalse(tap.disabled)
        self.assertNotIn("pre_step_actuators", sink.rows[-1])
        self.assertFalse(sink.rows[0]["p0e_active_gain_pre_step"])


class P0eAnalysisTests(unittest.TestCase):
    def test_audit_matches_model_from_pre_step_not_from_future_qpos(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = validate_pre_step_audit(write_stream(tmp, audited_rows()))
            result = audit_native_actuators(synthetic_p0b(), rows)
        self.assertTrue(result["stand"]["all_force_samples_within_2_mNm"])
        self.assertTrue(result["walk"]["all_force_samples_within_2_mNm"])
        self.assertEqual(0, result["stand"]["total_force_clamped_samples"])
        self.assertEqual(0, result["walk"]["total_force_clamped_samples"])
        self.assertAlmostEqual(.44, result["stand"]["joints"]["left_knee"]
                               ["active_gain_median_nm_per_rad"])
        self.assertEqual(.55, result["walk"]["joints"]["right_knee"]
                         ["active_gain_median_nm_per_rad"])
        self.assertEqual(0., result["walk"]["max_force_formula_residual_nm"])
        self.assertFalse(result["gait_validated"])
        self.assertEqual("unknown", result["locomotion_root_cause"])

    def test_legacy_and_tampered_audit_frames_fail_closed(self):
        sample = audited_rows()
        for case in ("old", "missing_pre", "bad_clock", "gear", "force_limit",
                     "changed_control", "missing_joint", "wrong_bias", "nan_gain",
                     "false_force_limited"):
            rows = copy.deepcopy(sample)
            if case == "missing_pre":
                del rows[2]["pre_step_actuators"]
            elif case == "bad_clock":
                rows[2]["pre_step_actuators"]["time_before_step_s"] -= .02
            elif case == "gear":
                rows[2]["pre_step_actuators"]["actuators"]["left_knee"]["gear"] = 2.
            elif case == "force_limit":
                rows[2]["pre_step_actuators"]["actuators"]["left_knee"]["force_max_nm"] = 12.
            elif case == "changed_control":
                rows[2]["pre_step_actuators"]["actuators"]["left_knee"]["control_rad"] = 1.
            elif case == "missing_joint":
                del rows[2]["pre_step_actuators"]["actuators"]["left_knee"]
            elif case == "wrong_bias":
                rows[2]["pre_step_actuators"]["actuators"]["left_knee"]["bias_position_nm_per_rad"] = 0.
            elif case == "nan_gain":
                rows[2]["pre_step_actuators"]["actuators"]["left_knee"]["gain_p_nm_per_rad"] = "unknown"
            elif case == "false_force_limited":
                rows[2]["pre_step_actuators"]["actuators"]["left_knee"]["force_limited"] = False
            with tempfile.TemporaryDirectory() as tmp:
                path = write_stream(tmp, rows, audit=case != "old")
                with self.subTest(case=case), self.assertRaises(GroundTruthError):
                    validate_pre_step_audit(path)

    def test_force_clipping_is_reported_separately_from_gait_proof(self):
        rows = audited_rows()
        row = rows[140]
        joint = row["pre_step_actuators"]["actuators"]["left_knee"]
        joint["control_rad"] = 4.
        row["actuator_position_controls_rad"]["left_knee"] = 4.
        row["actuator_force_simulated_nm"]["left_knee"] = .96
        with tempfile.TemporaryDirectory() as tmp:
            checked = validate_pre_step_audit(write_stream(tmp, rows))
            result = audit_native_actuators(synthetic_p0b(), checked)
        self.assertEqual(1, result["walk"]["joints"]["left_knee"]
                         ["frames_force_clamped_by_model"])
        self.assertEqual(1, result["walk"]["joints"]["left_knee"]
                         ["frames_observed_force_near_limit"])
        self.assertFalse(result["gait_validated"])

    def test_large_force_residual_is_reported_not_silently_overridden(self):
        rows = audited_rows()
        rows[140]["actuator_force_simulated_nm"]["left_knee"] += .25
        with tempfile.TemporaryDirectory() as tmp:
            checked = validate_pre_step_audit(write_stream(tmp, rows))
            result = audit_native_actuators(synthetic_p0b(), checked)
        self.assertFalse(result["walk"]["all_force_samples_within_2_mNm"])
        self.assertGreater(result["walk"]["max_force_formula_residual_nm"], .2)

    def test_cli_refuses_incomplete_trace_and_keeps_output_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "p0b.json"
            trace.write_text(json.dumps(synthetic_p0b()))
            output = Path(tmp) / "audit.json"
            old = write_stream(tmp, audited_rows(), audit=False)
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(["--input", str(old), "--p0b", str(trace),
                             "--output", str(output)])
            self.assertEqual(1, code)
            self.assertFalse(output.exists())

    def test_cli_produces_structured_data_without_claiming_locomotion(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "p0b.json"
            trace.write_text(json.dumps(synthetic_p0b()))
            output = Path(tmp) / "audit.json"
            path = write_stream(tmp, audited_rows())
            with contextlib.redirect_stdout(io.StringIO()):
                status = main(["--input", str(path), "--p0b", str(trace),
                               "--output", str(output)])
            self.assertEqual(0, status)
            result = json.loads(output.read_text())
            self.assertFalse(result["motor_hardware_validated"])
            self.assertTrue(result["pre_step_snapshot_precedes_oem_mj_step"])
            self.assertFalse(result["gait_validated"])


if __name__ == "__main__":
    unittest.main()
