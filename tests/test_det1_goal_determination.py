"""DET-1: paired mock-only ablations for the EXISTING F2 decision path."""
from __future__ import annotations

import math
from pathlib import Path
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain, Motivations
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_ledger import MockExperienceLedger, MockResolution
from microduck_companion.mock_goal_memory import MockGoalMemory
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot

WALL = 1_770_000_000.0
GOAL_DOG = "g-00000000000000d1"
GOAL_UNKNOWN = "g-00000000000000d2"
SESSION = "s-00000000000000d1"


def read(*categories: str, t: float = 100.0, seq: int = 1,
         status: str = "ok", source: str = "mock",
         environment: str = "mock", confidence: float = .96) -> PassiveRead:
    events = tuple(
        PerceptionEvent("object_label", cat, source, t, 1.0, confidence,
                        track_id=f"fixture-track-{i}")
        for i, cat in enumerate(categories)
    )
    return PassiveRead(
        status=status,
        snapshot=PerceptionSnapshot(environment, events, t),
        sequence=seq,
    )


class DET1DeterminationTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.memory = ExperienceMemory(Path(scratch.name) / "only.sqlite3")
        self.addCleanup(self.memory.close)
        self.journal = PassiveObservationJournal(self.memory)
        self.ledger = MockExperienceLedger(self.memory)
        self.goals = MockGoalMemory(self.memory, self.ledger)

    def add_goal(self, key=GOAL_DOG, category="dog",
                 kind="observe_category", *, created=WALL, state="active"):
        self.goals.create(
            goal_id=key, kind=kind, category=category,
            resume_when="new_view", at_epoch_s=created)
        if state != "candidate":
            self.goals.transition(
                goal_id=key, expected_revision=1,
                next_state="active", reason="begin_mock_goal",
                at_epoch_s=created + .1)
        if state == "suspended":
            self.goals.transition(
                goal_id=key, expected_revision=2,
                next_state="suspended", reason="repeat_blocked",
                at_epoch_s=created + .2)

    def choose(self, *, determination: float, goals=True, frame=None,
               at=WALL+1, mono=100.1):
        brain = AutonomyBrain(self.memory,
                             Motivations(determination=determination))
        proposal = brain.propose_balanced_passive(
            frame or read("dog", "ball"),
            journal=self.journal, now_monotonic_s=mono,
            now_wall_epoch_s=at, goals=self.goals if goals else None)
        return brain, proposal

    def test_paired_ablation_same_scene_high_determination_changes_priority(self):
        self.add_goal()
        control, baseline = self.choose(determination=0., goals=True)
        optional, no_goals = self.choose(determination=1., goals=False)
        focused, high = self.choose(determination=1., goals=True)
        self.assertEqual("ball", baseline.target_category)
        self.assertEqual("ball", no_goals.target_category)
        self.assertEqual(("observe", "dog", "det1_mock_goal_focus"),
                         (high.intention, high.target_category, high.reason))
        self.assertEqual("mock", high.source)
        self.assertFalse(high.executed)
        self.assertFalse(high.request_pc_analysis)
        self.assertEqual(0, high.motor_commands_issued)
        self.assertEqual(0, self.memory.experience_count())
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT count(*) FROM mem1_mock_goal_links").fetchone()[0])
        self.assertEqual("active", self.goals.get(GOAL_DOG).state)
        self.assertEqual(1, focused.passive_rhythm_metrics().cycles)
        self.assertEqual(1, control.passive_rhythm_metrics().cycles)
        self.assertEqual(1, optional.passive_rhythm_metrics().cycles)

    def test_existing_f2_can_still_choose_idle_at_high_caution(self):
        self.add_goal()
        brain = AutonomyBrain(
            self.memory, Motivations(curiosity=0., play=0., caution=1.,
                                     determination=1.))
        result = brain.propose_balanced_passive(
            read("dog", "ball"), journal=self.journal, goals=self.goals,
            now_monotonic_s=100.1, now_wall_epoch_s=WALL+1)
        self.assertEqual("idle", result.intention)
        self.assertEqual(0, result.motor_commands_issued)

    def test_cooldown_precedes_determination_even_on_same_unattempted_goal(self):
        self.add_goal()
        brain = AutonomyBrain(self.memory,
                             Motivations(determination=1.))
        first = brain.propose_balanced_passive(
            read("dog", t=100., seq=1), journal=self.journal, goals=self.goals,
            now_monotonic_s=100.1, now_wall_epoch_s=WALL+1)
        second = brain.propose_balanced_passive(
            read("dog", t=101., seq=2), journal=self.journal, goals=self.goals,
            now_monotonic_s=101.1, now_wall_epoch_s=WALL+2)
        self.assertEqual("observe", first.intention)
        self.assertEqual("det1_mock_goal_focus", first.reason)
        self.assertEqual("idle", second.intention)
        self.assertEqual(1, brain.passive_rhythm_metrics().cooldown_blocks)
        self.assertEqual(0, brain.passive_rhythm_metrics().consecutive_active_repeats)

    def test_previous_attempt_even_proposed_blocks_second_determination_boost(self):
        self.add_goal()
        initial = self.choose(determination=1.)[1]
        self.assertEqual("dog", initial.target_category)
        self.ledger.record_proposal(
            PassiveIntent("observe", "fixture", "object_label", "dog"),
            session=SESSION, sequence=1, proposed_at_epoch_s=WALL+.5)
        self.goals.link_attempt(
            goal_id=GOAL_DOG, session=SESSION, sequence=1,
            strategy="observe_from_distance", context="initial",
            at_epoch_s=WALL+.75)
        self.assertEqual(frozenset(), self.goals.attention_focus(
            now_wall_epoch_s=WALL+1))
        result = self.choose(determination=1.)[1]
        self.assertEqual(("observe", "ball", "novel_mock_category"),
                         (result.intention, result.target_category, result.reason))
        self.ledger.retract(
            session=SESSION, sequence=1, reason="source_retracted")
        result_after_retraction = self.choose(determination=1.)[1]
        self.assertEqual("ball", result_after_retraction.target_category)
        self.assertFalse(result_after_retraction.executed)

    def test_retraction_suspension_correction_and_expiry_do_not_focus(self):
        for state in ("candidate", "suspended", "retracted", "old"):
            with self.subTest(state=state):
                scratch = tempfile.TemporaryDirectory()
                self.addCleanup(scratch.cleanup)
                memory = ExperienceMemory(Path(scratch.name)/"fixture.sqlite3")
                self.addCleanup(memory.close)
                journal = PassiveObservationJournal(memory)
                ledger = MockExperienceLedger(memory)
                goals = MockGoalMemory(memory, ledger)
                created = WALL - 15*24*3600 if state == "old" else WALL
                goals.create(goal_id=GOAL_DOG, kind="observe_category",
                             category="dog", resume_when="new_view",
                             at_epoch_s=created)
                if state != "candidate":
                    goals.transition(
                        goal_id=GOAL_DOG, expected_revision=1,
                        next_state="active", reason="begin_mock_goal",
                        at_epoch_s=created + .1)
                if state == "suspended":
                    goals.transition(
                        goal_id=GOAL_DOG, expected_revision=2,
                        next_state="suspended", reason="uncertain",
                        at_epoch_s=WALL+.2)
                if state == "retracted":
                    goals.retract(goal_id=GOAL_DOG, reason="source_retracted")
                brain = AutonomyBrain(memory, Motivations(determination=1.))
                p = brain.propose_balanced_passive(
                    read("dog", "ball"), journal=journal, goals=goals,
                    now_monotonic_s=100.1, now_wall_epoch_s=WALL+1)
                self.assertEqual("ball", p.target_category)

    def test_stored_goal_does_not_create_undetected_or_familiar_candidate(self):
        self.add_goal()
        _, ball_only = self.choose(
            determination=1., frame=read("ball"))
        self.assertEqual("ball", ball_only.target_category)
        # F1 makes the category familiar, no EX3 positive trend: DET-1
        # cannot fabricate a candidate which F2 declined to admit.
        self.journal.append(read("dog"), now_monotonic_s=100.1,
                            now_wall_epoch_s=WALL)
        _, familiar = self.choose(
            determination=1., frame=read("dog"))
        self.assertEqual("idle", familiar.intention)
        self.assertEqual(0, familiar.motor_commands_issued)

    def test_unknown_goal_can_only_rank_existing_uncertain_inspection(self):
        self.add_goal(GOAL_UNKNOWN, "unknown", "inspect_unknown")
        _, baseline = self.choose(
            determination=0., frame=read("unknown", "ball"))
        _, high = self.choose(
            determination=1., frame=read("unknown", "ball"))
        self.assertEqual("ball", baseline.target_category)
        self.assertEqual(("inspect", "unknown", "det1_mock_goal_focus"),
                         (high.intention, high.target_category, high.reason))
        self.assertFalse(high.executed)

    def test_unavailable_and_stale_observations_still_fail_closed(self):
        self.add_goal()
        cases = [
            read("dog", status="unavailable_or_invalid"),
            read("dog", environment="robot"),
            read("dog", source="sensor"),
            read("dog", confidence=.2),
            read("dog", t=98.),
            read("dog", t=102.),
        ]
        for fixture in cases:
            with self.subTest(fixture=fixture):
                _, p = self.choose(determination=1., frame=fixture)
                self.assertEqual("idle", p.intention)
                self.assertFalse(p.executed)
                self.assertEqual(0, p.motor_commands_issued)

    def test_corrupt_goal_table_fails_closed_without_energy_bookkeeping(self):
        self.add_goal()
        self.memory.conn.execute("DROP TABLE mem1_mock_goals")
        self.memory.conn.commit()
        brain = AutonomyBrain(self.memory, Motivations(determination=1.))
        energy = brain.motives.energy
        p = brain.propose_balanced_passive(
            read("dog", "ball"), journal=self.journal, goals=self.goals,
            now_monotonic_s=100.1, now_wall_epoch_s=WALL+1)
        self.assertEqual(("idle", "det1_goal_memory_unavailable"),
                         (p.intention, p.reason))
        self.assertEqual(energy, brain.motives.energy)
        self.assertEqual(0, p.motor_commands_issued)

    def test_invalid_determination_and_foreign_store_are_refused(self):
        self.add_goal()
        for value in (float("nan"), float("inf"), -1., 1.1, True):
            with self.subTest(value=repr(value)):
                brain = AutonomyBrain(self.memory)
                brain.motives.determination = value
                p = brain.propose_balanced_passive(
                    read("dog", "ball"), journal=self.journal, goals=self.goals,
                    now_monotonic_s=100.1, now_wall_epoch_s=WALL+1)
                self.assertEqual(("idle", "invalid_motivations"),
                                 (p.intention, p.reason))
        foreign = ExperienceMemory(":memory:")
        self.addCleanup(foreign.close)
        other = MockGoalMemory(foreign, MockExperienceLedger(foreign))
        brain = AutonomyBrain(self.memory)
        with self.assertRaises(ValueError):
            brain.propose_balanced_passive(
                read("dog", "ball"), journal=self.journal, goals=other,
                now_monotonic_s=100.1, now_wall_epoch_s=WALL+1)
        with self.assertRaises(TypeError):
            brain.propose_balanced_passive(
                read("dog", "ball"), journal=self.journal, goals="bad",
                now_monotonic_s=100.1, now_wall_epoch_s=WALL+1)


if __name__ == "__main__":
    unittest.main()
