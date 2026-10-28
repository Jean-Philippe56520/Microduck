"""F4-A category memory integration: only historic F1-C/F2-C mock evidence."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import sqlite3
import tempfile
import unittest

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_learning import PassiveLearning
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot
from microduck_companion.category_semantics import (
    CategorySemantics, RETENTION_S, MAX_SEMANTIC_ROWS, MAX_HYPOTHESES,
)

WALL = 1_770_000_000.


def observation(label="ball", *, kind="object_label", mono=100.,
                confidence=.96, track="track-fictional"):
    return PerceptionEvent(
        kind,label,"mock",mono,1.,confidence,
        track_id=track if kind=="object_label" else None,
    )


def receipt(*events,seq=1,mono=100.):
    return PassiveRead(
        "ok",PerceptionSnapshot("mock",tuple(events),mono),seq,
        "mock_fixture_unix",
    )


class SemanticMemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"knowledge.sqlite3"
        self.mem=ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.journal=PassiveObservationJournal(self.mem)
        self.learning=PassiveLearning(self.mem)
        self.semantic=CategorySemantics(self.mem)

    def record(self,label="ball",*,seq=1,mono=100.,wall=WALL,
               kind="object_label",confidence=.96):
        r=receipt(observation(label,kind=kind,mono=mono,
                              confidence=confidence),seq=seq,mono=mono)
        assert self.journal.append(
            r,now_monotonic_s=mono+.1,now_wall_epoch_s=wall)==1
        recorded=self.learning.record(
            journal=self.journal,sequence=seq,now_wall_epoch_s=wall)
        assert len(recorded)==1
        return recorded[0].observation_id

    def remember(self,id,wall=WALL):
        return self.semantic.remember(
            journal=self.journal,learning=self.learning,
            observation_id=id,now_wall_epoch_s=wall)

    def test_zero_evidence_has_no_known_categories(self):
        self.assertEqual((),self.semantic.recall(now_wall_epoch_s=WALL))
        self.assertEqual(0,self.mem.conn.execute(
            "SELECT COUNT(*) FROM f4a_semantic_categories").fetchone()[0])
        self.assertIsNone(self.mem.get("toy"))

    def test_new_mock_category_is_historical_only(self):
        sid=self.record()
        self.assertTrue(self.remember(sid))
        (item,)=self.semantic.recall(now_wall_epoch_s=WALL)
        self.assertEqual(("ball","visual_label","0.96"),
                         (item.category,item.modality,str(item.reported_confidence)))
        self.assertTrue(item.historical_only)
        self.assertFalse(item.real_sensor_verified)
        self.assertEqual(item.motor_commands_issued,0)
        self.assertEqual(item.source,"mock_fixture_journal")
        self.assertEqual(sid,item.observation_id)
        self.assertEqual(0,self.mem.experience_count())

    def test_idempotent_semantics_without_double_learning(self):
        sid=self.record()
        self.assertTrue(self.remember(sid))
        self.assertFalse(self.remember(sid))
        self.assertEqual(1,len(self.semantic.recall(now_wall_epoch_s=WALL)))
        self.assertAlmostEqual(.02,self.learning.preference("observe"))

    def test_sound_modality_separated_from_visual(self):
        one=self.record("bark",kind="sound_label")
        self.assertTrue(self.remember(one))
        (rec,)=self.semantic.recall(now_wall_epoch_s=WALL)
        self.assertEqual(("bark","sound_label"),(rec.category,rec.modality))
        self.assertFalse(rec.real_sensor_verified)
        self.assertNotIn("voiceprint",str(rec))

    def test_repeated_observation_kept_but_no_individual_identity(self):
        one=self.record("dog")
        two=self.record("dog",seq=2,mono=101.,wall=WALL+1)
        self.assertTrue(self.remember(one))
        self.assertTrue(self.remember(two,WALL+1))
        rows=self.semantic.recall(now_wall_epoch_s=WALL+1,category="dog")
        self.assertEqual(2,len(rows))
        self.assertTrue(all(r.category=="dog" for r in rows))
        self.assertNotIn("track-fictional",str(rows))
        self.assertFalse(any(r.real_sensor_verified for r in rows))

    def test_unknown_and_low_confidence_never_become_facts(self):
        for sid,label,conf in ((1,"unknown",.96),(2,"cat",.2)):
            old=self.record(label,seq=sid,mono=100.+sid,
                            wall=WALL+sid,confidence=conf)
            self.assertFalse(self.remember(old,WALL+sid))
        self.assertEqual((),self.semantic.recall(now_wall_epoch_s=WALL+5))

    def test_duplicate_in_same_frame_does_not_increase_semantics(self):
        r=receipt(
            observation("ball",track="track-one"),
            observation("ball",track="track-two"),
        )
        self.assertEqual(2,self.journal.append(
            r,now_monotonic_s=100.1,now_wall_epoch_s=WALL))
        result=self.learning.record(
            journal=self.journal,sequence=1,now_wall_epoch_s=WALL)
        self.assertEqual(("new_information","duplicate_in_frame"),
                         tuple(x.outcome for x in result))
        self.assertTrue(self.remember(result[0].observation_id))
        self.assertFalse(self.remember(result[1].observation_id))
        self.assertEqual(1,len(self.semantic.recall(now_wall_epoch_s=WALL)))

    def test_f2c_retraction_is_immediate_and_does_not_promote_history(self):
        sid=self.record("cat")
        self.assertTrue(self.remember(sid))
        self.assertTrue(self.learning.retract(sid,reason="source_retracted"))
        self.assertEqual((),self.semantic.recall(now_wall_epoch_s=WALL))
        self.assertFalse(self.remember(sid))
        self.assertEqual(0,self.mem.conn.execute(
            "SELECT COUNT(*) FROM objects").fetchone()[0])

    def test_source_row_changed_underneath_cannot_remain_semantic_truth(self):
        sid=self.record("cat")
        self.assertTrue(self.remember(sid))
        self.mem.conn.execute(
            "UPDATE passive_observation_log SET category='dog' WHERE id=?",
            (sid,))
        self.assertEqual((),self.semantic.recall(now_wall_epoch_s=WALL))
        self.assertEqual(0,self.mem.conn.execute(
            "SELECT COUNT(*) FROM objects").fetchone()[0])

    def test_f4a_forgetting_reversible_source_but_not_resurrected(self):
        sid=self.record("toy")
        self.assertTrue(self.remember(sid))
        self.assertTrue(self.semantic.forget_observation(
            sid,reason="fixture_annotation_error"))
        self.assertFalse(self.semantic.forget_observation(
            sid,reason="fixture_annotation_error"))
        self.assertEqual((),self.semantic.recall(now_wall_epoch_s=WALL))
        self.assertFalse(self.remember(sid))

    def test_expired_or_future_evidence_never_accepted(self):
        sid=self.record("ball")
        self.assertFalse(self.remember(sid,WALL+3))
        self.assertFalse(self.remember(sid,WALL-.2))
        self.assertEqual((),self.semantic.recall(now_wall_epoch_s=WALL+3))

    def test_different_journal_or_learning_database_rejected(self):
        other=ExperienceMemory()
        self.addCleanup(other.close)
        alien=PassiveObservationJournal(other)
        separate_learning=PassiveLearning(other)
        sid=self.record()
        for journal,learning in ((alien,self.learning),
                                 (self.journal,separate_learning)):
            with self.assertRaises(ValueError):
                self.semantic.remember(
                    journal=journal,learning=learning,
                    observation_id=sid,now_wall_epoch_s=WALL)
        self.assertEqual((),self.semantic.recall(now_wall_epoch_s=WALL))

    def test_sqlite_persists_across_reopen_and_never_replays_sensors(self):
        sid=self.record("dog")
        self.assertTrue(self.remember(sid))
        self.mem.close()
        next_mem=ExperienceMemory(self.path)
        try:
            next_sem=CategorySemantics(next_mem)
            (x,)=next_sem.recall(now_wall_epoch_s=WALL+1)
            self.assertEqual("dog",x.category)
            self.assertTrue(x.historical_only)
            self.assertFalse(x.real_sensor_verified)
        finally:
            next_mem.close()

    def test_aged_data_is_invisible_and_pruned(self):
        sid=self.record()
        self.assertTrue(self.remember(sid))
        self.assertEqual((),self.semantic.recall(
            now_wall_epoch_s=WALL+RETENTION_S+1))
        self.semantic.prune(now_wall_epoch_s=WALL+RETENTION_S+1)
        self.assertEqual(0,self.mem.conn.execute(
            "SELECT COUNT(*) FROM f4a_semantic_categories").fetchone()[0])

    def test_hypothesis_not_fact_and_stays_unverified(self):
        hid=self.semantic.hypothesize(
            category="cat",property="texture",value="soft",
            confidence=.72,now_wall_epoch_s=WALL)
        self.assertIsInstance(hid,int)
        self.assertEqual((),self.semantic.recall(now_wall_epoch_s=WALL))
        (row,)=self.semantic.hypotheses(category="cat",now_wall_epoch_s=WALL)
        self.assertEqual(("texture","soft"),(row.property,row.value))
        self.assertFalse(row.confirmed)
        self.assertFalse(row.can_authorize_actions)
        self.assertEqual("fictional_llm_hypothesis_only",row.source)
        self.assertIsNone(self.semantic.hypothesize(
            category="cat",property="texture",value="soft",
            confidence=.90,now_wall_epoch_s=WALL))
        self.assertEqual(.72,self.semantic.hypotheses(
            category="cat",now_wall_epoch_s=WALL)[0].proposed_confidence)

    def test_conflicting_hypotheses_are_not_resolved_as_truth(self):
        self.semantic.hypothesize(category="dog",property="movement",
            value="moving",confidence=.9,now_wall_epoch_s=WALL)
        self.semantic.hypothesize(category="dog",property="movement",
            value="stationary",confidence=.8,now_wall_epoch_s=WALL)
        rows=self.semantic.hypotheses(category="dog",now_wall_epoch_s=WALL)
        self.assertEqual({"moving","stationary"},{r.value for r in rows})
        self.assertTrue(all(not r.confirmed for r in rows))
        self.assertEqual((),self.semantic.recall(now_wall_epoch_s=WALL))

    def test_hypotheses_cannot_contain_people_locations_or_safety_grants(self):
        for args in (
            {"category":"person","property":"texture","value":"soft"},
            {"category":"unknown","property":"texture","value":"soft"},
            {"category":"private-name","property":"texture","value":"soft"},
            {"category":"cat","property":"location","value":"home"},
            {"category":"dog","property":"affordance","value":"safe_to_move"},
            {"category":"cat","property":"texture","value":"biometric"},
        ):
            with self.subTest(args=args),self.assertRaises(ValueError):
                self.semantic.hypothesize(
                    **args,confidence=.4,now_wall_epoch_s=WALL)

    def test_bad_confidence_or_clocks_are_rejected(self):
        for conf in (True,-.1,1.1,float("nan"),float("inf"),"0.6"):
            with self.subTest(conf=conf),self.assertRaises(ValueError):
                self.semantic.hypothesize(category="cat",property="texture",
                    value="soft",confidence=conf,now_wall_epoch_s=WALL)
        for now in (-1.,True,float("nan"),float("inf")):
            with self.subTest(now=now),self.assertRaises(ValueError):
                self.semantic.hypothesize(category="cat",property="texture",
                    value="soft",confidence=.6,now_wall_epoch_s=now)

    def test_hypothesis_retraction_and_ttl(self):
        hid=self.semantic.hypothesize(category="cat",property="texture",
            value="soft",confidence=.6,now_wall_epoch_s=WALL)
        self.assertTrue(self.semantic.retract_hypothesis(
            hid,reason="source_retracted"))
        self.assertFalse(self.semantic.retract_hypothesis(
            hid,reason="source_retracted"))
        self.assertEqual((),self.semantic.hypotheses(
            category="cat",now_wall_epoch_s=WALL))
        self.assertFalse(self.semantic.retract_hypothesis(
            hid+1,reason="source_retracted"))
        self.semantic.prune(now_wall_epoch_s=WALL+RETENTION_S+1)
        # C2: a retracted hypothesis remains as a compact UNIQUE-key
        # correction marker, even when its former active TTL has expired.
        row=self.mem.conn.execute("""
            SELECT active,correction_reason,proposed_confidence
            FROM f4a_property_hypotheses WHERE id=?
        """,(hid,)).fetchone()
        self.assertEqual((0,"source_retracted",0.),
                         tuple(row))
        self.assertIsNone(self.semantic.hypothesize(
            category="cat",property="texture",value="soft",
            confidence=.99,now_wall_epoch_s=WALL+RETENTION_S+2))
        self.assertEqual((),self.semantic.hypotheses(
            category="cat",now_wall_epoch_s=WALL+RETENTION_S+2))

    def test_invalid_limits_and_schemas_fail_closed(self):
        sid=self.record()
        for limit in (True,0,51):
            with self.assertRaises(ValueError):
                self.semantic.recall(now_wall_epoch_s=WALL,limit=limit)
            with self.assertRaises(ValueError):
                self.semantic.hypotheses(category="cat",
                    now_wall_epoch_s=WALL,limit=limit)
        for index in (True,0,-1):
            with self.assertRaises(ValueError):
                self.remember(index)
        with self.assertRaises(ValueError):
            self.semantic.recall(now_wall_epoch_s=WALL,category="stranger")
        with self.assertRaises(ValueError):
            self.semantic.forget_observation(sid,reason="motor_allow")
        with self.assertRaises(ValueError):
            self.semantic.retract_hypothesis(1,reason="unapproved")

    def test_closed_sqlite_never_grants_truth_or_motion(self):
        self.mem.close()
        with self.assertRaises(sqlite3.Error):
            self.semantic.recall(now_wall_epoch_s=WALL)
        with self.assertRaises(sqlite3.Error):
            self.semantic.hypothesize(category="cat",property="texture",
                value="soft",confidence=.5,now_wall_epoch_s=WALL)


if __name__=="__main__":
    unittest.main()
