"""EX3: conservative, reversible MOCK-only attention trends; no causal claims."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from microduck_companion import AutonomyBrain, ExperienceMemory
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot
from microduck_companion.experience_ledger import MockExperienceLedger, MockResolution
from microduck_companion.experience_effects import (
    MockCue, MockEffectPair, MockEffectJournal,
)
from microduck_companion.experience_expectations import (
    BIAS_STEP, MAX_ATTENTION_BIAS, MockAttentionTrends,
    compute_mock_attention_trend,
)
from microduck_companion.kwipi_journal import (
    read_attention_trend, render_attention_trend,
)

NOW = 1_770_000_000.


def session_id(index: int) -> str:
    return f"s-{index:016x}"


def frame(category: str = "ball", *, sequence: int = 1,
          mono: float = 100., source: str = "mock",
          channel: str = "mock_fixture_unix") -> PassiveRead:
    kind = "sound_label" if category in {"bark", "meow", "knock"} else "object_label"
    event = PerceptionEvent(
        kind, category, source, mono, 1.0, .96,
        track_id="synthetic-track" if kind == "object_label" else None,
    )
    return PassiveRead(
        "ok", PerceptionSnapshot("mock", (event,), mono),
        sequence, channel,
    )


class EX3ExpectationTests(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "experience.sqlite3"
        self.mem = ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.ex1 = MockExperienceLedger(self.mem)
        self.ex2 = MockEffectJournal(self.ex1)
        self.trends = MockAttentionTrends(self.ex2)

    def add(self, index: int, *, category="ball", intention="observe",
            before="still", after="moving", cue_kind="motion",
            resolution="mock_executed", same_scene=True, competing=False,
            confidence=.95, when=None, sequence=1):
        t = NOW + index * 10 if when is None else when
        sid = session_id(index)
        kind = "sound_label" if intention == "listen" else "object_label"
        self.assertTrue(self.ex1.record_proposal(
            PassiveIntent(intention, "synthetic-only", kind, category),
            session=sid, sequence=sequence, proposed_at_epoch_s=t,
        ))
        if resolution is not None:
            self.assertTrue(self.ex1.resolve(
                MockResolution(sid, sequence, resolution, t+1),
            ))
        if resolution == "mock_executed":
            return self.ex2.record(MockEffectPair(
                sid, sequence,
                MockCue(cue_kind, before, t-.5, confidence),
                MockCue(cue_kind, after, t+1.2, confidence),
                same_scene, competing,
            ))
        return False

    def trend(self, *, intention="observe", category="ball", at=NOW+200):
        return self.trends.summary(
            intention=intention, category=category,
            now_wall_epoch_s=at,
        )

    def familiar_brain(self, *, category="ball", at=NOW+200):
        # F1-C's mock category history makes it familiar, so F2 does not
        # simply choose a novel object and misattribute it to EX3.
        journal = PassiveObservationJournal(self.mem)
        read = frame(category)
        self.assertEqual(1, journal.append(
            read, now_monotonic_s=100.1, now_wall_epoch_s=at-1,
        ))
        return journal, read

    def test_no_effects_yield_zero_and_no_new_ex3_table(self):
        trend = self.trend()
        self.assertEqual((0, 0, 0, 0.0),
                         (trend.distinct_mock_sessions, trend.changed,
                          trend.unchanged, trend.attention_bias))
        self.assertEqual("insufficient_mock_sessions", trend.status)
        self.assertFalse(trend.causality_established)
        self.assertFalse(trend.verified_on_robot)
        self.assertEqual(0, trend.motor_commands_issued)
        self.assertFalse(any(
            x[0].startswith("ex3") for x in self.mem.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        ))

    def test_three_distinct_mock_sessions_give_small_reversible_hint(self):
        for i in (1, 2, 3):
            self.add(i)
        trend = self.trend()
        self.assertEqual((3,3,0), (trend.distinct_mock_sessions,
                                  trend.changed, trend.unchanged))
        self.assertAlmostEqual(3*BIAS_STEP, trend.attention_bias)
        self.assertEqual("repeated_temporal_mock_pattern", trend.status)
        self.assertFalse(trend.causality_established)
        self.assertEqual("mock_fixture_only", trend.source)
        self.assertTrue(self.ex2.retract(
            session=session_id(1), sequence=1, reason="source_retracted",
        ))
        after = self.trend()
        self.assertEqual(2, after.distinct_mock_sessions)
        self.assertEqual(0., after.attention_bias)

    def test_one_session_with_three_sequences_does_not_prove_repetition(self):
        self.add(7)
        # Intentionally replay another sequence in the same synthetic session.
        for seq, t in ((2, NOW+75), (3, NOW+78)):
            sid = session_id(7)
            self.ex1.record_proposal(
                PassiveIntent("observe","synthetic","object_label","ball"),
                session=sid,sequence=seq,proposed_at_epoch_s=t)
            self.ex1.resolve(MockResolution(sid,seq,"mock_executed",t+1))
            self.ex2.record(MockEffectPair(
                sid,seq,MockCue("motion","still",t-.5,.95),
                MockCue("motion","moving",t+1.2,.95),True,False))
        outcome = self.trend()
        self.assertEqual(1, outcome.distinct_mock_sessions)
        self.assertEqual(0., outcome.attention_bias)

    def test_only_temporal_fixtures_count_not_actual_causality(self):
        self.add(1, competing=True)
        self.add(2, same_scene=False)
        self.add(3, confidence=.5)
        self.add(4, category="unknown")
        self.add(5, resolution="refused")
        self.add(6, resolution="interrupted")
        self.add(7, resolution=None)
        trend = self.trend()
        self.assertEqual(0, trend.distinct_mock_sessions)
        self.assertEqual(0., trend.attention_bias)

    def test_social_signal_is_never_reward_or_trend(self):
        for i in (1,2,3,4):
            self.add(i, before="no_signal",after="friendly_signal",
                     cue_kind="social")
        trend = self.trend()
        self.assertEqual(0,trend.distinct_mock_sessions)
        self.assertEqual(0.,trend.attention_bias)
        self.assertEqual(0,self.mem.experience_count())
        self.assertEqual(0.,self.mem.intent_preference("robot","explore"))

    def test_contradictions_cancel_instead_of_hardcoding_preference(self):
        for i in (1,2,3):
            self.add(i)
        for i in (4,5,6):
            self.add(i,before="still",after="still")
        trend=self.trend()
        self.assertEqual((3,3), (trend.changed,trend.unchanged))
        self.assertEqual(0.,trend.attention_bias)
        self.assertEqual("balanced_mock_pattern",trend.status)
        self.assertTrue(self.ex1.retract(
            session=session_id(1),sequence=1,
            reason="fixture_annotation_error"))
        trend2=self.trend()
        self.assertEqual((2,3), (trend2.changed,trend2.unchanged))
        self.assertAlmostEqual(-BIAS_STEP,trend2.attention_bias)

    def test_unchanged_mock_effects_mean_less_interest_not_negative_reward(self):
        for i in (1,2,3,4):
            self.add(i,before="still",after="still")
        t=self.trend()
        self.assertEqual(0,t.changed)
        self.assertEqual(4,t.unchanged)
        self.assertEqual(-MAX_ATTENTION_BIAS,t.attention_bias)
        self.assertEqual(0,self.mem.experience_count())

    def test_bias_is_bounded_even_with_many_sessions(self):
        for i in range(1,18):
            self.add(i)
        self.assertEqual(MAX_ATTENTION_BIAS,self.trend().attention_bias)
        self.assertLessEqual(self.trend().distinct_mock_sessions,32)

    def test_expiration_and_category_change_remove_signal(self):
        for i in (1,2,3):
            self.add(i)
        self.assertGreater(self.trend().attention_bias,0)
        self.assertEqual(0,self.trend(category="cat").distinct_mock_sessions)
        self.assertEqual(0,self.trend(at=NOW+14*86400+300).distinct_mock_sessions)

    def test_sound_cues_can_propose_listen_but_unrelated_cues_do_not(self):
        for i in (1,2,3):
            self.add(i,category="bark",intention="listen",
                     before="quiet",after="heard",cue_kind="sound")
        good=self.trend(intention="listen",category="bark")
        self.assertEqual(3,good.changed)
        self.assertGreater(good.attention_bias,0)
        self.assertEqual(0.,self.trend().attention_bias)

    def test_unknown_intention_category_and_bad_clock_rejected(self):
        for args in (
            {"intention":"kick","category":"ball"},
            {"intention":"observe","category":"unknown"},
            {"intention":"listen","category":"ball"},
            {"intention":"observe","category":"Malo"},
        ):
            with self.subTest(args=args),self.assertRaises(ValueError):
                self.trend(**args)
        for t in (True, float("nan"), -1, "NOW"):
            with self.subTest(time=t),self.assertRaises(ValueError):
                self.trend(at=t)
        with self.assertRaises(TypeError):
            compute_mock_attention_trend(
                "not-a-db", intention="observe",category="ball",
                now_wall_epoch_s=NOW+200)

    def test_cross_process_persistence_and_on_demand_query_no_writes(self):
        for i in (1,2,3):
            self.add(i)
        expected = self.trend().attention_bias
        second=ExperienceMemory(self.path)
        try:
            second_ex1=MockExperienceLedger(second)
            second_ex2=MockEffectJournal(second_ex1)
            found=MockAttentionTrends(second_ex2).summary(
                intention="observe",category="ball",
                now_wall_epoch_s=NOW+200)
            self.assertEqual(expected,found.attention_bias)
        finally:
            second.close()
        original=self.path.read_bytes()
        view=read_attention_trend(self.path,intention="observe",
                                  category="ball",now_wall_epoch_s=NOW+200)
        self.assertEqual(expected,view["attention_bias"])
        self.assertEqual(original,self.path.read_bytes())
        out=render_attention_trend(view,format="jsonl")
        self.assertFalse(json.loads(out)["causality_established"])
        self.assertNotIn("synthetic-only",out)
        csv=render_attention_trend(view,format="csv")
        self.assertIn("distinct_mock_sessions",csv)
        self.assertNotIn("synthetic-only",csv)

    def test_missing_db_and_broken_schema_fail_closed(self):
        absent=self.path.with_name("missing.sqlite3")
        with self.assertRaises(FileNotFoundError):
            read_attention_trend(absent,intention="observe",
                category="ball",now_wall_epoch_s=NOW)
        self.assertFalse(absent.exists())
        invalid=self.path.with_name("incompatible.sqlite3")
        con=sqlite3.connect(invalid)
        con.execute("CREATE TABLE fake (id INTEGER)")
        con.close()
        with self.assertRaises(ValueError):
            read_attention_trend(invalid,intention="observe",
                category="ball",now_wall_epoch_s=NOW)
        with self.assertRaises(ValueError):
            render_attention_trend({},format="html")

    def test_cli_trend_json_and_csv_without_daemons_or_network(self):
        for i in (1,2,3):
            self.add(i)
        cmd=[sys.executable,"-m","microduck_companion.kwipi_journal",
             str(self.path),"--at",str(NOW+200),
             "--trend","observe","--category","ball"]
        for extra in ([],["--format","csv"]):
            proc=subprocess.run(cmd+extra,text=True,capture_output=True,
                    cwd=Path(__file__).resolve().parents[1],timeout=20)
            self.assertEqual(0,proc.returncode,proc.stderr)
            self.assertIn("mock_fixture_only",proc.stdout)
            self.assertIn("causality_established",proc.stdout)
        without_category=subprocess.run(
            cmd[:-2],text=True,capture_output=True,
            cwd=Path(__file__).resolve().parents[1],timeout=20)
        self.assertEqual(2,without_category.returncode)
        self.assertEqual("",without_category.stdout)

    def test_optional_passive_brain_reproposes_familiar_category_only_with_hint(self):
        for i in (1,2,3):
            self.add(i)
        journal, reading=self.familiar_brain()
        nohint=AutonomyBrain(self.mem)
        b0=nohint.propose_balanced_passive(
            reading,journal=journal,
            now_monotonic_s=100.1,now_wall_epoch_s=NOW+200)
        withhint=AutonomyBrain(self.mem)
        b1=withhint.propose_balanced_passive(
            reading,journal=journal,expectations=self.trends,
            now_monotonic_s=100.1,now_wall_epoch_s=NOW+200)
        self.assertEqual("idle",b0.intention)
        self.assertEqual(("observe","ball"),(b1.intention,b1.target_category))
        self.assertFalse(b1.executed)
        self.assertEqual(0,b1.motor_commands_issued)
        self.assertFalse(b1.request_pc_analysis)
        # A correction makes even the next independent brain choose idle.
        self.ex2.retract(session=session_id(1),sequence=1,
                         reason="source_retracted")
        undone=AutonomyBrain(self.mem).propose_balanced_passive(
            reading,journal=journal,expectations=self.trends,
            now_monotonic_s=100.1,now_wall_epoch_s=NOW+200)
        self.assertEqual("idle",undone.intention)

    def test_wrong_memory_or_untrusted_channel_not_rescued_by_trend(self):
        for i in (1,2,3):
            self.add(i)
        journal, reading=self.familiar_brain()
        other=ExperienceMemory()
        self.addCleanup(other.close)
        wrong=MockAttentionTrends(MockEffectJournal(MockExperienceLedger(other)))
        with self.assertRaises(ValueError):
            AutonomyBrain(self.mem).propose_balanced_passive(
                reading,journal=journal,expectations=wrong,
                now_monotonic_s=100.1,now_wall_epoch_s=NOW+200)
        with self.assertRaises(TypeError):
            AutonomyBrain(self.mem).propose_balanced_passive(
                reading,journal=journal,expectations=object(),
                now_monotonic_s=100.1,now_wall_epoch_s=NOW+200)
        unsafe=frame(source="sensor")
        withhint=AutonomyBrain(self.mem).propose_balanced_passive(
            unsafe,journal=journal,expectations=self.trends,
            now_monotonic_s=100.1,now_wall_epoch_s=NOW+200)
        self.assertEqual("idle",withhint.intention)
        self.assertEqual(0,self.mem.experience_count())
        self.assertEqual(0.,self.mem.intent_preference("robot","explore"))


if __name__ == "__main__":
    unittest.main()
