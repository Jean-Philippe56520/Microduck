"""F1-C: passive journal in existing SQLite; fictional categories only.

Real independent Python subprocesses use the same database in a temporary
directory. No camera, audio recording, robotd, movement, or external service.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from microduck_companion import ExperienceMemory, PerceptionEvent, PerceptionSnapshot
from microduck_companion.passive_memory import (
    MAX_STORED_OBSERVATIONS, RETENTION_SECONDS, PassiveMemoryEntry,
    PassiveObservationJournal,
)
from microduck_companion.passive_sources import PassiveRead


WALL = 1_770_000_000.0


def event(kind="object_label", category="ball", *, track="track-fixture-1",
          source="mock", mono=100., ttl=1., confidence=.95):
    return PerceptionEvent(
        kind=kind, value=category, source=source,
        observed_at=mono, ttl_s=ttl, confidence=confidence,
        track_id=track if kind == "object_label" else None,
    )


def read(*events, seq=1, at=100., status="ok", channel="mock_fixture_unix",
         env="mock"):
    return PassiveRead(
        status, PerceptionSnapshot(env, tuple(events), at), seq, channel)


class JournalTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.db = Path(td.name) / "memory.sqlite3"
        self.memory = ExperienceMemory(self.db)
        self.addCleanup(self.memory.close)
        self.journal = PassiveObservationJournal(self.memory)

    def append(self, reading, *, mono=100.1, wall=WALL):
        return self.journal.append(
            reading, now_monotonic_s=mono, now_wall_epoch_s=wall)

    def test_accepted_mock_category_stored_and_read_back(self):
        self.assertEqual(1, self.append(read(event())))
        one, = self.journal.recent(now_wall_epoch_s=WALL)
        self.assertIsInstance(one, PassiveMemoryEntry)
        self.assertEqual(("object_label", "ball", "identified", "mock"),
                         (one.kind, one.category, one.status, one.source))
        self.assertEqual(self.journal.session_id, one.session_id)
        self.assertTrue(one.is_historical)
        self.assertEqual(1, self.journal.category_count(
            "object_label", "ball", now_wall_epoch_s=WALL))
        self.assertIsNone(self.memory.get("track-fixture-1"))

    def test_unknown_is_persisted_without_promotion(self):
        self.assertEqual(1, self.append(read(event(category="unknown"))))
        one, = self.journal.recent(now_wall_epoch_s=WALL)
        self.assertEqual(("unknown", "unknown"),
                         (one.category, one.status))
        self.assertEqual(0, self.journal.category_count(
            "object_label", "unknown", now_wall_epoch_s=WALL))

    def test_conflicting_labels_are_recorded_as_conflict_unknown(self):
        receipt = read(event(category="ball"), event(category="toy"))
        self.assertEqual(1, self.append(receipt))
        one, = self.journal.recent(now_wall_epoch_s=WALL)
        self.assertEqual(("conflict", "unknown"), (one.status, one.category))
        self.assertEqual(0, self.journal.category_count(
            "object_label", "ball", now_wall_epoch_s=WALL))

    def test_uncertain_does_not_erase_known_but_cannot_count_as_known(self):
        self.assertEqual(1, self.append(read(event(), seq=1)))
        self.assertEqual(1, self.append(read(event(category="unknown"), seq=2),
                                        wall=WALL+1))
        rows = self.journal.recent(now_wall_epoch_s=WALL+1)
        self.assertEqual(["unknown", "ball"], [r.category for r in rows])
        self.assertEqual(1, self.journal.category_count(
            "object_label", "ball", now_wall_epoch_s=WALL+1))

    def test_low_confidence_stale_and_future_remain_uncertain(self):
        self.assertEqual(1, self.append(read(event(confidence=.3))))
        self.assertEqual(1, self.append(
            read(event(mono=98.), seq=2, at=100.)))
        self.assertEqual(1, self.append(
            read(event(), seq=3), mono=99.))
        self.assertEqual(["future", "stale", "low_confidence"], [
            r.status for r in self.journal.recent(now_wall_epoch_s=WALL)])
        self.assertTrue(all(r.category == "unknown"
                            for r in self.journal.recent(now_wall_epoch_s=WALL)))

    def test_two_types_only_cat_vs_meow_are_distinct(self):
        self.assertEqual(2, self.append(read(
            event(category="cat"), event("sound_label", "meow"))))
        self.assertEqual(1, self.journal.category_count(
            "object_label", "cat", now_wall_epoch_s=WALL))
        self.assertEqual(1, self.journal.category_count(
            "sound_label", "meow", now_wall_epoch_s=WALL))
        self.assertEqual(0, self.journal.category_count(
            "object_label", "dog", now_wall_epoch_s=WALL))

    def test_no_track_id_or_raw_person_name_or_media_written(self):
        self.assertEqual(1, self.append(
            read(event(category="someone's dog", track="track-private-id"))))
        raw = self.memory.conn.execute(
            "SELECT * FROM passive_observation_log").fetchone()
        columns = raw.keys()
        self.assertNotIn("track_id", columns)
        self.assertNotIn("raw_pixels", columns)
        self.assertNotIn("transcript", columns)
        self.assertNotIn("object_id", columns)
        self.assertNotIn("track-private-id", tuple(raw))
        self.assertNotIn("someone's dog", tuple(raw))
        self.assertEqual("unknown", raw["category"])
        self.assertEqual("unknown", raw["status"])

    def test_non_ok_never_reuses_previous_good_observation(self):
        self.append(read(event(), seq=1))
        for state in ("rate_limited", "duplicate_or_out_of_order",
                      "unavailable_or_invalid", "clock_reset"):
            with self.subTest(status=state):
                self.assertEqual(0, self.append(
                    read(event(category="dog"), seq=2, status=state)))
        self.assertEqual(1, len(self.journal.recent(now_wall_epoch_s=WALL)))
        self.assertEqual(0, self.journal.category_count(
            "object_label", "dog", now_wall_epoch_s=WALL))

    def test_duplicate_sequence_is_idempotent_within_session(self):
        x = read(event(), seq=9)
        self.assertEqual(1, self.append(x))
        self.assertEqual(0, self.append(x))
        self.assertEqual(1, len(self.journal.recent(now_wall_epoch_s=WALL)))

    def test_reused_sequence_cannot_add_a_different_second_category(self):
        self.assertEqual(1, self.append(read(event(category="ball"), seq=7)))
        second = read(event(category="ball"),
                      event("sound_label", "meow"), seq=7)
        self.assertEqual(0, self.append(second, wall=WALL+1))
        entries = self.journal.recent(now_wall_epoch_s=WALL+1)
        self.assertEqual(1, len(entries))
        self.assertEqual("ball", entries[0].category)

    def test_sequence_with_multiple_categories_counts_actual_insertions(self):
        reading = read(event(category="ball"),
                       event("sound_label", "bark"), seq=12)
        self.assertEqual(2, self.append(reading))
        self.assertEqual(0, self.append(reading))
        self.assertEqual(2, len(self.journal.recent(now_wall_epoch_s=WALL)))

    def test_rejects_sensor_or_robot_and_conflicting_channel(self):
        candidates = (
            read(event(source="sensor"), seq=1),
            read(event(), seq=2, env="robot"),
            read(event(), seq=3, channel="oem_media_hello_only"),
            read(event(), seq=4, channel="sensor"),
            read(PerceptionEvent("floor_clear", True, "mock", 100., 1., 1.), seq=5),
        )
        for item in candidates:
            with self.subTest(item=item.sequence), self.assertRaises(ValueError):
                self.append(item)
        self.assertEqual((), self.journal.recent(now_wall_epoch_s=WALL))

    def test_raw_or_untrusted_categories_cannot_enter_table(self):
        for value in ("my pet", "person named Alex", "photo.png"):
            with self.subTest(value=value):
                self.assertEqual(1, self.append(
                    read(event(category=value), seq=len(value))))
                one = self.journal.recent(now_wall_epoch_s=WALL)[0]
                self.assertEqual("unknown", one.category)
        for bad in ("who is talking", "private voice", "Nessquick"):
            with self.assertRaises(ValueError):
                event("sound_label", bad)

    def test_bad_sequence_and_timestamp_fail_closed(self):
        for seq in (True, -1, 2**63, "1", None):
            with self.subTest(seq=seq), self.assertRaises(ValueError):
                self.append(read(event(), seq=seq))
        for bad in (True, -1, "x", float("nan"), math.inf):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.journal.append(read(event()),
                                    now_monotonic_s=bad,
                                    now_wall_epoch_s=WALL)
            with self.subTest(wall=bad), self.assertRaises(ValueError):
                self.journal.append(read(event()),
                                    now_monotonic_s=100.1,
                                    now_wall_epoch_s=bad)

    def test_rejects_non_experience_memory(self):
        with self.assertRaises(TypeError):
            PassiveObservationJournal(":memory:")

    def test_category_count_rejects_unlisted_types_and_query_limits(self):
        for cat in ("person X", "Malo", "ball with eyes"):
            with self.assertRaises(ValueError):
                self.journal.category_count(
                    "object_label", cat, now_wall_epoch_s=WALL)
        with self.assertRaises(ValueError):
            self.journal.category_count(
                "floor_clear", "ball", now_wall_epoch_s=WALL)
        for n in (0, -1, True, 101):
            with self.assertRaises(ValueError):
                self.journal.recent(now_wall_epoch_s=WALL, limit=n)

    def test_recent_history_is_not_live_after_reboot_or_clock_change(self):
        self.append(read(event(), seq=1), wall=WALL)
        self.assertEqual((), self.journal.recent(now_wall_epoch_s=WALL-1))
        self.assertEqual((), self.journal.recent(
            now_wall_epoch_s=WALL+RETENTION_SECONDS+1))
        self.assertEqual(0, self.journal.category_count(
            "object_label", "ball",
            now_wall_epoch_s=WALL+RETENTION_SECONDS+1))

    def test_retention_cutoff_purges_only_old_rows(self):
        self.append(read(event(category="ball"), seq=1), wall=WALL)
        self.append(read(event(category="toy"), seq=2),
                    wall=WALL+RETENTION_SECONDS-1)
        self.assertEqual(1, self.journal.prune(
            now_wall_epoch_s=WALL+RETENTION_SECONDS+1))
        remaining, = self.journal.recent(
            now_wall_epoch_s=WALL+RETENTION_SECONDS+1)
        self.assertEqual("toy", remaining.category)

    def test_future_rows_are_not_replayed_and_clock_skew_is_bounded(self):
        self.append(read(event(), seq=1), wall=WALL+300)
        self.assertEqual((), self.journal.recent(now_wall_epoch_s=WALL))
        self.assertEqual(1, self.journal.prune(now_wall_epoch_s=WALL))
        self.assertEqual((), self.journal.recent(now_wall_epoch_s=WALL+301))

    def test_retention_hard_bounded_to_512_rows(self):
        for i in range(MAX_STORED_OBSERVATIONS+6):
            self.assertEqual(1, self.append(
                read(event(category="toy"), seq=i),
                wall=WALL+i))
        c = self.memory.conn.execute(
            "SELECT COUNT(*) FROM passive_observation_log").fetchone()[0]
        self.assertEqual(MAX_STORED_OBSERVATIONS, c)
        self.assertEqual(MAX_STORED_OBSERVATIONS, self.journal.category_count(
            "object_label", "toy",
            now_wall_epoch_s=WALL+MAX_STORED_OBSERVATIONS+6))

    def test_objects_and_rewards_unchanged(self):
        self.memory.observe("fictional-1", "unknown", "mock")
        before = self.memory.get("fictional-1")
        self.append(read(event(category="dog")))
        self.assertEqual(before, self.memory.get("fictional-1"))
        self.assertEqual(0, self.memory.experience_count())
        self.assertEqual(0., self.memory.intent_preference("simulator", "explore"))

    def test_journal_sessions_have_unique_random_nonidentifying_ids(self):
        different = PassiveObservationJournal(self.memory)
        self.assertNotEqual(self.journal.session_id, different.session_id)
        self.assertEqual(32, len(self.journal.session_id))


class ProcessRestartTests(unittest.TestCase):
    def test_two_real_processes_share_database_but_not_monotonic_ttl(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"memory.sqlite3"
            code = """
