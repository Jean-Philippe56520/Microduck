"""P15-B17: source-only recipe fixtures; no BitBake, rootfs or /run access."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import per_p15b17_oem_receiver_package as b17

ROOT = Path(__file__).resolve().parents[1]


class P15B17PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kwipi-b17-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.layer = self.work / "first"

    def _stage(self):
        return b17.stage(ROOT, self.layer)

    def test_01_existing_b10_source_and_exact_four_additions(self):
        result = self._stage()
        self.assertEqual(result["historical_python_modules"], 24)
        self.assertEqual(result["new_modules"], 4)
        self.assertEqual(result["status"],
                         "b17_source_only_b12_receiver_candidate_not_bitbake")
        self.assertEqual(result, b17.verify(ROOT, self.layer))
        self.assertEqual(set(result["new_sha256"]), b17.SELECTED)
        self.assertEqual(len(result["historical_b6_sha256"]), 5)
        self.assertTrue(result["companion_import_edges"])
        for key in ("bitbake_executed", "bitbake_parsed", "service_installed",
                    "rootfs_modified", "oem_producer_enabled", "oem_sensor_verified",
                    "robot_validated", "motor_commands_issued", "dev_image_selected",
                    "shipping_image_selected", "license_redistribution_approved"):
            self.assertFalse(result[key], key)

    def test_02_repeated_staging_is_deterministic(self):
        first = self._stage()
        next_dir = self.work / "second"
        self.assertEqual(first, b17.stage(ROOT, next_dir))
        paths = {p.relative_to(self.layer) for p in self.layer.rglob("*") if p.is_file()}
        self.assertEqual(paths, {p.relative_to(next_dir) for p in next_dir.rglob("*")
                                 if p.is_file()})
        for path in paths:
            self.assertEqual((self.layer / path).read_bytes(),
                             (next_dir / path).read_bytes())

    def test_03_recipe_does_not_select_images_or_modify_oem(self):
        self._stage()
        recipe = (self.layer / b17.RECIPE_PATH).read_text()
        self.assertIn('LICENSE = "CLOSED"', recipe)
        self.assertIn("inherit allarch python3-dir", recipe)
        self.assertIn("RDEPENDS:", recipe)
        self.assertIn("kwipi-companion kwipi-passive-fixture", recipe)
        self.assertIn("SRC_URI[p15b17.sha256sum]", recipe)
        self.assertEqual(recipe.count("install -m 0644"), 1)
        for banned in ("IMAGE_INSTALL", "ExecStart=", "SYSTEMD_AUTO_ENABLE",
                       "robotd.sock", "media.sock", "kwipi_local_detections",
                       "SupplementaryGroups", "USERADD_PARAM"):
            self.assertNotIn(banned, recipe)
        self.assertEqual(set(b17.staged_files(ROOT)[0]), {
            "conf/layer.conf", b17.RECIPE_PATH, b17.ARCHIVE_PATH, b17.REPORT_PATH})

    def test_04_extra_or_missing_artifact_refused(self):
        self._stage()
        extra = self.layer / "unexpected.txt"
        extra.write_text("unexpected")
        with self.assertRaises(b17.Refused):
            b17.verify(ROOT, self.layer)
        extra.unlink()
        (self.layer / b17.REPORT_PATH).unlink()
        with self.assertRaises(b17.Refused):
            b17.verify(ROOT, self.layer)

    def test_05_tampered_recipe_and_archive_refused(self):
        self._stage()
        for rel in (b17.RECIPE_PATH, b17.ARCHIVE_PATH):
            target = self.layer / rel
            saved = target.read_bytes()
            target.write_bytes(saved + b"unsafe")
            with self.subTest(target=rel), self.assertRaises(b17.Refused):
                b17.verify(ROOT, self.layer)
            target.write_bytes(saved)

    def test_06_symlinked_provenance_refused(self):
        self._stage()
        file = self.layer / b17.REPORT_PATH
        target = self.work / "outside.json"
        target.write_bytes(file.read_bytes())
        file.unlink()
        file.symlink_to(target)
        with self.assertRaises(b17.Refused):
            b17.verify(ROOT, self.layer)

    def test_07_unreviewed_imports_refused(self):
        original, _ = b17.selected(ROOT)
        previous = set(b17.p14b.p14a.SELECTED) | b17.b6.ADDON
        name = "microduck_companion/b16_oem_readonly_reader.py"
        for tail in (b"\nimport sqlite3\n",
                     b"\nfrom .unreviewed_motor import x\n",
                     b"\nfrom ..outside import x\n"):
            modified = dict(original)
            modified[name] += tail
            with self.subTest(tail=tail), self.assertRaises(b17.Refused):
                b17.audit_new_sources(modified, previous)

    def test_08_unapproved_side_effects_refused(self):
        original, _ = b17.selected(ROOT)
        previous = set(b17.p14b.p14a.SELECTED) | b17.b6.ADDON
        name = "microduck_companion/b16_oem_readonly_reader.py"
        for tail in (b"\nos.setxattr('/tmp', 'a', b'0')\n",
                     b"\nconn.sendall(b'robot.move')\n",
                     b"\nPath('/tmp/x').write_text('unsafe')\n"):
            modified = dict(original)
            modified[name] += tail
            with self.subTest(tail=tail), self.assertRaises(b17.Refused):
                b17.audit_new_sources(modified, previous)

    def test_09_receiver_explicit_opt_in_and_exact_set(self):
        original, _ = b17.selected(ROOT)
        previous = set(b17.p14b.p14a.SELECTED) | b17.b6.ADDON
        name = "microduck_companion/b16_oem_readonly_reader.py"
        changed = dict(original)
        changed[name] = changed[name].replace(b"enabled: bool = False",
                                            b"enabled: bool = True")
        with self.assertRaises(b17.Refused):
            b17.audit_new_sources(changed, previous)
        changed = dict(original)
        changed.pop(name)
        with self.assertRaises(b17.Refused):
            b17.audit_new_sources(changed, previous)
        changed = dict(original)
        changed["microduck_companion/extra.py"] = b"print('unsafe')"
        with self.assertRaises(b17.Refused):
            b17.audit_new_sources(changed, previous)

    def test_10_staging_cannot_overwrite_or_write_in_checkout(self):
        self._stage()
        with self.assertRaises(b17.Refused):
            b17.stage(ROOT, self.layer)
        with self.assertRaises(b17.Refused):
            b17.stage(ROOT, ROOT / "scripts/unsafe-b17-output")
        with self.assertRaises(b17.Refused):
            b17.stage(ROOT, Path("relative-output"))
        link = self.work / "link"
        link.symlink_to(self.layer, target_is_directory=True)
        with self.assertRaises(b17.Refused):
            b17.stage(ROOT, link)

    def test_11_archive_manifest_checksum_and_b10_pins(self):
        report = self._stage()
        tar = (self.layer / b17.ARCHIVE_PATH).read_bytes()
        self.assertEqual(report["archive_sha256"], hashlib.sha256(tar).hexdigest())
        self.assertEqual(report["historical_p14b_archive_sha256"],
                         b17.p16a.PINNED_P14B_ARCHIVE_SHA256)
        self.assertEqual(report["historical_b6_sha256"], b17.b10.B6_SHA256)

    def test_12_historical_b6_hash_drift_refused(self):
        original = dict(b17.b10.B6_SHA256)
        original[next(iter(original))] = "0" * 64
        with patch.object(b17.b10, "B6_SHA256", original):
            with self.assertRaises(b17.Refused):
                b17.staged_files(ROOT)


if __name__ == "__main__":
    unittest.main()
