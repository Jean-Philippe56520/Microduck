"""EX1 fixture-only experience lifecycle; never proves a physical action."""
from __future__ import annotations

from pathlib import Path
import math
import subprocess
import sys
import tempfile
import unittest

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.experience_ledger import (
    MAX_STORED, RETENTION_S, MAX_RESOLUTION_DELAY_S,
    MockExperienceLedger, MockResolution,
)

NOW = 1_770_000_000.0
SESSION = "s-0000000000000001"


def inspect(category="unknown"):
    return PassiveIntent(
        "inspect", "the fixture claims something unfamiliar",
        target_kind="object_label", target_category=category,
    )


class EX1ExperienceLedgerTests(unittest.TestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "mem.sqlite3"
        self.mem = ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.ledger = MockExperienceLedger(self.mem)

    def proposal(self, sequence=1, *, time=NOW, intent=None, session=SESSION):
        return self.ledger.record_proposal(
            intent if intent is not None else inspect(),
            session=session, sequence=sequence,
            proposed_at_epoch_s=time,
        )

    def resolve(self, sequence=1, *, time=NOW + 1,
                status="mock_executed", session=SESSION):
        return self.ledger.resolve(MockResolution(
            session, sequence, status, time,
        ))

    def test_reuses_experience_memory_and_no_new_sqlite_connection(self):
        self.assertIs(self.mem, self.ledger._memory)
        before = self.mem.conn.execute(
            "SELECT COUNT(*) FROM experiences").fetchone()[0]
        self.assertTrue(self.proposal())
        self.assertTrue(self.resolve())
        after = self.mem.conn.execute(
            "SELECT COUNT(*) FROM experiences").fetchone()[0]
        self.assertEqual(before, after)
        self.assertEqual(0.0, self.mem.intent_preference("robot", "explore"))
        (trace,) = self.ledger.history(now_wall_epoch_s=NOW+2)
        self.assertEqual("mock_executed", trace.status)
        self.assertFalse(trace.verified_on_robot)
        self.assertEqual(0, trace.motor_commands_issued)
        self.assertEqual("mock_fixture_only", trace.source)

    def test_intention_alone_never_counts_as_executed(self):
        self.assertTrue(self.proposal())
        (trace,) = self.ledger.history(now_wall_epoch_s=NOW+2)
        self.assertEqual("proposed", trace.status)
        self.assertIsNone(trace.resolved_at_epoch_s)
        self.assertFalse(trace.verified_on_robot)
        self.assertEqual("inspect", trace.intention)
        self.assertEqual("unknown", trace.target_category)

    def test_same_proposal_and_resolution_replays_are_idempotent(self):
        self.assertTrue(self.proposal())
        self.assertFalse(self.proposal())
        self.assertTrue(self.resolve())
        self.assertFalse(self.resolve())
        self.assertEqual(1, self.mem.conn.execute(
            "SELECT COUNT(*) FROM ex1_mock_experiences").fetchone()[0])
        self.assertEqual(1, len(self.ledger.history(now_wall_epoch_s=NOW+2)))

    def test_conflicting_replays_do_not_replace_history(self):
        self.proposal()
        with self.assertRaises(ValueError):
            self.proposal(intent=inspect("ball"))
        self.resolve(status="refused")
        with self.assertRaises(ValueError):
            self.resolve(status="mock_executed")
        with self.assertRaises(ValueError):
            self.resolve(status="refused", time=NOW+2)
        (trace,) = self.ledger.history(now_wall_epoch_s=NOW+2)
        self.assertEqual("refused", trace.status)

    def test_refused_interrupted_and_idle_never_train_a_motor(self):
        for i, status in enumerate(("refused", "interrupted"), 1):
            self.proposal(i, time=NOW+i)
            self.resolve(i, time=NOW+i+0.5, status=status)
        self.proposal(3, time=NOW+3, intent=PassiveIntent("idle", "nothing new"))
        statuses = {t.status for t in self.ledger.history(now_wall_epoch_s=NOW+5)}
        self.assertEqual({"refused", "interrupted", "proposed"}, statuses)
        self.assertEqual(0, self.mem.experience_count())

    def test_denies_resolution_without_proposal_and_wrong_type(self):
        with self.assertRaises(ValueError):
            self.resolve()
        with self.assertRaises(TypeError):
            self.ledger.resolve("fictional success")

    def test_denies_late_reversed_or_invalid_timestamps(self):
        self.proposal()
        for when in (NOW-1, NOW+MAX_RESOLUTION_DELAY_S+0.001):
            with self.subTest(when=when), self.assertRaises(ValueError):
                self.resolve(time=when)
        for invalid in (True, -1, float("nan"), float("inf"), "now"):
            with self.subTest(invalid=repr(invalid)), self.assertRaises(ValueError):
                self.proposal(2, time=invalid)
        self.assertEqual("proposed",
                         self.ledger.history(now_wall_epoch_s=NOW+1)[0].status)

    def test_rejects_untrusted_sources_private_ids_and_motor_claims(self):
        for session in ("Malo", "person-bob", "s-aa", "s-"+"g"*16, ""):
            with self.subTest(session=session), self.assertRaises(ValueError):
                self.proposal(session=session)
        for invalid in (0, -1, True, 1.3, "1"):
            with self.subTest(sequence=invalid), self.assertRaises(ValueError):
                self.proposal(sequence=invalid)
        with self.assertRaises(TypeError):
            self.ledger.record_proposal(
                "kick", session=SESSION, sequence=1, proposed_at_epoch_s=NOW)
        with self.assertRaises(ValueError):
            PassiveIntent(
                "inspect", "untrusted", "object_label", "ball",
                source="sensor", executed=True,
            )
        with self.assertRaises(ValueError):
            MockResolution(SESSION, 1, "mock_executed", NOW, source="robotd")
        with self.assertRaises(ValueError):
            MockResolution(SESSION, 1, "real_executed", NOW)

    def test_retraction_is_immutable_and_changes_history_not_motor(self):
        self.proposal()
        self.resolve()
        self.assertTrue(self.ledger.retract(
            session=SESSION, sequence=1, reason="source_retracted"))
        self.assertFalse(self.ledger.retract(
            session=SESSION, sequence=1, reason="source_retracted"))
        self.assertEqual((), self.ledger.history(now_wall_epoch_s=NOW+2))
        with self.assertRaises(ValueError):
            self.resolve()
        self.assertFalse(self.proposal())  # old evidence cannot be reactivated
        with self.assertRaises(ValueError):
            self.ledger.retract(
                session=SESSION, sequence=1, reason="approved_robot_action")

    def test_expiration_query_bounds_and_storage_quota(self):
        self.proposal(1, time=NOW)
        self.assertEqual((), self.ledger.history(
            now_wall_epoch_s=NOW+RETENTION_S+1))
        for i in range(MAX_STORED+2):
            self.proposal(i+2, time=NOW+1+i)
        rows = self.mem.conn.execute(
            "SELECT COUNT(*) FROM ex1_mock_experiences").fetchone()[0]
        self.assertEqual(MAX_STORED, rows)
        self.assertEqual(50, len(self.ledger.history(
            now_wall_epoch_s=NOW+MAX_STORED+10, limit=50)))
        for limit in (0, 51, True, 3.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.ledger.history(now_wall_epoch_s=NOW+3, limit=limit)

    def test_two_sqlite_connections_can_reopen_without_duplicate_events(self):
        self.proposal()
        self.resolve()
        independent = ExperienceMemory(self.path)
        try:
            other = MockExperienceLedger(independent)
            self.assertEqual("mock_executed",
                             other.history(now_wall_epoch_s=NOW+2)[0].status)
            self.assertFalse(other.record_proposal(
                inspect(), session=SESSION, sequence=1,
                proposed_at_epoch_s=NOW))
            self.assertFalse(other.resolve(
                MockResolution(SESSION, 1, "mock_executed", NOW+1)))
        finally:
            independent.close()

    def test_second_process_reads_same_sqlite_without_mock_upgrade(self):
        self.proposal()
        self.resolve()
        script = """
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_ledger import MockExperienceLedger
import sys
m=ExperienceMemory(sys.argv[1])
try:
    rows=MockExperienceLedger(m).history(now_wall_epoch_s=1770000002.0)
    assert len(rows)==1 and rows[0].status=='mock_executed'
    assert not rows[0].verified_on_robot
    assert rows[0].motor_commands_issued==0
finally:
    m.close()
"""
        completed = subprocess.run(
            [sys.executable, "-c", script, str(self.path)],
            cwd=Path(__file__).resolve().parents[1],
            check=False, text=True, capture_output=True, timeout=20,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == "__main__":
    unittest.main()
