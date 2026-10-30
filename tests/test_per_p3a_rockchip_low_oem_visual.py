"""PER-P3A host-only contracts: no ONNX, camera, NPU or robot in unit tests."""
import unittest

try:
    import numpy as np
except ImportError:  # The repository-wide lightweight Python CI does not install numpy.
    np = None

from experiments.per_p3a_rockchip_low_oem_visual import (
    BallGTError, EXPECTED_SHAPES, PINNED_CASES, check_heads,
    check_predictions, score_case, visual_gate,
)


def box(cl, *, score=0.87, coords=None):
    return {
        "class_index": cl,
        "score": float(score),
        "xyxy": [float(v) for v in
                 (coords if coords is not None else [10, 10, 60, 60])],
    }


class TestPerP3AOutputContracts(unittest.TestCase):
    @unittest.skipUnless(np is not None, "numpy only in dedicated visual job")
    def test_official_nine_head_layout_accepted(self):
        heads = [np.zeros(shape, dtype=np.float32) for shape in EXPECTED_SHAPES]
        check_heads(heads)

    @unittest.skipUnless(np is not None, "numpy only in dedicated visual job")
    def test_reject_missing_wrong_shape_or_dtype(self):
        heads = [np.zeros(shape, dtype=np.float32) for shape in EXPECTED_SHAPES]
        for bad in (heads[:-1], heads[:-1] + [np.zeros((1, 1, 81, 81), np.float32)],
                    heads[:-1] + [np.zeros(EXPECTED_SHAPES[-1], np.int8)]):
            with self.subTest(length=len(bad)):
                with self.assertRaises(BallGTError):
                    check_heads(bad)

    @unittest.skipUnless(np is not None, "numpy only in dedicated visual job")
    def test_reject_non_finite_output(self):
        heads = [np.zeros(shape, dtype=np.float32) for shape in EXPECTED_SHAPES]
        heads[-1][0, 0, 0, 0] = np.nan
        with self.assertRaises(BallGTError):
            check_heads(heads)


    def test_reject_invalid_scored_box(self):
        check_predictions([box(32)])
        for candidate in (
            box(-1), box(80), box(32, score=1.1),
            box(32, score=float("nan")), box(32, coords=[60, 10, 10, 60]),
            box(32, coords=[0, 0, 361, 60]), box(32, coords=[10, -1, 60, 60]),
        ):
            with self.subTest(candidate=candidate):
                with self.assertRaises(BallGTError):
                    check_predictions([candidate])


class TestPerP3AVisualDecision(unittest.TestCase):
    def test_wrong_class_overlap_never_counts_as_recognition(self):
        result = score_case(
            "flat_ball_ahead", [10, 10, 60, 60], [box(56)])
        self.assertEqual(result["best_iou_any_class"], 1.0)
        self.assertEqual(result["best_iou_correct_class"], 0.0)
        self.assertFalse(result["recognised_iou50"])

    def test_correct_ball_and_chair_count(self):
        ball = score_case("flat_ball_ahead", [10, 10, 60, 60], [box(32)])
        chair = score_case("chair_near", [10, 10, 60, 60], [box(56)])
        self.assertTrue(ball["recognised_iou50"])
        self.assertTrue(chair["recognised_iou50"])

    def test_negative_reports_false_ball_and_rejects_gt(self):
        result = score_case("flat_ball_behind", None, [box(32), box(56)])
        self.assertEqual(result["false_sports_ball_detections"], 1)
        self.assertIsNone(result["recognised_iou50"])
        with self.assertRaises(BallGTError):
            score_case("flat_ball_behind", [10, 10, 60, 60], [])

    def test_pillar_cannot_be_promoted_to_known_category(self):
        result = score_case("vslam_pillar", [10, 10, 60, 60], [box(56)])
        self.assertIsNone(result["recognised_iou50"])
        self.assertEqual(result["best_iou_any_class"], 1.0)

    def test_visual_gate_positive_and_negative(self):
        cases = [
            score_case("flat_ball_ahead", [10, 10, 60, 60], [box(32)]),
            score_case("s2_far_right_yaw105", [10, 10, 60, 60], [box(32)]),
            score_case("chair_near", [10, 10, 60, 60], [box(56)]),
            score_case("vslam_pillar", [10, 10, 60, 60], []),
            score_case("flat_ball_behind", None, [box(56)]),
        ]
        self.assertEqual([r["case"] for r in cases],
                         [name for name, _ in PINNED_CASES])
        self.assertTrue(visual_gate(cases))
        with self.assertRaises(BallGTError):
            visual_gate(cases[:-1])
        with self.assertRaises(BallGTError):
            visual_gate(cases[::-1])
        mutated = [dict(x) for x in cases]
        mutated[-1]["false_sports_ball_detections"] = 1
        self.assertFalse(visual_gate(mutated))
        mutated[-1]["false_sports_ball_detections"] = 0
        mutated[1]["recognised_iou50"] = False
        self.assertFalse(visual_gate(mutated))


if __name__ == "__main__":
    unittest.main()
