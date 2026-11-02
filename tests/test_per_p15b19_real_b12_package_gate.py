"""P15-B19: adversarial Linux package-split fixtures; NOT BitBake execution."""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import per_p15b17_oem_receiver_package as b17
from scripts import per_p15b18_dev_receiver_env_gate as b18
from scripts import per_p15b19_real_b12_package_gate as b19
from scripts.per_p13a_bitbake_env_gate import EnvRefused

ROOT = Path(__file__).resolve().parents[1]


class B19SplitGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="p15b19-package-")
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.tmp = self.work / "build/tmp"
        self.pkgdest = self.tmp / "work/all-poky-linux/kwipi-b12-receiver/0.1.0/packages-split"
        self.package = self.pkgdest / b17.PACKAGE
        self.target = self.package / b19.PYDIR
        self.target.mkdir(parents=True)
        self.source = b17.staged_files(ROOT)[1]
        for file in b17.SELECTED:
            path = self.target / Path(file).name
            path.write_bytes((ROOT / file).read_bytes())
            path.chmod(0o644)
        self.metadata = {
            "schema": b18.SCHEMA,
            "status": b18.STATUS,
            "dev_receiver_count": 1,
            "shipping_receiver_count": 0,
            "oem_packages_preserved": True,
            "kwipi_account_isolated_by_effective_metadata": True,
            "receiver_rdepends_checked": True,
            "source_receiver_sha256": self.source["archive_sha256"],
            "receiver_recipe_license": "CLOSED",
            "receiver_recipe_version": b17.VERSION,
        }
        self.recipe = (f'TMPDIR="{self.tmp}"\n'
                       f'PKGDEST="{self.pkgdest}"\n')

    def check(self, *, env=None, receiver=None, metadata=None):
        return b19.inspect_split(
            self.recipe if env is None else env,
            receiver_source=self.source if receiver is None else receiver,
            metadata=self.metadata if metadata is None else metadata)

    def test_01_positive_only_four_files_no_task_claim(self):
        output = self.check()
        self.assertEqual(output["schema"], b19.SCHEMA)
        self.assertEqual(output["status"], b19.PASS)
        self.assertEqual(output["receiver_modules_in_package_split"], 4)
        self.assertEqual(output["historical_python_modules_preserved_in_source"], 24)
        self.assertEqual(set(output["packaged_source_sha256"]), b17.SELECTED)
        self.assertEqual(len(output["packaged_source_sizes"]), 4)
        self.assertTrue(output["main_package_has_only_four_python_sources"])
        self.assertTrue(output["other_splits_contain_no_files"])
        self.assertEqual(output["shipping_receiver_count"], 0)
        for field in (
            "bitbake_do_package_execution_attested_by_gate",
            "rootfs_built", "dev_image_installed", "shipping_image_changed",
            "service_installed", "oem_detector_activated",
            "sensor_verified", "physical_robot_verified",
        ):
            self.assertFalse(output[field], field)
        self.assertEqual(output["motor_commands_issued"], 0)

    def test_02_main_package_missing_module_is_refused(self):
        path = self.target / "b16_oem_readonly_reader.py"
        path.unlink()
        with self.assertRaises(EnvRefused):
            self.check()

    def test_03_main_package_tampered_source_refused(self):
        path = self.target / "b14_host_identity_gate.py"
        path.write_bytes(path.read_bytes() + b"\n# mismatch\n")
        with self.assertRaises(EnvRefused):
            self.check()

    def test_04_unexpected_payload_or_hidden_file_refused(self):
        for extra in ("__init__.py", "boot.service", "camera.rknn",
                      "experience.sqlite", "identity.json", ".hidden"):
            p = self.target / extra
            p.write_bytes(b"extra")
            with self.subTest(extra=extra), self.assertRaises(EnvRefused):
                self.check()
            p.unlink()

    def test_05_symlink_or_wrong_mode_refused(self):
        p = self.target / "b12_local_wire_contract.py"
        p.unlink()
        p.symlink_to(ROOT / "microduck_companion/b12_local_wire_contract.py")
        with self.assertRaises(EnvRefused):
            self.check()
        p.unlink()
        p.write_bytes((ROOT / "microduck_companion/b12_local_wire_contract.py").read_bytes())
        for mode in (0o755, 0o600, 0o444):
            p.chmod(mode)
            with self.subTest(mode=mode), self.assertRaises(EnvRefused):
                self.check()

    def test_06_extra_empty_directory_and_package_symlink_refused(self):
        foreign = self.package / "opt"
        foreign.mkdir()
        with self.assertRaises(EnvRefused):
            self.check()
        foreign.rmdir()
        outside = self.work / "source"
        outside.mkdir()
        shutil.rmtree(self.target)
        self.target.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(EnvRefused):
            self.check()

    def test_07_pkgdest_missing_outside_tmpdir_or_linked_refused(self):
        other = self.work / "outside"
        other.mkdir()
        for replacement in (other, self.tmp / "missing", self.package,
                            self.work):
            env = self.recipe.replace(str(self.pkgdest), str(replacement))
            with self.subTest(replacement=replacement), self.assertRaises(EnvRefused):
                self.check(env=env)
        linked = self.work / "pkgdest-link"
        linked.symlink_to(self.pkgdest, target_is_directory=True)
        with self.assertRaises(EnvRefused):
            self.check(env=self.recipe.replace(str(self.pkgdest), str(linked)))

    def test_08_absent_duplicate_or_invalid_env_variables_refused(self):
        for bad in (
            self.recipe.replace("PKGDEST=", "TYPO="),
            self.recipe.replace("TMPDIR=", "TYPO="),
            self.recipe + f'PKGDEST="{self.pkgdest}"\n',
            self.recipe.replace(str(self.tmp), "/tmp/other-tmp"),
        ):
            with self.subTest(bad=bad[:80]), self.assertRaises(EnvRefused):
                self.check(env=bad)

    def test_09_other_split_must_not_hide_source_or_service(self):
        other = self.pkgdest / (b17.PACKAGE + "-dbg")
        other.mkdir()
        self.check()  # empty split allowed by BitBake
        item = other / "systemd.service"
        item.write_bytes(b"unexpected")
        with self.assertRaises(EnvRefused):
            self.check()
        item.unlink()
        symlink = other / "linked"
        symlink.symlink_to(self.target, target_is_directory=True)
        with self.assertRaises(EnvRefused):
            self.check()

    def test_10_bad_source_provenance_refused(self):
        for key, value in (
            ("new_modules", 5), ("new_sha256", {}),
            ("historical_python_modules", 23), ("oem_producer_enabled", True),
            ("license_redistribution_approved", True),
            ("archive_sha256", "0" * 64),
        ):
            other = {**self.source, key: value}
            with self.subTest(key=key), self.assertRaises(EnvRefused):
                self.check(receiver=other)

    def test_11_bad_b18_metadata_refused(self):
        for key, value in (
            ("schema", "untrusted"), ("dev_receiver_count", 2),
            ("shipping_receiver_count", 1),
            ("oem_packages_preserved", False),
            ("kwipi_account_isolated_by_effective_metadata", False),
            ("receiver_rdepends_checked", False),
            ("source_receiver_sha256", "0" * 64),
            ("receiver_recipe_license", "MIT"),
        ):
            corrupted = {**self.metadata, key: value}
            with self.subTest(key=key), self.assertRaises(EnvRefused):
                self.check(metadata=corrupted)

    def test_12_actual_B18_composition_is_required_not_bypassed(self):
        # Dedicated B18 fixtures independently verify both success/failure
        # for real source closures and DEV/shipping -e. Here the composition
        # contract is asserted; this is NOT a claim of actual BitBake work.
        with patch.object(b19.b18, "source_gate", return_value=(
                {"schema": "fixture"}, {"schema": "fixture"}, self.source)) as source, \
             patch.object(b19.b18, "validate", return_value=self.metadata) as metadata:
            result = b19.validate_package(
                ROOT, selection_layer=self.work / "sel",
                b10_selection=self.work / "b10",
                receiver_layer=self.work / "b17",
                addon_layer=self.work / "addon",
                dev_layer=self.work / "dev",
                python_layer=self.work / "base",
                account_layer=self.work / "acct",
                recipe_env=self.recipe,
                dev_env='PN="microduck-image-dev"\n',
                shipping_env='PN="microduck-image"\n',
                appends="fixture",
                checksum=self.source["archive_sha256"],
            )
        self.assertEqual(result["status"], b19.PASS)
        source.assert_called_once()
        metadata.assert_called_once()


if __name__ == "__main__":
    unittest.main()
