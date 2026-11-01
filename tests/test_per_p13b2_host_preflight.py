"""PER-P13B2-H1: positive and negative host-gate fixtures.

These unit tests DO NOT have a Yocto build host and may not attest a package.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.per_p11_v1_source_release import PIN as OEM_SHA, RL_PIN
from scripts.per_p12_yocto_layer import YOCTO_SHA
from scripts.per_p13b2_host_preflight import (
    DISK_BUDGET_GIB, GIB, SCHEMA, HostBlocked, HostSnapshot,
    _disk_budget, plan, preflight,
)


class P13B2HostPreflightTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.project, self.yocto, self.p12 = (
            self.folder / n for n in ("companion", "yocto-os", "meta-kwipi"))
        self.build, self.dl, self.sstate = (
            self.folder / n for n in ("build", "downloads", "sstate"))
        for folder in (self.project, self.yocto, self.p12,
                       self.build, self.dl, self.sstate,
                       self.project / "upstream/microduck",
                       self.project / "upstream/microduck_rl"):
            folder.mkdir(parents=True, exist_ok=True)

        self.proof = {
            "yocto_sha": YOCTO_SHA,
            "oem_sha": OEM_SHA,
            "crates_generated": 568,
            "source_only": True,
            "detector_enabled_by_default": False,
            "companion_sha": "c" * 40,
            "archive_sha256": "a" * 64,
        }
        self.snapshot = HostSnapshot("Linux", "x86_64", 8, 32 * GIB, 24 * GIB)

        def git(folder, *args):
            if args[0] == "status":
                return ""
            if args[0] == "ls-tree":
                name = args[-1]
                sha = OEM_SHA if name == "upstream/microduck" else RL_PIN
                return "160000 commit " + sha + "\t" + name
            if args[0] == "rev-parse":
                return OEM_SHA if folder.name == "microduck" else RL_PIN
            raise AssertionError("unexpected git operation")

        patches = [
            patch("scripts.per_p13b2_host_preflight._git", side_effect=git),
            patch("scripts.per_p13b2_host_preflight.check_yocto",
                  return_value="nonempty OEM include"),
            patch("scripts.per_p13b2_host_preflight.verify_p12",
                  return_value=self.proof),
            patch("scripts.per_p13b2_host_preflight.shutil.which",
                  return_value="/usr/bin/audited-tool"),
            patch("scripts.per_p13b2_host_preflight.device_key", return_value=42),
            patch("scripts.per_p13b2_host_preflight.available_bytes",
                  return_value=300 * GIB),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def check(self, *, snapshot=None, p12=None, build=None, dl=None, sstate=None):
        return preflight(
            self.project, self.yocto, p12 or self.p12,
            build or self.build, dl or self.dl, sstate or self.sstate,
            snapshot=snapshot or self.snapshot,
        )

    def test_offline_plan_makes_zero_build_claims(self):
        p = plan()
        self.assertEqual(p["schema"], SCHEMA)
        self.assertFalse(p["network_calls"])
        self.assertFalse(p["bitbake_executed"])
        self.assertEqual(p["same_volume_requires_sum_gib"], 290)
        self.assertIn("scripts/build-local.sh", p["do_not_run"])

    def test_host_fixture_passes_resources_only(self):
        v = self.check()
        self.assertEqual(v["status"], "host_resource_preflight_passed_only")
        self.assertEqual(v["p12_archive_sha256"], "a" * 64)
        self.assertEqual(v["disk_budgets"]["combined_budget_gib"], 290)
        self.assertEqual(v["disk_budgets"]["volumes"][0]["required_gib"], 290)
        for key in ("bitbake_parse_executed", "bitbake_build_executed",
                    "arm64_elf_produced", "python_package_installed",
                    "rauc_built_or_signed", "robot_validated"):
            self.assertFalse(v[key])

    def test_shared_volume_not_counted_three_times(self):
        with patch("scripts.per_p13b2_host_preflight.available_bytes",
                   return_value=220 * GIB):
            with self.assertRaisesRegex(HostBlocked, "minimum 290 GiB"):
                self.check()

    def test_separate_volume_budgets_check_each_independently(self):
        def dev(path):
            return {self.build: 1, self.dl: 2, self.sstate: 3}[path]
        with patch("scripts.per_p13b2_host_preflight.device_key", side_effect=dev):
            with patch("scripts.per_p13b2_host_preflight.available_bytes",
                       side_effect=lambda path: {
                           self.build: 200 * GIB, self.dl: 30 * GIB,
                           self.sstate: 60 * GIB}[path]):
                result = self.check()
        self.assertEqual(len(result["disk_budgets"]["volumes"]), 3)

    def test_insufficient_independent_download_volume_refused(self):
        with patch("scripts.per_p13b2_host_preflight.device_key",
                   side_effect=lambda p: {self.build: 1, self.dl: 2,
                                          self.sstate: 3}[p]), \
             patch("scripts.per_p13b2_host_preflight.available_bytes",
                   side_effect=lambda p: 29 * GIB if p == self.dl else 300 * GIB):
            with self.assertRaisesRegex(HostBlocked, "downloads"):
                self.check()

    def test_cpu_or_ram_below_declared_budget_refused(self):
        for facts in (
            HostSnapshot("Linux", "x86_64", 2, 32 * GIB, 24 * GIB),
            HostSnapshot("Linux", "x86_64", 8, 8 * GIB, 7 * GIB),
            HostSnapshot("Linux", "x86_64", 8, 32 * GIB, 4 * GIB),
            HostSnapshot("Linux", "aarch64", 8, 32 * GIB, 24 * GIB),
            HostSnapshot("Windows", "x86_64", 8, 32 * GIB, 24 * GIB),
        ):
            with self.subTest(facts=facts), self.assertRaises(HostBlocked):
                self.check(snapshot=facts)

    def test_missing_host_kas_refused_without_install_attempt(self):
        with patch("scripts.per_p13b2_host_preflight.shutil.which",
                   side_effect=lambda name: None if name == "kas" else "/usr/bin/git"):
            with self.assertRaisesRegex(HostBlocked, "kas or git absent"):
                self.check()

    def test_wrong_yocto_or_p12_pin_refused(self):
        with patch("scripts.per_p13b2_host_preflight.check_yocto",
                   side_effect=ValueError("wrong OEM SHA")):
            with self.assertRaises(HostBlocked):
                self.check()
        for change in ({"oem_sha": "f" * 40},
                       {"crates_generated": 567},
                       {"detector_enabled_by_default": True}):
            with self.subTest(change=change):
                with patch("scripts.per_p13b2_host_preflight.verify_p12",
                           return_value={**self.proof, **change}):
                    with self.assertRaises(HostBlocked):
                        self.check()

    def test_wrong_gitlink_or_submodule_refused(self):
        with patch("scripts.per_p13b2_host_preflight._git",
                   return_value="unreviewed git output"):
            with self.assertRaises(HostBlocked):
                self.check()

    def test_cache_inside_repo_denied(self):
        nested = self.project / "build-cache"
        nested.mkdir()
        with self.assertRaises(HostBlocked):
            self.check(build=nested)

    def test_cache_symlink_or_overlapping_paths_denied(self):
        link = self.folder / "linked"
        link.symlink_to(self.build, target_is_directory=True)
        with self.assertRaises(HostBlocked):
            self.check(build=link)
        with self.assertRaises(HostBlocked):
            self.check(dl=self.build)

    def test_missing_staged_source_refused(self):
        with self.assertRaises(HostBlocked):
            self.check(p12=self.folder / "nonexistent")

    def test_no_external_program_or_network_from_fixture(self):
        with patch("scripts.per_p13b2_host_preflight.subprocess.run",
                   side_effect=AssertionError("unexpected process")):
            result = self.check()
        self.assertTrue(result["no_files_written"])

    def test_threshold_values_explicitly_conservative(self):
        self.assertEqual(DISK_BUDGET_GIB, {"build": 200,
                                           "downloads": 30, "sstate": 60})


if __name__ == "__main__":
    unittest.main()
