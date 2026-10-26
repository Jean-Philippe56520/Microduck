"""R2-A: choose the EXISTING M1-B writer and keep M1-A historical.

The opt-in guard is *not* a global ban on arbitrary legacy callers:
it refuses mixed DB contents before R2-A operations, including after
cross-connection writes. No new storage schema, model or real media.
"""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from microduck_companion.compact_multimodal_memory import (
    CompactPatternMemory, audio_fingerprint, image_fingerprint,
)
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.m1a_multimodal_demo import (
    FIXTURE_WALL, _synthetic_audio, _synthetic_pixels,
)
from microduck_companion.multiview_pattern_memory import (
    MultiviewLimits, MultiviewPatternMemory,
)


def rows(db: ExperienceMemory, table: str) -> int:
    if table not in {"m1a_compact_patterns", "m1b_groups", "m1b_signatures"}:
        raise ValueError("test-only bounded table")
    return db.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def tables(db: ExperienceMemory) -> set[str]:
    return {
        item[0] for item in db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }


class R2AOneWriterSelectionTests(unittest.TestCase):
    def setUp(self):
        self.db = ExperienceMemory()
        self.addCleanup(self.db.close)

    def test_r2a_reuses_m1b_without_even_creating_m1a_table(self):
        # A selection, not a new memory implementation or database.
        self.assertNotIn("m1a_compact_patterns", tables(self.db))
        store = MultiviewPatternMemory(self.db, r2a_single_writer=True)
        first = store.observe_image(
            _synthetic_pixels(), now_wall_epoch_s=FIXTURE_WALL,
            category="object",
        )
        sound = store.observe_audio(
            _synthetic_audio(), now_wall_epoch_s=FIXTURE_WALL + .25,
            category="ambient",
        )
        for i in range(1, 8):
            seen = store.observe_image(
                _synthetic_pixels(brightness=5),
                now_wall_epoch_s=FIXTURE_WALL + i,
            )
            self.assertEqual("similar_group_unverified", seen.status)
            self.assertEqual(first.group_id, seen.group_id)
        self.assertEqual("new_group_unverified", first.status)
        self.assertNotEqual(first.group_id, sound.group_id)
        self.assertEqual(2, rows(self.db, "m1b_groups"))
        self.assertEqual(2, rows(self.db, "m1b_signatures"))
        self.assertEqual(80, store.stats()["fingerprint_bytes"])
        self.assertEqual(8, seen.group_sightings)
        self.assertEqual(1, seen.exemplar_count)
        self.assertNotIn("m1a_compact_patterns", tables(self.db))
        self.assertEqual(0, first.network_requests)
        self.assertEqual(0, sound.media_files_stored)
        self.assertFalse(seen.same_physical_source_verified)

    def test_existing_legacy_rows_are_refused_without_creating_m1b_tables(self):
        legacy = CompactPatternMemory(self.db)
        original = legacy.observe_image(
            _synthetic_pixels(), now_wall_epoch_s=FIXTURE_WALL,
        )
        self.assertEqual("new_pattern_unverified", original.status)
        before = self.db.conn.total_changes
        with self.assertRaisesRegex(ValueError, "nonempty M1-A"):
            MultiviewPatternMemory(self.db, r2a_single_writer=True)
        self.assertEqual(before, self.db.conn.total_changes)
        self.assertEqual(1, rows(self.db, "m1a_compact_patterns"))
        self.assertNotIn("m1b_groups", tables(self.db))
        self.assertNotIn("m1b_signatures", tables(self.db))

    def test_empty_legacy_table_is_not_mistaken_for_a_double_writer(self):
        CompactPatternMemory(self.db)  # Historical empty schema is harmless.
        store = MultiviewPatternMemory(self.db, r2a_single_writer=True)
        self.assertEqual(0, rows(self.db, "m1a_compact_patterns"))
        self.assertEqual(
            "new_group_unverified",
            store.observe_image(
                _synthetic_pixels(), now_wall_epoch_s=FIXTURE_WALL,
            ).status,
        )
        self.assertEqual(0, rows(self.db, "m1a_compact_patterns"))
        self.assertEqual(1, rows(self.db, "m1b_signatures"))

    def test_legacy_write_after_selection_fails_next_observe_and_prune(self):
        store = MultiviewPatternMemory(self.db, r2a_single_writer=True)
        first = store.observe_image(
            _synthetic_pixels(), now_wall_epoch_s=FIXTURE_WALL,
        )
        CompactPatternMemory(self.db).observe_audio(
            _synthetic_audio(), now_wall_epoch_s=FIXTURE_WALL + .3,
        )
        before = store.stats().copy()
        with self.assertRaisesRegex(ValueError, "nonempty M1-A"):
            store.observe_image(
                _synthetic_pixels(), now_wall_epoch_s=FIXTURE_WALL + 1,
            )
        with self.assertRaisesRegex(ValueError, "nonempty M1-A"):
            store.prune(now_wall_epoch_s=FIXTURE_WALL + 100_000_000)
        self.assertEqual(before, store.stats())
        self.assertEqual(1, rows(self.db, "m1a_compact_patterns"))
        self.assertEqual(first.group_id, self.db.conn.execute(
            "SELECT id FROM m1b_groups"
        ).fetchone()[0])

    def test_other_connection_legacy_writer_is_detected_next_transaction(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "study.sqlite3"
            primary = ExperienceMemory(path)
            try:
                store = MultiviewPatternMemory(
                    primary, r2a_single_writer=True,
                )
                store.observe_image(
                    _synthetic_pixels(), now_wall_epoch_s=FIXTURE_WALL,
                )
                secondary = ExperienceMemory(path)
                try:
                    CompactPatternMemory(secondary).observe_audio(
                        _synthetic_audio(), now_wall_epoch_s=FIXTURE_WALL,
                    )
                finally:
                    secondary.close()
                with self.assertRaisesRegex(ValueError, "nonempty M1-A"):
                    store.observe_audio(
                        _synthetic_audio(), now_wall_epoch_s=FIXTURE_WALL + 1,
                    )
                self.assertEqual(1, rows(primary, "m1b_signatures"))
            finally:
                primary.close()

    def test_tight_reopen_limits_refuse_before_mutating_existing_rows(self):
        store = MultiviewPatternMemory(self.db)
        store.observe_image(
            _synthetic_pixels(), now_wall_epoch_s=FIXTURE_WALL,
        )
        store.observe_audio(
            _synthetic_audio(), now_wall_epoch_s=FIXTURE_WALL + 1,
        )
        before = store.stats()
        limits = MultiviewLimits(
            max_groups=1, max_signatures=1, max_signatures_per_group=1,
            max_fingerprint_bytes=64, max_comparisons=1,
        )
        with self.assertRaisesRegex(ValueError, "would evict"):
            MultiviewPatternMemory(
                self.db, limits=limits, r2a_single_writer=True,
            )
        self.assertEqual(before, store.stats())

    def test_valid_existing_m1b_reopens_without_replay_or_new_m1a_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "study.sqlite3"
            first_db = ExperienceMemory(path)
            try:
                store = MultiviewPatternMemory(
                    first_db, r2a_single_writer=True,
                )
                initial = store.observe_image(
                    _synthetic_pixels(), now_wall_epoch_s=FIXTURE_WALL,
                )
            finally:
                first_db.close()
            second_db = ExperienceMemory(path)
            try:
                store = MultiviewPatternMemory(
                    second_db, r2a_single_writer=True,
                )
                repeated = store.observe_image(
                    _synthetic_pixels(brightness=4),
                    now_wall_epoch_s=FIXTURE_WALL + 1,
                )
                self.assertEqual(initial.group_id, repeated.group_id)
                self.assertEqual("similar_group_unverified", repeated.status)
                self.assertEqual(2, repeated.group_sightings)
                self.assertEqual(1, rows(second_db, "m1b_signatures"))
                self.assertNotIn("m1a_compact_patterns", tables(second_db))
            finally:
                second_db.close()

    def test_partial_schema_and_invalid_selection_are_rejected(self):
        with self.assertRaises(TypeError):
            MultiviewPatternMemory(self.db, r2a_single_writer=1)
        self.db.conn.execute(
            "CREATE TABLE m1b_groups(id INTEGER PRIMARY KEY)"
        )
        with self.assertRaisesRegex(ValueError, "partial M1-B"):
            MultiviewPatternMemory(self.db, r2a_single_writer=True)
        self.assertNotIn("m1b_signatures", tables(self.db))

    def test_comparison_helpers_stay_pure_without_opening_legacy_memory(self):
        # M1-A as reference means its functions, NOT its persistent writer.
        self.assertEqual(64, len(image_fingerprint(_synthetic_pixels())))
        self.assertEqual(16, len(audio_fingerprint(_synthetic_audio())))
        self.assertNotIn("m1a_compact_patterns", tables(self.db))
        self.assertNotIn("m1b_groups", tables(self.db))


if __name__ == "__main__":
    unittest.main()
