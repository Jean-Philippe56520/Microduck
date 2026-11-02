"""F3-C OEM-shaped metadata and synthetic sound-cue routing tests.

Tests intentionally never connect to real mediad, load camera/audio buffers,
authenticate WebRTC, call robotd, or turn voice into an emergency stop.
"""
from __future__ import annotations

import json
import math
import unittest

from microduck_companion.passive_media_router import (
    MAX_BOXES, MAX_NOTIFICATION_BYTES, MAX_SOUND_FIXTURE_BYTES,
    MOCK_AUDIO_CUES, OEM_NOTIFICATION_METHODS, OEM_REVISION_REVIEWED,
    MediaMetadata, MockAudioCueRouter, PassiveMediaError,
    parse_oem_shape_notification, parse_b12_local_shape_notification,
)
from microduck_companion.passive_sources import (
    OEM_API_VERSION, OEM_SOCKET, PINNED_OEM_REVISION,
)


def video(*, with_intrinsics=False):
    params = {
        "width": 720, "height": 1280, "rotate": 90,
        "mono_ns": 1_002_000_000, "real_ns": 1_802_000_000,
    }
    if with_intrinsics:
        params["intrinsics"] = {
            "fx": 610.2, "fy": 610.2, "cx": 355.4, "cy": 631.8,
            "source": "family", "calibrated": True,
            "distortion": [-.01, .001, 0., 0., .001],
        }
    return {"jsonrpc": "2.0", "method": "media.video", "params": params}


def detections(*, count=1):
    return {"jsonrpc": "2.0", "method": "media.detections", "params": {
        "width": 720, "height": 1280, "took_ms": 63.5,
        "boxes": [
            {"x0": 10., "y0": 20., "x1": 110., "y1": 220.,
             "score": 1.38}
            for _ in range(count)
        ],
    }}


def encoded(data):
    return json.dumps(data, allow_nan=False).encode("utf-8")


def sound(cue="petting_start", *, seq=1, sample=100.):
    return encoded({"schema_version": 1, "sequence": seq,
                    "sample_monotonic_s": sample, "cue": cue})


