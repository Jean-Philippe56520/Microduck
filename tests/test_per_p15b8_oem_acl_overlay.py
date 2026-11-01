"""P15-B8 source-only fail-closed overlay checks; no OEM socket is opened.

Actual Linux Rust ACL tests run separately on a disposable OEM source archive
by the existing P15-B4 workflow. These Python tests mutate only tempfile
stand-ins for the pinned OEM source marker, B4 module and B4 main snippet.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL
from scripts.per_p10b_apply_oem_tail_overlay import OverlayRefused
from scripts import per_p15b4_apply_oem_local_detections as b4
from scripts import per_p15b8_apply_oem_acl_binder as b8


ROOT = Path(__file__).resolve().parents[1]


class P15B8OverlayOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kwipi-b8-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.archive = self.base / "oem-copy"
        self.archive.mkdir()
        (self.archive / SENTINEL).write_text(PIN + "\n")
        self.project = self.base / "project"
        src = self.project / "scripts"
        src.mkdir(parents=True)
        for name in ("per_p15b4_local_detections.rs",
                     "per_p15b8_acl_policy.rs"):
            shutil.copyfile(ROOT / "scripts" / name, src / name)
        self.med = self.archive / "mediad" / "src"
        self.med.mkdir(parents=True)
        self.main = self.med / "main.rs"
        self.main.write_text(b4.ARGS_TO + "\n" + b4.MAIN_ADDITION + "\n")
        self.local = self.med / b4.MODULE_NAME
        shutil.copyfile(src / "per_p15b4_local_detections.rs", self.local)
        self.helper = self.med / b8.HELPER_NAME

    def test_01_applies_only_to_b4_in_disposable_tree(self):
        original_main = self.main.read_bytes()
        original_source = (self.project / "scripts/per_p15b4_local_detections.rs").read_bytes()
        b8.apply(self.archive, self.project)
        self.assertEqual(self.main.read_bytes(), original_main)
        self.assertEqual(
            (self.project / "scripts/per_p15b4_local_detections.rs").read_bytes(),
            original_source)
        self.assertEqual(
            self.helper.read_bytes(),
            (self.project / "scripts/per_p15b8_acl_policy.rs").read_bytes())
        changed = self.local.read_text()
        for anchor in ("include!(\"local_detections_acl.rs\")",
                       "bind_with_uid(&private.join(\"detections.sock\"), uid)",
                       "acl_policy::grant_private_dir(parent, uid)",
                       "acl_policy::grant_socket(path, uid)",
                       "fn bind_checked("):
            self.assertIn(anchor, changed)
        self.assertEqual(changed.count("mod acl_policy"), 1)
        self.assertEqual(changed.count("grant_socket(path, uid)"), 1)

    def test_02_repeat_overlay_refuses_without_mutation(self):
        b8.apply(self.archive, self.project)
        changed = self.local.read_bytes()
        with self.assertRaises(OverlayRefused):
            b8.apply(self.archive, self.project)
        self.assertEqual(self.local.read_bytes(), changed)

    def test_03_bad_pinned_marker_refuses(self):
        (self.archive / SENTINEL).write_text("wrong-pin\n")
        with self.assertRaises(OverlayRefused):
            b8.apply(self.archive, self.project)
        self.assertFalse(self.helper.exists())

    def test_04_tampered_b4_source_refuses_and_preserves_bytes(self):
        self.local.write_text(self.local.read_text() + "\n// tampered\n")
        original = self.local.read_bytes()
        with self.assertRaises(OverlayRefused):
            b8.apply(self.archive, self.project)
        self.assertEqual(self.local.read_bytes(), original)
        self.assertFalse(self.helper.exists())

    def test_05_missing_main_opt_in_contract_refuses(self):
        self.main.write_text("unrelated mediad fixture")
        with self.assertRaises(OverlayRefused):
            b8.apply(self.archive, self.project)
        self.assertFalse(self.helper.exists())

    def test_06_symlinked_b4_module_or_helper_refuses(self):
        self.local.unlink()
        self.local.symlink_to(self.project / "scripts/per_p15b4_local_detections.rs")
        with self.assertRaises(OverlayRefused):
            b8.apply(self.archive, self.project)
        self.assertFalse(self.helper.exists())
        self.local.unlink()
        shutil.copyfile(self.project / "scripts/per_p15b4_local_detections.rs", self.local)
        self.helper.symlink_to(self.project / "scripts/per_p15b8_acl_policy.rs")
        with self.assertRaises(OverlayRefused):
            b8.apply(self.archive, self.project)

    def test_07_source_helper_missing_contract_refuses(self):
        helper = self.project / "scripts/per_p15b8_acl_policy.rs"
        helper.write_text("not a policy\n")
        with self.assertRaises(OverlayRefused):
            b8.apply(self.archive, self.project)
        self.assertFalse(self.helper.exists())

    def test_08_existing_git_directory_refuses(self):
        (self.archive / ".git").mkdir()
        with self.assertRaises(OverlayRefused):
            b8.apply(self.archive, self.project)
        self.assertFalse(self.helper.exists())

    def test_09_missing_one_anchor_has_zero_writes(self):
        # Replacing the authoritative B4 file at both source+stage still must
        # refuse if any of the six exact insertion anchors has drifted.
        changed = self.local.read_text().replace(
            b8.DEFAULT_FROM, "    // unexpected source contract\n")
        self.local.write_text(changed)
        (self.project / "scripts/per_p15b4_local_detections.rs").write_text(changed)
        with self.assertRaises(OverlayRefused):
            b8.apply(self.archive, self.project)
        self.assertEqual(self.local.read_text(), changed)
        self.assertFalse(self.helper.exists())


if __name__ == "__main__":
    unittest.main()
