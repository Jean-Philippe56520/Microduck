"""PER-P4L1: contract tests only; no camera, models or MuJoCo required."""
from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unittest

from experiments.per_p4l1_yolo26_lowview import (
    BallGTError, CASES, FRAME_H, FRAME_W, box_iou, decision,
    mask_vs_rectangle, verify_preflight, verify_weight,
)


def geometry():
    return [{
        "case": c.name, "scene": c.scene, "target_geom": c.geom,
        "visible_target_pixels": 1000 if c.geom else 0,
        "gt_bbox": [30, 80, 130, 190] if c.geom else None,
        "static_qpos_time": True,
    } for c in CASES]


def paired():
    before, after = [], []
    for idx, c in enumerate(CASES):
        if c.geom is None:
            before.append({"case": c.name, "prediction_count": 0,
                           "five_class_strong_claims": 0})
            after.append({"case": c.name, "prediction_count": 0,
                          "five_class_strong_claims": 0})
        else:
            before.append({"case": c.name, "prediction_count": 1,
                           "region_iou50": idx == 0})
            after.append({"case": c.name, "prediction_count": 1,
                          "region_iou50": idx != 2,
                          "mask_better": idx != 2})
    return before, after


class LowViewFixtureContract(unittest.TestCase):
    def test_preregistered_cases_immutable_and_distinct(self):
        self.assertEqual(tuple(c.name for c in CASES),
                         ("cube_south_living", "chair_near",
                          "pillar_cyan_near", "empty_floor_yaw27"))
        self.assertEqual(len(set(c.name for c in CASES)), 4)
        self.assertAlmostEqual(CASES[-1].yaw, math.radians(27))
        self.assertEqual(CASES[-1].scene, "scene.xml")
        self.assertFalse(any(c.name == "ball_hidden_by_chair" for c in CASES))

    def test_three_positive_plus_empty_source_geometry_passes(self):
        self.assertTrue(verify_preflight(geometry()))

    def test_malformed_or_reordered_geometry_rejected(self):
        for rows in (geometry()[:-1], geometry()[::-1]):
            with self.assertRaises(BallGTError):
                verify_preflight(rows)
        rows = geometry()
        rows[-1]["visible_target_pixels"] = 15
        with self.assertRaises(BallGTError):
            verify_preflight(rows)
        rows = geometry()
        rows[1]["gt_bbox"] = [0, 0, FRAME_H + 1, FRAME_W]
        with self.assertRaises(BallGTError):
            verify_preflight(rows)
        rows = geometry()
        rows[0]["static_qpos_time"] = False
        with self.assertRaises(BallGTError):
            verify_preflight(rows)

    def test_box_iou_positive_and_negative(self):
        self.assertAlmostEqual(box_iou((10, 10, 60, 60),
                                       (10, 10, 60, 60)), 1.)
        self.assertEqual(box_iou((10, 10, 60, 60),
                                 (90, 90, 130, 120)), 0.)
        for invalid in ((0, 0, 0, 1), (float("nan"), 0, 20, 20)):
            with self.assertRaises(BallGTError):
                box_iou(invalid, (0, 0, 20, 20))

    def test_exact_predicted_mask_can_beat_matched_rectangle(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("NumPy only needed for dedicated OEM workflow")
        truth = np.zeros((FRAME_W, FRAME_H), dtype=bool)
        truth[100:120, 40:60] = True
        predicted = truth.astype(np.float32)
        mask, rectangle = mask_vs_rectangle(
            truth, predicted, (30., 90., 70., 130.))
        self.assertEqual(mask, 1.)
        self.assertLess(rectangle, mask)

    def test_wrong_mask_or_unstable_mask_rejected(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("NumPy only needed for dedicated OEM workflow")
        truth = np.zeros((FRAME_W, FRAME_H), dtype=bool)
        with self.assertRaises(BallGTError):
            mask_vs_rectangle(truth, np.zeros((20, 20)), (0, 0, 30, 30))
        faulty = np.zeros_like(truth, dtype=np.float32)
        faulty[0, 0] = float("nan")
        with self.assertRaises(BallGTError):
            mask_vs_rectangle(truth, faulty, (0, 0, 30, 30))

    def test_successful_value_gate_does_not_promote_model(self):
        a, b = paired()
        result = decision(a, b)
        self.assertTrue(result["lowview_candidate_gate_met"])
        self.assertEqual(result["segmenter_regions_at_iou50_of_3"], 2)
        self.assertIn("not_robot", result["status"])

    def test_low_recall_regression_mask_or_negative_stops(self):
        for variant in ("low_recall", "regression", "mask_fail", "negative"):
            a, b = paired()
            if variant == "low_recall":
                b[1]["region_iou50"] = False
                b[1]["mask_better"] = None
            if variant == "regression":
                a[0]["region_iou50"] = True
                a[1]["region_iou50"] = True
                a[2]["region_iou50"] = True
            if variant == "mask_fail":
                b[1]["mask_better"] = False
            if variant == "negative":
                b[-1]["five_class_strong_claims"] = 1
            with self.subTest(variant=variant):
                self.assertFalse(decision(a, b)["lowview_candidate_gate_met"])

    def test_partial_or_forged_result_rejected(self):
        a, b = paired()
        for left, right in ((a[:-1], b), (a, list(reversed(b)))):
            with self.assertRaises(BallGTError):
                decision(left, right)
        a, b = paired()
        b[0]["mask_better"] = "yes"
        with self.assertRaises(BallGTError):
            decision(a, b)
        a, b = paired()
        b[-1]["five_class_strong_claims"] = -1
        with self.assertRaises(BallGTError):
            decision(a, b)

    def test_fake_or_symlinked_model_refused(self):
        with tempfile.TemporaryDirectory() as work:
            p = Path(work) / "yolo26n-seg.pt"
            p.write_bytes(b"fake")
            with self.assertRaises(BallGTError):
                verify_weight(p)
            p.unlink()
            p.symlink_to(Path(work) / "missing")
            with self.assertRaises(BallGTError):
                verify_weight(p)


if __name__ == "__main__":
    unittest.main()
