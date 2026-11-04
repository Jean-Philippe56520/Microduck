"""Offline score-side fixtures, no model/metadata/network/robot dependencies."""
import unittest
from types import SimpleNamespace

from experiments.per_qual1_sama_gt_gate import TARGETS
from experiments.per_qual1b_yolox_paired42 import _score_against_both, N_IMAGES


def proposal(class_idx, box):
    return SimpleNamespace(class_idx=class_idx, box=box, confidence=.9)


def fixture():
    cases = tuple((i, TARGETS[i // 6]) for i in range(N_IMAGES))
    names = {n:i for i,n in enumerate(TARGETS)}
    boxes = {}
    for ident, label in cases:
        boxes[(ident,names[label])] = ((10.,10.,40.,40.),)
    return cases, names, boxes


class PairedTruthScores(unittest.TestCase):
    def test_identical_truth_scores_identical_against_both(self):
        cases, names, gt = fixture()
        outputs = {i:(proposal(names[name],(10.,10.,40.,40.)),)
                   for i,name in cases}
        rows = _score_against_both(cases,names,gt,gt,outputs)
        for r in rows.values():
            self.assertEqual(r['allocated_photos'], 6)
            self.assertEqual(r['evaluated_photos'], 42)
            self.assertEqual(r['gt_coco_boxes'], 6)
            self.assertEqual(r['gt_sama_boxes'], 6)
            self.assertEqual(r['matched_coco_iou50'], 6)
            self.assertEqual(r['matched_sama_iou50'], 6)
            self.assertEqual(r['recall_delta_sama_minus_coco'], 0.0)

    def test_additional_secondary_truth_reduces_recall_not_model_outputs(self):
        cases,names,gt = fixture()
        sama = dict(gt)
        category=TARGETS[0]
        ident = cases[0][0]
        sama[(ident,names[category])]+=((80.,80.,100.,100.),)
        outputs={i:(proposal(names[label],(10.,10.,40.,40.)),)
                 for i,label in cases}
        rows=_score_against_both(cases,names,gt,sama,outputs)
        self.assertEqual(rows[category]['proposals'],6)
        self.assertEqual(rows[category]['gt_coco_boxes'],6)
        self.assertEqual(rows[category]['gt_sama_boxes'],7)
        self.assertEqual(rows[category]['matched_coco_iou50'],6)
        self.assertEqual(rows[category]['matched_sama_iou50'],6)
        self.assertEqual(rows[category]['recall_coco_iou50'],1.0)
        self.assertEqual(rows[category]['recall_sama_iou50'],round(6/7,6))
        self.assertLess(rows[category]['recall_delta_sama_minus_coco'],0.)

    def test_missing_gt_is_not_assumed_verified_negative(self):
        cases,names,gt = fixture()
        outputs={i:(proposal(names['person'],(80.,80.,100.,100.)),)
                 for i,label in cases}
        scores=_score_against_both(cases,names,gt,gt,outputs)
        self.assertEqual(scores['person']['proposals'],42)
        self.assertEqual(scores['person']['matched_coco_iou50'],0)
        self.assertEqual(scores['person']['coco_unmatched_not_proven_false'],42)
        self.assertFalse('false_positives' in scores['person'])

    def test_one_to_one_matching_non_greedy(self):
        cases,names,gt=fixture()
        selected=cases[0][0]
        cat=names[cases[0][1]]
        gt=dict(gt)
        gt[(selected,cat)]=((1.,0.,11.,10.),(-2.,0.,8.,10.))
        outputs={i:tuple() for i,_ in cases}
        outputs[selected]=(proposal(cat,(0.,0.,10.,10.)),
                           proposal(cat,(2.,0.,12.,10.)))
        scores=_score_against_both(cases,names,gt,gt,outputs)
        self.assertEqual(scores[cases[0][1]]['matched_coco_iou50'],2)
        self.assertEqual(scores[cases[0][1]]['matched_sama_iou50'],2)

    def test_missing_prediction_or_reused_ids_fail_before_scoring(self):
        cases,names,gt=fixture()
        with self.assertRaises(ValueError):
            _score_against_both(cases,names,gt,gt,{})
        with self.assertRaises(ValueError):
            _score_against_both(cases[:-1]+(cases[0],), names,gt,gt,
                                {i:() for i,_ in cases})

    def test_malformed_decoded_proposals_stop(self):
        cases,names,gt=fixture()
        outputs={i:tuple() for i,_ in cases}
        outputs[cases[0][0]]=(proposal(names['person'],(float('nan'),0.,3.,3.)),)
        with self.assertRaises(ValueError):
            _score_against_both(cases,names,gt,gt,outputs)


if __name__=='__main__':
    unittest.main()