class OemNotificationTests(unittest.TestCase):
    def test_pinned_revision_and_oem_socket_are_existing_f1b_values(self):
        self.assertEqual(OEM_REVISION_REVIEWED, PINNED_OEM_REVISION)
        self.assertEqual(44, OEM_API_VERSION)
        self.assertEqual("/run/mediad/media.sock", OEM_SOCKET)
        self.assertEqual({"media.video", "media.detections"},
                         set(OEM_NOTIFICATION_METHODS))
        self.assertNotIn("media.frame", OEM_NOTIFICATION_METHODS)

    def test_oem_video_without_intrinsics_is_metadata_only(self):
        result = parse_oem_shape_notification(encoded(video()))
        self.assertEqual("metadata_unverified", result.status)
        self.assertEqual((720, 1280, 90),
                         (result.width, result.height, result.rotate))
        self.assertEqual(0, result.reported_boxes)
        self.assertIsNone(result.intrinsics_source)
        self.assertEqual("unknown", result.category)
        self.assertFalse(result.verified_sensor)
        self.assertEqual(0, result.motor_commands_issued)
        self.assertEqual(0, result.media_bytes_stored)

    def test_oem_video_with_family_calibration_preserves_only_source(self):
        r = parse_oem_shape_notification(encoded(video(with_intrinsics=True)))
        self.assertEqual("family", r.intrinsics_source)
        self.assertFalse(r.verified_sensor)
        self.assertNotIn("distortion", str(r))
        self.assertNotIn("fx", str(r))
        self.assertNotIn("610.2", str(r))

    def test_oem_sim_intrinsics_are_not_physical_calibration(self):
        data = video(with_intrinsics=True)
        data["params"]["intrinsics"]["source"] = "sim"
        data["params"]["intrinsics"]["calibrated"] = False
        self.assertEqual("sim", parse_oem_shape_notification(
            encoded(data)).intrinsics_source)

    def test_one_class_detection_never_becomes_cat_or_dog(self):
        report = parse_oem_shape_notification(encoded(detections()))
        self.assertEqual("duck_candidates_unverified", report.status)
        self.assertEqual("unknown", report.category)
        self.assertEqual(1, report.reported_boxes)
        self.assertEqual(1.38, report.raw_score_max)
        self.assertEqual(63.5, report.reported_inference_ms)
        self.assertIsNone(report.rotate)
        self.assertFalse(report.verified_sensor)
        self.assertEqual(0, report.motor_commands_issued)

    def test_oem_raw_score_above_one_is_valid_and_not_probability(self):
        r = parse_oem_shape_notification(encoded(detections()))
        self.assertGreater(r.raw_score_max, 1.)
        self.assertEqual("unknown", r.category)

    def test_empty_detection_clears_candidate_count(self):
        r = parse_oem_shape_notification(encoded(detections(count=0)))
        self.assertEqual("no_candidate_boxes", r.status)
        self.assertEqual(0, r.reported_boxes)
        self.assertIsNone(r.raw_score_max)
        self.assertEqual("unknown", r.category)

    def test_no_id_allowed_on_notification(self):
        data = video()
        data["id"] = 1
        with self.assertRaises(PassiveMediaError):
            parse_oem_shape_notification(encoded(data))

    def test_rpc_result_or_robot_command_not_parsed(self):
        for data in (
            {"jsonrpc": "2.0", "id": 1, "result": {}},
            {"jsonrpc": "2.0", "method": "robot.move", "params": {}},
            {"jsonrpc": "2.0", "method": "robot.sound", "params": {}},
            {"jsonrpc": "2.0", "method": "media.frame", "params": {}},
            {"jsonrpc": "2.0", "method": "robot.stop", "params": {}},
            {"jsonrpc": "2.0", "method": "media.sound", "params": {}},
        ):
            with self.subTest(data=data), self.assertRaises(PassiveMediaError):
                parse_oem_shape_notification(encoded(data))

    def test_unrecognized_metadata_fields_are_rejected(self):
        for key, value in (
            ("authenticated", True),
            ("source", "mediad"),
            ("identified_individual", "private-name"),
            ("sound", "dog_bark"),
            ("camera_pixels", "base64data"),
            ("floor_clear", True),
        ):
            data = video()
            data["params"][key] = value
            with self.subTest(key=key), self.assertRaises(PassiveMediaError):
                parse_oem_shape_notification(encoded(data))

    def test_wrong_video_geometry_and_clock_values_rejected(self):
        for key, bad in (
            ("width", 0), ("height", 8192), ("width", 3.5),
            ("rotate", 45), ("rotate", True),
            ("mono_ns", True), ("mono_ns", -1), ("mono_ns", 2**64),
            ("real_ns", -1), ("real_ns", 1.5),
        ):
            d = video()
            d["params"][key] = bad
            with self.subTest(key=key, bad=bad):
                with self.assertRaises(PassiveMediaError):
                    parse_oem_shape_notification(encoded(d))

    def test_intrinsics_bad_calibration_or_distortion_rejected(self):
        for key, val in (
            ("fx", 0), ("fy", float("nan")), ("cx", -3),
            ("cy", 1400.), ("calibrated", 1),
            ("source", "sensor"), ("distortion", [0.,0.]),
            ("distortion", [0.,0.,0.,float("inf"),0.]),
        ):
            d = video(with_intrinsics=True)
            d["params"]["intrinsics"][key] = val
            with self.subTest(key=key), self.assertRaises(PassiveMediaError):
                # allow_nan=True is intentional to exercise strict parser.
                parse_oem_shape_notification(json.dumps(d).encode())

    def test_intrinsics_missing_or_extra_properties_rejected(self):
        d = video(with_intrinsics=True)
        del d["params"]["intrinsics"]["fx"]
        with self.assertRaises(PassiveMediaError):
            parse_oem_shape_notification(encoded(d))
        d = video(with_intrinsics=True)
        d["params"]["intrinsics"]["robot_name"] = "private"
        with self.assertRaises(PassiveMediaError):
            parse_oem_shape_notification(encoded(d))

    def test_detection_wrong_fields_or_geometry_are_rejected(self):
        for key, value in (
            ("x0", -1.), ("x1", 900.), ("y1", 1400.),
            ("score", -1.), ("score", float("nan")),
            ("score", True), ("x0", "10.0"),
        ):
            d = detections()
            d["params"]["boxes"][0][key] = value
            with self.subTest(key=key, value=value):
                with self.assertRaises(PassiveMediaError):
                    parse_oem_shape_notification(json.dumps(d).encode())

    def test_detection_inverted_or_zero_area_rejected(self):
        for key, value in (("x1", 10.), ("x1", 0.),
                           ("y1", 20.), ("y1", 0.)):
            d = detections()
            d["params"]["boxes"][0][key] = value
            with self.subTest(key=key), self.assertRaises(PassiveMediaError):
                parse_oem_shape_notification(encoded(d))

    def test_too_many_boxes_and_high_latency_rejected(self):
        d = detections(count=MAX_BOXES + 1)
        with self.assertRaises(PassiveMediaError):
            parse_oem_shape_notification(encoded(d))
        d = detections()
        d["params"]["took_ms"] = 6000.
        with self.assertRaises(PassiveMediaError):
            parse_oem_shape_notification(encoded(d))

    def test_detections_do_not_accept_claimed_identity_or_kind(self):
        for extra in ("category", "kind", "source", "confidence", "track_id"):
            d = detections()
            d["params"]["boxes"][0][extra] = "dog"
            with self.subTest(extra=extra), self.assertRaises(PassiveMediaError):
                parse_oem_shape_notification(encoded(d))

    def test_wrong_rpc_envelope_and_duplicate_keys_rejected(self):
        d = detections()
        d["jsonrpc"] = "1.0"
        with self.assertRaises(PassiveMediaError):
            parse_oem_shape_notification(encoded(d))
        with self.assertRaises(PassiveMediaError):
            parse_oem_shape_notification(
                b'{"jsonrpc":"2.0","jsonrpc":"2.0","method":"media.video","params":{}}')

    def test_nonfinite_json_literals_and_oversized_notifications_rejected(self):
        for raw in (
            b'{"jsonrpc":NaN}',
            b'{"jsonrpc":Infinity}',
            b"not-json",
            encoded(video()) + b"\n",
            b"x" * (MAX_NOTIFICATION_BYTES + 1),
            b"",
        ):
            with self.subTest(len=len(raw)), self.assertRaises(PassiveMediaError):
                parse_oem_shape_notification(raw)

    def test_bytes_only_no_filenames_or_paths_are_accepted(self):
        with self.assertRaises(PassiveMediaError):
            parse_oem_shape_notification("/private/photo.jpg")
        with self.assertRaises(PassiveMediaError):
            parse_oem_shape_notification(bytearray(encoded(video())))

    def test_no_geometry_grants_motion_or_floor_safety(self):
        for raw in (encoded(video()), encoded(detections())):
            report = parse_oem_shape_notification(raw)
            self.assertFalse(report.verified_sensor)
            self.assertEqual(0, report.motor_commands_issued)
            self.assertEqual("unknown", report.category)
            self.assertNotIn("safe_to_move", str(report))
            self.assertNotIn("floor_clear", str(report))


