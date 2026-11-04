"""PER-80 public 80-category benchmark contract tests, fake fixtures only.

No network, image capture, robot, model weight or database in these tests.
"""
from __future__ import annotations

import copy
import importlib.util
from hashlib import sha256
import unittest

from experiments.per80_yolox_coco_public import (
    COCO80_ID_ORDER, P4_IDS, P4_IDS_SHA256, _GRANTS,
    Truth, Proposal, _box_from_annotation, check_class_order,
    decode_all_classes, evaluate_report, select_cases,
)
from microduck_companion.cata2_bbox_eval import decode_boxes


def fixture_data():
    categories = []
    names = {
        0: "person", 15: "cat", 16: "dog",
        32: "sports ball", 56: "chair",
    }
    for idx, cid in enumerate(COCO80_ID_ORDER):
        categories.append({
            "id": cid, "name": names.get(idx, f"unit class {idx}")
        })
    photo = []
    annotations = []
    for idx, cid in enumerate(COCO80_ID_ORDER):
        ident = idx + 1000
        photo.append({
            "id": ident, "file_name": f"{ident:012d}.jpg",
            "width": 200, "height": 100, "license": 4,
        })
        annotations.append({
            "image_id": ident, "category_id": cid,
            "iscrowd": 0, "bbox": [20, 10, 70, 50],
        })
    for idx in range(40):
        ident = idx + 3000
        photo.append({
            "id": ident, "file_name": f"{ident:012d}.jpg",
            "width": 200, "height": 100, "license": 4,
        })
    licences = [
        {"id": i, "name": name, "url": url}
        for i, (name, url) in _GRANTS.items()
    ]
    return {
        "categories": categories, "images": photo,
        "annotations": annotations, "licenses": licences,
    }


