"""Cat-A2b low viewpoint: fake private fixtures, strict provenance and gates.

NO real photo, identity, secret, location, camera capture, motor, or model
weight enters the repository or GitHub Actions. Host-only unit tests.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from microduck_companion.cata2_bbox_eval import Box
from microduck_companion.cata2b_private_low import (
    SOURCE, MIN_HEIGHT_MM, MAX_HEIGHT_MM, LowDataset,
    benchmark_private_low_dataset, load_private_low_dataset,
    summarize_private_dataset, main,
)
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError

HAS_PIL = importlib.util.find_spec("PIL") is not None


def identifier(prefix, index):
    return f"{prefix}-{index:016x}"


def jpeg(color, *, width=80, height=120):
    from PIL import Image
    buffer = BytesIO()
    Image.new("RGB", (width, height), color).save(
        buffer, format="JPEG",
    )
    return buffer.getvalue()


@unittest.skipUnless(HAS_PIL, "Pillow only in focused Cat-A2b CI")
class PrivateLowCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "images").mkdir()
        (self.root / "evidence").mkdir()
        self.manifest = self.root / "manifest.json"
        self.data = {
            "schema_version": 1,
            "source": SOURCE,
            "sessions": [],
            "samples": [],
        }
        for index, split in enumerate(
            ("train", "validation", "test", "test"), start=1
        ):
            sample_id = identifier("s", index)
            session_id = identifier("g", index)
            site_id = identifier("g", index+100)
            scene_id = identifier("g", index+200)
            evidence = f"e-{index:016x}.jpg"
            evidence_bytes = jpeg((index*10, 180, 200), height=72)
            (self.root / "evidence" / evidence).write_bytes(evidence_bytes)
            self.data["sessions"].append({
                "session_id": session_id,
                "site_group_id": site_id,
                "camera_height_mm": 190 + index*10,
                "ruler_evidence_file": evidence,
                "ruler_evidence_sha256": sha256(evidence_bytes).hexdigest(),
                "measurement_method": "ruler_at_optical_center",
            })
            image_bytes = jpeg((index*20, 80, 80))
            (self.root / "images" / f"{sample_id}.jpg").write_bytes(image_bytes)
            label = ("cat", "dog", "chair", None)[index-1]
            self.data["samples"].append({
                "sample_id": sample_id, "session_id": session_id,
                "scene_group_id": scene_id, "split": split,
                "image_sha256": sha256(image_bytes).hexdigest(),
                "image_width": 80, "image_height": 120,
                "boxes": ([{
                    "category": label, "xyxy": [10,20,35,55],
                    "visibility": "partial" if split == "test" else "full",
                }] if label is not None else []),
                "all_targets_reviewed": True,
                "privacy_and_consent_reviewed": True,
            })
        self.write()

    def write(self):
        self.manifest.write_text(
            json.dumps(self.data, sort_keys=True), encoding="utf-8"
        )

    def validate(self):
        self.write()
        return load_private_low_dataset(self.manifest)

    def test_valid_private_capture_is_not_claimed_independent(self):
        data = self.validate()
        self.assertIsInstance(data, LowDataset)
        result = summarize_private_dataset(data)
        self.assertEqual(
            {"train":1, "validation":1, "test":2},
            result["dataset_splits"])
        self.assertEqual([200, 230],
                         result["declared_low_optical_center_range_mm"])
        self.assertEqual(1, result["test_partial_objects"])
        self.assertEqual(1, result["test_negative_images"])
        self.assertFalse(result["model_evaluated"])
        self.assertFalse(result["independent_height_validation"])
        self.assertFalse(result["robot_camera_viewpoint_confirmed"])
        self.assertFalse(result["personal_media_published"])
        self.assertEqual(0, result["sqlite_writes"])
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertNotIn("images/", json.dumps(result))
        self.assertNotIn("evidence/", json.dumps(result))
        self.assertNotIn("camera-ruler.jpg", json.dumps(result))

    def test_private_coverage_reports_omissions_only_from_test(self):
        report = summarize_private_dataset(self.validate())
        counts = report["coverage_by_split_operator_declared"]
        self.assertEqual(1, counts["train"]["categories"]["cat"]["annotated_instances"])
        self.assertEqual(1, counts["validation"]["categories"]["dog"]["annotated_instances"])
        self.assertEqual(0, counts["test"]["categories"]["cat"]["annotated_instances"])
        self.assertEqual(1, counts["test"]["categories"]["chair"]["partial_instances"])
        self.assertEqual(1, counts["test"]["categories"]["chair"]["images_with_class"])
        self.assertEqual(1, counts["test"]["negative_images"])
        self.assertEqual(2, counts["test"]["declared_sessions"])
        self.assertEqual(2, counts["test"]["declared_sites"])
        self.assertEqual(
            {"person", "cat", "dog", "sports_ball"}, set(report["missing_test_categories"]))
        self.assertIn("person", report["test_categories_without_partial_examples"])
        self.assertTrue(report["coverage_counts_do_not_prove_independent_captures"])
        public = json.dumps(report)
        for secret in (str(self.root), "g-000000000000", "s-000000000000",
                       "e-000000000000"):
            self.assertNotIn(secret, public)

    def test_coverage_counts_instances_and_photos_separately(self):
        self.data["samples"][2]["boxes"].extend([
            {"category": "chair", "xyxy": [40, 60, 70, 90], "visibility": "full"},
            {"category": "dog", "xyxy": [15, 55, 40, 85], "visibility": "partial"},
        ])
        report = summarize_private_dataset(self.validate())
        counts = report["coverage_by_split_operator_declared"]["test"]
        chair = counts["categories"]["chair"]
        self.assertEqual(2, chair["annotated_instances"])
        self.assertEqual(1, chair["images_with_class"])
        self.assertEqual(1, chair["full_instances"])
        self.assertEqual(1, chair["partial_instances"])
        self.assertEqual(1, chair["declared_sessions_with_class"])
        self.assertEqual(1, chair["declared_sites_with_class"])
        self.assertNotIn("dog", report["missing_test_categories"])
        self.assertNotIn("dog", report["test_categories_without_partial_examples"])
        self.assertEqual(1, counts["categories"]["dog"]["annotated_instances"])
        self.assertEqual(1, counts["negative_images"])

    def test_manifest_with_private_name_or_path_field_rejected(self):
        for key, value in (
            ("name", "anonymous-person?"), ("image_file", "../../etc/passwd"),
            ("latitude", 48.1234), ("face_id", "person-1"),
            ("audio_file", "private.wav"), ("url", "https://example.org"),
        ):
            with self.subTest(key=key):
                altered = deepcopy(self.data)
                altered["samples"][0][key] = value
                self.data = altered
                with self.assertRaises(PhotoBaselineError):
                    self.validate()
                del self.data["samples"][0][key]

    def test_nonconsent_or_unreviewed_target_refused(self):
        for key in ("privacy_and_consent_reviewed", "all_targets_reviewed"):
            self.data["samples"][2][key] = False
            with self.assertRaises(PhotoBaselineError):
                self.validate()
            self.data["samples"][2][key] = True
        self.data["source"] = "downloaded_unlicensed_photo"
        with self.assertRaises(PhotoBaselineError):
            self.validate()

    def test_height_cannot_be_inferred_from_robot_total_height(self):
        self.data["sessions"][0]["camera_height_mm"] = MAX_HEIGHT_MM + 1
        with self.assertRaises(PhotoBaselineError):
            self.validate()
        self.data["sessions"][0]["camera_height_mm"] = MIN_HEIGHT_MM - 1
        with self.assertRaises(PhotoBaselineError):
            self.validate()
        self.data["sessions"][0]["camera_height_mm"] = 200
        self.data["sessions"][0]["measurement_method"] = "robot_total_height"
        with self.assertRaises(PhotoBaselineError):
            self.validate()
        self.data["sessions"][0]["measurement_method"] = "ruler_at_optical_center"
        self.assertEqual(200, self.validate().sessions[0].camera_height_mm)

    def test_evidence_and_photo_sha_or_geometry_mismatch_fail_closed(self):
        self.data["sessions"][1]["ruler_evidence_sha256"] = "0"*64
        with self.assertRaisesRegex(PhotoBaselineError, "evidence hash"):
            self.validate()
        evidence = self.data["sessions"][1]["ruler_evidence_file"]
        self.data["sessions"][1]["ruler_evidence_sha256"] = sha256(
            (self.root / "evidence" / evidence).read_bytes()
        ).hexdigest()
        self.data["samples"][2]["image_sha256"] = "f"*64
        with self.assertRaisesRegex(PhotoBaselineError, "checksum"):
            self.validate()
        self.data["samples"][2]["image_sha256"] = sha256(
            (self.root / "images" / "s-0000000000000003.jpg").read_bytes()
        ).hexdigest()
        self.data["samples"][2]["image_width"] = 100
        with self.assertRaisesRegex(PhotoBaselineError, "geometry"):
            self.validate()

    def test_symlink_photo_and_evidence_refused(self):
        photo = self.root / "images" / "s-0000000000000003.jpg"
        original = photo.read_bytes()
        photo.unlink()
        target = self.root / "private.jpg"
        target.write_bytes(original)
        photo.symlink_to(target)
        with self.assertRaises(PhotoBaselineError):
            self.validate()
        photo.unlink()
        photo.write_bytes(original)
        evidence = self.root / "evidence" / "e-0000000000000003.jpg"
        content = evidence.read_bytes()
        evidence.unlink()
        other = self.root / "ruler-private.jpg"
        other.write_bytes(content)
        evidence.symlink_to(other)
        with self.assertRaises(PhotoBaselineError):
            self.validate()

    def test_same_session_scene_or_site_cannot_cross_splits(self):
        for field, section in (
            ("session_id", "samples"),
            ("scene_group_id", "samples"),
        ):
            old = self.data["samples"][2][field]
            self.data["samples"][2][field] = self.data["samples"][0][field]
            with self.subTest(field=field):
                with self.assertRaisesRegex(PhotoBaselineError, "leakage"):
                    self.validate()
            self.data["samples"][2][field] = old
        orig = self.data["sessions"][2]["site_group_id"]
        self.data["sessions"][2]["site_group_id"] = (
            self.data["sessions"][0]["site_group_id"])
        with self.assertRaisesRegex(PhotoBaselineError, "leakage"):
            self.validate()
        self.data["sessions"][2]["site_group_id"] = orig

    def test_duplicated_media_bytes_refused(self):
        a = self.root / "images" / "s-0000000000000001.jpg"
        b = self.root / "images" / "s-0000000000000002.jpg"
        b.write_bytes(a.read_bytes())
        self.data["samples"][1]["image_sha256"] = sha256(
            b.read_bytes()).hexdigest()
        with self.assertRaisesRegex(PhotoBaselineError, "duplicate"):
            self.validate()

    def test_unsupported_human_part_labels_and_bbox_refused(self):
        self.data["samples"][2]["boxes"][0]["category"] = "shoe"
        with self.assertRaisesRegex(PhotoBaselineError, "unsupported class"):
            self.validate()
        self.data["samples"][2]["boxes"][0]["category"] = "chair"
        self.data["samples"][2]["boxes"][0]["xyxy"] = [10,20,82,110]
        with self.assertRaisesRegex(PhotoBaselineError, "outside"):
            self.validate()
        self.data["samples"][2]["boxes"][0]["xyxy"] = [10,20,35,55]
        self.data["samples"][2]["boxes"][0]["visibility"] = "unknown"
        with self.assertRaises(PhotoBaselineError):
            self.validate()

    def test_no_learned_score_from_unannotated_or_incomplete_test(self):
        self.data["samples"][3]["split"] = "validation"
        with self.assertRaises(PhotoBaselineError):
            self.validate()
        self.data["samples"][3]["split"] = "test"
        self.data["samples"][3]["boxes"] = [{
            "category":"chair", "xyxy":[1,1,35,55], "visibility":"full"}]
        with self.assertRaisesRegex(PhotoBaselineError, "incomplete test"):
            self.validate()

    def test_cli_requires_explicit_privacy_authorization(self):
        from contextlib import redirect_stderr
        err = BytesIO()
        # argparse emits expected diagnostics; no external access or images.
        with patch("sys.stderr", new=SimpleNamespace(write=lambda x: len(x))):
            with self.assertRaises(SystemExit) as ctx:
                main(["--manifest",str(self.manifest),"--validate-only"])
            self.assertEqual(2,ctx.exception.code)
        self.validate()
        with patch("builtins.print") as seen:
            self.assertEqual(0,main([
                "--manifest",str(self.manifest),"--validate-only",
                "--approved-private-local-media",
            ]))
        result = json.loads(seen.call_args.args[0])
        self.assertEqual(2, result["test_image_count"])
        self.assertFalse(result["independent_height_validation"])

    def test_reuses_cata2a_iou_evaluator_without_new_models(self):
        data = self.validate()
        fake_session = SimpleNamespace(
            get_inputs=lambda:[SimpleNamespace(name="images",shape=[1,3,416,416])],
            get_outputs=lambda:[SimpleNamespace(name="output",shape=[1,3549,85])],
            run=lambda *args:[object()],
        )
        fake_ort = SimpleNamespace(
            SessionOptions=type("FakeOptions",(),{}),
            InferenceSession=lambda *a,**kw:fake_session,
        )
        with patch("microduck_companion.cata2b_private_low.validate_model_file"), \
             patch.dict(sys.modules,{"onnxruntime":fake_ort}), \
             patch("microduck_companion.cata2b_private_low.prepare_image",
                   return_value=object()), \
             patch("microduck_companion.cata2b_private_low.decode_boxes",
                   side_effect=[
                       (Box("chair",(10.,20.,35.,55.),.9),), (),
                   ]):
            score = benchmark_private_low_dataset(
                data, model_path=self.root / "fake-not-an-onnx-model",
            )
        self.assertTrue(score["model_evaluated"])
        self.assertEqual(1,score["test_metrics"]["tp_iou50"])
        self.assertEqual(0,score["test_metrics"]["fp_iou50"])
        self.assertEqual(0,score["test_metrics"]["fn_iou50"])
        self.assertEqual(1,score["subgroups_image_level_not_instance_level"][
            "has_partial"]["tp_iou50"])
        self.assertEqual(1,score["subgroups_image_level_not_instance_level"][
            "no_target"]["empty_gt_images_without_false_alarm"])
        self.assertIsNone(score["subgroups_image_level_not_instance_level"]["full_only"])
        self.assertFalse(score["independent_height_validation"])
        self.assertFalse(score["robot_or_rknn_validated"])
        self.assertEqual(0,score["motor_commands"])
        self.assertEqual(0,score["sqlite_writes"])
        self.assertNotIn(str(self.root),json.dumps(score))

    def test_model_sha_validation_rejects_unapproved_model(self):
        data = self.validate()
        with self.assertRaises(PhotoBaselineError):
            benchmark_private_low_dataset(
                data, model_path=self.root / "unapproved-weights.onnx")


if __name__=="__main__":
    unittest.main()
