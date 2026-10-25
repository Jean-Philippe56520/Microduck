"""F1-B read-only source tests: real fake Unix IPC, no robotd or camera data."""
from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from microduck_companion import AutonomyBrain, ExperienceMemory
from microduck_companion.passive_observations import summarize_passive
from microduck_companion.passive_sources import (
    FixtureUnixReader, MediaProbe, OEM_API_VERSION, OEM_SOCKET,
    PINNED_OEM_REVISION, PassiveSourceError, _read_fixture_frame, _strict_json,
    probe_official_mediad,
)

UNIX = hasattr(socket, "AF_UNIX")


def frame(*, sequence: int = 1, at: float = 100.0,
          category: str = "ball", kind: str = "object_label",
          source: str | None = None, events: list[dict] | None = None):
    if events is None:
        obj = {"kind": kind, "category": category, "confidence": .96,
               "ttl_s": 1.0}
        if kind == "object_label":
            obj["track_id"] = "track-unit-01"
        events = [obj]
    record: dict = {
        "schema_version": 1,
        "sequence": sequence,
        "sample_monotonic_s": at,
        "events": events,
    }
    if source is not None:
        record["source"] = source  # Forbidden: network peer cannot claim origin.
    return record


def packet(data: dict) -> bytes:
    return (json.dumps(data, separators=(",", ":")) + "\n").encode()


class LocalFakeService:
    """A fixture process responding on an actual local Unix socket."""

    def __init__(self, root: Path, responses: list[bytes], *,
                 received: list[dict] | None = None,
                 delay: float = 0.0):
        self.path = root / "fixture.sock"
        self.responses = responses
        self.received = received
        self.delay = delay
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(str(self.path))
        self.sock.listen(len(responses) + 1)
        self.sock.settimeout(2.0)
        self.errors = []
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    def _work(self):
        for data in self.responses:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            try:
                with conn:
                    conn.settimeout(1.0)
                    if self.received is not None:
                        buf = bytearray()
                        while b"\n" not in buf and len(buf) < 1024:
                            chunk = conn.recv(1024)
                            if not chunk:
                                break
                            buf.extend(chunk)
                        self.received.append(json.loads(buf.split(b"\n")[0]))
                    if self.delay:
                        time.sleep(self.delay)
                    if data:
                        conn.sendall(data)
            except (OSError, ValueError) as exc:
                self.errors.append(str(exc))

    def close(self):
        self.sock.close()
        self.thread.join(timeout=2.0)


