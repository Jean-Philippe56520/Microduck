"""P15-B1: lifecycle tests on actual host processes and fake Unix sockets ONLY."""
from __future__ import annotations

import json
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from microduck_companion.passive_demo import (
    _fictional_unix_server, _frame, _item,
)
from microduck_companion.passive_fixture_runtime import (
    run_fixture_lifecycle, validate_fixture_args,
)


class FixtureLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sock = self.root / "synthetic.sock"
        self.db = self.root / "memory.sqlite3"

    def _records(self):
        with sqlite3.connect(self.db) as c:
            return c.execute(
                "SELECT category, source FROM passive_observation_log"
            ).fetchall()

    def test_one_real_fake_unix_frame_reuses_one_sqlite(self):
        with _fictional_unix_server(
            self.sock, (_frame(1, time.monotonic(), _item("ball")),)
        ):
            r = run_fixture_lifecycle(self.sock, self.db, cycles=1)
        self.assertEqual("fixture_cycles_finished", r["status"])
        self.assertEqual("untrusted_mock_fixture_unix_only", r["source"])
        self.assertEqual(1, r["cycles_attempted"])
        self.assertEqual(1, r["observations_stored"])
        self.assertEqual(1, r["events_accepted"])
        self.assertEqual(1, r["sqlite_writer_instances"])
        self.assertEqual([("ball", "mock")], self._records())
        self.assertEqual(0, r["motor_commands_issued"])
        self.assertFalse(r["robot_validated"])

    def test_missing_socket_is_idle_without_memory_observation(self):
        r = run_fixture_lifecycle(self.sock, self.db, cycles=1)
        self.assertEqual({"source_unavailable": 1}, r["cycle_statuses"])
        self.assertEqual(0, r["observations_stored"])
        self.assertEqual([], self._records())

    def test_invalid_frame_cannot_create_a_category(self):
        with _fictional_unix_server(self.sock, (b'{"motor":"robot.move"}\n',)):
            r = run_fixture_lifecycle(self.sock, self.db, cycles=1)
        self.assertEqual(0, r["observations_stored"])
        self.assertEqual([], self._records())
        self.assertEqual(0, r["motor_commands_issued"])

    def test_stale_frame_is_not_replayed(self):
        with _fictional_unix_server(
            self.sock, (_frame(1, time.monotonic() - 4, _item("dog")),)
        ):
            r = run_fixture_lifecycle(self.sock, self.db, cycles=1)
        self.assertEqual(0, r["observations_stored"])
        self.assertEqual([], self._records())

    def test_separate_runs_share_one_history_not_live_replay(self):
        with _fictional_unix_server(
            self.sock, (_frame(1, time.monotonic(), _item("ball")),)
        ):
            first = run_fixture_lifecycle(self.sock, self.db, cycles=1)
        second = run_fixture_lifecycle(self.root / "missing.sock", self.db, cycles=1)
        self.assertEqual((1, 0), (
            first["observations_stored"], second["observations_stored"],
        ))
        self.assertEqual([("ball", "mock")], self._records())

    def test_stop_before_initialization_does_not_create_database(self):
        stop = threading.Event()
        stop.set()
        r = run_fixture_lifecycle(
            self.sock, self.db, cycles=16, stop_event=stop,
        )
        self.assertTrue(r["stop_requested"])
        self.assertEqual(0, r["cycles_attempted"])
        self.assertEqual(0, r["sqlite_writer_instances"])
        self.assertFalse(self.db.exists())

    def test_stop_during_wait_does_not_read_a_second_frame(self):
        stop = threading.Event()
        timer = threading.Timer(0.15, stop.set)
        timer.start()
        try:
            r = run_fixture_lifecycle(
                self.sock, self.db, cycles=16, interval_s=0.5,
                stop_event=stop,
            )
        finally:
            timer.join(timeout=2)
        self.assertEqual("fixture_stop_requested", r["status"])
        self.assertEqual(1, r["cycles_attempted"])
        self.assertEqual(0, r["observations_stored"])

    def test_rejects_oem_socket_and_symlink_before_sqlite(self):
        for s in (Path("/run/robotd.sock"), Path("/var/run/mediad.sock"),
                  Path("/dev/fake.sock"), Path("/proc/fake.sock")):
            with self.subTest(path=str(s)), self.assertRaises(ValueError):
                run_fixture_lifecycle(s, self.db, cycles=1)
        self.assertFalse(self.db.exists())
        link = self.root / "forged.sock"
        link.symlink_to("/run/robotd.sock")
        with self.assertRaises(ValueError):
            run_fixture_lifecycle(link, self.db, cycles=1)
        self.assertFalse(self.db.exists())

    def test_invalid_quotas_fail_before_database(self):
        for value in (0, 17, True, "2"):
            with self.subTest(cycles=value), self.assertRaises(ValueError):
                validate_fixture_args(self.sock, self.db, cycles=value, interval_s=0.6)
        for value in (0, float("nan"), float("inf"), 3., True):
            with self.subTest(interval=value), self.assertRaises(ValueError):
                validate_fixture_args(self.sock, self.db, cycles=1, interval_s=value)
        with self.assertRaises(ValueError):
            validate_fixture_args(Path("relative.sock"), self.db,
                                  cycles=1, interval_s=0.6)
        self.assertFalse(self.db.exists())

    def test_cli_requires_explicit_mock_mode_without_creating_sqlite(self):
        p = subprocess.run(
            [sys.executable, "-m", "microduck_companion.passive_fixture_runtime",
             "--fixture-unix-socket", str(self.sock), "--database", str(self.db)],
            capture_output=True, text=True, timeout=12,
        )
        self.assertEqual(2, p.returncode)
        self.assertFalse(self.db.exists())

    def test_real_subprocess_uses_one_fixture_then_exits(self):
        with _fictional_unix_server(
            self.sock, (_frame(1, time.monotonic(), _item("chair")),)
        ):
            p = subprocess.run(
                [sys.executable, "-m", "microduck_companion.passive_fixture_runtime",
                 "--mock-only", "--fixture-unix-socket", str(self.sock),
                 "--database", str(self.db), "--cycles", "1"],
                capture_output=True, text=True, timeout=12,
            )
        self.assertEqual(0, p.returncode, p.stderr)
        payload = json.loads(p.stdout)
        self.assertEqual(1, payload["cycles_attempted"])
        self.assertEqual(1, payload["observations_stored"])
        self.assertFalse(payload["action_executed"])
        self.assertEqual([("chair", "mock")], self._records())

    @unittest.skipUnless(sys.platform.startswith("linux"), "SIGTERM on Linux only")
    def test_real_sigterm_stops_a_bounded_subprocess(self):
        p = subprocess.Popen(
            [sys.executable, "-m", "microduck_companion.passive_fixture_runtime",
             "--mock-only", "--fixture-unix-socket", str(self.sock),
             "--database", str(self.db), "--cycles", "16",
             "--interval-s", "2.0"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            deadline = time.monotonic() + 8
            while not self.db.exists() and time.monotonic() < deadline:
                if p.poll() is not None:
                    self.fail("fixture runtime ended before SIGTERM test")
                time.sleep(0.025)
            self.assertTrue(self.db.exists(), "fixture runtime did not start")
            time.sleep(0.1)
            p.send_signal(signal.SIGTERM)
            out, err = p.communicate(timeout=7)
        finally:
            if p.poll() is None:
                p.kill()
                p.communicate(timeout=3)
        self.assertEqual(0, p.returncode, err)
        payload = json.loads(out)
        self.assertEqual("fixture_stop_requested", payload["status"])
        self.assertLess(payload["cycles_attempted"], 16)
        self.assertEqual(0, payload["motor_commands_issued"])


if __name__ == "__main__":
    unittest.main()
