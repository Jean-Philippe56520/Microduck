"""Cat-A2b blinded review gate on generated images only.

No real photographs, annotator identities, model output, secrets, Ollama,
network access or robot control are used by these tests.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.cata2b_blind_review import (
    REVIEW_SOURCE, main, review_blind_test_annotations, _matched_boxes,
)
from microduck_companion.cata2_bbox_eval import Box
from microduck_companion.cata2b_private_low import SOURCE
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError

HAS_PIL = importlib.util.find_spec("PIL") is not None


def ident(prefix, i):
    return f"{prefix}-{i:016x}"


def fake_jpeg(index):
    from PIL import Image
    buffer = BytesIO()
    Image.new("RGB", (80, 120), (index * 20, 100, 180)).save(
        buffer, format="JPEG",
    )
    return buffer.getvalue()


@unittest.skipUnless(HAS_PIL, "Pillow is required in Cat-A2b CI")
class BlindReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("images", "evidence", "reviews"):
            (self.root / name).mkdir()
        self.manifest = self.root / "manifest.json"
        self.review_first_path = self.root / "reviews" / "r-0000000000000001.json"
        self.review_second_path = self.root / "reviews" / "r-0000000000000002.json"
        self.capture = {
            "schema_version": 1, "source": SOURCE,
            "sessions": [], "samples": [],
        }
        for i, split in enumerate(("train", "validation", "test", "test"), 1):
            sample_id = ident("s", i)
            session_id = ident("g", i)
            evidence_name = f"e-{i:016x}.jpg"
            evidence = fake_jpeg(i + 4)
            (self.root / "evidence" / evidence_name).write_bytes(evidence)
            self.capture["sessions"].append({
                "session_id": session_id, "site_group_id": ident("g", 100+i),
                "camera_height_mm": 200,
                "ruler_evidence_file": evidence_name,
                "ruler_evidence_sha256": sha256(evidence).hexdigest(),
                "measurement_method": "ruler_at_optical_center",
            })
            image = fake_jpeg(i)
            (self.root / "images" / f"{sample_id}.jpg").write_bytes(image)
            boxes = [{
                "category": "chair" if split == "test" else "cat",
                "xyxy": [10, 20, 35, 55], "visibility": "partial",
            }] if i != 4 else []
            self.capture["samples"].append({
                "sample_id": sample_id, "session_id": session_id,
                "scene_group_id": ident("g", 200+i), "split": split,
                "image_sha256": sha256(image).hexdigest(),
                "image_width": 80, "image_height": 120,
                "boxes": boxes, "all_targets_reviewed": True,
                "privacy_and_consent_reviewed": True,
            })
        test = self.capture["samples"][2:]
        self.first = {
            "schema_version": 1, "source": REVIEW_SOURCE, "role": "first",
            "review_session_id": ident("g", 901),
            "blind_to_model_predictions_declared": True,
            "manual_independent_review_declared": True,
            "samples": [self.annotation(s) for s in test],
        }
        self.second = deepcopy(self.first)
        self.second["role"] = "second"
        self.second["review_session_id"] = ident("g", 902)
        self.write()

    def annotation(self, sample):
        return {
            "sample_id": sample["sample_id"],
            "image_sha256": sample["image_sha256"],
            "boxes": deepcopy(sample["boxes"]),
            "all_targets_reviewed": True, "uncertain": False,
        }

    def write(self):
        self.manifest.write_text(json.dumps(self.capture), encoding="utf-8")
        self.review_first_path.write_text(json.dumps(self.first), encoding="utf-8")
        self.review_second_path.write_text(json.dumps(self.second), encoding="utf-8")

    def audit(self):
        self.write()
        return review_blind_test_annotations(
            self.manifest, first_review_path=self.review_first_path,
            second_review_path=self.review_second_path,
        )

    def test_matching_blind_declarations_is_not_independent_truth(self):
        result = self.audit()
        self.assertEqual("declared_blind_review_disagreement_audit_only", result["status"])
        self.assertEqual(2, result["test_images"])
        self.assertEqual(2, result["agreed_images"])
        self.assertEqual(1, result["agreed_negative_images"])
        self.assertEqual(1, result["matched_boxes_iou50_class_and_visibility"])
        self.assertEqual(0, result["disagreement_images"])
        self.assertEqual(0, result["uncertain_images"])
        self.assertEqual(0, result["primary_manifest_disagreements_with_first"])
        self.assertFalse(result["reviewer_independence_authenticated"])
        self.assertFalse(result["blindness_to_predictions_authenticated"])
        self.assertFalse(result["ground_truth_adjudicated"])
        self.assertFalse(result["benchmark_authorized_by_this_review"])
        self.assertFalse(result["c3_generalization_validated"])
        self.assertEqual(0, result["independent_scenes_verified"])
        self.assertEqual(0, result["motor_commands"])
        self.assertEqual(0, result["qwen_calls"])
        self.assertEqual(0, result["sqlite_writes"])
        self.assertNotIn("sample_id", result)
        self.assertNotIn("image_sha256", result)
        self.assertNotIn(ident("s", 3), json.dumps(result))

    def test_category_disagreement_not_automatically_adjudicated(self):
        self.second["samples"][0]["boxes"][0]["category"] = "dog"
        report = self.audit()
        self.assertEqual(1, report["agreed_images"])
        self.assertEqual(1, report["disagreement_images"])
        self.assertEqual(1, report["primary_manifest_disagreements_with_second"])
        self.assertFalse(report["ground_truth_adjudicated"])

    def test_visibility_disagreement_is_reported(self):
        self.second["samples"][0]["boxes"][0]["visibility"] = "full"
        report = self.audit()
        self.assertEqual(1, report["disagreement_images"])

    def test_iou_below_threshold_is_disagreement(self):
        self.second["samples"][0]["boxes"][0]["xyxy"] = [48, 60, 75, 100]
        report = self.audit()
        self.assertEqual(0, report["matched_boxes_iou50_class_and_visibility"])
        self.assertEqual(1, report["disagreement_images"])

    def test_box_order_permutation_does_not_create_disagreement(self):
        one = {"category": "chair", "xyxy": [10,20,35,55], "visibility": "partial"}
        two = {"category": "chair", "xyxy": [50,60,75,90], "visibility": "partial"}
        self.first["samples"][0]["boxes"] = [one, two]
        self.second["samples"][0]["boxes"] = [two, one]
        report = self.audit()
        self.assertEqual(2, report["agreed_images"])
        self.assertEqual(2, report["matched_boxes_iou50_class_and_visibility"])
        self.assertEqual(1, report["primary_manifest_disagreements_with_first"])

    def test_matching_uses_augmenting_path_not_greedy_order(self):
        def item(coords):
            return (Box("chair", tuple(float(x) for x in coords)), "partial")
        first = (item([10,20,35,55]), item([20,20,45,55]))
        # second box matches first item alone; first second-box
        # matches both, so naive greedy first-match may lose a pairing.
        second = (item([15,20,40,55]), item([10,20,35,55]))
        self.assertEqual(2, _matched_boxes(first, second))

    def test_uncertainty_blocks_consensus_without_hiding_boxes(self):
        self.second["samples"][0]["uncertain"] = True
        report = self.audit()
        self.assertEqual(1, report["agreed_images"])
        self.assertEqual(1, report["uncertain_images"])
        self.assertEqual(0, report["disagreement_images"])

    def test_reviewers_must_declare_distinct_sessions(self):
        self.second["review_session_id"] = self.first["review_session_id"]
        with self.assertRaisesRegex(PhotoBaselineError, "distinct"):
            self.audit()

    def test_blind_and_manual_declarations_must_be_explicit(self):
        for field in ("blind_to_model_predictions_declared",
                      "manual_independent_review_declared"):
            with self.subTest(field=field):
                self.first[field] = False
                with self.assertRaises(PhotoBaselineError):
                    self.audit()
                self.first[field] = True

    def test_unknown_fields_personal_names_and_free_text_are_refused(self):
        self.second["person_name"] = "private"
        with self.assertRaises(PhotoBaselineError):
            self.audit()
        del self.second["person_name"]
        self.second["samples"][0]["free_text"] = "untrusted"
        with self.assertRaises(PhotoBaselineError):
            self.audit()

    def test_review_only_accepts_the_exact_test_partition(self):
        self.second["samples"].append(self.annotation(self.capture["samples"][0]))
        with self.assertRaisesRegex(PhotoBaselineError, "incomplete"):
            self.audit()
        self.second["samples"].pop()
        self.second["samples"][1]["sample_id"] = self.second["samples"][0]["sample_id"]
        with self.assertRaises(PhotoBaselineError):
            self.audit()

    def test_review_must_bind_exact_image_sha_without_logging_it(self):
        self.second["samples"][0]["image_sha256"] = "f" * 64
        with self.assertRaisesRegex(PhotoBaselineError, "mismatched"):
            self.audit()

    def test_corrupt_geometry_unknown_label_and_nonfinite_are_refused(self):
        row = self.second["samples"][0]["boxes"][0]
        for cat, coord in (("shoe", [10,20,35,55]),
                           ("chair", [10,20,81,55]),
                           ("chair", [10,20,10,55])):
            with self.subTest(cat=cat, coord=coord):
                row["category"], row["xyxy"] = cat, coord
                with self.assertRaises(PhotoBaselineError):
                    self.audit()
        row["category"], row["xyxy"] = "chair", [10,20,35,float("nan")]
        with self.assertRaises(PhotoBaselineError):
            self.audit()

    def test_refuse_duplicate_json_keys(self):
        self.write()
        self.review_second_path.write_text(
            json.dumps(self.second).replace('"role": "second"',
                                            '"role": "second", "role": "second"'),
            encoding="utf-8",
        )
        with self.assertRaises(PhotoBaselineError):
            review_blind_test_annotations(
                self.manifest, first_review_path=self.review_first_path,
                second_review_path=self.review_second_path,
            )

    def test_refuse_review_path_outside_private_root_and_symlink(self):
        outside = self.root / "outside.json"
        outside.write_text(json.dumps(self.second), encoding="utf-8")
        self.write()
        with self.assertRaises(PhotoBaselineError):
            review_blind_test_annotations(
                self.manifest, first_review_path=self.review_first_path,
                second_review_path=outside,
            )
        self.review_second_path.unlink()
        self.review_second_path.symlink_to(outside)
        with self.assertRaises(PhotoBaselineError):
            review_blind_test_annotations(
                self.manifest, first_review_path=self.review_first_path,
                second_review_path=self.review_second_path,
            )

    def test_no_duplicate_review_file(self):
        self.write()
        with self.assertRaises(PhotoBaselineError):
            review_blind_test_annotations(
                self.manifest, first_review_path=self.review_first_path,
                second_review_path=self.review_first_path,
            )

    def test_manifest_split_leakage_rejected_before_review(self):
        self.capture["sessions"][2]["site_group_id"] = (
            self.capture["sessions"][0]["site_group_id"])
        with self.assertRaisesRegex(PhotoBaselineError, "leakage"):
            self.audit()

    def test_cli_consent_is_mandatory_and_report_is_aggregated(self):
        self.write()
        with patch("sys.stderr"):
            with self.assertRaises(SystemExit) as ex:
                main(["--manifest", str(self.manifest),
                      "--review-first", str(self.review_first_path),
                      "--review-second", str(self.review_second_path)])
            self.assertEqual(2, ex.exception.code)
        with patch("builtins.print") as printer:
            self.assertEqual(0, main([
                "--manifest", str(self.manifest),
                "--review-first", str(self.review_first_path),
                "--review-second", str(self.review_second_path),
                "--approved-private-local-media",
            ]))
        printed = printer.call_args.args[0]
        self.assertEqual(2, json.loads(printed)["agreed_images"])
        self.assertNotIn(str(self.root), printed)
        self.assertNotIn(self.capture["samples"][2]["image_sha256"], printed)
        self.assertNotIn(ident("s", 3), printed)

    def test_no_network_sqlite_ollama_or_robot_access(self):
        self.write()
        with patch("sqlite3.connect", side_effect=AssertionError("no SQLite")), \
             patch("socket.socket", side_effect=AssertionError("no network")):
            result = review_blind_test_annotations(
                self.manifest, first_review_path=self.review_first_path,
                second_review_path=self.review_second_path,
            )
        self.assertEqual(0, result["motor_commands"])
        self.assertEqual(0, result["sqlite_writes"])
        self.assertEqual(0, result["model_inference_calls"])


if __name__ == "__main__":
    unittest.main()