@unittest.skipUnless(UNIX, "requires local Unix sockets")
class FakeUnixReaderTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)

    def service(self, *responses, **kwargs):
        serv = LocalFakeService(self.root, list(responses), **kwargs)
        self.addCleanup(serv.close)
        return serv

    def test_fixture_category_is_always_mock_and_passive(self):
        server = self.service(packet(frame()))
        reader = FixtureUnixReader(server.path, clock=lambda: 100.2)
        result = reader.read()
        self.assertEqual(("ok", "mock_fixture_unix", 1),
                         (result.status, result.channel, result.sequence))
        self.assertEqual("mock", result.snapshot.environment)
        observation, = summarize_passive(result.snapshot, now=100.2)
        self.assertEqual(("ball", "mock", "identified"),
                         (observation.category, observation.claimed_source,
                          observation.status))
        memory = ExperienceMemory()
        try:
            action = AutonomyBrain(memory).choose_from_snapshot(
                result.snapshot, now=100.2)
            self.assertEqual("halt", action.intention)
            self.assertIsNone(memory.get("track-unit-01"))
        finally:
            memory.close()

    def test_mock_sound_fixture_does_not_trigger_motor_stop(self):
        server = self.service(packet(frame(kind="sound_label",
                                           category="keyword_stop")))
        result = FixtureUnixReader(server.path, clock=lambda: 100.1).read()
        self.assertEqual("ok", result.status)
        obs, = summarize_passive(result.snapshot, now=100.2)
        self.assertEqual(("sound_label", "keyword_stop", "mock"),
                         (obs.kind, obs.category, obs.claimed_source))
        self.assertFalse(hasattr(result, "robot_stop"))

    def test_unknown_fixture_category_is_valid_but_not_identified(self):
        server = self.service(packet(frame(category="unknown")))
        result = FixtureUnixReader(server.path, clock=lambda: 100.1).read()
        obs, = summarize_passive(result.snapshot, now=100.1)
        self.assertEqual(("unknown", "unknown"),
                         (obs.category, obs.status))

    def test_fixture_source_field_sensor_or_robot_is_rejected(self):
        for claimed in ("sensor", "robot"):
            with self.subTest(claim=claimed):
                with tempfile.TemporaryDirectory() as d:
                    server = LocalFakeService(Path(d), [packet(frame(source=claimed))])
                    try:
                        result = FixtureUnixReader(
                            server.path, clock=lambda: 100.1).read()
                        self.assertEqual("unavailable_or_invalid", result.status)
                        self.assertFalse(result.snapshot.events)
                    finally:
                        server.close()

    def test_fixture_never_accepts_safety_or_control_method(self):
        for kind in ("floor_clear", "safe_area", "robot.move", "media.frame",
                     "battery_pct"):
            with self.subTest(kind=kind):
                with tempfile.TemporaryDirectory() as d:
                    server = LocalFakeService(Path(d), [packet(frame(
                        events=[{"kind": kind, "value": True}]))])
                    try:
                        out = FixtureUnixReader(
                            server.path, clock=lambda: 100.1).read()
                        self.assertEqual("unavailable_or_invalid", out.status)
                        self.assertEqual((), out.snapshot.events)
                    finally:
                        server.close()

    def test_duplicate_sequence_and_nonadvancing_sequence_never_reused(self):
        serv = self.service(
            packet(frame(sequence=9, at=100.)),
            packet(frame(sequence=9, at=101.)),
            packet(frame(sequence=8, at=102.)),
            packet(frame(sequence=10, at=103.)),
        )
        clock = [100.1]
        reader = FixtureUnixReader(
            serv.path, clock=lambda: clock[0], min_interval_s=.5)
        self.assertEqual("ok", reader.read().status)
        for now in (101.1, 102.1):
            clock[0] = now
            out = reader.read()
            self.assertEqual("duplicate_or_out_of_order", out.status)
            self.assertEqual((), out.snapshot.events)
        clock[0] = 103.1
        self.assertEqual("ok", reader.read().status)

    def test_limit_rate_before_connect_and_without_reusing_frames(self):
        serv = self.service(packet(frame(sequence=1, at=100.)),
                            packet(frame(sequence=2, at=101.)))
        clock = [100.1]
        reader = FixtureUnixReader(serv.path, clock=lambda: clock[0])
        self.assertEqual("ok", reader.read().status)
        clock[0] = 100.3
        result = reader.read()
        self.assertEqual("rate_limited", result.status)
        self.assertFalse(result.snapshot.events)
        clock[0] = 101.1
        self.assertEqual("ok", reader.read().status)

    def test_missing_service_returns_empty_and_later_recovers(self):
        path = self.root/"fixture.sock"
        clock = [100.1]
        reader = FixtureUnixReader(path, clock=lambda: clock[0])
        self.assertEqual("unavailable_or_invalid", reader.read().status)
        server = self.service(packet(frame(sequence=1, at=101.)))
        self.assertEqual(path, server.path)
        clock[0] = 101.1
        self.assertEqual("ok", reader.read().status)

    def test_disconnect_and_silent_timeout_fail_closed(self):
        for raw, delay in ((b"", 0.), (b'{"incomplete":', 0.),
                           (packet(frame()), .2)):
            with self.subTest(raw=raw[:20], delay=delay):
                with tempfile.TemporaryDirectory() as d:
                    server = LocalFakeService(Path(d), [raw], delay=delay)
                    try:
                        out = FixtureUnixReader(
                            server.path, timeout_s=.05,
                            clock=lambda: 100.1).read()
                        self.assertEqual("unavailable_or_invalid", out.status)
                        self.assertEqual((), out.snapshot.events)
                    finally:
                        server.close()

    def test_oversized_and_trailing_data_are_refused(self):
        for raw in (b"x" * 9000 + b"\n", packet(frame()) + b"extra"):
            with self.subTest(n=len(raw)):
                with tempfile.TemporaryDirectory() as d:
                    server = LocalFakeService(Path(d), [raw])
                    try:
                        res = FixtureUnixReader(server.path, clock=lambda: 100.1).read()
                        self.assertEqual("unavailable_or_invalid", res.status)
                    finally:
                        server.close()

    def test_rejects_symlink_and_regular_file_instead_of_socket(self):
        wrong = self.root / "file.sock"
        wrong.write_text("not a socket")
        link = self.root / "link.sock"
        link.symlink_to(wrong)
        for p in (wrong, link):
            with self.subTest(path=str(p)):
                self.assertEqual("unavailable_or_invalid",
                                 FixtureUnixReader(p, clock=lambda: 100.1).read().status)

    def test_service_hello_only_reads_metadata_never_frames(self):
        messages = []
        hello = {
            "jsonrpc": "2.0", "id": 1,
            "result": {"api_version": OEM_API_VERSION,
                       "daemon_version": "0.0.1",
                       "revision": PINNED_OEM_REVISION},
        }
        server = self.service(packet(hello), received=messages)
        probe = probe_official_mediad(server.path, timeout_s=.5)
        self.assertIsInstance(probe, MediaProbe)
        self.assertEqual("unverified_peer", probe.status)
        self.assertFalse(probe.verified_for_pinned_oem)
        self.assertEqual("oem_media_hello_only", probe.channel)
        self.assertEqual([{
            "jsonrpc": "2.0", "id": 1, "method": "hello"
        }], messages)
        self.assertFalse(hasattr(probe, "events"))

    def test_fake_hello_wrong_method_id_or_version_is_never_verified(self):
        for response in (
            {"jsonrpc": "2.0", "id": 2, "result": {
                "api_version": 44, "daemon_version": None,
                "revision": PINNED_OEM_REVISION}},
            {"jsonrpc": "2.0", "id": 1, "result": {
                "api_version": 200, "daemon_version": None, "revision": None}},
            {"jsonrpc": "2.0", "id": 1, "result": {
                "api_version": 44, "daemon_version": None, "revision": "fake"}},
        ):
            with tempfile.TemporaryDirectory() as d:
                server = LocalFakeService(Path(d), [packet(response)])
                try:
                    probe = probe_official_mediad(server.path)
                    self.assertFalse(probe.verified_for_pinned_oem)
                    self.assertIn(probe.status, {"unverified_peer",
                                                  "unavailable_or_invalid"})
                finally:
                    server.close()

    def test_fake_hello_cannot_claim_default_path_with_symlink(self):
        fake = self.root / "regular.sock"
        fake.write_text("forged")
        probe = probe_official_mediad(fake)
        self.assertEqual("unavailable_or_invalid", probe.status)
        self.assertFalse(probe.verified_for_pinned_oem)


