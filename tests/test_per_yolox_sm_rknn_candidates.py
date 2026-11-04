"""PER-YOLOX-SM-0: fixture-positive and adversarial source/model gates."""
from __future__ import annotations

import unittest
from unittest import mock

try:
    import numpy as np
except ModuleNotFoundError:
    # The production-oriented all-tests CI intentionally has no NumPy;
    # the dedicated Rockchip host CI runs the full fixture set with NumPy.
    np = None

from experiments import per_yolox_sm_rknn_candidates as sm
from experiments.per_qual1_sama_gt_gate import SourceGateError, TARGETS
from experiments.per80_yolox_coco_public import COCO80_ID_ORDER, Proposal


def blank_heads():
    return [
        np.zeros((1, 85, 80, 80), dtype=np.float32),
        np.zeros((1, 85, 40, 40), dtype=np.float32),
        np.zeros((1, 85, 20, 20), dtype=np.float32),
    ]


def old_rosters():
    return (
        frozenset(range(1, 1233)),
        tuple((i, "ball") for i in range(1233, 1275)),
        tuple((i, "ball") for i in range(1275, 1317)),
    )


def scored_case_fixtures():
    id_map = {
        "sports_ball": 37, "book": 84, "bottle": 44,
        "chair": 62, "dog": 18, "cat": 17, "person": 1,
    }
    maps = {
        name: {"coco_category_id": id_map[name],
               "yolox_head_idx": COCO80_ID_ORDER.index(id_map[name])}
        for name in TARGETS
    }
    cases = tuple((i+1, TARGETS[i//6]) for i in range(42))
    ca, sa, preds = {}, {}, {}
    for ident, label in cases:
        coco_id, head_id = maps[label]["coco_category_id"], maps[label]["yolox_head_idx"]
        ca[(ident, coco_id)] = ((5., 6., 45., 46.),)
        sa[(ident, coco_id)] = ((5., 6., 45., 46.),)
        preds[ident] = (Proposal(head_id, (5., 6., 45., 46.), 0.9),)
    return cases, maps, ca, sa, preds


class RockchipYoloxSMTests(unittest.TestCase):
    def test_positive_historical_1316_are_excluded_exactly(self):
        a, b, c = old_rosters()
        got = sm.combine_exclusions(a, b, c)
        self.assertEqual(1316, len(got))
        self.assertTrue(set(range(1, 1317)) <= got)

    def test_negative_old_id_overlap_or_repetition_fails_closed(self):
        a, b, c = old_rosters()
        with self.assertRaises(SourceGateError):
            sm.combine_exclusions(a, ((1232, "person"),)+b[1:], c)
        with self.assertRaises(SourceGateError):
            sm.combine_exclusions(a, b, ((1233,"cat"),)+c[1:])
        with self.assertRaises(SourceGateError):
            sm.combine_exclusions(a, b, c[:-1]+(c[0],))
        with self.assertRaises(SourceGateError):
            sm.combine_exclusions(frozenset(range(2,1233)), b, c)
        with self.assertRaises(SourceGateError):
            sm.combine_exclusions(a, ((True,"cat"),)+b[1:], c)

    @unittest.skipIf(np is None, "NumPy fixtures run in specialized PER-SM host CI")
    def test_positive_vendor_head_order_is_derived_from_shapes(self):
        a, b, c = blank_heads()
        heads = sm.validate_heads([c, a, b])
        self.assertEqual({80,40,20}, set(heads))
        self.assertEqual((), sm.decode_vendor_heads([c,a,b],width=640,height=640))

    @unittest.skipIf(np is None, "NumPy fixtures run in specialized PER-SM host CI")
    def test_positive_vendor_box_and_class_recover(self):
        heads = blank_heads()
        heads[0][0,4,20,20] = 0.9
        heads[0][0,5+32,20,20] = 0.9
        (p,) = sm.decode_vendor_heads(heads,width=640,height=640)
        self.assertEqual(32, p.class_idx)
        self.assertAlmostEqual(0.81, p.confidence,places=4)
        self.assertEqual((156.,156.,164.,164.),p.box)

    @unittest.skipIf(np is None, "NumPy fixtures run in specialized PER-SM host CI")
    def test_negative_wrong_single_flat_nan_bool_probability_or_duplicate_scale(self):
        heads=blank_heads()
        with self.assertRaises(ValueError):
            sm.validate_heads([np.zeros((1,8400,85),dtype=np.float32)])
        with self.assertRaises(ValueError):
            sm.validate_heads([heads[0], heads[0], heads[2]])
        heads[1][0,4,0,0]=float("nan")
        with self.assertRaises(ValueError):
            sm.validate_heads(heads)
        heads[1][0,4,0,0]=1.01
        with self.assertRaises(ValueError):
            sm.validate_heads(heads)
        heads[1][0,4,0,0]=-0.1
        with self.assertRaises(ValueError):
            sm.validate_heads(heads)

    @unittest.skipIf(np is None, "NumPy fixtures run in specialized PER-SM host CI")
    def test_positive_global_nms_rejects_overlap_even_different_class(self):
        heads=blank_heads()
        heads[0][0,4,20,20]=0.95
        heads[0][0,5+32,20,20]=0.95
        heads[0][0,2,20,20]=np.log(2)
        heads[0][0,3,20,20]=np.log(2)
        heads[1][0,4,10,10]=0.85
        heads[1][0,5+16,10,10]=0.85
        out=sm.decode_vendor_heads(heads,width=640,height=640)
        self.assertEqual(1,len(out))
        self.assertEqual(32,out[0].class_idx)

    @unittest.skipIf(np is None, "NumPy fixtures run in specialized PER-SM host CI")
    def test_negative_geometry_exp_and_weak_objectness(self):
        heads=blank_heads()
        heads[0][0,4,20,20]=0.24
        heads[0][0,5+32,20,20]=1.0
        self.assertEqual((),sm.decode_vendor_heads(heads,width=640,height=640))
        heads[0][0,4,20,20]=1.0
        heads[0][0,2,20,20]=100.
        with self.assertRaises(ValueError):
            sm.decode_vendor_heads(heads,width=640,height=640)
        heads[0][0,2,20,20]=0.
        with self.assertRaises(ValueError):
            sm.decode_vendor_heads(heads,width=True,height=640)

    def test_positive_dual_gt_id_contract_on_42_fixture_cases(self):
        cases,maps,ca,sa,preds = scored_case_fixtures()
        result=sm.score_same_images(cases,maps,ca,sa,preds)
        self.assertEqual(set(TARGETS),set(result))
        for label in TARGETS:
            self.assertEqual(6,result[label]["assigned"])
            self.assertEqual(6,result[label]["gt_coco_boxes"])
            self.assertEqual(6,result[label]["matched_coco_iou50"])
            self.assertEqual(1.0,result[label]["recall_sama_iou50"])

    def test_negative_wrong_head_id_not_falsely_scored(self):
        cases,maps,ca,sa,preds=scored_case_fixtures()
        wrong={name:dict(value) for name,value in maps.items()}
        wrong["cat"]["yolox_head_idx"]=wrong["dog"]["yolox_head_idx"]
        with self.assertRaises(SourceGateError):
            sm.score_same_images(cases,wrong,ca,sa,preds)
        coco_id=maps["sports_ball"]["coco_category_id"]
        del ca[(1,coco_id)]
        with self.assertRaises(SourceGateError):
            sm.score_same_images(cases,maps,ca,sa,preds)

    def test_positive_source_only_makes_no_model_or_media_access(self):
        cases,maps,ca,sa,_=scored_case_fixtures()
        metadata=dict(old_coco_val_ids_excluded=1316,new_public_photos=42)
        with mock.patch.object(sm,"source_and_truth",
                               return_value=(cases,maps,ca,sa,{},metadata)):
            with mock.patch.object(sm,"open_vendor_models") as forbidden:
                # Source branch requires metadata paths even when its
                # implementation is mocked to prohibit actual file access.
                from pathlib import Path
                out=sm.run(Path("unopened-coco.json"),
                           Path("unopened-sama.zip"),stage="source")
        self.assertEqual("SOURCE_PASS_NO_MODELS_NO_PIXELS",out["status"])
        forbidden.assert_not_called()
        self.assertEqual(0,out["input_photo_download_count"])
        self.assertEqual({"s":0,"m":0,"nano":0},out["inferences_executed"])

    @unittest.skipIf(np is None, "NumPy fixtures run in specialized PER-SM host CI")
    def test_positive_synthetic_abi_does_not_depend_on_unavailable_coco(self):
        # Vendor structural compatibility is independently testable even
        # when the third COCO cohort has zero licensed sports balls.
        session_s, session_m = mock.Mock(), mock.Mock()
        session_s.run.return_value = blank_heads()
        session_m.run.return_value = blank_heads()
        vendor = {"s": (session_s, "input"), "m": (session_m, "input")}
        proofs = {"s": {"sha256": "1"*64}, "m": {"sha256": "2"*64}}
        with mock.patch.object(sm, "source_and_truth") as forbidden:
            with mock.patch.object(sm, "open_vendor_models",
                                   return_value=(vendor, proofs)) as opened:
                result = sm.run(None, None, stage="abi",
                                model_s=object(), model_m=object())
        forbidden.assert_not_called()
        opened.assert_called_once()
        self.assertEqual("HOST_VENDOR_ABI_SMOKE_ONLY_NO_PUBLIC_PIXELS",
                         result["status"])
        self.assertEqual("NOT_EVALUATED_ABI_ONLY",
                         result["source"]["status"])
        self.assertFalse(result["source"]["cohort_qualified"])
        self.assertEqual({"s":1,"m":1,"nano":0}, result["inferences_executed"])
        self.assertEqual(0, result["input_photo_download_count"])
        self.assertFalse(result["actual_rk3566_npu_inference"])
        self.assertFalse(result["model_promoted"])

    def test_negative_source_without_metadata_is_not_accidentally_passed(self):
        with mock.patch.object(sm, "source_and_truth") as forbidden:
            with self.assertRaisesRegex(SourceGateError, "metadata files"):
                sm.run(None, None, stage="source")
        forbidden.assert_not_called()

    def test_positive_inventory_counts_photo_licences_without_ids_or_pixels(self):
        excluded = frozenset(range(1, 1317))
        images = {
            1317: (640, 480, "a.jpg", 4),
            1318: (640, 480, "b.jpg", 5),
        }
        official = {name: COCO80_ID_ORDER.index(COCO80_ID_ORDER[0]) + i
                    for i, name in enumerate(TARGETS)}
        boxes = {
            (1317, official["person"]): ((4., 4., 20., 20.),),
            (1318, official["sports_ball"]): ((4., 4., 20., 20.),),
        }
        with mock.patch.object(sm, "_historical_sources",
                               return_value=({}, (), {}, {}, excluded)):
            with mock.patch.object(sm, "_images", return_value=images):
                with mock.patch.object(sm, "_valid_license_ids",
                                       return_value=frozenset({4, 5})):
                    with mock.patch.object(sm, "_category_ids",
                                           return_value=official):
                        with mock.patch.object(sm, "_index_boxes",
                                               return_value=(boxes, set())):
                            r = sm.license_inventory(None, None)
        self.assertEqual("LICENSE_COUNTS_ONLY_NO_SOURCE_PROMOTION", r["status"])
        self.assertEqual(0,r["licence_id4_CC_BY_2_0_sports_ball_paired"])
        self.assertEqual(1,r["counts_by_coco_photo_license"]["5"]
                         ["paired_positive_by_category"]["sports_ball"])
        self.assertFalse(r["photo_pool_qualified"])
        self.assertEqual(0,r["jpeg_bytes_accessed"])
        self.assertEqual(0,r["models_loaded"])
        self.assertNotIn("photo_ids",r)

    def test_positive_inventory_stage_never_downloads_or_opens_models(self):
        inventory = {"status":"LICENSE_COUNTS_ONLY_NO_SOURCE_PROMOTION",
                     "photo_pool_qualified":False}
        with mock.patch.object(sm,"license_inventory",return_value=inventory):
            with mock.patch.object(sm,"open_vendor_models") as unopened:
                result=sm.run(object(),object(),stage="inventory")
        unopened.assert_not_called()
        self.assertEqual("HOST_GT_LICENSE_INVENTORY_ONLY_NO_MEDIA",result["status"])
        self.assertFalse(result["source"]["photo_pool_qualified"])
        self.assertEqual(0,result["input_photo_download_count"])

    def test_negative_no_benchmark_before_frozen_vendor_hash(self):
        cases,maps,ca,sa,_=scored_case_fixtures()
        with mock.patch.object(sm,"source_and_truth",
                               return_value=(cases,maps,ca,sa,{},{})):
            with mock.patch.object(sm,"FROZEN_VENDOR_SHA256",{"s":None,"m":None}):
                with mock.patch.object(sm,"open_vendor_models",
                                       return_value=({"s":(None,"x"),"m":(None,"y")},{})):
                    with self.assertRaises(SourceGateError):
                        sm.run(None,None,stage="benchmark",
                               model_s=object(),model_m=object(),model_nano=object())

    def test_provenance_and_rights_are_not_misrepresented(self):
        self.assertEqual(4,sm.LICENSE_ID)
        self.assertEqual(
            "a39c8476d10c242298d6a8654cb29937a9cc3c062358f4d96367689df23d1796",
            sm.FROZEN_VENDOR_SHA256["s"])
        self.assertEqual(
            "47a76546f3a499b2dbf55cdf2c5ea49bf2b7fa8c943de40edf1ee39b20e45f29",
            sm.FROZEN_VENDOR_SHA256["m"])
        self.assertEqual(640,sm.SIZE)
        self.assertEqual(0.25,sm.SCORE_THRESHOLD)
        self.assertEqual(0.45,sm.NMS_THRESHOLD)
        self.assertEqual(1316,sm.HISTORICAL)
        for name in ("s","m"):
            self.assertEqual("https",sm.MODEL_URLS[name].split(":",1)[0])
            self.assertIn("examples/yolox/yolox_"+name+".onnx",sm.MODEL_URLS[name])


if __name__=="__main__":
    unittest.main()
