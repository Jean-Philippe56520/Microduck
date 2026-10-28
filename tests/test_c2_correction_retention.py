"""C2: durable, bounded F4-A correction markers in the EXISTING SQLite.

No robot, Qwen, sensor, motor, identity, signature table or action/reward.
All observations and property labels are fictional, closed-vocabulary fixtures.
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

from microduck_companion.category_semantics import (
    CategorySemantics,
    CORRECTION_REASONS,
    HYPOTHESIS_CATEGORIES,
    MAX_HYPOTHESES,
    MAX_HYPOTHESIS_KEYS,
    PROPERTIES,
    RETENTION_S,
)
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.memory_consolidation import recall_category
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_learning import PassiveLearning

WALL = 1_770_000_000.0


class C2DurableCorrectionTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "same-experience.sqlite3"
        self.memory = ExperienceMemory(self.path)
        self.addCleanup(self._close)
        # C1 must only read a fully initialized, provenance-linked F1-C/F2-C
        # fixture schema. Do not invent a source event for the C2 tests.
        self.journal = PassiveObservationJournal(self.memory)
        self.learning = PassiveLearning(self.memory)
        self.semantics = CategorySemantics(self.memory)

    def _close(self):
        if self.memory is not None:
            self.memory.close()

    def propose(self, *, category="cat", prop="texture", value="soft",
                at=WALL, confidence=.7):
        return self.semantics.hypothesize(
            category=category, property=prop, value=value,
            confidence=confidence, now_wall_epoch_s=at)

    def rows(self):
        return self.memory.conn.execute("""
            SELECT id,category,property,value,proposed_confidence,
                   active,correction_reason,proposed_epoch_s
            FROM f4a_property_hypotheses ORDER BY id
        """).fetchall()

    def test_closed_keyspace_fits_in_existing_table_without_new_schema(self):
        self.assertEqual(6, len(HYPOTHESIS_CATEGORIES))
        self.assertEqual(9, sum(len(v) for v in PROPERTIES.values()))
        self.assertEqual(54, MAX_HYPOTHESIS_KEYS)
        self.assertLessEqual(MAX_HYPOTHESIS_KEYS, MAX_HYPOTHESES)
        self.assertEqual(
            {"fixture_annotation_error", "source_retracted"},
            set(CORRECTION_REASONS))

    def test_tombstone_survives_multiple_ttls_and_blocks_reentry(self):
        hid = self.propose()
        self.assertIsInstance(hid, int)
        self.assertTrue(self.semantics.retract_hypothesis(
            hid, reason="fixture_annotation_error"))
        for when in (WALL, WALL+RETENTION_S+1,
                     WALL+8*RETENTION_S):
            with self.subTest(when=when):
                self.semantics.prune(now_wall_epoch_s=when)
                self.assertEqual(1, len(self.rows()))
                self.assertIsNone(self.propose(at=when, confidence=.99))
                self.assertEqual((), self.semantics.hypotheses(
                    category="cat", now_wall_epoch_s=when))
                result = recall_category(
                    self.semantics, category="cat",
                    now_wall_epoch_s=when)
                self.assertEqual("unknown", result.status)
                self.assertFalse(result.physical_actions_authorized)
                self.assertEqual(0, result.memory_writes)
                self.assertEqual(0, result.causal_effects_verified)
        (row,) = self.rows()
        self.assertEqual(hid, row["id"])
        self.assertEqual(0, row["active"])
        self.assertEqual("fixture_annotation_error", row["correction_reason"])
        self.assertEqual(0, row["proposed_confidence"])

    def test_legacy_retraction_with_existing_schema_survives_restart(self):
        # The old F4-A release used these exact columns and UNIQUE key.
        h = self.propose(category="dog", prop="movement", value="moving")
        with self.memory.conn:
            self.memory.conn.execute("""
                UPDATE f4a_property_hypotheses
                SET active=0,correction_reason='source_retracted'
                WHERE id=?
            """, (h,))
        tables_before = {
            row[0] for row in self.memory.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        }
        self.memory.close()
        self.memory = ExperienceMemory(self.path)
        self.semantics = CategorySemantics(self.memory)
        self.semantics.prune(now_wall_epoch_s=WALL+RETENTION_S*3)
        self.assertIsNone(self.propose(
            category="dog", prop="movement", value="moving",
            at=WALL+RETENTION_S*3))
        self.assertEqual(
            "source_retracted", self.rows()[0]["correction_reason"])
        tables_after = {
            row[0] for row in self.memory.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        }
        self.assertEqual(tables_before, tables_after)
        self.assertFalse(any(x.startswith("c2_") for x in tables_after))

    def test_expired_active_hypothesis_can_be_reconsidered_with_one_call(self):
        h = self.propose(value="hard")
        later = WALL+RETENTION_S+1
        fresh = self.propose(value="hard", at=later, confidence=.63)
        self.assertIsInstance(fresh, int)
        self.assertNotEqual(h, fresh)
        self.assertEqual(1, len(self.rows()))
        (rec,) = self.semantics.hypotheses(
            category="cat", now_wall_epoch_s=later)
        self.assertEqual(.63, rec.proposed_confidence)
        self.assertFalse(rec.confirmed)
        self.assertFalse(rec.can_authorize_actions)

    def test_new_contradictory_hypothesis_allowed_without_reviving_corrected_one(self):
        soft = self.propose(value="soft")
        self.assertTrue(self.semantics.retract_hypothesis(
            soft, reason="source_retracted"))
        hard = self.propose(value="hard")
        self.assertNotEqual(soft, hard)
        self.assertEqual(2, len(self.rows()))
        (only,) = self.semantics.hypotheses(
            category="cat", now_wall_epoch_s=WALL)
        self.assertEqual("hard", only.value)
        self.assertEqual(
            (), recall_category(self.semantics, category="cat",
                                now_wall_epoch_s=WALL
                                ).conflicting_hypothesis_properties)
        self.assertFalse(only.can_authorize_actions)

    def test_all_54_closed_keys_fit_and_are_still_withdrawn_after_prune(self):
        ids = []
        for category in sorted(HYPOTHESIS_CATEGORIES):
            for prop, values in sorted(PROPERTIES.items()):
                for value in sorted(values):
                    hid = self.propose(
                        category=category, prop=prop, value=value)
                    self.assertIsInstance(hid, int)
                    self.assertTrue(self.semantics.retract_hypothesis(
                        hid, reason="fixture_annotation_error"))
                    ids.append(hid)
        self.assertEqual(MAX_HYPOTHESIS_KEYS, len(ids))
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(MAX_HYPOTHESIS_KEYS, len(self.rows()))
        for future in (WALL+2*RETENTION_S, WALL+100*RETENTION_S):
            self.semantics.prune(now_wall_epoch_s=future)
            self.assertEqual(MAX_HYPOTHESIS_KEYS, len(self.rows()))
            self.assertTrue(all(r["active"] == 0 for r in self.rows()))
        for category in HYPOTHESIS_CATEGORIES:
            self.assertEqual(
                (), self.semantics.hypotheses(
                    category=category, now_wall_epoch_s=future))
        self.assertIsNone(self.propose(
            category="cat", prop="texture", value="soft", at=future))

    def test_repeat_retraction_never_overwrites_original_reason(self):
        hid = self.propose()
        self.assertTrue(self.semantics.retract_hypothesis(
            hid, reason="source_retracted"))
        self.assertFalse(self.semantics.retract_hypothesis(
            hid, reason="fixture_annotation_error"))
        self.assertEqual(
            "source_retracted", self.rows()[0]["correction_reason"])

    def test_active_expiration_cannot_remove_other_corrected_key(self):
        corrected = self.propose(value="soft")
        self.semantics.retract_hypothesis(
            corrected, reason="source_retracted")
        active = self.propose(value="hard")
        self.semantics.prune(
            now_wall_epoch_s=WALL+RETENTION_S+1)
        self.assertEqual(
            [corrected], [r["id"] for r in self.rows()])
        self.assertIsNone(self.propose(
            value="soft", at=WALL+RETENTION_S+1))
        self.assertIsInstance(self.propose(
            value="hard", at=WALL+RETENTION_S+1), int)
        self.assertNotEqual(active, self.rows()[-1]["id"])

    def test_clock_rollback_or_future_clock_does_not_erase_correction(self):
        hid = self.propose(at=WALL+600)
        self.assertTrue(self.semantics.retract_hypothesis(
            hid, reason="source_retracted"))
        self.semantics.prune(now_wall_epoch_s=WALL)
        self.assertEqual(hid, self.rows()[0]["id"])
        self.assertIsNone(self.propose(at=WALL, confidence=1))

    def test_corrupt_inactive_row_without_reason_refuses_to_prune(self):
        with self.memory.conn:
            self.memory.conn.execute("""
                INSERT INTO f4a_property_hypotheses(
                    category,property,value,proposed_confidence,
                    proposed_epoch_s,source,active)
                VALUES ('dog','texture','soft',.4,?,
                        'fictional_llm_hypothesis_only',0)
            """, (WALL,))
        before = self.memory.conn.total_changes
        with self.assertRaisesRegex(
                ValueError, "inconsistent persisted hypothesis correction"):
            self.semantics.prune(now_wall_epoch_s=WALL+RETENTION_S+1)
        self.assertEqual(before, self.memory.conn.total_changes)
        self.assertEqual(1, len(self.rows()))

    def test_corrupt_foreign_category_refused_even_if_below_cap(self):
        with self.memory.conn:
            self.memory.conn.execute("""
                INSERT INTO f4a_property_hypotheses(
                    category,property,value,proposed_confidence,
                    proposed_epoch_s,source,active,correction_reason)
                VALUES ('private_identity','texture','soft',0,?,
                        'fictional_llm_hypothesis_only',0,'source_retracted')
            """, (WALL,))
        with self.assertRaisesRegex(ValueError, "unsupported persisted"):
            self.propose(category="cat")
        self.assertEqual(1, len(self.rows()))

    def test_over_budget_store_refuses_correction_eviction_and_rolls_back(self):
        old = self.propose(value="soft")
        # Pretend that a broken older writer allowed 65 arbitrary keys.
        with self.memory.conn:
            for i in range(MAX_HYPOTHESES+1):
                self.memory.conn.execute("""
                    INSERT INTO f4a_property_hypotheses(
                        category,property,value,proposed_confidence,
                        proposed_epoch_s,source,active,correction_reason)
                    VALUES (?,?, 'soft',0,?,
                            'fictional_llm_hypothesis_only',0,
                            'source_retracted')
                """, (f"forged{i}", "texture", WALL))
        with self.assertRaisesRegex(ValueError, "retention cap exceeded"):
            self.semantics.prune(
                now_wall_epoch_s=WALL+RETENTION_S+1)
        # The expired active entry must be rolled back along with the prune.
        self.assertIsNotNone(self.memory.conn.execute(
            "SELECT 1 FROM f4a_property_hypotheses WHERE id=?",
            (old,)).fetchone())
        self.assertEqual(MAX_HYPOTHESES+2, len(self.rows()))

    def test_reduced_capacity_fails_closed_instead_of_dropping_tombstone(self):
        h = self.propose()
        self.semantics.retract_hypothesis(
            h, reason="source_retracted")
        with patch("microduck_companion.category_semantics.MAX_HYPOTHESES", 1):
            with self.assertRaisesRegex(ValueError, "vocabulary exceeds"):
                self.semantics.prune(
                    now_wall_epoch_s=WALL+RETENTION_S+1)
        self.assertEqual(h, self.rows()[0]["id"])

    def test_no_new_tables_no_model_no_action_or_reward_updates(self):
        before = {
            r[0] for r in self.memory.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        }
        old_pref = self.memory.intent_preference(
            "simulator", "explore")
        h = self.propose()
        self.semantics.retract_hypothesis(
            h, reason="fixture_annotation_error")
        self.semantics.prune(now_wall_epoch_s=WALL+RETENTION_S*3)
        result = recall_category(
            self.semantics, category="cat",
            now_wall_epoch_s=WALL+RETENTION_S*3)
        after = {
            r[0] for r in self.memory.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        }
        self.assertEqual(before, after)
        self.assertEqual(old_pref, self.memory.intent_preference(
            "simulator", "explore"))
        self.assertEqual(0, self.memory.experience_count())
        self.assertEqual(0, result.causal_effects_verified)
        self.assertEqual(0, result.motor_commands_issued)
        self.assertFalse(result.physical_actions_authorized)


if __name__ == "__main__":
    main()
