"""P0j: synthetic offline samples and fail-closed archived-trace gates.

No unit test starts MuJoCo or sends a motor request. The real P0e archive is
consumed separately by the opt-in P0j read-only GitHub Actions workflow.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.sim_p0j_load_transfer import (
    EXPECTED_SHA256, LOADED_N, OfflineTraceError, _read_exact,
    _strict_json, _windows, audit_files, main, summarize_window,
)


def frame(t: float, left: float, right: float, *, x: float = 0.) -> dict:
    return {
        "kind": "frame", "step": int(round(t / .005)),
        "sim_time_s": t, "live_solver_source": True,
        "trunk_xyz_after_integration_m": [x, 0., .12],
        "contacts_original_solver": {
            "left": {"pair_count": 1 if left else 0,
                     "normal_force_n": left, "tangent_force_norm_n": .1},
            "right": {"pair_count": 1 if right else 0,
                      "normal_force_n": right, "tangent_force_norm_n": .2},
        },
        "foot_sites_solver_cache_xyz_m": {
            "left": [x + .04, .05, 0.],
            "right": [x + .04, -.05, 0.]},
    }


class WindowTests(unittest.TestCase):
    def test_both_loaded_asymmetric_share_is_measurement_not_causality(self):
        observations = [frame(1+i*.02, 3., 5., x=.001*i) for i in range(5)]
        report = summarize_window(observations)
        self.assertEqual(5, report["frames"])
        self.assertEqual(
            {"both": 5, "left_only": 0, "right_only": 0, "neither": 0},
            report["contact_load_0_1n"])
        self.assertAlmostEqual(.375, report["left_share_mean"])
        self.assertAlmostEqual(.004, report["trunk_world_xy_net_m"])
        self.assertAlmostEqual(
            .004, report["feet"]["left"]["site_cached_world_xy_path_m"])
        self.assertEqual(
            0, report["left_share_crosses_half_between_adjacent_samples"])

    def test_classification_is_strictly_above_0_1_n(self):
        observations = [frame(1, LOADED_N, 2.),
                        frame(1.02, 2., LOADED_N)]
        result = summarize_window(observations)
        self.assertEqual(0, result["contact_load_0_1n"]["both"])
        self.assertEqual(1, result["contact_load_0_1n"]["left_only"])
        self.assertEqual(1, result["contact_load_0_1n"]["right_only"])

    def test_load_share_crossings_do_not_mean_single_support(self):
        observations = [frame(1, 4., 2.), frame(1.02, 2., 4.),
                        frame(1.04, 4., 2.)]
        result = summarize_window(observations)
        self.assertEqual(
            2, result["left_share_crosses_half_between_adjacent_samples"])
        self.assertEqual(3, result["contact_load_0_1n"]["both"])

    def test_no_load_refuses_undefined_normal_share(self):
        with self.assertRaisesRegex(OfflineTraceError, "share undefined"):
            summarize_window([frame(1, 0, 0), frame(1.02, 0, 0)])

    def test_discontinuous_solver_clock_refused(self):
        with self.assertRaisesRegex(OfflineTraceError, "clock reset"):
            summarize_window([frame(1, 2, 2), frame(1.08, 2, 2)])

    def test_nan_infinity_negative_bool_string_and_missing_forces_fail(self):
        for invalid in (float("nan"), float("inf"), -1., True, "3"):
            observations = [frame(1, 2, 2), frame(1.02, 2, 2)]
            observations[1]["contacts_original_solver"]["left"]["normal_force_n"] = invalid
            with self.subTest(invalid=str(invalid)), self.assertRaises(OfflineTraceError):
                summarize_window(observations)
        observations = [frame(1, 2, 2), frame(1.02, 2, 2)]
        del observations[1]["contacts_original_solver"]
        with self.assertRaises(OfflineTraceError):
            summarize_window(observations)

    def test_force_without_original_contact_pair_refused(self):
        observations = [frame(1, 2, 2), frame(1.02, 2, 2)]
        observations[1]["contacts_original_solver"]["right"]["pair_count"] = 0
        with self.assertRaisesRegex(OfflineTraceError, "without contact"):
            summarize_window(observations)


class ProvenanceTests(unittest.TestCase):
    def test_unknown_digest_and_edited_artifact_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"solver-tap.jsonl"
            path.write_bytes(b'{"kind":"header"}\n')
            with self.assertRaisesRegex(OfflineTraceError, "digest mismatch"):
                _read_exact(path)
            with self.assertRaisesRegex(OfflineTraceError, "unrecognized"):
                _read_exact(Path(folder)/"unknown.json")

    def test_nonfinite_and_duplicate_json_properties_refused(self):
        for source in ('{"a":NaN}', '{"a":1,"a":2}', '{"x":Infinity}'):
            with self.subTest(source=source), self.assertRaises(OfflineTraceError):
                _strict_json(source)

    def test_phase_windows_and_completed_stop_are_required(self):
        analysis = {
            "source": "original_live_pinned_oem_mujoco_solver",
            "schema_version": 1, "original_p0b_stop_confirmed": True,
            "gait_validated": False, "locomotion_root_cause": "unknown",
            "provenance": {
                "rl_commit": "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3",
                "flat_scene_git_blob": "a3848be52113a50138d54921748733f09488d496",
                "full_stream_validated": True,
                "same_world_as_official_robotd": True,
            },
            "phase_windows_from_p0b_10hz": {
                "stand": [1., 2.], "walk": [3., 4.],
            },
        }
        comparison = {
            "environment": "pinned_official_mujoco_only",
            "stop_confirmed": True,
            "motion_commands_sent_by_existing_j2e_trial": 24,
            "requested_walk_speed_mps": .12,
            "gait_validated": False,
            "motion_memory_outcome": "no_progress_observed",
            "measured_walk_displacement_m": .002,
        }
        self.assertEqual((3., 4.), _windows(analysis, comparison)["walk"])
        for key, value in (
            ("stop_confirmed", False),
            ("measured_walk_displacement_m", .05),
            ("gait_validated", True),
        ):
            wrong = comparison.copy()
            wrong[key] = value
            with self.subTest(key=key), self.assertRaises(OfflineTraceError):
                _windows(analysis, wrong)
        wrong = json.loads(json.dumps(analysis))
        wrong["phase_windows_from_p0b_10hz"]["walk"] = [1.5, 2.5]
        with self.assertRaisesRegex(OfflineTraceError, "overlapping"):
            _windows(wrong, comparison)

    def test_incomplete_inputs_cannot_create_report(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            output = base/"report.json"
            args = [
                "--solver-tap", str(base/"solver-tap.jsonl"),
                "--solver-analysis", str(base/"solver-analysis.json"),
                "--walk-comparison", str(base/"walk-comparison.json"),
                "--output", str(output),
            ]
            with patch("sys.stderr"):
                self.assertEqual(1, main(args))
            self.assertFalse(output.exists())

    def test_source_pinning_and_no_motor_runtime_api(self):
        self.assertEqual(3, len(EXPECTED_SHA256))
        self.assertTrue(all(len(digest) == 64 for digest in EXPECTED_SHA256.values()))
        from microduck_companion import sim_p0j_load_transfer as module
        import inspect
        source = inspect.getsource(module)
        for forbidden in (
            "socket.socket(", "robot.move", "robot.stop",
            "subprocess.run(", "mujoco.mj_step(",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
