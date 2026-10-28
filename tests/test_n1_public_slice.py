"""N1b fixture-only tests. No real Companion or robot code is imported."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from scripts.n1_inventory import collect
from scripts.n1_public_slice import build_public_slice, select_public_closure


def fixture(root: Path, *, core: str = "VALUE = 3\n", init: str = "from .core import VALUE\n"):
    pkg = root / "microduck_companion"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(init, encoding="utf-8")
    (pkg / "core.py").write_text(core, encoding="utf-8")
    (pkg / "sim_motor.py").write_text("raise RuntimeError('MOTOR MUST NEVER IMPORT')\n", encoding="utf-8")
    return pkg


class N1PublicSliceTests(unittest.TestCase):
    def test_isolated_archive_without_simulator_and_with_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pkg = fixture(root)
            baseline = {p.name: p.read_bytes() for p in pkg.iterdir()}
            output = root / "only-public-api.zip"
            report = build_public_slice(root, output)
            self.assertEqual(report["selected_python_modules"], 2)
            self.assertEqual(report["excluded_python_modules"], 1)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(sorted(archive.namelist()), [
                    "microduck_companion/__init__.py", "microduck_companion/core.py"])
            # -I excludes the source checkout from sys.path, only the isolated ZIP is inserted.
            code = "import sys; sys.path.insert(0, sys.argv[1]); import microduck_companion as m; assert m.VALUE == 3"
            subprocess.run([sys.executable, "-I", "-B", "-c", code, str(output)],
                           check=True, cwd=root, timeout=10)
            self.assertEqual({p.name: p.read_bytes() for p in pkg.iterdir()}, baseline)

    def test_missing_static_import_refused_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root, init="from .missing import THING\n")
            output = root / "never.zip"
            with self.assertRaisesRegex(ValueError, "Unresolved"):
                build_public_slice(root, output)
            self.assertFalse(output.exists())

    def test_dynamic_import_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root, core="import importlib\nimportlib.import_module('anything')\n")
            with self.assertRaisesRegex(ValueError, "Dynamic import"):
                select_public_closure(collect(root))

    def test_motor_rpc_marker_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root, core="CALL = 'robot.move'\n")
            with self.assertRaisesRegex(ValueError, "Motor RPC marker"):
                select_public_closure(collect(root))

    def test_forbidden_simulator_dependency_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root, init="from .sim_motor import ANYTHING\n")
            with self.assertRaisesRegex(ValueError, "Simulator"):
                select_public_closure(collect(root))


if __name__ == "__main__":
    unittest.main()
