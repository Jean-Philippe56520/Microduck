"""QW-QUAL-2A-P2: the clipboard is always a mocked, synthetic local string."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.qwen9b_blind_review_packet import (
    STUDY, capture_clipboard_case, collect_reports, main,
)
from microduck_companion.qwen9b_role_preview import MODEL, ROLE_VERSION_V2
from microduck_companion.qwen9b_semantic_quality import CASE_IDS


def fake_json(case: str) -> str:
    report = {
        "study": STUDY,
        "mode": "one_real_pc_request",
        "case_id": case,
        "model": MODEL,
        "role_version": ROLE_VERSION_V2,
        "status": "unverified",
        "review_state": "independent_human_review_required",
        "quality_score": None,
        "advisor_text_for_human_only": "Fake original response - " + case,
        "machine_use": "blocked",
        "physical_actions_authorized": False,
        "motor_commands_issued": 0,
        "memory_writes": 0,
        "private_images_read": 0,
        "robot_validated": False,
        "model_text_saved_by_probe": False,
        "synthetic_image_saved_by_probe": False,
    }
    return json.dumps(report, ensure_ascii=False)


class ClipboardCaptureTests(unittest.TestCase):
    def test_four_separate_mock_clipboard_captures_preserve_text_and_preflight(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "private-originals"
            for case in CASE_IDS:
                content = fake_json(case)
                with patch("microduck_companion.qwen9b_blind_review_packet._read_clipboard_text",
                           return_value=content) as reader, patch(
                           "microduck_companion.qwen9b_blind_review_packet.make_synthetic_png",
                           side_effect=AssertionError("no rendered image during capture")):
                    with redirect_stdout(io.StringIO()) as output:
                        code = main(["--source-dir", str(source),
                            "--capture-clipboard-case", case,
                            "--authorize-private-source-write"])
                self.assertEqual(code, 0)
                reader.assert_called_once_with()
                result = json.loads(output.getvalue())
                self.assertEqual(result["case_id"], case)
                self.assertEqual(result["files_written"], 1)
                self.assertEqual(result["qwen_calls"], 0)
                self.assertEqual(result["source_authenticity"], "operator_asserted_not_verified")
                self.assertNotIn("Fake original", output.getvalue())
                self.assertEqual((source / (case + ".json")).read_text("utf-8"), content)
            self.assertEqual(len(collect_reports(source)), 4)
            self.assertEqual(sorted(p.name for p in source.iterdir()),
                             sorted(case + ".json" for case in CASE_IDS))

    def test_no_write_on_invalid_or_unrelated_clipboard_content(self):
        with tempfile.TemporaryDirectory() as temp:
            for i, data in enumerate([
                "not JSON at all",
                "```json\n" + fake_json("scene_a") + "\n```",
                fake_json("scene_b"),
                fake_json("scene_a") + " garbage",
                fake_json("scene_a").replace('"motor_commands_issued": 0',
                                                   '"motor_commands_issued": true'),
                "x" * 33000,
                "",
            ]):
                source = Path(temp) / ("case-" + str(i))
                with patch("microduck_companion.qwen9b_blind_review_packet._read_clipboard_text",
                           return_value=data):
                    with self.assertRaises(ValueError):
                        capture_clipboard_case(source, "scene_a")
                self.assertFalse(source.exists())

    def test_no_clipboard_read_if_case_exists_or_git_leak(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "originals"
            source.mkdir()
            (source / "scene_a.json").write_text(fake_json("scene_a"), encoding="utf-8")
            with patch("microduck_companion.qwen9b_blind_review_packet._read_clipboard_text",
                       side_effect=AssertionError("do not inspect clipboard")):
                with self.assertRaisesRegex(ValueError, "no overwrite"):
                    capture_clipboard_case(source, "scene_a")
            (Path(temp) / ".git").mkdir()
            with patch("microduck_companion.qwen9b_blind_review_packet._read_clipboard_text",
                       side_effect=AssertionError("do not inspect clipboard")):
                with self.assertRaisesRegex(ValueError, "outside a Git worktree"):
                    capture_clipboard_case(source, "scene_b")

    def test_cli_requires_opt_in_before_access_to_clipboard(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "new-folder"
            for args in [
                ["--source-dir", str(source), "--capture-clipboard-case", "scene_a"],
                ["--source-dir", str(source), "--authorize-private-source-write"],
                ["--source-dir", str(source), "--authorize-private-source-write",
                 "--capture-clipboard-case", "scene_a", "--write-private-packet"],
                ["--source-dir", str(source), "--authorize-private-source-write",
                 "--capture-clipboard-case", "scene_a", "--output-root", str(Path(temp) / "out")],
                ["--source-dir", str(source), "--authorize-private-source-write",
                 "--capture-clipboard-case", "invalid_case"],
            ]:
                with self.subTest(args=args), patch(
                    "microduck_companion.qwen9b_blind_review_packet._read_clipboard_text",
                    side_effect=AssertionError("clipboard must not be accessed")):
                    with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        main(args)
            self.assertFalse(source.exists())

    def test_dry_run_does_not_touch_clipboard(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "originals"
            source.mkdir()
            with patch("microduck_companion.qwen9b_blind_review_packet._read_clipboard_text",
                       side_effect=AssertionError("never read without capture switch")):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(["--source-dir", str(source)])

    def test_bad_clipboard_type_and_unknown_case_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "private"
            with patch("microduck_companion.qwen9b_blind_review_packet._read_clipboard_text",
                       return_value=None):
                with self.assertRaisesRegex(ValueError, "plain text"):
                    capture_clipboard_case(path, "scene_a")
            with patch("microduck_companion.qwen9b_blind_review_packet._read_clipboard_text",
                       side_effect=AssertionError("do not read")):
                with self.assertRaisesRegex(ValueError, "unknown fixed"):
                    capture_clipboard_case(path, "scene_z")
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
