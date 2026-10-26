"""R1: all OEM-shaped inputs remain metadata-only, fixture-only and non-motor.

No sockets, images, raw audio, model loading, network or real sensor access.
Uses existing F3-C/F3-E/F1/F2/sim_ipc parsers and safety gates.
"""
from __future__ import annotations

import json
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.oem_passive_fixture import (
    LANES, OEMFixtureInspector,
)
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.sim_ipc import Notification

NOW = 100.0
UNIX_US = 1_830_000_000_000_000


def envelope(method: str, params: dict) -> bytes:
    return json.dumps({
        "jsonrpc": "2.0", "method": method, "params": params,
    }, allow_nan=False).encode()


def video() -> bytes:
    return envelope("media.video", {
        "width": 720, "height": 1280, "rotate": 90,
        "mono_ns": 123_000_000, "real_ns": 123_450_000,
    })


def duck_boxes(*, suspicious: bool = False) -> bytes:
    p = {
        "width": 720, "height": 1280, "took_ms": 47.5,
        "boxes": [{"x0": 10., "y0": 20., "x1": 110., "y1": 230.,
                   "score": 1.38}],
    }
    if suspicious:
        p["floor_clear"] = True
    return envelope("media.detections", p)


def frame_header(*, age_us: int = 1000, extra=None) -> bytes:
    data = {
        "jsonrpc": "2.0", "id": 1,
        "result": {
            "width": 720, "height": 1280, "format": "UYVY",
            "bytes": 720 * 1280 * 2, "rotate": 90,
            "captured_at_unix_us": UNIX_US - age_us,
        },
    }
    if extra is not None:
        data["result"]["private_photo"] = extra
    return json.dumps(data).encode()


def depth(seq=1, received=99.5, **extra) -> Notification:
    params = {
        "rows": 8, "cols": 8, "seq": seq, "t_ns": 5_000_000,
        "distance_mm": [750] * 64, "status": [5] * 64,
    }
    params.update(extra)
    return Notification("tof.frame", params, received)


def audio(seq=1, cue="ambient_change", sample=99.5):
    return json.dumps({
        "schema_version": 1,
        "sequence": seq,
        "sample_monotonic_s": sample,
        "cue": cue,
    }).encode()


