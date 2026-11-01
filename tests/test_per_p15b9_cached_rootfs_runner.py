"""P15-B9-R cached rootfs runner fixtures: never execute KAS or BitBake."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts import per_p15b9_cached_rootfs_runner as run
from scripts import per_p15b6_cached_package_runner as cached


class RootfsRunnerFixtures(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="p15b9r-runner-")
        self.addCleanup(temp.cleanup)
        base = Path(temp.name)
        self.project = base / "repo"
        self.project.mkdir()
        self.cfg = cached.Config(
            self.project, base / "yocto", base / "kas-work",
            base / "build", base / "scratch", "a" * 40,
        )

    def test_01_overlay_exact_layers_no_passive_or_motor_service(self):
        overlay = run._overlay(self.cfg)
        for item in ("kwipi:", "kwipipy:", "kwipidev:",
                     "kwipip15:", "kwipiaccount:"):
            self.assertIn(item, overlay)
        self.assertIn('BB_NO_NETWORK = "1"', overlay)
        for forbidden in ("kwipipassive:", "IMAGE_INSTALL", "rauc:",
                          "robotd:", "SYSTEMD_AUTO_ENABLE"):
            self.assertNotIn(forbidden, overlay)

    def test_02_metadata_only_before_explicit_rootfs(self):
        cmd = run._metadata_command(self.cfg.scratch)
        for item in ("bitbake -p", "bitbake -e microduck-image-dev",
                     "bitbake -e microduck-image",
                     "bitbake -e kwipi-readonly-probe",
                     "bitbake-layers show-appends"):
            self.assertIn(item, cmd)
        for forbidden in ("-c rootfs", "do_image", "wic", "rauc", "cleanall"):
            self.assertNotIn(forbidden, cmd)

    def test_03_private_bitbake_environment_files_are_0600(self):
        self.cfg.scratch.mkdir()
        path = self.cfg.scratch / "private-env.txt"
        old = os.umask(0o022)
        try:
            run._private(path)
        finally:
            os.umask(old)
        self.assertEqual(0o600, path.stat().st_mode & 0o777)
        with self.assertRaises(FileExistsError):
            run._private(path)

    def test_04_effective_paths_confined_to_cached_workdir(self):
        root = self.cfg.build / "tmp/work/machine/recipe/1.0"
        root.mkdir(parents=True)
        env = (
            f'WORKDIR="{root}"\n'
            f'T="{root / "temp"}"\n'
            f'IMAGE_ROOTFS="{root / "rootfs"}"\n'
        )
        self.assertEqual((root / "rootfs", root / "temp"),
                         run._paths(self.cfg, env))
        unsafe = env.replace(f'{root / "rootfs"}', '/tmp/external/rootfs')
        with self.assertRaises(cached.Refused):
            run._paths(self.cfg, unsafe)

    def test_05_log_required_to_change_not_old_cache(self):
        folder = self.cfg.build / "temp"
        folder.mkdir(parents=True)
        (folder / "log.do_rootfs.101").write_text("old")
        original = run._logs(folder)
        self.assertEqual(original, run._logs(folder))
        (folder / "log.do_rootfs.102").write_text("new")
        self.assertTrue(run._logs(folder) - original)

    def test_06_refuse_preflight_failure_without_staging(self):
        with patch.object(run.preflight, "check", side_effect=cached.Refused("missing")), \
             patch.object(run, "_stage") as stage:
            with self.assertRaises(cached.Refused):
                run.execute(self.cfg)
            stage.assert_not_called()

    def test_07_check_only_does_not_call_bitbake(self):
        with patch.object(run.preflight, "check", return_value={
                "status": "p15b9r_cached_rootfs_readonly_preflight_only",
                "bitbake_executed": False,
                "rootfs_built": False,
            }) as check, patch.object(run, "_stage") as stage:
            result = run.preflight.check(self.cfg)
            self.assertFalse(result["rootfs_built"])
            check.assert_called_once_with(self.cfg)
            stage.assert_not_called()


if __name__ == "__main__":
    unittest.main()
