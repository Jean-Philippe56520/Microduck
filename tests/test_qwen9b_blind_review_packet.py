"""QW-QUAL-2A: only synthetic operator JSON fixtures, never real model calls."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.qwen9b_blind_review_packet import (
    STUDY, _valid_report, collect_reports, main, make_packet,
)
from microduck_companion.qwen9b_role_preview import MODEL, ROLE_VERSION_V2
from microduck_companion.qwen9b_semantic_quality import CASE_IDS, make_synthetic_png


def fixture(case: str) -> dict:
    return {
        "study": STUDY,
        "mode": "one_real_pc_request",
        "case_id": case,
        "model": MODEL,
        "role_version": ROLE_VERSION_V2,
        "status": "unverified",
        "review_state": "independent_human_review_required",
        "quality_score": None,
        "advisor_text_for_human_only": "Local advice for " + case + " - unverified.",
        "machine_use": "blocked",
        "physical_actions_authorized": False,
        "motor_commands_issued": 0,
        "memory_writes": 0,
        "private_images_read": 0,
        "robot_validated": False,
        "model_text_saved_by_probe": False,
        "synthetic_image_saved_by_probe": False,
    }


def write_inputs(directory: Path) -> None:
    directory.mkdir()
    for case in CASE_IDS:
        (directory / (case + ".json")).write_text(
            json.dumps(fixture(case), ensure_ascii=False), encoding="utf-8"
        )


class BlindPacketTests(unittest.TestCase):
    def test_readonly_preflight_has_no_images_no_qwen_and_no_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sources"
            write_inputs(source)
            with patch("microduck_companion.qwen9b_blind_review_packet.make_synthetic_png",
                       side_effect=AssertionError("must not render")), redirect_stdout(io.StringIO()) as out:
                self.assertEqual(0, main(["--source-dir", str(source)]))
            report = json.loads(out.getvalue())
            self.assertEqual(report["mode"], "read_only_preflight")
            self.assertEqual(report["cases"], 4)
            self.assertEqual(report["files_written"], 0)
            self.assertNotIn("advisor_text", out.getvalue())
            self.assertEqual(sorted(p.name for p in Path(temp).iterdir()), ["sources"])

    def test_prepare_output_separated_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "originals"
            write_inputs(source)
            root = Path(temp) / "review"
            with redirect_stdout(io.StringIO()) as out:
                self.assertEqual(0, main(["--source-dir", str(source),
                    "--output-root", str(root), "--write-private-packet"]))
            safe = json.loads(out.getvalue())
            self.assertEqual(safe["share_only"], "REVIEWER_SHARE_ONLY")
            self.assertEqual(safe["review"], "independent_human_review_pending")
            self.assertEqual(safe["qwen_calls"], 0)
            reviewer = root / "REVIEWER_SHARE_ONLY"
            coordinator = root / "COORDINATOR_PRIVATE"
            mapping = json.loads((coordinator / "mapping.json").read_text("utf-8"))
            self.assertEqual(mapping["reviewer_independence"], "not_attested")
            self.assertEqual(mapping["source_authenticity"],
                             "operator_asserted_not_cryptographically_verified")
            self.assertEqual(len(mapping["cases"]), 4)
            self.assertEqual({e["case_id"] for e in mapping["cases"].values()},
                             set(CASE_IDS))
            self.assertEqual(len(list(reviewer.iterdir())), 10)
            self.assertTrue((reviewer / "READY.txt").exists())
            self.assertNotIn("mapping", " ".join(x.name for x in reviewer.iterdir()))
            self.assertTrue((reviewer / "BLIND_REVIEW_FORM.txt").exists())
            self.assertTrue((root / "READ_THIS_PRIVATE.txt").exists())
            for label, data in mapping["cases"].items():
                self.assertTrue(label.startswith("R"))
                self.assertEqual((reviewer / (label + ".txt")).read_text("utf-8"),
                                 fixture(data["case_id"])["advisor_text_for_human_only"])
                self.assertEqual((reviewer / (label + ".png")).read_bytes(),
                                 make_synthetic_png(data["case_id"]))
            before = sorted(str(p) for p in root.rglob("*"))
            with self.assertRaisesRegex(ValueError, "new empty destination"):
                make_packet(source, root)
            self.assertEqual(before, sorted(str(p) for p in root.rglob("*")))

    def test_missing_text_or_case_fails_without_creating_output(self):
        for damage, expected in [
            (lambda r: r.pop("advisor_text_for_human_only"), "complete adviser"),
            (lambda r: r.update(case_id="scene_a"), "case_id"),
            (lambda r: r.update(model="not_the_9b"), "model"),
            (lambda r: r.update(status="unavailable"), "status"),
            (lambda r: r.update(quality_score=1), "unscored"),
            (lambda r: r.update(machine_use="allowed"), "machine_use"),
            (lambda r: r.update(motor_commands_issued=True), "motor_commands"),
            (lambda r: r.update(physical_actions_authorized=True), "physical_actions"),
            (lambda r: r.update(model_text_saved_by_probe=True), "model_text_saved"),
        ]:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp:
                source = Path(temp) / "originals"
                write_inputs(source)
                bad = fixture("scene_c")
                damage(bad)
                (source / "scene_c.json").write_text(json.dumps(bad), encoding="utf-8")
                dest = Path(temp) / "should_never_exist"
                with self.assertRaisesRegex(ValueError, expected):
                    make_packet(source, dest)
                self.assertFalse(dest.exists())

    def test_no_fabrication_if_original_json_missing_or_duplicate_text(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "originals"
            write_inputs(source)
            (source / "scene_b.json").unlink()
            dest = Path(temp) / "out"
            with self.assertRaisesRegex(ValueError, "scene_b"):
                make_packet(source, dest)
            self.assertFalse(dest.exists())
            (source / "scene_b.json").write_text(json.dumps(fixture("scene_b")))
            same = fixture("scene_c")
            same["advisor_text_for_human_only"] = fixture("scene_a")["advisor_text_for_human_only"]
            (source / "scene_c.json").write_text(json.dumps(same))
            with self.assertRaisesRegex(ValueError, "identical adviser"):
                collect_reports(source)

    def test_strict_json_input_rejects_duplicates_truncation_and_overbudget(self):
        for source in [
            b'{"case_id":"scene_a","case_id":"scene_b"}',
            b'{"status":NaN}',
            b'[]',
            b'{"bad":',
            b'x' * 32769,
        ]:
            with self.subTest(source=source[:22]), self.assertRaises(ValueError):
                _valid_report(source, "scene_a")

    def test_prevent_repo_leaks_and_symlink_files_and_overlaps(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "originals"
            write_inputs(source)
            with self.assertRaisesRegex(ValueError, "overlap"):
                make_packet(source, source / "out")
            with self.assertRaisesRegex(ValueError, "overlap"):
                make_packet(source, Path(temp))
            (Path(temp) / ".git").mkdir()
            with self.assertRaisesRegex(ValueError, "Git worktree"):
                collect_reports(source)
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "originals"
            write_inputs(source)
            (source / "scene_a.json").unlink()
            (source / "scene_a.json").symlink_to(source / "scene_b.json")
            with self.assertRaisesRegex(ValueError, "scene_a"):
                collect_reports(source)

    def test_cli_explicit_opt_in_and_absolute_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "originals"
            write_inputs(source)
            for flags in [
                ["--source-dir", str(source), "--write-private-packet"],
                ["--source-dir", str(source), "--output-root", str(Path(temp) / "out")],
            ]:
                with self.subTest(flags=flags), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        main(flags)
            with self.assertRaisesRegex(ValueError, "absolute"):
                collect_reports(Path("originals"))


if __name__ == "__main__":
    unittest.main()