class FrameValidationTests(unittest.TestCase):
    def test_rejects_stale_future_and_wrong_version(self):
        examples = [
            frame(at=95.),
            frame(at=105.),
            {**frame(), "schema_version": 2},
            {**frame(), "sequence": -1},
            {**frame(), "sample_monotonic_s": True},
        ]
        for x in examples:
            with self.subTest(data=x):
                with self.assertRaises(PassiveSourceError):
                    _read_fixture_frame(x, now=100.2, max_age_s=1.)

    def test_rejects_confidence_unsafe_label_and_raw_media(self):
        for val in ("someone's dog", "my pet", "Malo", "kitty.png"):
            with self.subTest(val=val):
                with self.assertRaises(PassiveSourceError):
                    _read_fixture_frame(frame(category=val), now=100.1, max_age_s=1.)
        for data in (
            {"kind": "object_label", "category": "ball", "track_id": "identity",
             "ttl_s": 1., "confidence": 1.},
            {"kind": "object_label", "category": "ball",
             "track_id": "track-1", "ttl_s": 1., "confidence": float("nan")},
            {"kind": "sound_label", "category": "speech",
             "ttl_s": 1., "confidence": .9, "transcript": "private"},
            {"kind": "sound_label", "category": "bark",
             "ttl_s": 2.5, "confidence": .95},
            {"kind": "object_label", "category": "ball",
             "track_id": "track-valid", "ttl_s": 1., "confidence": .98,
             "pixels": "raw_camera"},
        ):
            with self.subTest(data=data), self.assertRaises(PassiveSourceError):
                _read_fixture_frame(frame(events=[data]), now=100.1, max_age_s=1.)

    def test_rejects_oversized_event_list(self):
        many = frame(events=[frame()["events"][0]] * 65)
        with self.assertRaises(PassiveSourceError):
            _read_fixture_frame(many, now=100.1, max_age_s=1.)

    def test_rejects_duplicate_json_keys_and_nonfinite_literals(self):
        for raw in (
            b'{"sequence":1,"sequence":2}',
            b'{"x":Infinity}', b'{"x":NaN}', b'[]',
        ):
            with self.subTest(raw=raw), self.assertRaises(PassiveSourceError):
                _strict_json(raw)

    def test_constructor_refuses_no_rate_limit_bad_clock_and_ttls(self):
        for kw in ({"timeout_s": 0}, {"timeout_s": True},
                   {"max_age_s": 5}, {"min_interval_s": 0},
                   {"clock": None}, {"timeout_s": math.inf}):
            with self.subTest(kw=kw), self.assertRaises((ValueError, TypeError)):
                FixtureUnixReader("/tmp/unused.sock", **kw)
        with self.assertRaises(ValueError):
            FixtureUnixReader("relative/path.sock")

    def test_incomplete_bad_timestamp_no_future_promotion(self):
        with self.assertRaises(PassiveSourceError):
            _read_fixture_frame(
                frame(at=100.15), now=100.1, max_age_s=1.)
        with self.assertRaises(PassiveSourceError):
            _read_fixture_frame(
                frame(at=100., events=[{"kind": "sound_label",
                                         "category": "speech",
                                         "confidence": False, "ttl_s": 1.}]),
                now=100.1, max_age_s=1.)


if __name__ == "__main__":
    unittest.main()
