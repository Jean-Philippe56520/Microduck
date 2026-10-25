"""P0c offline MuJoCo reconstruction: geometric proxy, NEVER live forces."""
import copy
import contextlib
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from microduck_companion.sim_contact_replay import (
    _validated_frames, _summary, replay_contact_geometry, main,
)
from microduck_companion.sim_flat_zone import (
    FLAT_SCENE_BLOB, GroundTruthError, RL_COMMIT,
)
from microduck_companion.sim_joint_trace import JOINT_NAMES
from microduck_companion.sim_walk_trial import WALK_SPEED_MPS, WALK_TICKS
from microduck_companion.sim_walk_compare import REST_SAMPLES


def frame(t, phase, idx):
    velocity = WALK_SPEED_MPS if phase == "walk" else 0.0
    return {
        "sim_time_s": t,
        "flat_scene_safe_area": True,
        "trunk_xyz_m": [0.02 + idx * 1e-5, .003, .116],
        "trunk_quat_wxyz": [1.0, 0.0, 0.0, 0.0],
        "positions_rad": [0.0] * len(JOINT_NAMES),
        "foot_contacts": None,
        "joint_targets_rad": None,
        "robotd": {
            "policy": phase,
            "applied_vx_vy_mps_vyaw_rad_s": [velocity, 0.0, 0.0],
        },
    }


def sample_trace():
    stand = [frame(1 + i*.1, "stand", i) for i in range(REST_SAMPLES)]
    moving = [frame(3 + i*.1, "walk", i) for i in range(WALK_TICKS)]
    moving[0]["robotd"]["policy"] = "stand"
    moving[0]["robotd"]["applied_vx_vy_mps_vyaw_rad_s"] = [0.0, 0.0, 0.0]
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
        "rest_trace": {
            "source": "pinned_official_mujoco_body_and_robotd",
            "mode": "passive_read_only",
            "rl_commit": RL_COMMIT,
            "flat_scene_git_blob": FLAT_SCENE_BLOB,
            "foot_contacts_available": False,
            "joint_targets_available": False,
            "joint_names_wire_order": list(JOINT_NAMES),
            "observations": stand,
        },
        "walk_trace": {"observations": moving},
    }


class FakeVector(list):
    def __setitem__(self, key, value):
        if isinstance(key, slice) and isinstance(value, (int, float)):
            value = [value] * len(self[key])
        super().__setitem__(key, value)


class FakeMjModel:
    def __init__(self):
        self.opt = types.SimpleNamespace(timestep=.002)
        self.names = {
            ("joint", "trunk_base_freejoint"): 0,
            ("geom", "floor"): 0,
            ("geom", "left_foot_collision"): 1,
            ("geom", "right_foot_collision"): 2,
            ("site", "left_foot"): 0,
            ("site", "right_foot"): 1,
        }
        self.jnt_qposadr = [0]
        for i, name in enumerate(JOINT_NAMES):
            if name != "mouth":
                self.names[("joint", name)] = len(self.jnt_qposadr)
                self.jnt_qposadr.append(7 + i - int(i > 9))
        self.nq = 21


class FakeMjData:
    def __init__(self, model):
        self.qpos = FakeVector([0.0] * model.nq)
        self.qvel = FakeVector([0.0] * model.nq)
        self.site_xpos = {0: [0., .015, .008], 1: [0., -.015, .009]}
        self.contact = []
        self.ncon = 0


class FakeMujoco:
    mjtObj = types.SimpleNamespace(
        mjOBJ_JOINT="joint", mjOBJ_GEOM="geom", mjOBJ_SITE="site"
    )
    MjModel = types.SimpleNamespace(from_xml_path=lambda _: FakeMjModel())
    MjData = FakeMjData
    calls = []

    @staticmethod
    def mj_name2id(model, kind, name):
        return model.names.get((kind, name), -1)

    @staticmethod
    def mj_forward(model, data):
        FakeMujoco.calls.append("mj_forward")
        # Two geometric near-contacts; ONE overlapping ground:
        data.contact = [
            types.SimpleNamespace(geom1=0, geom2=1, dist=-.001),
            types.SimpleNamespace(geom1=0, geom2=2, dist=.004),
        ]
        data.ncon = 2

    @staticmethod
    def mj_step(*args):
        raise AssertionError("offline replay MUST NOT step the physics")


