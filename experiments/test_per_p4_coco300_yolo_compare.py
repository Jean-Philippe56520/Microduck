"""PER-P4 deterministic offline contract tests; never download photos/models."""
import unittest

from experiments.per_p4_coco300_yolo_compare import (
    COCO_IDS, Case, CONTROLS, PER_TARGET, TARGETS, TOTAL,
    box_iou, match_predictions, score_single_image, score_summary, select_300,
)
from microduck_companion.cata2_bbox_eval import (
    PHOTO_LICENSE_NAME, PHOTO_LICENSE_URL,
)


def synthetic_coco():
    images = []
    annotations = []
    excluded = set()
    n = 1
    for name in TARGETS:
        for j in range(PER_TARGET+1):
            images.append({"id": n, "file_name": f"{n:012d}.jpg",
                           "width": 640, "height": 480, "license": 1})
            annotations.append({
                "id": n, "image_id": n, "category_id": COCO_IDS[name],
                "iscrowd": 0, "bbox": [10, 20, 80, 80],
                "segmentation": [[10, 20, 90, 20, 90, 100, 10, 100]],
            })
            if j == 0:
                excluded.add(n)
            n += 1
    for _ in range(CONTROLS):
        images.append({"id": n, "file_name": f"{n:012d}.jpg",
                       "width": 640, "height": 480, "license": 1})
        n += 1
    data = {"images": images, "annotations": annotations,
            "licenses": [{"id": 1, "name": PHOTO_LICENSE_NAME,
                          "url": PHOTO_LICENSE_URL}]}
    return data, excluded


class PERP4Tests(unittest.TestCase):
    def test_iou_and_invalid_numbers(self):
        self.assertEqual(box_iou((1, 2, 11, 12), (1, 2, 11, 12)), 1)
        self.assertEqual(box_iou((1, 2, 11, 12), (12, 13, 20, 25)), 0)
        with self.assertRaises(ValueError):
            box_iou((float("nan"), 2, 11, 12), (1, 2, 11, 12))

    def test_unknown_region_matches_despite_false_category(self):
        gt = ({"category_id": COCO_IDS["dog"], "box": [0, 0, 30, 30]},)
        pred = [{"category_id": COCO_IDS["cat"], "box": [0, 0, 30, 30],
                 "confidence": .9}]
        self.assertEqual(match_predictions(pred, gt, class_aware=True), {})
        self.assertEqual(match_predictions(pred, gt, class_aware=False), {0: 0})

    def test_unique_match_one_prediction_cannot_hit_two_objects(self):
        gt = ({"category_id": COCO_IDS["dog"], "box": [0, 0, 30, 30]},
              {"category_id": COCO_IDS["dog"], "box": [0, 0, 30, 30]})
        pred = [{"category_id": COCO_IDS["dog"], "box": [0, 0, 30, 30],
                 "confidence": .9}]
        self.assertEqual(len(match_predictions(pred, gt, class_aware=True)), 1)
        self.assertEqual(len(match_predictions(pred, gt, class_aware=False)), 1)

    def test_selection_300_unique_excludes_historic(self):
        data, excluded = synthetic_coco()
        a = select_300(data, excluded)
        b = select_300(data, excluded)
        self.assertEqual(a, b)
        self.assertEqual(len(a), TOTAL)
        self.assertEqual(len({c.image_id for c in a}), TOTAL)
        self.assertFalse({c.image_id for c in a} & excluded)
        for name in TARGETS:
            self.assertEqual(sum(c.assigned_group == name for c in a), PER_TARGET)
        self.assertEqual(sum(c.assigned_group == "target_free" for c in a), CONTROLS)
        self.assertFalse(any(c.annotations for c in a if c.assigned_group == "target_free"))

    def test_rejects_unlicensed_and_underpopulated_cohorts(self):
        data, excluded = synthetic_coco()
        data["licenses"][0]["name"] = "All Rights Reserved"
        with self.assertRaisesRegex(ValueError, "approved"):
            select_300(data, excluded)
        data, excluded = synthetic_coco()
        # Remove one eligible cat photo: now 29 after exclusion.
        cat_id = next(i["id"] for i in data["images"]
                      if i["id"] not in excluded and i["id"] > PER_TARGET+1
                      and i["id"] < (PER_TARGET+1)*2)
        data["images"] = [x for x in data["images"] if x["id"] != cat_id]
        with self.assertRaisesRegex(ValueError, "insufficient licensed"):
            select_300(data, excluded)

    def test_region_recall_independent_of_category_and_negatives(self):
        case = Case(333, "000000000333.jpg", 100, 100, ({
            "category_id": COCO_IDS["cat"], "box": [0, 0, 30, 30],
            "segmentation": [[0, 0, 30, 0, 30, 30, 0, 30]],
        },), "cat")
        wrong = [{"category_id": COCO_IDS["dog"], "box": [0, 0, 30, 30],
                  "confidence": .95}]
        row = score_single_image(wrong, case)
        self.assertEqual(row["class_hits"]["cat"], 0)
        self.assertEqual(row["region_hits"]["cat"], 1)
        control = Case(334, "000000000334.jpg", 100, 100, (), "target_free")
        nr = score_single_image(wrong, control)
        self.assertEqual(nr["predicted_target_boxes"], 1)
        result = score_summary([row, nr], [2.0, 10.0])
        self.assertEqual(result["categories"]["cat"]["region_hits"], 1)
        self.assertEqual(result["categories"]["cat"]["class_hits"], 0)
        self.assertEqual(result["target_class_predictions_on_target_free_controls"], 1)

    def test_no_mask_pairs_without_segmentation(self):
        case = Case(333, "000000000333.jpg", 100, 100, (), "target_free")
        row = score_single_image([], case)
        self.assertEqual(row["mask_pairs"], 0)
        self.assertEqual(row["predicted_target_boxes"], 0)


if __name__ == "__main__":
    unittest.main()
