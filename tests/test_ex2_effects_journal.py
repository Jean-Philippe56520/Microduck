"""EX2 fictional effects and the optional read-only Kwipi Journal."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_ledger import (
    MockExperienceLedger, MockResolution,
)
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.experience_effects import (
    MockCue, MockEffectPair, MockEffectJournal, RETENTION_S,
)
from microduck_companion.kwipi_journal import read_journal, render_journal

NOW = 1_770_000_000.0
SESSION = "s-000000000000000a"


def cue(value, *, at, kind="motion", confidence=.95):
    return MockCue(kind, value, at, confidence)


class EX2EffectsTests(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "kwipi.sqlite3"
        self.mem = ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.ex1 = MockExperienceLedger(self.mem)
        self.effects = MockEffectJournal(self.ex1)

    def proposal(self, sequence=1, *, status="mock_executed",
                 intention="inspect", target="ball", start=NOW):
        kind = "sound_label" if intention == "listen" else "object_label"
        self.ex1.record_proposal(
            PassiveIntent(intention, "synthetic event", kind, target),
            session=SESSION, sequence=sequence,
            proposed_at_epoch_s=start,
        )
        if status is not None:
            self.ex1.resolve(MockResolution(SESSION, sequence, status, start+1))

    def pair(self, sequence=1, *, before="still", after="moving",
             kind="motion", confidence=.95, same_scene=True,
             competing=False, start=NOW):
        return MockEffectPair(
            SESSION, sequence, cue(before, at=start-.5, kind=kind,
                                   confidence=confidence),
            cue(after, at=start+1.2, kind=kind, confidence=confidence),
            same_scene, competing,
        )

    def test_typed_mock_effect_with_temporal_but_never_causal_link(self):
        self.proposal()
        self.assertTrue(self.effects.record(self.pair()))
        (trace,) = self.effects.history(now_wall_epoch_s=NOW+2)
        self.assertEqual(("changed", "temporal_only", "after_mock_resolution"),
                         (trace.effect_status, trace.association_status,
                          trace.reason_code))
        self.assertFalse(trace.causality_established)
        self.assertFalse(trace.verified_on_robot)
        self.assertEqual(0, trace.motor_commands_issued)
        self.assertEqual("ball", trace.category)
        self.assertEqual(0, self.mem.experience_count())
        self.assertEqual(0., self.mem.intent_preference("robot", "explore"))

    def test_identical_replay_is_idempotent(self):
        self.proposal()
        a = self.pair()
        self.assertTrue(self.effects.record(a))
        self.assertFalse(self.effects.record(a))
        self.assertEqual(1, self.mem.conn.execute(
            "SELECT COUNT(*) FROM ex2_mock_effects").fetchone()[0])

    def test_divergent_replay_does_not_replace_evidence(self):
        self.proposal()
        self.effects.record(self.pair())
        with self.assertRaises(ValueError):
            self.effects.record(self.pair(after="still"))
        self.assertEqual("changed",
                         self.effects.history(now_wall_epoch_s=NOW+2)[0].effect_status)

    def test_no_effect_if_unexecuted_interrupted_or_refused(self):
        for seq, status in ((1, None), (2, "refused"), (3, "interrupted")):
            self.proposal(seq, status=status)
            with self.subTest(status=status), self.assertRaises(ValueError):
                self.effects.record(self.pair(seq))
        self.assertEqual((), self.effects.history(now_wall_epoch_s=NOW+2))
        self.assertEqual(0, self.mem.experience_count())

    def test_no_effect_for_idle_and_rest_even_when_mock_executed(self):
        for seq, intention in ((1, "idle"), (2, "rest")):
            self.ex1.record_proposal(PassiveIntent(intention, "fictional rest"),
                session=SESSION, sequence=seq, proposed_at_epoch_s=NOW)
            self.ex1.resolve(MockResolution(SESSION,seq,"mock_executed", NOW+1))
            with self.assertRaises(ValueError):
                self.effects.record(self.pair(seq))

    def test_unknown_cue_or_category_abstains(self):
        self.proposal(target="unknown")
        self.effects.record(self.pair())
        (trace,) = self.effects.history(now_wall_epoch_s=NOW+2)
        self.assertEqual(("indeterminate", "indeterminate"),
                         (trace.effect_status,trace.association_status))
        self.assertEqual("unknown_cue_or_category", trace.reason_code)

    def test_low_confidence_abstains(self):
        self.proposal()
        self.effects.record(self.pair(confidence=.55))
        (trace,) = self.effects.history(now_wall_epoch_s=NOW+2)
        self.assertEqual("low_mock_confidence", trace.reason_code)
        self.assertEqual("indeterminate", trace.effect_status)

    def test_competing_event_does_not_become_action_cause(self):
        self.proposal()
        self.effects.record(self.pair(competing=True))
        (trace,) = self.effects.history(now_wall_epoch_s=NOW+2)
        self.assertEqual("confounded", trace.association_status)
        self.assertEqual("competing_event", trace.reason_code)
        self.assertFalse(trace.causality_established)

    def test_scene_discontinuity_stays_indeterminate(self):
        self.proposal()
        self.effects.record(self.pair(same_scene=False))
        (trace,) = self.effects.history(now_wall_epoch_s=NOW+2)
        self.assertEqual("scene_not_correlated", trace.reason_code)
        self.assertEqual("indeterminate", trace.effect_status)

    def test_unchanged_scene_never_reports_positive_or_negative(self):
        self.proposal()
        self.effects.record(self.pair(after="still"))
        (trace,) = self.effects.history(now_wall_epoch_s=NOW+2)
        self.assertEqual("unchanged", trace.effect_status)
        self.assertEqual("none", trace.association_status)

    def test_social_cue_is_observation_not_emotional_intent(self):
        self.proposal()
        self.effects.record(self.pair(
            kind="social",before="no_signal",after="friendly_signal"))
        (trace,) = self.effects.history(now_wall_epoch_s=NOW+2)
        self.assertEqual("social", trace.cue_kind)
        self.assertEqual("temporal_only", trace.association_status)
        self.assertFalse(trace.causality_established)

    def test_listen_sound_cue_and_mismatched_modality(self):
        self.proposal(intention="listen",target="bark")
        self.effects.record(self.pair(
            kind="sound",before="quiet",after="heard"))
        self.assertEqual("sound",self.effects.history(
            now_wall_epoch_s=NOW+2)[0].cue_kind)
        with self.assertRaises(ValueError):
            self.effects.record(self.pair(kind="motion"))

    def test_bad_source_and_type_disallowed(self):
        self.proposal()
        with self.assertRaises(ValueError):
            MockCue("motion","still",NOW,1.0,source="sensor")
        with self.assertRaises(ValueError):
            MockCue("motion","still",NOW,float("nan"))
        with self.assertRaises(ValueError):
            MockCue("motion","sleep",NOW,.95)
        with self.assertRaises(ValueError):
            MockEffectPair(SESSION,1,cue("still",at=NOW),
                           cue("moving",at=NOW),True,False)
        with self.assertRaises(ValueError):
            MockEffectPair(SESSION,1,cue("still",at=NOW),
                           cue("heard",kind="sound",at=NOW+1),True,False)
        with self.assertRaises(TypeError):
            self.effects.record({"result":"moving"})
        with self.assertRaises(ValueError):
            MockEffectPair(SESSION,1,cue("still",at=NOW),
                           cue("moving",at=NOW+1),"yes",False)

    def test_stale_future_or_wrong_order_rejected(self):
        self.proposal()
        for before, after in ((NOW-3,NOW+1.2), (NOW+.1,NOW+1.2),
                              (NOW-.5,NOW+.8),(NOW-.5,NOW+3.01)):
            pair=MockEffectPair(
                SESSION,1,cue("still",at=before),
                cue("moving",at=after),True,False)
            with self.subTest(before=before,after=after), self.assertRaises(ValueError):
                self.effects.record(pair)

    def test_retraction_and_parent_retraction_hide_effects(self):
        self.proposal()
        self.effects.record(self.pair())
        self.assertTrue(self.effects.retract(
            session=SESSION,sequence=1,reason="source_retracted"))
        self.assertFalse(self.effects.retract(
            session=SESSION,sequence=1,reason="source_retracted"))
        self.assertEqual((),self.effects.history(now_wall_epoch_s=NOW+2))
        with self.assertRaises(ValueError):
            self.effects.record(self.pair())
        self.assertTrue(self.ex1.retract(
            session=SESSION,sequence=1,reason="fixture_annotation_error"))
        self.assertEqual((),self.effects.history(now_wall_epoch_s=NOW+2))
        with self.assertRaises(ValueError):
            self.effects.retract(
                session=SESSION,sequence=1,reason="invalid")
        with self.assertRaises(ValueError):
            self.effects.history(now_wall_epoch_s=NOW+2,limit=51)

    def test_parent_retraction_alone_invalidates_visibility(self):
        self.proposal()
        self.effects.record(self.pair())
        self.ex1.retract(session=SESSION,sequence=1,reason="source_retracted")
        self.assertEqual((),self.effects.history(now_wall_epoch_s=NOW+2))

    def test_cross_process_reads_persisted_fictional_effects(self):
        self.proposal()
        self.effects.record(self.pair())
        cmd=[
            sys.executable,"-m","microduck_companion.kwipi_journal",
            str(self.path),"--at",str(NOW+2),
        ]
        p=subprocess.run(cmd,capture_output=True,text=True,
            cwd=Path(__file__).resolve().parents[1],timeout=15)
        self.assertEqual(0,p.returncode,p.stderr)
        row=json.loads(p.stdout.splitlines()[0])
        self.assertEqual("changed",row["effect_status"])
        self.assertEqual("temporal_only",row["association_status"])
        self.assertFalse(row["verified_on_robot"])
        self.assertFalse(row["causality_established"])


class EX2JournalReadOnlyTests(unittest.TestCase):

    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path=Path(tmp.name)/"fixture.sqlite3"
        self.mem=ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.ex1=MockExperienceLedger(self.mem)
        self.ex1.record_proposal(
            PassiveIntent("inspect","fictional ball","object_label","ball"),
            session=SESSION,sequence=1,proposed_at_epoch_s=NOW)
        self.ex1.resolve(MockResolution(SESSION,1,"mock_executed",NOW+1))

    def read(self, **kwargs):
        return read_journal(self.path,now_wall_epoch_s=NOW+2,**kwargs)

    def test_ex1_only_database_is_readable_without_schema_mutation(self):
        before=self.path.read_bytes()
        (row,)=self.read()
        self.assertEqual(before,self.path.read_bytes())
        self.assertEqual("not_recorded",row["effect_status"])
        self.assertEqual("indeterminate",row["association_status"])
        self.assertFalse(row["verified_on_robot"])
        self.assertFalse(row["causality_established"])
        self.assertEqual("mock_fixture_only",row["source"])

    def test_ex2_join_filters_status_category_and_limits(self):
        effects=MockEffectJournal(self.ex1)
        effects.record(MockEffectPair(
            SESSION,1,cue("still",at=NOW-.5),
            cue("moving",at=NOW+1.2),True,False))
        (row,)=self.read(category="ball",status="mock_executed")
        self.assertEqual("changed",row["effect_status"])
        self.assertEqual("temporal_only",row["association_status"])
        self.assertEqual((),self.read(category="cat"))
        self.assertEqual((),self.read(status="refused"))
        self.assertEqual((),read_journal(self.path,
            now_wall_epoch_s=NOW+RETENTION_S+1))

    def test_export_csv_and_jsonl_use_fixed_schema(self):
        (row,)=self.read()
        csv_text=render_journal((row,),format="csv")
        self.assertIn("causality_established",csv_text)
        self.assertIn("mock_fixture_only",csv_text)
        exported=render_journal((row,),format="jsonl")
        parsed=json.loads(exported)
        self.assertFalse(parsed["causality_established"])
        self.assertNotIn("fictional ball",exported)
        self.assertEqual("",render_journal((),format="jsonl"))
        self.assertEqual(1,len(render_journal((),format="csv").splitlines()))

    def test_withdrawn_effect_stays_withdrawn_when_requested(self):
        effects=MockEffectJournal(self.ex1)
        effects.record(MockEffectPair(SESSION,1,cue("still",at=NOW-.5),
                                     cue("moving",at=NOW+1.2),True,False))
        effects.retract(session=SESSION,sequence=1,reason="source_retracted")
        (row,)=self.read(include_withdrawn=True)
        self.assertEqual("withdrawn",row["effect_status"])
        self.assertTrue(row["corrected"])
        self.assertEqual("effect_withdrawn",row["reason_code"])
        self.assertIsNone(row["after"])

    def test_parent_withdrawn_hidden_unless_requested(self):
        self.ex1.retract(session=SESSION,sequence=1,
                         reason="fixture_annotation_error")
        self.assertEqual((),self.read())
        (row,)=self.read(include_withdrawn=True)
        self.assertTrue(row["corrected"])
        self.assertEqual("withdrawn",row["status"])
        self.assertEqual("withdrawn",row["effect_status"])

    def test_bad_limits_filters_and_time_rejected(self):
        for k in (0,True,51,1.2):
            with self.subTest(limit=k),self.assertRaises(ValueError):
                self.read(limit=k)
        with self.assertRaises(ValueError):
            self.read(category="ball' OR 1=1 --")
        with self.assertRaises(ValueError):
            self.read(status="real_executed")
        with self.assertRaises(ValueError):
            self.read(include_withdrawn="true")
        with self.assertRaises(ValueError):
            read_journal(self.path,now_wall_epoch_s=float("nan"))
        with self.assertRaises(ValueError):
            render_journal((),format="pdf")

    def test_read_only_connection_never_creates_file(self):
        nonexistent=self.path.with_name("not-created.sqlite3")
        with self.assertRaises(FileNotFoundError):
            read_journal(nonexistent,now_wall_epoch_s=NOW+2)
        self.assertFalse(nonexistent.exists())

    def test_foreign_sqlite_schema_refused(self):
        other=self.path.with_name("unrelated.sqlite3")
        conn=sqlite3.connect(other)
        conn.execute("CREATE TABLE other (x INTEGER)")
        conn.close()
        with self.assertRaises(ValueError):
            read_journal(other,now_wall_epoch_s=NOW+2)

    def test_reader_does_not_change_existing_database_bytes(self):
        effects=MockEffectJournal(self.ex1)
        effects.record(MockEffectPair(
            SESSION,1,cue("still",at=NOW-.5),
            cue("moving",at=NOW+1.2),True,False))
        before=self.path.read_bytes()
        self.read()
        self.read(include_withdrawn=True)
        self.assertEqual(before,self.path.read_bytes())
        self.assertEqual(0,self.mem.experience_count())

    def test_cli_csv_is_on_demand_with_no_network(self):
        cmd=[
            sys.executable,"-m","microduck_companion.kwipi_journal",
            str(self.path),"--at",str(NOW+2),"--format","csv",
            "--category","ball","--limit","1",
        ]
        run=subprocess.run(cmd,capture_output=True,text=True,
            cwd=Path(__file__).resolve().parents[1],timeout=15)
        self.assertEqual(0,run.returncode,run.stderr)
        self.assertIn("mock_fixture_only",run.stdout)
        self.assertIn("causality_established",run.stdout)

    def test_cli_missing_database_does_not_create_it(self):
        nonexistent=self.path.with_name("missing.sqlite3")
        cmd=[
            sys.executable,"-m","microduck_companion.kwipi_journal",
            str(nonexistent),
        ]
        run=subprocess.run(cmd,capture_output=True,text=True,
            cwd=Path(__file__).resolve().parents[1],timeout=15)
        self.assertEqual(2,run.returncode)
        self.assertEqual("",run.stdout)
        self.assertFalse(nonexistent.exists())


if __name__ == "__main__":
    unittest.main()