class ContactReplayTests(unittest.TestCase):
    def test_valid_full_trace_is_accepted_without_gait_claim(self):
        stand, walk = _validated_frames(sample_trace())
        self.assertEqual(REST_SAMPLES, len(stand))
        self.assertEqual(WALK_TICKS, len(walk))

    def test_old_p0b_trace_lacking_quaternion_is_rejected(self):
        trace = sample_trace()
        for phase in ("rest_trace", "walk_trace"):
            trace[phase]["observations"][0].pop("trunk_quat_wxyz")
        with self.assertRaisesRegex(GroundTruthError, "quaternion"):
            _validated_frames(trace)

    def test_wrong_pinned_metadata_never_replayed(self):
        for section, key, value in (
            (None, "stop_confirmed", False),
            (None, "gait_validated", True),
            (None, "environment", "robot"),
            (None, "requested_walk_speed_mps", .22),
            (None, "motion_commands_sent_by_existing_j2e_trial", 23),
            ("rest_trace", "rl_commit", "unknown"),
            ("rest_trace", "flat_scene_git_blob", "modified"),
            ("rest_trace", "joint_names_wire_order", []),
        ):
            trace = sample_trace()
            target = trace if section is None else trace[section]
            target[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(GroundTruthError):
                _validated_frames(trace)

    def test_bad_pose_quaternion_and_unverified_claims_refused(self):
        for name, value in (
            ("trunk_quat_wxyz", None),
            ("trunk_quat_wxyz", [1., 0.]),
            ("trunk_quat_wxyz", [float("nan"), 0., 0., 1.]),
            ("trunk_quat_wxyz", [0., 0., 0., 0.]),
            ("positions_rad", [0.] * 14),
            ("trunk_xyz_m", [float("inf"), 0., .12]),
            ("foot_contacts", {"left": True}),
            ("joint_targets_rad", [0.] * 15),
        ):
            trace = sample_trace()
            trace["walk_trace"]["observations"][3][name] = value
            with self.subTest(name=name, value=value), self.assertRaises(GroundTruthError):
                _validated_frames(trace)

    def test_out_of_order_and_unsafe_frames_are_rejected(self):
        for key, value in (("sim_time_s", 1.0), ("flat_scene_safe_area", False)):
            trace = sample_trace()
            trace["walk_trace"]["observations"][3][key] = value
            with self.subTest(key=key), self.assertRaises(GroundTruthError):
                _validated_frames(trace)

    def test_reject_motion_in_reference_phase_and_wrong_policy(self):
        trace = sample_trace()
        trace["rest_trace"]["observations"][3]["robotd"][
            "applied_vx_vy_mps_vyaw_rad_s"] = [.12, 0., 0.]
        with self.assertRaisesRegex(GroundTruthError, "motion"):
            _validated_frames(trace)
        trace = sample_trace()
        trace["walk_trace"]["observations"][3]["robotd"]["policy"] = "sit"
        with self.assertRaises(GroundTruthError):
            _validated_frames(trace)

    def test_offline_replay_never_steps_or_sends_motor_commands(self):
        FakeMujoco.calls = []
        trace = sample_trace()
        with (patch("microduck_companion.sim_contact_replay.verify_flat_scene") as check,
              patch.dict(sys.modules, {"mujoco": FakeMujoco})):
            result = replay_contact_geometry(trace, "/dummy/pinned")
        check.assert_called_once()
        self.assertEqual(["mj_forward"] * (REST_SAMPLES + WALK_TICKS),
                         FakeMujoco.calls)
        self.assertTrue(result["no_motor_commands_sent"])
        self.assertFalse(result["original_live_solver_contacts_observed"])
        self.assertFalse(result["gait_validated"])
        self.assertFalse(result["traction_validated"])
        self.assertEqual("unknown", result["locomotion_root_cause"])
        self.assertEqual(REST_SAMPLES, result["stand"]["summary"]["frames"])
        self.assertEqual(WALK_TICKS, result["walk"]["summary"]["frames"])
        self.assertEqual(REST_SAMPLES, result["stand"]["summary"]
                         ["left_geometric_overlap_frames"])
        self.assertEqual(0, result["walk"]["summary"]
                         ["right_geometric_overlap_frames"])
        point = result["walk"]["frames"][0]
        self.assertIsNone(point["original_contact_forces_n"])
        self.assertIsNone(point["original_contact_pairs"])
        self.assertIsNone(point["original_joint_targets_rad"])
        self.assertAlmostEqual(-.001, point[
            "replayed_min_signed_contact_dist_m"]["left"])

    def test_modified_or_unknown_scene_is_refused_before_model_load(self):
        with (patch("microduck_companion.sim_contact_replay.verify_flat_scene",
                    side_effect=GroundTruthError("modified MJCF")),
              patch.dict(sys.modules, {"mujoco": FakeMujoco}),
              self.assertRaisesRegex(GroundTruthError, "modified")):
            replay_contact_geometry(sample_trace(), "/dummy")

    def test_summary_never_calls_absent_overlap_a_contact_force(self):
        fake = [
            {"replayed_ground_foot_candidate_pairs": {"left": 1, "right": 0},
             "replayed_ground_foot_overlapping_pairs": {"left": 1, "right": 0}},
            {"replayed_ground_foot_candidate_pairs": {"left": 0, "right": 0},
             "replayed_ground_foot_overlapping_pairs": {"left": 0, "right": 0}},
        ]
        summary = _summary(fake)
        self.assertEqual(1, summary["left_geometric_overlap_frames"])
        self.assertEqual(1, summary["no_geometric_overlap_frames"])
        self.assertEqual(0, summary["both_geometric_overlap_frames"])

    def test_cli_refuses_partial_trace_without_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "old.json"
            out = Path(tmp) / "replay.json"
            data.write_text(json.dumps({"schema_version": 1}))
            with contextlib.redirect_stderr(io.StringIO()):
                code = main(["--rl-root", tmp, "--input", str(data),
                             "--output", str(out)])
            self.assertEqual(1, code)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
