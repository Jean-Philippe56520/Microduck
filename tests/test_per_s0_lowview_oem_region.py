"""Positive/negative PER-S0 protocol tests; never load model/OEM renderer."""
from __future__ import annotations

from dataclasses import replace
import math
import unittest

from experiments.per_s0_lowview_oem_region import (
    CASES, OUTSIDE, BallGTError, gate, validate_preflight,
)


def geo():
    return [{
        "case": spec.name, "role": spec.role,
        "pose_static": True, "valid_geometry": True,
        "geom_pixels": 0 if spec.role == "empty_negative" else 1000,
        "geom_bbox_xyxy": None if spec.role == "empty_negative"
        else [10, 25, 80, 95],
    } for spec in CASES]


def scored():
    rows = []
    for spec in CASES:
        outside = spec.role == "outside_five"
        negative = spec.role == "empty_negative"
        caps = {}
        for cap in (1, 3, 5):
            caps[str(cap)] = {
                "region_count": 0 if negative else 1,
                "strong_ge_0_80": 0,
                "iou50": None if negative else False,
                "best_geom_iou": None if negative else 0.0,
            }
        if spec.name in OUTSIDE[:2]:
            caps["3"]["iou50"] = True
            caps["3"]["best_geom_iou"] = 0.75
        rows.append({
            "case": spec.name, "role": spec.role, "region_caps": caps,
            "top3_recovers_without_five_class_box":
                spec.name == OUTSIDE[0] if outside else False,
        })
    return rows


class TestPerS0Preflight(unittest.TestCase):
    def test_exact_five_positive_and_negative_pass(self):
        self.assertTrue(validate_preflight(geo()))
        self.assertEqual([x.role for x in CASES].count("outside_five"), 4)
        self.assertEqual([x.role for x in CASES].count("known_ball"), 1)

    def test_incomplete_reordered_and_geometry_inconsistent_refused(self):
        for bad in (geo()[:-1], geo()[::-1]):
            with self.assertRaises(BallGTError):
                validate_preflight(bad)
        cases = geo()
        cases[0]["geom_bbox_xyxy"] = None
        with self.assertRaises(BallGTError):
            validate_preflight(cases)

    def test_gt_missing_or_changed_pose_stops_without_inference(self):
        cases = geo()
        cases[1]["valid_geometry"] = False
        self.assertFalse(validate_preflight(cases))
        cases = geo()
        cases[0]["pose_static"] = False
        self.assertFalse(validate_preflight(cases))

    def test_invalid_negative_or_out_of_frame_bbox_is_rejected(self):
        cases = geo()
        cases[-1]["geom_pixels"] = 5
        with self.assertRaises(BallGTError):
            validate_preflight(cases)
        cases = geo()
        cases[1]["geom_bbox_xyxy"] = [0, 0, 361, 100]
        with self.assertRaises(BallGTError):
            validate_preflight(cases)


class TestPerS0FixedDecision(unittest.TestCase):
    def test_two_unknown_and_one_increment_with_negative_zero(self):
        decision = gate(scored())
        self.assertTrue(decision["functional_value_gate_met"])
        self.assertEqual(decision["unknown_region_top3_iou50"], 2)
        self.assertEqual(decision["unknown_incremental_over_five_class"], 1)
        self.assertEqual(decision["known_ball_top3_iou50"], False)

    def test_known_ball_cannot_substitute_for_unknown_object(self):
        rows = scored()
        rows[1]["region_caps"]["3"]["iou50"] = False
        rows[-2]["region_caps"]["3"]["iou50"] = True
        decision = gate(rows)
        self.assertEqual(decision["unknown_region_top3_iou50"], 1)
        self.assertFalse(decision["functional_value_gate_met"])

    def test_five_class_overlap_without_increment_stops(self):
        rows = scored()
        rows[0]["top3_recovers_without_five_class_box"] = False
        self.assertFalse(gate(rows)["functional_value_gate_met"])

    def test_high_score_empty_negative_stops(self):
        rows = scored()
        rows[-1]["region_caps"]["3"]["region_count"] = 1
        rows[-1]["region_caps"]["3"]["strong_ge_0_80"] = 1
        self.assertFalse(gate(rows)["functional_value_gate_met"])

    def test_reject_partial_or_nan_or_bad_case_order(self):
        with self.assertRaises(BallGTError):
            gate(scored()[:-1])
        with self.assertRaises(BallGTError):
            gate(scored()[::-1])
        rows = scored()
        rows[0]["region_caps"]["3"]["best_geom_iou"] = float("nan")
        with self.assertRaises(BallGTError):
            gate(rows)
        rows = scored()
        rows[0]["region_caps"]["3"]["region_count"] = 4
        with self.assertRaises(BallGTError):
            gate(rows)

    def test_malformed_flags_not_promoted_to_positive(self):
        rows = scored()
        rows[0]["top3_recovers_without_five_class_box"] = "true"
        with self.assertRaises(BallGTError):
            gate(rows)

    def test_case_specs_are_frozen_unique_and_no_motor_source(self):
        self.assertEqual(len({c.name for c in CASES}), 6)
        self.assertEqual(len([c for c in CASES if c.scene == "scene.xml"]), 1)
        self.assertTrue(all(c.role in {
            "outside_five", "known_ball", "empty_negative"} for c in CASES))
        self.assertTrue(all(c.free_body in (None, "obj_1", "ball_1")
                            for c in CASES))


if __name__ == "__main__":
    unittest.main()
