"""P15-B9 effective metadata fixtures; no BitBake, rootfs, robot or secrets."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.per_p13a_bitbake_env_gate import EnvRefused
from scripts.per_p15b9_dev_account_env_gate import (
    APPEND_REL, EXPECTED_OEM_GROUPS, SCHEMA, _commands, validate,
)

OPERATOR = (
    "useradd -m -s /bin/bash -G " + EXPECTED_OEM_GROUPS +
    " -p '$6$synthetic-fixture-only' microduck;"
)
KWIPI = (" groupadd -r kwipi; useradd -r -g kwipi -M "
         "-s /sbin/nologin -p '!' kwipi;")


class AccountMetadataGateTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.layer = Path(temporary.name) / "meta-kwipi-p15-account"
        append = self.layer / APPEND_REL
        append.parent.mkdir(parents=True)
        append.write_text("EXTRA_USERS_PARAMS:append = 'fixture'\n")
        self.appends = f"/oem/microduck-image-dev.bb:\n  {append}\n"

    def env(self, image: str, params: str, *, layers: str | None = None) -> str:
        if layers is None:
            layers = str(self.layer)
        return (f'PN="{image}"\nBBLAYERS="{layers}"\n'
                f'EXTRA_USERS_PARAMS="{params}"\n')

    def check(self, *, dev=None, ship=None, appends=None):
        return validate(
            self.env("microduck-image-dev", OPERATOR + KWIPI)
            if dev is None else dev,
            self.env("microduck-image", OPERATOR)
            if ship is None else ship,
            self.appends if appends is None else appends,
            account_layer=self.layer,
        )

    def test_nominal_is_metadata_only_and_never_exposes_hash(self):
        output = self.check()
        self.assertEqual(output["schema"], SCHEMA)
        self.assertEqual(output["dev_identity_commands"], 3)
        self.assertEqual(output["shipping_identity_commands"], 1)
        self.assertTrue(output["kwipi_user_declared_dev_only"])
        self.assertFalse(output["account_present_in_new_rootfs_verified"])
        self.assertFalse(output["robot_validated"])
        self.assertNotIn("synthetic-fixture-only", str(output))

    def test_negative_identity_mutations(self):
        mutations = {
            "motor_group": KWIPI.replace("-g kwipi", "-G robot -g kwipi"),
            "operator_group": KWIPI.replace("-g kwipi", "-g robot"),
            "interactive_shell": KWIPI.replace("/sbin/nologin", "/bin/bash"),
            "password_not_locked": KWIPI.replace("-p '!'", "-p 'pw'"),
            "no_password": KWIPI.replace("-p '!'", ""),
            "home_created": KWIPI.replace("-M", "-m"),
            "non_system_user": KWIPI.replace("useradd -r", "useradd"),
            "fixed_uid": KWIPI.replace("useradd -r", "useradd -u 1003 -r"),
            "extra_privileged_command": KWIPI + " usermod -aG robot kwipi;",
            "missing_kwipi": "",
            "missing_group": KWIPI.replace(" groupadd -r kwipi;", ""),
            "duplicate": KWIPI + KWIPI,
            "incomplete": KWIPI[:-1],
        }
        for label, value in mutations.items():
            with self.subTest(label=label), self.assertRaises(EnvRefused):
                self.check(dev=self.env("microduck-image-dev", OPERATOR + value))

    def test_shipping_leak_or_drift_refused(self):
        mutations = {
            "leak_to_shipping": OPERATOR + KWIPI,
            "operator_motor_removed": OPERATOR.replace(
                "robot,sudo", "sudo"),
            "operator_name_changed": OPERATOR.replace(
                "microduck;", "admin;"),
            "operator_command_missing": "",
        }
        for label, value in mutations.items():
            with self.subTest(label=label), self.assertRaises(EnvRefused):
                self.check(ship=self.env("microduck-image", value))

    def test_wrong_image_layer_or_append_refused(self):
        with self.assertRaises(EnvRefused):
            self.check(dev=self.env("microduck-image", OPERATOR + KWIPI))
        with self.assertRaises(EnvRefused):
            self.check(ship=self.env("microduck-image-dev", OPERATOR))
        with self.assertRaises(EnvRefused):
            self.check(dev=self.env("microduck-image-dev",
                                    OPERATOR + KWIPI, layers="/missing"))
        with self.assertRaises(EnvRefused):
            self.check(appends="microduck-image.bb: other.bbappend")

    def test_invalid_semicolon_and_quoting_refused(self):
        for text in (OPERATOR + " ;" + KWIPI, OPERATOR + KWIPI + ";",
                     OPERATOR + ' "broken quote;', OPERATOR[:-1]):
            with self.subTest(value=text[:25]), self.assertRaises(EnvRefused):
                _commands(text)


if __name__ == "__main__":
    unittest.main()
