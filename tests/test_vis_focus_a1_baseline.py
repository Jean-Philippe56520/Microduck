"""VIS-FOCUS-A1: source-faithful F1/F2 baseline on declared mock sequences.

No camera, model, NPU, robot, tracker or physical identity proof. These tests
characterize the existing category-only attention and fail-closed boundaries.
"""
from __future__ import annotations

from dataclasses import fields
import unittest

from microduck_companion import (
    AutonomyBrain, ExperienceMemory, Motivations, PassiveObservationJournal,
    PerceptionEvent, PerceptionSnapshot,
)
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_sources import PassiveRead

WALL = 1_770_000_000.0


def observed(category="ball", *, mono=100.0, track="track-fixture-1",
             confidence=0.96, ttl=1.0):
    return PerceptionEvent(
        "object_label", category, "mock", mono, ttl, confidence, track_id=track
    )


def receipt(*events, at=100.0, seq=1, status="ok"):
    return PassiveRead(
        status, PerceptionSnapshot("mock", tuple(events), at),
        seq, "mock_fixture_unix",
    )


class VisFocusA1ExistingBaseline(unittest.TestCase):
    def setUp(self):
        self.memory = ExperienceMemory()
        self.addCleanup(self.memory.close)
        self.journal = PassiveObservationJournal(self.memory)
        self.brain = AutonomyBrain(self.memory)

    def decide(self, read, *, now=100.1):
        result = self.brain.propose_balanced_passive(
            read, journal=self.journal,
            now_monotonic_s=now, now_wall_epoch_s=WALL + (now - 100.0),
        )
        self.assertEqual("mock", result.source)
        self.assertFalse(result.executed)
        self.assertEqual(0, result.motor_commands_issued)
        return result

    def test_p1_three_objects_one_primary_category_by_motivation(self):
        self.brain.motives = Motivations(
            curiosity=0.35, sociability=0.55, play=1.0, energy=1.0,
            caution=0.2, determination=0.55,
        )
        plan = self.decide(receipt(
            observed("dog", track="track-fixture-dog"),
            observed("cat", track="track-fixture-cat"),
            observed("toy", track="track-fixture-toy"),
        ))
        self.assertEqual(("observe", "toy"), (plan.intention, plan.target_category))
        self.assertNotIn("track-fixture", repr(plan))

    def test_p2_same_declared_track_during_cooldown_does_not_repeat(self):
        first = self.decide(receipt(observed()), now=100.1)
        second = self.decide(receipt(
            observed(mono=101.0), at=101.0, seq=2), now=101.1)
        self.assertEqual(("observe", "idle"),
                         (first.intention, second.intention))
        self.assertIsNone(second.target_category)
        self.assertEqual(0, self.memory.experience_count())

    def test_p3_new_current_category_can_replace_attention(self):
        first = self.decide(receipt(observed("ball")), now=100.1)
        second = self.decide(receipt(
            observed("dog", mono=101.0, track="track-fixture-dog"),
            at=101.0, seq=2), now=101.1)
        self.assertEqual(("ball", "dog"),
                         (first.target_category, second.target_category))

    def test_p4_after_missing_frame_new_uncertain_cue_is_not_old_position(self):
        first = self.decide(receipt(observed()), now=100.1)
        loss = self.decide(receipt(at=101.0, seq=2), now=101.1)
        reacquired = self.decide(receipt(
            observed("unknown", mono=102.0, track="track-fixture-new"),
            at=102.0, seq=3), now=102.1)
        self.assertEqual("observe", first.intention)
        self.assertEqual("idle", loss.intention)
        self.assertEqual(("inspect", "unknown"),
                         (reacquired.intention, reacquired.target_category))
        self.assertIsNone(self.memory.get("track-fixture-1"))

    def test_n1_source_unavailable_is_idle(self):
        self.assertEqual("idle", self.decide(receipt(
            observed(), status="unavailable_or_invalid")).intention)

    def test_n2_expired_observation_is_not_current(self):
        self.assertEqual("idle", self.decide(receipt(
            observed(mono=98.0), at=100.0)).intention)

    def test_n3_future_snapshot_is_not_current(self):
        self.assertEqual("idle", self.decide(receipt(
            observed(mono=101.0), at=101.0), now=100.1).intention)

    def test_n4_conflicting_class_on_one_declared_track_remains_unknown(self):
        result = self.decide(receipt(observed("ball"), observed("toy")))
        self.assertEqual(("inspect", "unknown"),
                         (result.intention, result.target_category))

    def test_n5_low_confidence_not_promoted(self):
        self.assertEqual("idle", self.decide(receipt(
            observed(confidence=0.20))).intention)

    def test_n6_two_same_category_tracks_have_no_verified_identity_output(self):
        plan = self.decide(receipt(
            observed("ball", track="track-fixture-a"),
            observed("ball", track="track-fixture-b"),
        ))
        self.assertEqual(("observe", "ball"),
                         (plan.intention, plan.target_category))
        self.assertNotIn("track_id", {f.name for f in fields(PassiveIntent)})
        self.assertNotIn("track-fixture-a", repr(plan))
        self.assertNotIn("track-fixture-b", repr(plan))

    def test_n7_category_label_cannot_verify_physical_vs_screen_person(self):
        plan = self.decide(receipt(observed("person")))
        self.assertEqual(("observe", "person"),
                         (plan.intention, plan.target_category))
        self.assertFalse(plan.executed)
        self.assertNotIn("is_physical", {f.name for f in fields(PassiveIntent)})
        self.assertEqual(0, self.memory.experience_count())

    def test_n8_missing_safety_has_no_motor_permission(self):
        r = receipt(observed("ball"))
        proposal = self.decide(r)
        safety_plan = self.brain.choose_from_snapshot(r.snapshot, now=100.1)
        self.assertEqual("halt", safety_plan.intention)
        self.assertFalse(proposal.executed)
        self.assertEqual(0, proposal.motor_commands_issued)
        self.assertEqual(0, self.memory.experience_count())


if __name__ == "__main__":
    unittest.main()
