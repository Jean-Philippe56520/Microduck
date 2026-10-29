"""Cat-A2a: deterministic bbox geometry, CC-BY COCO selection, honest metrics.

These tests synthesize *annotations and logits* only; the separate opt-in
Cat-A2a CI runs the REAL model over REAL COCO validation JPEGs. No motors,
Qwen, raw media commits, camera height claim or SQLite modifications.
"""
from __future__ import annotations

from dataclasses import replace
import json
import math
import unittest

from microduck_companion.cata2_bbox_eval import (
    ANNOTATIONS_SHA256, ANNOTATIONS_URL, CATEGORIES, COCO_IDS,
    IMAGE_HOST, MATCH_IOU, NMS_IOU, PHOTO_LICENSE_NAME,
    PHOTO_LICENSE_URL, SEED, Box, CocoCase, decode_boxes, evaluate_localization,
    iou, select_coco_cases,
)
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError


def fixture_annotation():
    """Six only-synthetic cases, one per supported class plus a negative."""
    images = [
        {"id":idx, "file_name":f"{idx:012d}.jpg",
         "width": 416, "height": 416, "license":4}
        for idx in range(1, 7)
    ]
    categories = [
        {"id":category_id, "name":label.replace("_", " ")}
        for label, category_id in COCO_IDS.items()
    ]
    annotations = [
        {"image_id":idx, "category_id":category_id,
         "iscrowd":0, "bbox":[10, 20, 100, 100]}
        for idx, category_id in enumerate(COCO_IDS.values(), 1)
    ]
    return {"images":images, "categories":categories,
            "licenses":[
                {"id":4,"name":PHOTO_LICENSE_NAME,"url":PHOTO_LICENSE_URL},
                {"id":3,"name":"Attribution-NonCommercial License",
                 "url":"http://creativecommons.org/licenses/by-nc/2.0/"},
            ], "annotations":annotations}


def fake_coco(**overrides):
    source=fixture_annotation()
    source.update(overrides)
    return json.dumps(source,sort_keys=True).encode()


def sample(ident, *items):
    return CocoCase(ident, f"{ident:012d}.jpg", 200, 200, tuple(items))


def box(category, *xy, conf=1.):
    return Box(category, tuple(float(n) for n in xy), float(conf))


