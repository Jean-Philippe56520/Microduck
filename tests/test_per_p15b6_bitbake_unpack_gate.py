"""P15-B6-M: synthetic adversarial metadata/unpack tests, NOT real BitBake."""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6
from scripts.per_p13a_bitbake_env_gate import EnvRefused
from scripts.per_p15b6_bitbake_unpack_gate import (
    PASS, validate_metadata, validate_unpack,
)

ROOT = Path(__file__).resolve().parents[1]


class B6MUnpackGateTests(unittest.TestCase):
    def setUp(self):
        self.context = tempfile.TemporaryDirectory(prefix="p15b6m-")
        self.addCleanup(self.context.cleanup)
        self.work = Path(self.context.name)
        self.base = self.work / p14b.LAYER
        self.addon = self.work / b6.LAYER
        self.dev_layer = ROOT / "yocto/meta-kwipi-dev-image"
        self.base_provenance = p14b.stage(ROOT, self.base)
        self.addon_provenance = b6.stage(ROOT, self.addon)
        self.tmp = self.work / "bitbake" / "tmp"
        self.unpack = self.tmp / "work" / "sources"
        self.source = self.unpack / (b6.PN + "-" + b6.PV)
        self.pkg = self.source / "microduck_companion"
        self.pkg.mkdir(parents=True)
        for rel in sorted(b6.ADDON):
            shutil.copyfile(ROOT / rel, self.pkg / Path(rel).name)
        self.env = "\n".join((
            f'PN="{b6.PN}"',
            f'PV="{b6.PV}"',
            'LICENSE="CLOSED"',
            'PACKAGE_ARCH="all"',
            f'SRC_URI="file://{b6.SRC_NAME};subdir={b6.PN}-{b6.PV};name=p15b6"',
            f'S="{self.source}"',
            f'BP="{b6.PN}-{b6.PV}"',
            f'UNPACKDIR="{self.unpack}"',
            f'TMPDIR="{self.tmp}"',
            'PYTHON_SITEPACKAGES_DIR="/usr/lib/python3.14/site-packages"',
            'BBLAYERS="' + " ".join(str(x) for x in (
                self.base, self.addon, self.dev_layer)) + '"',
            f'RDEPENDS:{b6.PN}="kwipi-companion"',
        )) + "\n"
        self.dev = (
            'PN="microduck-image-dev"\n'
            'IMAGE_INSTALL="microduck-daemon microduck-data kwipi-companion"\n'
        )
        self.shipping = (
            'PN="microduck-image"\n'
            'IMAGE_INSTALL="microduck-daemon microduck-data"\n'
        )

    def check(self, recipe=None, dev=None, shipping=None, checksum=None):
        return validate_unpack(
            ROOT, self.base, self.addon, self.dev_layer,
            self.env if recipe is None else recipe,
            self.dev if dev is None else dev,
            self.shipping if shipping is None else shipping,
            self.addon_provenance["archive_sha256"] if checksum is None else checksum)

    def test_01_nominal_fixture_explicitly_not_bitbake_proof(self):
        report = self.check()
        self.assertEqual(PASS, report["status"])
        self.assertEqual((19, 5), (
            report["base_python_modules_unchanged"],
            report["addon_python_modules_unpacked"]))
        self.assertTrue(report["unpacked_source_bytes_verified"])
        for key in ("bitbake_task_execution_attested_by_this_script",
                    "bitbake_do_install_run", "bitbake_do_package_run",
                    "rootfs_installed", "service_installed",
                    "real_oem_observation", "signed_release",
                    "physical_robot_verified"):
            self.assertFalse(report[key])
        self.assertEqual(0, report["motor_commands_issued"])

    def test_02_wrong_identity_version_license_arch_refused(self):
        for before, after in (
            (f'PN="{b6.PN}"', 'PN="robotd"'),
            (f'PV="{b6.PV}"', 'PV="0.2.0"'),
            ('LICENSE="CLOSED"', 'LICENSE="MIT"'),
            ('PACKAGE_ARCH="all"', 'PACKAGE_ARCH="aarch64"'),
        ):
            with self.subTest(before=before), self.assertRaises(EnvRefused):
                self.check(recipe=self.env.replace(before, after))

    def test_03_uri_digest_or_base_package_refused(self):
        for before, after in (
            (f'name=p15b6"', 'name=evil"'),
            (f'name=p15b6"', 'name=p15b6 file://other.tar.gz"'),
            (f'BP="{b6.PN}-{b6.PV}"', 'BP="injected"'),
        ):
            with self.subTest(before=before), self.assertRaises(EnvRefused):
                self.check(recipe=self.env.replace(before, after))

    def test_04_missing_layer_base_dep_or_wrong_target_python_refused(self):
        for before, after in (
            (str(self.addon), str(self.work / "other-layer")),
            (f'RDEPENDS:{b6.PN}="kwipi-companion"',
             f'RDEPENDS:{b6.PN}="python3-core"'),
            ("/python3.14/", "/python3.13/"),
        ):
            with self.subTest(before=before), self.assertRaises(EnvRefused):
                self.check(recipe=self.env.replace(before, after))

    def test_05_dev_or_shipping_selection_refused(self):
        with self.assertRaises(EnvRefused):
            self.check(dev=self.dev.replace("kwipi-companion",
                                            "kwipi-companion kwipi-passive-fixture"))
        with self.assertRaises(EnvRefused):
            self.check(shipping=self.shipping.replace("microduck-data",
                                                      "microduck-data kwipi-passive-fixture"))
        with self.assertRaises(EnvRefused):
            self.check(shipping=self.shipping.replace("microduck-data",
                                                      "microduck-data kwipi-companion"))
        with self.assertRaises(EnvRefused):
            self.check(dev=self.dev.replace(" kwipi-companion", ""))

    def test_06_missing_added_or_tampered_unpacked_source_refused(self):
        missing = self.pkg / "passive_fixture_runtime.py"
        missing.unlink()
        with self.assertRaises(EnvRefused):
            self.check()
        shutil.copyfile(ROOT / "microduck_companion/passive_fixture_runtime.py", missing)
        (self.pkg / "second.sqlite3").write_bytes(b"not allowed")
        with self.assertRaises(EnvRefused):
            self.check()
        (self.pkg / "second.sqlite3").unlink()
        missing.write_bytes(missing.read_bytes() + b"\n# modified")
        with self.assertRaises(EnvRefused):
            self.check()

    def test_07_unpack_symlink_refused(self):
        p = self.pkg / "passive_fixture_runtime.py"
        p.unlink()
        p.symlink_to(ROOT / "microduck_companion/passive_fixture_runtime.py")
        with self.assertRaises(EnvRefused):
            self.check()

    def test_08_unpack_outside_tmpdir_refused(self):
        with self.assertRaises(EnvRefused):
            self.check(recipe=self.env.replace(
                f'TMPDIR="{self.tmp}"', f'TMPDIR="{self.work / "unrelated"}"'))
        with self.assertRaises(EnvRefused):
            self.check(recipe=self.env.replace(
                f'S="{self.source}"', f'S="{self.work}"'))

    def test_09_duplicate_env_var_or_missing_image_refused(self):
        with self.assertRaises(EnvRefused):
            self.check(recipe=self.env + 'PV="0.1.0"\n')
        with self.assertRaises(EnvRefused):
            self.check(shipping="PN=\"microduck-image\"\n")

    def test_10_recipe_source_tamper_refused(self):
        recipe_file = self.addon / b6.RECIPE
        recipe_file.write_bytes(recipe_file.read_bytes() + b"\n# rogue")
        with self.assertRaises(b6.Refused):
            self.check()

    def test_11_image_gate_is_independent_from_unpacked_files(self):
        self.pkg.joinpath("passive_fixture_runtime.py").unlink()
        result = validate_metadata(
            self.env, self.dev, self.shipping,
            base_layer=self.base, addon_layer=self.addon,
            dev_layer=self.dev_layer,
            digest=self.addon_provenance["archive_sha256"],
            checksum=self.addon_provenance["archive_sha256"])
        self.assertEqual(result["PN"], b6.PN)

    def test_12_missing_wrong_multiline_checksum_flag_refused(self):
        digest = self.addon_provenance["archive_sha256"]
        for bad in ("", "0" * 64, digest + "extra", digest + "\nother"):
            with self.subTest(bad=bad), self.assertRaises(EnvRefused):
                self.check(checksum=bad)

    def test_13_source_env_text_does_not_spoof_effective_checksum(self):
        digest = self.addon_provenance["archive_sha256"]
        fake_env = self.env + f'SRC_URI[p15b6.sha256sum]="{digest}"\n'
        with self.assertRaises(EnvRefused):
            self.check(recipe=fake_env, checksum="0" * 64)


if __name__ == "__main__":
    unittest.main()
