"""COG-A2-P0 static contract fixtures, not proof of OEM visual performance.

All examples are fabricated numeric traces for positive/negative fail-closed
tests; actual OEM geometry and YOLOX are tested in a dedicated workflow.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import math
import unittest

try:
    import numpy as np
except ImportError:
    np = None

from microduck_companion.sim_ball_segmentation_gt import BallGTError
from experiments.cog_a2_p0_paired_vision import (
    CASES, CASE_NAMES, PairSpec, _fixed_camera,
    validate_preflight, score_pair, gate,
)


def _view(box, *, angle=0.):
    c, s = math.cos(angle), math.sin(angle)
    return {
        "bbox": box, "geom_pixels": 0 if box is None else 1000,
        "state_frozen": True, "camera_xyz": [0., 0., .12],
        "camera_rot": [[c, -s, 0.], [s, c, 0.], [0., 0., 1.]],
        "rgb_sha256": "a" * 64, "mask_sha256": "b" * 64,
    }


def geometry():
    rows = []
    for s in CASES:
        a = None if s.role == "empty_negative" else [100, 200, 140, 240]
        b = ([135, 200, 175, 240] if s.role == "positive"
             else a)
        v0 = _view(a)
        v1 = _view(b, angle=math.radians(20.) if s.role == "camera_negative" else 0.)
        camera_fixed, angle = _fixed_camera(v0, v1)
        rows.append({
            "case": s.name, "role": s.role, "scene": s.scene,
            "views": [v0, v1], "camera_fixed": camera_fixed,
            "camera_rotation_rad": angle,
            "gt_delta_px": (35. if s.role == "positive"
                            else None if s.role == "empty_negative" else 0.),
            "f2_or_motor_executed": False, "physical_rolling_observed": False,
        })
    return rows


def proposal(box, *, cls=56):
    return {
        "xyxy": tuple(float(x) for x in box),
        "score": .9,
        "untrusted_coco_class_index": cls,
    }


def scores(rows=None, *, positive_count=2, still_moving=False,
           empty_ball=False):
    if rows is None:
        rows = geometry()
    out = []
    for i, (spec, source) in enumerate(zip(CASES[:4], rows[:4])):
        a, b = [x["bbox"] for x in source["views"]]
        if spec.role == "positive" and i >= positive_count:
            preds = (None, None)
        elif spec.role == "still_negative":
            preds = (proposal(a),
                     proposal([a[0] + 40, a[1], a[2] + 40, a[3]])
                     if still_moving else proposal(a))
        elif spec.role == "empty_negative":
            preds = ((proposal([10, 20, 60, 70], cls=32), None)
                     if empty_ball else (None, None))
        else:
            preds = (proposal(a), proposal(b))
        out.append(score_pair(spec, source, preds))
    return out


@unittest.skipUnless(np is not None, "numpy available in dedicated OEM runner")
class PairedOpticalGateTests(unittest.TestCase):
    def test_preregistered_five_case_order_and_no_second_driver(self):
        self.assertEqual(CASE_NAMES, (
            "flat_ball_shift", "office_ball_shift", "flat_ball_still",
            "empty_floor", "camera_yaw_confounded"))
        self.assertEqual({c.scene for c in CASES},
                         {"scene_ball.xml", "scene_apartment.xml", "scene.xml"})
        self.assertEqual(CASES[-1].role, "camera_negative")
        self.assertTrue(validate_preflight(geometry()))

    def test_paired_candidate_positive_is_optical_only(self):
        rows = geometry()
        report = scores(rows)
        for item in report[:2]:
            self.assertTrue(item["positive_optical_gate"])
            self.assertTrue(item["both_views_iou50"])
            self.assertEqual(0., item["delta_abs_error_px"])
            self.assertFalse(item["physical_motion_or_identity_verified"])
            self.assertFalse(item["category_or_effect_promoted"])
        gate_result = gate(report, rows)
        self.assertTrue(gate_result["optic_value_gate_met"])
        self.assertFalse(gate_result["rolling_property_verified"])
        self.assertFalse(gate_result["a2_four_positives_eight_negatives_verified"])
        self.assertEqual(0, gate_result["motor_commands_issued"])

    def test_one_of_two_positive_is_minimum_and_both_missing_is_stop(self):
        self.assertTrue(gate(scores(positive_count=1), geometry())
                        ["optic_value_gate_met"])
        self.assertFalse(gate(scores(positive_count=0), geometry())
                         ["optic_value_gate_met"])

    def test_fake_shift_on_stationary_ball_is_not_a_success(self):
        rows = geometry()
        self.assertFalse(gate(scores(rows, still_moving=True), rows)
                         ["optic_value_gate_met"])

    def test_empty_frame_ball_category_candidate_is_negative(self):
        rows = geometry()
        self.assertFalse(gate(scores(rows, empty_ball=True), rows)
                         ["optic_value_gate_met"])

    def test_camera_rotation_is_refused_before_optical_candidate(self):
        rows = geometry()
        self.assertFalse(rows[-1]["camera_fixed"])
        self.assertGreater(rows[-1]["camera_rotation_rad"], .15)
        rows[-1]["camera_fixed"] = True
        with self.assertRaises(BallGTError):
            validate_preflight(rows)

    def test_missing_target_or_wrong_gt_delta_stops_without_inference(self):
        rows = geometry()
        rows[0]["views"][0]["geom_pixels"] = 0
        self.assertFalse(validate_preflight(rows))
        rows = geometry()
        rows[0]["gt_delta_px"] = 200.
        with self.assertRaises(BallGTError):
            validate_preflight(rows)

    def test_invalid_case_order_origin_claim_and_frozen_frame_refused(self):
        rows = geometry()
        for bad in (rows[:-1], list(reversed(rows))):
            with self.assertRaises(BallGTError):
                validate_preflight(bad)
        rows = geometry()
        rows[0]["physical_rolling_observed"] = True
        with self.assertRaises(BallGTError):
            validate_preflight(rows)
        rows = geometry()
        rows[0]["views"][0]["state_frozen"] = False
        with self.assertRaises(BallGTError):
            validate_preflight(rows)

    def test_wrong_camera_pose_without_flag_is_refused(self):
        rows = geometry()
        rows[0]["views"][1]["camera_rot"] = (
            _view([1, 2, 3, 4], angle=math.radians(12.))["camera_rot"])
        with self.assertRaises(BallGTError):
            validate_preflight(rows)

    def test_no_wrong_way_motion_with_same_displacement_magnitude(self):
        rows = geometry()
        # Both predictions could be individually broad yet pass IoU .50;
        # reverse direction must not be scored by matching |delta| alone.
        src = rows[0]
        good = (proposal(src["views"][0]["bbox"]),
                proposal(src["views"][1]["bbox"]))
        result = score_pair(CASES[0], src, good)
        self.assertTrue(result["positive_optical_gate"])
        bad = (proposal([135, 200, 175, 240]),
               proposal([100, 200, 140, 240]))
        wrong = score_pair(CASES[0], src, bad)
        self.assertEqual(35., wrong["candidate_centre_delta_px"])
        self.assertEqual(70., wrong["delta_abs_error_px"])
        self.assertFalse(wrong["positive_optical_gate"])

    def test_bad_score_candidates_and_forged_approval_are_rejected(self):
        src = geometry()[0]
        for bad in (
            {"xyxy": (0., 0., float("nan"), 10.), "score": .9,
             "untrusted_coco_class_index": 32},
            {"xyxy": (0., 0., 10., 10.), "score": 1.1,
             "untrusted_coco_class_index": 32},
            {"xyxy": (0., 0., 10., 10.), "score": .9,
             "untrusted_coco_class_index": "ball"},
            {"xyxy": (0., 0., 10., 10.), "score": .9,
             "untrusted_coco_class_index": 32, "verified_category": True},
        ):
            with self.subTest(bad=bad), self.assertRaises(BallGTError):
                score_pair(CASES[0], src, (bad, None))
        reports = scores()
        reports[0]["category_or_effect_promoted"] = True
        with self.assertRaises(BallGTError):
            gate(reports, geometry())

    def test_confounded_and_unknown_cannot_become_verified_contact(self):
        self.assertEqual(5, len(CASES))
        self.assertEqual(4, len(scores()))
        self.assertEqual(0, sum(
            int(x["physical_motion_or_identity_verified"]) for x in scores()))
        with self.assertRaises(BallGTError):
            gate(scores()[:-1], geometry())


if __name__ == "__main__":
    unittest.main()
