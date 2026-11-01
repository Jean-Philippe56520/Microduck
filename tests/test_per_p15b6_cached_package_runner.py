"""P15-B6-P cached operator runner: host fixtures only, NEVER launch BitBake."""
from __future__ import annotations

from pathlib import Path
import json
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from scripts import per_p15b6_cached_package_runner as runner


class CachedOperatorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="kwipi-b6p-cached-")
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        self.sha = "a" * 40
        self.cfg = runner.Config(
            root / "project", root / "yocto", root / "work",
            root / "build", root / "scratch", self.sha)
        self.cfg.project.mkdir()
        self.cfg.yocto.mkdir()
        self.cfg.work.mkdir()
        self.cfg.build.mkdir()
        (self.cfg.project / "upstream/microduck").mkdir(parents=True)
        (self.cfg.project / "upstream/microduck_rl").mkdir(parents=True)
        for repo in runner.KAS_REPOS:
            (self.cfg.work / repo).mkdir()
        (self.cfg.yocto / "kas").mkdir()
        (self.cfg.yocto / "kas/microduck.yml").write_text("header:\n  version: 14\n")
        (self.cfg.build / "conf").mkdir()
        (self.cfg.build / "conf/local.conf").write_text('MACHINE = "microduck-zero3"\n')
        (self.cfg.build / "tmp/work").mkdir(parents=True)
        target = self.cfg.build / "tmp/stamps/x86_64-linux/cmake-native/4.3.1-r0"
        target.mkdir(parents=True)
        (target / "do_populate_sysroot").write_text("done")
        self.revisions = {
            self.cfg.project: self.sha, self.cfg.yocto: runner.YOCTO,
            self.cfg.project / "upstream/microduck": runner.OEM,
            self.cfg.project / "upstream/microduck_rl": runner.RL,
            **{self.cfg.work / name: rev for name, rev in runner.KAS_REPOS.items()},
        }
        self.git_patch = patch.object(runner, "_git", side_effect=self._fake_git)
        self.space_patch = patch.object(
            runner.shutil, "disk_usage",
            return_value=SimpleNamespace(free=17 * 1024**3))
        self.git_patch.start()
        self.space_patch.start()
        self.addCleanup(self.git_patch.stop)
        self.addCleanup(self.space_patch.stop)

    def _fake_git(self, path, *cmd):
        if cmd == ("status", "--porcelain", "--untracked-files=no"):
            return ""
        if cmd == ("rev-parse", "HEAD:upstream/microduck"):
            return runner.OEM
        if cmd == ("rev-parse", "HEAD:upstream/microduck_rl"):
            return runner.RL
        if cmd == ("rev-parse", "HEAD"):
            return self.revisions[path]
        raise AssertionError("unexpected Git query: " + str(cmd))

    def test_01_readonly_preflight_succeeds_without_creating_scratch(self):
        report = runner.preflight(self.cfg)
        self.assertEqual(runner.CHECK, report["status"])
        self.assertTrue(report["existing_bitbake_cache"])
        self.assertFalse(report["bitbake_run"])
        self.assertFalse(report["package_verified"])
        self.assertFalse(self.cfg.scratch.exists())

    def test_02_wrong_expected_sha_refused(self):
        bad = runner.Config(*self.cfg.__dict__.values())  # same paths, pinned sha below
        self.assertEqual(bad.expected_sha, self.sha)
        invalid = runner.Config(
            self.cfg.project, self.cfg.yocto, self.cfg.work,
            self.cfg.build, self.cfg.scratch, "invalid")
        with self.assertRaises(runner.Refused):
            runner.preflight(invalid)
        self.revisions[self.cfg.project] = "b" * 40
        with self.assertRaises(runner.Refused):
            runner.preflight(self.cfg)

    def test_03_wrong_oem_or_yocto_repository_refused(self):
        for path in (self.cfg.yocto, self.cfg.project / "upstream/microduck",
                     self.cfg.project / "upstream/microduck_rl", self.cfg.work / "bitbake"):
            before = self.revisions[path]
            self.revisions[path] = "0" * 40
            with self.subTest(path=path), self.assertRaises(runner.Refused):
                runner.preflight(self.cfg)
            self.revisions[path] = before

    def test_04_cache_required_no_cold_build(self):
        conf = self.cfg.build / "conf/local.conf"
        conf.unlink()
        with self.assertRaises(runner.Refused):
            runner.preflight(self.cfg)
        conf.write_text("restored")
        stamp = next((self.cfg.build / "tmp/stamps").rglob("do_populate_sysroot"))
        stamp.unlink()
        with self.assertRaises(runner.Refused):
            runner.preflight(self.cfg)

    def test_05_signatures_only_do_not_count_as_completed_cache(self):
        stamp_dir = next((self.cfg.build / "tmp/stamps").rglob("cmake-native")).parent / "cmake-native/4.3.1-r0"
        stamp_dir.joinpath("do_populate_sysroot").unlink()
        stamp_dir.joinpath("do_populate_sysroot.sigdata.abc").write_bytes(b"fake")
        with self.assertRaises(runner.Refused):
            runner.preflight(self.cfg)

    def test_06_insufficient_disk_and_existing_scratch_refused(self):
        with patch.object(runner.shutil, "disk_usage",
                          return_value=SimpleNamespace(free=8 * 1024**3)):
            with self.assertRaises(runner.Refused):
                runner.preflight(self.cfg)
        self.cfg.scratch.mkdir()
        with self.assertRaises(runner.Refused):
            runner.preflight(self.cfg)

    def test_07_scratch_overlapping_existing_build_or_checkout_refused(self):
        for scratch in (self.cfg.project / "stage", self.cfg.build / "new",
                        self.cfg.yocto / "new", self.cfg.work / "new"):
            cfg = runner.Config(
                self.cfg.project, self.cfg.yocto, self.cfg.work,
                self.cfg.build, scratch, self.sha)
            with self.subTest(scratch=scratch), self.assertRaises(runner.Refused):
                runner.preflight(cfg)

    def test_08_overlay_offline_sources_only_never_selects_addon(self):
        overlay = runner._overlay(self.cfg)
        self.assertIn('BB_NO_NETWORK = "1"', overlay)
        self.assertIn(str(self.cfg.scratch / "meta-kwipi-passive"), overlay)
        self.assertNotIn("IMAGE_INSTALL", overlay)
        command = runner._task_command(self.cfg.scratch)
        self.assertIn("bitbake -c package kwipi-passive-fixture", command)
        self.assertIn("bitbake-getvar", command)
        for prohibited in ("do_rootfs", "do_image", "cleansstate",
                           "bitbake -c build", "rauc"):
            self.assertNotIn(prohibited, command)

    def test_09_run_invokes_one_bounded_bitbake_and_checks_report(self):
        calls = []
        def emulate(command, env, *, timeout, cwd, capture=False):
            calls.append((command, timeout, dict(env)))
            if command[1:3] == ["-m", "scripts.per_p15b6_bitbake_package_gate"]:
                (self.cfg.scratch / "package-proof.json").write_text(json.dumps({
                    "status": runner.PASS,
                    "source_revision": self.sha,
                    "package_split_files_verified": True,
                }))
            return ""
        with patch.object(runner, "_check_kas"), patch.object(runner, "_execute", side_effect=emulate):
            result = runner.execute(self.cfg)
        self.assertEqual(runner.PASS, result["status"])
        self.assertEqual(0, result["bitbake_do_package_exit_code"])
        self.assertEqual(6, len(calls))
        kas = [x for x in calls if x[0][0] == "kas"]
        self.assertEqual(1, len(kas))
        self.assertEqual(1600, kas[0][1])
        self.assertIn("--skip", kas[0][0])
        self.assertIn("repos_checkout", kas[0][0])
        self.assertEqual("true", kas[0][2]["CARGO_NET_OFFLINE"])
        self.assertTrue((self.cfg.scratch / "package-proof.json").exists())

    def test_10_no_success_on_kas_failure_or_missing_report(self):
        calls = []
        def fail_kas(command, env, *, timeout, cwd, capture=False):
            calls.append(command)
            if command[0] == "kas":
                raise runner.Refused("BitBake native timeout")
            return ""
        with patch.object(runner, "_check_kas"), patch.object(runner, "_execute", side_effect=fail_kas):
            with self.assertRaises(runner.Refused):
                runner.execute(self.cfg)
        self.assertFalse((self.cfg.scratch / "package-proof.json").exists())
        self.assertEqual(1, sum(cmd[0] == "kas" for cmd in calls))

    def test_11_run_does_nothing_without_valid_kas_version(self):
        with patch.object(runner, "_check_kas", side_effect=runner.Refused("wrong kas")), \
             patch.object(runner, "_execute") as executed:
            with self.assertRaises(runner.Refused):
                runner.execute(self.cfg)
            executed.assert_not_called()
        self.assertFalse(self.cfg.scratch.exists())

    def test_12_pin_fails_if_staged_tree_dirty(self):
        def dirty(path, *cmd):
            if path == self.cfg.project and cmd == (
                    "status", "--porcelain", "--untracked-files=no"):
                return " M Cargo.lock"
            return self._fake_git(path, *cmd)
        with patch.object(runner, "_git", side_effect=dirty):
            with self.assertRaises(runner.Refused):
                runner.preflight(self.cfg)


if __name__ == "__main__":
    unittest.main()
