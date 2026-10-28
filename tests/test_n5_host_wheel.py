"""N5: source-only negative gates and temporary staging; no robot connection."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
import zipfile

from scripts import n5_host_wheel as n5
from scripts.n1_inventory import collect
from scripts.n1_public_slice import select_public_closure


ROOT = Path(__file__).resolve().parents[1]


def fixture(folder: Path) -> Path:
    root = folder / "repo"
    pkg = root / "microduck_companion"
    pkg.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools>=68"]\n'
        'build-backend = "setuptools.build_meta"\n'
        '[project]\nname = "microduck-companion"\nversion = "0.2.0"\n',
        encoding="utf-8")
    (pkg / "__init__.py").write_text("from .core import VALUE\n", encoding="utf-8")
    (pkg / "core.py").write_text("VALUE = 42\n", encoding="utf-8")
    return root


SMALL_ALLOWLIST = frozenset({
    "microduck_companion/__init__.py", "microduck_companion/core.py",
})


class N5HostWheelTests(TestCase):
    def test_real_public_closure_exactly_reviewed_modules(self):
        inventory = collect(ROOT)
        selection = select_public_closure(inventory)
        self.assertEqual(inventory["module_count"], 121)
        self.assertEqual({x["path"] for x in selection}, n5.APPROVED_FILES)
        self.assertEqual(len(selection), 19)
        self.assertEqual(
            {x["path"] for x in selection if x["path"].split("/")[-1].startswith("mock_")},
            n5.LAB_EXCEPTIONS,
        )
        self.assertFalse(any(m["dynamic_import"] for m in selection))
        self.assertFalse(any(m["contains_motor_rpc_literal"] for m in selection))

    def test_stage_copies_only_allowlisted_bytes_outside_repository(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            source = fixture(base)
            staged = base / "candidate"
            with patch.object(n5, "APPROVED_FILES", SMALL_ALLOWLIST):
                report = n5.stage_probe(source, staged)
            self.assertEqual(report["selected_module_count"], 2)
            self.assertEqual(report["excluded_from_probe_count"], 0)
            self.assertEqual(report["probe_distribution"], n5.DIST_NAME)
            self.assertEqual(
                {p.relative_to(staged).as_posix() for p in staged.rglob("*") if p.is_file()},
                {*SMALL_ALLOWLIST, "pyproject.toml"},
            )
            self.assertEqual(
                (staged / "microduck_companion/core.py").read_bytes(),
                (source / "microduck_companion/core.py").read_bytes(),
            )
            self.assertNotIn("upstream", str(staged))
            self.assertIn("HOST", n5.PROBE_PYPROJECT.upper())

    def test_added_internal_dependency_fails_closed(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            source = fixture(base)
            pkg = source / "microduck_companion"
            (pkg / "core.py").write_text("from .extra import FLAG\nVALUE = FLAG\n")
            (pkg / "extra.py").write_text("FLAG = 42\n")
            staged = base / "candidate"
            with patch.object(n5, "APPROVED_FILES", SMALL_ALLOWLIST):
                with self.assertRaisesRegex(ValueError, "allowlist"):
                    n5.stage_probe(source, staged)
            self.assertFalse(staged.exists())

    def test_dynamic_import_fails_closed(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            source = fixture(base)
            (source / "microduck_companion/core.py").write_text(
                "import importlib\nVALUE=importlib.import_module('os')\n"
            )
            with patch.object(n5, "APPROVED_FILES", SMALL_ALLOWLIST):
                with self.assertRaisesRegex(ValueError, "Dynamic import"):
                    n5.stage_probe(source, base / "candidate")

    def test_motor_rpc_marker_fails_closed(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            source = fixture(base)
            (source / "microduck_companion/core.py").write_text("VALUE = 'robot.do'\n")
            with patch.object(n5, "APPROVED_FILES", SMALL_ALLOWLIST):
                with self.assertRaisesRegex(ValueError, "Motor RPC marker"):
                    n5.stage_probe(source, base / "candidate")

    def test_symlink_fails_closed(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            source = fixture(base)
            other = base / "other.py"
            other.write_text("VALUE = 42\n")
            core = source / "microduck_companion/core.py"
            core.unlink()
            core.symlink_to(other)
            with patch.object(n5, "APPROVED_FILES", SMALL_ALLOWLIST):
                with self.assertRaisesRegex(ValueError, "regular in-tree"):
                    n5.stage_probe(source, base / "candidate")

    def test_staging_inside_source_or_nonempty_path_refused(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            source = fixture(base)
            with patch.object(n5, "APPROVED_FILES", SMALL_ALLOWLIST):
                with self.assertRaisesRegex(ValueError, "outside"):
                    n5.stage_probe(source, source / "candidate")
                stage = base / "candidate"
                stage.mkdir()
                (stage / "sentinel").write_text("keep")
                with self.assertRaisesRegex(ValueError, "must be empty"):
                    n5.stage_probe(source, stage)
                self.assertEqual((stage / "sentinel").read_text(), "keep")

    def test_wheel_source_byte_mismatch_refused(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            root = fixture(base)
            fake = base / "fake.whl"
            normal = base / "normal.whl"
            with zipfile.ZipFile(fake, "w") as z:
                z.write(root / "microduck_companion/__init__.py", "microduck_companion/__init__.py")
                z.writestr("microduck_companion/core.py", "VALUE = 99\n")
            with zipfile.ZipFile(normal, "w") as z:
                z.write(root / "microduck_companion/__init__.py", "microduck_companion/__init__.py")
                z.write(root / "microduck_companion/core.py", "microduck_companion/core.py")
                z.writestr("microduck_companion/lab.py", "LAB = True\n")
            (root / "microduck_companion/lab.py").write_text("LAB = True\n")
            with patch.object(n5, "APPROVED_FILES", SMALL_ALLOWLIST):
                with self.assertRaisesRegex(ValueError, "source bytes"):
                    n5.inspect_probe(root, fake, normal)


if __name__ == "__main__":
    import unittest
    unittest.main()
