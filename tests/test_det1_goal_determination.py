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


    def _det2_link_initial_dog(self):
        self.add_goal()
        self.ledger.record_proposal(
            PassiveIntent("observe", "fictional_first", "object_label", "dog"),
            session=SESSION, sequence=1, proposed_at_epoch_s=WALL+.5)
        self.goals.link_attempt(
            goal_id=GOAL_DOG, session=SESSION, sequence=1,
            strategy="observe_from_distance", context="initial",
            at_epoch_s=WALL+.75)

    def _det2_brain(self, *, determination=1., curiosity=.75,
                    caution=.35, energy=.8, play=.6):
        return AutonomyBrain(self.memory, Motivations(
            determination=determination, curiosity=curiosity,
            caution=caution, energy=energy, play=play))

    def _det2_tick(self, brain, frame, *, wall=WALL+1, mono=100.1,
                   guarded=True, pacing=False):
        return brain.propose_balanced_passive(
            frame, journal=self.journal, goals=self.goals,
            guard_attempted_goals=guarded, personality_pacing=pacing,
            now_monotonic_s=mono, now_wall_epoch_s=wall)

    def test_det2_paired_attempted_goal_stops_automatic_repetition(self):
        self._det2_link_initial_dog()
        control=self._det2_brain()
        guarded=self._det2_brain()
        before=self.memory.conn.total_changes
        a=self._det2_tick(control, read("dog"), guarded=False)
        b=self._det2_tick(guarded, read("dog"), guarded=True)
        self.assertEqual(("observe","dog"),
                         (a.intention,a.target_category))
        self.assertEqual(("idle",None),
                         (b.intention,b.target_category))
        self.assertEqual(before,self.memory.conn.total_changes)
        self.assertEqual(0,b.motor_commands_issued)
        self.assertFalse(b.executed)
        self.assertFalse(b.request_pc_analysis)
        advice=self.goals.retry_attention(now_wall_epoch_s=WALL+1)
        self.assertEqual(frozenset({("observe","dog")}),advice.held)
        self.assertEqual((),advice.resume_once)
        self.assertFalse(advice.physical_effect_verified)
        self.assertFalse(advice.independent_new_view_verified)
        # A different, freshly eligible category must remain available.
        distinct=self._det2_tick(
            self._det2_brain(),read("dog","ball"),guarded=True)
        self.assertEqual(("observe","ball"),
                         (distinct.intention,distinct.target_category))

    def test_det2_suspended_goal_without_attempt_is_still_on_hold(self):
        self.add_goal(state="suspended")
        p=self._det2_tick(self._det2_brain(),read("dog"))
        self.assertEqual("idle",p.intention)
        self.assertEqual(frozenset({("observe","dog")}),
                         self.goals.retry_attention(
                             now_wall_epoch_s=WALL+1).held)

    def test_det2_explicit_mock_resume_one_proposal_then_hold_until_new_link(self):
        self._det2_link_initial_dog()
        self.goals.transition(
            goal_id=GOAL_DOG,expected_revision=2,next_state="suspended",
            reason="repeat_blocked",at_epoch_s=WALL+.8)
        self.assertEqual("idle",self._det2_tick(
            self._det2_brain(),read("dog")).intention)
        # This is a declared MOCK context transition, not proof of a new view.
        self.goals.transition(
            goal_id=GOAL_DOG,expected_revision=3,next_state="active",
            reason="new_view",at_epoch_s=WALL+.9)
        advice=self.goals.retry_attention(now_wall_epoch_s=WALL+1)
        self.assertEqual((),tuple(advice.held))
        self.assertEqual((("observe","dog",GOAL_DOG,4),),
                         advice.resume_once)
        brain=self._det2_brain()
        before=self.memory.conn.total_changes
        one=self._det2_tick(brain,read("dog"))
        self.assertEqual(("observe","det2_mock_resumed_strategy_unverified"),
                         (one.intention,one.reason))
        self.assertEqual(before,self.memory.conn.total_changes)
        later=self._det2_tick(
            brain,read("dog",t=104.,seq=2),wall=WALL+5,mono=104.1)
        self.assertEqual("idle",later.intention)
        # The other MEM-1 strategy is recorded EXPLICITLY, never by F2.
        self.ledger.record_proposal(
            PassiveIntent("observe","fictional_new_strategy",
                          "object_label","dog"),
            session=SESSION,sequence=2,proposed_at_epoch_s=WALL+5.5)
        self.goals.link_attempt(
            goal_id=GOAL_DOG,session=SESSION,sequence=2,
            strategy="observe_over_time",context="new_view",
            at_epoch_s=WALL+5.75)
        self.goals.transition(
            goal_id=GOAL_DOG,expected_revision=4,next_state="suspended",
            reason="repeat_blocked",at_epoch_s=WALL+6)
        self.goals.transition(
            goal_id=GOAL_DOG,expected_revision=5,next_state="active",
            reason="new_view",at_epoch_s=WALL+7)
        self.assertEqual(frozenset({("observe","dog")}),
                         self.goals.retry_attention(
                             now_wall_epoch_s=WALL+8).held)
        third=self._det2_tick(
            self._det2_brain(),read("dog",t=108.,seq=3),
            wall=WALL+8,mono=108.1)
        self.assertEqual("idle",third.intention)

    def test_det2_retracted_link_cannot_erase_attempt_or_restore_goal_focus(self):
        self._det2_link_initial_dog()
        self.ledger.retract(
            session=SESSION,sequence=1,reason="source_retracted")
        brain=self._det2_brain()
        guarded=self._det2_tick(brain,read("dog"))
        self.assertEqual("idle",guarded.intention)
        self.assertEqual("unavailable",self.goals.attempts(
            GOAL_DOG)[0].mock_resolution)
        # Withdrawing the goal removes its influence rather than reactivating it.
        self.goals.retract(goal_id=GOAL_DOG,reason="source_retracted")
        self.assertEqual(frozenset(),self.goals.retry_attention(
            now_wall_epoch_s=WALL+1).held)
        new_brain=self._det2_brain()
        p=self._det2_tick(new_brain,read("dog"))
        self.assertEqual(("observe","novel_mock_category"),
                         (p.intention,p.reason))
        self.assertEqual(0,self.memory.experience_count())

    def test_det2_corrupt_or_future_goal_fails_closed_not_motor(self):
        self._det2_link_initial_dog()
        brain=self._det2_brain()
        energy=brain.motives.energy
        self.memory.conn.execute("DROP TABLE mem1_mock_goal_links")
        self.memory.conn.commit()
        p=self._det2_tick(brain,read("dog"))
        self.assertEqual(("idle","det2_goal_history_unavailable"),
                         (p.intention,p.reason))
        self.assertEqual(energy,brain.motives.energy)
        self.assertFalse(p.executed)
        self.assertEqual(0,p.motor_commands_issued)

    def test_det2_bad_flags_and_stale_or_untrusted_reads_fail_closed(self):
        self.add_goal()
        for flags in ({"guard_attempted_goals":1},
                      {"guard_attempted_goals":True,
                       "personality_pacing":"yes"}):
            with self.assertRaises(TypeError):
                AutonomyBrain(self.memory).propose_balanced_passive(
                    read("dog"),journal=self.journal,goals=self.goals,
                    now_monotonic_s=100.1,now_wall_epoch_s=WALL+1,**flags)
        with self.assertRaises(ValueError):
            AutonomyBrain(self.memory).propose_balanced_passive(
                read("dog"),journal=self.journal,
                guard_attempted_goals=True,
                now_monotonic_s=100.1,now_wall_epoch_s=WALL+1)
        for frame in (read("dog",source="sensor"),
                      read("dog",environment="robot"),
                      read("dog",status="unavailable_or_invalid"),
                      read("dog",t=98.),read("dog",t=102.)):
            with self.subTest(frame=frame):
                brain=self._det2_brain()
                prior=brain.motives.energy
                p=self._det2_tick(brain,frame)
                self.assertEqual("idle",p.intention)
                self.assertEqual(prior,brain.motives.energy)

    def test_per1_engagement_cost_paired_off_on_and_strong_motivation(self):
        def brain(curiosity=.6, play=.6,caution=.4):
            return self._det2_brain(
                determination=0.,curiosity=curiosity,play=play,
                caution=caution,energy=.8)
        plain,low_cost=brain(),brain()
        empty=read(t=100.,seq=1)
        self.assertEqual("idle",self._det2_tick(
            plain,empty,guarded=False,pacing=False).intention)
        self.assertEqual("idle",self._det2_tick(
            low_cost,empty,guarded=False,pacing=True).intention)
        before=self.memory.conn.total_changes
        next_frame=read("ball",t=101.,seq=2)
        control=self._det2_tick(
            plain,next_frame,wall=WALL+2,mono=101.1,
            guarded=False,pacing=False)
        paced=self._det2_tick(
            low_cost,next_frame,wall=WALL+2,mono=101.1,
            guarded=False,pacing=True)
        self.assertEqual(("observe","ball"),
                         (control.intention,control.target_category))
        self.assertEqual(("idle",None),
                         (paced.intention,paced.target_category))
        self.assertEqual(before,self.memory.conn.total_changes)
        # Reuse existing PD2: post-F2 affect cannot select another action.
        from microduck_companion.behavior_continuity import MockBehaviorSituation
        portrait=low_cost.describe_behavior(
            paced,journal=self.journal,now_wall_epoch_s=WALL+2)
        disposition=low_cost.describe_behavior_continuity(
            portrait,situation=MockBehaviorSituation(),
            now_monotonic_s=101.1)
        self.assertEqual(("Chill","Chill"),
                         (portrait.state,disposition.state))
        self.assertFalse(disposition.physical_execution_authorized)
        self.assertEqual(0,disposition.motor_commands_issued)
        strong=brain(curiosity=1.,play=1.,caution=.05)
        self._det2_tick(strong,empty,guarded=False,pacing=True)
        strong_choice=self._det2_tick(
            strong,next_frame,wall=WALL+2,mono=101.1,
            guarded=False,pacing=True)
        self.assertEqual("observe",strong_choice.intention)

    def test_per1_rest_and_source_safety_preempt_any_engagement(self):
        for flag in (False,True):
            brain=self._det2_brain(energy=.15)
            prior=self.memory.conn.total_changes
            p=self._det2_tick(
                brain,read("ball"),guarded=False,pacing=flag)
            self.assertEqual("rest",p.intention)
            self.assertEqual(0,p.motor_commands_issued)
            self.assertEqual(prior,self.memory.conn.total_changes)
            bad=self._det2_tick(
                brain,read("ball",source="sensor",t=101.,seq=2),
                wall=WALL+2,mono=101.1,guarded=False,pacing=flag)
            self.assertEqual("idle",bad.intention)
            self.assertFalse(bad.executed)



if __name__ == "__main__":
    unittest.main()
