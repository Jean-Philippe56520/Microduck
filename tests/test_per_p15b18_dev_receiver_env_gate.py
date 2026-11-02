"""P15-B18: synthetic DEV/shipping metadata, plus exact real source closure.

No BitBake or robot is run in these tests. CI has a separate real -p/-e step.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6
from scripts import per_p15b10_dev_passive_env_gate as b10
from scripts import per_p15b17_oem_receiver_package as b17
from scripts import per_p15b18_dev_receiver_env_gate as b18
from scripts.per_p13a_bitbake_env_gate import EnvRefused

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = ROOT / "yocto/meta-kwipi-p15-account"
DEV = ROOT / "yocto/meta-kwipi-dev-image"
B10 = ROOT / b10.LAYER_REL
B18 = ROOT / b18.LAYER_REL
OEM_OPERATOR = (
    "useradd -m -s /bin/bash -G "
    "robot,sudo,audio,video,dialout,i2c,plugdev,input "
    "-p '$6$synthetic_not_a_hash' microduck;"
)
KWIPI = " groupadd -r kwipi; useradd -r -g kwipi -M -s /sbin/nologin -p '!' kwipi;"


class P15B18DevReceiverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kwipi-b18-fixtures-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)
        self.sel = self.work / "b18-selection"
        self.b10 = self.work / "b10-selection"
        self.src = self.work / b17.LAYER
        self.base = self.work / p14b.LAYER
        self.addon = self.work / b6.LAYER
        shutil.copytree(B18, self.sel)
        shutil.copytree(B10, self.b10)
        self.src.mkdir()
        self.base.mkdir()
        self.addon.mkdir()
        receiver = b17.staged_files(ROOT)[1]
        revision = receiver["source_revision"]
        self.base_proof = {
            "schema": p14b.SCHEMA, "source_revision": revision,
            "oem_yocto_sha": p14b.YOCTO_SHA,
            "selected_python_modules": 19, "license_recipe_closed": True,
            "source_license_checked": False,
            "source_sha256": {
                **{name: "a" * 64 for name in p14b.p14a.SELECTED},
                "pyproject.toml": "b" * 64,
            },
        }
        self.addon_proof = {
            "schema": b6.SCHEMA, "source_revision": revision,
            "oem_yocto_sha": p14b.YOCTO_SHA,
            "status": "host_addon_source_candidate_not_bitbake",
            "addon_modules": 5, "base_modules": 19,
            "base_sha256": {
                key: self.base_proof["source_sha256"][key]
                for key in p14b.p14a.SELECTED
            },
            "dev_image_selected": False, "shipping_image_selected": False,
            "systemd_installed": False, "robot_validated": False,
        }
        self.receiver = receiver

    def env(self, image: str, *, rcount: int | None = None,
            pcount: int | None = None, bcount: int | None = None,
            extra: str = "", identity: str | None = None,
            features: str = "", layers: list[Path] | None = None) -> str:
        dev = image == "microduck-image-dev"
        if rcount is None:
            rcount = int(dev)
        if pcount is None:
            pcount = int(dev)
        if bcount is None:
            bcount = int(dev)
        installed = ["microduck-daemon", "microduck-data"]
        installed += ["kwipi-companion"] * bcount
        installed += [b10.PACKAGE] * pcount
        installed += [b17.PACKAGE] * rcount
        installed += extra.split()
        actual_layers = layers if layers is not None else [
            DEV, ACCOUNT, self.base, self.addon, self.src,
            self.b10, self.sel,
        ]
        acct = identity if identity is not None else OEM_OPERATOR + (KWIPI if dev else "")
        return (
            f'PN="{image}"\n'
            f'IMAGE_INSTALL="{" ".join(installed)}"\n'
            f'IMAGE_FEATURES="{features}"\n'
            f'BBLAYERS="{" ".join(str(x) for x in actual_layers)}"\n'
            f'EXTRA_USERS_PARAMS="{acct}"\n'
        )

    def recipe_env(self, overrides: dict[str, str] | None = None) -> str:
        base = b17.PACKAGE + "-" + b17.VERSION
        vars = {
            "PN": b17.PACKAGE,
            "PV": b17.VERSION,
            "LICENSE": "CLOSED",
            "PACKAGE_ARCH": "all",
            "SRC_URI": f"file://{b17.ARCHIVE};subdir={base};name=p15b17",
            "BP": base,
            "S": f"/tmp/test-unpack/{base}",
            "UNPACKDIR": "/tmp/test-unpack",
            "PYTHON_SITEPACKAGES_DIR": b18.PYTHON_DIR,
            "BBLAYERS": " ".join(str(x) for x in (
                DEV, ACCOUNT, self.base, self.addon,
                self.b10, self.sel, self.src,
            )),
            "RDEPENDS:" + b17.PACKAGE: " ".join(b17.RUNTIME),
        }
        vars.update(overrides or {})
        return "".join(f'{k}="{v}"\n' for k, v in vars.items())

    def appends(self):
        return (
            "microduck-image-dev.bb:\n"
            f"  {DEV / 'recipes-core/images/microduck-image-dev.bbappend'}\n"
            f"  {ACCOUNT / 'recipes-core/images/microduck-image-dev.bbappend'}\n"
            f"  {self.b10 / b10.APPEND}\n"
            f"  {self.sel / b18.APPEND}\n"
        )

    def check(self, *, dev=None, shipping=None, appends=None, recipe=None,
              checksum=None, receiver=None):
        return b18.validate(
            dev if dev is not None else self.env("microduck-image-dev"),
            shipping if shipping is not None else self.env("microduck-image"),
            appends if appends is not None else self.appends(),
            recipe if recipe is not None else self.recipe_env(),
            checksum if checksum is not None else self.receiver["archive_sha256"],
            selection_layer=self.sel, b10_selection=self.b10,
            receiver_layer=self.src, addon_layer=self.addon,
            dev_layer=DEV, python_layer=self.base, account_layer=ACCOUNT,
            base_provenance=self.base_proof,
            addon_provenance=self.addon_proof,
            receiver_provenance=self.receiver if receiver is None else receiver,
        )

    def test_01_nominal_fixture_metadata_no_robot_claim(self):
        report = self.check()
        self.assertEqual(report["schema"], b18.SCHEMA)
        self.assertEqual(report["status"], b18.STATUS)
        self.assertEqual((report["base_modules"], report["passive_modules"],
                          report["receiver_modules"]), (19, 5, 4))
        self.assertEqual((report["dev_receiver_count"],
                          report["shipping_receiver_count"]), (1, 0))
        self.assertTrue(report["oem_packages_preserved"])
        self.assertTrue(report["kwipi_account_isolated_by_effective_metadata"])
        self.assertTrue(report["receiver_rdepends_checked"])
        self.assertEqual(report["motor_commands_issued"], 0)
        for key in ("bitbake_executed_by_this_gate",
                    "rootfs_or_package_built_by_this_gate",
                    "new_dev_rootfs_installed", "shipping_image_changed",
                    "systemd_service_activated", "oem_producer_activated",
                    "robot_sensor_validated", "robot_validated"):
            self.assertFalse(report[key])

    def test_02_real_reused_source_gates_and_unchanged_source(self):
        shutil.rmtree(self.base)
        shutil.rmtree(self.addon)
        shutil.rmtree(self.src)
        p14b.stage(ROOT, self.base)
        b6.stage(ROOT, self.addon)
        b17.stage(ROOT, self.src)
        base, addon, receiver = b18.source_gate(
            ROOT, selection_layer=self.sel, b10_selection=self.b10,
            receiver_layer=self.src, addon_layer=self.addon,
            dev_layer=DEV, python_layer=self.base, account_layer=ACCOUNT,
        )
        self.assertEqual(base["selected_python_modules"], 19)
        self.assertEqual(addon["addon_modules"], 5)
        self.assertEqual(receiver["new_modules"], 4)
        self.assertEqual(receiver["source_revision"], base["source_revision"])

    def test_03_absent_or_duplicate_dev_receiver(self):
        for count in (0, 2):
            with self.subTest(count=count), self.assertRaises(EnvRefused):
                self.check(dev=self.env("microduck-image-dev", rcount=count))

    def test_04_shipping_receiver_leak_or_unsafe_features(self):
        for bad in (
            self.env("microduck-image", rcount=1),
            self.env("microduck-image", features="allow-root-login"),
            self.env("microduck-image", extra="kwipi-companion"),
        ):
            with self.subTest(bad=bad[-70:]), self.assertRaises(EnvRefused):
                self.check(shipping=bad)

    def test_05_historical_base_and_oem_must_remain_selected(self):
        for bad in (
            self.env("microduck-image-dev", pcount=0),
            self.env("microduck-image-dev", bcount=0),
            self.env("microduck-image-dev", extra="kwipi-passive-fixture"),
            self.env("microduck-image-dev").replace("microduck-daemon",
                                                     "not-oem-daemon"),
        ):
            with self.subTest(case=bad[-100:]), self.assertRaises(EnvRefused):
                self.check(dev=bad)

    def test_06_missing_required_layer_in_dev_or_shipping_or_recipe(self):
        layers = [DEV, ACCOUNT, self.base, self.addon, self.src, self.b10, self.sel]
        for gone in (self.sel, self.src, self.b10):
            new = [x for x in layers if x != gone]
            with self.subTest(gone=str(gone)):
                with self.assertRaises(EnvRefused):
                    self.check(dev=self.env("microduck-image-dev", layers=new))
                with self.assertRaises(EnvRefused):
                    self.check(shipping=self.env("microduck-image", layers=new))
        env = self.recipe_env().replace(str(self.src), "/tmp/unrelated-layer")
        with self.assertRaises(EnvRefused):
            self.check(recipe=env)

    def test_07_append_missing_repeated_or_selected_shipping(self):
        src = str(self.sel / b18.APPEND)
        for bad in (
            self.appends().replace(src, "/tmp/foreign.bbappend"),
            self.appends() + f"  {src}\n",
            self.appends().replace("microduck-image-dev.bb:",
                                   "microduck-image.bb:"),
            self.appends() + f"microduck-image.bb:\n  {src}\n",
            self.appends() + f"other.bb:\n  {src}\n",
        ):
            with self.subTest(bad=bad[-120:]), self.assertRaises(EnvRefused):
                self.check(appends=bad)

    def test_08_identity_oem_operator_and_private_kwipi_guards(self):
        for value in (
            OEM_OPERATOR,
            OEM_OPERATOR + " groupadd -r kwipi; useradd -r -G robot kwipi;",
            OEM_OPERATOR + KWIPI + " usermod -aG robot kwipi;",
        ):
            with self.subTest(identity=value[-75:]), self.assertRaises(EnvRefused):
                self.check(dev=self.env("microduck-image-dev", identity=value))

    def test_09_wrong_recipe_identity_license_arch_or_abi(self):
        for key, value in (
            ("PN", "kwipi-b12-fake"),
            ("PV", "0.9.0"),
            ("LICENSE", "MIT"),
            ("PACKAGE_ARCH", "aarch64"),
            ("PYTHON_SITEPACKAGES_DIR", "/usr/lib/python3.12/site-packages"),
            ("BP", "other-package-0.1.0"),
        ):
            with self.subTest(key=key), self.assertRaises(EnvRefused):
                self.check(recipe=self.recipe_env({key: value}))

    def test_10_source_uri_unpacked_target_and_checksum_refused(self):
        base = b17.PACKAGE + "-" + b17.VERSION
        for key, val in (
            ("SRC_URI", "file://unreviewed.tar.gz"),
            ("SRC_URI", f"file://{b17.ARCHIVE};subdir={base};name=p15b17 "
                        f"file://unreviewed.tar.gz"),
            ("SRC_URI", f"file://{b17.ARCHIVE};subdir={base};name=p15b17 "
                        f"file://{b17.ARCHIVE};subdir={base};name=p15b17"),
            ("S", "/tmp/escape"),
            ("UNPACKDIR", "relative-dir"),
        ):
            with self.subTest(key=key), self.assertRaises(EnvRefused):
                self.check(recipe=self.recipe_env({key: val}))
        for bad in ("0" * 64, "not-a-sha256", self.receiver["archive_sha256"] + "garbage"):
            with self.assertRaises(EnvRefused):
                self.check(checksum=bad)

    def test_11_runtime_dependencies_not_missing_or_extra(self):
        var = "RDEPENDS:" + b17.PACKAGE
        original = list(b17.RUNTIME)
        for values in (original[:-1], original + ["robot"],
                       original + [original[0]]):
            with self.subTest(values=values), self.assertRaises(EnvRefused):
                self.check(recipe=self.recipe_env({var: " ".join(values)}))

    def test_12_source_provenance_cannot_be_implicitly_promoted(self):
        for key, value in (
            ("schema", "unreviewed"),
            ("new_modules", 5),
            ("dev_image_selected", True),
            ("oem_producer_enabled", True),
            ("robot_validated", True),
            ("license_redistribution_approved", True),
            ("source_revision", "other-revision"),
            ("archive_sha256", "0" * 64),
        ):
            corrupted = {**self.receiver, key: value}
            with self.subTest(key=key), self.assertRaises(EnvRefused):
                self.check(receiver=corrupted)

    def test_13_selection_layer_strict_two_files(self):
        self.assertEqual(b18.closed_layer(self.sel), self.sel.resolve())
        extra = self.sel / "unexpected.txt"
        extra.write_text("not-approved")
        with self.assertRaises(EnvRefused):
            self.check()
        extra.unlink()
        conf = self.sel / b18.CONF
        saved = conf.read_text()
        conf.write_text(saved + '\nBBFILES += "unreviewed"\n')
        with self.assertRaises(EnvRefused):
            self.check()
        conf.write_text(saved)
        append = self.sel / b18.APPEND
        append.unlink()
        with self.assertRaises(EnvRefused):
            self.check()

    def test_14_symlinked_selection_path_refused(self):
        linked = self.work / "selection-link"
        linked.symlink_to(self.sel, target_is_directory=True)
        with self.assertRaises(EnvRefused):
            b18.closed_layer(linked)
        checked = self.sel / b18.APPEND
        saved = checked.read_bytes()
        other = self.work / "outside.bbappend"
        other.write_bytes(saved)
        checked.unlink()
        checked.symlink_to(other)
        with self.assertRaises(EnvRefused):
            b18.closed_layer(self.sel)

    def test_15_private_metadata_input_refused_when_symlinked_or_public(self):
        env = self.work / "real-env"
        env.write_text(self.env("microduck-image-dev"))
        env.chmod(0o644)
        with self.assertRaises(EnvRefused):
            b10._private_env(env)
        env.chmod(0o600)
        self.assertIn('PN="microduck-image-dev"', b10._private_env(env))
        symlink = self.work / "linked-env"
        symlink.symlink_to(env)
        with self.assertRaises(EnvRefused):
            b10._private_env(symlink)

    def test_16_b17_source_layer_symlink_rejected(self):
        source = self.work / "replaced"
        source.symlink_to(self.src, target_is_directory=True)
        with self.assertRaises(b17.Refused):
            b17.verify(ROOT, source)


if __name__ == "__main__":
    unittest.main()
