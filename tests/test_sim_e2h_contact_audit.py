"""SIM-E2H: fail-closed OFFLINE original-solver foot load analysis."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.sim_e2h_contact_audit import (
    main, summarize_support,
)
from microduck_companion.sim_flat_zone import (
    FLAT_SCENE_BLOB, GroundTruthError, RL_COMMIT,
)
from microduck_companion.sim_live_solver_tap import JOINT_NAMES
from microduck_companion.sim_policy_pair import PINNED_V8_SHA256


def _header():
    return {
        "kind": "header", "schema_version": 1,
        "source": "live_pinned_oem_mujoco_mj_step_tap",
        "rl_commit": RL_COMMIT,
        "flat_scene_git_blob": FLAT_SCENE_BLOB,
        "sample_every_n_physics_steps": 4,
        "model_timestep_s": 0.005,
        "capture_is_not_actuator_authority": True,
        "p0e_active_gain_pre_step": False,
    }


def _frame(i):
    left = (i // 12) % 2 == 0
    return {
        "kind": "frame", "step": (i+1)*4,
        "sim_time_s": (i+1)*.02,
        "trunk_xyz_after_integration_m": [i*.0015, 0., .12],
        "foot_sites_solver_cache_xyz_m": {
            "left": [i*.0015, .02, 0.],
            "right": [i*.0015, -.02, 0.],
        },
        "contacts_original_solver": {
            "left": {
                "pair_count": 1,
                "normal_force_n": 2.0 if left else .01,
                "tangent_force_norm_n": .01,
                "min_signed_distance_m": -.001,
            },
            "right": {
                "pair_count": 1,
                "normal_force_n": .01 if left else 2.0,
                "tangent_force_norm_n": .01,
                "min_signed_distance_m": -.001,
            },
        },
        "actuator_position_controls_rad": dict.fromkeys(JOINT_NAMES, 0.),
        "joint_angles_post_integration_rad": dict.fromkeys(JOINT_NAMES, 0.),
        "actuator_force_simulated_nm": dict.fromkeys(JOINT_NAMES, 0.),
        "capture_us": 37.,
        "live_solver_source": True,
    }


def _report():
    return {
        "experiment": "SIM-E2G_one_fixed_speed_onset_pinned_OEM_sim_only",
        "robotd_only_motor_authority": True,
        "network_slots_verified_from_live_robotd": True,
        "pinned_v8_sha256": dict(PINNED_V8_SHA256),
        "active_gait": {
            "walk": "alpha_walking.onnx", "stand": "alpha_stand.onnx",
        },
        "speed_mps": .30, "commands_sent": 12,
        "stop_confirmed": True, "gait_validated": False,
        "sampled_policy": {
            "policy_samples": 12, "walk_policy_samples": 12,
            "limited_by": [], "max_applied_vx_mps": .2999,
        },
        "sim_baseline_time_s": .3, "sim_after_stop_time_s": 1.6,
        "simulated_duration_s": 1.3, "net_xy_displacement_m": .095,
        "forward_x_m": .095, "lateral_y_m": 0.,
    }


class OriginalSolverSupportTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.folder = Path(t.name)
        self.solver = self.folder / "solver-tap.jsonl"
        self.e2g = self.folder / "sim-e2g-report.json"
        self.out = self.folder / "sim-e2h-contact-report.json"
        self.rows = [_header()] + [_frame(i) for i in range(100)]
        self.report = _report()
        self.write()

    def write(self):
        self.solver.write_text(
            "\n".join(json.dumps(x) for x in self.rows)+"\n")
        # NaN fixture is deliberately non-standard: validate the strict reader.
        self.e2g.write_text(json.dumps(self.report, allow_nan=False))

    def test_real_original_solver_payload_contract_not_a_gait(self):
        x = summarize_support(self.solver, self.e2g)
        self.assertEqual("contact_load_transfer_observed_not_stable_gait",
                         x["interpretation"])
        self.assertTrue(x["complete_original_solver_stream"])
        self.assertTrue(x["both_feet_were_unilaterally_loaded_at_different_samples"])
        self.assertTrue(x["loaded_contact_samples"]["left_only"] > 0)
        self.assertTrue(x["loaded_contact_samples"]["right_only"] > 0)
        self.assertFalse(x["gait_validated"])
        self.assertFalse(x["foot_slip_verified"])
        self.assertFalse(x["causal_low_speed_threshold_proven"])
        self.assertAlmostEqual(.095, x["trunk_e2g_reported_net_xy_m"])
        self.assertLess(abs(x["solver_minus_e2g_distance_m"]), .015)

    def test_deadman_does_not_erase_original_contacts_or_prove_control(self):
        self.report["sampled_policy"]["limited_by"] = ["deadman"]
        self.report["control_eligible"] = False
        self.write()
        result = summarize_support(self.solver, self.e2g)
        self.assertEqual(["deadman"], result["control_limited_by_any_sample"])
        self.assertFalse(result["e2g_control_eligible"])
        self.assertTrue(result["both_feet_were_unilaterally_loaded_at_different_samples"])
        self.assertFalse(result["motor_command_caused_displacement_proven"])
        self.assertFalse(result["gait_validated"])

    def test_slow_capture_explicitly_marked_confounded(self):
        for row in self.rows[1:]:
            row["capture_us"] = 2501.
        self.write()
        result = summarize_support(self.solver, self.e2g)
        self.assertTrue(result["observer_cost_confounded"])
        self.assertFalse(result["gait_validated"])

    def test_missing_or_untrusted_stop_policy_and_clock_refused(self):
        invalid = (
            ("stop_confirmed", False),
            ("commands_sent", 24),
            ("active_gait", {"walk": "velstand.onnx", "stand": None}),
            ("pinned_v8_sha256", {}),
            ("sim_after_stop_time_s", 0.0),
            ("sim_baseline_time_s", -1.0),
            ("gait_validated", True),
        )
        for name, value in invalid:
            with self.subTest(name=name):
                self.report[name] = value
                self.write()
                with self.assertRaises(GroundTruthError):
                    summarize_support(self.solver, self.e2g)
                self.report = _report()

    def test_missing_frames_wrong_source_and_contact_forces_rejected(self):
        # Full stream, including frames outside the phase, must be coherent.
        cases = (
            lambda: self.rows[15].update({"step": 61}),
            lambda: self.rows[0].update({"rl_commit": "wrong"}),
            lambda: self.rows[40]["contacts_original_solver"]["left"].update(
                {"normal_force_n": -0.1}),
            lambda: self.rows[40]["contacts_original_solver"]["right"].update(
                {"normal_force_n": 0.2, "pair_count": 0}),
            lambda: self.rows[30].update({"capture_us": float("nan")}),
        )
        for mutate in cases:
            with self.subTest(mutate=str(mutate)):
                self.rows = [_header()] + [_frame(i) for i in range(100)]
                mutate()
                self.write()
                with self.assertRaises(GroundTruthError):
                    summarize_support(self.solver, self.e2g)

    def test_unnaturally_mismatched_ground_truth_is_not_gait(self):
        self.report["net_xy_displacement_m"] = .01
        self.write()
        with self.assertRaisesRegex(GroundTruthError, "disagrees"):
            summarize_support(self.solver, self.e2g)

    def test_false_supported_condition_does_not_invent_transfer(self):
        for row in self.rows[1:]:
            row["contacts_original_solver"]["left"]["normal_force_n"] = 2.
            row["contacts_original_solver"]["right"]["normal_force_n"] = 2.
        self.write()
        x = summarize_support(self.solver, self.e2g)
        self.assertFalse(x["both_feet_were_unilaterally_loaded_at_different_samples"])
        self.assertEqual("no_independent_unilateral_load_transfer_evidence",
                         x["interpretation"])

    def test_missing_coverage_or_stale_file_is_refused(self):
        self.rows = self.rows[:45]
        self.write()
        with self.assertRaisesRegex(GroundTruthError, "cover"):
            summarize_support(self.solver, self.e2g)

    def test_cli_requires_isolated_output_and_real_source(self):
        self.assertEqual(0, main([
            "--trace", str(self.solver), "--e2g", str(self.e2g),
            "--output", str(self.out),
        ]))
        self.assertTrue(self.out.is_file())
        with self.assertRaises(GroundTruthError):
            # summary refuses a broken source independently of CLI.
            self.solver.write_text("{}\n")
            summarize_support(self.solver, self.e2g)
        self.assertEqual(1, main([
            "--trace", str(self.solver), "--e2g", str(self.e2g),
            "--output", str(self.out),
        ]))

    def test_no_motor_network_or_memory_api_usage(self):
        with patch("socket.create_connection", side_effect=AssertionError("no net")), \
             patch("socket.socket", side_effect=AssertionError("no socket")):
            self.assertTrue(summarize_support(self.solver, self.e2g)
                            ["complete_original_solver_stream"])


if __name__ == "__main__":
    unittest.main()
