"""VIS-ATT-2 fixture tests; photos and ONNX run only in pinned public CI."""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from experiments import vis_att2_eighth_coco_category_vs_region as study


def row_set():
    """18 artificial rows, no COCO image or network, including target-free."""
    rows = []
    category_names = tuple(study.CATEGORIES)
    for i in range(18):
        target = category_names[i//3] if i < 15 else "target_free"
        top1 = i < 6
        top3 = i < 10
        top5 = i < 12
        # The second category has a top3 region but not a correct class.
        class_hit = top3 and i != 5
        count = 1 if top5 else (1 if i >= 15 else 0)
        rows.append({
            "image_id": i + 999000,
            "evaluated_target": target,
            "gt_target_count": 0 if i >= 15 else 1,
            "class_correct_hit": bool(class_hit),
            "region_k1_target_hit": bool(top1),
            "region_k3_target_hit": bool(top3),
            "region_k5_target_hit": bool(top5),
            "region_high_confidence_target_hit": bool(top3 and i % 2 == 0),
            "top3_candidate_count": count,
            "top3_matched_to_any_coco_annotation": 1 if top3 else 0,
            "top3_score_above_f2_mock_threshold_count": 1 if count and i % 2 == 0 else 0,
        })
    return rows


def fake_past_and_eighth(*, broken_seventh=False, leak=False):
    groups = []
    next_id = 1000
    for n in (24, 24, 18, 12, 12, 12):
        groups.append([SimpleNamespace(image_id=i)
                       for i in range(next_id, next_id + n)])
        next_id += n
    previous = study.SEVENTH_EXPECTED_IDS
    groups.append([SimpleNamespace(image_id=i)
                   for i in previous])
    if broken_seventh:
        groups[6][-1] = SimpleNamespace(image_id=12345678)
    eighth = []
    for k in range(18):
        target = tuple(study.CATEGORIES)[k//3] if k < 15 else None
        ident = (1000 if leak and k == 0 else 100000 + k)
        gt = () if target is None else (SimpleNamespace(category=target),)
        eighth.append(SimpleNamespace(image_id=ident, ground_truth=gt))
    groups.append(eighth)
    return groups


class EighthCategoryVsRegionTests(unittest.TestCase):
    def test_predeclared_selection_and_thresholds(self):
        self.assertEqual(
            ((4, 4), (4, 4), (3, 3), (2, 2), (2, 2), (2, 2), (2, 2)),
            study.COHORT_SEQUENCE,
        )
        self.assertEqual((3, 3), study.EIGHTH_SPEC)
        self.assertEqual(.5, study.MATCH_IOU)
        self.assertEqual(.70, study.MAX_UNMATCHED_GT_FRACTION)
        self.assertEqual(15., study.MAX_POSTPROCESS_P95_MS)
        self.assertEqual(.8, study.DETECTION_CONFIDENCE)

    def test_prior_seven_reproduced_and_eighth_has_new_ids(self):
        blob = json.dumps({
            "images": [], "annotations": [], "licenses": [], "categories": [],
            "synthetic_test_padding": "X" * 180,
        }).encode()
        # The pinned hash guard remains active for real public evidence.
        with patch.object(study, "ANNOTATIONS_SHA256",
                          hashlib.sha256(blob).hexdigest()), patch.object(
                study, "select_coco_cases",
                side_effect=fake_past_and_eighth(),
        ):
            cases, _, prior, excluded = study.eighth_disjoint(blob)
        self.assertEqual([24, 24, 18, 12, 12, 12, 12], prior)
        self.assertEqual(114, len(excluded))
        self.assertEqual(18, len(cases))
        self.assertFalse({c.image_id for c in cases} & excluded)

    def test_wrong_seventh_cohort_stops_before_model(self):
        blob = json.dumps({
            "images": [], "annotations": [], "licenses": [], "categories": [],
            "synthetic_test_padding": "X" * 180,
        }).encode()
        with patch.object(study, "ANNOTATIONS_SHA256",
                          hashlib.sha256(blob).hexdigest()), patch.object(
                study, "select_coco_cases",
                side_effect=fake_past_and_eighth(broken_seventh=True),
        ):
            with self.assertRaisesRegex(ValueError, "seventh cohort"):
                study.eighth_disjoint(blob)

    def test_reused_old_image_is_refused(self):
        blob = json.dumps({
            "images": [], "annotations": [], "licenses": [], "categories": [],
            "synthetic_test_padding": "X" * 180,
        }).encode()
        with patch.object(study, "ANNOTATIONS_SHA256",
                          hashlib.sha256(blob).hexdigest()), patch.object(
                study, "select_coco_cases",
                side_effect=fake_past_and_eighth(leak=True),
        ):
            with self.assertRaisesRegex(ValueError, "leaked"):
                study.eighth_disjoint(blob)

    def test_positive_category_miss_rescued_by_region_is_distinct(self):
        score = study.summarize(row_set())
        self.assertEqual(15, score["target_images"])
        self.assertEqual(3, score["target_free_images"])
        self.assertEqual(10, score["top3_target_images_localized"])
        self.assertEqual(12, score["top5_target_images_localized"])
        self.assertEqual(10, score["top3_nonball_target_images_localized"])
        self.assertEqual(1, score["top3_nonball_rescued_from_class_miss"])
        self.assertTrue(score["top3_nonball_new_value_gate"])
        self.assertTrue(score["top3_target_recall_gate"])
        self.assertTrue(score["unmatched_annotation_gate"])

    def test_target_free_with_a_region_is_not_false_positive_by_itself(self):
        metric = study.summarize(row_set())
        self.assertEqual(3, metric["target_free_with_top3_region"])
        self.assertTrue(metric["not_object_free_nor_false_positive_measurement"])
        self.assertGreaterEqual(
            metric["top3_not_matched_to_80class_GT_NOT_proved_false"], 3)

    def test_no_rescue_fails_specific_value_gate(self):
        rows = row_set()
        rows[5]["class_correct_hit"] = True
        metric = study.summarize(rows)
        self.assertEqual(0, metric["top3_nonball_rescued_from_class_miss"])
        self.assertFalse(metric["top3_nonball_new_value_gate"])

    def test_target_free_is_never_declared_object_free_or_ground_truth_hit(self):
        rows = row_set()
        rows[-1]["region_k3_target_hit"] = True
        rows[-1]["region_k5_target_hit"] = True
        with self.assertRaisesRegex(ValueError, "target-free"):
            study.summarize(rows)
        rows = row_set()
        rows[-1]["gt_target_count"] = 1
        with self.assertRaisesRegex(ValueError, "GT"):
            study.summarize(rows)

    def test_k3_false_to_true_order_or_spoofed_score_fails(self):
        rows = row_set()
        rows[10]["region_k1_target_hit"] = True
        with self.assertRaisesRegex(ValueError, "monotonic"):
            study.summarize(rows)
        rows = row_set()
        rows[0]["top3_score_above_f2_mock_threshold_count"] = 5
        with self.assertRaisesRegex(ValueError, "scores"):
            study.summarize(rows)

    def test_missing_row_and_duplicated_ids_are_refused(self):
        with self.assertRaisesRegex(ValueError, "18 distinct"):
            study.summarize(row_set()[:-1])
        rows = row_set()
        rows[0]["image_id"] = rows[1]["image_id"]
        with self.assertRaisesRegex(ValueError, "18 distinct"):
            study.summarize(rows)


if __name__ == "__main__":
    unittest.main()
