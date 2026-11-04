"""QUAL-R0 realistic source fixtures, no JPEG, ONNX, network or robot."""
from __future__ import annotations

from collections import defaultdict
import unittest

from experiments.per80_yolox_coco_public import COCO80_ID_ORDER, Proposal
from experiments.per_qual1_sama_gt_gate import (
    TARGETS, SourceGateError, _index_boxes, validate_dual_class_map,
)
from experiments.per_qual_r0_scoring_contract import (
    N_IMAGES, validate_paired_contract, score_paired_contract,
)

OFFICIAL = {"person": 1, "cat": 17, "dog": 18, "sports_ball": 37,
            "bottle": 44, "chair": 62, "book": 84}
BOX = (20., 30., 90., 100.)


def source_fixture():
    images = {1000+i: (320, 240, f"{1000+i:012d}.jpg", 4)
              for i in range(N_IMAGES)}
    cases = tuple((1000+i, TARGETS[i//6]) for i in range(N_IMAGES))
    classes = [f"unused_{idx}" for idx in range(80)]
    for name, cat_id in OFFICIAL.items():
        classes[COCO80_ID_ORDER.index(cat_id)] = name
    class_spaces = validate_dual_class_map(tuple(classes), OFFICIAL,
                                          COCO80_ID_ORDER)
    annotation = []
    for num, (ident, name) in enumerate(cases):
        annotation.append({"id": num+1, "image_id": ident,
                           "category_id": OFFICIAL[name], "iscrowd": 0,
                           "bbox": [20, 30, 70, 70]})
    first, bad_a = _index_boxes({"annotations": annotation}, images, set(images))
    second, bad_b = _index_boxes({"annotations": annotation}, images, set(images))
    assert not bad_a and not bad_b
    return cases, class_spaces, first, second


def perfect_outputs(cases, class_spaces):
    return {ident: (Proposal(class_spaces[name]["yolox_head_idx"], BOX, .9),)
            for ident, name in cases}


class QualR0RealReaderContract(unittest.TestCase):
    def test_positive_loader_returns_defaultdict_and_preflight_accepts(self):
        cases, spaces, ca, sa = source_fixture()
        self.assertIsInstance(ca, defaultdict)
        self.assertIsInstance(sa, defaultdict)
        self.assertNotEqual(type(ca), dict)  # Reproduces PR #304
        before = len(ca), len(sa)
        preflight = validate_paired_contract(cases, spaces, ca, sa)
        self.assertEqual(preflight["status"], "HOST_GT_CONTRACT_PASS_NO_INFERENCE")
        self.assertEqual(preflight["source_reader_types"], ["defaultdict", "defaultdict"])
        self.assertEqual(preflight["selected_photos"], 42)
        self.assertEqual(preflight["inferences_executed"], 0)
        self.assertEqual(before, (len(ca), len(sa)))

    def test_positive_seven_real_coco_ids_vs_seven_model_indices(self):
        cases, spaces, ca, sa = source_fixture()
        rows = score_paired_contract(cases, spaces, ca, sa,
                                     perfect_outputs(cases, spaces))
        for name in TARGETS:
            self.assertNotEqual(spaces[name]["coco_category_id"],
                                spaces[name]["yolox_head_idx"])
            self.assertEqual(rows[name]["allocated_photos"], 6)
            self.assertEqual(rows[name]["coco_gt_boxes"], 6)
            self.assertEqual(rows[name]["sama_gt_boxes"], 6)
            self.assertEqual(rows[name]["matched_coco_iou50"], 6)
            self.assertEqual(rows[name]["matched_sama_iou50"], 6)
            self.assertEqual(rows[name]["recall_coco_iou50"], 1.)
            self.assertEqual(rows[name]["delta_sama_minus_coco"], 0.)

    def test_extra_secondary_gt_changes_recall_not_yolox_predictions(self):
        cases, spaces, ca, sa = source_fixture()
        ident, label = cases[0]
        sa[(ident, spaces[label]["coco_category_id"])].append((120., 120., 150., 150.))
        row = score_paired_contract(cases, spaces, ca, sa,
                                    perfect_outputs(cases, spaces))[label]
        self.assertEqual(row["proposals"], 6)
        self.assertEqual(row["matched_coco_iou50"], 6)
        self.assertEqual(row["matched_sama_iou50"], 6)
        self.assertEqual(row["sama_gt_boxes"], 7)
        self.assertLess(row["delta_sama_minus_coco"], 0.)

    def test_unmatched_not_physically_false(self):
        cases, spaces, ca, sa = source_fixture()
        predictions = {ident: (Proposal(0, (120., 120., 160., 160.), .9),)
                       for ident, _ in cases}
        rows = score_paired_contract(cases, spaces, ca, sa, predictions)
        self.assertEqual(rows["person"]["proposals"], 42)
        self.assertEqual(rows["person"]["matched_coco_iou50"], 0)
        self.assertEqual(rows["person"]["unmatched_coco_not_proven_false"], 42)
        self.assertNotIn("false_positives", rows["person"])

    def test_negative_wrong_gt_id_instead_of_coco_id(self):
        cases, spaces, ca, sa = source_fixture()
        spaces["person"]["coco_category_id"] = 0
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            validate_paired_contract(cases, spaces, ca, sa)

    def test_negative_swapped_head_indices(self):
        cases, spaces, ca, sa = source_fixture()
        spaces["cat"]["yolox_head_idx"] = 0
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            validate_paired_contract(cases, spaces, ca, sa)

    def test_negative_missing_positive_in_either_annotation(self):
        cases, spaces, ca, sa = source_fixture()
        ident, name = cases[0]
        ca.pop((ident, spaces[name]["coco_category_id"]))
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            validate_paired_contract(cases, spaces, ca, sa)
        cases, spaces, ca, sa = source_fixture()
        ident, name = cases[0]
        sa.pop((ident, spaces[name]["coco_category_id"]))
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            validate_paired_contract(cases, spaces, ca, sa)

    def test_negative_duplicate_or_incomplete_cases(self):
        cases, spaces, ca, sa = source_fixture()
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            validate_paired_contract(cases[:-1] + (cases[0],), spaces, ca, sa)
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            validate_paired_contract(cases[:-1], spaces, ca, sa)
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            validate_paired_contract(cases[:-6] + (cases[6],)*6, spaces, ca, sa)

    def test_negative_corrupt_gt_geometry_nan_or_type(self):
        cases, spaces, ca, sa = source_fixture()
        key = (cases[0][0], spaces[cases[0][1]]["coco_category_id"])
        ca[key] = [(float("nan"), 1., 3., 3.)]
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            validate_paired_contract(cases, spaces, ca, sa)
        cases, spaces, ca, sa = source_fixture()
        sa[key] = "not-a-real-box-list"
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            validate_paired_contract(cases, spaces, ca, sa)

    def test_negative_nonfinite_and_out_of_range_proposals(self):
        cases, spaces, ca, sa = source_fixture()
        outputs = perfect_outputs(cases, spaces)
        ident, name = cases[0]
        for proposal in (Proposal(0, BOX, float("inf")),
                         Proposal(80, BOX, .9),
                         Proposal(0, (0., 0., 0., 1.), .9),
                         Proposal(True, BOX, .9),
                         "unexpected-output"):
            outputs[ident] = (proposal,)
            with self.assertRaisesRegex(SourceGateError, "STOP_MODEL"):
                score_paired_contract(cases, spaces, ca, sa, outputs)

    def test_negative_prediction_set_is_not_complete(self):
        cases, spaces, ca, sa = source_fixture()
        outputs = perfect_outputs(cases, spaces)
        outputs.pop(cases[0][0])
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            score_paired_contract(cases, spaces, ca, sa, outputs)

    def test_negative_unsupported_gt_map_type(self):
        cases, spaces, ca, sa = source_fixture()
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            validate_paired_contract(cases, spaces, list(ca.items()), sa)

    def test_positive_matching_max_cardinality_not_greedy(self):
        cases, spaces, ca, sa = source_fixture()
        ident, name = cases[0]
        key = (ident, spaces[name]["coco_category_id"])
        box_a = ((1., 0., 11., 10.), (-2., 0., 8., 10.))
        ca[key] = list(box_a)
        sa[key] = list(box_a)
        outputs = perfect_outputs(cases, spaces)
        outputs[ident] = (Proposal(spaces[name]["yolox_head_idx"], (0.,0.,10.,10.), .9),
                          Proposal(spaces[name]["yolox_head_idx"], (2.,0.,12.,10.), .8))
        row = score_paired_contract(cases, spaces, ca, sa, outputs)[name]
        self.assertEqual(row["matched_coco_iou50"], 7)
        self.assertEqual(row["matched_sama_iou50"], 7)


if __name__ == "__main__":
    unittest.main()
