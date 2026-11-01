"""P15-B6-P: adversarial fake PKGDEST checks; NOT real BitBake execution."""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6
from scripts.per_p13a_bitbake_env_gate import EnvRefused
from scripts.per_p15b6_bitbake_package_gate import PASS, validate_package

ROOT = Path(__file__).resolve().parents[1]


class B6PPackageGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="p15b6p-")
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.base = self.work / p14b.LAYER
        self.addon = self.work / b6.LAYER
        self.dev_layer = ROOT / "yocto/meta-kwipi-dev-image"
        p14b.stage(ROOT, self.base)
        self.source = b6.stage(ROOT, self.addon)
        self.tmp = self.work / "build" / "tmp"
        self.pkgdest = self.tmp / "work" / "packages-split"
        self.target = self.pkgdest / b6.PN / "usr/lib/python3.14/site-packages/microduck_companion"
        self.target.mkdir(parents=True)
        for rel in sorted(b6.ADDON):
            shutil.copyfile(ROOT / rel, self.target / Path(rel).name)
        self.env = "\n".join((
            'PN="kwipi-passive-fixture"',
            'PV="0.1.0"',
            'LICENSE="CLOSED"',
            'PACKAGE_ARCH="all"',
            f'SRC_URI="file://{b6.SRC_NAME};subdir={b6.PN}-{b6.PV};name=p15b6"',
            f'S="{self.tmp / "unpack" / (b6.PN + "-" + b6.PV)}"',
            f'BP="{b6.PN}-{b6.PV}"',
            f'UNPACKDIR="{self.tmp / "unpack"}"',
            f'TMPDIR="{self.tmp}"',
            f'PKGDEST="{self.pkgdest}"',
            'PYTHON_SITEPACKAGES_DIR="/usr/lib/python3.14/site-packages"',
            'BBLAYERS="' + " ".join(str(p) for p in (self.base, self.addon, self.dev_layer)) + '"',
            f'RDEPENDS:{b6.PN}="kwipi-companion"',
        )) + "\n"
        self.dev = 'PN="microduck-image-dev"\nIMAGE_INSTALL="microduck-daemon microduck-data kwipi-companion"\n'
        self.shipping = 'PN="microduck-image"\nIMAGE_INSTALL="microduck-daemon microduck-data"\n'

    def check(self, *, env=None, dev=None, shipping=None, checksum=None):
        return validate_package(
            ROOT, self.base, self.addon, self.dev_layer,
            self.env if env is None else env,
            self.dev if dev is None else dev,
            self.shipping if shipping is None else shipping,
            self.source["archive_sha256"] if checksum is None else checksum)

    def test_01_nominal_fixture_does_not_attest_bitbake(self):
        data = self.check()
        self.assertEqual(PASS, data["status"])
        self.assertEqual(data["addon_modules_packaged"], 5)
        self.assertEqual(data["base_modules_preserved"], 19)
        self.assertTrue(data["package_split_files_verified"])
        for key in ("bitbake_task_execution_attested_by_this_script",
                    "bitbake_do_package_run_attested_by_this_script",
                    "rootfs_installed", "service_installed",
                    "robot_validated", "signed_release", "oem_sensor_validated"):
            self.assertFalse(data[key])
        self.assertEqual(data["motor_commands_issued"], 0)

    def test_02_missing_or_tampered_source_fails(self):
        file = self.target / "passive_fixture_runtime.py"
        file.unlink()
        with self.assertRaises(EnvRefused):
            self.check()
        shutil.copyfile(ROOT / "microduck_companion/passive_fixture_runtime.py", file)
        file.write_bytes(file.read_bytes() + b"\n# tampered")
        with self.assertRaises(EnvRefused):
            self.check()

    def test_03_unapproved_extra_and_duplicate_init_fail(self):
        for name in ("__init__.py", "other.py", "kwipi_seg.rknn", "boot.service", "old.sqlite3", "readme.txt"):
            with self.subTest(name=name):
                path = self.target / name
                path.write_bytes(b"bad")
                with self.assertRaises(EnvRefused):
                    self.check()
                path.unlink()

    def test_04_symlink_and_executable_file_fail(self):
        path = self.target / "passive_resilience.py"
        path.unlink()
        path.symlink_to(ROOT / "microduck_companion/passive_resilience.py")
        with self.assertRaises(EnvRefused):
            self.check()
        path.unlink()
        shutil.copyfile(ROOT / "microduck_companion/passive_resilience.py", path)
        path.chmod(0o755)
        with self.assertRaises(EnvRefused):
            self.check()

    def test_05_unexpected_empty_dir_or_target_symlink_fail(self):
        extra = self.pkgdest / b6.PN / "opt"
        extra.mkdir()
        with self.assertRaises(EnvRefused):
            self.check()
        extra.rmdir()
        bad = self.work / "elsewhere"
        bad.mkdir()
        target = self.target
        shutil.rmtree(target)
        target.symlink_to(bad, target_is_directory=True)
        with self.assertRaises(EnvRefused):
            self.check()

    def test_06_pkgdest_missing_outside_work_or_linked_fail(self):
        real = self.env.replace(f'PKGDEST="{self.pkgdest}"',
                                f'PKGDEST="{self.work / "external"}"')
        with self.assertRaises(EnvRefused):
            self.check(env=real)
        real = self.env.replace(f'PKGDEST="{self.pkgdest}"',
                                f'PKGDEST="{self.tmp / "missing"}"')
        with self.assertRaises(EnvRefused):
            self.check(env=real)
        real = self.env.replace(f'PKGDEST="{self.pkgdest}"',
                                f'PKGDEST="{self.pkgdest / b6.PN}"')
        with self.assertRaises(EnvRefused):
            self.check(env=real)

    def test_07_effective_checksum_wrong_or_missing_fails(self):
        for checksum in ("", "0" * 64, self.source["archive_sha256"] + "\nspoof"):
            with self.subTest(checksum=checksum), self.assertRaises(EnvRefused):
                self.check(checksum=checksum)

    def test_08_wrong_python_version_or_runtime_dependency_fails(self):
        for src, dst in (("/python3.14/", "/python3.13/"),
                         (f'RDEPENDS:{b6.PN}="kwipi-companion"',
                          f'RDEPENDS:{b6.PN}="python3-core"')):
            with self.subTest(src=src), self.assertRaises(EnvRefused):
                self.check(env=self.env.replace(src, dst))

    def test_09_image_inclusion_rejected(self):
        with self.assertRaises(EnvRefused):
            self.check(dev=self.dev.replace("kwipi-companion", "kwipi-companion " + b6.PN))
        with self.assertRaises(EnvRefused):
            self.check(shipping=self.shipping.replace("microduck-data", "microduck-data " + b6.PN))

    def test_10_missing_or_tampered_layer_rejected(self):
        p = self.addon / b6.PROVENANCE
        p.write_bytes(p.read_bytes() + b"tamper")
        with self.assertRaises(b6.Refused):
            self.check()


if __name__ == "__main__":
    unittest.main()
