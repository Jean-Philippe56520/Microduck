"""Positive and negative tests: host-only one-ROI, one-iteration GrabCut."""
import unittest
import cv2
import numpy as np

from experiments.light_grabcut_region_probe import (
    grabcut_rectangle, mask_iou, describe_mask,
)


class LightGrabCutTests(unittest.TestCase):
    def test_red_circle_region(self):
        img = np.full((160, 160, 3), 220, np.uint8)
        cv2.circle(img, (80, 80), 36, (225, 35, 35), -1)
        gt = np.zeros((160, 160), np.uint8)
        cv2.circle(gt, (80, 80), 36, 255, -1)
        result, mask, _ = grabcut_rectangle(img, (44, 44, 116, 116))
        self.assertEqual(result["status"], "candidate")
        self.assertGreater(mask_iou(mask, gt), 0.60)
        self.assertEqual(result["descriptor"]["shape"], "round_like")
        self.assertEqual(result["descriptor"]["colors"][0]["name"], "red")

    def test_blue_rectangle_not_round(self):
        img = np.full((160, 160, 3), 220, np.uint8)
        cv2.rectangle(img, (30, 50), (130, 110), (24, 50, 226), -1)
        result, _, _ = grabcut_rectangle(img, (30, 50, 131, 111))
        self.assertEqual(result["status"], "candidate")
        self.assertNotEqual(result["descriptor"]["shape"], "round_like")
        self.assertEqual(result["descriptor"]["colors"][0]["name"], "blue")

    def test_blank_scene_does_not_invent_object(self):
        img = np.full((160, 160, 3), 120, np.uint8)
        result, mask, _ = grabcut_rectangle(img, (30, 30, 130, 130))
        self.assertEqual(result["status"], "indeterminate")
        self.assertIsNone(result.get("descriptor"))

    def test_invalid_geometry_refused(self):
        img = np.zeros((160, 160, 3), np.uint8)
        for box in ((-1, 2, 90, 90), (5, 2, 200, 40),
                    (1, 2, float("nan"), 80), (80, 80, 80, 120)):
            with self.subTest(box=box):
                with self.assertRaises(ValueError):
                    grabcut_rectangle(img, box)
        with self.assertRaises(ValueError):
            grabcut_rectangle(img.astype(np.float32), (4, 4, 90, 90))

    def test_mismatched_masks_refused(self):
        z = np.zeros((10, 10), np.uint8)
        with self.assertRaises(ValueError):
            mask_iou(z, z[:9])
        with self.assertRaises(ValueError):
            describe_mask(np.zeros((10, 10, 3), np.uint8), z[:9])


if __name__ == "__main__":
    unittest.main()
