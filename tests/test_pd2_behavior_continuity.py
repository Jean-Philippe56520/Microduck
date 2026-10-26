"""PD2: simulated continuity over the 16 OEM historical behavior labels.

All scenes/conditions are scripted. None is a physical motor/sound receipt,
person/animal recognition, safe-floor verdict or real-world emotional state.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain, Motivations
from microduck_companion.behavior_continuity import (
    MIN_MOCK_EXPRESSION_DWELL_S, MAX_FIXTURE_CUE_AGE_S,
    REENTRY_COOLDOWN_S, MockBehaviorContinuity,
    MockBehaviorSituation, MockBehaviorDisposition,
)
from microduck_companion.behavior_personality import (
    HISTORICAL_OEM_STATES, expression_capability_for,
)
from microduck_companion.behavioral_memory import BehavioralMemory
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.mock_cycle_demo import mock_snapshot
from microduck_companion.mock_cycles import MockConsequence, MockCycleRunner
from microduck_companion.mock_social_cues import MockSocialContext, MockSocialPlan
from microduck_companion.oem_expression_hints import (
    MockOemConditions, MockOemCue,
)
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_memory import PassiveObservationJournal

NOW = 100.0
WALL = 1_780_000_000.0


def source_cue(cue, at=NOW-.1, *, conditions=None):
    return MockBehaviorSituation(
        cue, at, MockOemConditions() if conditions is None else conditions,
    )


def optin():
    return MockSocialContext(
        operator_opt_in=True, supervised=True, privacy_reviewed=True,
        quiet_mode=False, brief_audio_opt_in=True,
    )


class PD2ContinuityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "one-experience-memory.sqlite3"
        self.mem = ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.journal = PassiveObservationJournal(self.mem)
        self.brain = AutonomyBrain(self.mem)

    def portrait(self, name="Chill", *, behavioral=None):
        selected = {
            "Chill": PassiveIntent("idle", "no_current_observation"),
            "LookAround": PassiveIntent(
                "observe", "novel_mock_category", "object_label", "ball"),
            "Nap": PassiveIntent("rest", "simulated_energy_recovery_hysteresis"),
            "BallPlay": MockSocialPlan(
                "play_cue", "fictional_invitation", "ball", 300),
            "SociableChill": MockSocialPlan(
                "chirp", "fictional_social_note", "bark", 180),
        }[name]
        return self.brain.describe_behavior(
            selected, journal=self.journal,
            now_wall_epoch_s=WALL, behavioral=behavioral,
        )

    def describe(self, name="Chill", cue="none", *, at=NOW, memory=False,
                 condition=None, portrait=None, hint=None):
        p = self.portrait(name) if portrait is None else portrait
        s = (MockBehaviorSituation(conditions=condition or MockOemConditions())
             if cue == "none"
             else source_cue(cue, at-.1, conditions=condition))
        if memory:
            return self.brain.describe_behavior_continuity(
                p, situation=s, now_monotonic_s=at, hint=hint,
                hint_evaluated_monotonic_s=NOW if hint is not None else None)
        return MockBehaviorContinuity().describe(
            p, motivations=self.brain.motives,
            situation=s, now_monotonic_s=at, hint=hint,
            hint_evaluated_monotonic_s=NOW if hint is not None else None)

    def hint(self, portrait, name="petting_start", *, condition=None):
        return self.brain.describe_oem_expression(
            portrait,
            cue=MockOemCue(name, NOW-.1),
            context=optin(), conditions=condition or MockOemConditions(),
            now_monotonic_s=NOW,
        )

    def test_catalogue_covers_all_16_as_fictional_descriptions(self):
        names = set()
        for base in ("Chill","LookAround","Nap","BallPlay"):
            names.add(self.describe(base).state)
        self.brain.motives.play = .94
        self.brain.motives.energy = .9
        self.brain.motives.caution = .2
        for cue, base in (
            ("new_space","LookAround"),
            ("viewpoint_ambiguity","LookAround"),
            ("play_burst","BallPlay"),
            ("social_settle","SociableChill"),
            ("quiet_grooming","Chill"),
            ("sneeze_like","Chill"),
            ("rhythm_pattern","BallPlay"),
            ("floor_object","LookAround"),
            ("held_like","Chill"),
        ):
            with self.subTest(cue=cue):
                r=self.describe(base,cue)
                self.assertEqual("contextual_mock_candidate",r.reason)
                names.add(r.state)
        continuity=MockBehaviorContinuity()
        continuity.describe(self.portrait("Nap"),
            motivations=self.brain.motives,
            situation=MockBehaviorSituation(),now_monotonic_s=90.)
        stretch=continuity.describe(self.portrait("Chill"),
            motivations=self.brain.motives,
            situation=source_cue("after_rest",NOW-.1),
            now_monotonic_s=NOW)
        self.assertEqual("Stretch",stretch.state)
        names.add(stretch.state)
        idle=self.portrait("Chill")
        for event,expected in (("petting_start","Petted"),
                               ("ambient_noise","Startle")):
            with self.subTest(event=event):
                h=self.hint(idle,event)
                result=self.describe(
                    portrait=idle,hint=h)
                self.assertEqual(expected,result.state)
                names.add(result.state)
        self.assertEqual(set(HISTORICAL_OEM_STATES),names)

    def test_pd2_never_dispatches_any_16_state_or_qwen(self):
        self.brain.motives.play=.95
        for c in (
            "new_space","viewpoint_ambiguity","play_burst",
            "rhythm_pattern","floor_object","quiet_grooming","held_like"):
            base = ("BallPlay" if c in {"play_burst","rhythm_pattern"} else
                    "LookAround" if c in {"new_space","viewpoint_ambiguity",
                                         "floor_object"} else "Chill")
            r=self.describe(base,c)
            self.assertIn(r.state,HISTORICAL_OEM_STATES)
            self.assertFalse(r.executed)
            self.assertFalse(r.hardware_verified)
            self.assertFalse(r.physical_execution_authorized)
            self.assertEqual((0,0,0,0),(
                r.motor_commands_issued,r.speaker_commands_issued,
                r.pc_requests_issued,r.memories_written))
            cap=expression_capability_for(r.state)
            self.assertEqual(cap.oem_expression_evidence,
                             r.oem_expression_evidence)
            self.assertEqual(cap.companion_status,r.companion_status)

    def test_all_ten_synthetic_contexts_require_explicit_cue(self):
        for c in ("new_space","viewpoint_ambiguity","play_burst",
                  "after_rest","social_settle","quiet_grooming",
                  "sneeze_like","rhythm_pattern","floor_object","held_like"):
            with self.subTest(cue=c):
                self.assertEqual("base_portrait",
                    self.describe("Chill").reason)
                with self.assertRaises(ValueError):
                    MockBehaviorSituation(c)
        self.assertEqual("Chill",self.describe("Chill").state)

    def test_strict_mock_source_invalid_type_and_time_are_rejected(self):
        invalid=(
            {"cue":"move_to_target","observed_monotonic_s":NOW},
            {"cue":"new_space","observed_monotonic_s":None},
            {"cue":"new_space","observed_monotonic_s":True},
            {"cue":"new_space","observed_monotonic_s":float("nan")},
            {"cue":"new_space","observed_monotonic_s":-1.},
            {"cue":"none","observed_monotonic_s":NOW},
            {"cue":"new_space","observed_monotonic_s":NOW,
             "source":"robotd"},
            {"cue":"new_space","observed_monotonic_s":NOW,
             "conditions":"safe"},
        )
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs),self.assertRaises((ValueError,TypeError)):
                MockBehaviorSituation(**kwargs)
        for x in (True, -1, float("nan"), "now"):
            with self.subTest(time=x),self.assertRaises(ValueError):
                self.describe("Chill",at=x)
        with self.assertRaises(TypeError):
            self.brain.describe_behavior_continuity(
                "Chill",situation=MockBehaviorSituation(),now_monotonic_s=NOW)
        with self.assertRaises(TypeError):
            self.brain.describe_behavior_continuity(
                self.portrait(),situation={},now_monotonic_s=NOW)

    def test_stale_future_and_boundary_are_conservative(self):
        p=self.portrait("LookAround")
        for t in (NOW-MAX_FIXTURE_CUE_AGE_S-.001,NOW+.001):
            with self.subTest(timestamp=t):
                c=MockBehaviorSituation("new_space",t)
                out=MockBehaviorContinuity().describe(
                    p,motivations=self.brain.motives,
                    situation=c,now_monotonic_s=NOW)
                self.assertEqual(("LookAround","stale_or_future_mock_cue"),
                                 (out.state,out.reason))
        c=MockBehaviorSituation("new_space",NOW-MAX_FIXTURE_CUE_AGE_S)
        out=MockBehaviorContinuity().describe(
            p,motivations=self.brain.motives,
            situation=c,now_monotonic_s=NOW)
        self.assertEqual("Wander",out.state)

    def test_high_caution_or_low_energy_blocks_mobile_labels(self):
        for candidate in ("new_space","viewpoint_ambiguity","floor_object",
                          "play_burst","rhythm_pattern"):
            base="BallPlay" if candidate in {"play_burst","rhythm_pattern"} else "LookAround"
            self.brain.motives.caution=.95
            out=self.describe(base,candidate)
            self.assertEqual(self.portrait(base).state,out.state)
            self.assertEqual("ineligible_mock_context",out.reason)
        self.brain.motives.caution=.10
        self.brain.motives.energy=.1
        self.brain.motives.play=.95
        for candidate in ("new_space","play_burst","rhythm_pattern"):
            base="BallPlay" if candidate in {"play_burst","rhythm_pattern"} else "LookAround"
            self.assertEqual(self.portrait(base).state,
                             self.describe(base,candidate).state)

    def test_no_fake_groundpick_or_wander_when_idle(self):
        for c in ("new_space","viewpoint_ambiguity","floor_object"):
            result=self.describe("Chill",c)
            self.assertEqual(("Chill","ineligible_mock_context"),
                             (result.state,result.reason))
        self.brain.motives.caution=.2
        self.assertEqual("GroundPick",self.describe("LookAround",
                                                   "floor_object").state)
        self.assertFalse(self.describe("LookAround","floor_object").executed)

    def test_no_zoomies_without_actual_fictional_play_proposal(self):
        self.brain.motives.play=.95
        self.brain.motives.energy=.95
        self.brain.motives.caution=.1
        for c in ("play_burst","rhythm_pattern"):
            self.assertEqual("Chill",self.describe("Chill",c).state)
        self.assertEqual("Zoomies",self.describe("BallPlay","play_burst").state)
        self.assertEqual("Dance",self.describe("BallPlay","rhythm_pattern").state)

    def test_stretch_only_after_proposed_rest(self):
        p=self.portrait("Chill")
        self.assertEqual("Chill",self.describe(
            portrait=p,cue="after_rest").state)
        self.assertEqual("Nap",self.describe("Nap").state)
        first=self.describe("Nap",memory=True,at=95.)
        self.assertEqual("Nap",first.state)
        later=self.describe("Chill","after_rest",memory=True,at=NOW)
        self.assertEqual(("Stretch","contextual_mock_candidate"),
                         (later.state,later.reason))

    def test_safety_preempts_even_duplicate_tick(self):
        first=self.describe("LookAround","new_space",memory=True)
        self.assertEqual("Wander",first.state)
        stop=self.describe("LookAround","new_space",memory=True,
            condition=MockOemConditions(stop_requested=True))
        self.assertEqual(("Chill","safety_or_stop"),(stop.state,stop.reason))
        self.assertFalse(stop.physical_execution_authorized)
        self.assertEqual(0,stop.motor_commands_issued)

    def test_busy_fallen_stop_flags_preempt_animated_labels(self):
        for flags in ({"busy":True},{"fallen":True},{"stop_requested":True}):
            with self.subTest(flags=flags):
                result=self.describe("BallPlay","play_burst",
                    condition=MockOemConditions(**flags))
                self.assertEqual(("Chill","safety_or_stop"),
                                 (result.state,result.reason))

    def test_rest_preempts_even_petting_start(self):
        rest=self.portrait("Nap")
        hint=self.hint(rest,"petting_start")
        result=self.describe(portrait=rest,hint=hint)
        self.assertEqual(("Nap","rest_preempts_expression"),
                         (result.state,result.reason))

    def test_hold_short_term_then_return_to_base_and_cooldown(self):
        r1=self.describe("LookAround","new_space",memory=True,at=100.)
        self.assertEqual("Wander",r1.state)
        r2=self.describe("LookAround",memory=True,at=101.)
        self.assertEqual(("Wander","minimum_dwell"),(r2.state,r2.reason))
        r3=self.describe("LookAround",memory=True,at=103.)
        self.assertEqual(("LookAround","base_portrait"),(r3.state,r3.reason))
        r4=self.describe("LookAround","new_space",memory=True,at=106.)
        self.assertEqual(("LookAround","reentry_cooldown"),(r4.state,r4.reason))
        r5=self.describe("LookAround","new_space",memory=True,at=112.)
        self.assertEqual("Wander",r5.state)
        self.assertEqual(8.,REENTRY_COOLDOWN_S)
        self.assertEqual(2.,MIN_MOCK_EXPRESSION_DWELL_S)

    def test_ineligible_context_never_keeps_risky_mock_label(self):
        self.brain.motives.caution=.1
        self.assertEqual("Wander",
            self.describe("LookAround","new_space",memory=True,at=100.).state)
        self.brain.motives.caution=.98
        denied=self.describe("LookAround","new_space",memory=True,at=100.5)
        self.assertEqual(("LookAround","ineligible_mock_context"),
                         (denied.state,denied.reason))

    def test_new_base_choice_overrides_dwell(self):
        self.assertEqual("Wander",self.describe(
            "LookAround","new_space",memory=True,at=100.).state)
        rest=self.describe("Nap",memory=True,at=100.2)
        self.assertEqual("Nap",rest.state)
        self.assertEqual("rest_preempts_expression",rest.reason)

    def test_clock_rollback_quiets_and_duplicate_does_not_switch(self):
        self.assertEqual("Wander",self.describe(
            "LookAround","new_space",memory=True,at=100.).state)
        same=self.describe("LookAround",memory=True,at=100.)
        self.assertEqual(("Wander","duplicate_cycle"),
                         (same.state,same.reason))
        rollback=self.describe("LookAround","new_space",
                               memory=True,at=99.)
        self.assertEqual(("Chill","clock_reset"),
                         (rollback.state,rollback.reason))
        restart=self.describe("LookAround","new_space",
                              memory=True,at=102.)
        self.assertIn(restart.state,("Chill","Wander","LookAround"))
        self.assertFalse(restart.executed)

    def test_petting_vs_startle_existing_pc_hints_not_extra_output(self):
        base=self.portrait()
        for cue_name, expected in (("petting_start","Petted"),
                                   ("ambient_noise","Startle")):
            h=self.hint(base,cue_name)
            got=self.describe(portrait=base,hint=h)
            self.assertEqual(expected,got.state)
            self.assertEqual(0,got.speaker_commands_issued)
            self.assertEqual(0,got.motor_commands_issued)
            self.assertEqual(0,got.pc_requests_issued)
            if expected=="Startle":
                self.assertEqual("none",got.oem_expression_evidence)
        other=self.portrait("Nap")
        with self.assertRaises(ValueError):
            self.describe(portrait=other,hint=self.hint(base))

    def test_listening_only_cannot_suggest_wander_turn_or_groundpick(self):
        listening=self.brain.describe_behavior(
            PassiveIntent("listen","fictional_sound_category",
                          "sound_label","bark"),
            journal=self.journal,now_wall_epoch_s=WALL)
        self.assertEqual(("LookAround","attentive"),
                         (listening.state,listening.affect))
        for signal in ("new_space","viewpoint_ambiguity","floor_object"):
            with self.subTest(signal=signal):
                out=self.describe(portrait=listening,cue=signal)
                self.assertEqual(("LookAround","ineligible_mock_context"),
                                 (out.state,out.reason))

    def test_pc_hint_fails_closed_when_missing_future_or_stale(self):
        base=self.portrait("Chill")
        hint=self.hint(base,"petting_start")
        continuity=MockBehaviorContinuity()
        for stamp,now in (
            (None,NOW),(NOW,NOW+MAX_FIXTURE_CUE_AGE_S+.01),
            (NOW,NOW-.01),
        ):
            with self.subTest(stamp=stamp,now=now):
                if stamp is None:
                    with self.assertRaises(ValueError):
                        continuity.describe(base,
                            motivations=self.brain.motives,
                            situation=MockBehaviorSituation(),
                            now_monotonic_s=now,hint=hint)
                else:
                    new=MockBehaviorContinuity().describe(base,
                        motivations=self.brain.motives,
                        situation=MockBehaviorSituation(),
                        now_monotonic_s=now,hint=hint,
                        hint_evaluated_monotonic_s=stamp)
                    self.assertEqual(("Chill","stale_or_future_mock_cue"),
                                     (new.state,new.reason))
                    self.assertEqual(0,new.speaker_commands_issued)
        with self.assertRaises(ValueError):
            continuity.describe(base,motivations=self.brain.motives,
                situation=MockBehaviorSituation(),
                now_monotonic_s=NOW,hint_evaluated_monotonic_s=NOW)

    def test_history_discourages_inspection_and_retraction_restores_candidate(self):
        runner=MockCycleRunner(self.mem,session="pd2-synthetic")
        behavioral=BehavioralMemory(self.mem)
        seqs=[]
        for i,t in enumerate((100.,103.)):
            target="synthetic-target-"+str(i)
            outcome=runner.step(mock_snapshot(t,target=target),now=t+.5,
                followup=mock_snapshot(t+.4,target=target),
                consequence=MockConsequence(target,"negative",t+.3))
            seqs.append(outcome.sequence)
            self.assertTrue(behavioral.record(
                runner=runner,sequence=outcome.sequence,
                now_wall_epoch_s=WALL))
        reserved=self.portrait("LookAround",behavioral=behavioral)
        self.assertEqual("inspection_reserved",reserved.inspection_habit)
        before=self.mem.conn.total_changes
        denied=self.describe(portrait=reserved,cue="new_space")
        self.assertEqual(("LookAround","history_discourages_inspection"),
                         (denied.state,denied.reason))
        self.assertEqual(before,self.mem.conn.total_changes)
        older=behavioral.history(now_wall_epoch_s=WALL)
        self.assertEqual(2,len(older))
        self.assertTrue(behavioral.retract(older[0].mock_cycle_id,
                                          reason="fixture_annotation_error"))
        fresh=self.portrait("LookAround",behavioral=behavioral)
        self.assertEqual("neutral",fresh.inspection_habit)
        accepted=self.describe(portrait=fresh,cue="new_space")
        self.assertEqual("Wander",accepted.state)
        self.assertFalse(accepted.executed)

    def test_disposition_rejects_forged_execution_or_qwen(self):
        base=self.describe("Chill")
        for change in (
            {"executed":True},{"hardware_verified":True},
            {"physical_execution_authorized":True},
            {"motor_commands_issued":1},
            {"speaker_commands_issued":1},{"pc_requests_issued":1},
            {"memories_written":1},
            {"oem_expression_evidence":"verified_movement"},
            {"companion_status":"confirmed_on_robot"},
            {"source":"robotd"},
            {"motor_commands_issued":False},
        ):
            with self.subTest(change=change),self.assertRaises(ValueError):
                replace(base,**change)

    def test_repeat_calls_do_not_modify_existing_sqlite_or_motives(self):
        portrait=self.portrait("LookAround")
        before=self.mem.conn.total_changes
        motivations=vars(self.brain.motives).copy()
        tables_before=self.mem.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for i in range(50):
            self.brain.describe_behavior_continuity(
                portrait, situation=source_cue("new_space",100.+i-.1),
                now_monotonic_s=100.+i)
        self.assertEqual(before,self.mem.conn.total_changes)
        self.assertEqual(motivations,vars(self.brain.motives))
        tables_after=self.mem.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        self.assertEqual(tables_before,tables_after)
        self.assertEqual(0,self.mem.experience_count())

    def test_restart_resets_ephemeral_disposition_but_not_f4_history(self):
        self.assertEqual("Wander",self.describe(
            "LookAround","new_space",memory=True,at=NOW).state)
        self.mem.close()
        resumed=ExperienceMemory(self.path)
        try:
            brain=AutonomyBrain(resumed)
            journal=PassiveObservationJournal(resumed)
            p=brain.describe_behavior(
                PassiveIntent("idle","no_current_observation"),
                journal=journal,now_wall_epoch_s=WALL)
            row=brain.describe_behavior_continuity(
                p,situation=MockBehaviorSituation(),
                now_monotonic_s=NOW+.1)
            self.assertEqual("Chill",row.state)
            self.assertEqual("base_portrait",row.reason)
            self.assertEqual(0,row.memories_written)
        finally:
            resumed.close()


if __name__ == "__main__":
    unittest.main()
