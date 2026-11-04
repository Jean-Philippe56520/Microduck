"""VIS-FOCUS-A1: new mock sequences, not pixels, a tracker or OEM validation.

The existing F1/F2 output is the comparator: PassiveIntent contains only a
category. The candidate only describes one current F1 fixture token AFTER F2.
4 positive scenarios + 8 negative gates are pre-registered in issue #78.
"""
from __future__ import annotations

import unittest

from microduck_companion.autonomy import AutonomyBrain, Motivations
from experiments.vis_focus_a1_host import HostFocusComparator, MockFocusHint
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot

WALL = 1_770_000_000.


def sighting(label="ball", *, track="track-ball-a", at=100.,
             confidence=.96, ttl=1., source="mock"):
    return PerceptionEvent(
        "object_label", label, source, at, ttl, confidence, track_id=track,
    )


def frame(*events, seq=1, at=100., status="ok",
          channel="mock_fixture_unix", env="mock"):
    return PassiveRead(status, PerceptionSnapshot(env, tuple(events), at),
                       seq, channel)


class VisualFocusA1(unittest.TestCase):
    def setUp(self):
        self.memory = ExperienceMemory()
        self.addCleanup(self.memory.close)
        self.journal = PassiveObservationJournal(self.memory)
        self.brain = AutonomyBrain(self.memory)
        self.focus = HostFocusComparator()

    def evaluate(self, r, *, now=100.1):
        baseline = self.brain.propose_balanced_passive(
            r, journal=self.journal, now_monotonic_s=now,
            now_wall_epoch_s=WALL + now,
        )
        before = self.memory.conn.total_changes
        old_energy = self.brain.motives.energy
        hint = self.focus.describe_mock_visual_focus(
            r, baseline, now_monotonic_s=now,
        )
        self.assertEqual(before, self.memory.conn.total_changes)
        self.assertEqual(old_energy, self.brain.motives.energy)
        self.assertIsInstance(hint, MockFocusHint)
        self.assertFalse(hint.physical_identity_verified)
        self.assertFalse(hint.location_verified)
        self.assertEqual(0, hint.motor_commands_issued)
        self.assertEqual("mock_fixture_only", hint.source)
        return baseline, hint

    # P1: 3+ current objects, only one optional fixture focus; F2 unchanged.
    def test_positive_three_objects_same_class_single_current_focus(self):
        r = frame(
            sighting("dog", track="track-dog", confidence=.95),
            sighting("ball", track="track-ball-a", confidence=.97),
            sighting("ball", track="track-ball-b", confidence=.91),
        )
        baseline, hint = self.evaluate(r)
        self.assertEqual(("observe", "ball"),
                         (baseline.intention, baseline.target_category))
        self.assertFalse(hasattr(baseline, "track_id"))
        self.assertEqual(("new", "ball", "track-ball-a"),
                         (hint.state, hint.category, hint.current_track_id))
        self.assertEqual(0, self.memory.experience_count())
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT COUNT(*) FROM objects").fetchone()[0])

    # P2: F2's cooldown stops repetitions, but a CURRENT token may remain
    # an unverified passive interest; no act or position is remembered.
    def test_positive_same_fresh_fixture_track_during_f2_cooldown(self):
        self.evaluate(frame(sighting()), now=100.1)
        selected, hint = self.evaluate(frame(
            sighting(at=101., track="track-ball-a"), seq=2, at=101.,
        ), now=101.1)
        self.assertEqual("idle", selected.intention)
        self.assertEqual(("continued", "track-ball-a"),
                         (hint.state, hint.current_track_id))
        self.assertEqual(0, selected.motor_commands_issued)

    # P3: Existing F2 may select a different FRESH category; current focus
    # changes because of that existing decision, not a second scheduler.
    def test_positive_f2_reprioritization_changes_focus(self):
        self.evaluate(frame(sighting()), now=100.1)
        selected, hint = self.evaluate(frame(
            sighting("ball", at=101., track="track-ball-a"),
            sighting("dog", at=101., track="track-dog"),
            seq=2, at=101.,
        ), now=101.1)
        self.assertEqual(("observe", "dog"),
                         (selected.intention, selected.target_category))
        self.assertEqual(("new", "dog", "track-dog"),
                         (hint.state, hint.category, hint.current_track_id))

    # P4: when one token is lost, a subsequent token is NEW, never proven
    # to refer to the same physical ball or person.
    def test_positive_loss_then_new_observation_is_not_reidentification(self):
        self.evaluate(frame(sighting()), now=100.1)
        _, missing = self.evaluate(frame(seq=2, at=101.), now=101.1)
        self.assertEqual(("none", None), (missing.state, missing.current_track_id))
        selected, new = self.evaluate(frame(
            sighting(at=104., track="track-ball-other"), seq=3, at=104.,
        ), now=104.1)
        self.assertEqual("observe", selected.intention)
        self.assertEqual(("new", "track-ball-other"),
                         (new.state, new.current_track_id))

    # N1: a broken or non-authenticated mock channel never keeps focus.
    def test_negative_source_loss_or_wrong_channel_discards_interest(self):
        self.evaluate(frame(sighting()), now=100.1)
        for read in (
            frame(seq=2, at=101., status="unavailable_or_invalid"),
            frame(sighting(at=101.), seq=2, at=101.,
                  channel="untrusted_channel"),
        ):
            _, hint = self.evaluate(read, now=101.1)
            self.assertEqual("none", hint.state)

    # N2: a previous label with TTL elapsed is not current position.
    def test_negative_stale_event_discards_interest(self):
        self.evaluate(frame(sighting()), now=100.1)
        selected, hint = self.evaluate(frame(
            sighting(at=100.5, ttl=.5), seq=2, at=101.5,
        ), now=101.6)
        self.assertEqual("idle", selected.intention)
        self.assertEqual("none", hint.state)

    # N3: future timestamps, repeated/out-of-order source IDs, clock reset.
    def test_negative_future_duplicate_and_clock_reset(self):
        self.evaluate(frame(sighting()), now=100.1)
        _, future = self.evaluate(frame(
            sighting(at=102.), seq=2, at=102.,
        ), now=101.9)
        self.assertEqual("none", future.state)
        _, repeated = self.evaluate(frame(
            sighting(at=103.), seq=1, at=103.,
        ), now=103.1)
        self.assertEqual(("none", "duplicate_or_out_of_order_fixture"),
                         (repeated.state, repeated.reason))
        _, reset = self.evaluate(frame(
            sighting(at=99.), seq=3, at=99.,
        ), now=99.1)
        self.assertEqual("none", reset.state)

    # N4: contradictory categories on one token are not an identity.
    def test_negative_conflicting_labels_never_get_a_focus_token(self):
        selected, hint = self.evaluate(frame(
            sighting("ball"), sighting("toy"),
        ), now=100.1)
        self.assertEqual(("inspect", "unknown"),
                         (selected.intention, selected.target_category))
        self.assertEqual(("none", None), (hint.state, hint.current_track_id))

    # N5: confidence below F1 threshold never selects any fixture token.
    def test_negative_low_confidence_is_not_promoted(self):
        selected, hint = self.evaluate(frame(
            sighting(confidence=.30),
        ), now=100.1)
        self.assertEqual("idle", selected.intention)
        self.assertEqual("none", hint.state)

    # N6: two same-category tokens cannot be bridged across source swaps.
    def test_negative_same_category_new_id_is_not_old_identity(self):
        self.evaluate(frame(sighting()), now=100.1)
        selected, lost = self.evaluate(frame(
            sighting(at=101., track="track-ball-b"), seq=2, at=101.,
        ), now=101.1)
        self.assertEqual("idle", selected.intention)
        self.assertEqual("none", lost.state)
        _, fresh = self.evaluate(frame(
            sighting(at=104., track="track-ball-b"), seq=3, at=104.,
        ), now=104.1)
        self.assertEqual(("new", "track-ball-b"),
                         (fresh.state, fresh.current_track_id))

    # N7: no F1 property says TV/photo/plush versus a real subject; this
    # test MUST NOT claim recognition of either a real human or depiction.
    def test_negative_screen_depiction_cannot_be_called_real_presence(self):
        selected, hint = self.evaluate(frame(
            sighting("person", track="track-screen-person"),
        ), now=100.1)
        self.assertEqual("person", selected.target_category)
        self.assertEqual("new", hint.state)
        self.assertFalse(hint.physical_identity_verified)
        self.assertFalse(hint.location_verified)
        with self.assertRaisesRegex(ValueError, "cannot certify"):
            MockFocusHint("new", "track-screen-person", "person",
                          physical_identity_verified=True)

    # N8: a mock visual interest never defeats the independent safety gate.
    def test_negative_no_floor_tof_or_operator_clearance_is_halt(self):
        r = frame(sighting())
        selected, hint = self.evaluate(r, now=100.1)
        self.assertEqual("halt",
                         self.brain.choose_from_snapshot(r.snapshot,
                                                         now=100.1).intention)
        self.assertEqual(0, selected.motor_commands_issued)
        self.assertEqual(0, hint.motor_commands_issued)
        self.assertFalse(hint.location_verified)

    def test_existing_sqlite_category_familiarity_changes_f2_not_focus_rules(self):
        old = frame(sighting())
        self.assertEqual(1, self.journal.append(
            old, now_monotonic_s=100.1, now_wall_epoch_s=WALL,
        ))
        selected, hint = self.evaluate(frame(
            sighting("ball", track="track-ball-a"),
            sighting("dog", track="track-dog"),
        ), now=100.1)
        self.assertEqual(("observe", "dog"),
                         (selected.intention, selected.target_category))
        self.assertEqual("track-dog", hint.current_track_id)

    def test_unknown_object_is_only_an_uncertain_passive_interest(self):
        selected, hint = self.evaluate(frame(
            sighting("unknown", track="track-unknown"),
        ), now=100.1)
        self.assertEqual(("inspect", "unknown"),
                         (selected.intention, selected.target_category))
        self.assertEqual(("new", "unknown", "track-unknown"),
                         (hint.state, hint.category, hint.current_track_id))
        self.assertFalse(hint.physical_identity_verified)

    def test_invalid_inputs_refused_and_no_safety_or_oem_added(self):
        selected, _ = self.evaluate(frame(sighting()), now=100.1)
        with self.assertRaises(TypeError):
            self.focus.describe_mock_visual_focus("not-a-read", selected,
                                                  now_monotonic_s=101.)
        with self.assertRaises(ValueError):
            self.focus.describe_mock_visual_focus(
                frame(sighting()), selected, now_monotonic_s=float("nan"))
        _, hint = self.evaluate(frame(
            PerceptionEvent("safe_area", True, "mock", 101., 1., 1.),
            seq=2, at=101.,
        ), now=101.1)
        self.assertEqual("none", hint.state)
        _, hint = self.evaluate(frame(
            sighting("ball", at=102., source="sensor"),
            seq=3, at=102.,
        ), now=102.1)
        self.assertEqual("none", hint.state)


if __name__ == "__main__":
    unittest.main()
