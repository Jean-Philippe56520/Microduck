"""EX3: conservative, reversible, read-derived MOCK attention trends.

No real-world cause is inferred. The EX3 optional link only re-ranks F2
non-motor intentions and never modifies the OEM motor/stop safety envelope.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain, Motivations, Scene
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_ledger import (
    MockExperienceLedger, MockResolution, RETENTION_S,
)
from microduck_companion.experience_effects import (
    MockCue, MockEffectJournal, MockEffectPair,
)
from microduck_companion.experience_expectations import (
    MockAttentionTrends, compute_mock_attention_trend,
    MIN_DISTINCT_SESSIONS, MAX_ATTENTION_BIAS,
)
from microduck_companion.kwipi_journal import (
    read_attention_trend, render_attention_trend, read_journal,
)
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot

WALL = 1_770_000_000.0


def passive_receipt(*, category="ball", kind="object_label", seq=3, mono=100.):
    event = PerceptionEvent(
        kind, category, "mock", mono, 1.0, .96,
        track_id=("mock-t1" if kind == "object_label" else None),
    )
    return PassiveRead(
        "ok", PerceptionSnapshot("mock", (event,), mono),
        seq, "mock_fixture_unix",
    )


class EX3MockAttentionTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "experience.sqlite3"
        self.memory = ExperienceMemory(self.path)
        self.addCleanup(self.memory.close)
        self.ex1 = MockExperienceLedger(self.memory)
        self.ex2 = MockEffectJournal(self.ex1)
        self.trends = MockAttentionTrends(self.ex2)

    def fixture(self, session_num, *, category="ball", kind="motion",
                before="still", after="moving", seq=1,
                intent="observe", start=None, competing=False,
                confidence=.95, same_scene=True):
        session = "s-" + format(session_num, "016x")
        when = WALL + 10 * session_num if start is None else start
        target_kind = "sound_label" if intent == "listen" else "object_label"
        intent_data = PassiveIntent(
            intent, "scripted test", target_kind, category,
        )
        self.ex1.record_proposal(
            intent_data, session=session, sequence=seq,
            proposed_at_epoch_s=when,
        )
        self.ex1.resolve(MockResolution(
            session, seq, "mock_executed", when + 1,
        ))
        pair = MockEffectPair(
            session, seq,
            MockCue(kind, before, when - .5, confidence),
            MockCue(kind, after, when + 1.3, confidence),
            same_scene, competing,
        )
        self.ex2.record(pair)
        return session, seq

    def summary(self, *, category="ball", intent="observe", now=WALL+150):
        return self.trends.summary(
            intention=intent, category=category, now_wall_epoch_s=now,
        )

    def test_empty_and_one_session_cannot_change_attention(self):
        first = self.summary()
        self.assertEqual((0, 0.0, "insufficient_mock_sessions"),
                         (first.distinct_mock_sessions, first.attention_bias,
                          first.status))
        self.fixture(1)
        hint = self.summary()
        self.assertEqual((1, 1, 0, 0.0),
                         (hint.distinct_mock_sessions, hint.changed,
                          hint.unchanged, hint.attention_bias))
        self.assertFalse(hint.causality_established)
        self.assertFalse(hint.verified_on_robot)
        self.assertEqual(0, hint.motor_commands_issued)

    def test_repeated_distinct_mock_sessions_add_only_tiny_mock_bias(self):
        for s in range(1, MIN_DISTINCT_SESSIONS + 1):
            self.fixture(s)
        hint = self.summary()
        self.assertEqual(3, hint.distinct_mock_sessions)
        self.assertEqual(3, hint.changed)
        self.assertEqual(.03, hint.attention_bias)
        self.assertLessEqual(abs(hint.attention_bias), MAX_ATTENTION_BIAS)
        self.assertEqual("repeated_temporal_mock_pattern", hint.status)
        self.assertEqual("mock_fixture_only", hint.source)
        self.assertEqual(0, self.memory.experience_count())
        self.assertEqual(0.0, self.memory.intent_preference("simulator", "explore"))

    def test_repeated_single_session_counts_at_most_once(self):
        for seq in range(1, 9):
            self.fixture(1, seq=seq, start=WALL+10+seq*.1)
        hint = self.summary()
        self.assertEqual((1, 0.0), (hint.distinct_mock_sessions, hint.attention_bias))

    def test_contradictions_can_cancel_tendency(self):
        for n in range(1, 4):
            self.fixture(n)
        for n in range(4, 7):
            self.fixture(n, after="still")
        hint = self.summary()
        self.assertEqual((3, 3, 0.), (hint.changed, hint.unchanged,
                                      hint.attention_bias))
        self.assertEqual("balanced_mock_pattern", hint.status)

    def test_retractions_recompute_without_second_sqlite_writer(self):
        sessions = [self.fixture(n) for n in (1, 2, 3)]
        self.assertGreater(self.summary().attention_bias, 0)
        self.assertTrue(self.ex2.retract(
            session=sessions[0][0], sequence=1,
            reason="source_retracted"))
        self.assertEqual(0., self.summary().attention_bias)
        self.assertEqual(2, self.summary().distinct_mock_sessions)
        self.assertTrue(self.ex1.retract(
            session=sessions[1][0], sequence=1,
            reason="fixture_annotation_error"))
        self.assertEqual(1, self.summary().distinct_mock_sessions)

    def test_parent_retraction_also_removes_trend(self):
        for n in (1, 2, 3):
            self.fixture(n)
        self.ex1.retract(
            session="s-"+format(2, "016x"), sequence=1,
            reason="source_retracted",
        )
        self.assertEqual(0., self.summary().attention_bias)

    def test_social_after_action_is_not_a_reward(self):
        for n in (1, 2, 3, 4):
            self.fixture(n, category="person", kind="social",
                         before="no_signal", after="friendly_signal")
        hint = self.summary(category="person")
        self.assertEqual(0, hint.distinct_mock_sessions)
        self.assertEqual(0., hint.attention_bias)
        self.assertEqual(0, self.memory.experience_count())

    def test_confounded_and_weak_or_broken_evidence_does_not_train(self):
        self.fixture(1, competing=True)
        self.fixture(2, confidence=.7)
        self.fixture(3, same_scene=False)
        hint = self.summary()
        self.assertEqual((0, 0.), (hint.distinct_mock_sessions,
                                   hint.attention_bias))

    def test_categories_and_sound_are_separate(self):
        for n in (1, 2, 3):
            self.fixture(n, category="ball")
            self.fixture(n+10, category="bark", intent="listen",
                         kind="sound", before="quiet", after="heard")
        self.assertEqual(3, self.summary(category="ball").changed)
        self.assertEqual(3, self.summary(category="bark", intent="listen").changed)
        self.assertEqual(0, self.summary(category="dog").changed)

    def test_unsupported_unknown_identity_action_and_time_fail(self):
        for args in (
            {"intention":"kick","category":"ball"},
            {"intention":"inspect","category":"ball"},
            {"intention":"observe","category":"unknown"},
            {"intention":"observe","category":"Malo"},
            {"intention":"listen","category":"ball"},
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                compute_mock_attention_trend(
                    self.memory.conn, now_wall_epoch_s=WALL+100, **args)
        for t in (True, -1, float("nan"), float("inf")):
            with self.subTest(t=t), self.assertRaises(ValueError):
                self.summary(now=t)
        with self.assertRaises(TypeError):
            compute_mock_attention_trend("not SQLite", intention="observe",
                    category="ball",now_wall_epoch_s=WALL)
        with self.assertRaises(TypeError):
            MockAttentionTrends(self.ex1)

    def test_tampered_fake_causality_in_db_does_not_qualify(self):
        sessions = [self.fixture(n) for n in (1, 2, 3)]
        self.assertEqual(.03, self.summary().attention_bias)
        self.memory.conn.execute("""
           UPDATE ex2_mock_effects SET association_status='confounded'
           WHERE ex1_id IN (
             SELECT id FROM ex1_mock_experiences WHERE session=?
           )
        """, (sessions[0][0],))
        self.memory.conn.commit()
        self.assertEqual(0., self.summary().attention_bias)

    def test_retention_window_removes_old_fixtures_from_recall(self):
        for n in (1, 2, 3):
            self.fixture(n)
        self.assertEqual(.03, self.summary().attention_bias)
        hint = self.summary(now=WALL+RETENTION_S+1000)
        self.assertEqual((0, 0.), (hint.distinct_mock_sessions,
                                   hint.attention_bias))

    def test_repeated_events_saturate_small_scoring_envelope(self):
        for n in range(1, 12):
            self.fixture(n)
        self.assertEqual(MAX_ATTENTION_BIAS,
                         self.summary().attention_bias)

    def test_restarting_process_keeps_fictional_history_and_correction(self):
        for n in (1, 2, 3):
            self.fixture(n)
        other = ExperienceMemory(self.path)
        try:
            other_ex3 = MockAttentionTrends(
                MockEffectJournal(MockExperienceLedger(other)))
            self.assertEqual(.03, other_ex3.bias_for(
                intention="observe", category="ball",
                now_wall_epoch_s=WALL+150,
            ))
        finally:
            other.close()

    def test_opt_in_changes_only_mock_familiar_passive_proposal(self):
        for n in (1, 2, 3):
            self.fixture(n)
        journal = PassiveObservationJournal(self.memory)
        familiar = passive_receipt(seq=1)
        self.assertGreater(journal.append(
            familiar, now_monotonic_s=100.1,
            now_wall_epoch_s=WALL+45,
        ), 0)
        self.assertGreater(journal.category_count(
            "object_label","ball",now_wall_epoch_s=WALL+150), 0)
        def brain():
            return AutonomyBrain(
                self.memory, Motivations(
                    curiosity=.75, sociability=.55,
                    play=.6, energy=.8, caution=.35,
                ),
            )
        without = brain().propose_balanced_passive(
            passive_receipt(seq=2), journal=journal,
            now_monotonic_s=100.1, now_wall_epoch_s=WALL+150,
        )
        with_hint = brain().propose_balanced_passive(
            passive_receipt(seq=2), journal=journal,
            now_monotonic_s=100.1, now_wall_epoch_s=WALL+150,
            expectations=self.trends,
        )
        self.assertEqual("idle", without.intention)
        self.assertEqual(("observe","ball","repeated_temporal_mock_attention"),
                         (with_hint.intention, with_hint.target_category,
                          with_hint.reason))
        self.assertFalse(with_hint.executed)
        self.assertEqual(0, with_hint.motor_commands_issued)
        self.assertFalse(with_hint.request_pc_analysis)
        self.assertEqual("halt", brain().choose(Scene()).intention)

    def test_opt_in_is_reversible_on_retraction_and_abstention(self):
        sessions=[self.fixture(n) for n in (1, 2, 3)]
        journal = PassiveObservationJournal(self.memory)
        journal.append(passive_receipt(seq=1),now_monotonic_s=100.1,
                       now_wall_epoch_s=WALL+40)
        def decision():
            return AutonomyBrain(self.memory).propose_balanced_passive(
                passive_receipt(seq=2), journal=journal,
                now_monotonic_s=100.1, now_wall_epoch_s=WALL+150,
                expectations=self.trends,
            )
        self.assertEqual("observe", decision().intention)
        self.ex2.retract(session=sessions[0][0], sequence=1,
                         reason="source_retracted")
        self.assertEqual("idle", decision().intention)

    def test_unauthorized_different_memory_and_wrong_adapters_refused(self):
        other = ExperienceMemory()
        self.addCleanup(other.close)
        foreign = MockAttentionTrends(MockEffectJournal(MockExperienceLedger(other)))
        brain = AutonomyBrain(self.memory)
        journal = PassiveObservationJournal(self.memory)
        with self.assertRaises(ValueError):
            brain.propose_balanced_passive(
                passive_receipt(), journal=journal,
                now_monotonic_s=100.1, now_wall_epoch_s=WALL,
                expectations=foreign,
            )
        with self.assertRaises(TypeError):
            brain.propose_balanced_passive(
                passive_receipt(), journal=journal,
                now_monotonic_s=100.1, now_wall_epoch_s=WALL,
                expectations="pretend verified",
            )

    def test_missing_ex2_table_never_generates_fake_results(self):
        # We can deliberately simulate a deployment containing EX1 only.
        self.memory.conn.execute("DROP TABLE ex2_mock_effects")
        self.memory.conn.commit()
        with self.assertRaises(sqlite3.Error):
            self.summary()

    def test_read_only_on_demand_cli_produces_a_provenance_aware_hint(self):
        for n in (1, 2, 3):
            self.fixture(n)
        before = self.path.read_bytes()
        hint = read_attention_trend(
            self.path, intention="observe", category="ball",
            now_wall_epoch_s=WALL+150,
        )
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(.03, hint["attention_bias"])
        self.assertFalse(hint["causality_established"])
        self.assertFalse(hint["verified_on_robot"])
        self.assertEqual(0, hint["motor_commands_issued"])
        output = render_attention_trend(hint, format="csv")
        self.assertIn("mock_fixture_only", output)
        jsonl = render_attention_trend(hint)
        self.assertEqual(.03, json.loads(jsonl)["attention_bias"])
        self.assertEqual(3, hint["distinct_mock_sessions"])
        result = subprocess.run([
            sys.executable,"-m","microduck_companion.kwipi_journal",
            str(self.path),"--trend","observe","--category","ball",
            "--at",str(WALL+150),
        ],capture_output=True,text=True,
            cwd=Path(__file__).resolve().parents[1],timeout=20)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(.03, json.loads(result.stdout)["attention_bias"])
        self.assertEqual((),read_journal(self.path,
            now_wall_epoch_s=WALL+RETENTION_S+5000))

    def test_reader_fails_without_ex2_and_on_bad_inputs(self):
        empty = self.path.with_name("other.sqlite3")
        empty.touch()
        with self.assertRaises(ValueError):
            read_attention_trend(empty, intention="observe",
                    category="ball",now_wall_epoch_s=WALL)
        with self.assertRaises(ValueError):
            read_attention_trend(self.path, intention="observe",
                    category="unknown",now_wall_epoch_s=WALL)
        with self.assertRaises(ValueError):
            render_attention_trend({}, format="pdf")
        with self.assertRaises(FileNotFoundError):
            read_attention_trend(self.path.with_name("missing.sqlite3"),
                    intention="observe",category="ball",
                    now_wall_epoch_s=WALL)


if __name__ == "__main__":
    unittest.main()
