"""Unit checks for the existing 80-class YOLOX region hypothesis decoder."""
import unittest

import numpy as np

from microduck_companion.yolox_attention_candidates import (
    _iou, decode_candidates,
)


def synthetic_head():
    raw = np.zeros((1, 3549, 85), np.float32)
    for i, xy, cls, obj in (
        (530, (10, 10), 49, .95),
        (1060, (20, 20), 0, .85),
        (1590, (30, 30), 32, .75),
    ):
        raw[0, i, 2:4] = np.log(20 / 8)
        raw[0, i, 4] = obj
        raw[0, i, 5 + cls] = .9
    # Same location as top proposal, should be NMS-removed.
    raw[0, 531, 0] = -1
    raw[0, 531, 2:4] = np.log(20 / 8)
    raw[0, 531, 4] = .6
    raw[0, 531, 5 + 49] = .9
    return raw


class CandidateRegionTests(unittest.TestCase):
    def test_three_ranked_different_classes_and_agnostic_nms(self):
        raw = synthetic_head()
        items = decode_candidates(raw, width=416, height=416,
                                  max_results=5)
        self.assertEqual(len(items), 3)
        self.assertEqual([r["untrusted_coco_class_index"] for r in items],
                         [49, 0, 32])
        self.assertEqual(items[:1],
                         decode_candidates(raw, width=416, height=416,
                                           max_results=1))
        self.assertEqual(items[:3],
                         decode_candidates(raw, width=416, height=416,
                                           max_results=3))
        self.assertGreater(items[0]["score"], items[1]["score"])
        self.assertGreater(items[1]["score"], items[2]["score"])

    def test_no_raw_coarse_objectness_is_a_valid_empty_proposal(self):
        raw = np.zeros((1, 3549, 85), np.float32)
        self.assertEqual(decode_candidates(raw, width=416, height=416), [])

    def test_bad_geometry_and_bad_scores_fail_closed(self):
        raw = synthetic_head()
        for args in (dict(width=0, height=416),
                     dict(width=416, height=-1),
                     dict(width=416, height=416, max_results=2)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    decode_candidates(raw, **args)
        with self.assertRaises(ValueError):
            decode_candidates(raw[:, :12], width=416, height=416)
        raw[0, 530, 4] = np.nan
        with self.assertRaises(ValueError):
            decode_candidates(raw, width=416, height=416)
        raw[0, 530, 4] = 2.0
        with self.assertRaises(ValueError):
            decode_candidates(raw, width=416, height=416)

    def test_overlap_zero_or_full(self):
        self.assertEqual(_iou((0, 0, 10, 10), (0, 0, 10, 10)), 1.0)
        self.assertEqual(_iou((0, 0, 10, 10), (100, 100, 120, 120)), 0.0)


if __name__ == "__main__":
    unittest.main()
