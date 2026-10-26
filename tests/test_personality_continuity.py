"""P-B: fictional, reversible personality habits using the ONE existing SQLite.

Only corroborated mock P2a outcomes may adjust the existing F2 inspection
score, and only on explicit opt-in. No identity, sound, camera or motor output.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain, Motivations
from microduck_companion.behavior_personality import MIN_HABIT_EVIDENCE
from microduck_companion.behavioral_memory import BehavioralMemory, RETENTION_S
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.mock_cycle_demo import mock_snapshot
from microduck_companion.mock_cycles import MockConsequence, MockCycleRunner
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot


WALL = 1_780_000_000.0


def unknown_fixture(*, t=200., seq=1, status="ok", channel="mock_fixture_unix"):
    event = PerceptionEvent(
        "object_label", "unknown", "mock", t, 1., .95,
        track_id="ephemeral-fixture-not-identity",
    )
    return PassiveRead(
        status, PerceptionSnapshot("mock", (event,), t), seq, channel,
    )


def inspect_proposal():
    return PassiveIntent(
        "inspect", "unresolved_fictional_object_category",
        "object_label", "unknown",
    )


class PersonalityContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "existing-experience.sqlite3"
        self.memory = ExperienceMemory(self.path)
        self.addCleanup(self.memory.close)
        self.brain = AutonomyBrain(self.memory)
        self.journal = PassiveObservationJournal(self.memory)
        self.runner = MockCycleRunner(self.memory, session="fictional-pb")
        self.behavioral = BehavioralMemory(self.memory)

    def outcome(self, result="positive", *, t=100., target="fictional-toy"):
        cycle = self.runner.step(
            mock_snapshot(t, target=target), now=t + .5,
            followup=mock_snapshot(t + .4, target=target),
            consequence=MockConsequence(target, result, t + .3),
        )
        self.assertEqual("mock_feedback", cycle.disposition)
        self.assertEqual("inspect_object", cycle.plan.intention)
        return cycle.sequence

    def record(self, result="positive", *, t=100., target="fictional-toy"):
        sequence = self.outcome(result, t=t, target=target)
        self.assertTrue(self.behavioral.record(
            runner=self.runner, sequence=sequence, now_wall_epoch_s=WALL))
        return sequence

    def portrait(self, *, memory=None, brain=None, journal=None,
                 behavioral=None, now=WALL):
        decision = inspect_proposal()
        return (brain or self.brain).describe_behavior(
            decision, journal=journal or self.journal,
            now_wall_epoch_s=now,
            behavioral=self.behavioral if behavioral is None else behavioral,
        )

    def test_no_outcomes_stays_neutral_and_read_only(self):
        before = self.memory.conn.total_changes
        p = self.portrait()
        self.assertEqual(("LookAround", "curious", "neutral"),
                         (p.state, p.affect, p.inspection_habit))
        self.assertEqual((0.0, 0, 0),
                         (p.outcome_bias, p.mock_positive_outcomes,
                          p.mock_negative_outcomes))
        self.assertEqual(before, self.memory.conn.total_changes)
        self.assertFalse(p.physical_execution_authorized)
        self.assertFalse(p.executed)

    def test_one_success_is_too_little_to_claim_stable_habit(self):
        self.record()
        p = self.portrait()
        self.assertEqual(2, MIN_HABIT_EVIDENCE)
        self.assertEqual("neutral", p.inspection_habit)
        self.assertAlmostEqual(.04, p.outcome_bias)
        self.assertEqual(1, p.mock_positive_outcomes)

    def test_two_corroborated_mock_successes_create_bounded_habit(self):
        self.record(target="toy-one")
        self.record(t=105., target="toy-two")
        before = self.memory.conn.total_changes
        p = self.portrait()
        self.assertEqual(("inspection_encouraged", 2, 0),
                         (p.inspection_habit, p.mock_positive_outcomes,
                          p.mock_negative_outcomes))
        self.assertAlmostEqual(.08, p.outcome_bias)
        self.assertEqual(0, p.motor_commands_issued)
        self.assertEqual(0, p.speaker_commands_issued)
        self.assertEqual(0, p.pc_requests_issued)
        self.assertEqual(0, p.memories_written)
        self.assertFalse(p.identity_verified)
        self.assertEqual(before, self.memory.conn.total_changes)
        self.assertNotIn("toy-one", str(p))
        self.assertNotIn("toy-two", str(p))

    def test_negative_mock_outcomes_reverse_the_habit(self):
        self.record("negative", target="toy-one")
        self.record("negative", t=105., target="toy-two")
        p = self.portrait()
        self.assertEqual("inspection_reserved", p.inspection_habit)
        self.assertAlmostEqual(-.08, p.outcome_bias)

    def test_conflicting_outcomes_cancel_without_fake_mood(self):
        self.record("positive", target="toy-one")
        self.record("negative", t=105., target="toy-two")
        p = self.portrait()
        self.assertEqual("neutral", p.inspection_habit)
        self.assertEqual((1, 1), (p.mock_positive_outcomes, p.mock_negative_outcomes))
        self.assertEqual(0.0, p.outcome_bias)
        self.assertEqual("curious", p.affect)

    def test_persisted_habit_survives_restart_without_a_second_database(self):
        self.record(target="toy-one")
        self.record(t=105., target="toy-two")
        original = self.portrait()
        self.memory.close()
        opened = ExperienceMemory(self.path)
        self.addCleanup(opened.close)
        reopened_brain = AutonomyBrain(opened)
        reopened_journal = PassiveObservationJournal(opened)
        reopened_behavior = BehavioralMemory(opened)
        before = opened.conn.total_changes
        other = self.portrait(
            brain=reopened_brain, journal=reopened_journal,
            behavioral=reopened_behavior,
        )
        self.assertEqual(original, other)
        self.assertEqual(before, opened.conn.total_changes)
        self.assertIs(reopened_brain.memory, reopened_journal._memory)
        self.assertIs(reopened_behavior._memory, reopened_brain.memory)

    def test_retract_existing_evidence_recomputes_without_relearning(self):
        self.record(target="toy-one")
        self.record(t=105., target="toy-two")
        self.assertEqual("inspection_encouraged", self.portrait().inspection_habit)
        trace = self.behavioral.history(now_wall_epoch_s=WALL)
        self.assertEqual(2, len(trace))
        self.assertTrue(self.behavioral.retract(
            trace[0].mock_cycle_id, reason="fixture_annotation_error"))
        p = self.portrait()
        self.assertEqual("neutral", p.inspection_habit)
        self.assertEqual(1, p.mock_positive_outcomes)
        self.assertAlmostEqual(.04, p.outcome_bias)
        self.assertFalse(self.behavioral.retract(
            trace[0].mock_cycle_id, reason="fixture_annotation_error"))

    def test_expiry_returns_to_neutral_without_erasing_original_provenance(self):
        self.record(target="toy-one")
        self.record(t=105., target="toy-two")
        p = self.portrait(now=WALL + RETENTION_S + 1.)
        self.assertEqual("neutral", p.inspection_habit)
        self.assertEqual((0, 0, 0.), (p.mock_positive_outcomes,
                                      p.mock_negative_outcomes, p.outcome_bias))
        self.assertFalse(p.identity_verified)

    def test_unexecuted_proposal_cannot_promote_habit(self):
        cycle = self.runner.step(
            mock_snapshot(100., target="fictional-toy"), now=100.1)
        self.assertEqual("unverified", cycle.disposition)
        self.assertFalse(self.behavioral.record(
            runner=self.runner, sequence=cycle.sequence,
            now_wall_epoch_s=WALL))
        self.assertEqual("neutral", self.portrait().inspection_habit)

    def test_repeated_record_does_not_reward_twice(self):
        sequence = self.record()
        self.assertFalse(self.behavioral.record(
            runner=self.runner, sequence=sequence,
            now_wall_epoch_s=WALL))
        self.assertEqual(1, self.portrait().mock_positive_outcomes)

    def test_opt_in_only_can_gently_change_f2_inspect_vs_idle(self):
        self.record(target="toy-one")
        self.record(t=105., target="toy-two")
        motives = dict(curiosity=.64, caution=.43, sociability=.55,
                      play=.60, energy=.80)
        plain = AutonomyBrain(self.memory, Motivations(**motives))
        optin = AutonomyBrain(self.memory, Motivations(**motives))
        reading = unknown_fixture()
        no_habit = plain.propose_balanced_passive(
            reading, journal=self.journal,
            now_monotonic_s=200.1, now_wall_epoch_s=WALL)
        with_habit = optin.propose_balanced_passive(
            reading, journal=self.journal,
            now_monotonic_s=200.1, now_wall_epoch_s=WALL,
            behavioral=self.behavioral)
        self.assertEqual("idle", no_habit.intention)
        self.assertEqual("inspect", with_habit.intention)
        self.assertFalse(with_habit.executed)
        self.assertEqual(0, with_habit.motor_commands_issued)
        self.assertEqual("halt", optin.choose_from_snapshot(
            reading.snapshot, now=200.1).intention)

    def test_negative_habit_can_reduce_inspection_without_motor_actions(self):
        self.record("negative", target="toy-one")
        self.record("negative", t=105., target="toy-two")
        motives = dict(curiosity=.75, caution=.4, sociability=.55,
                      play=.60, energy=.8)
        reading = unknown_fixture()
        plain = AutonomyBrain(self.memory, Motivations(**motives))
        optin = AutonomyBrain(self.memory, Motivations(**motives))
        a = plain.propose_balanced_passive(reading, journal=self.journal,
                 now_monotonic_s=200.1, now_wall_epoch_s=WALL)
        b = optin.propose_balanced_passive(reading, journal=self.journal,
                 now_monotonic_s=200.1, now_wall_epoch_s=WALL,
                 behavioral=self.behavioral)
        self.assertEqual(("inspect", "idle"), (a.intention, b.intention))
        self.assertEqual(0, b.motor_commands_issued)

    def test_bad_fixture_cannot_use_a_positive_habit_to_activate(self):
        self.record(target="toy-one")
        self.record(t=105., target="toy-two")
        for kw in (dict(channel="untrusted_socket"),
                   dict(status="unavailable_or_invalid")):
            with self.subTest(kw=kw):
                brain = AutonomyBrain(self.memory)
                energy = brain.motives.energy
                result = brain.propose_balanced_passive(
                    unknown_fixture(**kw), journal=self.journal,
                    now_monotonic_s=200.1, now_wall_epoch_s=WALL,
                    behavioral=self.behavioral)
                self.assertEqual("idle", result.intention)
                self.assertEqual(energy, brain.motives.energy)

    def test_cross_sqlite_and_wrong_type_are_rejected(self):
        alien = ExperienceMemory()
        self.addCleanup(alien.close)
        foreign = BehavioralMemory(alien)
        r = unknown_fixture()
        with self.assertRaises(ValueError):
            self.brain.propose_balanced_passive(r, journal=self.journal,
                now_monotonic_s=200.1, now_wall_epoch_s=WALL,
                behavioral=foreign)
        with self.assertRaises(ValueError):
            self.brain.describe_behavior(inspect_proposal(),
                journal=self.journal, now_wall_epoch_s=WALL,
                behavioral=foreign)
        with self.assertRaises(TypeError):
            self.brain.describe_behavior(inspect_proposal(),
                journal=self.journal, now_wall_epoch_s=WALL,
                behavioral="forged_positive_outcome")

    def test_closed_database_defaults_to_quiet_with_no_energy_change(self):
        self.record(target="toy-one")
        self.record(t=105., target="toy-two")
        brain = AutonomyBrain(self.memory)
        energy = brain.motives.energy
        self.memory.close()
        p = self.portrait(brain=brain)
        self.assertEqual(("Chill", "quiet", "unavailable"),
                         (p.state, p.affect, p.inspection_habit))
        self.assertEqual((0., 0, 0), (p.outcome_bias,
                                      p.mock_positive_outcomes,
                                      p.mock_negative_outcomes))
        result = brain.propose_balanced_passive(
            unknown_fixture(), journal=self.journal,
            now_monotonic_s=200.1, now_wall_epoch_s=WALL,
            behavioral=self.behavioral)
        self.assertEqual("idle", result.intention)
        self.assertEqual("behavioral_history_unavailable", result.reason)
        self.assertEqual(energy, brain.motives.energy)

    def test_invalid_claims_cannot_be_forged_into_portraits(self):
        p = self.portrait()
        with self.assertRaises(ValueError):
            replace(p, outcome_bias=.8)
        with self.assertRaises(ValueError):
            replace(p, mock_positive_outcomes=1000)
        with self.assertRaises(ValueError):
            replace(p, inspection_habit="obey_motor_command")
        with self.assertRaises(ValueError):
            replace(p, motor_commands_issued=1)


    def test_reading_history_creates_no_new_schema_or_write(self):
        tables_before = tuple(row[0] for row in self.memory.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
        before = self.memory.conn.total_changes
        self.portrait()
        self.assertEqual(before, self.memory.conn.total_changes)
        tables_after = tuple(row[0] for row in self.memory.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
        self.assertEqual(tables_before, tables_after)

    def test_corrupted_original_evidence_does_not_create_a_habit(self):
        self.record(target="toy-one")
        self.record(t=105., target="toy-two")
        with self.memory.conn:
            self.memory.conn.execute(
                "UPDATE mock_cognitive_cycles SET reward=0.3 "
                "WHERE session=? AND sequence=1", (self.runner.session,))
        p = self.portrait()
        self.assertEqual("neutral", p.inspection_habit)
        self.assertEqual(1, p.mock_positive_outcomes)
        self.assertAlmostEqual(.04, p.outcome_bias)

    def test_blocked_motion_is_not_a_personality_result(self):
        cycle = self.runner.step(mock_snapshot(100.), now=100.1)
        self.assertEqual("blocked_motion", cycle.disposition)
        self.assertFalse(self.behavioral.record(
            runner=self.runner, sequence=cycle.sequence,
            now_wall_epoch_s=WALL))
        self.assertEqual(("neutral", 0.0),
                         (self.portrait().inspection_habit,
                          self.portrait().outcome_bias))

    def test_missing_behavior_table_fails_closed_without_energy_gain(self):
        self.memory.conn.execute("DROP TABLE f4a_mock_behavior_outcomes")
        energy = self.brain.motives.energy
        result = self.brain.propose_balanced_passive(
            unknown_fixture(), journal=self.journal,
            now_monotonic_s=200.1, now_wall_epoch_s=WALL,
            behavioral=self.behavioral)
        self.assertEqual(("idle", "behavioral_history_unavailable"),
                         (result.intention, result.reason))
        self.assertEqual(energy, self.brain.motives.energy)
        p = self.portrait()
        self.assertEqual(("Chill", "quiet", "unavailable"),
                         (p.state, p.affect, p.inspection_habit))
        self.assertFalse(p.physical_execution_authorized)


if __name__ == "__main__":
    unittest.main()
