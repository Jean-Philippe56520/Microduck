"""F3-A: no-media manifest contract and strictly synthetic evaluation tests."""
from __future__ import annotations

from dataclasses import asdict
import json
import math
import unittest

from microduck_companion.visual_dataset import (
    CATEGORIES, DETECTION_CONFIDENCE, MAX_JSON_BYTES,
    PREDICTION_ORIGIN, TASK,
    VisualProtocolError, evaluate_mock_predictions, parse_visual_manifest,
)
from microduck_companion.visual_dataset_demo import fixture_json, run_demo


class VisualDatasetTests(unittest.TestCase):
    def setUp(self):
        self.manifest_json, self.prediction_json = fixture_json()
        self.manifest = json.loads(self.manifest_json)
        self.predictions = json.loads(self.prediction_json)

    def parsed(self):
        return parse_visual_manifest(
            json.dumps(self.manifest, allow_nan=False))

    def scored(self):
        return evaluate_mock_predictions(
            self.parsed(), json.dumps(self.predictions, allow_nan=False))

    def test_synthetic_fixture_has_three_group_isolated_splits(self):
        dataset = self.parsed()
        self.assertTrue(dataset.synthetic_only)
        self.assertEqual(28, len(dataset.samples))
        self.assertEqual((8, 8, 12), tuple(
            len(dataset.partition(split))
            for split in ("train", "validation", "test")))
        self.assertEqual(28, len({s.group_id for s in dataset.samples}))
        self.assertEqual(28, len({s.fingerprint_sha256 for s in dataset.samples}))
        self.assertEqual(28, len({s.sample_id for s in dataset.samples}))

    def test_all_categories_align_with_existing_perception_contract(self):
        self.assertEqual(
            {"unknown", "ball", "toy", "dog", "cat", "person",
             "microduck", "other_object"}, set(CATEGORIES))
        self.assertNotIn("private-child-example", CATEGORIES)
        self.assertNotIn("private-dog-example", CATEGORIES)
        self.assertNotIn("private-cat-example", CATEGORIES)
        self.assertNotIn("keyword_stop", CATEGORIES)

    def test_mock_evaluation_reports_correct_mislabels_and_abstentions(self):
        result = self.scored()
        self.assertEqual(12, result.test_samples)
        self.assertEqual(9, result.correct)
        self.assertAlmostEqual(.75, result.accuracy)
        self.assertEqual(10, result.known_support)
        self.assertEqual(2, result.unknown_support)
        self.assertEqual(3, result.predicted_unknown)
        self.assertEqual(2, result.low_confidence_abstentions)
        self.assertEqual(.75, result.coverage)
        self.assertAlmostEqual(7/9, result.selective_accuracy)
        self.assertEqual(1., result.unknown_recall)
        self.assertGreater(result.macro_f1_known, 0.)
        self.assertLess(result.macro_f1_known, 1.)
        self.assertTrue(result.is_synthetic_only)
        self.assertEqual(PREDICTION_ORIGIN, result.prediction_source)
        self.assertEqual(0, result.executed_actions)
        self.assertEqual(0, result.motor_commands_issued)

    def test_per_category_metrics_are_defined_by_test_not_train(self):
        result = self.scored()
        labels = {score.category: score for score in result.per_category}
        self.assertEqual(7, len(labels))
        dog = labels["dog"]
        self.assertEqual((2, 3, 2),
                         (dog.support, dog.predicted, dog.true_positive))
        self.assertAlmostEqual(2/3, dog.precision)
        self.assertAlmostEqual(1., dog.recall)
        self.assertAlmostEqual(.8, dog.f1)
        self.assertEqual(0, labels["person"].true_positive)
        self.assertEqual(0., labels["person"].recall)
        self.assertNotIn("unknown", labels)
        confusion = dict(((t, p), n) for t, p, n in result.confusion)
        self.assertEqual(2, confusion[("dog", "dog")])
        self.assertEqual(1, confusion[("cat", "dog")])
        self.assertEqual(1, confusion[("person", "unknown")])
        self.assertEqual(2, confusion[("unknown", "unknown")])
        self.assertEqual(12, sum(confusion.values()))

    def test_confidence_threshold_matches_f1_policy_but_is_not_calibrated(self):
        self.assertEqual(.8, DETECTION_CONFIDENCE)
        # Low-confidence "person" is counted as unknown, not true positive.
        self.assertIn(("person", "unknown", 1), self.scored().confusion)

    def test_zero_coverage_is_not_division_by_zero(self):
        for row in self.predictions["predictions"]:
            row["category"] = "unknown"
            row["confidence"] = 0.
        report = self.scored()
        self.assertEqual(0., report.coverage)
        self.assertIsNone(report.selective_accuracy)
        self.assertEqual(2, report.correct)
        self.assertEqual(0., report.macro_f1_known)
        self.assertEqual(1., report.unknown_recall)

    def test_demo_is_reproducible_and_explicitly_fictional(self):
        a, b = fixture_json()
        self.assertEqual((a, b), fixture_json())
        result = run_demo()
        self.assertEqual("synthetic_metadata_only", result["scope"])
        self.assertEqual(0, result["opened_images"])
        self.assertEqual(0, result["motor_commands_issued"])
        self.assertFalse(result["physical_camera_validated"])
        self.assertEqual({"train": 8, "validation": 8, "test": 12},
                         result["split_counts"])
        self.assertIn("not_model_accuracy", result["evaluation_kind"])

    def test_metadata_has_no_image_paths_person_names_or_raw_media(self):
        for sample in self.manifest["samples"]:
            self.assertEqual({
                "sample_id", "group_id", "fingerprint_sha256",
                "split", "category", "source_kind", "rights_basis",
                "annotation_basis"}, set(sample))
        self.assertNotIn("private-child-example", self.manifest_json)
        self.assertNotIn("private-cat-example", self.manifest_json)
        self.assertNotIn("private-dog-example", self.manifest_json)
        self.assertNotIn("filename", self.manifest_json)
        self.assertNotIn("image_path", self.manifest_json)

    def test_duplicate_sample_id_rejected(self):
        self.manifest["samples"][16]["sample_id"] = self.manifest["samples"][0]["sample_id"]
        with self.assertRaisesRegex(VisualProtocolError, "duplicate"):
            self.parsed()

    def test_identical_digest_across_splits_rejected(self):
        self.manifest["samples"][16]["fingerprint_sha256"] = (
            self.manifest["samples"][0]["fingerprint_sha256"])
        with self.assertRaisesRegex(VisualProtocolError, "duplicate"):
            self.parsed()

    def test_capture_group_cross_split_leakage_rejected(self):
        self.manifest["samples"][16]["group_id"] = (
            self.manifest["samples"][0]["group_id"])
        with self.assertRaisesRegex(VisualProtocolError, "leaks"):
            self.parsed()

    def test_group_reuse_within_same_split_is_allowed(self):
        self.manifest["samples"][1]["group_id"] = (
            self.manifest["samples"][0]["group_id"])
        self.assertEqual(28, len(self.parsed().samples))

    def test_unexpected_personal_field_and_media_path_are_forbidden(self):
        for key, value in (
            ("image_path", "/private/child.jpg"),
            ("person_name", "private-child"),
            ("bbox", [0., 0., .5, .5]),
            ("uri", "https://example.invalid/personal.jpg"),
        ):
            with self.subTest(key=key):
                sample = self.manifest["samples"][0]
                sample[key] = value
                with self.assertRaises(VisualProtocolError):
                    self.parsed()
                del sample[key]

    def test_non_opaque_identifiers_are_forbidden(self):
        for field, bad in (
            ("sample_id", "dog-private-child-example"),
            ("sample_id", "s-short"),
            ("group_id", "g-private-cat-example"),
            ("fingerprint_sha256", "NOT_A_DIGEST"),
            ("fingerprint_sha256", "a"*63),
        ):
            with self.subTest(field=field, bad=bad):
                self.manifest["samples"][0][field] = bad
                with self.assertRaises(VisualProtocolError):
                    self.parsed()
                self.manifest["samples"] = json.loads(self.manifest_json)["samples"]

    def test_personal_identity_or_audio_not_ground_truth_categories(self):
        for category in ("private-dog-example", "private-cat-example", "private-child-example",
                         "bark", "keyword_stop", "llm_guess", ""):
            with self.subTest(category=category):
                self.manifest["samples"][0]["category"] = category
                with self.assertRaises(VisualProtocolError):
                    self.parsed()
                self.manifest["samples"] = json.loads(self.manifest_json)["samples"]

    def test_unknown_is_valid_holdout_ground_truth(self):
        self.assertEqual(2, sum(s.category == "unknown"
                                 for s in self.parsed().partition("test")))

    def test_test_split_must_include_unknown_and_known(self):
        for all_unknown in (True, False):
            self.manifest = json.loads(self.manifest_json)
            for row in self.manifest["samples"]:
                if row["split"] == "test":
                    row["category"] = ("unknown" if all_unknown else "dog")
            with self.subTest(all_unknown=all_unknown), self.assertRaises(
                    VisualProtocolError):
                self.parsed()

    def test_empty_required_split_rejected(self):
        for split in ("train", "validation", "test"):
            self.manifest = json.loads(self.manifest_json)
            for row in self.manifest["samples"]:
                if row["split"] == split:
                    row["split"] = "train" if split != "train" else "validation"
            with self.subTest(split=split), self.assertRaises(VisualProtocolError):
                self.parsed()

    def test_invalid_annotation_rights_are_rejected(self):
        for field, value in (
            ("source_kind", "robot"),
            ("rights_basis", "unknown"),
            ("rights_basis", "consent_recorded_locally"),
            ("annotation_basis", "model_suggestion"),
        ):
            self.manifest = json.loads(self.manifest_json)
            self.manifest["samples"][0][field] = value
            with self.subTest(field=field), self.assertRaises(VisualProtocolError):
                self.parsed()

    def test_external_sources_require_opt_in_and_are_not_certified(self):
        for origin, rights in (
            ("licensed_external", "license_reviewed_locally"),
            ("consented_private", "consent_recorded_locally"),
        ):
            self.manifest = json.loads(self.manifest_json)
            row = self.manifest["samples"][0]
            row["source_kind"] = origin
            row["rights_basis"] = rights
            row["annotation_basis"] = "human_reviewed"
            payload = json.dumps(self.manifest)
            with self.subTest(origin=origin):
                with self.assertRaises(VisualProtocolError):
                    parse_visual_manifest(payload)
                parsed = parse_visual_manifest(payload, allow_external=True)
                self.assertFalse(parsed.synthetic_only)
                with self.assertRaises(VisualProtocolError):
                    evaluate_mock_predictions(parsed, self.prediction_json)

    def test_external_rights_claim_does_not_override_fixture_restrictions(self):
        self.manifest["samples"][0]["source_kind"] = "consented_private"
        self.manifest["samples"][0]["rights_basis"] = "generated_fixture"
        self.manifest["samples"][0]["annotation_basis"] = "human_reviewed"
        with self.assertRaises(VisualProtocolError):
            parse_visual_manifest(json.dumps(self.manifest), allow_external=True)

    def test_invalid_manifest_schema_and_task_rejected(self):
        for key, value in (
            ("schema_version", True),
            ("schema_version", 2),
            ("task", "face_recognition"),
            ("task", ["single_label_visual_category"]),
        ):
            self.manifest = json.loads(self.manifest_json)
            self.manifest[key] = value
            with self.subTest(key=key), self.assertRaises(VisualProtocolError):
                self.parsed()

    def test_json_key_duplication_nan_and_non_object_rejected(self):
        for payload in (
            '{"schema_version":1,"schema_version":1,"task":"x","samples":[]}',
            '{"schema_version":NaN,"task":"x","samples":[]}',
            '["unexpected"]',
            "this is not JSON",
        ):
            with self.subTest(payload=payload), self.assertRaises(
                    VisualProtocolError):
                parse_visual_manifest(payload)

    def test_invalid_encoding_type_and_oversize_rejected(self):
        with self.assertRaises(VisualProtocolError):
            parse_visual_manifest(b"\xff")
        with self.assertRaises(TypeError):
            parse_visual_manifest({"samples": []})
        with self.assertRaises(VisualProtocolError):
            parse_visual_manifest(" "* (MAX_JSON_BYTES + 1))
        with self.assertRaises(TypeError):
            parse_visual_manifest(self.manifest_json, allow_external="yes")
        self.assertEqual(28, len(parse_visual_manifest(
            self.manifest_json.encode("utf-8")).samples))

    def test_prediction_unknown_provenance_rejected(self):
        for source in ("sensor", "real_model", "qwen", "mujoco", ""):
            self.predictions["source"] = source
            with self.subTest(source=source), self.assertRaises(
                    VisualProtocolError):
                self.scored()

    def test_prediction_missing_or_extra_test_id_rejected(self):
        self.predictions["predictions"].pop()
        with self.assertRaises(VisualProtocolError):
            self.scored()
        self.predictions = json.loads(self.prediction_json)
        self.predictions["predictions"][0]["sample_id"] = (
            self.manifest["samples"][0]["sample_id"])
        with self.assertRaises(VisualProtocolError):
            self.scored()

    def test_duplicate_test_prediction_rejected(self):
        self.predictions["predictions"][1]["sample_id"] = (
            self.predictions["predictions"][0]["sample_id"])
        with self.assertRaises(VisualProtocolError):
            self.scored()

    def test_unrecognized_predicted_label_rejected(self):
        for category in ("private-child-example", "dog+cat", "keyword_stop", ""):
            self.predictions = json.loads(self.prediction_json)
            self.predictions["predictions"][0]["category"] = category
            with self.subTest(category=category), self.assertRaises(
                    VisualProtocolError):
                self.scored()

    def test_prediction_confidence_validation(self):
        for value in (True, -1., 1.1, float("nan"),
                      float("inf"), "0.9", None):
            self.predictions = json.loads(self.prediction_json)
            self.predictions["predictions"][0]["confidence"] = value
            raw = json.dumps(self.predictions)
            with self.subTest(value=value), self.assertRaises(
                    VisualProtocolError):
                evaluate_mock_predictions(self.parsed(), raw)

    def test_prediction_media_fields_or_duplicate_json_keys_rejected(self):
        self.predictions["predictions"][0]["frame_bytes"] = "fake"
        with self.assertRaises(VisualProtocolError):
            self.scored()
        with self.assertRaises(VisualProtocolError):
            evaluate_mock_predictions(
                self.parsed(),
                '{"schema_version":1,"source":"mock_prediction",'
                '"source":"sensor","predictions":[]}',
            )

    def test_non_test_labels_do_not_enter_test_metrics(self):
        old = self.scored()
        self.manifest["samples"][0]["category"] = "cat"
        self.manifest["samples"][8]["category"] = "toy"
        changed = self.scored()
        self.assertEqual(asdict(old), asdict(changed))

    def test_invalid_partition_and_dataset_types_are_rejected(self):
        with self.assertRaises(ValueError):
            self.parsed().partition("not_a_split")
        with self.assertRaises(TypeError):
            evaluate_mock_predictions("not dataset", self.prediction_json)


if __name__ == "__main__":
    unittest.main()
