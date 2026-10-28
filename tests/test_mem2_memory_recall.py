"""MEM-2: bounded read-only context, synthetic data only.

No image, network, model, motor or physical object is used. Equal F0 keys
are test declarations, NOT evidence of identity across real camera sessions.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import time
import unittest

from microduck_companion.category_semantics import CategorySemantics
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_ledger import MockExperienceLedger
from microduck_companion.memory_recall import recall_memory, MAX_RECALLED_GOALS
from microduck_companion.mock_goal_memory import MockGoalMemory
from microduck_companion.passive_learning import PassiveLearning
from microduck_companion.passive_memory import PassiveObservationJournal

OBJECT_A = "o-00000000000000a1"
OBJECT_B = "o-00000000000000b2"


class MEM2RecallTests(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.path = Path(scratch.name) / "single.sqlite3"
        self.mem = ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.journal = PassiveObservationJournal(self.mem)
        self.learning = PassiveLearning(self.mem)
        self.semantics = CategorySemantics(self.mem)
        self.ledger = MockExperienceLedger(self.mem)
        self.goals = MockGoalMemory(self.mem, self.ledger)
        self.now = time.time() + 5.0

    def recall(self, category="unknown", key=None, goals=None):
        return recall_memory(
            self.mem, self.semantics, category=category,
            now_wall_epoch_s=self.now, object_key=key, goals=goals,
        )

    def test_empty_history_never_means_real_detection(self):
        result = self.recall()
        self.assertEqual("unknown", result.category_history.status)
        self.assertIsNone(result.object_counter)
        self.assertTrue(result.unverified_context_only)
        self.assertFalse(result.same_physical_object_verified)
        self.assertEqual(0, result.independent_encounters_verified)
        self.assertEqual(0, result.qwen_requests)
        self.assertEqual(0, result.memory_writes)
        self.assertEqual(0, result.motor_commands_issued)

    def test_100_repeated_calls_update_one_declared_key_not_100_rows(self):
        for _ in range(100):
            self.mem.observe(OBJECT_A, "unknown", source="mock")
        before = self.mem.conn.total_changes
        result = self.recall(key=OBJECT_A)
        self.assertEqual(before, self.mem.conn.total_changes)
        self.assertEqual(100, result.object_counter.sightings)
        self.assertEqual("unknown", result.object_counter.label_claim)
        self.assertEqual(0, result.object_counter.independent_encounters_verified)
        self.assertFalse(result.object_counter.identity_verified)
        self.assertEqual(1, self.mem.conn.execute(
            "SELECT COUNT(*) FROM objects").fetchone()[0])

    def test_two_similar_fixtures_do_not_merge_without_same_key_proof(self):
        for _ in range(30):
            self.mem.observe(OBJECT_A, "unknown", source="mock")
            self.mem.observe(OBJECT_B, "unknown", source="mock")
        a = self.recall(key=OBJECT_A).object_counter
        b = self.recall(key=OBJECT_B).object_counter
        self.assertEqual(30, a.sightings)
        self.assertEqual(30, b.sightings)
        self.assertEqual(2, self.mem.conn.execute(
            "SELECT COUNT(*) FROM objects").fetchone()[0])
        self.assertFalse(self.recall(key=OBJECT_A).same_physical_object_verified)

    def test_f0_label_never_creates_category_history_or_verified_link(self):
        self.mem.observe(OBJECT_A, "cat", source="sensor")
        result = self.recall(category="cat", key=OBJECT_A)
        self.assertEqual("cat", result.object_counter.label_claim)
        self.assertEqual("sensor", result.object_counter.label_source)
        self.assertEqual("unknown", result.category_history.status)
        self.assertFalse(result.same_physical_object_verified)

    def test_unknown_free_text_label_is_not_exported(self):
        self.mem.observe(OBJECT_A, "private-person-name", source="mock")
        self.assertEqual("unknown", self.recall(key=OBJECT_A).object_counter.label_claim)

    def test_existing_c1_rechecks_sources_and_withdrawal_read_only(self):
        when = self.now - 2
        with self.mem.conn:
            row = self.mem.conn.execute("""
                INSERT INTO passive_observation_log(
                    session_id,sequence,ordinal,recorded_epoch_s,
                    observed_monotonic_s,kind,category,status,source,
                    confidence,channel)
                VALUES ('synthetic-session',1,0,?,10,'object_label',
                        'cat','identified','mock',0.9,'mock_fixture_unix')
            """, (when,))
            oid = row.lastrowid
            self.mem.conn.execute("""
                INSERT INTO passive_learning_events(observation_id,active,outcome)
                VALUES (?,1,'new_information')
            """, (oid,))
            self.mem.conn.execute("""
                INSERT INTO f4a_semantic_categories(
                    observation_id,category,kind,reported_confidence,
                    recorded_epoch_s,source,active)
                VALUES (?,'cat','object_label',0.9,?,'mock_fixture_journal',1)
            """, (oid, when))
        before = self.mem.conn.total_changes
        result = self.recall(category="cat")
        self.assertEqual(before, self.mem.conn.total_changes)
        self.assertEqual("historical_mock_only", result.category_history.status)
        self.assertEqual(1, result.category_history.evidence[0].observation_count)
        self.assertEqual(1, result.category_history.evidence[0].fixture_session_count)
        self.assertEqual(0, result.category_history.evidence[0].independent_scenes_verified)
        with self.mem.conn:
            self.mem.conn.execute(
                "UPDATE passive_learning_events SET active=0 WHERE observation_id=?",
                (oid,))
        self.assertEqual("unknown", self.recall(category="cat").category_history.status)

    def test_unverified_hypothesis_retracts_and_stays_withdrawn_on_reopen(self):
        hypid = self.semantics.hypothesize(
            category="cat", property="texture", value="soft",
            confidence=0.65, now_wall_epoch_s=self.now-1,
        )
        self.assertIsInstance(hypid, int)
        result = self.recall(category="cat")
        self.assertEqual("hypotheses_only", result.category_history.status)
        self.assertFalse(result.category_history.property_hypotheses[0].confirmed)
        self.assertTrue(self.semantics.retract_hypothesis(
            hypid, reason="fixture_annotation_error"))
        self.assertEqual((), self.recall(category="cat").category_history.property_hypotheses)
        with self.mem.conn:
            active = self.mem.conn.execute(
                "SELECT active FROM f4a_property_hypotheses WHERE id=?",
                (hypid,)).fetchone()[0]
        self.assertEqual(0, active)
        self.mem.close()
        other = ExperienceMemory(self.path)
        try:
            PassiveObservationJournal(other)
            PassiveLearning(other)
            again = CategorySemantics(other)
            result = recall_memory(other, again, category="cat", now_wall_epoch_s=self.now)
            self.assertEqual((), result.category_history.property_hypotheses)
        finally:
            other.close()

    def test_optional_goals_are_unverified_category_scoped_not_object_linked(self):
        self.goals.create(goal_id="g-0000000000000001", kind="inspect_unknown",
                          category="unknown", resume_when="new_view",
                          at_epoch_s=self.now-10)
        self.mem.observe(OBJECT_A, "unknown", source="mock")
        result = self.recall(key=OBJECT_A, goals=self.goals)
        self.assertEqual(1, len(result.category_goals))
        goal = result.category_goals[0]
        self.assertEqual("candidate", goal.state)
        self.assertEqual(0, goal.linked_attempts)
        self.assertFalse(goal.physical_completion_verified)
        self.assertFalse(result.same_physical_object_verified)
        self.assertTrue(self.goals.retract(
            goal_id=goal.goal_ref, reason="source_retracted"))
        self.assertEqual((), self.recall(goals=self.goals).category_goals)

    def test_goal_bound_explicit_truncation_and_no_duplicate_rows(self):
        for i in range(MAX_RECALLED_GOALS + 1):
            self.goals.create(
                goal_id=f"g-{i+1:016x}", kind="inspect_unknown",
                category="unknown", resume_when="new_view",
                at_epoch_s=self.now - 20,
            )
        before = self.mem.conn.total_changes
        snapshot = self.recall(goals=self.goals)
        self.assertEqual(before, self.mem.conn.total_changes)
        self.assertEqual(MAX_RECALLED_GOALS, len(snapshot.category_goals))
        self.assertTrue(snapshot.goals_truncated)
        self.assertEqual(snapshot, self.recall(goals=self.goals))

    def test_invalid_keys_time_category_and_wrong_database_refused(self):
        for invalid in ("private name", "o-nothex", "o-00000000000000a1' OR 1=1"):
            with self.assertRaises(ValueError):
                self.recall(key=invalid)
        with self.assertRaises(ValueError):
            self.recall(category="plant")  # not in the present public vocabulary
        with self.assertRaises(ValueError):
            recall_memory(self.mem, self.semantics, category="unknown",
                          now_wall_epoch_s=float("nan"))
        other = ExperienceMemory(":memory:")
        self.addCleanup(other.close)
        with self.assertRaises(ValueError):
            recall_memory(other, self.semantics, category="unknown",
                          now_wall_epoch_s=self.now)
        with self.assertRaises(ValueError):
            recall_memory(self.mem, self.semantics, category="unknown",
                          now_wall_epoch_s=self.now, goals=object())

    def test_future_counter_fails_closed(self):
        self.mem.observe(OBJECT_A, "unknown", source="mock")
        with self.mem.conn:
            self.mem.conn.execute(
                "UPDATE objects SET last_seen=? WHERE identifier=?",
                (self.now + 100.0, OBJECT_A))
        with self.assertRaises(ValueError):
            self.recall(key=OBJECT_A)


if __name__ == "__main__":
    unittest.main()