class MockSoundTests(unittest.TestCase):
    def setUp(self):
        self.router = MockAudioCueRouter()

    def test_supported_sound_labels_are_hypotheses_never_microphone_proof(self):
        for i, cue in enumerate(sorted(MOCK_AUDIO_CUES)):
            with self.subTest(cue=cue):
                result = MockAudioCueRouter().route(
                    sound(cue, seq=i+1, sample=100.),
                    now_monotonic_s=100.2)
                self.assertEqual("fixture_hypothesis_only", result.status)
                self.assertEqual(cue, result.cue)
                self.assertEqual("unknown", result.category)
                self.assertFalse(result.verified_microphone)
                self.assertFalse(result.stops_robot)
                self.assertEqual(0, result.motor_commands_issued)
                self.assertEqual(0, result.audio_bytes_stored)

    def test_stop_keyword_is_never_motor_stop(self):
        r = self.router.route(sound("keyword_stop"), now_monotonic_s=100.1)
        self.assertEqual("keyword_stop", r.cue)
        self.assertFalse(r.stops_robot)
        self.assertEqual("unknown", r.category)
        self.assertEqual(0, r.motor_commands_issued)

    def test_keyword_viens_is_not_motor_permission(self):
        r = self.router.route(sound("keyword_viens"), now_monotonic_s=100.1)
        self.assertEqual("fixture_hypothesis_only", r.status)
        self.assertEqual(0, r.motor_commands_issued)

    def test_replay_duplicate_and_regression_refused(self):
        self.router.route(sound(), now_monotonic_s=100.1)
        for seq, sample, expected in (
            (1, 101., "duplicate_or_out_of_order"),
            (0, 101., "duplicate_or_out_of_order"),
            (2, 99., "clock_regression"),
        ):
            with self.subTest(seq=seq, sample=sample):
                result = self.router.route(
                    sound(seq=seq, sample=sample), now_monotonic_s=101.1)
                self.assertEqual(expected, result.status)
                self.assertIsNone(result.cue)
        self.assertEqual("fixture_hypothesis_only", self.router.route(
            sound(seq=2, sample=101.), now_monotonic_s=101.2).status)

    def test_future_stale_low_rate_are_refused_without_state_change(self):
        stale = self.router.route(sound(seq=5, sample=100.),
                                  now_monotonic_s=103.)
        future = self.router.route(sound(seq=5, sample=105.),
                                   now_monotonic_s=104.)
        self.assertEqual("stale_or_future", stale.status)
        self.assertEqual("stale_or_future", future.status)
        self.assertEqual("fixture_hypothesis_only", self.router.route(
            sound(seq=5, sample=100.), now_monotonic_s=100.2).status)
        limited = self.router.route(sound(seq=6, sample=100.2),
                                    now_monotonic_s=100.3)
        self.assertEqual("rate_limited", limited.status)
        self.assertIsNone(limited.cue)
        accepted = self.router.route(sound(seq=6, sample=100.6),
                                     now_monotonic_s=100.7)
        self.assertEqual("fixture_hypothesis_only", accepted.status)

    def test_wrong_source_audio_payload_is_refused(self):
        for raw in (
            {"schema_version":1,"sequence":1,"sample_monotonic_s":100.,
             "cue":"speaker_said_private_name"},
            {"schema_version":1,"sequence":1,"sample_monotonic_s":100.,
             "cue":"dog"},
            {"schema_version":1,"sequence":1,"sample_monotonic_s":100.,
             "cue":"keyword_stop","raw_audio":"bytes"},
            {"schema_version":1,"sequence":1,"sample_monotonic_s":100.,
             "cue":"keyword_stop","authenticated":True},
            {"schema_version":1,"sequence":1,"sample_monotonic_s":100.,
             "cue":"keyword_stop","motor_stop":True},
        ):
            with self.subTest(raw=raw), self.assertRaises(PassiveMediaError):
                self.router.route(encoded(raw), now_monotonic_s=100.1)

    def test_bad_sound_sequence_version_and_clocks_rejected(self):
        for key, value in (
            ("sequence", True), ("sequence", -1),
            ("sequence", 2**63), ("schema_version", True),
            ("schema_version", 2), ("sample_monotonic_s", float("nan")),
            ("sample_monotonic_s", float("inf")),
            ("sample_monotonic_s", -10.), ("cue", False),
        ):
            d = json.loads(sound())
            d[key] = value
            with self.subTest(key=key), self.assertRaises(PassiveMediaError):
                self.router.route(json.dumps(d).encode(),
                                  now_monotonic_s=100.1)

    def test_invalid_runtime_monotonic_clock_rejected(self):
        for now in (-1., float("nan"), float("inf"), True, "now"):
            with self.subTest(now=now), self.assertRaises(ValueError):
                self.router.route(sound(), now_monotonic_s=now)

    def test_sound_fixture_size_and_duplicate_properties_rejected(self):
        for raw in (
            b"z" * (MAX_SOUND_FIXTURE_BYTES+1),
            b"",
            b'{"schema_version":1,"schema_version":1}',
            sound() + b"\n",
        ):
            with self.subTest(length=len(raw)), self.assertRaises(PassiveMediaError):
                self.router.route(raw, now_monotonic_s=100.1)

    def test_malformed_sound_does_not_consume_sequence(self):
        d = json.loads(sound(seq=1, sample=100.))
        d["cue"] = "not_trained"
        with self.assertRaises(PassiveMediaError):
            self.router.route(encoded(d), now_monotonic_s=100.1)
        r = self.router.route(sound(seq=1, sample=100.),
                              now_monotonic_s=100.1)
        self.assertEqual("fixture_hypothesis_only", r.status)
        self.assertEqual(1, r.sequence)


