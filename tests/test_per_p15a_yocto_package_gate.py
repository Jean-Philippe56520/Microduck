"""P15A-P tests on synthetic packages; never pretend to run BitBake here."""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.per_p13a_bitbake_env_gate import EnvRefused
from scripts.per_p15a_yocto_package_gate import (
    PN, UNIT, PROBE_REL, UNIT_REL, SCHEMA, validate_package,
)

ROOT = Path(__file__).resolve().parents[1]
LAYER = ROOT / "yocto/meta-kwipi-p15-readonly"


class P15APackageGateFixtureTests(unittest.TestCase):
    def setUp(self):
        ctx = tempfile.TemporaryDirectory()
        self.addCleanup(ctx.cleanup)
        self.root = Path(ctx.name)
        self.tmpdir = self.root / "build/tmp"
        self.pkgdest = self.tmpdir / "work/all-arch/kwipi-readonly-probe/0.1/packages-split"
        self.pkgroot = self.pkgdest / PN
        self.libexec = "/usr/libexec"
        self.systemd_unitdir = "/usr/lib/systemd"
        self.systemd_system_unitdir = "/usr/lib/systemd/system"
        self.probe = self.pkgroot / "usr/libexec/kwipi/health_probe.py"
        self.unit = self.pkgroot / "usr/lib/systemd/system/kwipi-readonly-probe.service"
        self.preset = self.pkgroot / "usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset"
        for path in (self.probe, self.unit, self.preset):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.probe.write_bytes((LAYER / PROBE_REL).read_bytes())
        source_unit = (LAYER / UNIT_REL).read_text()
        self.unit.write_text(source_unit.replace("@LIBEXECDIR@", self.libexec))
        self.preset.write_text("disable kwipi-readonly-probe.service\n")
        for path in (self.probe, self.unit, self.preset):
            path.chmod(0o644)
        self.env = "\n".join((
            'PN="kwipi-readonly-probe"', 'PV="0.1"',
            f'FILE="{LAYER}/recipes-kwipi/kwipi-readonly-probe/kwipi-readonly-probe_0.1.bb"',
            'LICENSE="CLOSED"',
            f'PKGDEST="{self.pkgdest}"',
            f'TMPDIR="{self.tmpdir}"',
            'S="/tmp/fake-unpack"', 'UNPACKDIR="/tmp/fake-unpack"',
            'export libexecdir="/usr/libexec"',
            'export systemd_unitdir="/usr/lib/systemd"',
            'export systemd_system_unitdir="/usr/lib/systemd/system"',
            f'BBLAYERS="{LAYER}"',
            'SYSTEMD_SERVICE:kwipi-readonly-probe="kwipi-readonly-probe.service"',
            'SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe="disable"',
            'RDEPENDS:kwipi-readonly-probe="kwipi-companion python3-core python3-json"',
        )) + "\n"

    def run_gate(self, env=None):
        return validate_package(ROOT, self.env if env is None else env)

    def test_positive_fixture_excludes_rootfs_or_motor_claims(self):
        r = self.run_gate()
        self.assertEqual(r["schema"], SCHEMA)
        self.assertEqual(r["status"], "bitbake_p15a_package_files_verified_only")
        self.assertEqual(r["package_files_verified"], 3)
        self.assertEqual(r["reviewed_source_files"], 5)
        self.assertTrue(r["systemd_unit_packaged"])
        self.assertTrue(r["oem_socket_group_is_not_readonly_acl"])
        self.assertFalse(r["bitbake_task_execution_attested_by_this_script"])
        for key in ("rootfs_installed", "service_executed_on_target",
                    "signed_release", "robot_validated"):
            self.assertFalse(r[key])
        self.assertEqual(r["motor_commands_issued"], 0)

    def test_plain_unexported_directories_still_work(self):
        # Some synthetic and custom metadata show the unexported spelling.
        # Both supported spellings must remain valid, never silently default.
        env = self.env.replace("export libexecdir=", "libexecdir=")
        env = env.replace("export systemd_unitdir=", "systemd_unitdir=")
        env = env.replace(
            "export systemd_system_unitdir=", "systemd_system_unitdir=")
        self.assertEqual(
            self.run_gate(env)["status"],
            "bitbake_p15a_package_files_verified_only",
        )

    def test_exported_directory_missing_duplicate_or_unquoted_refused(self):
        for var in (
            "libexecdir", "systemd_unitdir", "systemd_system_unitdir",
        ):
            assignment = next(line for line in self.env.splitlines()
                              if line.startswith("export " + var + "="))
            for altered in (
                self.env.replace(assignment + "\\n", ""),
                self.env + assignment + "\\n",
                self.env + assignment.replace("export ", "", 1) + "\\n",
                self.env.replace(assignment,
                                 assignment.replace('="', "=")
                                           .rstrip('"')),
            ):
                with self.subTest(var=var), self.assertRaises(EnvRefused):
                    self.run_gate(altered)

    def test_missing_or_tampered_script_rejected(self):
        self.probe.unlink()
        with self.assertRaises(EnvRefused):
            self.run_gate()
        shutil.copyfile(LAYER / PROBE_REL, self.probe)
        self.probe.write_bytes(self.probe.read_bytes() + b"# tampered\n")
        with self.assertRaises(EnvRefused):
            self.run_gate()

    def test_unit_activation_or_unreviewed_exec_rejected(self):
        self.unit.write_text(self.unit.read_text() + "\n[Install]\nWantedBy=multi-user.target\n")
        with self.assertRaises(EnvRefused):
            self.run_gate()
        self.unit.write_text(self.unit.read_text().replace(
            "robot.health", "robot.do"))
        with self.assertRaises(EnvRefused):
            self.run_gate()

    def test_preset_enable_is_rejected(self):
        self.preset.write_text("enable kwipi-readonly-probe.service\n")
        with self.assertRaises(EnvRefused):
            self.run_gate()

    def test_preset_absent_is_rejected(self):
        self.preset.unlink()
        with self.assertRaises(EnvRefused):
            self.run_gate()

    def test_extra_model_file_is_rejected(self):
        p = self.pkgroot / "usr/libexec/kwipi/unapproved.onnx"
        p.write_bytes(b"unreviewed")
        with self.assertRaises(EnvRefused):
            self.run_gate()

    def test_package_symlink_or_mode_drift_rejected(self):
        self.probe.unlink()
        self.probe.symlink_to(LAYER / PROBE_REL)
        with self.assertRaises(EnvRefused):
            self.run_gate()
        self.probe.unlink()
        shutil.copyfile(LAYER / PROBE_REL, self.probe)
        self.probe.chmod(0o755)
        with self.assertRaises(EnvRefused):
            self.run_gate()

    def test_identity_or_license_or_filename_drift_rejected(self):
        for old, new in (
            ('PV="0.1"', 'PV="1.0"'),
            ('LICENSE="CLOSED"', 'LICENSE="MIT"'),
            ('kwipi-readonly-probe_0.1.bb"', 'substituted.bb"'),
        ):
            with self.subTest(old=old), self.assertRaises(EnvRefused):
                self.run_gate(self.env.replace(old, new))

    def test_auto_enable_and_missing_runtime_rejected(self):
        for old, new in (
            ('SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe="disable"',
             'SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe="enable"'),
            ('kwipi-companion python3-core python3-json',
             'python3-core python3-json'),
        ):
            with self.subTest(old=old), self.assertRaises(EnvRefused):
                self.run_gate(self.env.replace(old, new))

    def test_fake_bitbake_layer_and_tmpdir_rejected(self):
        for old, new in (
            (f'BBLAYERS="{LAYER}"', 'BBLAYERS="/tmp/foreign-layer"'),
            (f'PKGDEST="{self.pkgdest}"',
             f'PKGDEST="{self.root}/unrelated"'),
        ):
            with self.subTest(old=old), self.assertRaises(EnvRefused):
                self.run_gate(self.env.replace(old, new))

    def test_unexpected_unit_layout_rejected(self):
        self.unit.unlink()
        new = self.pkgroot / "etc/systemd/system/kwipi-readonly-probe.service"
        new.parent.mkdir(parents=True)
        new.write_text((LAYER / UNIT_REL).read_text().replace(
            "@LIBEXECDIR@", self.libexec))
        with self.assertRaises(EnvRefused):
            self.run_gate()


if __name__ == "__main__":
    unittest.main()
