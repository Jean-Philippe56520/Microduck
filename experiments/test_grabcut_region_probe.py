"""Controlled positive/negative unit tests, separate from COCO real images."""
import unittest

import cv2
import numpy as np

from experiments.grabcut_region_probe import (
    describe_mask, grabcut_rectangle, mask_iou,
)


class GrabcutProbeTests(unittest.TestCase):
    def test_circle_colour_iou_improves_over_rectangle(self):
        img=np.full((192,192,3),220,dtype=np.uint8)
        cv2.circle(img,(95,95),42,(220,35,35),-1)
        ground=np.zeros((192,192),dtype=np.uint8)
        cv2.circle(ground,(95,95),42,255,-1)
        prediction, mask, _=grabcut_rectangle(img,(53,53,138,138))
        self.assertEqual(prediction["status"],"candidate")
        self.assertGreater(mask_iou(mask,ground),.74)
        d=prediction["descriptor"]
        self.assertEqual(d["shape"],"round_like")
        self.assertEqual(d["colors"][0]["name"],"red")
        self.assertEqual(d["not_an_object_identity_or_category"],True)

    def test_blue_rectangle_is_not_a_ball_category(self):
        img=np.full((192,192,3),230,dtype=np.uint8)
        cv2.rectangle(img,(40,64),(151,130),(30,40,215),-1)
        prediction, mask, _=grabcut_rectangle(img,(39,63,152,131))
        self.assertEqual(prediction["status"],"candidate")
        self.assertNotEqual(prediction["descriptor"]["shape"],"round_like")
        self.assertEqual(prediction["descriptor"]["colors"][0]["name"],"blue")

    def test_dark_solid_scene_must_not_invent_an_object(self):
        img=np.full((192,192,3),20,dtype=np.uint8)
        d,mask,_=grabcut_rectangle(img,(45,45,145,145))
        self.assertEqual(d["status"],"indeterminate")
        self.assertIsNone(d.get("descriptor"))

    def test_invalid_rectangles_refused(self):
        img=np.zeros((192,192,3),dtype=np.uint8)
        for box in ((-1,0,40,40),(20,20,20,30),(1,1,200,200),
                    (1,1,float("nan"),40)):
            with self.subTest(box=box),self.assertRaises(ValueError):
                grabcut_rectangle(img,box)
        with self.assertRaises(ValueError):
            grabcut_rectangle(img.astype(np.float32),(0,0,60,60))

    def test_mask_geometry_and_mismatched_sizes_refused(self):
        black=np.zeros((40,40),dtype=np.uint8)
        white=np.full((40,40),255,dtype=np.uint8)
        self.assertEqual(mask_iou(black,white),0.)
        self.assertIsNone(mask_iou(black,black))
        with self.assertRaises(ValueError):
            mask_iou(black,white[:30])
        with self.assertRaises(ValueError):
            describe_mask(np.zeros((40,40,3),dtype=np.uint8),
                          white[:30])


if __name__ == "__main__":
    unittest.main()