def b12_local(*, now_ns=100_000_000_000, age_ns=100_000_000,
              seq=1, count=1):
    data = detections(count=count)
    data["params"].update({
        "captured_at_monotonic_ns": now_ns - age_ns,
        "captured_at_unix_us": 1_800_000_000_000_000,
        "look_seq": seq,
    })
    return data


class B12LocalWireTests(unittest.TestCase):
    """Real P15-B12 key contract on independent bytes; no real source claims."""

    def test_fresh_capture_shape_is_unknown_and_not_a_motor_grant(self):
        raw = encoded(b12_local(seq=7))
        with self.assertRaises(PassiveMediaError):
            parse_oem_shape_notification(raw)  # Keep pre-B12 WebRTC strict.
        actual = parse_b12_local_shape_notification(
            raw, now_monotonic_ns=100_000_000_000)
        self.assertEqual("b12_shape_unverified", actual.status)
        self.assertEqual(7, actual.look_seq)
        self.assertEqual(1, actual.reported_boxes)
        self.assertEqual(1.38, actual.raw_score_max)
        self.assertEqual("unknown", actual.category)
        self.assertFalse(actual.verified_sensor)
        self.assertEqual(0, actual.motor_commands_issued)
        self.assertEqual(0, actual.media_bytes_stored)
        self.assertNotIn("ball", str(actual))
        self.assertNotIn("person", str(actual))

    def test_zero_boxes_and_capture_timestamp_boundary(self):
        data = b12_local(age_ns=2_000_000_000, count=0)
        actual = parse_b12_local_shape_notification(
            encoded(data), now_monotonic_ns=100_000_000_000)
        self.assertEqual("b12_empty_look_unverified", actual.status)
        self.assertEqual(0, actual.reported_boxes)
        self.assertEqual("unknown", actual.category)
        for age_ns in (-1, 2_000_000_001):
            with self.subTest(age_ns=age_ns), self.assertRaises(PassiveMediaError):
                parse_b12_local_shape_notification(
                    encoded(b12_local(age_ns=age_ns)),
                    now_monotonic_ns=100_000_000_000)

    def test_exact_b12_keys_and_source_revision_are_not_identity(self):
        from scripts.per_p15b12_apply_oem_capture_provenance import LOCAL_SERIALIZER
        for k in ("captured_at_monotonic_ns", "captured_at_unix_us", "look_seq"):
            self.assertIn(k, LOCAL_SERIALIZER)
        p = b12_local()
        for key in list(p["params"]):
            bad = b12_local()
            bad["params"].pop(key)
            with self.subTest(missing=key), self.assertRaises(PassiveMediaError):
                parse_b12_local_shape_notification(
                    encoded(bad), now_monotonic_ns=100_000_000_000)
        for name, value in (("category", "dog"), ("sensor", "true"),
                            ("safe_area", True), ("raw_image", "secret")):
            bad = b12_local()
            bad["params"][name] = value
            with self.subTest(extra=name), self.assertRaises(PassiveMediaError):
                parse_b12_local_shape_notification(
                    encoded(bad), now_monotonic_ns=100_000_000_000)

    def test_b12_rejects_clock_sequence_types_and_limits(self):
        for key, value in (
            ("captured_at_monotonic_ns", True),
            ("captured_at_monotonic_ns", -1),
            ("captured_at_monotonic_ns", 0),
            ("captured_at_monotonic_ns", 2**64),
            ("captured_at_monotonic_ns", 1.0),
            ("captured_at_unix_us", 0),
            ("captured_at_unix_us", "today"),
            ("look_seq", 0),
            ("look_seq", -1),
            ("look_seq", True),
            ("look_seq", 2**64),
        ):
            bad = b12_local()
            bad["params"][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(PassiveMediaError):
                parse_b12_local_shape_notification(
                    encoded(bad), now_monotonic_ns=100_000_000_000)
        for now in (0, -1, True, 100.5, "100", 2**64):
            with self.subTest(now=now), self.assertRaises(PassiveMediaError):
                parse_b12_local_shape_notification(
                    encoded(b12_local()), now_monotonic_ns=now)

    def test_b12_rejects_untrusted_commands_legacy_bulk_and_bad_boxes(self):
        for change in ("robot", "frame", "extra_id", "invalid_box", "oversize"):
            bad = b12_local()
            if change == "robot":
                bad["method"] = "robot.do"
            elif change == "frame":
                bad["method"] = "media.frame"
            elif change == "extra_id":
                bad["id"] = 123
            elif change == "invalid_box":
                bad["params"]["boxes"][0]["score"] = 101.0
            else:
                bad["params"]["boxes"] *= MAX_BOXES + 1
            with self.subTest(change=change), self.assertRaises(PassiveMediaError):
                parse_b12_local_shape_notification(
                    encoded(bad), now_monotonic_ns=100_000_000_000)
        for raw in (
            encoded(detections()),  # B4 legacy shape cannot masquerade as B12.
            b'{"jsonrpc":"2.0","jsonrpc":"2.0","method":"media.detections","params":{}}',
            b"x" * (MAX_NOTIFICATION_BYTES + 1),
            encoded(b12_local()) + b"\n",
        ):
            with self.subTest(size=len(raw)), self.assertRaises(PassiveMediaError):
                parse_b12_local_shape_notification(
                    raw, now_monotonic_ns=100_000_000_000)


if __name__ == "__main__":
    unittest.main()
