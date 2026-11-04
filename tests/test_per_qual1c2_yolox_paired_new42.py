"""PER-QUAL-1C2: zero-photo fixtures exercising REAL COCO-ID vs YOLOX index."""
import unittest

from experiments.per80_yolox_coco_public import COCO80_ID_ORDER, Proposal
from experiments.per_qual1_sama_gt_gate import SourceGateError, TARGETS
from experiments.per_qual1c2_yolox_paired_new42 import score_double_gt

CATEGORIES = {
    "person": (1, 0), "cat": (17, 15), "dog": (18, 16),
    "sports_ball": (37, 32), "bottle": (44, 39),
    "chair": (62, 56), "book": (84, 73),
}
BASE_BOX = (10.0, 10.0, 40.0, 40.0)


def fixtures():
    cases = tuple((i, TARGETS[i//6]) for i in range(42))
    spaces = {name: {"coco_category_id":ids[0], "yolox_head_idx":ids[1]}
              for name,ids in CATEGORIES.items()}
    coco, sama, preds = {}, {}, {}
    for image_id, name in cases:
        coco[(image_id, spaces[name]["coco_category_id"])] = (BASE_BOX,)
        sama[(image_id, spaces[name]["coco_category_id"])] = (BASE_BOX,)
        preds[image_id] = (
            Proposal(spaces[name]["yolox_head_idx"], BASE_BOX, .9),)
    return cases, spaces, coco, sama, preds


class PairedScoringContract(unittest.TestCase):
    def test_real_coco_ids_and_zero_based_heads_score_one_to_one(self):
        cases, spaces, coco, sama, predicted = fixtures()
        scored=score_double_gt(cases,spaces,coco,sama,predicted)
        for name, (coco_id, model_idx) in CATEGORIES.items():
            self.assertNotEqual(coco_id,model_idx)
            self.assertEqual(COCO80_ID_ORDER[model_idx],coco_id)
            row=scored[name]
            self.assertEqual(row["allocated_photos"],6)
            self.assertEqual(row["evaluated_photos"],42)
            self.assertEqual(row["gt_coco_boxes"],6)
            self.assertEqual(row["gt_sama_boxes"],6)
            self.assertEqual(row["proposals"],6)
            self.assertEqual(row["matched_coco_iou50"],6)
            self.assertEqual(row["matched_sama_iou50"],6)
            self.assertEqual(row["recall_coco_iou50"],1.0)
            self.assertEqual(row["recall_sama_iou50"],1.0)

    def test_person_coco_one_and_head_zero_is_not_missing_gt(self):
        cases,spaces,coco,sama,predicted=fixtures()
        scored=score_double_gt(cases,spaces,coco,sama,predicted)
        self.assertEqual(scored["person"]["gt_coco_boxes"],6)
        self.assertEqual(scored["person"]["matched_coco_iou50"],6)

    def test_swapped_coco_and_head_domains_fail_before_measurement(self):
        cases,spaces,coco,sama,predicted=fixtures()
        spaces["person"] = {"coco_category_id": 0, "yolox_head_idx": 1}
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            score_double_gt(cases,spaces,coco,sama,predicted)
        cases,spaces,coco,sama,predicted=fixtures()
        spaces["chair"]["coco_category_id"]=56
        with self.assertRaisesRegex(SourceGateError,"STOP_SCHEMA"):
            score_double_gt(cases,spaces,coco,sama,predicted)

    def test_missing_assigned_positive_gt_is_stop_not_zero_recall(self):
        cases,spaces,coco,sama,predicted=fixtures()
        ident, cat=cases[0]
        coco.pop((ident, spaces[cat]["coco_category_id"]))
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            score_double_gt(cases,spaces,coco,sama,predicted)
        cases,spaces,coco,sama,predicted=fixtures()
        ident,cat=cases[0]
        sama.pop((ident, spaces[cat]["coco_category_id"]))
        with self.assertRaisesRegex(SourceGateError,"STOP_SCHEMA"):
            score_double_gt(cases,spaces,coco,sama,predicted)

    def test_secondary_extra_object_lowers_recall_without_changing_model(self):
        cases,spaces,coco,sama,predicted=fixtures()
        ident,name=cases[0]
        key=(ident,spaces[name]["coco_category_id"])
        sama[key]=sama[key]+((100.0,100.0,140.0,140.0),)
        scored=score_double_gt(cases,spaces,coco,sama,predicted)[name]
        self.assertEqual(scored["proposals"],6)
        self.assertEqual(scored["gt_coco_boxes"],6)
        self.assertEqual(scored["gt_sama_boxes"],7)
        self.assertEqual(scored["matched_coco_iou50"],6)
        self.assertEqual(scored["matched_sama_iou50"],6)
        self.assertLess(scored["delta_sama_minus_coco"],0.0)

    def test_missing_gt_elsewhere_never_claims_physical_false_positive(self):
        cases,spaces,coco,sama,predicted=fixtures()
        for ident,_ in cases:
            predicted[ident]=(Proposal(0,(100.0,100.0,140.0,140.0),.9),)
        person=score_double_gt(cases,spaces,coco,sama,predicted)["person"]
        self.assertEqual(person["proposals"],42)
        self.assertEqual(person["matched_coco_iou50"],0)
        self.assertEqual(person["unmatched_coco_not_proven_false"],42)
        self.assertNotIn("false_positives",person)

    def test_maximum_bipartite_matching_does_not_depend_on_box_order(self):
        cases,spaces,coco,sama,predicted=fixtures()
        image_id,label=cases[0]
        source_key=(image_id,spaces[label]["coco_category_id"])
        gt=((1.0,0.0,11.0,10.0),(-2.0,0.0,8.0,10.0))
        coco[source_key]=gt
        sama[source_key]=gt
        head=spaces[label]["yolox_head_idx"]
        predicted[image_id]=(Proposal(head,(0.0,0.0,10.0,10.0),.9),
                             Proposal(head,(2.0,0.0,12.0,10.0),.8))
        row=score_double_gt(cases,spaces,coco,sama,predicted)[label]
        self.assertEqual(row["matched_coco_iou50"],7)
        self.assertEqual(row["matched_sama_iou50"],7)

    def test_missing_repeated_or_extra_image_predictions_fail(self):
        cases,spaces,coco,sama,predicted=fixtures()
        predicted.pop(cases[0][0])
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            score_double_gt(cases,spaces,coco,sama,predicted)
        cases,spaces,coco,sama,predicted=fixtures()
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            score_double_gt(cases[:-1]+(cases[0],),spaces,coco,sama,predicted)

    def test_nonfinite_out_of_range_or_foreign_decoded_outputs_stop(self):
        cases,spaces,coco,sama,predicted=fixtures()
        image_id,name=cases[0]
        head=spaces[name]["yolox_head_idx"]
        invalid=(
            Proposal(head,(float('nan'),0.0,3.0,3.0),.9),
            Proposal(80,BASE_BOX,.9),
            Proposal(head,BASE_BOX,float('inf')),
            "unexpected untyped proposal",
        )
        for proposal in invalid:
            predicted[image_id]=(proposal,)
            with self.assertRaisesRegex(SourceGateError, "STOP_MODEL"):
                score_double_gt(cases,spaces,coco,sama,predicted)


if __name__=="__main__":
    unittest.main()
