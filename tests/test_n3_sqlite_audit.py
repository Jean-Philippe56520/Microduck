"""N3 source-only SQLite tests: positive and adversarial fixtures."""
from pathlib import Path
import tempfile
import unittest

from scripts.n3_sqlite_audit import (
    enforce_non_destructive_boundaries, scan_source, scan_tree,
)


def example_source(root: Path) -> Path:
    package = root / "microduck_companion"
    package.mkdir()
    (package / "episodic_memory.py").write_text(
        "import sqlite3\n"
        "def initialize():\n"
        "    db = sqlite3.connect(':memory:')\n"
        "    db.executescript('CREATE TABLE objects(id INTEGER);')\n"
        "    return db\n", encoding="utf-8")
    (package / "category_semantics.py").write_text(
        "def trim(db):\n"
        "    db.execute('CREATE TABLE IF NOT EXISTS f4a_property_hypotheses(id INTEGER,active INTEGER)')\n"
        "    db.execute('DELETE FROM f4a_property_hypotheses WHERE active=1 AND id>10')\n",
        encoding="utf-8")
    (package / "compact_multimodal_memory.py").write_text(
        "def create(db):\n"
        "    db.execute('CREATE TABLE IF NOT EXISTS m1a_compact_patterns (id INTEGER)')\n",
        encoding="utf-8")
    (package / "multiview_pattern_memory.py").write_text(
        "def create(db):\n"
        "    db.execute('CREATE TABLE m1b_groups(id INTEGER); CREATE TABLE m1b_signatures(id INTEGER);')\n",
        encoding="utf-8")
    (package / "kwipi_journal.py").write_text(
        "import sqlite3\n"
        "def history(path):\n"
        "    db = sqlite3.connect(path + '?mode=ro', uri=True)\n"
        "    db.execute('PRAGMA query_only=ON')\n"
        "    return db\n", encoding="utf-8")
    return package


class N3SqliteInventoryTests(unittest.TestCase):
    def test_approved_single_writer_and_readonly_journal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = example_source(root)
            (package / "mock_cycles.py").write_text(
                "def write(c):\n"
                "    c.execute('UPDATE objects SET id=? WHERE id=?', (1,2))\n",
                encoding="utf-8")
            report = scan_tree(root)
            enforce_non_destructive_boundaries(report)
            self.assertEqual(report["table_count"], 5)
            self.assertEqual(len(report["connection_sites"]), 2)
            self.assertEqual(report["connection_sites"][1]["mode"], "read_only_uri")
            self.assertEqual(report["cross_module_writes"], [
                {"table": "objects", "module": "mock_cycles.py",
                 "owners": ["episodic_memory.py"]}
            ])
            self.assertEqual(report["destructive_sites"], [])

    def test_second_write_connection_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = example_source(root)
            (package / "other.py").write_text(
                "import sqlite3 as sql\n"
                "def bad(): return sql.connect('second.db')\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "second writable"):
                enforce_non_destructive_boundaries(scan_tree(root))

    def test_ro_uri_requires_uri_true(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = example_source(root)
            path = package / "kwipi_journal.py"
            path.write_text(path.read_text().replace("uri=True", "uri=False"),
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "second writable"):
                enforce_non_destructive_boundaries(scan_tree(root))

    def test_unbounded_correction_deletion_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = example_source(root)
            path = package / "category_semantics.py"
            path.write_text(path.read_text().replace("WHERE active=1 AND id>10", "WHERE id>10"),
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "corrections"):
                enforce_non_destructive_boundaries(scan_tree(root))

    def test_drop_table_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = example_source(root)
            (package / "drop.py").write_text(
                "def wrong(c): c.execute('DROP TABLE m1b_signatures')\n",
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Destructive SQL"):
                enforce_non_destructive_boundaries(scan_tree(root))

    def test_dynamic_sql_is_flagged_as_uncertain(self):
        report = scan_source("def q(c, table):\n    c.execute(f'SELECT * FROM {table}')\n",
                             "dynamic.py")
        self.assertEqual(report["sql_sites"], [])
        self.assertEqual(report["dynamic_sql_sites"], [
            {"module": "dynamic.py", "line": 2, "method": "execute"}
        ])

    def test_invalid_syntax_is_not_silently_skipped(self):
        with self.assertRaises(SyntaxError):
            scan_source("def nope(:\n", "invalid.py")


if __name__ == "__main__":
    unittest.main()
