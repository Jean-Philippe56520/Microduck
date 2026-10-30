"""PER-P4 fixture-only positive/negative checks (not model accuracy)."""
import unittest
import importlib.util

from experiments.per_p4_yolo26_coco300 import (
    COCO_IDS, TARGETS, Target, assign, box_iou, mask_scores, select_cases
)


def fixture():
    images = []
    ann = []
    names = {
        "person": 1, "cat": 17, "dog": 18, "sports_ball": 37, "chair": 62
    }
    for index, (name, cid) in enumerate(names.items(), 1):
        images.append({"id": index, "file_name": f"{index:012d}.jpg",
                       "width": 40, "height": 40, "license": 4})
        ann.append({"id": index, "image_id": index, "category_id": cid,
                    "iscrowd": 0, "bbox": [2, 2, 12, 12],
                    "segmentation": [[2, 2, 14, 2, 14, 14, 2, 14]]})
    images.append({"id": 6, "file_name": "000000000006.jpg",
                   "width": 40, "height": 40, "license": 4})
    return {"licenses": [{"id": 4, "name": "Attribution License",
                          "url": "http://creativecommons.org/licenses/by/2.0/"}],
            "categories": [{"id": cid, "name": name.replace("_", " ")}
                           for name, cid in names.items()],
            "images": images, "annotations": ann}


class TestPerP4(unittest.TestCase):
    def test_one_case_for_each_class_and_targetfree(self):
        cases = select_cases(fixture(), set(), per_class=1, negatives=1)
        self.assertEqual(len(cases), 6)
        self.assertEqual(len({case.image_id for case, _ in cases}), 6)
        self.assertEqual({gt[0].category for _, gt in cases[:5]}, set(TARGETS))
        self.assertEqual(cases[-1][1], ())

    def test_exclusion_refuses_reused_photo(self):
        with self.assertRaisesRegex(ValueError, "insufficient licensed target"):
            select_cases(fixture(), {1}, per_class=1, negatives=1)

    def test_license_mismatch_rejected(self):
        raw = fixture()
        raw["licenses"][0]["name"] = "All Rights Reserved"
        with self.assertRaisesRegex(ValueError, "licens"):
            select_cases(raw, set(), per_class=1, negatives=1)

    def test_bad_bbox_rejected(self):
        raw = fixture()
        raw["annotations"][0]["bbox"] = [5, 5, -5, 3]
        with self.assertRaisesRegex(ValueError, "insufficient licensed target"):
            select_cases(raw, set(), per_class=1, negatives=1)

    def test_unknown_category_is_region_not_identity(self):
        gt = (Target("cat", (2., 2., 14., 14.), []),)
        predicted = [{"category": "dog", "xyxy": (2., 2., 14., 14.)}]
        self.assertEqual(assign(gt, predicted, class_aware=True), [])
        self.assertEqual(len(assign(gt, predicted, class_aware=False)), 1)

    def test_one_prediction_never_matches_two_instances(self):
        gt = (Target("cat", (2., 2., 14., 14.), []),
              Target("cat", (2., 2., 14., 14.), []))
        predicted = [{"category": "cat", "xyxy": (2., 2., 14., 14.)}]
        self.assertEqual(len(assign(gt, predicted, class_aware=True)), 1)

    def test_rectangle_iou_geometry(self):
        self.assertEqual(box_iou((2., 2., 10., 10.), (2., 2., 10., 10.)), 1.0)
        self.assertEqual(box_iou((2., 2., 10., 10.), (20., 20., 25., 25.)), 0.0)

    @unittest.skipUnless(importlib.util.find_spec('numpy') and importlib.util.find_spec('pycocotools'), 'optional scientific dependencies unavailable')
    def test_predicted_mask_can_be_worse_than_box(self):
        import numpy as np
        blank = np.zeros((40, 40), dtype=np.float32)
        mi, ri = mask_scores([[10, 10, 20, 10, 20, 20, 10, 20]],
                             blank, (10., 10., 20., 20.), 40, 40)
        self.assertEqual(mi, 0)
        self.assertGreater(ri, 0.5)

    @unittest.skipUnless(importlib.util.find_spec('numpy') and importlib.util.find_spec('pycocotools'), 'optional scientific dependencies unavailable')
    def test_wrong_mask_shape_is_error(self):
        import numpy as np
        with self.assertRaisesRegex(ValueError, "geometry"):
            mask_scores([[10, 10, 20, 10, 20, 20, 10, 20]],
                        np.zeros((20, 20), dtype=np.float32),
                        (10., 10., 20., 20.), 40, 40)

    def test_no_models_needed_for_fixture_tests(self):
        self.assertEqual(set(COCO_IDS), set(TARGETS))


if __name__ == "__main__":
    unittest.main()
