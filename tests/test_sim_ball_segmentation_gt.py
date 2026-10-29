"""SIM-VIS-B: positive/negative oracle geometry and one-to-one matching."""
import importlib.util
import unittest

from microduck_companion.cata2_bbox_eval import Box
from microduck_companion.sim_ball_segmentation_gt import (
    BallGTError, compare_boxes, visible_geom_bbox, FRAME_H, FRAME_W,
)

HAS_NUMPY = importlib.util.find_spec("numpy") is not None


class BallGTContractTests(unittest.TestCase):
    def test_correct_single_50_percent_iou_match(self):
        gt = [Box("sports_ball", (10, 20, 40, 50))]
        proposals = (Box("sports_ball", (11, 21, 39, 49), 0.7),)
        outcome = compare_boxes(gt, proposals)
        self.assertEqual(outcome["matched_iou_at_least_0_50"], 1)
        self.assertEqual(outcome["false_negatives"], 0)
        self.assertEqual(outcome["false_positives"], 0)

    def test_one_proposal_cannot_match_two_balls(self):
        gt = [
            Box("sports_ball", (10, 20, 40, 50)),
            Box("sports_ball", (10, 20, 40, 50)),
        ]
        proposals = (Box("sports_ball", (11, 21, 39, 49), 0.8),)
        outcome = compare_boxes(gt, proposals)
        self.assertEqual(outcome["matched_iou_at_least_0_50"], 1)
        self.assertEqual(outcome["false_negatives"], 1)

    def test_negative_scene_ball_proposal_is_false_positive(self):
        outcome = compare_boxes(
            [], (Box("sports_ball", (0, 0, 30, 30), 0.8),)
        )
        self.assertEqual(outcome["false_positives"], 1)
        self.assertEqual(outcome["ground_truth_count"], 0)

    def test_wrong_category_does_not_count_as_ball_match(self):
        outcome = compare_boxes(
            [Box("sports_ball", (10, 10, 40, 40))],
            (Box("cat", (10, 10, 40, 40), 0.9),),
        )
        self.assertEqual(outcome["matched_iou_at_least_0_50"], 0)
        self.assertEqual(outcome["false_negatives"], 1)

    def test_subthreshold_overlap_does_not_match(self):
        outcome = compare_boxes(
            [Box("sports_ball", (10, 10, 40, 40))],
            (Box("sports_ball", (30, 30, 60, 60), 0.9),),
        )
        self.assertEqual(outcome["matched_iou_at_least_0_50"], 0)
        self.assertEqual(outcome["false_negatives"], 1)
        self.assertEqual(outcome["false_positives"], 1)

    @unittest.skipUnless(HAS_NUMPY, "numpy optional in general Python CI")
    def test_segmentation_geom_id_type_and_exclusive_pixel_boundary(self):
        import numpy as np
        seg = np.full((FRAME_W, FRAME_H, 2), -1, dtype=np.int32)
        seg[20:30, 50:70, 0] = 9
        seg[20:30, 50:70, 1] = 5
        self.assertEqual(
            visible_geom_bbox(seg, geom_id=9, geom_type=5),
            ([50, 20, 70, 30], 200),
        )
        # Same ID with a different object type is not a match.
        self.assertEqual(
            visible_geom_bbox(seg, geom_id=9, geom_type=4),
            (None, 0),
        )
        self.assertEqual(
            visible_geom_bbox(seg, geom_id=10, geom_type=5),
            (None, 0),
        )

    @unittest.skipUnless(HAS_NUMPY, "numpy optional in general Python CI")
    def test_segmentation_wrong_geometry_or_float_is_rejected(self):
        import numpy as np
        with self.assertRaises(BallGTError):
            visible_geom_bbox(np.zeros((FRAME_H, FRAME_W, 2), np.int32),
                              geom_id=9, geom_type=5)
        with self.assertRaises(BallGTError):
            visible_geom_bbox(np.zeros((FRAME_W, FRAME_H, 2), np.float32),
                              geom_id=9, geom_type=5)


if __name__ == "__main__":
    unittest.main()
