"""P13B1 positive/negative tests of BitBake-unpacked-source integrity gate.

Isolated fixtures do not stand in for BitBake. The CI additionally executes
real pinned kas/BitBake do_fetch and do_unpack before using this validator.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import io
import tarfile
import unittest
from unittest.mock import patch

from scripts.per_p12_yocto_layer import BMI_SHA, MODEL_NAME
from scripts.per_p13a_bitbake_env_gate import EnvRefused
from scripts.per_p13b1_unpacked_source_gate import (
    REQUIRED_MEMBERS, SCHEMA, _regular, validate_unpacked,
)

PINNED = {
    "schema": "kwipi-p12-yocto-source-layer-v1",
    "archive_sha256": "b" * 64,
    "companion_sha": "c" * 40,
    "oem_sha": "d" * 40,
    "yocto_sha": "e" * 40,
    "crates_generated": 568,
}


class SourceGateTests(unittest.TestCase):
    def setUp(self):
        self.t = TemporaryDirectory()
        self.addCleanup(self.t.cleanup)
        self.base = Path(self.t.name)
        self.build = self.base / "build"
        self.tmp = self.build / "tmp"
        self.unpack = self.tmp / "work/pkg/unpack"
        self.src = self.unpack / "microduck-daemon-test"
        self.src.mkdir(parents=True)
        self.layer = self.base / "meta-kwipi"
        archive = (self.layer / "recipes-microduck/microduck-daemon/files"
                   / MODEL_NAME)
        archive.parent.mkdir(parents=True)
        self.archive = archive
        with tarfile.open(archive, "w:gz") as tf:
            for name in REQUIRED_MEMBERS:
                data = ("source:" + name + "\n").encode("ascii")
                member = tarfile.TarInfo(name)
                member.size = len(data)
                tf.addfile(member, io.BytesIO(data))
                p = self.src / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data)
        (self.unpack / "bmi088-rs").mkdir()
        self.env = "\n".join((
            f'S="{self.src}"',
            f'UNPACKDIR="{self.unpack}"',
            f'TMPDIR="{self.tmp}"',
            f'SRCREV_bmi088="{BMI_SHA}"',
        )) + "\n"
        self.patch_p12 = patch(
            "scripts.per_p13b1_unpacked_source_gate.verify_p12",
            return_value=PINNED,
        )
        self.patch_p13a = patch(
            "scripts.per_p13b1_unpacked_source_gate.validate_p13a",
            return_value={"bitbake_parse_passed": True,
                          "bitbake_compile_run": False},
        )
        self.patch_vendor = patch(
            "scripts.per_p13b1_unpacked_source_gate._vendor_revision",
            return_value=BMI_SHA,
        )
        self.patch_p12.start()
        self.patch_p13a.start()
        self.patch_vendor.start()
        self.addCleanup(self.patch_p12.stop)
        self.addCleanup(self.patch_p13a.stop)
        self.addCleanup(self.patch_vendor.stop)

    def check(self, env=None):
        return validate_unpacked(
            env_text=self.env if env is None else env,
            layer=self.layer, build_dir=self.build,
        )

    def test_complete_fixture_source_passes_but_not_compile(self):
        report = self.check()
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["status"], "bitbake_unpacked_source_verified")
        self.assertEqual(report["source_members_verified"], len(REQUIRED_MEMBERS))
        self.assertEqual(report["vendor_bmi088_unpacked_sha"], BMI_SHA)
        for key in ("bitbake_compile_run", "bitbake_package_run", "rauc_built",
                    "signed_release", "python_companion_installed", "robot_tested"):
            self.assertIs(report[key], False)

    def test_missing_extracted_file_is_fatal(self):
        (self.src / "Cargo.lock").unlink()
        with self.assertRaises(EnvRefused):
            self.check()

    def test_modified_extracted_file_is_fatal(self):
        with (self.src / "mediad/Cargo.toml").open("ab") as f:
            f.write(b"\n# unexpected source modification")
        with self.assertRaises(EnvRefused):
            self.check()

    def test_symlinked_source_is_fatal(self):
        p = self.src / "duck-detect/Cargo.toml"
        p.unlink()
        p.symlink_to(self.src / "Cargo.toml")
        with self.assertRaises(EnvRefused):
            self.check()

    def test_wrong_source_dir_or_tmpdir_is_fatal(self):
        old = str(self.src)
        new = str(self.base / "unrelated")
        with self.assertRaises(EnvRefused):
            self.check(self.env.replace(f'S="{old}"', f'S="{new}"'))
        with self.assertRaises(EnvRefused):
            self.check(self.env.replace(f'TMPDIR="{self.tmp}"',
                                        f'TMPDIR="{self.base}"'))

    def test_wrong_vendor_pin_is_fatal(self):
        with self.assertRaises(EnvRefused):
            self.check(self.env.replace(BMI_SHA, "f" * 40))

    def test_missing_vendor_directory_is_fatal(self):
        (self.unpack / "bmi088-rs").rmdir()
        with self.assertRaises(EnvRefused):
            self.check()

    def test_vendor_revision_mismatch_is_fatal(self):
        with patch("scripts.per_p13b1_unpacked_source_gate._vendor_revision",
                   return_value="f" * 40):
            with self.assertRaises(EnvRefused):
                self.check()

    def test_metadata_contract_must_have_succeeded(self):
        with patch("scripts.per_p13b1_unpacked_source_gate.validate_p13a",
                   return_value={"bitbake_parse_passed": False,
                                 "bitbake_compile_run": False}):
            with self.assertRaises(EnvRefused):
                self.check()

    def test_regular_source_refuses_traversal(self):
        with self.assertRaises(EnvRefused):
            _regular(self.src, "../../outside")


if __name__ == "__main__":
    unittest.main()