import json,sys
from microduck_companion import ExperienceMemory,PerceptionEvent,PerceptionSnapshot
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.passive_memory import PassiveObservationJournal
db,sequence,mono,wall=sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),float(sys.argv[4])
mem=ExperienceMemory(db)
journal=PassiveObservationJournal(mem)
ev=PerceptionEvent('object_label','ball','mock',mono,1.,.95,track_id='track-reused')
read=PassiveRead('ok',PerceptionSnapshot('mock',(ev,),mono),sequence)
inserted=journal.append(read,now_monotonic_s=mono+.1,now_wall_epoch_s=wall)
print(json.dumps({'count':journal.category_count('object_label','ball',now_wall_epoch_s=wall),
                  'inserted':inserted,'session':journal.session_id,
                  'history':len(journal.recent(now_wall_epoch_s=wall))}))
mem.close()
"""
            results = []
            for seq, mono, wall in ((1, 100., WALL), (1, 1., WALL+3)):
                p = subprocess.run(
                    [sys.executable, "-c", code, str(path), str(seq),
                     str(mono), str(wall)],
                    check=True, capture_output=True, text=True, timeout=12,
                )
                results.append(json.loads(p.stdout))
            self.assertEqual([1, 2], [r["count"] for r in results])
            self.assertEqual([1, 2], [r["history"] for r in results])
            self.assertEqual([1, 1], [r["inserted"] for r in results])
            self.assertNotEqual(results[0]["session"], results[1]["session"])
            with sqlite3.connect(path) as conn:
                names = {x[0] for x in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertIn("objects", names)
                self.assertIn("passive_observation_log", names)
                self.assertEqual(2, conn.execute(
                    "SELECT COUNT(DISTINCT session_id) FROM passive_observation_log"
                ).fetchone()[0])
                self.assertFalse(any("track" in k for k in
                                     (x[1] for x in conn.execute(
                                         "PRAGMA table_info(passive_observation_log)"))))


if __name__ == "__main__":
    unittest.main()
