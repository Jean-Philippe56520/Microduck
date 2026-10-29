"""QW-QUAL-1A: offline synthetic images and fake adviser; NEVER real Qwen."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import unittest
from unittest.mock import patch

from microduck_companion.qwen9b_action_guard import screen_preview_text
from microduck_companion.qwen9b_production_role_v2 import ROLE_VERSION
from microduck_companion.qwen9b_semantic_quality import (
    CASE_IDS, MAX_SOURCE_BYTES, independent_reference,
    main, make_synthetic_png, run_case,
)


def fake_response(prose="Observer sans contact ; pas de geste autorise."):
    return {
        "status": "unverified",
        "advisor_text": prose,
        "advice_guard": screen_preview_text(prose),
        "elapsed_s": 11.5,
        "generated_tokens": 91,
    }


class SyntheticScenesTests(unittest.TestCase):
    def test_four_distinct_original_in_memory_drawings(self):
        from PIL import Image
        self.assertEqual(4, len(CASE_IDS))
        blobs = [make_synthetic_png(case) for case in CASE_IDS]
        self.assertEqual(4, len({hashlib.sha256(b).digest() for b in blobs}))
        for blob in blobs:
            self.assertTrue(blob.startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertLessEqual(len(blob), MAX_SOURCE_BYTES)
            image = Image.open(io.BytesIO(blob))
            self.assertEqual((320, 240), image.size)
            self.assertEqual("RGB", image.mode)
            self.assertFalse(image.info.get("exif"))

    def test_references_stay_out_of_the_model_request(self):
        # The human reference describes the intentionally stylized drawing.
        # A test cannot claim real-world vision or semantic correctness.
        self.assertIn("KICK", independent_reference("scene_b")["drawing"].upper() +
                      independent_reference("scene_b")["review_focus"].upper())
        notes = independent_reference("scene_b")
        notes["drawing"] = "tampered"
        self.assertNotEqual("tampered", independent_reference("scene_b")["drawing"])
        self.assertEqual(ROLE_VERSION, "kwipi-qwen9b-role-v2-candidate")

    def test_unknown_case_and_bad_types_fail_before_render(self):
        for case in ("", "scene_x", "cat", None, 1, True):
            with self.subTest(case=case), self.assertRaises(ValueError):
                make_synthetic_png(case)
            with self.subTest(reference=case), self.assertRaises(ValueError):
                independent_reference(case)


class PCOnlyOneShotTests(unittest.TestCase):
    def test_dry_run_is_zero_network_zero_render(self):
        stream = io.StringIO()
        with patch(
            "microduck_companion.qwen9b_semantic_quality.make_synthetic_png",
            side_effect=AssertionError("dry run must not load PIL"),
        ), patch(
            "microduck_companion.qwen9b_semantic_quality.evaluate_local_image",
            side_effect=AssertionError("dry run must not call Ollama"),
        ), redirect_stdout(stream):
            self.assertEqual(0, main([]))
        r = json.loads(stream.getvalue())
        self.assertEqual("dry_run_no_network", r["mode"])
        self.assertEqual(0, r["calls"])
        self.assertEqual(list(CASE_IDS), r["cases"])
        self.assertNotIn("advisor_text", r)

    def test_consent_and_cli_gating_before_model_or_image(self):
        with patch(
            "microduck_companion.qwen9b_semantic_quality.make_synthetic_png",
            side_effect=AssertionError("must not render before consent"),
        ):
            with self.assertRaises(ValueError):
                run_case(case_id="scene_a", consent=False)
            for opts in ({"port": 0}, {"port": 65536},
                         {"port": True}, {"timeout_s": float("nan")},
                         {"timeout_s": 181}, {"display_advice": 1}):
                with self.subTest(opts=opts), self.assertRaises(ValueError):
                    run_case(case_id="scene_a", consent=True, **opts)
        with redirect_stderr(io.StringIO()):
            for args in (
                ["--run"],
                ["--run", "--case", "scene_a"],
                ["--run", "--authorize-one-synthetic-call"],
                ["--display-advice"],
                ["--authorize-one-synthetic-call"],
                ["--run", "--case", "scene_a",
                 "--authorize-one-synthetic-call", "--show-independent-reference"],
            ):
                with self.subTest(args=args), self.assertRaises(SystemExit):
                    main(args)

    def test_one_call_reuses_existing_role_and_guard(self):
        prose = "Observation : une forme ronde. Possibilites : observer ; incertitude."
        with patch(
            "microduck_companion.qwen9b_semantic_quality.evaluate_local_image",
            return_value=fake_response(prose),
        ) as evaluated:
            report = run_case(
                case_id="scene_a", consent=True, port=11434, timeout_s=110,
                display_advice=True,
            )
        evaluated.assert_called_once()
        args, kwargs = evaluated.call_args
        self.assertTrue(args[0].startswith(b"\x89PNG"))
        self.assertEqual(ROLE_VERSION, kwargs["role_version"])
        self.assertTrue(kwargs["consent"])
        self.assertTrue(kwargs["reviewed"])
        self.assertEqual(11434, kwargs["port"])
        self.assertEqual(110, kwargs["timeout_s"])
        self.assertEqual(("127.0.0.1", 11434), kwargs["endpoint"].host_port)
        self.assertEqual(prose, report["advisor_text_for_human_only"])
        self.assertEqual("independent_human_review_required", report["review_state"])
        self.assertIsNone(report["quality_score"])
        self.assertEqual("blocked", report["machine_use"])
        self.assertIs(False, report["physical_actions_authorized"])
        self.assertEqual(0, report["motor_commands_issued"])
        self.assertEqual(0, report["memory_writes"])
        self.assertEqual(0, report["private_images_read"])
        self.assertFalse(report["robot_validated"])
        self.assertEqual(91, report["generated_tokens"])

    def test_default_hides_prose_and_no_quality_claims(self):
        prose = "Observation : un chat ; ground_pick pour pointer vers le chat."
        with patch(
            "microduck_companion.qwen9b_semantic_quality.evaluate_local_image",
            return_value=fake_response(prose),
        ):
            report = run_case(case_id="scene_b", consent=True)
        self.assertNotIn("advisor_text_for_human_only", report)
        self.assertNotIn(prose, json.dumps(report))
        self.assertIn("possible_living_motor_risk", report["review_flags"])
        self.assertEqual("blocked", report["machine_use"])
        self.assertIsNone(report["quality_score"])
        self.assertFalse(report["physical_actions_authorized"])

    def test_bad_guard_and_unknown_envelope_are_rejected_without_logging(self):
        variants = [
            {"status": "unverified", "advisor_text": "safe",
             "advice_guard": {"machine_use": "allowed",
                              "physical_actions_authorized": True,
                              "review_flags": []}},
            {"status": "unverified", "advisor_text": "PRIVATE_USERNAME",
             "advice_guard": {"machine_use": "blocked",
                              "physical_actions_authorized": False,
                              "review_flags": ["unknown_flag"]}},
            {"status": "unverified", "advisor_text": "X" * 1201,
             "advice_guard": screen_preview_text("ok")},
            {"status": "succeeded", "advisor_text": "untrusted"},
            {"not_status": "anything"},
        ]
        for answer in variants:
            with self.subTest(answer=answer.get("status")), patch(
                "microduck_companion.qwen9b_semantic_quality.evaluate_local_image",
                return_value=answer,
            ):
                with self.assertRaises(ValueError):
                    run_case(case_id="scene_a", consent=True, display_advice=True)

    def test_rejected_or_unavailable_dont_leak_diagnostic_or_claim_review(self):
        for status in ("rejected", "unavailable"):
            with self.subTest(status=status), patch(
                "microduck_companion.qwen9b_semantic_quality.evaluate_local_image",
                return_value={"status": status,
                              "diagnostic": "PRIVATE_USERNAME",
                              "advisor_text": "PRIVATE_USERNAME"},
            ):
                report = run_case(case_id="scene_d", consent=True,
                                  display_advice=True)
            self.assertEqual(status, report["status"])
            self.assertNotIn("PRIVATE_USERNAME", json.dumps(report))
            self.assertNotIn("advisor_text_for_human_only", report)
            self.assertIsNone(report["quality_score"])
            self.assertEqual("blocked", report["machine_use"])

    def test_cli_one_case_with_explicit_text_display_is_only_opt_in(self):
        r = {"study": "QW-QUAL-1A-PC-synthetic-human-review",
             "case_id": "scene_c", "status": "unverified",
             "advisor_text_for_human_only": "hypothese non verifiee"}
        stream = io.StringIO()
        with patch(
            "microduck_companion.qwen9b_semantic_quality.run_case",
            return_value=r,
        ) as fn, redirect_stdout(stream):
            status = main(["--run", "--case", "scene_c",
                           "--authorize-one-synthetic-call",
                           "--display-advice", "--ollama-port", "11434"])
        self.assertEqual(0, status)
        fn.assert_called_once_with(
            case_id="scene_c", consent=True, port=11434,
            timeout_s=120.0, display_advice=True,
        )
        self.assertEqual("scene_c", json.loads(stream.getvalue())["case_id"])

    def test_independent_reference_is_only_separate_offline_command(self):
        stream = io.StringIO()
        with patch(
            "microduck_companion.qwen9b_semantic_quality.evaluate_local_image",
            side_effect=AssertionError("must be offline"),
        ), redirect_stdout(stream):
            self.assertEqual(0, main(["--case", "scene_c",
                                      "--show-independent-reference"]))
        report = json.loads(stream.getvalue())
        self.assertEqual("dry_run_no_network", report["mode"])
        self.assertIn("review_focus", report["independent_reference"])


if __name__ == "__main__":
    unittest.main()
