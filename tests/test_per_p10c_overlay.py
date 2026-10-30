"""PER-P10C pinned OEM integration: negative tests without camera, NPU or robot."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL, replace_once
from scripts.per_p10b_apply_oem_tail_overlay import OverlayRefused
from scripts.per_p10c_apply_oem_mediad_overlay import (
    DETECT_BLOB, apply, BACKEND_BEGIN, WORKER_BEGIN, SIGHTING_BEGIN,
)


class P10CSingleTeeSafetyTests(unittest.TestCase):
    def test_pinned_oem_exact_contract_anchors_are_declared(self):
        self.assertEqual(DETECT_BLOB, "2383f297533fe775a39b6452ed528c4087f82d89")
        self.assertIn("Npu(", BACKEND_BEGIN)
        self.assertIn("Cpu(", BACKEND_BEGIN)
        self.assertIn("match backend.infer", WORKER_BEGIN)
        self.assertIn("pub found: Vec<Detection>", SIGHTING_BEGIN)

    def test_source_anchor_failure_is_fail_closed(self):
        for text in ("missing", "same same"):
            with self.assertRaises(ValueError):
                replace_once(text, "same", "changed")

    def test_unmarked_checkout_wrong_pin_missing_p10a_p10b_refused(self):
        with tempfile.TemporaryDirectory(prefix="per-p10c-") as tmp:
            archive = Path(tmp)
            project = archive / "project"
            project.mkdir()
            with self.assertRaises(OverlayRefused):
                apply(archive, project)
            (archive / SENTINEL).write_text("wrong", encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(archive, project)
            (archive / SENTINEL).write_text(PIN, encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(archive, project)
            (archive / ".git").mkdir()
            with self.assertRaises(OverlayRefused):
                apply(archive, project)
            self.assertFalse((archive / "mediad" / "src" / "detect" / "seg.rs").exists())
            self.assertFalse((archive / "p10c-harness").exists())

    def test_existing_overlay_never_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="per-p10c-") as tmp:
            archive = Path(tmp)
            project = archive / "project"
            project.mkdir()
            (archive / SENTINEL).write_text(PIN, encoding="utf-8")
            destination = archive / "mediad" / "src" / "detect" / "seg.rs"
            destination.parent.mkdir(parents=True)
            destination.write_text("existing", encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(archive, project)
            self.assertEqual(destination.read_text(), "existing")


if __name__ == "__main__":
    unittest.main()
