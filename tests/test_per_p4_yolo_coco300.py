"""PER-P4 deterministic selection/scoring fixtures, not real model inference."""
import hashlib
import importlib.util
import json
from unittest import TestCase
from unittest.mock import patch

from experiments import per_p4_yolo_coco300 as m


class TestPERP4(TestCase):
    def test_one_to_one_prevents_reusing_one_detection(self):
        gt = [{"box": (0, 0, 10, 10), "category": "cat"} for _ in range(2)]
        det = [{"box": (0, 0, 10, 10), "category": "cat", "score": .8}]
        self.assertEqual(len(m.one_to_one_matches(gt, det, correct_category=True)), 1)

    def test_class_agnostic_is_not_correct_class(self):
        gt = [{"box": (0, 0, 10, 10), "category": "cat"}]
        det = [{"box": (0, 0, 10, 10), "category": "chair", "score": .8}]
        self.assertEqual(len(m.one_to_one_matches(gt, det, correct_category=True)), 0)
        self.assertEqual(len(m.one_to_one_matches(gt, det, correct_category=False)), 1)

    def test_gt_controls_are_not_assumed_empty_room(self):
        self.assertTrue(m.photo_is_control([]))
        self.assertFalse(m.photo_is_control([{"category_id": 17}]))

    def test_model_gate_is_predeclared(self):
        def r(recall, gain=None, masks=0):
            return {"primary_region_recall_iou50": recall, "mask_evaluable_instances": masks,
                    "mask_better_than_predicted_box_fraction": gain}
        self.assertEqual(m.decide({"yolo26n.pt": r(.73)})["status"], "insufficient")
        self.assertEqual(m.decide({"yolo11n.pt": r(.80), "yolo26n.pt": r(.85),
                                   "yolo26n-seg.pt": r(.84, .70, 22)})["recommended_for_low_camera_study"], "yolo26n-seg.pt")
        self.assertEqual(m.decide({"yolo11n.pt": r(.80), "yolo26n.pt": r(.85),
                                   "yolo26n-seg.pt": r(.84, .30, 22)})["recommended_for_low_camera_study"], "yolo26n.pt")

    def test_reject_partial_300_report(self):
        acc = m.new_accumulator()
        acc["times_ms"] = [1.0]
        with self.assertRaises(ValueError):
            m.summarize_model(acc, "a"*64)

    def test_selection_deterministic(self):
        self.assertEqual(m.fixed_order([101, 3, 20]), m.fixed_order([20, 101, 3]))

    def test_300_unique_disjoint_public_cases_and_bad_sha(self):
        data = {"images": [], "annotations": [],
                "licenses": [{"id": 4, "name": m.PHOTO_LICENSE_NAME, "url": m.PHOTO_LICENSE_URL}],
                "categories": [{"id": cid, "name": name.replace("_", " ")}
                               for name, cid in m.COCO_IDS.items()]}
        for index, (name, cid) in enumerate(m.COCO_IDS.items()):
            for i in range(60):
                image_id = 2000 + index*100 + i
                data["images"].append({"id": image_id, "file_name": f"{image_id:012d}.jpg",
                                       "width": 640, "height": 480, "license": 4})
                data["annotations"].append({"image_id": image_id, "category_id": cid,
                                            "bbox": [10, 20, 50, 40], "iscrowd": 0,
                                            "segmentation": [[0, 0, 10, 0, 10, 10]]})
        for i in range(200):
            image_id = 4000 + i
            data["images"].append({"id": image_id, "file_name": f"{image_id:012d}.jpg",
                                   "width": 640, "height": 480, "license": 4})
        blob = json.dumps(data).encode()
        previous_ids = set(range(132))
        with patch.object(m, "ANNOTATIONS_SHA256", hashlib.sha256(blob).hexdigest()), patch.object(
                m, "eighth_disjoint", return_value=([], data, [24, 24, 18, 12, 12, 12, 12], previous_ids)):
            selected = m.select_photos(blob)
            self.assertEqual(len(selected), 300)
            self.assertEqual(len({p.image_id for p in selected}), 300)
            self.assertEqual(sum(p.target_cohort == "target_free" for p in selected), 100)
            self.assertFalse({p.image_id for p in selected} & previous_ids)
            with patch.object(m, "ANNOTATIONS_SHA256", "0"*64):
                with self.assertRaises(ValueError):
                    m.select_photos(blob)

    def test_reject_nonfinite_geometry(self):
        self.assertEqual(m.box_iou((0,0,10,10),(30,30,40,40)), 0)

    @__import__('unittest').skipUnless(importlib.util.find_spec('numpy'), 'numpy only in PER-P4 model workflow')
    def test_mask_geometry_and_rectangle_baseline(self):
        import numpy as np
        truth = np.zeros((10,10), dtype='uint8')
        truth[1:4,2:8] = 1
        baseline = m.rectangle_mask((2,1,8,4),10,10)
        self.assertEqual(m.mask_iou(truth, baseline), 1.0)
        with self.assertRaises(ValueError):
            m.mask_iou(truth, baseline[:9])