class CocoBoxContracts(unittest.TestCase):
    def test_predeclared_model_coco_mapping_and_content_pin(self):
        self.assertEqual({"person":0, "cat":15, "dog":16,
                          "sports_ball":32,"chair":56},CATEGORIES)
        self.assertEqual({"person":1, "cat":17, "dog":18,
                          "sports_ball":37, "chair":62},COCO_IDS)
        self.assertEqual(64, len(ANNOTATIONS_SHA256))
        self.assertEqual(
            "e8c7f7908f1d7278341fae127d0da654f102f11bd7b21d8aeefa635b8c810b6f",
            ANNOTATIONS_SHA256)
        self.assertTrue(ANNOTATIONS_URL.endswith("instances_val2017.json"))
        self.assertTrue(IMAGE_HOST.startswith("https://s3.amazonaws.com/images.cocodataset.org/val2017/"))
        self.assertEqual(.5,MATCH_IOU)
        self.assertEqual(.5,NMS_IOU)
        self.assertIn("kwipi",SEED)

    def test_iou_overlap_disjoint_and_edge_contact(self):
        a=box("cat",0,0,10,10)
        b=box("cat",5,5,15,15)
        self.assertAlmostEqual(25/(100+100-25),iou(a,b))
        self.assertEqual(1.,iou(a,a))
        self.assertEqual(0.,iou(a,box("cat",10,0,20,10)))
        self.assertEqual(0.,iou(a,box("dog",80,0,90,10)))

    def test_valid_synthetic_coco_roster_selects_each_category_once(self):
        a=select_coco_cases(fake_coco(),per_class=1,negatives=1)
        b=select_coco_cases(fake_coco(),per_class=1,negatives=1)
        self.assertEqual(a,b)
        self.assertEqual(6,len(a))
        self.assertEqual(6,len({x.image_id for x in a}))
        self.assertEqual(1,sum(not x.ground_truth for x in a))
        self.assertEqual(set(CATEGORIES),{
            gt.category for x in a for gt in x.ground_truth
        })
        self.assertTrue(all(x.filename == f"{x.image_id:012d}.jpg" for x in a))
        self.assertTrue(all(x.width==416 and x.height==416 for x in a))


    def test_disjoint_followup_cohort_reuses_pinned_annotations(self):
        data=fixture_annotation()
        for image in tuple(data["images"]):
            duplicate=dict(image)
            duplicate["id"] += 20
            duplicate["file_name"] = f'{duplicate["id"]:012d}.jpg'
            data["images"].append(duplicate)
        for ann in tuple(data["annotations"]):
            duplicate=dict(ann)
            duplicate["image_id"] += 20
            data["annotations"].append(duplicate)
        blob=json.dumps(data).encode()
        original=select_coco_cases(blob,per_class=1,negatives=1)
        holdout=select_coco_cases(
            blob,per_class=1,negatives=1,
            excluded_image_ids=frozenset(c.image_id for c in original))
        self.assertEqual(6,len(original))
        self.assertEqual(6,len(holdout))
        self.assertFalse({c.image_id for c in original} &
                         {c.image_id for c in holdout})
        self.assertEqual(original,select_coco_cases(
            blob,per_class=1,negatives=1,
            excluded_image_ids=frozenset()))
        self.assertEqual(set(CATEGORIES),{
            b.category for case in holdout for b in case.ground_truth})
        self.assertEqual(1,sum(not x.ground_truth for x in holdout))
        self.assertEqual(holdout,select_coco_cases(
            blob,per_class=1,negatives=1,
            excluded_image_ids=frozenset(c.image_id for c in original)))

    def test_disjoint_cohort_fails_closed_on_invalid_exclusion(self):
        blob=fake_coco()
        for excluded in ({1},frozenset({-1}),frozenset({"1"}),
                         frozenset({True}),frozenset(range(26))):
            with self.subTest(excluded=excluded):
                with self.assertRaises(PhotoBaselineError):
                    select_coco_cases(blob,per_class=1,negatives=1,
                                      excluded_image_ids=excluded)
        with self.assertRaisesRegex(PhotoBaselineError,"insufficient licensed"):
            select_coco_cases(blob,per_class=1,negatives=1,
                              excluded_image_ids=frozenset(range(1,7)))

    def test_coco_unknown_is_absence_of_target_annotations_only(self):
        # Five-class labels do not certify absence of unlabelled real subjects.
        result=evaluate_localization((
            (sample(1), (box("person",1,1,50,50,conf=.51),)),
            (sample(2), ()),
        ))
        self.assertEqual(2,result["images_with_no_gt_target"])
        self.assertEqual(1,result["empty_gt_images_with_false_alarm"])
        self.assertEqual(1,result["empty_gt_images_without_false_alarm"])
        self.assertEqual(1,result["fp_iou50"])


    def test_disallowed_noncommercial_licence_is_excluded(self):
        data=fixture_annotation()
        data["images"][0]["license"]=3
        with self.assertRaisesRegex(PhotoBaselineError,"insufficient licensed"):
            select_coco_cases(json.dumps(data).encode(),per_class=1,negatives=1)

    def test_missing_or_misnamed_coco_classes_rejected(self):
        data=fixture_annotation()
        data["categories"][0]["name"]="driver"
        with self.assertRaisesRegex(PhotoBaselineError,"class order"):
            select_coco_cases(json.dumps(data).encode(),per_class=1,negatives=1)

    def test_crowd_and_invalid_ground_truth_disqualify_whole_sample(self):
        for mutate in ("crowd","negative_width","outside"):
            data=fixture_annotation()
            a=data["annotations"][0]
            if mutate=="crowd":
                a["iscrowd"]=1
            elif mutate=="negative_width":
                a["bbox"]=[1,1,-1,20]
            else:
                a["bbox"]=[600,600,10,10]
            with self.subTest(mutate=mutate):
                with self.assertRaisesRegex(PhotoBaselineError,"insufficient licensed"):
                    select_coco_cases(json.dumps(data).encode(),
                                      per_class=1,negatives=1)

    def test_invalid_coco_schema_and_leakage_rejected(self):
        for obj in (
            {"images":[]}, {"images":None,"annotations":[],"licenses":[],"categories":[]},
            fixture_annotation() | {"categories": []},
        ):
            with self.subTest(obj=obj):
                with self.assertRaises(PhotoBaselineError):
                    select_coco_cases(json.dumps(obj).encode(),
                                      per_class=1,negatives=1)
        with self.assertRaises(PhotoBaselineError):
            select_coco_cases(b"untrusted",per_class=1,negatives=1)
        with self.assertRaises(PhotoBaselineError):
            select_coco_cases(fake_coco(),per_class=0,negatives=1)
        with self.assertRaises(PhotoBaselineError):
            select_coco_cases(fake_coco(),per_class=1,negatives=5)

    def test_one_to_one_match_and_duplicate_false_positive(self):
        case=sample(1,box("cat",0,0,50,50),box("cat",100,100,150,150))
        preds=(
            box("cat",0,0,50,50,conf=.95),
            box("cat",0,0,50,50,conf=.80),  # duplicate -> FP
            box("dog",100,100,150,150,conf=.90),  # wrong class -> FP
        )
        result=evaluate_localization(((case,preds),))
        self.assertEqual((1,2,1), (result["tp_iou50"],
                                    result["fp_iou50"],result["fn_iou50"]))
        self.assertEqual((2,3), (result["gt_instances"],
                                 result["proposed_boxes"]))
        self.assertEqual((1,1,1),(
            result["by_class"]["cat"]["tp_iou50"],
            result["by_class"]["cat"]["fp_iou50"],
            result["by_class"]["cat"]["fn_iou50"],
        ))
        self.assertEqual(0.5,result["recall_iou50"])
        self.assertAlmostEqual(1/3,result["precision_iou50"],places=6)

    def test_perfect_two_categories_and_a_negative_yield_one_ap(self):
        r=evaluate_localization((
            (sample(11,box("person",5,5,100,100)),
             (box("person",5,5,100,100,conf=.81),)),
            (sample(12,box("chair",15,10,130,160)),
             (box("chair",15,10,130,160,conf=.95),)),
            (sample(13),()),
        ))
        self.assertEqual(2,r["tp_iou50"])
        self.assertEqual(0,r["fp_iou50"])
        self.assertEqual(0,r["fn_iou50"])
        self.assertEqual(1.,r["macro_ap50_101point_present_classes"])
        self.assertIsNone(r["by_class"]["dog"]["ap50_101point"])
        self.assertEqual((1,1,0),(r["images_with_no_gt_target"],
                                  r["empty_gt_images_without_false_alarm"],
                                  r["empty_gt_images_with_false_alarm"]))

    def test_empty_gt_false_alarms_are_counted_not_assumed_correct(self):
        result=evaluate_localization((
            (sample(1), (box("person",5,5,100,100,conf=.4),)),
        ))
        self.assertEqual(1,result["empty_gt_images_with_false_alarm"])
        self.assertIsNone(result["recall_iou50"])
        self.assertIsNone(result["macro_ap50_101point_present_classes"])
        self.assertEqual(1,result["fp_iou50"])

    def test_malformed_output_and_duplicate_image_results_are_rejected(self):
        case=sample(2,box("cat",0,0,40,40))
        for records in (
            (), ((case,()),(case,())),
            ((case,(box("cat",199,199,210,210),)),),
        ):
            with self.subTest(records=records):
                with self.assertRaises(PhotoBaselineError):
                    evaluate_localization(records)
        with self.assertRaises(PhotoBaselineError):
            box("cat",0,0,0,1)
        with self.assertRaises(PhotoBaselineError):
            box("person",0,0,10,10,conf=float("nan"))
        with self.assertRaises(PhotoBaselineError):
            CocoCase(1,"../../somewhere.jpg",200,200,())

    @unittest.skipUnless(
        __import__("importlib").util.find_spec("numpy"),"NumPy optional")
    def test_real_yolox_head_box_mapping_and_classwise_nms(self):
        import numpy as np
        raw=np.zeros((1,3549,85),dtype=np.float32)
        # Cell 0 -> center=(1,1)*8; cell 1 -> center=(0+1,1)*8.
        # Both predict exactly the same cat box, NMS suppresses one.
        for anchor,x in ((0,1.),(1,0.)):
            raw[0,anchor,:4]=[x,1.,math.log(2),math.log(2)]
            raw[0,anchor,4]=.95
            raw[0,anchor,5+15]=.9 if anchor==0 else .8
        pred=decode_boxes(raw,width=416,height=416)
        self.assertEqual(1,len(pred))
        self.assertEqual("cat",pred[0].category)
        self.assertAlmostEqual(.855,pred[0].confidence,places=5)
        self.assertAlmostEqual(0.,pred[0].xyxy[0],places=4)
        self.assertAlmostEqual(16.,pred[0].xyxy[2],places=4)

    @unittest.skipUnless(
        __import__("importlib").util.find_spec("numpy"),"NumPy optional")
    def test_boundary_reprojection_is_clamped_after_float_scale(self):
        import numpy as np
        # 416 * (417 / 416) may exceed 417 by one floating ULP.
        raw=np.zeros((1,3549,85),dtype=np.float32)
        raw[0,0,:4]=[53.,2.,2.,2.]
        raw[0,0,4]=.95
        raw[0,0,5+56]=.90
        pred=decode_boxes(raw,width=417,height=32)
        self.assertEqual(1,len(pred))
        self.assertEqual("chair",pred[0].category)
        self.assertEqual(417.,pred[0].xyxy[2])
        self.assertTrue(all(0 <= v <= bound for v,bound in zip(
            pred[0].xyxy,(417,32,417,32))))
        self.assertEqual(1,evaluate_localization((
            (sample(10,box("chair",0,0,200,100)),()),
        ))["fn_iou50"])

    @unittest.skipUnless(
        __import__("importlib").util.find_spec("numpy"),"NumPy optional")
    def test_letterbox_padding_is_excluded_from_detection(self):
        import numpy as np
        raw=np.zeros((1,3549,85),dtype=np.float32)
        # Image 416x208 -> resized 416x208, padding below y>=208.
        # Grid 16,16 is at (132,132) in valid area; grid 16,40 in padding.
        for anchor in (16*52+16,40*52+16):
            raw[0,anchor,:4]=[.5,.5,0.,0.]
            raw[0,anchor,4]=.95
            raw[0,anchor,5+16]=.9
        pred=decode_boxes(raw,width=416,height=208)
        self.assertEqual(1,len(pred))
        self.assertEqual("dog",pred[0].category)
        self.assertLess(pred[0].xyxy[3],208.)


if __name__=="__main__":
    unittest.main()
