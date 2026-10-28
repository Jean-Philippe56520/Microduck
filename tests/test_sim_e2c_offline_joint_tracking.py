"""SIM-E2-C: only fabricated fixture frames; no sockets, simulator or motor."""
from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.sim_p0j_load_transfer import OfflineTraceError
from microduck_companion import sim_e2c_offline_joint_tracking as p0k


def fixture(n=3):
    frames = []
    for index in range(n):
        actuators = {}
        for name in p0k.SELECTED_JOINTS:
            sign = -1 if name.startswith("left") else 1
            actuators[name] = {
                "control_rad": sign * 0.1 * (index + 1),
                "position_rad": sign * 0.05,
            }
        frames.append({
            "sim_time_s": (index + 1) * 0.02,
            "pre_step_actuators": {"actuators": actuators},
        })
    return frames


class PhaseSummaryTests(unittest.TestCase):
    def test_signed_offsets_ranges_and_mirrored_target_correlation(self):
        report = p0k.summarize_phase(fixture())
        self.assertEqual(3, report["frames"])
        left = report["joints"]["left_hip_roll"]
        right = report["joints"]["right_hip_roll"]
        self.assertAlmostEqual(-math.degrees(.15),
                               left["mean_signed_control_minus_position_deg"])
        self.assertAlmostEqual(math.degrees(.15),
                               right["mean_signed_control_minus_position_deg"])
        self.assertAlmostEqual(math.degrees(.2),
                               left["control_excursion_deg"])
        self.assertAlmostEqual(0, left["position_excursion_deg"])
        self.assertAlmostEqual(-1.0,
                               report["hip_roll_left_right_control_correlation"])
        self.assertIsNone(report["hip_roll_left_right_position_correlation"])

    def test_insufficient_bad_or_duplicate_clock_fails(self):
        cases = [
            [],
            fixture(1),
            [dict(f, sim_time_s=0.02) for f in fixture()],
            [{**f, "sim_time_s": f["sim_time_s"] + (0.03 if i else 0)}
             for i, f in enumerate(fixture())],
        ]
        for frames in cases:
            with self.subTest(count=len(frames)), self.assertRaises(OfflineTraceError):
                p0k.summarize_phase(frames)

    def test_missing_nonfinite_bool_or_wrong_joint_fails(self):
        for mutation in ("no_pre", "no_joint", "nan", "inf", "bool"):
            frames = fixture()
            if mutation == "no_pre":
                frames[1].pop("pre_step_actuators")
            elif mutation == "no_joint":
                frames[1]["pre_step_actuators"]["actuators"].pop("left_knee")
            else:
                vals = {"nan": float("nan"), "inf": float("inf"), "bool": True}
                frames[1]["pre_step_actuators"]["actuators"]["left_hip_roll"][
                    "control_rad"] = vals[mutation]
            with self.subTest(mutation=mutation), self.assertRaises(OfflineTraceError):
                p0k.summarize_phase(frames)

    def test_nonstationary_target_does_not_imply_nonzero_body_motion(self):
        frames = fixture()
        # The summary does not invent trunk displacement or contact observations.
        result = p0k.summarize_phase(frames)
        self.assertNotIn("trunk_displacement", result)
        self.assertNotIn("foot_contact", result)
        self.assertGreater(result["joints"]["left_knee"]["control_excursion_deg"], 0)


class ArchiveGateTests(unittest.TestCase):
    def test_archive_hash_rejection_precedes_all_solver_processing(self):
        with patch.object(p0k, "_read_exact",
                          side_effect=OfflineTraceError("source digest mismatch")):
            with patch.object(p0k, "_verified_frames") as parse:
                with patch.object(p0k, "validate_pre_step_audit") as validate:
                    with self.assertRaisesRegex(OfflineTraceError, "digest mismatch"):
                        p0k.audit_files(Path("solver-tap.jsonl"),
                                        Path("solver-analysis.json"),
                                        Path("walk-comparison.json"))
                    parse.assert_not_called()
                    validate.assert_not_called()

    def test_wrong_frame_count_is_never_silently_accepted(self):
        stand = fixture()
        for i, row in enumerate(stand):
            row["sim_time_s"] = 12.20 + i * .02
        with patch.object(p0k, "_read_exact", return_value=b"{}"):
            with patch.object(p0k, "_verified_frames", return_value=stand):
                with patch.object(p0k, "validate_pre_step_audit",
                                  return_value=stand):
                    with patch.object(p0k, "_strict_json",
                                      side_effect=[{"stand": {"frames": 79}},
                                                   {"measured_walk_displacement_m": .002}]):
                        with patch.object(p0k, "_windows",
                                          return_value={
                                              "stand": (12.20, 13.76),
                                              "walk": (14.26, 16.78)}):
                            with self.assertRaisesRegex(
                                    OfflineTraceError, "missing original P0e stand window"):
                                p0k.audit_files(Path("solver-tap.jsonl"),
                                                Path("solver-analysis.json"),
                                                Path("walk-comparison.json"))

    def test_cli_does_not_write_when_input_is_untrusted(self):
        with tempfile.TemporaryDirectory() as td:
            destination = Path(td) / "report.json"
            with patch.object(p0k, "audit_files",
                              side_effect=OfflineTraceError("changed source")):
                status = p0k.main([
                    "--solver-tap", "solver-tap.jsonl",
                    "--solver-analysis", "solver-analysis.json",
                    "--walk-comparison", "walk-comparison.json",
                    "--output", str(destination),
                ])
            self.assertEqual(1, status)
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
