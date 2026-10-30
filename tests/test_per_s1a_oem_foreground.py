"""PER-S1A positive/negative feature gates, source separation; no model/camera."""
from __future__ import annotations

import math
import unittest

from experiments.per_s1a_oem_foreground import (
    CASES, BallGTError, assess, _mask_iou, _shape_compactness,
    predict_from_region, score_proposal,
)
from experiments.per_s0_lowview_oem_region import validate_preflight


def rows_for_gate():
    rows=[]
    for i,c in enumerate(CASES):
        if i==6:
            rows.append({"case":c.name,"had_region":False,
                         "descriptor_produced":False})
        elif i<4:
            rows.append({
                "case":c.name,"had_region":True,
                "top1_iou":.75,"descriptor_produced":True,
                "mask_iou":.71,"colour_error_rgb":14.,
                "shape_compactness_error":.10,
                "rectangle_mask_iou":.48,
                "rectangle_colour_error_rgb":55.,
                "feature_host_ms":4.})
        else:
            rows.append({"case":c.name,"had_region":False,
                         "descriptor_produced":False,
                         "top1_iou":0.,"feature_host_ms":0.})
    return rows


def geometry():
    return [{
        "case": c.name, "role":c.role,
        "pose_static":True,"valid_geometry":True,
        "geom_pixels":0 if c.role=="empty_negative" else 1000,
        "geom_bbox_xyxy":None if c.role=="empty_negative" else [15,30,80,90],
    } for c in CASES]


class TestPerS1AContract(unittest.TestCase):
    def test_new_specs_unique_independent_from_s0_case_ids(self):
        from experiments.per_s0_lowview_oem_region import CASES as S0
        self.assertEqual(len(CASES),7)
        self.assertEqual(len({x.name for x in CASES}),7)
        self.assertFalse(set(x.name for x in CASES)&set(x.name for x in S0))
        self.assertEqual(CASES[-1].scene,"scene.xml")

    def test_reused_oem_preflight_exact_list_and_negative(self):
        self.assertTrue(validate_preflight(geometry(),authorized_cases=CASES))
        with self.assertRaises(BallGTError):
            validate_preflight(geometry()[:-1],authorized_cases=CASES)
        data=geometry()
        data[-1]["geom_pixels"]=20
        with self.assertRaises(BallGTError):
            validate_preflight(data,authorized_cases=CASES)

    def test_positive_decision_without_oracle_model_name(self):
        out=assess(rows_for_gate())
        self.assertTrue(out["functional_value_gate_met"])
        self.assertEqual(out["top1_region_iou50"],4)
        self.assertEqual(out["complete_mask_colour_compactness"],4)
        self.assertEqual(out["false_confident_when_not_located"],0)

    def test_stop_on_wrong_region_even_if_colour_looks_right(self):
        data=rows_for_gate()
        data[4].update(descriptor_produced=True,colour_error_rgb=0.,
                       mask_iou=0.,shape_compactness_error=0.,
                       rectangle_mask_iou=0.,rectangle_colour_error_rgb=0.)
        out=assess(data)
        self.assertEqual(out["false_confident_when_not_located"],1)
        self.assertFalse(out["functional_value_gate_met"])

    def test_stop_on_missed_colour_shape_or_rectangle_gain(self):
        data=rows_for_gate()
        for x in data[:4]:
            x["colour_error_rgb"]=75.
        self.assertFalse(assess(data)["functional_value_gate_met"])
        data=rows_for_gate()
        for x in data[:4]:
            x["shape_compactness_error"]=.35
        self.assertFalse(assess(data)["functional_value_gate_met"])
        data=rows_for_gate()
        for x in data[:4]:
            x["mask_iou"]=.40
        self.assertFalse(assess(data)["functional_value_gate_met"])
        data=rows_for_gate()
        for x in data[:4]:
            x["rectangle_colour_error_rgb"]=10.
        self.assertFalse(assess(data)["functional_value_gate_met"])

    def test_negative_activity_or_high_cpu_stops(self):
        data=rows_for_gate()
        data[-1]["had_region"]=True
        self.assertFalse(assess(data)["functional_value_gate_met"])
        data=rows_for_gate()
        data[0]["feature_host_ms"]=300.
        self.assertFalse(assess(data)["functional_value_gate_met"])

    def test_reject_missing_case_nan_and_fake_fields(self):
        with self.assertRaises(BallGTError):
            assess(rows_for_gate()[:-1])
        with self.assertRaises(BallGTError):
            assess(rows_for_gate()[::-1])
        data=rows_for_gate()
        data[2]["mask_iou"]=float("nan")
        with self.assertRaises(BallGTError):
            assess(data)
        data=rows_for_gate()
        data[2]["top1_iou"]=-.5
        with self.assertRaises(BallGTError):
            assess(data)


