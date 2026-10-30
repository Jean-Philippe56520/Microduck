"""PER-P10B: forbid accidental installation or source/contract drift."""
import tempfile
import unittest
from pathlib import Path

from scripts.per_p10b_apply_oem_tail_overlay import (
    CORE_BLOBS, OEM_LIB_ANCHOR, OEM_CARGO_ANCHOR, OverlayRefused, apply,
)
from scripts.per_p10b_synthetic_onnx import HEADS, SHAPES, PROTOS
from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL


class P10BIntegrityTests(unittest.TestCase):
    def test_ten_original_head_names_are_frozen(self):
        self.assertEqual(len(HEADS), 9)
        self.assertEqual(len(set(HEADS)), 9)
        self.assertTrue(all(x.endswith("Conv_output_0") for x in HEADS))
        self.assertEqual([s[1] for s in SHAPES], [4, 4, 4, 80, 80, 80, 32, 32, 32])
        self.assertEqual(PROTOS, (1, 32, 160, 160))
        self.assertEqual(sum(__import__("math").prod(x) for x in SHAPES)
                         + __import__("math").prod(PROTOS), 1_793_600)

    def test_core_contract_is_explicit_and_never_copied_from_unknown_source(self):
        self.assertEqual(set(CORE_BLOBS), {
            "Cargo.toml", "src/lib.rs", "src/oem_region.rs"
        })
        self.assertIn("pub mod rknn", OEM_LIB_ANCHOR)
        self.assertIn('anyhow = "1"', OEM_CARGO_ANCHOR)

    def test_refuses_checkout_unmarked_archive_and_uninstalled_p10a(self):
        with tempfile.TemporaryDirectory(prefix="p10b-negative-") as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            source = root / "example.rs"
            source.write_text("// synthetic", encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(root, source, project)
            (root / SENTINEL).write_text("wrong", encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(root, source, project)
            (root / SENTINEL).write_text(PIN, encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(root, source, project)
            (root / ".git").mkdir()
            with self.assertRaises(OverlayRefused):
                apply(root, source, project)
            self.assertFalse((root / "kwipi-seg-mask-core").exists())
            self.assertFalse((root / "duck-detect" / "src" / "seg_tail.rs").exists())

    def test_reapplication_and_wrong_pin_cannot_look_successful(self):
        with tempfile.TemporaryDirectory(prefix="p10b-negative-") as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (root / SENTINEL).write_text(PIN, encoding="utf-8")
            source = root / "example.rs"
            source.write_text("example", encoding="utf-8")
            target = root / "duck-detect" / "src" / "seg_tail.rs"
            target.parent.mkdir(parents=True)
            target.write_text("existing", encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(root, source, project)
            self.assertEqual(target.read_text(), "existing")


if __name__ == "__main__":
    unittest.main()
