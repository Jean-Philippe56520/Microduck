"""PD3: MOCK-only information need, no request without useful evidence.

The F5-A advisory MUST already have been produced by the one existing F2
brain. No test calls a live model, worker, socket, motors or media service.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.behavior_continuity import MockBehaviorSituation
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.mock_social_cues import MockSocialPlan
from microduck_companion.oem_expression_hints import MockOemConditions
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot
from microduck_companion.pc_hypothesis_contract import (
    OptionalPCAdvisory, PCObservation, start_optional_pc_cycle,
)
from microduck_companion.selective_pc_policy import SelectivePCPolicy
from microduck_companion.semantic_pc_opportunity import (
    MAX_MOCK_FRAME_AGE_S, MAX_MOCK_SAMPLE_GAP_S,
    MIN_MOCK_SAMPLE_GAP_S, MockPCOpportunity,
    assess_mock_pc_opportunity,
)

NOW=100.
WALL=1_780_000_000.


def reading(mode="unknown", *, at=NOW, seq=2, track="fiction-track",
            source="mock", channel="mock_fixture_unix", status="ok",
            environment="mock"):
    if mode=="conflict":
        entries=[("object_label","cat",.95),("object_label","dog",.94)]
    elif mode=="unknown_person":
        entries=[("object_label","unknown",.95),
                 ("object_label","person",.98)]
    elif mode=="unknown_sound":
        entries=[("object_label","unknown",.95),("sound_label","speech",.98)]
    else:
        entries=[("object_label",mode,.95)]
    events=tuple(PerceptionEvent(
        kind,value,source,at,1.,confidence,
        track_id=track if kind=="object_label" else None,
    ) for kind,value,confidence in entries)
    return PassiveRead(status,PerceptionSnapshot(environment,events,at),
                       seq,channel)


class PD3Tests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path=Path(temp.name)/"existing.sqlite3"
        self.mem=ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.journal=PassiveObservationJournal(self.mem)
        self.brain=AutonomyBrain(self.mem)

    def prepared(self, *, previous=None, current=None, cue="none",
                 now=NOW+.1, optin=False, portrait=None, disposition=None,
                 situation=None, advisory=None):
        old=previous if previous is not None else reading(at=NOW-1,seq=1)
        new=current if current is not None else reading()
        if advisory is None:
            # The *single* actual local F2 decision is taken by F5-A.
            advisory=start_optional_pc_cycle(
                self.brain,new,journal=self.journal,
                now_monotonic_s=new.snapshot.observed_at+.1,
                now_wall_epoch_s=WALL)
        if portrait is None:
            portrait=self.brain.describe_behavior(
                advisory.local_intent,journal=self.journal,
                now_wall_epoch_s=WALL)
        if situation is None:
            situation=(MockBehaviorSituation() if cue=="none"
                else MockBehaviorSituation(cue,new.snapshot.observed_at))
        if disposition is None:
            disposition=self.brain.describe_behavior_continuity(
                portrait,situation=situation,
                now_monotonic_s=new.snapshot.observed_at+.1)
        result=assess_mock_pc_opportunity(
            advisory,portrait=portrait,disposition=disposition,
            previous_read=old,current_read=new,
            situation=situation,motivations=self.brain.motives,
            now_monotonic_s=now,pc_opt_in=optin,
        )
        return result,advisory,portrait,disposition,situation

    def test_persistent_unknown_produces_interesting_but_unsendable_candidate(self):
        out,adv,portrait,disp,ctx=self.prepared(optin=True)
        self.assertEqual("inspect",adv.local_intent.intention)
        self.assertEqual("pending_transport",adv.status)
        self.assertEqual("LookAround",portrait.state)
        self.assertEqual(("LookAround","base_portrait"),(disp.state,disp.reason))
        self.assertTrue(out.interesting)
        self.assertEqual("f5_has_no_discriminating_input",out.reason)
        self.assertEqual("unknown",out.trigger)
        self.assertEqual(2,out.fixture_samples)
        self.assertEqual("mock_pd3_semantic_opportunity_only",out.source)
        self.assertFalse(out.eligible_for_transport)
        self.assertFalse(out.request_transmitted)
        self.assertFalse(out.real_scene_verified)
        self.assertEqual((0,0,0,0),(
            out.motor_commands_issued,out.speaker_commands_issued,
            out.pc_requests_issued,out.memories_written))
        self.assertFalse(adv.local_intent.executed)
        self.assertEqual(0,adv.motor_commands_issued)

    def test_default_without_optin_is_local_only(self):
        out,_,_,_,_=self.prepared()
        self.assertTrue(out.interesting)
        self.assertEqual("pc_opt_in_missing",out.reason)
        self.assertFalse(out.eligible_for_transport)
        self.assertEqual(0,out.pc_requests_issued)

    def test_repeated_conflict_is_descriptive_not_a_fact(self):
        out,adv,_,_,_=self.prepared(
            previous=reading("conflict",at=NOW-1,seq=1),
            current=reading("conflict"),optin=True)
        self.assertTrue(out.interesting)
        self.assertEqual("conflict",out.trigger)
        self.assertEqual("conflict",adv.request.observations[0].status)
        self.assertEqual("f5_has_no_discriminating_input",out.reason)
        self.assertFalse(out.real_scene_verified)

    def test_lookaround_unfamiliar_scene_may_be_candidate_without_motor(self):
        for cue,state in (("viewpoint_ambiguity","TurnInPlace"),
                          ("new_space","Wander")):
            with self.subTest(cue=cue):
                # Fresh F2-A/F5-A cycle per scenario, without duplicate F2 ticks.
                mem=ExperienceMemory()
                try:
                    brain=AutonomyBrain(mem)
                    journal=PassiveObservationJournal(mem)
                    new=reading()
                    adv=start_optional_pc_cycle(
                        brain,new,journal=journal,
                        now_monotonic_s=NOW+.1,now_wall_epoch_s=WALL)
                    p=brain.describe_behavior(
                        adv.local_intent,journal=journal,
                        now_wall_epoch_s=WALL)
                    situation=MockBehaviorSituation(cue,NOW)
                    disp=brain.describe_behavior_continuity(
                        p,situation=situation,now_monotonic_s=NOW+.1)
                    self.assertEqual(state,disp.state)
                    out=assess_mock_pc_opportunity(
                        adv,portrait=p,disposition=disp,
                        previous_read=reading(at=NOW-1,seq=1),
                        current_read=new,situation=situation,
                        motivations=brain.motives,
                        now_monotonic_s=NOW+.1,pc_opt_in=True)
                    self.assertTrue(out.interesting)
                    self.assertEqual(state,out.behavior_state)
                    self.assertFalse(out.eligible_for_transport)
                finally:
                    mem.close()

    def test_no_automatic_pc_from_ballplay_or_groundpick_label(self):
        base,adv,p,_,_=self.prepared()
        self.assertTrue(base.interesting)
        # BallPlay is a social/play description; F5-A asks only on inspect.
        play=self.brain.describe_behavior(
            MockSocialPlan("play_cue","fictional_play","ball",300),
            journal=self.journal,now_wall_epoch_s=WALL)
        ctx=MockBehaviorSituation()
        play_desc=self.brain.describe_behavior_continuity(
            play,situation=ctx,now_monotonic_s=NOW+2)
        denied=assess_mock_pc_opportunity(
            adv,portrait=play,disposition=play_desc,
            previous_read=reading(at=NOW-1,seq=1),
            current_read=reading(),situation=ctx,
            motivations=self.brain.motives,now_monotonic_s=NOW+.1,
            pc_opt_in=True)
        self.assertEqual(("no_semantic_behavior",False),
                         (denied.reason,denied.interesting))
        # GroundPick cannot derive from an unknown object's P-A familiarity
        # under the existing PD2 contract, and never gains motor authority.
        self.assertNotEqual("GroundPick",p.state)
        self.assertEqual(0,denied.motor_commands_issued)

    def test_known_objects_or_one_uncertainty_do_not_trigger(self):
        current=reading("ball")
        out,adv,_,_,_=self.prepared(current=current,optin=True)
        self.assertEqual("not_needed",adv.status)
        self.assertEqual("no_f5_inspection_question",out.reason)
        # New F2 brain is required for a distinct fictional session.
        self.brain=AutonomyBrain(self.mem)
        # Previous known => no repetition even if current is unresolved.
        out,_,_,_,_=self.prepared(
            previous=reading("ball",at=NOW-1,seq=1),optin=True)
        self.assertEqual("invalid_or_private_mock_samples",out.reason)

    def test_private_person_sound_and_freeform_labels_are_rejected(self):
        for mode in ("unknown_person","unknown_sound","Malo"):
            with self.subTest(mode=mode):
                # Keep the current F5 advisory valid, inject suspect OLD
                # independent fixture to test the PD3 privacy boundary.
                old=reading(mode,at=NOW-1,seq=1)
                out,_,_,_,_=self.prepared(previous=old,optin=True)
                self.assertEqual("invalid_or_private_mock_samples",out.reason)
                self.assertEqual(0,out.pc_requests_issued)

    def test_person_or_voice_current_can_never_be_consulted(self):
        for mode in ("unknown_person","unknown_sound","Malo"):
            with self.subTest(mode=mode):
                one=reading(mode)
                out,adv,_,_,_=self.prepared(current=one,optin=True)
                self.assertFalse(out.interesting)
                self.assertNotEqual("f5_has_no_discriminating_input",out.reason)
                self.assertFalse(out.eligible_for_transport)
                self.assertEqual(0,out.pc_requests_issued)

    def test_same_or_out_of_order_sequence_fails_closed(self):
        for seq in (0,2,3):
            with self.subTest(seq=seq):
                old=reading(at=NOW-1,seq=seq)
                out,_,_,_,_=self.prepared(previous=old)
                self.assertEqual("invalid_or_private_mock_samples",out.reason)

    def test_not_repeat_same_track_or_same_uncertainty(self):
        older=reading(track="track-one",seq=1,at=NOW-1)
        new=reading(track="track-two")
        out,_,_,_,_=self.prepared(previous=older,current=new)
        self.assertEqual("not_repeated_mock_uncertainty",out.reason)
        old_conflict=reading("conflict",seq=1,at=NOW-1)
        out,_,_,_,_=self.prepared(previous=old_conflict)
        self.assertTrue(out.interesting)  # both unresolved but not necessarily identical

    def test_stale_future_and_untrusted_previous_read_denied(self):
        cases=[
            reading(at=NOW-MAX_MOCK_SAMPLE_GAP_S-1,seq=1),
            reading(at=NOW-MIN_MOCK_SAMPLE_GAP_S+.1,seq=1),
            reading(at=NOW-1,seq=1,channel="not-a-fixture"),
            reading(at=NOW-1,seq=1,source="sensor"),
            reading(at=NOW-1,seq=1,status="unavailable"),
        ]
        for old in cases:
            with self.subTest(old=old):
                out,_,_,_,_=self.prepared(previous=old)
                self.assertEqual("invalid_or_private_mock_samples",out.reason)

    def test_forged_state_and_stale_scene_cue_cannot_become_reason(self):
        out,adv,p,d,ctx=self.prepared(optin=True)
        self.assertTrue(out.interesting)
        # A name such as 'Wander' is never sufficient by itself.
        fake=replace(d,state="Wander",reason="contextual_mock_candidate",
                     oem_expression_evidence="none",
                     companion_status="requires_oem_m9_or_sensor_review")
        denied=assess_mock_pc_opportunity(
            adv,portrait=p,disposition=fake,
            previous_read=reading(at=NOW-1,seq=1),
            current_read=reading(),situation=ctx,
            motivations=self.brain.motives,
            now_monotonic_s=NOW+.1,pc_opt_in=True)
        self.assertEqual("no_semantic_behavior",denied.reason)
        fresh_ctx=MockBehaviorSituation("new_space",NOW)
        fake_valid=assess_mock_pc_opportunity(
            adv,portrait=p,disposition=fake,
            previous_read=reading(at=NOW-1,seq=1),
            current_read=reading(),situation=fresh_ctx,
            motivations=self.brain.motives,
            now_monotonic_s=NOW+.1,pc_opt_in=True)
        # Even a fabricated matching label only marks a fictional interest;
        # it grants no PC transport or real-world affordance.
        self.assertTrue(fake_valid.interesting)
        self.assertFalse(fake_valid.eligible_for_transport)
        stale_ctx=MockBehaviorSituation("new_space",NOW-2)
        stale=assess_mock_pc_opportunity(
            adv,portrait=p,disposition=fake,
            previous_read=reading(at=NOW-1,seq=1),
            current_read=reading(),situation=stale_ctx,
            motivations=self.brain.motives,
            now_monotonic_s=NOW+.1,pc_opt_in=True)
        self.assertEqual("invalid_or_private_mock_samples",stale.reason)

    def test_invalid_privacy_and_safety_context_preempt(self):
        candidates=(
            MockBehaviorSituation(
                conditions=MockOemConditions(stop_requested=True)),
            MockBehaviorSituation(
                conditions=MockOemConditions(fallen=True)),
            MockBehaviorSituation(
                conditions=MockOemConditions(busy=True)),
        )
        out,adv,p,d,_=self.prepared()
        self.assertTrue(out.interesting)
        for ctx in candidates:
            with self.subTest(ctx=ctx):
                denied=assess_mock_pc_opportunity(
                    adv,portrait=p,disposition=d,
                    previous_read=reading(at=NOW-1,seq=1),
                    current_read=reading(),situation=ctx,
                    motivations=self.brain.motives,
                    now_monotonic_s=NOW+.1,pc_opt_in=True)
                self.assertEqual(("unsafe_mock_context",False),
                    (denied.reason,denied.interesting))

    def test_low_curiosity_energy_and_high_caution_block(self):
        out,adv,p,d,ctx=self.prepared()
        self.assertTrue(out.interesting)
        for name,value in (("curiosity",.10),("energy",.1),("caution",.95)):
            original=getattr(self.brain.motives,name)
            try:
                setattr(self.brain.motives,name,value)
                denied=assess_mock_pc_opportunity(
                    adv,portrait=p,disposition=d,
                    previous_read=reading(at=NOW-1,seq=1),
                    current_read=reading(),situation=ctx,
                    motivations=self.brain.motives,
                    now_monotonic_s=NOW+.1,pc_opt_in=True)
                self.assertEqual("insufficient_mock_interest",denied.reason)
            finally:
                setattr(self.brain.motives,name,original)

    def test_retracted_inspection_habit_blocks_but_can_be_recomputed(self):
        out,adv,p,d,ctx=self.prepared()
        self.assertTrue(out.interesting)
        cautious=replace(p,inspection_habit="inspection_reserved")
        denied=assess_mock_pc_opportunity(
            adv,portrait=cautious,disposition=d,
            previous_read=reading(at=NOW-1,seq=1),
            current_read=reading(),situation=ctx,
            motivations=self.brain.motives,
            now_monotonic_s=NOW+.1,pc_opt_in=True)
        self.assertEqual("insufficient_mock_interest",denied.reason)
        restored=replace(p,inspection_habit="neutral")
        accepted=assess_mock_pc_opportunity(
            adv,portrait=restored,disposition=d,
            previous_read=reading(at=NOW-1,seq=1),
            current_read=reading(),situation=ctx,
            motivations=self.brain.motives,
            now_monotonic_s=NOW+.1,pc_opt_in=True)
        self.assertTrue(accepted.interesting)

    def test_expired_and_future_pc_request_cannot_leak(self):
        out,adv,p,d,ctx=self.prepared()
        self.assertTrue(out.interesting)
        for now in (NOW-.01,NOW+2.5):
            denied=assess_mock_pc_opportunity(
                adv,portrait=p,disposition=d,
                previous_read=reading(at=NOW-1,seq=1),
                current_read=reading(),situation=ctx,
                motivations=self.brain.motives,
                now_monotonic_s=now,pc_opt_in=True)
            self.assertEqual("expired_f5_request",denied.reason)

    def test_malformed_snapshot_and_current_frame_expiry_fail_closed(self):
        _,adv,p,d,ctx=self.prepared(optin=True)
        malformed=PassiveRead("ok",None,2,"mock_fixture_unix")
        for prev,curr,now in (
            (malformed,reading(),NOW+.1),
            (reading(seq=1,at=NOW-1),malformed,NOW+.1),
            (reading(seq=1,at=NOW-1),reading(),NOW+1.2),
            (reading(seq=1,at=NOW-1),reading(at=NOW+.4),NOW+.1),
        ):
            with self.subTest(now=now,previous=prev,current=curr):
                r=assess_mock_pc_opportunity(
                    adv,portrait=p,disposition=d,
                    previous_read=prev,current_read=curr,
                    situation=ctx,motivations=self.brain.motives,
                    now_monotonic_s=now,pc_opt_in=True)
                self.assertEqual("invalid_or_private_mock_samples",r.reason)
                self.assertFalse(r.eligible_for_transport)
                self.assertEqual(0,r.pc_requests_issued)

    def test_failed_and_fake_pc_reading_statuses_cannot_upgrade_scene(self):
        _,adv,p,d,ctx=self.prepared(optin=True)
        for value in (
            reading(status="unavailable"),
            reading(channel="fake_hardware"),
            reading(source="sensor"),
        ):
            with self.subTest(value=value):
                r=assess_mock_pc_opportunity(
                    adv,portrait=p,disposition=d,
                    previous_read=reading(seq=1,at=NOW-1),
                    current_read=value,situation=ctx,
                    motivations=self.brain.motives,
                    now_monotonic_s=NOW+.1,pc_opt_in=True)
                self.assertEqual("invalid_or_private_mock_samples",r.reason)

    def test_request_contents_must_match_current_fixture(self):
        out,adv,p,d,ctx=self.prepared()
        self.assertTrue(out.interesting)
        wrong_obs=PCObservation("object_label","unknown","conflict",.95)
        wrong=replace(adv,request=replace(
            adv.request,observations=(wrong_obs,)))
        denied=assess_mock_pc_opportunity(
            wrong,portrait=p,disposition=d,
            previous_read=reading(at=NOW-1,seq=1),
            current_read=reading(),situation=ctx,
            motivations=self.brain.motives,
            now_monotonic_s=NOW+.1,pc_opt_in=True)
        self.assertEqual("f5_request_mismatch",denied.reason)

    def test_invalid_types_and_forged_result_flags_rejected(self):
        out,adv,p,d,ctx=self.prepared()
        with self.assertRaises(TypeError):
            assess_mock_pc_opportunity(
                {},portrait=p,disposition=d,
                previous_read=reading(at=NOW-1,seq=1),
                current_read=reading(),situation=ctx,
                motivations=self.brain.motives,
                now_monotonic_s=NOW+.1)
        with self.assertRaises(ValueError):
            assess_mock_pc_opportunity(
                adv,portrait=p,disposition=d,
                previous_read=reading(at=NOW-1,seq=1),
                current_read=reading(),situation=ctx,
                motivations=self.brain.motives,
                now_monotonic_s=NOW+.1,pc_opt_in=1)
        for change in (
            {"eligible_for_transport":True},
            {"request_transmitted":True},
            {"real_scene_verified":True},
            {"pc_requests_issued":1},
            {"motor_commands_issued":1},
            {"speaker_commands_issued":1},
            {"memories_written":1},
            {"source":"robotd"},
            {"fixture_samples":8},
            {"trigger":"person"},
        ):
            with self.subTest(change=change),self.assertRaises(ValueError):
                replace(out,**change)

    def test_no_new_schema_writer_network_or_qwen_uses(self):
        policy=SelectivePCPolicy(self.mem)
        before=self.mem.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        writes=self.mem.conn.total_changes
        quotas=policy.counts()
        out,adv,p,d,ctx=self.prepared(optin=True)
        self.assertTrue(out.interesting)
        for _ in range(20):
            # Re-assess the same F5-A local decision; NEVER tick F2 again.
            out=assess_mock_pc_opportunity(
                adv,portrait=p,disposition=d,
                previous_read=reading(at=NOW-1,seq=1),
                current_read=reading(),situation=ctx,
                motivations=self.brain.motives,
                now_monotonic_s=NOW+.1,pc_opt_in=True)
            self.assertTrue(out.interesting)
            self.assertFalse(out.eligible_for_transport)
        after=self.mem.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        self.assertEqual(before,after)
        self.assertEqual(writes,self.mem.conn.total_changes)
        self.assertEqual(quotas,policy.counts())
        self.assertEqual(0,self.mem.experience_count())
        self.assertEqual(0,self.brain.passive_rhythm_metrics().count("rest"))

    def test_existing_quota_is_not_called_by_pd3(self):
        policy=SelectivePCPolicy(self.mem)
        out,adv,p,d,ctx=self.prepared(optin=True)
        self.assertEqual(0,out.pc_requests_issued)
        self.assertEqual({},policy.counts())
        self.assertEqual("pending_transport",adv.status)
        # PD3 returns no entitlement to submit the existing request.
        self.assertFalse(out.eligible_for_transport)


if __name__=="__main__":
    unittest.main()