class R1OEMFixtureTests(unittest.TestCase):
    def setUp(self):
        self.gate = OEMFixtureInspector()

    def assert_untrusted(self, report, *, lane):
        self.assertEqual(lane, report.lane)
        self.assertEqual("unknown", report.category)
        self.assertFalse(report.source_authenticated)
        self.assertFalse(report.motion_authorized)
        self.assertEqual(0, report.motor_commands_issued)
        self.assertEqual(0, report.raw_media_stored_bytes)
        self.assertEqual(0, report.pc_requests_issued)
        self.assertIsNone(report.to_passive_read().sequence)
        self.assertEqual("oem_fixture_metadata_only",
                         report.to_passive_read().channel)
        self.assertEqual((), report.to_passive_read().snapshot.events)
        self.assertNotEqual("ok", report.to_passive_read().status)
        self.assertFalse(report.to_passive_read().snapshot.to_scene(
            now=report.received_monotonic_s).floor_clear)

    def test_oem_webrtc_video_is_not_a_unix_frame_or_fresh_sensor(self):
        r = self.gate.web_metadata(video(), now_monotonic_s=NOW)
        self.assertEqual("metadata_unverified", r.status)
        self.assertEqual("capture_time_unverified", r.timestamp_basis)
        self.assertIsNone(r.sample_age_s)
        self.assertEqual(len(video()), r.metadata_bytes)
        self.assertIsNone(r.advertised_media_bytes)
        self.assertEqual(0, r.duck_box_count)
        self.assert_untrusted(r, lane="webrtc_metadata_fixture")

    def test_detected_ducks_not_categories_or_calibrated_probabilities(self):
        r = self.gate.web_metadata(duck_boxes(), now_monotonic_s=NOW)
        self.assertEqual("duck_candidates_unverified", r.status)
        self.assertEqual(1, r.duck_box_count)
        self.assertAlmostEqual(47.5, r.detector_reported_ms)
        self.assertIsNone(r.sample_age_s)
        self.assertNotIn("1.38", str(r))
        self.assert_untrusted(r, lane="webrtc_metadata_fixture")

    def test_invalid_or_safety_grant_webrtc_fails_closed(self):
        for raw in (
            duck_boxes(suspicious=True), b'{"jsonrpc":"2.0","method":"robot.move"}',
            b"\xff", b"x" * 4097, b'{"jsonrpc":NaN}',
            b'{"jsonrpc":"2.0","method":"media.frame","params":{}}',
        ):
            with self.subTest(size=len(raw)):
                r = self.gate.web_metadata(raw, now_monotonic_s=NOW)
                self.assertEqual("invalid_fixture", r.status)
                self.assert_untrusted(r, lane="webrtc_metadata_fixture")

    def test_frame_header_only_reports_length_and_unverified_wall_age(self):
        r = self.gate.frame_header(frame_header(), now_unix_us=UNIX_US,
                                   now_monotonic_s=NOW)
        self.assertEqual("header_unverified", r.status)
        self.assertEqual("unverified_wall_clock", r.timestamp_basis)
        self.assertAlmostEqual(.001, r.sample_age_s)
        self.assertEqual(720*1280*2, r.advertised_media_bytes)
        self.assertLess(r.metadata_bytes, 1024)
        self.assertNotIn("UYVY", str(r))
        self.assert_untrusted(r, lane="media_frame_header_fixture")

    def test_frame_bad_age_future_private_or_bulk_rejected(self):
        for raw, wall, expected in (
            (frame_header(age_us=3_000_000), UNIX_US, "invalid_fixture"),
            (frame_header(age_us=-50_000), UNIX_US, "stale_or_future"),
            (frame_header(extra="private"), UNIX_US, "invalid_fixture"),
            (frame_header(), -1, "invalid_fixture"),
            (b"x" * 2049, UNIX_US, "invalid_fixture"),
        ):
            with self.subTest(status=expected, size=len(raw)):
                r = self.gate.frame_header(raw, now_unix_us=wall,
                                           now_monotonic_s=NOW)
                self.assertEqual(expected, r.status)
                self.assert_untrusted(r, lane="media_frame_header_fixture")

    def test_tof_uses_existing_8x8_parser_and_retains_no_raw_zones(self):
        r = self.gate.depth(depth(), now_monotonic_s=NOW)
        self.assertEqual("depth_shape_unverified", r.status)
        self.assertEqual("local_fixture_receipt_monotonic", r.timestamp_basis)
        self.assertAlmostEqual(.5, r.sample_age_s)
        self.assertEqual(64, r.tof_zone_count)
        self.assertEqual(1, r.sequence)
        self.assertNotIn("750", str(r))
        self.assertNotIn("floor_clear", str(r))
        self.assert_untrusted(r, lane="tof_notification_fixture")

    def test_tof_stale_future_replay_or_clock_reset(self):
        first = self.gate.depth(depth(seq=10), now_monotonic_s=NOW)
        self.assertEqual("depth_shape_unverified", first.status)
        self.assertEqual("duplicate_or_out_of_order",
                         self.gate.depth(depth(seq=10),
                                         now_monotonic_s=100.5).status)
        self.assertEqual("stale_or_future",
                         self.gate.depth(depth(seq=11, received=93),
                                         now_monotonic_s=100.5).status)
        self.assertEqual("stale_or_future",
                         self.gate.depth(depth(seq=11, received=102),
                                         now_monotonic_s=100.5).status)
        self.assertEqual("clock_reset",
                         self.gate.depth(depth(seq=11, received=99),
                                         now_monotonic_s=99.8).status)
        self.assertEqual("depth_shape_unverified",
                         self.gate.depth(depth(seq=1, received=99.7),
                                         now_monotonic_s=100.).status)

    def test_tof_wrong_geometry_extra_safety_or_unbounded_seq(self):
        cases = [
            depth(rows=4),
            depth(**{"distance_mm": [20]*63}),
            depth(**{"status": [0]*63}),
            depth(floor_clear=True),
            depth(seq=2**65),
            Notification("robot.state", depth().params, 99.),
            Notification("tof.frame", {"rows":8}, 99.),
            Notification("tof.frame", depth().params, float("nan")),
        ]
        for i, case in enumerate(cases):
            with self.subTest(case=i):
                r = OEMFixtureInspector().depth(case, now_monotonic_s=NOW)
                self.assertEqual("invalid_fixture", r.status)
                self.assert_untrusted(r, lane="tof_notification_fixture")

    def test_audio_uses_existing_synthetic_router_never_keyword_motor(self):
        r = self.gate.audio(audio(cue="keyword_stop"), now_monotonic_s=NOW)
        self.assertEqual("fixture_hypothesis_only", r.status)
        self.assertEqual("synthetic_monotonic_checked", r.timestamp_basis)
        self.assertEqual(1, r.sequence)
        self.assertNotIn("keyword_stop", str(r))
        self.assert_untrusted(r, lane="audio_cue_fixture")
        self.assertEqual("duplicate_or_out_of_order",
                         self.gate.audio(audio(seq=1, cue="petting_start"),
                                         now_monotonic_s=100.5).status)
        self.assertEqual("fixture_hypothesis_only",
                         self.gate.audio(audio(seq=2, cue="ambient_change",
                                               sample=100.1),
                                         now_monotonic_s=100.3).status)

    def test_audio_rejects_private_transcript_and_age(self):
        bad = json.dumps({
            "schema_version": 1, "sequence": 1,
            "sample_monotonic_s": 99.5,
            "cue": "ambient_change", "transcript": "private",
        }).encode()
        self.assertEqual("invalid_fixture", self.gate.audio(
            bad, now_monotonic_s=NOW).status)
        self.assertEqual("stale_or_future", self.gate.audio(
            audio(sample=97.0), now_monotonic_s=NOW).status)
        self.assertEqual("invalid_fixture", self.gate.audio(
            audio(cue="dog"), now_monotonic_s=NOW).status)

    def test_unavailable_lanes_fresh_receipt_no_old_data(self):
        self.gate.depth(depth(), now_monotonic_s=NOW)
        for lane in LANES:
            r = self.gate.unavailable(lane, now_monotonic_s=101.)
            self.assertEqual("unavailable", r.status)
            self.assertEqual(0, r.metadata_bytes)
            self.assertIsNone(r.sequence)
            self.assert_untrusted(r, lane=lane)
        with self.assertRaises(ValueError):
            self.gate.unavailable("robot.move", now_monotonic_s=NOW)

    def test_bad_local_monotonic_clock_never_yields_sensing(self):
        for bad in (-1., True, float("nan"), float("inf"), "now"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.gate.web_metadata(video(), now_monotonic_s=bad)
            with self.assertRaises(ValueError):
                self.gate.frame_header(frame_header(), now_unix_us=UNIX_US,
                                       now_monotonic_s=bad)
            with self.assertRaises(ValueError):
                self.gate.depth(depth(), now_monotonic_s=bad)
            with self.assertRaises(ValueError):
                self.gate.audio(audio(), now_monotonic_s=bad)

    def test_existing_brain_and_sqlite_must_ignore_oem_metadata(self):
        memory = ExperienceMemory()
        self.addCleanup(memory.close)
        journal = PassiveObservationJournal(memory)
        brain = AutonomyBrain(memory)
        reports = (
            self.gate.web_metadata(duck_boxes(), now_monotonic_s=NOW),
            self.gate.frame_header(frame_header(), now_unix_us=UNIX_US,
                                   now_monotonic_s=NOW),
            self.gate.depth(depth(), now_monotonic_s=NOW),
            self.gate.audio(audio(cue="keyword_viens"), now_monotonic_s=NOW),
        )
        for r in reports:
            receipt = r.to_passive_read()
            intent = brain.propose_passive(
                receipt, journal=journal,
                now_monotonic_s=100.1, now_wall_epoch_s=1_830_000_000.)
            self.assertEqual("idle", intent.intention)
            self.assertFalse(intent.executed)
            self.assertEqual(0, intent.motor_commands_issued)
            self.assertFalse(intent.request_pc_analysis)
            rows = journal.append(
                receipt, now_monotonic_s=100.1,
                now_wall_epoch_s=1_830_000_000.)
            self.assertEqual(0, rows)
        self.assertEqual((), journal.recent(now_wall_epoch_s=1_830_000_000.))


if __name__ == "__main__":
    unittest.main()
