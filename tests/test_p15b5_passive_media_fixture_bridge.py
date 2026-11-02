"""P15-B5: real Unix mock transport and P15-B1 sidecar separation tests.

NO robot, camera, network, WebRTC, model, OEM /run permissions, motor, or
second SQLite. The source wire is only an untrusted P15-B4-shaped fixture.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import signal
import socket
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
from microduck_companion.passive_fixture_runtime import run_fixture_lifecycle
from microduck_companion.passive_media_fixture_reader import (
    MediaFixtureReader, validate_media_fixture_path,
)

UNIX = hasattr(socket, "AF_UNIX")


def packet(boxes=1, *, score=1.38) -> bytes:
    data = {
        "jsonrpc": "2.0",
        "method": "media.detections",
        "params": {
            "width": 720, "height": 1280, "took_ms": 63.5,
            "boxes": [{
                "x0": 10.0, "y0": 20.0, "x1": 110.0, "y1": 220.0,
                "score": score,
            } for _ in range(boxes)],
        },
    }
    return (json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n").encode()


@contextmanager
def push_only_server(path: Path, response: bytes, *, delay_s: float = 0.0):
    """A real local Unix listener that records whether a client sends requests."""
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.settimeout(1.5)
    listener.bind(str(path))
    listener.listen(1)
    written = []
    stop = threading.Event()
    errors = []

    def worker():
        try:
            with listener.accept()[0] as conn:
                conn.settimeout(0.05)
                try:
                    data = conn.recv(256)
                except socket.timeout:
                    data = b""
                written.append(data)
                if delay_s:
                    stop.wait(delay_s)
                if response:
                    conn.sendall(response)
        except OSError as exc:
            if not stop.is_set():
                errors.append(type(exc).__name__)

    job = threading.Thread(target=worker, daemon=True)
    job.start()
    try:
        yield written
    finally:
        stop.set()
        listener.close()
        job.join(timeout=2)
        if job.is_alive():
            raise AssertionError("fake local mediad server did not exit")
        if errors:
            raise AssertionError(f"fixture server errors: {errors}")


@unittest.skipUnless(UNIX, "Unix socket fixture tests require AF_UNIX")
class MediaFixtureReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / "media.sock"

    def test_01_one_oem_shape_line_is_unknown_and_no_request_is_written(self):
        with push_only_server(self.media, packet()) as sent:
            result = MediaFixtureReader(self.media).read()
        self.assertEqual([b""], sent)
        self.assertEqual("shape_only_untrusted", result.status)
        self.assertTrue(result.notification_valid_shape_only)
        self.assertEqual(1, result.reported_boxes)
        self.assertEqual("unknown", result.category)
        self.assertFalse(result.physical_sensor_verified)
        self.assertFalse(result.fresh_capture_verified)
        self.assertEqual(0, result.motor_commands_issued)
        self.assertEqual(0, result.camera_frames_requested)
        self.assertEqual(0, result.memory_writes)
        self.assertNotIn("score", str(result))
        self.assertNotIn("1.38", str(result))

    def test_02_zero_boxes_is_not_missing_service_or_proven_empty_room(self):
        with _fictional_unix_server(self.media, (packet(0),)):
            empty = MediaFixtureReader(self.media).read()
        missing = MediaFixtureReader(self.root / "no-socket.sock").read()
        self.assertEqual("empty_look_untrusted", empty.status)
        self.assertTrue(empty.notification_valid_shape_only)
        self.assertEqual(0, empty.reported_boxes)
        self.assertEqual("unavailable_or_invalid", missing.status)
        self.assertFalse(missing.notification_valid_shape_only)

    def test_03_video_motor_seg_and_frame_notifications_are_refused(self):
        for method, params in (
            ("media.video", {
                "width": 720, "height": 1280, "rotate": 0,
                "mono_ns": 1, "real_ns": 1,
            }),
            ("robot.move", {}),
            ("robot.do", {}),
            ("media.frame", {}),
            ("media.region_candidates", {}),
            ("media.sound", {}),
        ):
            with self.subTest(method=method):
                raw = (json.dumps({"jsonrpc": "2.0", "method": method,
                                   "params": params}) + "\n").encode()
                path = self.root / f"test-{method.replace('.', '-')}.sock"
                with _fictional_unix_server(path, (raw,)):
                    result = MediaFixtureReader(path).read()
                self.assertEqual("unavailable_or_invalid", result.status)
                self.assertEqual("unknown", result.category)
                self.assertEqual(0, result.memory_writes)

    def test_04_duplicate_nan_invalid_boxes_trailing_and_bulk_are_rejected(self):
        bad = [
            b'{"jsonrpc":"2.0","jsonrpc":"2.0","method":"media.detections","params":{}}\n',
            packet().replace(b"1.38", b"NaN"),
            packet().replace(b'"x1":110.0', b'"x1":5.0'),
            packet().replace(b'"score":1.38', b'"score":-1.0'),
            packet().replace(b'"width":720', b'"width":true'),
            packet(33),
            packet() + packet(),
            b"x" * 4097 + b"\n",
            b"{\n",
        ]
        for index, data in enumerate(bad):
            with self.subTest(index=index):
                path = self.root / f"invalid-{index}.sock"
                with _fictional_unix_server(path, (data,)):
                    result = MediaFixtureReader(path).read()
                self.assertEqual("unavailable_or_invalid", result.status)
                self.assertEqual(0, result.reported_boxes)

    def test_05_dedicated_reader_rate_limits_repeated_connections(self):
        stamps = iter((100.0, 100.1, 99.0))
        with _fictional_unix_server(self.media, (packet(),)):
            reader = MediaFixtureReader(self.media, clock=lambda: next(stamps))
            self.assertEqual("shape_only_untrusted", reader.read().status)
            self.assertEqual("rate_limited", reader.read().status)
            self.assertEqual("clock_reset", reader.read().status)

    def test_06_silent_or_slow_source_fails_without_stale_replay(self):
        with push_only_server(self.media, packet(), delay_s=0.15):
            report = MediaFixtureReader(self.media, timeout_s=0.08).read()
        self.assertEqual("unavailable_or_invalid", report.status)
        self.assertEqual(0, report.reported_boxes)
        self.assertFalse(report.notification_valid_shape_only)

    def test_07_oem_paths_symlink_alias_and_invalid_reader_limits_refused(self):
        banned = [
            Path("/run/mediad/kwipi/detections.sock"),
            Path("/var/run/mediad/kwipi/detections.sock"),
            Path("/run/robotd.sock"),
            Path("/dev/fake.sock"), Path("/proc/fake.sock"),
            Path("relative.sock"),
        ]
        for p in banned:
            with self.subTest(path=str(p)), self.assertRaises(ValueError):
                validate_media_fixture_path(p)
        link = self.root / "link.sock"
        link.symlink_to(self.media)
        with self.assertRaises(ValueError):
            MediaFixtureReader(link)
        parent_link = self.root / "dir-link"
        actual = self.root / "actual"
        actual.mkdir()
        parent_link.symlink_to(actual)
        with self.assertRaises(ValueError):
            MediaFixtureReader(parent_link / "s.sock")
        for value in (0, 0.5, True, float("nan"), "0.2"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MediaFixtureReader(self.media, timeout_s=value)
        with self.assertRaises(TypeError):
            MediaFixtureReader(self.media, clock=None)


@unittest.skipUnless(UNIX, "requires real Linux/Unix fixture sockets")
class SidecarLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cognitive = self.root / "cognitive.sock"
        self.media = self.root / "media.sock"
        self.db = self.root / "one-memory.sqlite3"

    def records(self):
        with sqlite3.connect(self.db) as db:
            return db.execute("SELECT category,source FROM passive_observation_log").fetchall()

    def test_08_one_process_has_single_sqlite_and_no_media_learning(self):
        with _fictional_unix_server(self.cognitive, (
                _frame(1, time.monotonic(), _item("ball")),)):
            with _fictional_unix_server(self.media, (packet(),)):
                r = run_fixture_lifecycle(
                    self.cognitive, self.db, cycles=1,
                    media_fixture_path=self.media)
        self.assertEqual(1, r["experience_memory_instances"])
        self.assertEqual([("ball", "mock")], self.records())
        self.assertEqual(1, r["observations_stored"])
        self.assertEqual(1, r["events_accepted"])
        self.assertEqual(1, r["media_notifications_received"])
        self.assertEqual({"shape_only_untrusted": 1}, r["media_statuses"])
        self.assertEqual(0, r["media_categories_recognized"])
        self.assertEqual(0, r["media_observations_stored"])
        self.assertFalse(r["media_sensor_verified"])
        self.assertEqual(0, r["motor_commands_issued"])
        self.assertEqual(0, r["camera_frames_captured"])
        self.assertEqual("untrusted_oem_shape_unix_fixture_only", r["media_source"])
        self.assertNotIn("x0", json.dumps(r))
        self.assertNotIn('"score":', json.dumps(r))
        self.assertNotIn('"raw_score":', json.dumps(r))

    def test_09_media_only_cannot_create_any_cognitive_category(self):
        with _fictional_unix_server(self.media, (packet(),)):
            r = run_fixture_lifecycle(
                self.cognitive, self.db, cycles=1,
                media_fixture_path=self.media)
        self.assertEqual(0, r["observations_stored"])
        self.assertEqual(0, r["events_accepted"])
        self.assertEqual(1, r["media_notifications_received"])
        self.assertEqual({"source_unavailable": 1}, r["cycle_statuses"])
        self.assertEqual([], self.records())

    def test_10_invalid_media_cannot_modify_the_valid_mock_memory(self):
        with _fictional_unix_server(self.cognitive, (
                _frame(1, time.monotonic(), _item("toy")),)):
            with _fictional_unix_server(self.media, (
                    b'{"jsonrpc":"2.0","method":"robot.do","params":{}}\n',)):
                r = run_fixture_lifecycle(
                    self.cognitive, self.db, cycles=1,
                    media_fixture_path=self.media)
        self.assertEqual([("toy", "mock")], self.records())
        self.assertEqual(1, r["observations_stored"])
        self.assertEqual(0, r["media_notifications_received"])
        self.assertEqual({"unavailable_or_invalid": 1}, r["media_statuses"])

    def test_11_preflight_rejects_oem_duplicate_or_link_before_sqlite(self):
        link = self.root / "forged.sock"
        link.symlink_to("/run/mediad/kwipi/detections.sock")
        for p in (Path("/run/mediad/kwipi/detections.sock"),
                  link, self.cognitive, Path("relative.sock")):
            with self.subTest(path=str(p)), self.assertRaises(ValueError):
                run_fixture_lifecycle(
                    self.cognitive, self.db, cycles=1, media_fixture_path=p)
        self.assertFalse(self.db.exists())

    def test_12_stop_before_start_opens_neither_socket_nor_sqlite(self):
        stop = threading.Event()
        stop.set()
        r = run_fixture_lifecycle(
            self.cognitive, self.db, cycles=16, stop_event=stop,
            media_fixture_path=self.media,
        )
        self.assertEqual("fixture_stop_requested", r["status"])
        self.assertEqual(0, r["media_notifications_received"])
        self.assertEqual({}, r["media_statuses"])
        self.assertEqual(0, r["experience_memory_instances"])
        self.assertFalse(self.db.exists())

    def test_13_cli_dual_mock_sources_terminates_without_motor(self):
        with _fictional_unix_server(self.cognitive, (
                _frame(1, time.monotonic(), _item("ball")),)):
            with _fictional_unix_server(self.media, (packet(),)):
                cp = subprocess.run([
                    sys.executable, "-m", "microduck_companion.passive_fixture_runtime",
                    "--mock-only",
                    "--fixture-unix-socket", str(self.cognitive),
                    "--media-fixture-unix-socket", str(self.media),
                    "--database", str(self.db), "--cycles", "1",
                ], capture_output=True, text=True, timeout=12)
        self.assertEqual(0, cp.returncode, cp.stderr)
        report = json.loads(cp.stdout)
        self.assertEqual(1, report["media_notifications_received"])
        self.assertEqual(1, report["observations_stored"])
        self.assertEqual([("ball", "mock")], self.records())
        self.assertFalse(report["action_executed"])
        self.assertFalse(report["oem_sensor_validated"])

    def test_14_cli_rejects_actual_oem_path_and_omitted_mock_flag(self):
        for extra in (
            ["--mock-only", "--media-fixture-unix-socket",
             "/run/mediad/kwipi/detections.sock"],
            ["--media-fixture-unix-socket", str(self.media)],
        ):
            cp = subprocess.run([
                sys.executable, "-m", "microduck_companion.passive_fixture_runtime",
                "--fixture-unix-socket", str(self.cognitive),
                "--database", str(self.db), "--cycles", "1",
                *extra,
            ], capture_output=True, text=True, timeout=12)
            self.assertEqual(2, cp.returncode)
            self.assertFalse(self.db.exists())
            self.assertNotIn("robot.move", cp.stderr)

    @unittest.skipUnless(sys.platform.startswith("linux"), "SIGTERM on Linux")
    def test_15_signal_stops_shared_cycle_without_new_media_reads(self):
        cp = subprocess.Popen([
            sys.executable, "-m", "microduck_companion.passive_fixture_runtime",
            "--mock-only",
            "--fixture-unix-socket", str(self.cognitive),
            "--media-fixture-unix-socket", str(self.media),
            "--database", str(self.db),
            "--cycles", "16", "--interval-s", "2.0",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 8.0
            while not self.db.exists() and time.monotonic() < deadline:
                if cp.poll() is not None:
                    self.fail("fixture process terminated unexpectedly")
                time.sleep(.02)
            self.assertTrue(self.db.exists())
            time.sleep(.1)
            cp.send_signal(signal.SIGTERM)
            out, err = cp.communicate(timeout=7)
        finally:
            if cp.poll() is None:
                cp.kill()
                cp.communicate(timeout=3)
        self.assertEqual(0, cp.returncode, err)
        payload = json.loads(out)
        self.assertTrue(payload["stop_requested"])
        self.assertLess(payload["cycles_attempted"], 16)
        self.assertEqual(0, payload["media_notifications_received"])
        self.assertEqual(0, payload["motor_commands_issued"])


def b12_packet(*, look_seq=1, capture_ns=100_000_000_000, boxes=1) -> bytes:
    data = json.loads(packet(boxes))
    data["params"].update({
        "look_seq": look_seq,
        "captured_at_monotonic_ns": capture_ns,
        "captured_at_unix_us": 1_800_000_000_000_000,
    })
    return (json.dumps(data, separators=(",", ":")) + "\n").encode()


@unittest.skipUnless(UNIX, "requires Linux/Unix fixture transport")
class B12LocalFixtureBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.media = Path(self.temp.name) / "b12.sock"

    def test_new_b12_fixture_requires_explicit_opt_in(self):
        raw = b12_packet(capture_ns=100_000_000_000)
        stamps = iter((100.1, 100.2))
        with push_only_server(self.media, raw) as sent:
            r = MediaFixtureReader(self.media, b12_local_shape=True,
                                   clock=lambda: next(stamps)).read()
        self.assertEqual([b""], sent)
        self.assertEqual("shape_only_untrusted", r.status)
        self.assertEqual(1, r.reported_boxes)
        self.assertFalse(r.physical_sensor_verified)
        self.assertFalse(r.fresh_capture_verified)
        self.assertEqual("unknown", r.category)
        self.assertEqual(0, r.memory_writes)
        self.assertEqual(0, r.camera_frames_requested)
        self.assertEqual(0, r.motor_commands_issued)
        with push_only_server(self.media, raw):
            legacy = MediaFixtureReader(self.media).read()
        self.assertEqual("unavailable_or_invalid", legacy.status)

    def test_b12_duplicate_sequence_cannot_replay_boxes(self):
        stamps = iter((100.1, 100.2, 100.7, 100.8))
        raw = b12_packet(capture_ns=100_000_000_000, look_seq=3)
        with _fictional_unix_server(self.media, (raw, raw)):
            reader = MediaFixtureReader(self.media, b12_local_shape=True,
                                        clock=lambda: next(stamps))
            self.assertEqual("shape_only_untrusted", reader.read().status)
            repeat = reader.read()
        self.assertEqual("duplicate_or_out_of_order", repeat.status)
        self.assertEqual(0, repeat.reported_boxes)
        self.assertEqual(0, repeat.memory_writes)

    def test_b12_stale_or_future_mock_frame_fails_closed(self):
        for i, stamp in enumerate((97_000_000_000, 101_000_000_000)):
            with self.subTest(stamp=stamp):
                tmp = Path(self.temp.name) / f"wrong-{i}.sock"
                times = iter((100.1, 100.2))
                with push_only_server(tmp, b12_packet(capture_ns=stamp)):
                    r = MediaFixtureReader(tmp, b12_local_shape=True,
                                           clock=lambda: next(times)).read()
                self.assertEqual("unavailable_or_invalid", r.status)
                self.assertEqual(0, r.reported_boxes)
                self.assertFalse(r.physical_sensor_verified)

    def test_b12_fixture_cannot_connect_oem_or_enable_by_string(self):
        with self.assertRaises(ValueError):
            MediaFixtureReader(
                Path("/run/mediad/kwipi/detections.sock"), b12_local_shape=True)
        with self.assertRaises(TypeError):
            MediaFixtureReader(self.media, b12_local_shape="true")



if __name__ == "__main__":
    unittest.main()
