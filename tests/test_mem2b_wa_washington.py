"""MEM-2B-WA source-free synthetic contract, no media or model."""
from __future__ import annotations

import unittest

from microduck_companion.rgbd_washington_mem2b_eval import (
    StopStudy, choose, evaluate,
)


def fake_features(*, collision: bool = False) -> dict:
    out = {}
    for obj in (1, 2, 3):
        sig = bytes([100 if collision else obj * 60] * 64)
        for frame in range(2):
            out[obj, 1, frame] = sig
        for video in (2, 4):
            for frame in range(3):
                out[obj, video, frame] = sig
    return out


class WashingtonPreregTests(unittest.TestCase):
    def test_frozen_fraction_indices_before_any_image_read(self):
        self.assertEqual((72, 216), choose(tuple(range(288)), True))
        self.assertEqual((68, 136, 204), choose(tuple(range(273)), False))
        with self.assertRaises(StopStudy):
            choose((0, 0, 1), True)
        with self.assertRaises(StopStudy):
            choose((2, 1, 3), False)
        with self.assertRaises(StopStudy):
            choose((1, 2), False)

    def test_synthetic_distinct_known_and_unknown_gate_passes(self):
        report = evaluate(fake_features())
        self.assertEqual(36, report["correct"])
        self.assertEqual(18, report["unknown_rejected"])
        self.assertEqual(0, report["wrong_known"])
        self.assertEqual(0, report["false_unknown"])
        self.assertTrue(report["predeclared_gate_passed"])
        self.assertEqual(36, report["memory_off_positive_abstentions"])
        self.assertFalse(report["physical_identity_verified"])
        self.assertEqual(0, report["sqlite_real_media_writes"])
        self.assertEqual(3, len(report["folds"]))

    def test_synthetic_impostor_collision_abstains_and_fails_quality(self):
        report = evaluate(fake_features(collision=True))
        self.assertEqual(0, report["correct"])
        self.assertEqual(36, report["known_abstain"])
        self.assertEqual(18, report["unknown_rejected"])
        self.assertGreater(report["ambiguity"], 0)
        self.assertFalse(report["predeclared_gate_passed"])
        self.assertEqual("INSUFFICIENT_STOP_NO_TUNING", report["quality_verdict"])

    def test_missing_chosen_view_refuses_instead_of_substitution(self):
        source = fake_features()
        del source[1, 1, 1]
        with self.assertRaises(StopStudy):
            evaluate(source)


if __name__ == "__main__":
    unittest.main()