class Public80CocoContractTests(unittest.TestCase):
    def test_official_80_id_map_and_five_legacy_anchors(self):
        data = fixture_data()
        names = check_class_order(data)
        self.assertEqual(80, len(names))
        self.assertEqual(
            [names[n] for n in (0, 15, 16, 32, 56)],
            ["person", "cat", "dog", "sports_ball", "chair"]
        )
        for idx, wrong in ((0, "people"), (32, "sport_ball")):
            changed = copy.deepcopy(data)
            changed["categories"][idx]["name"] = wrong
            with self.assertRaises(ValueError):
                check_class_order(changed)

    def test_missing_or_duplicate_class_ids_refused(self):
        data = fixture_data()
        data["categories"][14]["id"] = 1
        with self.assertRaises(ValueError):
            check_class_order(data)
        data = fixture_data()
        data["categories"].pop()
        with self.assertRaises(ValueError):
            check_class_order(data)

    def test_historical_public_300_exclusion_roster(self):
        self.assertEqual(300, len(P4_IDS))
        self.assertEqual(P4_IDS_SHA256, sha256(
            ",".join(str(i) for i in sorted(P4_IDS)).encode()
        ).hexdigest())
        self.assertNotIn(0, P4_IDS)

    def test_80_category_coverage_on_synthetic_ground_truth(self):
        data = fixture_data()
        names, selected, coverage, counts = select_cases(
            data, frozenset(), image_count=100, per_class=1,
        )
        self.assertEqual(100, len(selected))
        self.assertEqual(80, len(names))
        self.assertTrue(all(v >= 1 for v in coverage))
        self.assertEqual(100, len({c.image_id for c, _ in selected}))
        self.assertEqual(120, counts["available_licensed_without_crowd"])
        self.assertTrue(all(not c.ground_truth for c, _ in selected))

    def test_selection_order_independent_of_source_row_order(self):
        data = fixture_data()
        first = select_cases(
            data, frozenset(), image_count=100, per_class=1,
        )
        for field in ("categories", "images", "annotations", "licenses"):
            data[field].reverse()
        second = select_cases(
            data, frozenset(), image_count=100, per_class=1,
        )
        self.assertEqual(first, second)

    def test_absent_category_or_historically_excluded_last_example_stops(self):
        data = fixture_data()
        with self.assertRaisesRegex(ValueError, "no official GT"):
            select_cases(data, frozenset({1000}), image_count=100, per_class=1)

    def test_licensing_misstatement_and_rotation_name_refused(self):
        data = fixture_data()
        data["licenses"][3]["name"] = "Not a CC grant"
        with self.assertRaises(ValueError):
            select_cases(data, frozenset(), image_count=100, per_class=1)
        data = fixture_data()
        data["images"][0]["file_name"] = "redirected.jpg"
        with self.assertRaises(ValueError):
            select_cases(data, frozenset(), image_count=100, per_class=1)

    def test_crowd_and_corrupted_bbox_do_not_become_valid_targets(self):
        for replacement in (
            ("iscrowd", 1), ("bbox", [20, 10, 0, 50]),
            ("bbox", [float("nan"), 10, 50, 50]),
        ):
            data = fixture_data()
            data["annotations"][0][replacement[0]] = replacement[1]
            with self.assertRaisesRegex(ValueError, "no official GT"):
                select_cases(data, frozenset(), image_count=100, per_class=1)

    def test_inadequate_or_invalid_selection_budget_refused(self):
        data = fixture_data()
        with self.assertRaisesRegex(ValueError, "budget"):
            select_cases(data, frozenset(), image_count=801, per_class=1)
        with self.assertRaisesRegex(ValueError, "few licensed"):
            select_cases(data, frozenset(), image_count=130, per_class=1)

    def test_geometry_rejects_malformed_boxes_without_repair(self):
        self.assertEqual((1., 2., 10., 22.), _box_from_annotation(
            {"bbox": [1, 2, 9, 20]}, 100, 100,
        ))
        for value in ([1,2,0,9], [100,1,1,10],
                      ["a",2,9,10], [float("nan"),1,3,3]):
            self.assertIsNone(_box_from_annotation(
                {"bbox": value}, 100, 100,
            ))

    @unittest.skipUnless(importlib.util.find_spec("numpy") is not None,
                         "NumPy available only in focused PER-80 benchmark CI")
    def test_all80_decoder_preserves_five_class_geometry_on_one_head(self):
        import numpy as np
        a = np.zeros((1, 3549, 85), dtype=np.float32)
        for row, cat in ((150, 15), (350, 32), (900, 56)):
            a[0, row, 4] = 0.92
            a[0, row, 5 + cat] = 0.82
        eighty = decode_all_classes(a, width=416, height=416)
        five = decode_boxes(a, width=416, height=416)
        self.assertEqual(3, len(eighty))
        self.assertEqual(3, len(five))
        by_name = {0:"person",15:"cat",16:"dog",32:"sports_ball",56:"chair"}
        for candidate in eighty:
            old = next(x for x in five
                       if x.category == by_name[candidate.class_idx])
            for x,y in zip(old.xyxy, candidate.box):
                self.assertAlmostEqual(x,y,places=4)
            self.assertAlmostEqual(old.confidence,candidate.confidence,places=5)

    @unittest.skipUnless(importlib.util.find_spec("numpy") is not None,
                         "NumPy available only in focused PER-80 benchmark CI")
    def test_invalid_output_refused_before_classification(self):
        import numpy as np
        for raw in (
            np.zeros((1, 3549, 84), dtype=np.float32),
            np.full((1, 3549, 85), float("nan"), dtype=np.float32),
        ):
            with self.assertRaises(ValueError):
                decode_all_classes(raw, width=416, height=416)

    def test_unseen_category_support_is_null_not_perfect_score(self):
        names = check_class_order(fixture_data())
        gt = (Truth(15,(10.,10.,50.,50.)),)
        pred = (Proposal(15,(10.,10.,50.,50.), .9),
                Proposal(15,(11.,11.,48.,48.), .8),
                Proposal(32,(5.,5.,20.,20.), .8))
        report = evaluate_report(
            names, [(gt,pred)], coverage=tuple(
                1 if c == 15 else 0 for c in range(80)
            ),
        )
        self.assertEqual(80, len(report["categories"]))
        self.assertEqual(1, report["gt_classes_represented"])
        self.assertEqual(1, report["matched_boxes_iou50"])
        self.assertEqual(2, report["unmatched_proposals_not_proven_false"])
        self.assertEqual(1, report["categories"]["cat"]["missed_gt"]+1)
        self.assertIsNone(report["categories"]["person"]["recall_iou50"])
        self.assertEqual("unsupported",report["categories"]["person"]["class_coverage_status"])
        self.assertEqual(0, report["physically_verified_absent_images"])
        self.assertFalse(report["all_80_category_safe_use"])


if __name__ == "__main__":
    unittest.main()