class TestPerS1AVisualPredictor(unittest.TestCase):
    def setUp(self):
        try:
            import cv2
            import numpy as np
        except ImportError:
            self.skipTest("NumPy and OpenCV present in pinned dedicated CI")
        self.cv2=cv2
        self.np=np

    def test_circle_on_different_background_has_foreground_candidate(self):
        np,cv2=self.np,self.cv2
        rgb=np.full((640,360,3),90,dtype=np.uint8)
        cv2.circle(rgb,(180,260),22,(225,35,45),-1)
        desc,mask=predict_from_region(rgb,(145.,225.,215.,295.))
        self.assertIsNotNone(desc)
        self.assertTrue(mask[260,180])
        self.assertFalse(mask[230,147])
        self.assertLess(desc["color_rgb_median_unverified"][1],50)
        self.assertFalse(desc["confidence_of_color_and_shape_known"])
        self.assertIsNotNone(_shape_compactness(mask))

    def test_uniform_background_and_degenerate_region_abstain(self):
        np=self.np
        rgb=np.full((640,360,3),160,dtype=np.uint8)
        self.assertEqual(predict_from_region(rgb,(145.,225.,215.,295.)),
                         (None,None))
        self.assertEqual(predict_from_region(rgb,(100.,100.,105.,200.)),
                         (None,None))

    def test_bad_image_bbox_nonfinite_rejected(self):
        np=self.np
        good=np.zeros((640,360,3),dtype=np.uint8)
        for image in (good.astype(np.float32),good[:200],None):
            with self.assertRaises(BallGTError):
                predict_from_region(image,(100.,100.,200.,200.))
        for bbox in ((-1.,0.,200.,200.),(1.,1.,float("nan"),90.),
                     (0.,0.,400.,100.),(10.,20.,10.,100.)):
            with self.assertRaises(BallGTError):
                predict_from_region(good,bbox)

    def test_scoring_never_selects_region_using_mask_truth(self):
        np,cv2=self.np,self.cv2
        rgb=np.full((640,360,3),90,dtype=np.uint8)
        oracle=np.zeros((640,360),dtype=np.bool_)
        cv2.circle(rgb,(180,260),22,(225,35,45),-1)
        cv2.circle(oracle.view(np.uint8),(180,260),22,1,-1)
        # Tight rectangle around the synthetic circle: GT bbox IoU >0.50.
        box=(153.,233.,207.,287.)
        first={"xyxy":box,"score":.8,"untrusted_coco_class_index":11}
        other={"xyxy":(80.,40.,120.,90.),"score":.3,
               "untrusted_coco_class_index":2}
        result=score_proposal("red_cube_near",rgb,oracle,[first,other])
        self.assertTrue(result["descriptor_produced"])
        self.assertGreater(result["top1_iou"],.50)
        self.assertEqual(result["candidate_class_unverified"],11)
        # Flip GT to a different patch. The RGB-only proposed features
        # stay identical; only independent benchmark measurement changes.
        changed=np.zeros_like(oracle)
        changed[40:90,80:120]=True
        d1,m1=predict_from_region(rgb,box)
        d2,m2=predict_from_region(rgb,box)
        self.assertEqual(d1,d2)
        self.assertTrue(np.array_equal(m1,m2))
        result_wrong=score_proposal("red_cube_near",rgb,changed,[first,other])
        self.assertEqual(result_wrong["candidate_class_unverified"],11)
        self.assertEqual(result_wrong["descriptor_produced"],True)
        self.assertLess(result_wrong["top1_iou"],.50)
        with self.assertRaises(TypeError):
            predict_from_region(rgb,box,oracle_mask=oracle)

    def test_bad_mask_provenance_rejected(self):
        np=self.np
        rgb=np.zeros((640,360,3),dtype=np.uint8)
        bad=np.zeros((360,640),dtype=np.bool_)
        with self.assertRaises(BallGTError):
            score_proposal("red_cube_near",rgb,bad,[])
        with self.assertRaises(BallGTError):
            _mask_iou(np.zeros((640,360),dtype=np.uint8),
                      np.zeros((640,360),dtype=np.bool_))


if __name__=="__main__":
    unittest.main()
