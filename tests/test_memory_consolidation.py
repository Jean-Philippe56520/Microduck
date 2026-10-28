"""C1: bounded conservative recall on synthetic F1-C/F2-C/F4-A evidence only."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from microduck_companion.category_semantics import CategorySemantics, RETENTION_S
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.memory_consolidation import recall_category
from microduck_companion.passive_learning import PassiveLearning
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot

WALL = 1_770_000_000.0


class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "one-memory.sqlite3"
        self.mem = ExperienceMemory(self.path)
        self.addCleanup(lambda: self.mem.close() if self.mem else None)
        self.journal = PassiveObservationJournal(self.mem)
        self.learning = PassiveLearning(self.mem)
        self.semantic = CategorySemantics(self.mem)

    def record(self, category="ball", *, seq=1, mono=100.0, wall=WALL,
               kind="object_label", confidence=.96, journal=None):
        journal = self.journal if journal is None else journal
        ev = PerceptionEvent(
            kind, category, "mock", mono, 1., confidence,
            track_id="ephemeral-mock" if kind == "object_label" else None)
        reading = PassiveRead(
            "ok", PerceptionSnapshot("mock", (ev,), mono), seq,
            "mock_fixture_unix")
        count = journal.append(
            reading, now_monotonic_s=mono+.1, now_wall_epoch_s=wall)
        self.assertEqual(1, count)
        learned = self.learning.record(
            journal=journal, sequence=seq, now_wall_epoch_s=wall)
        self.assertEqual(1, len(learned))
        return learned[0].observation_id

    def remember(self, sid, *, wall=WALL, journal=None):
        return self.semantic.remember(
            journal=self.journal if journal is None else journal,
            learning=self.learning, observation_id=sid, now_wall_epoch_s=wall)

    def test_unknown_category_is_not_a_known_object(self):
        r = recall_category(self.semantic, category="ball",
                            now_wall_epoch_s=WALL)
        self.assertEqual("unknown", r.status)
        self.assertEqual((), r.evidence)
        self.assertEqual((), r.property_hypotheses)
        self.assertEqual(0, r.verified_real_observations)
        self.assertEqual(0, r.causal_effects_verified)
        self.assertFalse(r.physical_actions_authorized)
        self.assertEqual(0, r.memory_writes)

    def test_repeated_frames_and_separate_mock_sessions_are_not_independent_scenes(self):
        a = self.record("dog", seq=1, mono=100, wall=WALL)
        b = self.record("dog", seq=2, mono=101, wall=WALL+1)
        other_journal = PassiveObservationJournal(self.mem)
        c = self.record("dog", seq=1, mono=10, wall=WALL+2,
                        journal=other_journal)
        self.assertTrue(self.remember(a))
        self.assertTrue(self.remember(b, wall=WALL+1))
        self.assertTrue(self.remember(c, wall=WALL+2,
                                      journal=other_journal))
        before = self.mem.conn.total_changes
        result = recall_category(
            self.semantic, category="dog", now_wall_epoch_s=WALL+2)
        self.assertEqual(before, self.mem.conn.total_changes)
        self.assertEqual("historical_mock_only", result.status)
        (e,) = result.evidence
        self.assertEqual("visual_label", e.modality)
        self.assertEqual(3, e.observation_count)
        self.assertEqual(2, e.fixture_session_count)
        self.assertEqual(0, e.independent_scenes_verified)
        self.assertFalse(e.real_sensor_verified)
        self.assertEqual(WALL+2, e.most_recent_epoch_s)
        self.assertEqual(.96, e.minimum_reported_confidence)
        self.assertEqual(.96, e.maximum_reported_confidence)
        self.assertNotIn("ephemeral-mock", repr(result))
        self.assertFalse(result.physical_actions_authorized)

    def test_source_or_learning_retraction_and_f4_correction_update_next_recall(self):
        a = self.record("ball", seq=1, mono=100, wall=WALL)
        b = self.record("ball", seq=2, mono=101, wall=WALL+1)
        self.assertTrue(self.remember(a))
        self.assertTrue(self.remember(b, wall=WALL+1))
        self.assertEqual(2, recall_category(
            self.semantic, category="ball",
            now_wall_epoch_s=WALL+2).evidence[0].observation_count)
        self.assertTrue(self.learning.retract(
            a, reason="source_retracted"))
        self.assertEqual(1, recall_category(
            self.semantic, category="ball",
            now_wall_epoch_s=WALL+2).evidence[0].observation_count)
        self.assertTrue(self.semantic.forget_observation(
            b, reason="fixture_annotation_error"))
        self.assertEqual("unknown", recall_category(
            self.semantic, category="ball",
            now_wall_epoch_s=WALL+2).status)
        self.assertFalse(self.remember(b, wall=WALL+2))

    def test_mutated_source_confidence_category_and_time_are_rejected(self):
        sid = self.record("cat")
        self.assertTrue(self.remember(sid))
        variations = (
            ("category", "dog"),
            ("confidence", .80),
            ("recorded_epoch_s", WALL-4),
            ("status", "unknown"),
        )
        for column, value in variations:
            with self.subTest(field=column):
                with self.mem.conn:
                    self.mem.conn.execute(
                        f"UPDATE passive_observation_log SET {column}=? WHERE id=?",
                        (value, sid))
                self.assertEqual("unknown", recall_category(
                    self.semantic, category="cat",
                    now_wall_epoch_s=WALL).status)
                with self.mem.conn:
                    self.mem.conn.execute(
                        f"UPDATE passive_observation_log "
                        f"SET category='cat', confidence=.96, "
                        f"recorded_epoch_s=?, status='identified' WHERE id=?",
                        (WALL, sid))
        self.assertEqual("historical_mock_only", recall_category(
            self.semantic, category="cat",
            now_wall_epoch_s=WALL).status)

    def test_low_confidence_unknown_and_expired_evidence_are_excluded(self):
        unknown = self.record("unknown", seq=1)
        self.assertFalse(self.remember(unknown))
        low = self.record("cat", seq=2, mono=101, wall=WALL+1,
                          confidence=.20)
        self.assertFalse(self.remember(low, wall=WALL+1))
        sid = self.record("cat", seq=3, mono=102, wall=WALL+2)
        self.assertTrue(self.remember(sid, wall=WALL+2))
        self.assertEqual("unknown", recall_category(
            self.semantic, category="cat",
            now_wall_epoch_s=WALL+2+RETENTION_S+1).status)
        self.assertEqual("unknown", recall_category(
            self.semantic, category="cat", now_wall_epoch_s=WALL-1).status)

    def test_sound_and_visual_modalities_are_not_merged(self):
        sound = self.record("bark", kind="sound_label")
        self.assertTrue(self.remember(sound))
        result = recall_category(self.semantic, category="bark",
                                 now_wall_epoch_s=WALL)
        self.assertEqual("sound_label", result.evidence[0].modality)
        self.assertEqual(1, result.evidence[0].observation_count)
        self.assertEqual((), result.property_hypotheses)

    def test_unverified_properties_are_separate_and_conflicts_never_resolved_as_fact(self):
        ids = [
            self.semantic.hypothesize(
                category="dog", property="texture", value=value,
                confidence=.9 if value == "soft" else .8,
                now_wall_epoch_s=WALL)
            for value in ("soft", "hard", "unknown")
        ]
        self.assertTrue(all(type(v) is int for v in ids))
        result = recall_category(self.semantic, category="dog",
                                 now_wall_epoch_s=WALL)
        self.assertEqual("hypotheses_only", result.status)
        self.assertEqual((), result.evidence)
        self.assertEqual(("texture",), result.conflicting_hypothesis_properties)
        self.assertEqual(3, len(result.property_hypotheses))
        self.assertTrue(all(
            not h.confirmed and not h.can_authorize_actions
            and h.source == "fictional_llm_hypothesis_only"
            for h in result.property_hypotheses))
        self.assertTrue(self.semantic.retract_hypothesis(
            ids[1], reason="fixture_annotation_error"))
        after = recall_category(self.semantic, category="dog",
                                now_wall_epoch_s=WALL)
        self.assertEqual((), after.conflicting_hypothesis_properties)
        self.assertEqual(2, len(after.property_hypotheses))
        self.assertFalse(after.physical_actions_authorized)

    def test_restart_keeps_only_live_mock_sources_and_hypotheses(self):
        sid = self.record("ball")
        self.assertTrue(self.remember(sid))
        self.semantic.hypothesize(
            category="ball", property="movement", value="moving",
            confidence=.55, now_wall_epoch_s=WALL)
        self.mem.close()
        self.mem = None
        next_mem = ExperienceMemory(self.path)
        try:
            next_sem = CategorySemantics(next_mem)
            before = next_mem.conn.total_changes
            result = recall_category(next_sem, category="ball",
                                     now_wall_epoch_s=WALL+1)
            self.assertEqual(1, result.evidence[0].observation_count)
            self.assertEqual("moving", result.property_hypotheses[0].value)
            self.assertEqual(before, next_mem.conn.total_changes)
            # Any correction to the *existing* source immediately invalidates
            # the historic summary, including across a fresh process.
            with next_mem.conn:
                next_mem.conn.execute(
                    "UPDATE passive_learning_events SET active=0 "
                    "WHERE observation_id=?", (sid,))
            result2 = recall_category(next_sem, category="ball",
                                      now_wall_epoch_s=WALL+1)
            self.assertEqual((), result2.evidence)
            self.assertEqual("hypotheses_only", result2.status)
        finally:
            next_mem.close()

    def test_read_only_and_no_second_sqlite_or_signature_writer(self):
        tables_before = {
            row[0] for row in self.mem.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        total_before = self.mem.conn.total_changes
        for _ in range(3):
            recall_category(self.semantic, category="chair",
                            now_wall_epoch_s=WALL)
        tables_after = {
            row[0] for row in self.mem.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(tables_before, tables_after)
        self.assertEqual(total_before, self.mem.conn.total_changes)
        self.assertNotIn("m1b_groups", tables_after)
        self.assertNotIn("m1a_compact_patterns", tables_after)

    def test_invalid_inputs_and_closed_database_fail_closed(self):
        for category in ("person/name", "🤖", "not-a-category", None, 7, True):
            with self.subTest(category=category), self.assertRaises(ValueError):
                recall_category(self.semantic, category=category,
                                now_wall_epoch_s=WALL)
        for now in (True, -1, float("nan"), float("inf")):
            with self.subTest(now=now), self.assertRaises(ValueError):
                recall_category(self.semantic, category="dog",
                                now_wall_epoch_s=now)
        with self.assertRaises(TypeError):
            recall_category(self.mem, category="dog",
                            now_wall_epoch_s=WALL)
        self.mem.close()
        self.mem = None
        with self.assertRaises(sqlite3.Error):
            recall_category(self.semantic, category="dog",
                            now_wall_epoch_s=WALL)

    def test_over_budget_forged_rows_are_not_silently_truncated(self):
        # Bypass normal F4-A retention to model a corrupt historical store.
        # A partial summary could turn 257 rows into a deceptive count of 256.
        with self.mem.conn:
            for i in range(257):
                row = self.mem.conn.execute("""
                    INSERT INTO passive_observation_log(
                        session_id,sequence,ordinal,recorded_epoch_s,
                        observed_monotonic_s,kind,category,status,source,
                        confidence,channel)
                    VALUES (?,?,0,?,100,'object_label','ball',
                            'identified','mock',.96,'mock_fixture_unix')
                """, (f"fixture_{i}", i, WALL)).lastrowid
                self.mem.conn.execute("""
                    INSERT INTO passive_learning_events(observation_id,active,outcome)
                    VALUES (?,1,'new_information')
                """, (row,))
                self.mem.conn.execute("""
                    INSERT INTO f4a_semantic_categories(
                        observation_id,category,kind,reported_confidence,
                        recorded_epoch_s,source)
                    VALUES (?,'ball','object_label',.96,?,'mock_fixture_journal')
                """, (row,WALL))
        with self.assertRaisesRegex(ValueError, "cap exceeded"):
            recall_category(self.semantic, category="ball",
                            now_wall_epoch_s=WALL)


if __name__ == "__main__":
    unittest.main()
