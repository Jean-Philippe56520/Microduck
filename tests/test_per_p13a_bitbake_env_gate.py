"""P13A effective BitBake metadata: fail-closed positive/negative fixtures."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.per_p12_yocto_layer import BMI_URI, SCHEMA
from scripts.per_p13a_bitbake_env_gate import EnvRefused, validate

REVISION = "a" * 40
P12 = {
    "schema": SCHEMA, "source_only": True, "bitbake_parsed": False,
    "robot_validated": False, "crates_generated": 2,
    "archive_sha256": "b" * 64, "companion_sha": REVISION,
}
LAYER = Path("/tmp/kwipi-p13-fixture-layer")
BASE_SRC = (
    "file://kwipi-v1-oem-source.tar.gz;subdir=microduck-daemon-0.17.8+kwipi.p12.aaaaaaaaaaaa;name=kwipisrc "
    + BMI_URI + " "
    "file://60-robot-i2c.rules "
    "file://robotctl.bash_completion "
    "file://microduck-voice-bank.service "
    "crate://crates.io/serde/1.0.0 "
    "crate://crates.io/anyhow/1.0.104"
)


def fake_env(src: str = BASE_SRC) -> str:
    return "\n".join((
        f'SRC_URI="{src}"',
        'PV="0.17.8+kwipi.p12.aaaaaaaaaaaa"',
        f'MICRODUCK_DAEMON_SRCREV="{REVISION}"',
        'SRCREV_FORMAT="bmi088"',
        'UNPACKDIR="/tmp/p13/unpack"',
        'BP="microduck-daemon-0.17.8+kwipi.p12.aaaaaaaaaaaa"',
        'S="/tmp/p13/unpack/microduck-daemon-0.17.8+kwipi.p12.aaaaaaaaaaaa"',
        f'BBLAYERS="{LAYER}"',
    )) + "\n"


class EffectiveEnvTests(unittest.TestCase):
    def test_exact_candidate_passes_and_does_not_claim_build(self):
        data = validate(fake_env(), P12, layer=LAYER)
        self.assertEqual(data["effective_crates"], 2)
        self.assertTrue(data["bitbake_parse_passed"])
        self.assertFalse(data["bitbake_compile_run"])
        self.assertFalse(data["signed_release"])
        self.assertFalse(data["physical_robot_verified"])

    def check_refused(self, old: str, new: str):
        with self.assertRaises(EnvRefused):
            validate(fake_env().replace(old, new, 1), P12, layer=LAYER)

    def test_original_oem_git_is_fatal(self):
        self.check_refused("crate://crates.io/serde/1.0.0",
                           "git://git@github.com/pollen-robotics/microduck_daemon.git;name=daemon")

    def test_missing_vendor_is_fatal(self):
        self.check_refused(BMI_URI, "")

    def test_missing_local_resource_is_fatal(self):
        self.check_refused("file://robotctl.bash_completion", "")

    def test_missing_archive_is_fatal(self):
        self.check_refused("file://kwipi-v1-oem-source.tar.gz",
                           "file://anonymous-source.tar.gz")

    def test_duplicate_crates_are_fatal(self):
        self.check_refused("crate://crates.io/serde/1.0.0",
                           "crate://crates.io/serde/1.0.0 crate://crates.io/serde/1.0.0")

    def test_wrong_version_is_fatal(self):
        self.check_refused('PV="0.17.8+kwipi', 'PV="0.17.8')

    def test_wrong_unpack_path_is_fatal(self):
        self.check_refused('S="/tmp/p13/unpack', 'S="/tmp/p13/different')

    def test_escaped_newlines_from_real_bitbake_are_normalized(self):
        escaped = 'BBLAYERS=" /tmp/irrelevant \\n ' + str(LAYER) + ' \\n "'
        env = fake_env().replace('BBLAYERS="' + str(LAYER) + '"', escaped)
        report = validate(env, P12, layer=LAYER)
        self.assertTrue(report["bitbake_parse_passed"])

    def test_wrong_layer_is_fatal(self):
        self.check_refused(f'BBLAYERS="{LAYER}"', 'BBLAYERS="/tmp/other-layer"')

    def test_no_unverified_promotion(self):
        changed = dict(P12, bitbake_parsed=True)
        with self.assertRaises(EnvRefused):
            validate(fake_env(), changed, layer=LAYER)


if __name__ == "__main__":
    unittest.main()
