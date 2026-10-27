"""X2-C fixture tests of report verification; NOT a MuJoCo simulation run."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.sim_bridge import SimulatorTelemetry
from microduck_companion.sim_ipc import HealthReading, StateReading, DepthReading
from microduck_companion.sim_passive_cycles import PassiveSimCycleRunner
from microduck_companion.sim_x2c_acceptance import (
    REPORT_SOURCE, validate_acceptance,
)


def reading(at: float, seq: int, battery: float = 80.) -> SimulatorTelemetry:
    return SimulatorTelemetry(
        HealthReading(True, battery, 50., 49.9, 0, at - .1),
        StateReading(False, False, 49.9, 0, seq * 1_000_000, at - .1),
        DepthReading(seq, (1400,) * 64, (5,) * 64,
                     seq * 1_000_000 + 10_000, at - .1),
    )


def metrics() -> dict:
    return {
        "latency_basis": "host_perf_counter_ms_nearest_rank_p95",
        "acquisition_ms_p50": 2.,
        "acquisition_ms_p95": 3.,
        "decision_ms_p50": .2,
        "decision_ms_p95": .3,
        "process_cpu_ms": 10.5,
        "session_wall_ms": 1500.,
        "process_peak_rss_kib": 14000,
        "sqlite_file_bytes": 40960,
        "sqlite_wal_bytes": 0,
        "samples": [
            {"sequence": 1, "acquisition_ms": 1., "decision_ms": .1},
            {"sequence": 2, "acquisition_ms": 2., "decision_ms": .2},
            {"sequence": 3, "acquisition_ms": 3., "decision_ms": .3},
        ],
    }


class X2cAcceptanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / "shared.sqlite3"
        memory = ExperienceMemory(self.database)
        a = PassiveSimCycleRunner(memory, session="x2c-session-a")
        a_results = []
        for i in range(3):
            x = a.step(reading(100. + i, i + 1,
                               battery=12. if i == 0 else 80.),
                       now=100. + i)
            a_results.append(x)
        b = PassiveSimCycleRunner(memory, session="x2c-session-b")
        b_results = []
        for i in range(3):
            x = b.step(reading(103. + i, i + 4), now=103. + i)
            b_results.append(x)
        memory.close()

        def make_report(session, xs, count):
            return {
                "source": REPORT_SOURCE, "session": session,
                "cycles": [{
                    "sequence": r.sequence,
                    "quality": r.quality,
                    "intention": r.plan.intention,
                    "disposition": r.disposition,
                    "depth_seq": r.depth_seq,
                    "attention": r.attention,
                    "comparison": r.comparison,
                    "reference_id": r.reference_id,
                } for r in xs],
                "journal_count": count,
                "coherent_cycles": 3,
                "motor_commands_issued": 0,
                "verified_consequences": 0,
                "hardware_validated": False,
                "floor_certified": False,
                "host_metrics": metrics(),
            }
        self.first = make_report("x2c-session-a", a_results, 3)
        self.second = make_report("x2c-session-b", b_results, 6)

    def test_six_coherent_cycles_link_memory_without_a_single_motor_or_reward(self):
        evidence = validate_acceptance(
            self.database, self.first, self.second)
        self.assertTrue(evidence["accepted"])
        self.assertEqual(6, evidence["coherent_cycles"])
        self.assertEqual(0, evidence["motor_commands_issued_by_companion"])
        self.assertEqual(0, evidence["verified_consequences"])
        self.assertEqual("observed", evidence["memory_context"]["status"])
        self.assertGreaterEqual(
            evidence["memory_context"]["cross_session_links"], 1)
        self.assertEqual("ok", evidence["storage"]["integrity"])
        self.assertEqual(6, evidence["storage"]["journal_rows"])
        self.assertEqual(2., evidence["host_latency"]["acquisition"]["p50_ms"])
        self.assertEqual(3., evidence["host_latency"]["acquisition"]["p95_ms"])
        self.assertEqual(.2, evidence["host_latency"]["decision"]["p50_ms"])
        self.assertIs(evidence["hardware_validated"], False)
        self.assertIs(evidence["floor_certified"], False)
        self.assertFalse(evidence["local_pc_transport_configured"])

    def test_second_report_must_prove_same_sqlite_and_a_distinct_session(self):
        for mutation in (
            {"journal_count": 3},
            {"session": "x2c-session-a"},
            {"coherent_cycles": 2},
            {"source": "real_robot"},
            {"hardware_validated": True},
            {"floor_certified": True},
            {"motor_commands_issued": 1},
            {"verified_consequences": 1},
        ):
            with self.subTest(mutation=mutation):
                wrong = dict(self.second, **mutation)
                with self.assertRaises(ValueError):
                    validate_acceptance(self.database, self.first, wrong)

    def test_invalid_sensor_and_action_claims_are_not_accepted(self):
        candidates = [
            {"quality": "invalid_or_missing"},
            {"intention": "explore"},
            {"disposition": "blocked_motion"},
            {"depth_seq": None},
            {"attention": "Wander"},
            {"comparison": "invented_object"},
            {"reference_id": 999},
        ]
        for mutation in candidates:
            with self.subTest(mutation=mutation):
                other = json.loads(json.dumps(self.second))
                other["cycles"][1].update(mutation)
                with self.assertRaises(ValueError):
                    validate_acceptance(self.database, self.first, other)

    def test_fabricated_latency_or_invalid_rss_fails_closed(self):
        for mutation in (
            {"acquisition_ms_p50": 0.},
            {"decision_ms_p95": float("nan")},
            {"process_peak_rss_kib": True},
            {"session_wall_ms": -1.},
            {"samples": []},
        ):
            with self.subTest(mutation=mutation):
                bad = json.loads(json.dumps(self.first))
                bad["host_metrics"].update(mutation)
                with self.assertRaises(ValueError):
                    validate_acceptance(self.database, bad, self.second)

    def test_corrupted_journal_intention_denied_even_with_perfect_report(self):
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE sim_passive_cycles SET intention='explore' WHERE id=1")
        with self.assertRaises(ValueError):
            validate_acceptance(self.database, self.first, self.second)

    def test_corrupted_reference_denied_even_with_perfect_report(self):
        # The JSON report and the database may agree, yet an invented link
        # must still not become proof of an observed, same-simulator event.
        with sqlite3.connect(self.database) as db:
            db.execute(
                "UPDATE sim_passive_cycles SET reference_id=999 WHERE id=6")
        bad = json.loads(json.dumps(self.second))
        bad["cycles"][-1]["reference_id"] = 999
        with self.assertRaises(ValueError):
            validate_acceptance(self.database, self.first, bad)

    def test_missing_database_does_not_create_a_second_sqlite(self):
        absent = self.database.parent / "missing.sqlite3"
        with self.assertRaises(ValueError):
            validate_acceptance(absent, self.first, self.second)
        self.assertFalse(absent.exists())

    def test_verifier_is_read_only_and_does_not_invent_robot_identity(self):
        before = self.database.stat().st_size
        validate_acceptance(self.database, self.first, self.second)
        self.assertEqual(before, self.database.stat().st_size)
        with sqlite3.connect(self.database) as db:
            self.assertEqual(6, db.execute(
                "SELECT count(*) FROM sim_passive_cycles").fetchone()[0])
            self.assertEqual(0, db.execute(
                "SELECT count(*) FROM experiences").fetchone()[0])
            self.assertEqual(0, db.execute(
                "SELECT count(*) FROM intent_preferences").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
