"""C3-A: adversarial paired mock ablation tests, NEVER a real memory benchmark."""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from microduck_companion.c3_mock_ablation import compare_mock_category_ablations
from microduck_companion.visual_dataset import VisualProtocolError
from microduck_companion.visual_dataset_demo import fixture_json


class C3MockAblationTests(unittest.TestCase):
    def setUp(self):
        manifest, baseline = fixture_json()
        self.manifest = json.loads(manifest)
        self.baseline = json.loads(baseline)
        self.recall = json.loads(baseline)

    @staticmethod
    def encoded(value):
        return json.dumps(value, allow_nan=False, sort_keys=True)

    def compare(self, *, pc=None):
        return compare_mock_category_ablations(
            self.encoded(self.manifest),
            self.encoded(self.baseline),
            self.encoded(self.recall),
            with_pc_json=None if pc is None else self.encoded(pc),
        )

    def test_reuses_f3a_scores_and_refuses_causal_credit(self):
        result = self.compare()
        self.assertEqual(12, result.without_memory.score.test_samples)
        self.assertEqual(9, result.without_memory.score.correct)
        self.assertEqual(0., result.sample_accuracy_delta_mock)
        self.assertEqual(0., result.group_balanced_accuracy_delta_mock)
        self.assertEqual(12, result.declared_test_groups)
        self.assertIsNone(result.with_pc)
        self.assertTrue(result.evaluated_synthetic_fixtures)
        self.assertFalse(result.ablation_execution_verified)
        self.assertEqual(0, result.independent_scenes_verified)
        self.assertFalse(result.real_sensors_verified)
        self.assertFalse(result.memory_benefit_verified)
        self.assertFalse(result.qwen_called)
        self.assertEqual(0, result.causal_effects_verified)
        self.assertFalse(result.physical_actions_authorized)
        self.assertEqual(0, result.memory_writes)
        self.assertEqual(0, result.motor_commands_issued)

    def test_correcting_three_mock_labels_is_not_evidence_of_memory_gain(self):
        for idx, category in ((1, "cat"), (2, "person"), (11, "ball")):
            row = self.recall["predictions"][idx]
            row["category"], row["confidence"] = category, .96
        result = self.compare()
        self.assertEqual(12, result.with_memory.score.correct)
        self.assertAlmostEqual(.25, result.sample_accuracy_delta_mock)
        self.assertAlmostEqual(.25, result.group_balanced_accuracy_delta_mock)
        self.assertFalse(result.memory_benefit_verified)
        self.assertFalse(result.ablation_execution_verified)

    def test_optional_third_lane_is_only_mock_not_real_qwen(self):
        pc = json.loads(self.encoded(self.recall))
        result = self.compare(pc=pc)
        self.assertIsNotNone(result.with_pc)
        self.assertEqual(9, result.with_pc.score.correct)
        self.assertFalse(result.qwen_called)
        self.assertFalse(result.memory_benefit_verified)

    def test_group_weighting_prevents_repeated_views_dominating(self):
        # Two TEST samples share a declared capture group: one correct,
        # one wrong. F3-A allows this *within* a split, not across splits.
        test = [s for s in self.manifest["samples"] if s["split"] == "test"]
        test[1]["group_id"] = test[0]["group_id"]
        result = self.compare()
        self.assertEqual(11, result.declared_test_groups)
        self.assertNotAlmostEqual(
            result.without_memory.declared_group_balanced_accuracy,
            result.without_memory.score.accuracy,
        )
        self.assertFalse(result.independent_scenes_verified)

    def test_unknown_false_acceptance_is_visible_even_if_score_improves(self):
        # Deliberately hallucinate a known animal on an unknown fixture.
        self.recall["predictions"][7]["category"] = "dog"
        self.recall["predictions"][7]["confidence"] = .99
        result = self.compare()
        self.assertEqual(1, result.with_memory.unknown_false_accepts)
        self.assertEqual(0, result.without_memory.unknown_false_accepts)
        self.assertLess(result.sample_accuracy_delta_mock, 0)
        self.assertFalse(result.physical_actions_authorized)

    def test_low_confidence_known_class_is_abstention(self):
        self.recall["predictions"][0]["confidence"] = .01
        result = self.compare()
        self.assertEqual(
            result.without_memory.score.correct - 1,
            result.with_memory.score.correct,
        )
        self.assertGreater(
            result.with_memory.score.low_confidence_abstentions,
            result.without_memory.score.low_confidence_abstentions,
        )

    def test_f3a_refuses_group_leakage_across_train_and_test(self):
        test = next(s for s in self.manifest["samples"] if s["split"] == "test")
        train = next(s for s in self.manifest["samples"] if s["split"] == "train")
        test["group_id"] = train["group_id"]
        with self.assertRaisesRegex(VisualProtocolError, "leaks"):
            self.compare()

    def test_f3a_refuses_same_content_digest_across_splits(self):
        test = next(s for s in self.manifest["samples"] if s["split"] == "test")
        train = next(s for s in self.manifest["samples"] if s["split"] == "train")
        test["fingerprint_sha256"] = train["fingerprint_sha256"]
        with self.assertRaisesRegex(VisualProtocolError, "duplicate"):
            self.compare()

    def test_f3a_refuses_external_sources_even_with_rights_claim(self):
        sample = self.manifest["samples"][0]
        sample["source_kind"] = "consented_private"
        sample["rights_basis"] = "consent_recorded_locally"
        sample["annotation_basis"] = "human_reviewed"
        with self.assertRaisesRegex(VisualProtocolError, "forbidden"):
            self.compare()

    def test_f3a_refuses_missing_or_duplicate_predictions_per_lane(self):
        self.recall["predictions"].pop()
        with self.assertRaisesRegex(VisualProtocolError, "cover"):
            self.compare()
        self.recall["predictions"].append(self.recall["predictions"][0].copy())
        with self.assertRaisesRegex(VisualProtocolError, "duplicate"):
            self.compare()

    def test_f3a_refuses_non_mock_pc_payload_and_extra_model_text(self):
        pc = json.loads(self.encoded(self.baseline))
        pc["source"] = "qwen_real"
        with self.assertRaises(VisualProtocolError):
            self.compare(pc=pc)
        pc["source"] = "mock_prediction"
        pc["free_text"] = "a suggestion is not ground truth"
        with self.assertRaises(VisualProtocolError):
            self.compare(pc=pc)

    def test_f3a_rejects_unknown_missing_from_test(self):
        for sample in self.manifest["samples"]:
            if sample["split"] == "test" and sample["category"] == "unknown":
                sample["category"] = "ball"
        with self.assertRaisesRegex(VisualProtocolError, "unknown ground truth"):
            self.compare()

    def test_f3a_rejects_oversize_and_nonfinite_predictions(self):
        self.recall["predictions"][0]["confidence"] = 10
        with self.assertRaises(VisualProtocolError):
            self.compare()
        self.recall["predictions"][0]["confidence"] = float("nan")
        with self.assertRaises(ValueError):
            self.compare()

    def test_no_camera_model_ollama_sqlite_or_motor_calls(self):
        # Inputs are ONLY declared F3-A metadata; the evaluator cannot
        # execute C1, open SQLite or connect to a robot or an Ollama server.
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), \
             patch("sqlite3.connect", side_effect=AssertionError("SQLite forbidden")):
            result = self.compare()
        self.assertEqual(0, result.motor_commands_issued)
        self.assertEqual(0, result.memory_writes)


if __name__ == "__main__":
    unittest.main()
