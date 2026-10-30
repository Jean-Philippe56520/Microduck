"""PER-P10A: test overlay safety without accessing model, device or OEM files."""
from pathlib import Path
import tempfile
import unittest

from scripts.per_p10a_apply_oem_rknn_overlay import (
    PIN, SENTINEL, OverlayRefused, apply, replace_once,
)


class OverlaySafetyTests(unittest.TestCase):
    def test_single_exact_anchor_replaced_without_other_edits(self):
        self.assertEqual(replace_once("a--pin--z", "--pin--", "ok"), "aokz")

    def test_missing_or_ambiguous_anchor_refused(self):
        for input_ in ("unchanged", "pin pin"):
            with self.subTest(input_=input_):
                with self.assertRaises(OverlayRefused):
                    replace_once(input_, "pin", "patched")

    def test_non_archive_and_invalid_source_blob_refused_without_edit(self):
        with tempfile.TemporaryDirectory(prefix="per-p10a-safety-") as tmp:
            root = Path(tmp)
            src = root / "duck-detect" / "src" / "rknn.rs"
            src.parent.mkdir(parents=True)
            src.write_text("not the audited OEM version", encoding="utf-8")
            extension = root / "extension.rs"
            extension.write_text("// no actual model", encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(root, extension)
            (root / SENTINEL).write_text("wrong-pin", encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(root, extension)
            (root / SENTINEL).write_text(PIN, encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(root, extension)
            self.assertEqual(src.read_text(), "not the audited OEM version")
            self.assertFalse((src.parent / "rknn" / "segments.rs").exists())

    def test_real_git_checkout_explicitly_refused(self):
        with tempfile.TemporaryDirectory(prefix="per-p10a-checkout-") as tmp:
            root = Path(tmp)
            (root / SENTINEL).write_text(PIN, encoding="utf-8")
            (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(root, root / "extension.rs")

    def test_never_overwrite_an_existing_overlay(self):
        with tempfile.TemporaryDirectory(prefix="per-p10a-existing-") as tmp:
            root = Path(tmp)
            (root / SENTINEL).write_text(PIN, encoding="utf-8")
            src = root / "duck-detect" / "src" / "rknn.rs"
            dest = root / "duck-detect" / "src" / "rknn" / "segments.rs"
            dest.parent.mkdir(parents=True)
            src.write_text("original", encoding="utf-8")
            dest.write_text("existing", encoding="utf-8")
            extension = root / "extension.rs"
            extension.write_text("replacement", encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(root, extension)
            self.assertEqual(dest.read_text(), "existing")
            self.assertEqual(src.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
