"""P14C: dev-image inclusion and production-exclusion tests (not a rootfs test)."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.per_p13a_bitbake_env_gate import EnvRefused
from scripts.per_p14c_dev_image_env_gate import (
    DEV_APPEND, EXPECTED_APPEND, EXPECTED_LAYER_CONF, LAYER_CONF,
    SCHEMA, source_gate, validate,
)

ROOT = Path(__file__).resolve().parents[1]
DEV_LAYER = ROOT / "yocto/meta-kwipi-dev-image"
PROVENANCE = {
    "selected_python_modules": 19,
    "source_license_checked": False,
    "license_recipe_closed": True,
}


class DevImageOnlyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.py_layer = Path(self.tmp.name) / "meta-kwipi-python"
        self.py_layer.mkdir()
        self.appends = f"/oem/microduck-image-dev.bb:\n  {DEV_LAYER / DEV_APPEND}\n"

    def env(self, image: str, packages: str, *, features: str = "") -> str:
        return "\n".join((
            f'PN="{image}"',
            f'IMAGE_INSTALL="{packages}"',
            f'BBLAYERS="{DEV_LAYER} {self.py_layer}"',
            f'IMAGE_FEATURES="{features}"',
        )) + "\n"

    def check(self, dev=None, ship=None, appends=None, provenance=None):
        dev = dev if dev is not None else self.env(
            "microduck-image-dev", "microduck-daemon microduck-data kwipi-companion")
        ship = ship if ship is not None else self.env(
            "microduck-image", "microduck-daemon microduck-data")
        return validate(dev, ship,
                        self.appends if appends is None else appends,
                        dev_layer=DEV_LAYER, py_layer=self.py_layer,
                        provenance=PROVENANCE if provenance is None else provenance)

    def test_repo_dev_layer_exact_and_only_two_files(self):
        self.assertEqual((DEV_LAYER / DEV_APPEND).read_text(), EXPECTED_APPEND)
        self.assertEqual((DEV_LAYER / LAYER_CONF).read_text(), EXPECTED_LAYER_CONF)
        self.assertEqual({
            path.relative_to(DEV_LAYER).as_posix()
            for path in DEV_LAYER.rglob("*") if path.is_file()
        }, {DEV_APPEND, LAYER_CONF})

    def test_nominal_fixture_is_not_rootfs_proof(self):
        report = self.check()
        self.assertEqual(report["schema"], SCHEMA)
        self.assertEqual(report["dev_image_package_count"], 1)
        self.assertEqual(report["shipping_image_package_count"], 0)
        self.assertFalse(report["packaged_in_rootfs"])
        self.assertFalse(report["robot_validated"])

    def test_prod_package_is_fatal(self):
        with self.assertRaises(EnvRefused):
            self.check(ship=self.env(
                "microduck-image", "microduck-daemon microduck-data kwipi-companion"))

    def test_dev_missing_package_is_fatal(self):
        with self.assertRaises(EnvRefused):
            self.check(dev=self.env("microduck-image-dev", "microduck-daemon microduck-data"))

    def test_dev_package_selected_twice_is_fatal(self):
        with self.assertRaises(EnvRefused):
            self.check(dev=self.env(
                "microduck-image-dev",
                "microduck-daemon microduck-data kwipi-companion kwipi-companion"))

    def test_loss_of_original_oem_data_is_fatal(self):
        with self.assertRaises(EnvRefused):
            self.check(ship=self.env("microduck-image", "microduck-daemon"))

    def test_unreviewed_root_login_on_prod_is_fatal(self):
        with self.assertRaises(EnvRefused):
            self.check(ship=self.env(
                "microduck-image", "microduck-daemon microduck-data",
                features="ssh-server-openssh allow-root-login"))

    def test_unrecognized_dev_bbappend_is_fatal(self):
        with self.assertRaises(EnvRefused):
            self.check(appends="microduck-image-dev.bb: unrelated-package\n")

    def test_python_package_source_not_reviewed_is_fatal(self):
        for value in ({}, {"selected_python_modules": 20, "license_recipe_closed": True},
                      {"selected_python_modules": 19, "license_recipe_closed": False}):
            with self.subTest(value=value), self.assertRaises(EnvRefused):
                self.check(provenance=value)

    def test_wrong_image_or_layer_is_fatal(self):
        with self.assertRaises(EnvRefused):
            self.check(dev=self.env("microduck-image", "microduck-daemon microduck-data"))
        invalid = self.env("microduck-image-dev",
                           "microduck-daemon microduck-data kwipi-companion")
        invalid = invalid.replace(str(DEV_LAYER), "/tmp/not-a-real-dev-layer")
        with self.assertRaises(EnvRefused):
            self.check(dev=invalid)

    def test_source_gate_denies_modified_official_image_blobs(self):
        with patch("scripts.per_p14c_dev_image_env_gate._git",
                   side_effect=["untrusted-y-commit"]):
            with self.assertRaises(EnvRefused):
                source_gate(Path(self.tmp.name), DEV_LAYER,
                            self.py_layer, ROOT)


if __name__ == "__main__":
    unittest.main()
