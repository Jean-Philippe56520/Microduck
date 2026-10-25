"""F1-A: fictional passive observations; no detector, recording or motor API."""
from __future__ import annotations

import math
import unittest

from microduck_companion import (
    AutonomyBrain, ExperienceMemory, PerceptionEvent, PerceptionSnapshot,
)
from microduck_companion.passive_observations import (
    MAX_EVENTS, PassiveObservation, summarize_passive,
)


def event(kind="object_label", category="ball", *, track_id="track-1",
          source="mock", at=100.0, ttl=1.0, confidence=0.95):
    return PerceptionEvent(
        kind=kind, value=category, source=source,
        observed_at=at, ttl_s=ttl, confidence=confidence,
        track_id=track_id if kind == "object_label" else None,
    )


def snapshot(*events, environment="mock", at=100.0):
    return PerceptionSnapshot(environment, tuple(events), at)


class PassiveObservationTests(unittest.TestCase):
    def summarize(self, *events, environment="mock", now=100.2, at=100.0):
        return summarize_passive(
            snapshot(*events, environment=environment, at=at), now=now,
        )

    def test_known_object_category_is_not_an_identity_or_authentication(self):
        one, = self.summarize(event())
        self.assertIsInstance(one, PassiveObservation)
        self.assertEqual(("object_label", "ball", "identified"),
                         (one.kind, one.category, one.status))
        self.assertEqual(("mock", "track-1"), (one.claimed_source, one.track_id))
        self.assertTrue(one.usable_category)

    def test_explicit_unknown_remains_unknown(self):
        one, = self.summarize(event(category="unknown"))
        self.assertEqual(("unknown", "unknown"),
                         (one.category, one.status))
        self.assertFalse(one.usable_category)

    def test_category_only_sound_events_are_passive(self):
        one, = self.summarize(event("sound_label", "knock"))
        self.assertEqual(("sound_label", "knock", "identified"),
                         (one.kind, one.category, one.status))
        self.assertIsNone(one.track_id)
        self.assertEqual("mock", one.claimed_source)

    def test_sound_keyword_stop_is_not_an_emergency_motor_action(self):
        snap = snapshot(event("sound_label", "keyword_stop"))
        self.assertEqual("keyword_stop", summarize_passive(
            snap, now=100.2)[0].category)
        with ExperienceMemory() as memory:
            plan = AutonomyBrain(memory).choose_from_snapshot(snap, now=100.2)
            self.assertEqual("halt", plan.intention)
            self.assertEqual(0, memory.conn.execute(
                "SELECT count(*) FROM objects").fetchone()[0])

    def test_sound_cannot_be_recognized_person_or_safety_gate(self):
        audio = event("sound_label", "speech")
        with ExperienceMemory() as memory:
            plan = AutonomyBrain(memory).choose_from_snapshot(
                snapshot(audio), now=100.2,
            )
        self.assertEqual("halt", plan.intention)

    def test_sound_is_not_a_transcript_or_identity(self):
        for invalid in ("hello there", "Nessquick", "Malo", "Please stop",
                        "", "STOP", "bark "):
            with self.subTest(label=invalid):
                with self.assertRaises(ValueError):
                    event("sound_label", invalid)
        with self.assertRaises(ValueError):
            PerceptionEvent("sound_label", "bark", "mock", 100.0, 1., 1.,
                            track_id="identity-123")

    def test_invalid_kind_and_version_remain_rejected(self):
        with self.assertRaises(ValueError):
            event("speech_transcript", "private audio")
        with self.assertRaises(ValueError):
            PerceptionEvent("sound_label", "knock", "mock",
                            100., 1., .95, schema_version=2)

    def test_stale_and_expired_events_never_recognize(self):
        one, = self.summarize(event(at=97.))
        self.assertEqual(("stale", "unknown", False),
                         (one.status, one.category, one.usable_category))

    def test_future_snapshot_cannot_recognize(self):
        one, = self.summarize(event(), now=99.)
        self.assertEqual(("future", "unknown"),
                         (one.status, one.category))

    def test_conflicting_labels_on_same_track_fail_closed(self):
        one, = self.summarize(event(category="ball"),
                              event(category="toy"))
        self.assertEqual(("conflict", "unknown"),
                         (one.status, one.category))
        self.assertFalse(one.usable_category)

    def test_unknown_and_known_on_same_track_conflict(self):
        one, = self.summarize(event(category="ball"),
                              event(category="unknown"))
        self.assertEqual("conflict", one.status)

    def test_low_confidence_is_not_recognized(self):
        one, = self.summarize(event(confidence=.79))
        self.assertEqual(("low_confidence", "unknown"),
                         (one.status, one.category))

    def test_confidence_conflict_cannot_be_outvoted(self):
        one, = self.summarize(event(category="ball", confidence=.99),
                              event(category="toy", confidence=.99),
                              event(category="ball", confidence=.99))
        self.assertEqual(("conflict", "unknown"),
                         (one.status, one.category))

    def test_low_confidence_on_same_track_blocks_promotion(self):
        one, = self.summarize(event(confidence=.99),
                              event(confidence=.1))
        self.assertEqual("low_confidence", one.status)

    def test_robot_does_not_trust_mock_or_llm_labels(self):
        for source in ("mock", "simulator", "llm_suggestion"):
            with self.subTest(source=source):
                one, = self.summarize(
                    event(source=source),
                    environment="robot",
                )
                self.assertEqual(("untrusted", "unknown"),
                                 (one.status, one.category))

    def test_permitted_robot_source_is_a_claim_not_motor_permission(self):
        snap = snapshot(event(source="sensor"), environment="robot")
        one, = summarize_passive(snap, now=100.2)
        self.assertEqual(("identified", "sensor"),
                         (one.status, one.claimed_source))
        with ExperienceMemory() as memory:
            plan = AutonomyBrain(memory).choose_from_snapshot(snap, now=100.2)
            self.assertEqual("halt", plan.intention)
            self.assertIsNone(memory.get("track-1"))

    def test_untrusted_llm_cannot_override_fresh_sensor_category(self):
        good = event(source="sensor", category="cat")
        bad = event(source="llm_suggestion", category="dog")
        one, = self.summarize(good, bad, environment="robot")
        self.assertEqual(("cat", "identified", "sensor"),
                         (one.category, one.status, one.claimed_source))

    def test_unlisted_legacy_freeform_object_cannot_become_identity(self):
        one, = self.summarize(event(category="Malo"))
        self.assertEqual(("unknown", "unknown"),
                         (one.category, one.status))
        one, = self.summarize(event(category="puppy with collar"))
        self.assertEqual("unknown", one.category)

    def test_separate_tracks_remain_separate_in_order(self):
        a, b, c = self.summarize(
            event(category="ball", track_id="a"),
            event(category="toy", track_id="b"),
            event("sound_label", "meow"),
        )
        self.assertEqual(["a", "b", None],
                         [x.track_id for x in (a, b, c)])
        self.assertEqual(["ball", "toy", "meow"],
                         [x.category for x in (a, b, c)])

    def test_competing_sounds_same_snapshot_cannot_claim_both(self):
        one, = self.summarize(event("sound_label", "bark"),
                              event("sound_label", "meow"))
        self.assertEqual("conflict", one.status)

    def test_motion_safety_kinds_are_not_passive_categories(self):
        safe_area = PerceptionEvent(
            "safe_area", True, "mock", 100., 1., 1.,
        )
        floor = PerceptionEvent(
            "floor_clear", True, "mock", 100., 1., 1.,
        )
        self.assertEqual((), self.summarize(safe_area, floor))

    def test_sound_label_never_alters_legacy_scene_conversion(self):
        base = (
            PerceptionEvent("safe_area", True, "mock", 100., 1., 1.),
            PerceptionEvent("floor_clear", True, "mock", 100., 1., 1.),
            PerceptionEvent("obstacle_m", 1.0, "mock", 100., 1., 1.),
            PerceptionEvent("battery_pct", 90.0, "mock", 100., 1., 1.),
        )
        original = snapshot(*base).to_scene(now=100.2)
        extended = snapshot(*base, event("sound_label", "bark")).to_scene(now=100.2)
        self.assertEqual(original, extended)

    def test_event_budget_fails_closed_not_silently_truncated(self):
        items = [event(track_id=f"track-{i}") for i in range(MAX_EVENTS)]
        self.assertEqual(MAX_EVENTS, len(
            self.summarize(*items)))
        with self.assertRaises(ValueError):
            self.summarize(*(items+[event(track_id="overflow")]))

    def test_invalid_clock_and_snapshot_type_refused(self):
        snap = snapshot(event())
        for now in (True, -1., float("nan"), float("inf"), "today"):
            with self.subTest(now=repr(now)):
                with self.assertRaises(ValueError):
                    summarize_passive(snap, now=now)
        with self.assertRaises(TypeError):
            summarize_passive("not a snapshot", now=100.)

    def test_stale_sounds_are_not_recognized(self):
        one, = self.summarize(event("sound_label", "bark", at=98.))
        self.assertEqual(("stale", "unknown"),
                         (one.status, one.category))

    def test_synthetic_sensor_source_does_not_forge_provenance(self):
        # F1-A checks allowed *labels*. F1-B must authenticate transports.
        one, = self.summarize(
            event("sound_label", "knock", source="sensor"),
            environment="robot",
        )
        self.assertEqual("sensor", one.claimed_source)
        self.assertTrue(one.usable_category)


if __name__ == "__main__":
    unittest.main()
