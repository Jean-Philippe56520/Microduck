"""F4-C: mock-only, quiet-by-default social proposal contracts."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot
from microduck_companion.mock_social_cues import (
    MockSocialComposer, MockSocialContext, MockSocialPlan, MAX_SOUNDS_PER_WINDOW,
    MAX_LOG_ROWS, PLAN_DURATIONS_MS, MIN_GLOBAL_GAP_S,
    MIN_SAME_CUE_GAP_S, SOUND_WINDOW_S,
)

WALL=1_780_000_000.


def event(label="ball", *, kind="object_label", t=100., confidence=.96,
          source="mock", track="track-ephemeral"):
    return PerceptionEvent(
        kind,label,source,t,1.,confidence,
        track_id=track if kind=="object_label" else None)


def reading(*events, sequence=1, t=100., status="ok",
            channel="mock_fixture_unix", environment="mock"):
    return PassiveRead(
        status,PerceptionSnapshot(environment,tuple(events),t),
        sequence,channel)


def permitted(**kw):
    opts=dict(operator_opt_in=True,supervised=True,privacy_reviewed=True,
              quiet_mode=False)
    opts.update(kw)
    return MockSocialContext(**opts)


class SocialProposalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"memory.sqlite3"
        self.mem=ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.journal=PassiveObservationJournal(self.mem)
        self.brain=AutonomyBrain(self.mem)
        self.composer=MockSocialComposer(self.brain,self.journal)

    def cue(self,label="ball",*,kind="object_label",at=100.,seq=1,
            now=None,wall=WALL,context=None,confidence=.96,track="track-public"):
        r=reading(event(label,kind=kind,t=at,confidence=confidence,track=track),
                  sequence=seq,t=at)
        return self.composer.propose(
            r,context=context if context is not None else permitted(),
            now_monotonic_s=at+.1 if now is None else now,
            now_wall_epoch_s=wall,
        )

    def test_default_context_is_silent_and_unrecorded(self):
        result=self.cue(context=MockSocialContext())
        self.assertEqual(("silence","no_operator_opt_in_or_supervision"),
                         (result.kind,result.reason))
        self.assertEqual(0,self.composer.count_proposals())
        self.assertEqual(.8,self.brain.motives.energy)

    def test_consent_is_mock_declaration_not_real_authorization(self):
        result=self.cue()
        self.assertEqual("glance",result.kind)
        self.assertEqual("ball",result.category)
        self.assertEqual(250,result.duration_ms)
        self.assertFalse(result.executed)
        self.assertFalse(result.real_consent_verified)
        self.assertFalse(result.real_sensor_authenticated)
        self.assertFalse(result.identity_verified)
        self.assertFalse(result.physical_execution_authorized)
        self.assertEqual((0,0,0,0),
                         (result.motor_commands_issued,result.speaker_commands_issued,
                          result.audio_bytes_stored,result.gaze_motor_commands_issued))
        self.assertEqual(1,self.composer.count_proposals())

    def test_missing_individual_claims_prevent_social_attention(self):
        for opts in (
            dict(operator_opt_in=False),
            dict(supervised=False),
            dict(privacy_reviewed=False),
        ):
            with self.subTest(opts=opts):
                r=self.cue(context=permitted(**opts))
                self.assertEqual("silence",r.kind)
        self.assertEqual(0,self.composer.count_proposals())

    def test_quiet_mode_blocks_visual_and_audio_candidates(self):
        r=self.cue(context=permitted(quiet_mode=True))
        self.assertEqual(("silence","quiet_mode"),(r.kind,r.reason))
        self.assertEqual(0,self.composer.count_proposals())

    def test_rest_from_existing_brain_is_silent_simulation(self):
        self.brain.motives.energy=.15
        answer=self.cue(context=permitted(quiet_mode=True))
        self.assertEqual("rest",answer.kind)
        self.assertIsNone(answer.category)
        self.assertEqual(0,answer.duration_ms)
        self.assertEqual(0,self.composer.count_proposals())
        self.assertFalse(answer.physical_execution_authorized)
        self.assertGreater(self.brain.motives.energy,.15)

    def test_toy_play_proposal_requires_separate_opt_in_and_motivation(self):
        self.brain.motives.play=.85
        r=self.cue("toy",context=permitted(play_invitation_opt_in=True))
        self.assertEqual(("play_cue","toy",300),
                         (r.kind,r.category,r.duration_ms))
        self.assertFalse(r.physical_execution_authorized)
        self.assertEqual(0,r.gaze_motor_commands_issued)
        self.assertEqual(0,r.speaker_commands_issued)

    def test_no_play_opt_in_proposes_brief_glance_only(self):
        self.brain.motives.play=.95
        self.assertEqual("glance",self.cue("toy").kind)

    def test_low_play_drive_falls_back_to_brief_glance(self):
        self.brain.motives.play=.25
        r=self.cue("toy",context=permitted(play_invitation_opt_in=True))
        self.assertEqual("glance",r.kind)

    def test_generic_mock_dog_and_cat_are_not_individual_identities(self):
        for label in ("cat","dog"):
            with self.subTest(label=label):
                brain=AutonomyBrain(self.mem)
                journal=PassiveObservationJournal(self.mem)
                composer=MockSocialComposer(brain,journal)
                item=composer.propose(
                    reading(event(label,t=100.)),context=permitted(),
                    now_monotonic_s=100.1,
                    now_wall_epoch_s=WALL+100. if label=="dog" else WALL+30.)
                self.assertEqual("glance",item.kind)
                self.assertEqual(label,item.category)
                self.assertFalse(item.identity_verified)
        self.assertEqual(2,self.composer.count_proposals())

    def test_animal_sound_requires_separate_brief_audio_opt_in(self):
        denied=self.cue("bark",kind="sound_label")
        self.assertEqual(("silence","brief_audio_not_opted_in"),
                         (denied.kind,denied.reason))
        self.assertEqual(0,self.composer.count_proposals())
        # Repeat with new source sequence and a sufficiently fresh fixture.
        allowed=self.cue("bark",kind="sound_label",seq=2,at=103.,
                         context=permitted(brief_audio_opt_in=True))
        self.assertEqual(("chirp","bark",180),
                         (allowed.kind,allowed.category,allowed.duration_ms))
        self.assertEqual(0,allowed.speaker_commands_issued)
        self.assertEqual(0,allowed.audio_bytes_stored)

    def test_speech_keywords_stop_and_person_never_trigger_cue(self):
        cases=(("person","object_label"),
               ("unknown","object_label"),
               ("microduck","object_label"),
               ("Malo","object_label"),
               ("speech","sound_label"),
               ("keyword_stop","sound_label"),
               ("keyword_microduck","sound_label"),
               ("keyword_viens","sound_label"),
               ("ambient","sound_label"),
               ("unknown","sound_label"))
        for label,kind in cases:
            with self.subTest(label=label):
                r=self.cue(label,kind=kind,
                           context=permitted(brief_audio_opt_in=True))
                self.assertEqual("silence",r.kind)
        self.assertEqual(0,self.composer.count_proposals())
        self.assertEqual(.8,self.brain.motives.energy)

    def test_multiple_categories_or_modalities_fail_silent(self):
        examples=(
            (event("ball"),event("dog",track="track-second")),
            (event("toy"),event("bark",kind="sound_label")),
            (event("dog"),event("unknown",track="track-private")),
        )
        for pair in examples:
            r=self.composer.propose(
                reading(*pair),context=permitted(brief_audio_opt_in=True),
                now_monotonic_s=100.1,now_wall_epoch_s=WALL)
            self.assertEqual("silence",r.kind)
        self.assertEqual(0,self.composer.count_proposals())

    def test_stale_low_confidence_and_no_events_cannot_emit(self):
        cases=(
            (reading(event("ball",confidence=.2)),100.1),
            (reading(event("dog",t=100.)),102.),
            (reading(),100.1),
        )
        for r,now in cases:
            with self.subTest(r=r):
                brain=AutonomyBrain(self.mem)
                c=MockSocialComposer(brain,PassiveObservationJournal(self.mem))
                result=c.propose(r,context=permitted(),
                                 now_monotonic_s=now,now_wall_epoch_s=WALL)
                self.assertEqual("silence",result.kind)
        self.assertEqual(0,self.composer.count_proposals())

    def test_untrusted_sources_and_safety_kinds_never_social(self):
        cases=(
            reading(event("ball",source="sensor")),
            reading(event("ball"),channel="oem_media_hello_only"),
            reading(event("ball"),environment="robot"),
            reading(event("ball"),status="unavailable_or_invalid"),
            reading(PerceptionEvent("floor_clear",True,"mock",100.,1.,1.)),
        )
        for r in cases:
            with self.subTest(r=r):
                result=self.composer.propose(
                    r,context=permitted(),
                    now_monotonic_s=100.1,now_wall_epoch_s=WALL)
                self.assertEqual("silence",result.kind)
        self.assertEqual(0,self.composer.count_proposals())

    def test_global_cooldown_blocks_different_category(self):
        first=self.cue("ball")
        self.assertEqual("glance",first.kind)
        second=self.cue("dog",seq=2,at=103.1,wall=WALL+3.1)
        self.assertEqual(("silence","social_global_cooldown"),
                         (second.kind,second.reason))
        self.assertEqual(1,self.composer.count_proposals())

    def test_same_cue_cooldown_survives_global_gate(self):
        self.assertEqual("glance",self.cue().kind)
        r=self.cue("ball",seq=2,at=112.,wall=WALL+12.)
        self.assertEqual(("silence","social_same_cue_cooldown"),
                         (r.kind,r.reason))
        self.assertEqual(1,self.composer.count_proposals())

    def test_same_cue_may_be_proposed_after_cooldown_only(self):
        self.assertEqual("glance",self.cue().kind)
        nextone=self.cue("ball",seq=2,at=161.,wall=WALL+61.)
        self.assertEqual("glance",nextone.kind)
        self.assertEqual(2,self.composer.count_proposals())

    def test_two_chirps_in_ten_minutes_max(self):
        context=permitted(brief_audio_opt_in=True)
        r1=self.cue("bark",kind="sound_label",context=context)
        r2=self.cue("meow",kind="sound_label",context=context,
                    at=171.,wall=WALL+71.,seq=2)
        r3=self.cue("bark",kind="sound_label",context=context,
                    at=251.,wall=WALL+151.,seq=3)
        self.assertEqual(("chirp","chirp","silence"),
                         (r1.kind,r2.kind,r3.kind))
        self.assertEqual("social_sound_budget",r3.reason)
        self.assertEqual(2,self.composer.count_proposals())

    def test_sound_budget_resets_after_window(self):
        context=permitted(brief_audio_opt_in=True)
        self.cue("bark",kind="sound_label",context=context)
        self.cue("meow",kind="sound_label",context=context,
                 at=171.,wall=WALL+71.,seq=2)
        r=self.cue("bark",kind="sound_label",context=context,
                   at=710.,wall=WALL+610.,seq=3)
        self.assertEqual("chirp",r.kind)
        self.assertEqual(3,self.composer.count_proposals())

    def test_wall_clock_regression_refuses_new_interaction(self):
        self.assertEqual("glance",self.cue(wall=WALL+20.).kind)
        r=self.cue("dog",seq=2,at=120.,wall=WALL+10.)
        self.assertEqual(("silence","wall_clock_regression"),
                         (r.kind,r.reason))
        self.assertEqual(1,self.composer.count_proposals())

    def test_cross_process_sqlite_cooldown_rejects_replayed_cue(self):
        ctx=permitted(brief_audio_opt_in=True)
        self.assertEqual("chirp",self.cue("bark",kind="sound_label",
                                       context=ctx).kind)
        # Reopen the DB with a completely new brain and fixture journal.
        other=ExperienceMemory(self.path)
        self.addCleanup(other.close)
        composer=MockSocialComposer(
            AutonomyBrain(other),PassiveObservationJournal(other))
        r=composer.propose(
            reading(event("bark",kind="sound_label",t=120.),sequence=1,t=120.),
            context=ctx,now_monotonic_s=120.1,now_wall_epoch_s=WALL+20.)
        self.assertEqual(("silence","social_same_cue_cooldown"),
                         (r.kind,r.reason))
        self.assertEqual(1,composer.count_proposals())

    def test_no_ephemeral_track_or_private_name_is_persisted(self):
        self.cue("ball",track="track-one-time-private")
        values=self.mem.conn.execute("""
            SELECT kind,category,source FROM f4c_mock_social_proposals
        """).fetchall()
        self.assertEqual([("glance","ball","mock_social_proposal_only")],
                         [tuple(x) for x in values])
        schema=self.mem.conn.execute("""
            SELECT sql FROM sqlite_master
            WHERE name='f4c_mock_social_proposals'
        """).fetchone()[0]
        self.assertNotIn("track_id",schema)
        self.assertNotIn("identity",schema)
        self.assertNotIn("audio_blob",schema)
        self.assertNotIn("person_name",schema)

    def test_context_and_plan_shapes_reject_execution_or_forgery(self):
        for field in ("supervised","operator_opt_in","quiet_mode"):
            with self.subTest(field=field),self.assertRaises(ValueError):
                MockSocialContext(**{field:1})
        for kw in (
            {"kind":"glance","reason":"test","category":"person",
             "duration_ms":250},
            {"kind":"chirp","reason":"test","category":"speech",
             "duration_ms":180},
            {"kind":"chirp","reason":"test","category":"meow",
             "duration_ms":180,"speaker_commands_issued":1},
            {"kind":"play_cue","reason":"test","category":"ball",
             "duration_ms":300,"executed":True},
            {"kind":"glance","reason":"test","category":"dog",
             "duration_ms":250,"physical_execution_authorized":True},
            {"kind":"rest","reason":"test","category":"cat"},
            {"kind":"dance","reason":"test"},
        ):
            with self.subTest(kw=kw),self.assertRaises(ValueError):
                MockSocialPlan(**kw)

    def test_cross_database_and_wrong_types_fail_closed(self):
        another=ExperienceMemory()
        self.addCleanup(another.close)
        with self.assertRaises(ValueError):
            MockSocialComposer(self.brain,PassiveObservationJournal(another))
        with self.assertRaises(TypeError):
            MockSocialComposer(object(),self.journal)
        with self.assertRaises(TypeError):
            self.composer.propose("fake",context=permitted(),
                now_monotonic_s=100.1,now_wall_epoch_s=WALL)
        with self.assertRaises(TypeError):
            self.composer.propose(reading(event()),
                context={"operator_opt_in":True},
                now_monotonic_s=100.1,now_wall_epoch_s=WALL)

    def test_bad_clock_cannot_change_log(self):
        r=reading(event())
        for mono,wall in ((True,WALL),(float("nan"),WALL),
                          (float("inf"),WALL),(-1.,WALL),
                          (100.1,True),(100.1,float("nan"))):
            with self.subTest(mono=mono,wall=wall),self.assertRaises(ValueError):
                self.composer.propose(r,context=permitted(),
                    now_monotonic_s=mono,now_wall_epoch_s=wall)
        self.assertEqual(0,self.composer.count_proposals())

    def test_closed_db_cannot_grant_interaction(self):
        self.mem.close()
        r=self.cue()
        self.assertEqual("silence",r.kind)
        self.assertFalse(r.physical_execution_authorized)

    def test_brain_motion_safety_unaffected_by_social_glance(self):
        from microduck_companion.perception import PerceptionSnapshot
        self.assertEqual("glance",self.cue().kind)
        plan=self.brain.choose_from_snapshot(
            PerceptionSnapshot("mock",(),100.),now=100.1)
        self.assertEqual("halt",plan.intention)
        self.assertEqual(0,self.mem.conn.execute(
            "SELECT COUNT(*) FROM intent_preferences").fetchone()[0])
        self.assertEqual(0,self.mem.experience_count())

if __name__=="__main__":
    unittest.main()
