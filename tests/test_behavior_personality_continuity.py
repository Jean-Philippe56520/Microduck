"""P-B: inspect-only mock habit continuity from the EXISTING F4-A ledger.

No new SQLite schema, model weights, real actions, personal identifiers,
or motor/speaker authority. Observations are not outcomes; only separately
corroborated P2a mock followups can influence the optional F2 tendency.
"""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.behavioral_memory import (
    BehavioralMemory, RETENTION_S,
)
from microduck_companion.behavior_personality import BehaviorPortrait
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.mock_cycles import MockConsequence, MockCycleRunner
from microduck_companion.mock_cycle_demo import mock_snapshot
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot

WALL = 1_780_000_000.0


def unknown_read(t=300.0, seq=1):
    event = PerceptionEvent(
        "object_label", "unknown", "mock", t, 1.0, .98,
        track_id="ephemeral-unknown-track",
    )
    return PassiveRead(
        "ok", PerceptionSnapshot("mock", (event,), t),
        seq, "mock_fixture_unix",
    )


class DurablePersonalityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "one_memory.sqlite"
        self.mem = ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.brain = AutonomyBrain(self.mem)
        self.journal = PassiveObservationJournal(self.mem)
        self.runner = MockCycleRunner(self.mem, session="pb-fiction-only")
        self.behavioral = BehavioralMemory(self.mem)

    def outcome(self, result, index):
        """One distinct *fictional* target, with explicit independent followup."""
        t = 100.0 + 3.0 * index
        target = f"fictional-toy-{index}"
        cycle = self.runner.step(
            mock_snapshot(t, target=target), now=t + .5,
            followup=mock_snapshot(t + .4, target=target),
            consequence=MockConsequence(target, result, t + .3),
        )
        self.assertEqual("inspect_object", cycle.plan.intention)
        self.assertEqual("mock_feedback", cycle.disposition)
        self.assertTrue(self.behavioral.record(
            runner=self.runner, sequence=cycle.sequence,
            now_wall_epoch_s=WALL,
        ))
        return cycle.sequence

    def portrait(self, **kwargs):
        return self.brain.describe_behavior(
            PassiveIntent("inspect", "fixture", "object_label", "unknown"),
            journal=self.journal, now_wall_epoch_s=WALL,
            behavioral=self.behavioral, **kwargs,
        )

    def tick(self, *, now=300.1, with_behavior=True):
        return self.brain.propose_balanced_passive(
            unknown_read(now - .1, seq=1),
            journal=self.journal,
            now_monotonic_s=now, now_wall_epoch_s=WALL,
            behavioral=self.behavioral if with_behavior else None,
        )

    def test_no_history_is_neutral_and_no_new_schema_or_writes(self):
        tables_before = tuple(row[0] for row in self.mem.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
        changes = self.mem.conn.total_changes
        profile = self.portrait()
        self.assertEqual(("neutral", 0.0, 0, 0),
                         (profile.inspection_habit, profile.outcome_bias,
                          profile.mock_positive_outcomes, profile.mock_negative_outcomes))
        self.assertEqual(changes, self.mem.conn.total_changes)
        tables_after = tuple(row[0] for row in self.mem.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
        self.assertEqual(tables_before, tables_after)
        self.assertFalse(profile.executed)
        self.assertFalse(profile.identity_verified)

    def test_one_result_cannot_become_stable_personality(self):
        self.outcome("positive", 0)
        p = self.portrait()
        self.assertEqual((1, 0, .04, "neutral"),
                         (p.mock_positive_outcomes, p.mock_negative_outcomes,
                          p.outcome_bias, p.inspection_habit))
        self.assertEqual(0, p.motor_commands_issued)

    def test_two_verified_mock_positive_followups_make_durable_small_habit(self):
        self.outcome("positive", 0)
        self.outcome("positive", 1)
        p = self.portrait()
        self.assertEqual(("inspection_encouraged", .08, 2, 0),
                         (p.inspection_habit, p.outcome_bias,
                          p.mock_positive_outcomes, p.mock_negative_outcomes))
        self.assertEqual("LookAround", p.state)
        self.assertEqual("unknown", p.familiarity)
        self.assertEqual(0, p.memories_written)
        self.assertEqual(0, p.motor_commands_issued)
        self.assertEqual(0, p.speaker_commands_issued)

        self.mem.close()
        again = ExperienceMemory(self.path)
        self.addCleanup(again.close)
        new_brain = AutonomyBrain(again)
        new_journal = PassiveObservationJournal(again)
        new_history = BehavioralMemory(again)
        reread = new_brain.describe_behavior(
            PassiveIntent("inspect", "fixture", "object_label", "unknown"),
            journal=new_journal, now_wall_epoch_s=WALL + 1,
            behavioral=new_history,
        )
        self.assertEqual(("inspection_encouraged", .08),
                         (reread.inspection_habit, reread.outcome_bias))
        self.assertFalse(reread.physical_execution_authorized)

    def test_negative_mock_outcomes_affect_inspection_only_when_opted_in(self):
        for index in range(3):
            self.outcome("negative", index)
        p = self.portrait()
        self.assertEqual(("inspection_reserved", -.12, 0, 3),
                         (p.inspection_habit, p.outcome_bias,
                          p.mock_positive_outcomes, p.mock_negative_outcomes))
        # Default F2 is untouched when P-B is not explicitly requested.
        baseline = AutonomyBrain(self.mem).propose_balanced_passive(
            unknown_read(), journal=self.journal,
            now_monotonic_s=300.1, now_wall_epoch_s=WALL,
        )
        self.assertEqual("inspect", baseline.intention)
        modified = self.tick()
        self.assertEqual("idle", modified.intention)
        self.assertFalse(modified.executed)
        self.assertEqual(0, modified.motor_commands_issued)
        # A motion plan still fails closed without authenticated safe floor.
        self.assertEqual("halt",
                         self.brain.choose_from_snapshot(
                             unknown_read().snapshot, now=300.1).intention)

    def test_positive_negative_cancel_without_double_learning(self):
        self.outcome("positive", 0)
        self.outcome("negative", 1)
        p = self.portrait()
        self.assertEqual(("neutral", 0.0, 1, 1),
                         (p.inspection_habit, p.outcome_bias,
                          p.mock_positive_outcomes, p.mock_negative_outcomes))
        self.assertFalse(self.behavioral.record(
            runner=self.runner, sequence=2, now_wall_epoch_s=WALL))
        self.assertEqual(0.0, self.portrait().outcome_bias)

    def test_retraction_reverses_habit_without_second_ledger(self):
        self.outcome("positive", 0)
        self.outcome("positive", 1)
        (trace,) = self.behavioral.history(
            now_wall_epoch_s=WALL, limit=1)
        self.assertTrue(self.behavioral.retract(
            trace.mock_cycle_id, reason="fixture_annotation_error"))
        self.assertEqual(("neutral", 1, .04),
                         (self.portrait().inspection_habit,
                          self.portrait().mock_positive_outcomes,
                          self.portrait().outcome_bias))
        self.assertFalse(self.behavioral.retract(
            trace.mock_cycle_id, reason="fixture_annotation_error"))

    def test_expired_feedback_does_not_survive_retention_window(self):
        self.outcome("positive", 0)
        self.outcome("positive", 1)
        gone = self.brain.describe_behavior(
            PassiveIntent("inspect", "fixture", "object_label", "unknown"),
            journal=self.journal,
            now_wall_epoch_s=WALL + RETENTION_S + 1,
            behavioral=self.behavioral,
        )
        self.assertEqual(("neutral", 0.0, 0, 0),
                         (gone.inspection_habit, gone.outcome_bias,
                          gone.mock_positive_outcomes,
                          gone.mock_negative_outcomes))

    def test_missing_original_evidence_is_not_an_outcome(self):
        self.outcome("positive", 0)
        self.outcome("positive", 1)
        with self.mem.conn:
            self.mem.conn.execute(
                "UPDATE mock_cognitive_cycles SET reward=0.3 "
                "WHERE session=? AND sequence=1",
                (self.runner.session,),
            )
        p = self.portrait()
        self.assertEqual(("neutral", .04, 1),
                         (p.inspection_habit, p.outcome_bias,
                          p.mock_positive_outcomes))

    def test_unverified_or_blocked_intention_never_updates_habit(self):
        start = 800.
        blocked = self.runner.step(mock_snapshot(start), now=start+.1)
        self.assertEqual("blocked_motion", blocked.disposition)
        self.assertFalse(self.behavioral.record(
            runner=self.runner, sequence=blocked.sequence,
            now_wall_epoch_s=WALL))
        planned = self.runner.step(
            mock_snapshot(start + 3, target="fictive-unknown"),
            now=start + 3.1)
        self.assertEqual("unverified", planned.disposition)
        self.assertFalse(self.behavioral.record(
            runner=self.runner, sequence=planned.sequence,
            now_wall_epoch_s=WALL))
        self.assertEqual(("neutral", 0.0),
                         (self.portrait().inspection_habit,
                          self.portrait().outcome_bias))

    def test_mismatched_memory_rejected_before_any_decision(self):
        second = ExperienceMemory()
        self.addCleanup(second.close)
        wrong = BehavioralMemory(second)
        with self.assertRaises(ValueError):
            self.brain.describe_behavior(
                PassiveIntent("idle", "mock"),
                journal=self.journal,
                now_wall_epoch_s=WALL,
                behavioral=wrong,
            )
        with self.assertRaises(ValueError):
            self.brain.propose_balanced_passive(
                unknown_read(), journal=self.journal,
                now_monotonic_s=300.1, now_wall_epoch_s=WALL,
                behavioral=wrong,
            )

    def test_missing_corrupt_behavior_table_fails_quietly_without_energy_gain(self):
        self.mem.conn.execute("DROP TABLE f4a_mock_behavior_outcomes")
        energy_before = self.brain.motives.energy
        decision = self.tick()
        self.assertEqual(("idle", "behavioral_history_unavailable"),
                         (decision.intention, decision.reason))
        self.assertEqual(energy_before, self.brain.motives.energy)
        p = self.portrait()
        self.assertEqual(("Chill", "quiet", "unavailable"),
                         (p.state, p.affect, p.inspection_habit))
        self.assertFalse(p.physical_execution_authorized)

    def test_bounded_forged_personality_output_refused(self):
        p = self.portrait()
        args = (p.state, p.affect, p.dominant_motivation,
                p.familiarity, p.category_observations,
                p.attention_bias, p.reason)
        with self.assertRaises(ValueError):
            BehaviorPortrait(*args, outcome_bias=0.25)
        with self.assertRaises(ValueError):
            BehaviorPortrait(*args, mock_positive_outcomes=1000)
        with self.assertRaises(ValueError):
            BehaviorPortrait(*args, inspection_habit="emotion_real")
        with self.assertRaises(ValueError):
            BehaviorPortrait(*args, speaker_commands_issued=1)


if __name__ == "__main__":
    unittest.main()
