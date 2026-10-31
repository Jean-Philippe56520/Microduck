"""P15-B6: source integrity and independent process tests (not real OEM)."""
from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest

from microduck_companion.passive_demo import _fictional_unix_server, _frame, _item
from scripts import per_p14a_embedded_wheel as p14a
from scripts import per_p15b6_passive_python_addon as b6

ROOT = Path(__file__).resolve().parents[1]


class P15B6ClosureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="kwipi-p15b6-")
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name)

    def test_01_exact_19_plus_5_audited_source_dependency(self):
        base, extra, edges = b6.select(ROOT)
        self.assertEqual((19, 5), (len(base), len(extra)))
        self.assertEqual((p14a.SELECTED, b6.ADDON), (set(base), set(extra)))
        self.assertFalse(set(base) & set(extra))
        self.assertIn("passive_resilience->offline_resource_budget", edges)
        self.assertIn("passive_fixture_runtime->passive_resilience", edges)

    def test_02_two_stages_byte_identical_and_preserve_19_hashes(self):
        a, b = self.work / "stage-a", self.work / "stage-b"
        m1, m2 = b6.stage(ROOT, a), b6.stage(ROOT, b)
        self.assertEqual(m1, m2)
        self.assertEqual(m1["base_sha256"], {
            p: b6.sha(data) for p, data in p14a.current_source(ROOT).items()
        })
        for name in b6.staged_files(ROOT)[0]:
            self.assertEqual((a / name).read_bytes(), (b / name).read_bytes())
        self.assertEqual(m1, b6.verify(ROOT, a))
        self.assertEqual(m2, b6.verify(ROOT, b))

    def test_03_layer_is_unselected_closed_additive_and_no_service(self):
        files, meta = b6.staged_files(ROOT)
        self.assertEqual(
            {"conf/layer.conf", b6.RECIPE, b6.ARCHIVE, b6.PROVENANCE}, set(files))
        recipe = files[b6.RECIPE].decode()
        self.assertIn('RDEPENDS:' + '$' + '{PN} += "kwipi-companion"', recipe)
        self.assertIn('LICENSE = "CLOSED"', recipe)
        self.assertIn('inherit allarch python3-dir', recipe)
        for banned in ("IMAGE_INSTALL", "SYSTEMD_AUTO_ENABLE", "robotd",
                       "media.frame", "bbappend", "useradd", "groupadd"):
            self.assertNotIn(banned, recipe)
        self.assertIn('LAYERDEPENDS_kwipipassive = "core kwipipy"',
                      files["conf/layer.conf"].decode())
        with tarfile.open(fileobj=io.BytesIO(files[b6.ARCHIVE]), mode="r:gz") as t:
            members = t.getmembers()
            self.assertEqual(set(b6.ADDON), {m.name for m in members})
            self.assertTrue(all(m.isfile() and m.mode == 0o644
                                and m.uid == 0 and m.gid == 0 and m.mtime == 0
                                for m in members))
        for key in ("bitbake_parsed", "target_python_tested", "dev_image_selected",
                    "shipping_image_selected", "systemd_installed",
                    "oem_sensor_validated", "robot_validated",
                    "redistribution_license_reviewed"):
            self.assertIs(meta[key], False)

    def test_04_unreviewed_import_or_missing_module_refused(self):
        base, extra, _ = b6.select(ROOT)
        files = {**base, **extra}
        key = "microduck_companion/passive_fixture_runtime.py"
        files[key] += b"\nfrom .robot_actuator import unsafe\n"
        with self.assertRaises(b6.Refused):
            b6.audit_imports(files)
        files.pop(key)
        with self.assertRaises(b6.Refused):
            b6.audit_imports(files)

    def test_05_linked_source_refused(self):
        root = self.work / "source"
        for name in b6.ADDON:
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, p)
        bad = root / "microduck_companion/passive_resilience.py"
        bad.unlink()
        bad.symlink_to(ROOT / "microduck_companion/passive_resilience.py")
        with self.assertRaises(b6.Refused):
            b6.addon_files(root.resolve())

    def test_06_tamper_of_any_layer_file_is_refused(self):
        for index, name in enumerate((b6.RECIPE, b6.PROVENANCE, b6.ARCHIVE)):
            with self.subTest(name=name):
                dest = self.work / f"layer-{index}"
                b6.stage(ROOT, dest)
                p = dest / name
                p.write_bytes(p.read_bytes() + b"tamper")
                with self.assertRaises(b6.Refused):
                    b6.verify(ROOT, dest)

    def test_07_unknown_file_no_restage_no_source_tree_stage(self):
        dest = self.work / "stage"
        b6.stage(ROOT, dest)
        with self.assertRaises(b6.Refused):
            b6.stage(ROOT, dest)
        (dest / "auto-start.service").write_text("forbidden")
        with self.assertRaises(b6.Refused):
            b6.verify(ROOT, dest)
        with self.assertRaises(b6.Refused):
            b6.stage(ROOT, ROOT / "stage-must-not-exist-b6")

    def isolated_tree(self, *, with_extra: bool):
        p = self.work / ("complete" if with_extra else "base-only")
        for name, raw in p14a.current_source(ROOT).items():
            dest = p / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
        if with_extra:
            files, _ = b6.staged_files(ROOT)
            with tarfile.open(fileobj=io.BytesIO(files[b6.ARCHIVE]), mode="r:gz") as t:
                for m in t.getmembers():
                    (p / m.name).write_bytes(t.extractfile(m).read())
        return p

    def test_08_baseline_19_modules_cannot_import_new_passive_runtime(self):
        p = self.isolated_tree(with_extra=False)
        cp = subprocess.run(
            [sys.executable, "-I", "-S", "-c",
             "import sys;sys.path.insert(0,sys.argv[1]);"
             "from microduck_companion.passive_fixture_runtime import main", str(p)],
            cwd=self.work, capture_output=True, text=True, timeout=8,
        )
        self.assertNotEqual(0, cp.returncode)
        self.assertIn("ModuleNotFoundError", cp.stderr)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux Unix fixture")
    def test_09_isolated_24_module_cli_unix_cycle_single_sqlite(self):
        p = self.isolated_tree(with_extra=True)
        cognitive = self.work / "cognitive.sock"
        media = self.work / "media.sock"
        database = self.work / "memory.sqlite3"
        media_line = (json.dumps({
            "jsonrpc": "2.0", "method": "media.detections",
            "params": {"width": 720, "height": 1280, "took_ms": 63.5,
                       "boxes": [{"x0": 10., "y0": 20., "x1": 110.,
                                  "y1": 220., "score": 1.38}]},
        }, separators=(",", ":")) + "\n").encode()
        script = (
            "import sys\nfrom pathlib import Path\n"
            "sys.path.insert(0,sys.argv[1])\n"
            "import microduck_companion.passive_fixture_runtime as r\n"
            "assert Path(r.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())\n"
            "raise SystemExit(r.main(['--mock-only','--fixture-unix-socket',"
            "sys.argv[2],'--media-fixture-unix-socket',sys.argv[3],"
            "'--database',sys.argv[4],'--cycles','1']))\n"
        )
        with _fictional_unix_server(cognitive, (
                _frame(1, time.monotonic(), _item("ball")),)):
            with _fictional_unix_server(media, (media_line,)):
                cp = subprocess.run(
                    [sys.executable, "-I", "-S", "-c", script,
                     str(p), str(cognitive), str(media), str(database)],
                    cwd=self.work, capture_output=True, text=True, timeout=12,
                )
        self.assertEqual(0, cp.returncode, cp.stderr)
        report = json.loads(cp.stdout)
        self.assertEqual(1, report["experience_memory_instances"])
        self.assertEqual(1, report["observations_stored"])
        self.assertEqual(1, report["media_notifications_received"])
        self.assertEqual(0, report["media_observations_stored"])
        self.assertEqual(0, report["motor_commands_issued"])
        self.assertFalse(report["oem_sensor_validated"])
        with sqlite3.connect(database) as db:
            actual = db.execute(
                "SELECT category,source FROM passive_observation_log").fetchall()
        self.assertEqual([("ball", "mock")], actual)


if __name__ == "__main__":
    unittest.main()
