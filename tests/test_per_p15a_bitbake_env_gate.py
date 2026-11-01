"""PER-P15A-M: source fingerprints and adversarial BitBake -e fixtures.

All environments here are synthetic; the separate CI job runs real kas/BitBake.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.per_p13a_bitbake_env_gate import EnvRefused
from scripts.per_p14c_dev_image_env_gate import DEV_APPEND as P14C_APPEND
from scripts.per_p15a_bitbake_env_gate import (
    DEV_APPEND, EXPECTED_RDEPENDS, RECIPE, SCHEMA, REVIEWED_BLOBS,
    validate, verify_source,
)

ROOT = Path(__file__).resolve().parents[1]
P15 = ROOT / "yocto/meta-kwipi-p15-readonly"
P14C = ROOT / "yocto/meta-kwipi-dev-image"
PROVENANCE = {
    "selected_python_modules": 19,
    "license_recipe_closed": True,
    "source_license_checked": False,
}


class P15AMetadataGateTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.py_layer = Path(tmp.name) / "meta-kwipi-python"
        self.py_layer.mkdir()
        self.layers = " ".join(map(str, (self.py_layer, P14C, P15)))
        self.appends = (
            "/official/microduck-image-dev.bb:\n"
            f"  {P14C / P14C_APPEND}\n"
            f"  {P15 / DEV_APPEND}\n"
        )
        self.recipe_env = self.recipe()
        self.dev_env = self.image("microduck-image-dev",
                                  "microduck-daemon microduck-data kwipi-companion kwipi-readonly-probe")
        self.ship_env = self.image("microduck-image",
                                   "microduck-daemon microduck-data")

    def recipe(self):
        return "\n".join((
            'PN="kwipi-readonly-probe"',
            'PV="0.1"',
            'LICENSE="CLOSED"',
            f'FILE="{P15 / RECIPE}"',
            'UNPACKDIR="/tmp/real-unpack"',
            'S="/tmp/real-unpack"',
            'SRC_URI="file://health_probe.py file://kwipi-readonly-probe.service"',
            'SYSTEMD_SERVICE:kwipi-readonly-probe="kwipi-readonly-probe.service"',
            'SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe="disable"',
            'SYSTEMD_PACKAGES="kwipi-readonly-probe"',
            'RDEPENDS:kwipi-readonly-probe="kwipi-companion python3-core python3-json"',
        )) + "\n"

    def image(self, image, installed, features=""):
        return "\n".join((
            f'PN="{image}"',
            f'IMAGE_INSTALL="{installed}"',
            f'BBLAYERS="{self.layers}"',
            f'IMAGE_FEATURES="{features}"',
        )) + "\n"

    def check(self, *, recipe=None, dev=None, ship=None, appends=None):
        return validate(
            self.recipe_env if recipe is None else recipe,
            self.dev_env if dev is None else dev,
            self.ship_env if ship is None else ship,
            self.appends if appends is None else appends,
            p15_layer=P15, dev_layer=P14C, py_layer=self.py_layer,
            provenance=PROVENANCE,
        )

    def test_positive_reviewed_bytes_and_metadata_only(self):
        self.assertEqual(set(REVIEWED_BLOBS), {
            p.relative_to(P15).as_posix()
            for p in P15.rglob("*") if p.is_file() or p.is_symlink()
        })
        self.assertTrue(verify_source(P15)["reviewed_source_unchanged"])
        self.assertEqual(EXPECTED_RDEPENDS,
                         {"kwipi-companion", "python3-core", "python3-json"})
        result = self.check()
        self.assertEqual(result["schema"], SCHEMA)
        self.assertEqual(result["status"],
                         "real_bitbake_p15a_metadata_dev_only_verified")
        self.assertEqual(result["p15a_dev_count"], 1)
        self.assertEqual(result["p15a_shipping_count"], 0)
        self.assertEqual(result["systemd_auto_enable"], "disable")
        for key in ("bitbake_package_run", "rootfs_built", "service_installed",
                    "signed_release", "robot_validated"):
            self.assertFalse(result[key])
        self.assertEqual(result["motor_commands_issued"], 0)

    def test_unexpected_source_and_symlink_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_layer = Path(tmp) / "layer"
            shutil.copytree(P15, temp_layer)
            self.assertTrue(verify_source(temp_layer)["reviewed_source_unchanged"])
            p = temp_layer / RECIPE
            p.write_text(p.read_text() + "\n# unauthorized\n")
            with self.assertRaises(EnvRefused):
                verify_source(temp_layer)
            p.write_bytes((P15 / RECIPE).read_bytes())
            (temp_layer / "unreviewed.service").write_text("bad")
            with self.assertRaises(EnvRefused):
                verify_source(temp_layer)
            (temp_layer / "unreviewed.service").unlink()
            q = temp_layer / "recipes-kwipi/kwipi-readonly-probe/files/health_probe.py"
            q.unlink()
            q.symlink_to(P15 / q.relative_to(temp_layer))
            with self.assertRaises(EnvRefused):
                verify_source(temp_layer)

    def test_auto_start_is_refused(self):
        with self.assertRaises(EnvRefused):
            self.check(recipe=self.recipe_env.replace(
                'SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe="disable"',
                'SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe="enable"'))

    def test_wrong_systemd_unit_or_recipe_is_refused(self):
        for old, new in (
            ('kwipi-readonly-probe.service"', 'robotd.service"'),
            (f'FILE="{P15 / RECIPE}"', 'FILE="/tmp/fake-package.bb"'),
            ('PV="0.1"', 'PV="0.2"'),
            ('LICENSE="CLOSED"', 'LICENSE="Apache-2.0"'),
            ('S="/tmp/real-unpack"', 'S="/tmp/other"'),
        ):
            with self.subTest(old=old), self.assertRaises(EnvRefused):
                self.check(recipe=self.recipe_env.replace(old, new))

    def test_unreviewed_sources_and_dependency_floor_are_refused(self):
        for old, new in (
            ('file://health_probe.py file://kwipi-readonly-probe.service',
             'file://health_probe.py file://unreviewed.service'),
            ('kwipi-companion python3-core python3-json',
             'python3-core python3-json'),
            ('SYSTEMD_PACKAGES="kwipi-readonly-probe"',
             'SYSTEMD_PACKAGES=""'),
        ):
            with self.subTest(old=old), self.assertRaises(EnvRefused):
                self.check(recipe=self.recipe_env.replace(old, new))

    def test_shipping_p15_or_missing_dev_or_duplicates_are_refused(self):
        with self.assertRaises(EnvRefused):
            self.check(ship=self.ship_env.replace(
                'microduck-data"', 'microduck-data kwipi-readonly-probe"'))
        with self.assertRaises(EnvRefused):
            self.check(dev=self.dev_env.replace(
                ' kwipi-readonly-probe', ''))
        with self.assertRaises(EnvRefused):
            self.check(dev=self.dev_env.replace(
                ' kwipi-readonly-probe', ' kwipi-readonly-probe kwipi-readonly-probe'))
        with self.assertRaises(EnvRefused):
            self.check(dev=self.dev_env.replace(
                ' kwipi-companion', ''))

    def test_missing_p15_layer_or_unrecognized_append_refused(self):
        with self.assertRaises(EnvRefused):
            self.check(dev=self.dev_env.replace(str(P15), "/tmp/other"))
        with self.assertRaises(EnvRefused):
            self.check(appends=self.appends.replace(
                str(P15 / DEV_APPEND), "/elsewhere/unknown.bbappend"))

    def test_original_oem_daemon_and_production_security_preserved(self):
        with self.assertRaises(EnvRefused):
            self.check(dev=self.dev_env.replace("microduck-daemon ", ""))
        with self.assertRaises(EnvRefused):
            self.check(ship=self.image(
                "microduck-image", "microduck-daemon microduck-data",
                features="allow-root-login"))


if __name__ == "__main__":
    unittest.main()
