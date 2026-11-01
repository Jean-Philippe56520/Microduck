"""P15-B4: fail-closed overlay checks without camera, OEM binaries or models.

Tests run on small stand-in files. The dedicated Rust CI also assembles the
actual P10A/B/C archive from the pinned OEM sources and compiles mediad.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL
from scripts.per_p10b_apply_oem_tail_overlay import OverlayRefused
from scripts import per_p15b4_apply_oem_local_detections as b4


class P15B4OverlaySafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="per-p15b4-test-")
        self.addCleanup(self.tmp.cleanup)
        self.archive = Path(self.tmp.name) / "oem-scratch"
        self.project = Path(self.tmp.name) / "project"
        self.archive.mkdir()
        self.project.mkdir()
        (self.archive / SENTINEL).write_text(PIN + "\n", encoding="utf-8")
        self.med = self.archive / "mediad" / "src"
        self.med.mkdir(parents=True)
        self.main = self.med / "main.rs"
        self.lib = self.med / "lib.rs"
        self.detector = self.med / "detect.rs"
        self.main.write_text(b4.ARGS_FROM + "\n" + b4.MAIN_ANCHOR + "\n", encoding="utf-8")
        self.lib.write_text(b4.LIB_FROM + "\n", encoding="utf-8")
        self.detector.write_text(
            "pub region_candidates: Option<_>;\n"
            "pub(crate) mod seg;\n"
            "frames.next_frame()\n"
            "pub fn notification(sighting: &Sighting) {}\n",
            encoding="utf-8",
        )
        scripts = self.project / "scripts"
        scripts.mkdir()
        (scripts / "per_p15b4_local_detections.rs").write_text(
            "region_candidates: None\n", encoding="utf-8",
        )
        self.module = self.med / b4.MODULE_NAME

    def apply_pinned_fixture(self) -> None:
        def pinned_hash(path: Path) -> str:
            return b4.MAIN_BLOB if path.name == "main.rs" else b4.LIB_BLOB
        with mock.patch.object(b4, "git_hash", side_effect=pinned_hash):
            b4.apply(self.archive, self.project)

    def test_01_existing_oem_contract_is_pinned_and_no_extra_dependency(self) -> None:
        self.assertEqual("58ce574c8ff52d35a0c1d1999553b2115c86f8ed", b4.MAIN_BLOB)
        self.assertEqual("e99c50d33a171ee14c2ed8363a4ea029ed2f75e7", b4.LIB_BLOB)
        self.assertIn("default_value_t = false", b4.ARGS_TO)
        self.assertIn("local_detections::serve(listener, sightings)", b4.MAIN_ADDITION)
        self.assertIn("existing.sightings.clone()", b4.MAIN_ADDITION)
        self.assertNotIn("media.frame", b4.MAIN_ADDITION)
        self.assertNotIn("robot.move", b4.MAIN_ADDITION)

    def test_02_pinned_source_adapts_only_in_ephemeral_directory(self) -> None:
        self.apply_pinned_fixture()
        self.assertTrue(self.module.is_file())
        self.assertEqual("region_candidates: None\n", self.module.read_text())
        self.assertEqual(1, self.main.read_text().count("kwipi_local_detections: bool"))
        self.assertEqual(1, self.main.read_text().count("local_detections::bind_default()"))
        self.assertEqual(1, self.lib.read_text().count("pub mod local_detections;"))
        self.assertIn("pub mod frame;", self.lib.read_text())
        self.assertNotIn("robotd", self.main.read_text())
        self.assertNotIn("media.frame", self.main.read_text())

    def test_03_reapply_refuses_without_overwriting_existing_module(self) -> None:
        self.apply_pinned_fixture()
        original = self.module.read_bytes()
        with self.assertRaises(OverlayRefused):
            self.apply_pinned_fixture()
        self.assertEqual(original, self.module.read_bytes())

    def test_04_missing_or_wrong_pin_and_git_worktree_are_refused(self) -> None:
        marker = self.archive / SENTINEL
        marker.unlink()
        with self.assertRaises(OverlayRefused):
            self.apply_pinned_fixture()
        marker.write_text("wrong", encoding="utf-8")
        with self.assertRaises(OverlayRefused):
            self.apply_pinned_fixture()
        marker.write_text(PIN, encoding="utf-8")
        (self.archive / ".git").mkdir()
        with self.assertRaises(OverlayRefused):
            self.apply_pinned_fixture()
        self.assertFalse(self.module.exists())

    def test_05_wrong_original_source_hashes_are_refused(self) -> None:
        for m, l in (("wrong", b4.LIB_BLOB), (b4.MAIN_BLOB, "wrong")):
            with self.subTest(main=m, lib=l):
                with mock.patch.object(b4, "git_hash", side_effect=[m, l]):
                    with self.assertRaises(OverlayRefused):
                        b4.apply(self.archive, self.project)
                self.assertFalse(self.module.exists())

    def test_06_absent_p10c_detector_contract_fails_closed(self) -> None:
        for source in ("", "frames.next_frame()\n",
                       "pub(crate) mod seg;\nframes.next_frame()\n"):
            with self.subTest(source=source):
                self.detector.write_text(source)
                with self.assertRaises(OverlayRefused):
                    self.apply_pinned_fixture()
                self.assertFalse(self.module.exists())

    def test_07_broken_anchor_fails_before_any_write(self) -> None:
        before_lib = self.lib.read_bytes()
        original = self.main.read_text()
        self.main.write_text("different", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.apply_pinned_fixture()
        self.assertEqual(before_lib, self.lib.read_bytes())
        self.assertEqual("different", self.main.read_text())
        self.assertFalse(self.module.exists())
        self.main.write_text(original)

        self.lib.write_text("different", encoding="utf-8")
        before_main = self.main.read_bytes()
        with self.assertRaises(ValueError):
            self.apply_pinned_fixture()
        self.assertEqual(before_main, self.main.read_bytes())
        self.assertFalse(self.module.exists())

    def test_08_symlink_sources_are_rejected_before_write(self) -> None:
        self.main.unlink()
        self.main.symlink_to(self.lib)
        with self.assertRaises(OverlayRefused):
            self.apply_pinned_fixture()
        self.assertFalse(self.module.exists())

    def test_09_existing_destination_never_replaced(self) -> None:
        self.module.write_text("do not replace")
        with self.assertRaises(OverlayRefused):
            self.apply_pinned_fixture()
        self.assertEqual("do not replace", self.module.read_text())

    def test_10_source_template_never_grants_motion_or_category(self) -> None:
        source = (Path(__file__).parent.parent / "scripts" /
                  "per_p15b4_local_detections.rs").read_text()
        self.assertIn('"media.detections"', source)
        self.assertIn("mode(0o700)", source)
        self.assertIn("from_millis(500)", source)
        self.assertIn("MAX_CLIENTS: usize = 2", source)
        # Test bodies intentionally contain rejected RPC strings and names;
        # only the server implementation, never fixture assertions, is policed.
        production = source.split("#[cfg(test)]", 1)[0]
        self.assertNotIn("robot.do", production)
        self.assertNotIn("robot.stop", production)
        self.assertNotIn("media.frame", production)
        self.assertNotIn("send_robot", production)
        self.assertNotIn("cmd_vel", production)


if __name__ == "__main__":
    unittest.main()
