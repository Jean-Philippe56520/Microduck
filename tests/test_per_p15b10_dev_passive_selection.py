"""P15-B10: DEV-only passive package metadata and negative security gates.

All effective BitBake environments here are synthetic; the real -e check is CI.
No BitBake task, rootfs, service or OEM socket is touched.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6
from scripts import per_p15b10_dev_passive_env_gate as b10
from scripts.per_p13a_bitbake_env_gate import EnvRefused

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = ROOT / "yocto/meta-kwipi-p15-account"
DEV = ROOT / "yocto/meta-kwipi-dev-image"
SELECTED = ROOT / b10.LAYER_REL
OPERATOR = (
    "useradd -m -s /bin/bash -G "
    "robot,sudo,audio,video,dialout,i2c,plugdev,input "
    "-p '$6$synthetic_not_a_hash' microduck;"
)
KWIPI = " groupadd -r kwipi; useradd -r -g kwipi -M -s /sbin/nologin -p '!' kwipi;"


class P15B10GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="p15b10-fixture-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.base = self.work / "meta-kwipi-python"
        self.addon = self.work / b6.LAYER
        self.selection = self.work / "selection"
        shutil.copytree(SELECTED, self.selection)
        self.base_proof = {
            "selected_python_modules": 19,
            "license_recipe_closed": True,
            "source_sha256": {"microduck_companion/test.py": "a" * 64},
        }
        self.addon_proof = {
            "schema": b6.SCHEMA,
            "status": "host_addon_source_candidate_not_bitbake",
            "addon_modules": 5, "base_modules": 19,
            "base_sha256": dict(self.base_proof["source_sha256"]),
            "dev_image_selected": False,
            "shipping_image_selected": False,
            "systemd_installed": False,
            "robot_validated": False,
        }

    def env(self, image, *, passive=None, base=None, extra="", identity=None,
            features=""):
        if passive is None:
            passive = 1 if image == "microduck-image-dev" else 0
        if base is None:
            base = 1 if image == "microduck-image-dev" else 0
        packages = ["microduck-daemon", "microduck-data"]
        packages += ["kwipi-companion"] * base + [b10.PACKAGE] * passive
        if extra:
            packages += extra.split()
        layers = [self.base, DEV, ACCOUNT, self.addon, self.selection]
        return (
            f'PN="{image}"\n'
            f'IMAGE_INSTALL="{" ".join(packages)}"\n'
            f'IMAGE_FEATURES="{features}"\n'
            f'BBLAYERS="{" ".join(map(str, layers))}"\n'
            f'EXTRA_USERS_PARAMS="{OPERATOR + (KWIPI if image.endswith("-dev") else "") if identity is None else identity}"\n'
        )

    def appends(self):
        return (
            "microduck-image-dev.bb:\n"
            f"  {DEV / 'recipes-core/images/microduck-image-dev.bbappend'}\n"
            f"  {ACCOUNT / 'recipes-core/images/microduck-image-dev.bbappend'}\n"
            f"  {self.selection / b10.APPEND}\n"
        )

    def check(self, *, dev=None, shipping=None, appends=None, base_proof=None,
              addon_proof=None):
        return b10.validate(
            dev if dev is not None else self.env("microduck-image-dev"),
            shipping if shipping is not None else self.env("microduck-image"),
            appends if appends is not None else self.appends(),
            selection_layer=self.selection, addon_layer=self.addon,
            dev_layer=DEV, python_layer=self.base,
            account_layer=ACCOUNT,
            base_provenance=self.base_proof if base_proof is None else base_proof,
            addon_provenance=self.addon_proof if addon_proof is None else addon_proof,
        )

    def test_01_nominal_mock_env_never_claims_image_or_robot(self):
        result = self.check()
        self.assertEqual("dev_only_passive_selection_effective_metadata_verified",
                         result["status"])
        self.assertEqual((1, 1, 0, 0),
                         tuple(result[k] for k in (
                             "dev_base_package_count", "dev_passive_package_count",
                             "shipping_base_package_count",
                             "shipping_passive_package_count")))
        self.assertEqual((19, 5), (result["base_modules"], result["addon_modules"]))
        self.assertTrue(result["oem_packages_preserved"])
        self.assertEqual(0, result["motor_commands_issued"])
        for key in ("bitbake_executed_by_gate", "rootfs_built_by_gate",
                    "package_installed_in_new_rootfs", "systemd_service_activated",
                    "oem_socket_acl_verified", "robot_validated"):
            self.assertFalse(result[key], key)

    def test_02_dev_passive_missing_or_duplicate_stops(self):
        for count in (0, 2):
            with self.subTest(count=count), self.assertRaises(EnvRefused):
                self.check(dev=self.env("microduck-image-dev", passive=count))

    def test_03_shipping_passive_leak_stops(self):
        with self.assertRaises(EnvRefused):
            self.check(shipping=self.env("microduck-image", passive=1))

    def test_04_dev_baseline_missing_or_duplicated_stops(self):
        for count in (0, 2):
            with self.subTest(count=count), self.assertRaises(EnvRefused):
                self.check(dev=self.env("microduck-image-dev", base=count))

    def test_05_oem_package_and_shipping_security_guard(self):
        for shipment in (
            self.env("microduck-image", extra="kwipi-companion"),
            self.env("microduck-image", features="allow-root-login"),
        ):
            with self.subTest(shipment=shipment[-90:]), self.assertRaises(EnvRefused):
                self.check(shipping=shipment)
        bad_oem = self.env("microduck-image-dev").replace(
            "microduck-daemon", "not-the-oem-daemon")
        with self.assertRaises(EnvRefused):
            self.check(dev=bad_oem)

    def test_06_missing_bblayers_or_wrong_recipe_stops(self):
        env = self.env("microduck-image-dev")
        for variant in (
            env.replace(str(self.selection), "/tmp/unrelated-layer"),
            env.replace(str(self.addon), "/tmp/unrelated-source"),
            env.replace('PN="microduck-image-dev"', 'PN="microduck-image"'),
        ):
            with self.subTest(variant=variant[-130:]), self.assertRaises(EnvRefused):
                self.check(dev=variant)

    def test_07_false_duplicate_shipping_or_missing_bitbake_append_stops(self):
        exact = str(self.selection / b10.APPEND)
        for bad in (
            self.appends().replace(exact, "/tmp/unrelated.bbappend"),
            self.appends() + "  " + exact + "\n",
            "microduck-image.bb:\n  " + exact + "\n",
            self.appends().replace(
                "microduck-image-dev.bb:", "microduck-image.bb:"),
            self.appends() +
            f"microduck-image.bb:\\n  {self.selection / b10.APPEND}\\n",
            self.appends() +
            f"unrelated.bb:\\n  {self.selection / b10.APPEND}\\n",
        ):
            with self.subTest(case=bad[-100:]), self.assertRaises(EnvRefused):
                self.check(appends=bad)

    def test_08_identity_change_stops_even_if_packages_selected(self):
        for value in (
            OPERATOR,
            OPERATOR + " groupadd -r kwipi; useradd -G robot -r kwipi;",
            OPERATOR + KWIPI + " usermod -aG robot kwipi;",
        ):
            with self.subTest(identity=value[-85:]), self.assertRaises(EnvRefused):
                self.check(dev=self.env("microduck-image-dev", identity=value))

    def test_09_addon_provenance_must_be_original_unselected(self):
        variants = [
            {**self.addon_proof, "base_sha256": {}},
            {**self.addon_proof, "dev_image_selected": True},
            {**self.addon_proof, "shipping_image_selected": True},
            {**self.addon_proof, "systemd_installed": True},
            {**self.addon_proof, "robot_validated": True},
            {**self.addon_proof, "addon_modules": 6},
            {**self.addon_proof, "status": "fake_pass"},
        ]
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(EnvRefused):
                self.check(addon_proof=variant)

    def test_10_layer_is_only_two_exact_files_and_dev_recipe(self):
        self.assertEqual(
            {b10.CONF, b10.APPEND},
            {p.relative_to(SELECTED).as_posix()
             for p in SELECTED.rglob("*") if p.is_file()})
        self.assertEqual(
            (SELECTED / b10.CONF).read_text(), b10.LAYER_CONF)
        self.assertEqual(
            (SELECTED / b10.APPEND).read_text(), b10.IMAGE_APPEND)
        self.assertFalse((SELECTED / "recipes-core/images/microduck-image.bbappend").exists())

    def test_11_source_gate_checks_real_closed_19_plus_5_layers(self):
        p14b.stage(ROOT, self.base)
        b6.stage(ROOT, self.addon)
        base, addon = b10.source_gate(
            ROOT, selection_layer=self.selection,
            addon_layer=self.addon, python_layer=self.base,
        )
        self.assertEqual((19, 5),
                         (base["selected_python_modules"], addon["addon_modules"]))
        self.assertEqual(base["source_sha256"], addon["base_sha256"])
        self.assertEqual("host_addon_source_candidate_not_bitbake", addon["status"])

    def test_12_unreviewed_selection_source_change_stops(self):
        for modification in ("extra", "changed", "shipping", "symlink"):
            with self.subTest(modification=modification):
                dst = self.work / ("bad-" + modification)
                shutil.copytree(SELECTED, dst)
                if modification == "extra":
                    (dst / "unexpected.txt").write_text("bad")
                if modification == "changed":
                    (dst / b10.APPEND).write_text(
                        'IMAGE_INSTALL:append = " kwipi-passive-fixture robotctl"\n')
                if modification == "shipping":
                    p = dst / "recipes-core/images/microduck-image.bbappend"
                    p.write_text('IMAGE_INSTALL:append = " kwipi-passive-fixture"\n')
                if modification == "symlink":
                    p = dst / b10.APPEND
                    p.unlink()
                    p.symlink_to(SELECTED / b10.APPEND)
                with self.assertRaises(EnvRefused):
                    b10.source_gate(ROOT, selection_layer=dst,
                                    addon_layer=self.addon, python_layer=self.base)

    def test_13_source_gate_refuses_modified_addon_package(self):
        p14b.stage(ROOT, self.base)
        b6.stage(ROOT, self.addon)
        p = self.addon / b6.RECIPE
        p.write_bytes(p.read_bytes() + b"\n# unexpected change\n")
        with self.assertRaises(b6.Refused):
            b10.source_gate(ROOT, selection_layer=self.selection,
                            addon_layer=self.addon, python_layer=self.base)

    def test_14_private_bitbake_env_and_symlink_fail_closed(self):
        private = self.work / "private-env.txt"
        private.write_text('PN="microduck-image-dev"\n')
        private.chmod(0o600)
        self.assertIn("microduck-image-dev", b10._private_env(private))
        private.chmod(0o644)
        with self.assertRaises(EnvRefused):
            b10._private_env(private)
        private.chmod(0o600)
        linked = self.work / "linked-env.txt"
        linked.symlink_to(private)
        with self.assertRaises(EnvRefused):
            b10._private_env(linked)


if __name__ == "__main__":
    unittest.main()
