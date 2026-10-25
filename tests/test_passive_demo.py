"""F1-D end-to-end fictional Unix fixture + existing cognition/SQLite tests."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from microduck_companion import (
    AutonomyBrain, ExperienceMemory, PerceptionEvent, PerceptionSnapshot,
    PassiveObservationJournal,
)
from microduck_companion.passive_demo import (
    _check_expected, _passive_cycle, _scenario, main, run_session,
)
from microduck_companion.passive_sources import PassiveRead


@unittest.skipUnless(hasattr(socket, "AF_UNIX"), "Unix socket only")
class FullPipelineTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.db = Path(td.name) / "f1d-memory.sqlite3"

    def subprocess_session(self, stage: str) -> tuple[int, dict | None]:
        proc = subprocess.run(
            [sys.executable, "-m", "microduck_companion.passive_demo",
             "--database", str(self.db), "--session", stage],
            capture_output=True, text=True, timeout=12,
        )
        return proc.returncode, json.loads(proc.stdout) if proc.stdout else None

    def test_two_independent_processes_reopen_one_sqlite_and_pass(self):
        first_code, first = self.subprocess_session("first")
        second_code, second = self.subprocess_session("second")
        self.assertEqual((0, 0), (first_code, second_code))
        self.assertTrue(first["phase_f1_d_demo_passed"])
        self.assertTrue(second["phase_f1_d_demo_passed"])
        self.assertNotEqual(first["session_id"], second["session_id"])
        self.assertEqual((5, 8), (first["historical_categories"],
                                  second["historical_categories"]))
        self.assertEqual((2, 4), (first["ball_category_count"],
                                  second["ball_category_count"]))
        self.assertEqual((6, 4), (first["cycles_count"], second["cycles_count"]))
        self.assertEqual("new_category",
                         first["cycles"][0]["observations"][0]["familiarity"])
        self.assertEqual("previously_seen_category",
                         first["cycles"][1]["observations"][0]["familiarity"])
        self.assertEqual(("unknown", "conflict", "unresolved"), (
            first["cycles"][2]["observations"][0]["category"],
            first["cycles"][2]["observations"][0]["status"],
            first["cycles"][2]["observations"][0]["familiarity"]))
        self.assertEqual("unknown",
                         first["cycles"][3]["observations"][0]["status"])
        self.assertEqual("unavailable_or_invalid",
                         first["cycles"][4]["source_status"])
        self.assertEqual([], first["cycles"][4]["observations"])
        self.assertEqual("previously_seen_category",
                         second["cycles"][0]["observations"][0]["familiarity"])
        self.assertEqual("new_category",
                         second["cycles"][1]["observations"][0]["familiarity"])
        self.assertEqual("unavailable_or_invalid",
                         second["cycles"][2]["source_status"])
        self.assertEqual([], second["cycles"][2]["observations"])
        self.assertEqual("previously_seen_category",
                         second["cycles"][3]["observations"][0]["familiarity"])
        for report in (first, second):
            self.assertEqual("mock_only", report["source"])
            self.assertEqual("fictional_f1d_unix_fixture_only",
                             report["scenario"])
            self.assertEqual(0, report["motor_commands_issued"])
            self.assertTrue(report["no_raw_media"])
            self.assertTrue(report["no_identity_recognition"])
            self.assertTrue(report["historical_is_not_live_perception"])
            self.assertFalse(report["physical_robot_validated"])
            self.assertFalse(report["oem_sensor_connected"])
            self.assertTrue(all(x["intention"] == "halt"
                                and x["motor_commands"] == 0
                                and x["disposition"] == "no_motor_execution"
                                for x in report["cycles"]))

    def test_database_contains_only_mock_categories_and_no_track_id(self):
        self.assertEqual(0, self.subprocess_session("first")[0])
        self.assertEqual(0, self.subprocess_session("second")[0])
        with sqlite3.connect(self.db) as db:
            rows = db.execute("""
                SELECT kind,category,status,source,channel
                FROM passive_observation_log ORDER BY id
            """).fetchall()
            self.assertEqual(8, len(rows))
            self.assertEqual({"mock"}, {row[3] for row in rows})
            self.assertEqual({"mock_fixture_unix"}, {row[4] for row in rows})
            self.assertEqual(
                [("unknown", "conflict"), ("unknown", "unknown")],
                [(r[1], r[2]) for r in rows if r[2] != "identified"])
            self.assertEqual(4, sum(r[1] == "ball" for r in rows))
            self.assertEqual(0, db.execute(
                "SELECT count(*) FROM objects").fetchone()[0])
            self.assertEqual(10, db.execute(
                "SELECT count(*) FROM experiences WHERE action='halt'"
            ).fetchone()[0])
            self.assertEqual(0, db.execute(
                "SELECT count(*) FROM sim_motion_trials").fetchone()[0])
            self.assertEqual(0, db.execute(
                "SELECT count(*) FROM intent_preferences").fetchone()[0])
            columns = {r[1] for r in db.execute(
                "PRAGMA table_info(passive_observation_log)")}
            self.assertFalse({"track_id", "pixels", "transcript", "object_id"} & columns)
        database_bytes = self.db.read_bytes()
        self.assertNotIn(b"track-fictional", database_bytes)
        self.assertNotIn(b"safe_area", database_bytes)
        self.assertNotIn(b"media.frame", database_bytes)

    def test_first_standalone_is_validated_without_second(self):
        report = run_session(self.db, session="first")
        _check_expected(report)
        self.assertFalse(report["phase_f1_d_demo_passed"])
        self.assertEqual(5, report["historical_categories"])

    def test_second_without_first_does_not_claim_success(self):
        code, report = self.subprocess_session("second")
        self.assertEqual(2, code)
        self.assertIsNone(report)

    def test_repeating_first_session_cannot_claim_clean_success(self):
        self.assertEqual(0, self.subprocess_session("first")[0])
        code, report = self.subprocess_session("first")
        self.assertEqual(2, code)
        self.assertIsNone(report)

    def test_skipped_and_repeated_sessions_leave_database_unchanged(self):
        self.assertEqual(2, self.subprocess_session("second")[0])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(0, db.execute(
                "SELECT count(*) FROM passive_observation_log"
            ).fetchone()[0])
        self.assertEqual(0, self.subprocess_session("first")[0])
        self.assertEqual(2, self.subprocess_session("first")[0])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(5, db.execute(
                "SELECT count(*) FROM passive_observation_log"
            ).fetchone()[0])
        self.assertEqual(0, self.subprocess_session("second")[0])

    def test_wrong_session_is_rejected(self):
        for invalid in ("robot", "both", "", "FIRST"):
            with self.subTest(session=invalid), self.assertRaises(ValueError):
                run_session(self.db, session=invalid)


class ContractSafetyTests(unittest.TestCase):
    def setUp(self):
        self.memory = ExperienceMemory()
        self.addCleanup(self.memory.close)
        self.journal = PassiveObservationJournal(self.memory)
        self.brain = AutonomyBrain(self.memory)

    def test_failed_source_cannot_reuse_or_forge_safety_frame(self):
        # A deliberately forged failed read includes a complete mock safety
        # frame. F1-D must throw it away and call the brain on an empty scene.
        events = (
            PerceptionEvent("safe_area", True, "mock", 100., 1., 1.),
            PerceptionEvent("floor_clear", True, "mock", 100., 1., 1.),
            PerceptionEvent("obstacle_m", 2., "mock", 100., 1., 1.),
            PerceptionEvent("battery_pct", 85., "mock", 100., 1., 1.),
            PerceptionEvent("object_label", "toy", "mock", 100., 1., .99,
                            track_id="track-private"),
        )
        failed = PassiveRead(
            "unavailable_or_invalid", PerceptionSnapshot("mock", events, 100.),
        )
        cycle = _passive_cycle(
            failed, memory=self.memory, journal=self.journal, brain=self.brain,
            now_mono=100.1, now_wall=1_770_000_000.,
        )
        self.assertEqual("halt", cycle["intention"])
        self.assertEqual(0, cycle["stored_rows"])
        self.assertEqual([], cycle["observations"])
        self.assertIsNone(self.memory.get("track-private"))

    def test_ok_with_safety_claim_is_rejected_not_logged(self):
        forged = PassiveRead(
            "ok", PerceptionSnapshot("mock", (
                PerceptionEvent("floor_clear", True, "mock", 100., 1., 1.),
            ), 100.), 1,
        )
        with self.assertRaises(ValueError):
            _passive_cycle(
                forged, memory=self.memory, journal=self.journal,
                brain=self.brain, now_mono=100.1, now_wall=1_770_000_000.,
            )
        self.assertEqual((), self.journal.recent(now_wall_epoch_s=1_770_000_000.))
        self.assertEqual(0, self.memory.experience_count())

    def test_wrong_read_type_and_times_rejected(self):
        for candidate in (None, "mock", {}):
            with self.assertRaises(TypeError):
                _passive_cycle(candidate, memory=self.memory,
                               journal=self.journal, brain=self.brain,
                               now_mono=100., now_wall=1_770_000_000.)
        read = PassiveRead("unavailable_or_invalid",
                           PerceptionSnapshot("mock", (), 100.))
        for clock in (float("nan"), float("inf"), "100"):
            with self.assertRaises(ValueError):
                _passive_cycle(read, memory=self.memory,
                               journal=self.journal, brain=self.brain,
                               now_mono=clock, now_wall=1_770_000_000.)

    def test_expectation_validator_blocks_forged_success_and_motion(self):
        report = {
            "session": "first", "cycles": [
                {"source_status": "ok", "stored_rows": 1,
                 "intention": "halt", "motor_commands": 0,
                 "observations": [{"familiarity": "new_category",
                                   "category": "ball", "status": "identified",
                                   "source": "mock"}]}
            ],
            "ball_category_count": 2, "historical_categories": 5,
            "no_raw_media": True, "no_identity_recognition": True,
            "historical_is_not_live_perception": True,
            "physical_robot_validated": False, "oem_sensor_connected": False,
        }
        with self.assertRaises(RuntimeError):
            _check_expected(report)
        report["cycles"][0]["intention"] = "explore"
        with self.assertRaises(RuntimeError):
            _check_expected(report)

    def test_scenario_is_bounded_and_fiction_only(self):
        first, second = _scenario("first"), _scenario("second")
        self.assertEqual((6, 4), (len(first), len(second)))
        self.assertEqual((100.1, 10.1), (first[0][0], second[0][0]))
        self.assertTrue(all(len(packet) < 8192
                            for _, packet in first + second))
        for _, raw in first + second:
            self.assertNotIn(b"Nessquick", raw)
            self.assertNotIn(b"Kitty", raw)
            self.assertNotIn(b"person_name", raw)
            self.assertNotIn(b"media.frame", raw)
            self.assertNotIn(b"robot.move", raw)


if __name__ == "__main__":
    unittest.main()
