"""P14B: effective Yocto Python metadata and do_package file gates.

These tests use deliberately synthetic BitBake values/files. Separate CI must
run the OEM pinned kas/BitBake tasks before a real-result claim.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.per_p13a_bitbake_env_gate import EnvRefused
from scripts.per_p14b_yocto_python_layer import LAYER, RUNTIME, SRC_NAME, stage
from scripts.per_p14b_yocto_package_gate import effective_variables, validate_package

ROOT = Path(__file__).resolve().parents[1]


class P14BPackageGateFixtureTests(unittest.TestCase):
    def setUp(self):
        self.context = tempfile.TemporaryDirectory()
        self.addCleanup(self.context.cleanup)
        self.dir = Path(self.context.name)
        self.layer = self.dir / LAYER
        self.provenance = stage(ROOT, self.layer)
        self.work = self.dir / "build/tmp/work"
        self.source = self.work / "unpack/kwipi-companion-0.2.0a1"
        self.source.mkdir(parents=True)
        self.pkg = self.work / "packages-split"
        self.target = (self.pkg / "kwipi-companion" /
                       "usr/lib/python3.14/site-packages/microduck_companion")
        self.target.mkdir(parents=True)
        for p in self.provenance["source_sha256"]:
            if p.startswith("microduck_companion/") and p.endswith(".py"):
                shutil.copyfile(ROOT / p, self.target / Path(p).name)
        self.env = "\n".join((
            'PV="0.2.0a1"',
            'LICENSE="CLOSED"',
            f'SRC_URI="file://{SRC_NAME};subdir=kwipi-companion-0.2.0a1;name=kwipipy"',
            f'S="{self.source}"',
            f'UNPACKDIR="{self.work}/unpack"',
            'BP="kwipi-companion-0.2.0a1"',
            f'PKGDEST="{self.pkg}"',
            f'TMPDIR="{self.work}"',
            'PYTHON_SITEPACKAGES_DIR="/usr/lib/python3.14/site-packages"',
            f'BBLAYERS="{self.layer}"',
            'RDEPENDS:kwipi-companion="' + " ".join(sorted(RUNTIME)) + '"',
        )) + "\n"

    def test_nominal_fixture_marks_bytes_not_bitbake_proof(self):
        result = validate_package(ROOT, self.layer, self.env)
        self.assertEqual(result["python_modules_packaged"], 19)
        self.assertTrue(result["package_source_bytes_verified"])
        self.assertFalse(result["bitbake_task_execution_attested_by_this_script"])
        for k in ("rootfs_installed", "systemd_installed",
                  "signed_release", "robot_validated"):
            self.assertFalse(result[k])

    def test_missing_one_module_fails(self):
        (self.target / "autonomy.py").unlink()
        with self.assertRaises(EnvRefused):
            validate_package(ROOT, self.layer, self.env)

    def test_changed_module_fails(self):
        with (self.target / "sim_ipc.py").open("ab") as f:
            f.write(b"# forgery")
        with self.assertRaises(EnvRefused):
            validate_package(ROOT, self.layer, self.env)

    def test_unexpected_model_in_package_fails(self):
        (self.target / "kwipi_seg.rknn").write_bytes(b"new unlicensed model")
        with self.assertRaises(EnvRefused):
            validate_package(ROOT, self.layer, self.env)

    def test_wrong_runtime_dependency_fails(self):
        altered = self.env.replace("python3-sqlite3", "python3-unknown")
        with self.assertRaises(EnvRefused):
            effective_variables(altered, self.layer)

    def test_wrong_python_version_fails(self):
        altered = self.env.replace("/python3.14/", "/python3.12/")
        with self.assertRaises(EnvRefused):
            effective_variables(altered, self.layer)

    def test_different_license_fails(self):
        altered = self.env.replace('LICENSE="CLOSED"', 'LICENSE="MIT"')
        with self.assertRaises(EnvRefused):
            effective_variables(altered, self.layer)

    def test_original_source_not_single_tar_fails(self):
        altered = self.env.replace(
            "name=kwipipy",
            "name=kwipipy git://example.com/other.git",
        )
        with self.assertRaises(EnvRefused):
            effective_variables(altered, self.layer)

    def test_pkgdest_outside_work_fails(self):
        altered = self.env.replace(f'PKGDEST="{self.pkg}"',
                                   f'PKGDEST="{self.layer}"')
        with self.assertRaises(EnvRefused):
            validate_package(ROOT, self.layer, altered)

    def test_bblayers_must_resolve_exact_layer(self):
        altered = self.env.replace(f'BBLAYERS="{self.layer}"',
                                   'BBLAYERS="/tmp/unrelated-layer"')
        with self.assertRaises(EnvRefused):
            effective_variables(altered, self.layer)


if __name__ == "__main__":
    unittest.main()
