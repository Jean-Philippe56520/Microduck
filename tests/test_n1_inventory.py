"""N1 fixture-only inventory tests: never import or execute target modules."""
import tempfile
import unittest
from pathlib import Path
from scripts.n1_inventory import collect, inspect_wheel, category
import zipfile


class N1InventoryTests(unittest.TestCase):
    def test_lab_classification_only_candidate(self):
        self.assertEqual(category("sim_walk_trial.py"), "lab_candidate")
        self.assertEqual(category("autonomy_demo.py"), "lab_candidate")
        self.assertEqual(category("autonomy.py"), "review_required")

    def test_import_edges_and_dynamic_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "microduck_companion"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")
            (pkg / "one.py").write_text(
                "from .two import Thing\nfrom . import two\nimport importlib\n"
                "importlib.import_module('microduck_companion.two')\n"
                "if __name__ == '__main__': print('not executed')\n")
            (pkg / "two.py").write_text("class Thing: pass\n")
            got = collect(root)
            one = next(x for x in got["modules"] if x["module"].endswith(".one"))
            self.assertEqual(one["internal_imports"], ["microduck_companion.two"])
            self.assertFalse(one["internal_imports_missing"])
            self.assertTrue(one["dynamic_import"])
            self.assertTrue(one["main_guard"])
            self.assertEqual(got["module_count"], 3)

    def test_read_only_wheel_inspection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "microduck_companion"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("")
            (pkg / "sim_probe.py").write_text("raise RuntimeError('must not import')\n")
            wheel = root / "candidate.whl"
            with zipfile.ZipFile(wheel, "w") as z:
                for p in pkg.iterdir():
                    z.write(p, p.relative_to(root).as_posix())
            m = collect(root)
            w = inspect_wheel(wheel, m)
            self.assertEqual(w["python_file_count"], 2)
            self.assertEqual(w["absent_source_modules"], [])
            self.assertIn("microduck_companion/sim_probe.py", w["lab_candidates_included"])

    def test_syntax_error_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "microduck_companion"
            pkg.mkdir()
            (pkg / "__init__.py").write_text("def broken(:\n")
            with self.assertRaises(SyntaxError):
                collect(Path(tmp))


if __name__ == "__main__":
    unittest.main()
