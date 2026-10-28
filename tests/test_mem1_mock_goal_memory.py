"""MEM-1: source-labelled mock goals and reference-only attempts."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_ledger import (
    MockExperienceLedger, MockResolution,
)
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.mock_goal_memory import (
    MockGoalMemory, MAX_GOALS, MAX_LINKS_PER_GOAL, MAX_LINKS_TOTAL,
)

NOW = 1_770_000_000.0
GOAL_ID = "g-00000000000000a1"
SESSION = "s-00000000000000a1"


class MEM1MockGoalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "memory.sqlite3"
        self.mem = ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.ex1 = MockExperienceLedger(self.mem)
        self.goals = MockGoalMemory(self.mem, self.ex1)

    def create(self, key=GOAL_ID, *, kind="observe_category",
               category="ball", resume_when="new_view", at=NOW):
        return self.goals.create(
            goal_id=key, kind=kind, category=category,
            resume_when=resume_when, at_epoch_s=at,
        )

    def active(self, key=GOAL_ID):
        self.assertTrue(self.create(key))
        self.goals.transition(
            goal_id=key, expected_revision=1,
            next_state="active", reason="begin_mock_goal",
            at_epoch_s=NOW + .1,
        )

    def event(self, *, seq=1, session=SESSION, at=NOW+1,
              intention="observe", category="ball",
              status="mock_executed"):
        self.ex1.record_proposal(
            PassiveIntent(
                intention, "PRIVATE TEXT MUST NEVER LEAVE EX1",
                "object_label", category,
            ), session=session, sequence=seq, proposed_at_epoch_s=at,
        )
        if status is not None:
            self.ex1.resolve(MockResolution(
                session, seq, status, at + .5,
            ))

    def link(self, *, seq=1, session=SESSION,
             strategy="observe_from_distance", context="initial",
             at=NOW+2, goal_id=GOAL_ID):
        return self.goals.link_attempt(
            goal_id=goal_id, session=session, sequence=seq,
            strategy=strategy, context=context, at_epoch_s=at,
        )

    def test_reuses_one_connection_and_references_but_never_copies_ex1(self):
        self.active()
        self.event()
        before = self.mem.conn.execute(
            "SELECT COUNT(*) FROM ex1_mock_experiences"
        ).fetchone()[0]
        self.assertTrue(self.link())
        self.assertEqual(before, self.mem.conn.execute(
            "SELECT COUNT(*) FROM ex1_mock_experiences"
        ).fetchone()[0])
        self.assertEqual(1, self.mem.conn.execute(
            "SELECT COUNT(*) FROM mem1_mock_goal_links"
        ).fetchone()[0])
        self.assertEqual(0, self.mem.experience_count())
        self.assertEqual(0., self.mem.intent_preference("robot", "explore"))
        g = self.goals.get(GOAL_ID)
        self.assertEqual("active", g.state)
        self.assertEqual(2, g.revision)
        self.assertFalse(g.physical_completion_verified)
        self.assertEqual(0, g.motor_commands_issued)
        (a,) = self.goals.attempts(GOAL_ID)
        self.assertEqual("mock_executed", a.mock_resolution)
        self.assertEqual("active_mock_ex1", a.evidence_state)
        self.assertFalse(a.physical_execution_verified)
        self.assertFalse(a.physical_effect_verified)
        self.assertFalse(a.causality_established)
        self.assertEqual(0, a.motor_commands_issued)
        self.assertNotIn("PRIVATE", repr(g) + repr(a))

    def test_create_and_link_are_idempotent_but_conflicts_fail(self):
        self.active()
        self.assertFalse(self.create())
        with self.assertRaises(ValueError):
            self.create(category="cat")
        self.event()
        self.assertTrue(self.link())
        self.assertFalse(self.link())
        with self.assertRaises(ValueError):
            self.link(context="new_view")
        self.assertEqual(1, len(self.goals.attempts(GOAL_ID)))

    def test_suspend_restart_and_resume_only_matching_condition(self):
        self.active()
        self.event(status="refused")
        self.link()
        self.goals.transition(
            goal_id=GOAL_ID, expected_revision=2,
            next_state="suspended", reason="repeat_blocked",
            at_epoch_s=NOW+3,
        )
        self.mem.close()
        other = ExperienceMemory(self.path)
        try:
            goals = MockGoalMemory(other, MockExperienceLedger(other))
            state = goals.get(GOAL_ID)
            self.assertEqual(("suspended", "new_view", 3),
                             (state.state, state.resume_when, state.revision))
            with self.assertRaises(ValueError):
                goals.transition(
                    goal_id=GOAL_ID, expected_revision=3,
                    next_state="active", reason="new_context",
                    at_epoch_s=NOW+4,
                )
            goals.transition(
                goal_id=GOAL_ID, expected_revision=3,
                next_state="active", reason="new_view",
                at_epoch_s=NOW+4,
            )
            self.assertEqual("active", goals.get(GOAL_ID).state)
            self.assertEqual("refused", goals.attempts(GOAL_ID)[0].mock_resolution)
            self.assertEqual(4, goals.get(GOAL_ID).revision)
        finally:
            other.close()

    def test_cross_process_reopen_reads_without_other_database(self):
        self.active()
        self.event(status="interrupted")
        self.link()
        program = """
import sys
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_ledger import MockExperienceLedger
from microduck_companion.mock_goal_memory import MockGoalMemory
m=ExperienceMemory(sys.argv[1])
try:
    store=MockGoalMemory(m, MockExperienceLedger(m))
    (g,) = store.recent()
    assert g.state == 'active' and not g.physical_completion_verified
    (a,) = store.attempts(g.goal_id)
    assert a.mock_resolution == 'interrupted'
    assert not a.physical_execution_verified
finally:
    m.close()
"""
        result = subprocess.run(
            [sys.executable, "-c", program, str(self.path)],
            cwd=Path(__file__).resolve().parents[1],
            text=True, capture_output=True, timeout=15,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_retraction_cannot_reactivate_goal_even_after_reopen(self):
        self.active()
        self.assertTrue(self.goals.retract(
            goal_id=GOAL_ID, reason="source_retracted"))
        self.assertFalse(self.goals.retract(
            goal_id=GOAL_ID, reason="source_retracted"))
        self.assertIsNone(self.goals.get(GOAL_ID))
        withdrawn = self.goals.get(GOAL_ID, include_withdrawn=True)
        self.assertTrue(withdrawn.corrected)
        self.assertEqual(3, withdrawn.revision)
        with self.assertRaises(ValueError):
            self.create()
        with self.assertRaises(ValueError):
            self.goals.transition(
                goal_id=GOAL_ID, expected_revision=3,
                next_state="active", reason="new_view",
                at_epoch_s=NOW+4,
            )
        self.mem.close()
        reopened = ExperienceMemory(self.path)
        try:
            goals = MockGoalMemory(reopened, MockExperienceLedger(reopened))
            self.assertTrue(goals.get(
                GOAL_ID, include_withdrawn=True).corrected)
            self.assertEqual((), goals.recent())
            with self.assertRaises(ValueError):
                goals.create(
                    goal_id=GOAL_ID, kind="observe_category",
                    category="ball", resume_when="new_view", at_epoch_s=NOW)
        finally:
            reopened.close()

    def test_source_retraction_propagates_without_false_effect(self):
        self.active()
        self.event()
        self.link()
        self.assertTrue(self.ex1.retract(
            session=SESSION, sequence=1, reason="source_retracted"))
        (attempt,) = self.goals.attempts(GOAL_ID)
        self.assertEqual("retracted_or_untrusted_ex1", attempt.evidence_state)
        self.assertEqual("unavailable", attempt.mock_resolution)
        with self.assertRaises(ValueError):
            self.goals.transition(
                goal_id=GOAL_ID, expected_revision=2,
                next_state="mock_closed", reason="fixture_review_only",
                at_epoch_s=NOW+3,
            )
        self.assertEqual("active", self.goals.get(GOAL_ID).state)

    def test_missing_ex1_from_existing_retention_is_unknown(self):
        self.active()
        self.event()
        self.link()
        # Mimic EX1's independently owned retention: no MEM-1 deletion.
        self.mem.conn.execute("""
            DELETE FROM ex1_mock_experiences
            WHERE session=? AND sequence=?
        """, (SESSION, 1))
        self.mem.conn.commit()
        (attempt,) = self.goals.attempts(GOAL_ID)
        self.assertEqual("missing_ex1", attempt.evidence_state)
        self.assertEqual("unavailable", attempt.mock_resolution)
        with self.assertRaises(ValueError):
            self.goals.transition(
                goal_id=GOAL_ID, expected_revision=2,
                next_state="mock_closed", reason="fixture_review_only",
                at_epoch_s=NOW+4,
            )

    def test_mock_closure_is_not_verified_achievement(self):
        self.active()
        with self.assertRaises(ValueError):
            self.goals.transition(
                goal_id=GOAL_ID, expected_revision=2,
                next_state="mock_closed", reason="fixture_review_only",
                at_epoch_s=NOW+3,
            )
        self.event()
        self.link()
        self.goals.transition(
            goal_id=GOAL_ID, expected_revision=2,
            next_state="mock_closed", reason="fixture_review_only",
            at_epoch_s=NOW+3,
        )
        g = self.goals.get(GOAL_ID)
        self.assertEqual("mock_closed", g.state)
        self.assertFalse(g.physical_completion_verified)
        with self.assertRaises(ValueError):
            self.goals.transition(
                goal_id=GOAL_ID, expected_revision=3,
                next_state="active", reason="new_view",
                at_epoch_s=NOW+4,
            )

    def test_nonactive_unknown_or_unmatched_attempts_refused(self):
        self.create()
        self.event()
        with self.assertRaises(ValueError):
            self.link()
        self.goals.transition(
            goal_id=GOAL_ID, expected_revision=1,
            next_state="active", reason="begin_mock_goal",
            at_epoch_s=NOW+.1,
        )
        with self.assertRaises(ValueError):
            self.link(seq=999)
        with self.assertRaises(ValueError):
            self.link(strategy="inspect_other_view")
        with self.assertRaises(ValueError):
            self.link(context="private_person")
        self.assertTrue(self.link())
        self.goals.transition(
            goal_id=GOAL_ID, expected_revision=2,
            next_state="suspended", reason="uncertain",
            at_epoch_s=NOW+3,
        )
        with self.assertRaises(ValueError):
            self.link()

    def test_no_repeated_same_strategy_context_even_different_ex1(self):
        self.active()
        self.event(seq=1, at=NOW+1)
        self.event(seq=2, at=NOW+2, status=None)
        self.link(seq=1, at=NOW+2)
        with self.assertRaises(ValueError):
            self.link(seq=2, at=NOW+3)
        self.assertTrue(self.link(seq=2, at=NOW+3, context="new_view"))
        self.assertEqual(2, len(self.goals.attempts(GOAL_ID)))

    def test_strict_quota_no_silent_prune_or_retracted_overwrite(self):
        self.active()
        for i in range(MAX_LINKS_PER_GOAL):
            session=f"s-{i+1:016x}"
            self.event(seq=1, session=session, at=NOW+1+i, status=None)
            strategy = ("observe_from_distance" if i % 2 == 0
                        else "observe_over_time")
            context = ("initial", "new_view", "new_context", "new_evidence")[i//2]
            self.assertTrue(self.link(
                seq=1, session=session, strategy=strategy,
                context=context, at=NOW+2+i))
        session="s-000000000000ffff"
        self.event(seq=1, session=session, at=NOW+11, status=None)
        with self.assertRaises(ValueError):
            self.link(seq=1, session=session, at=NOW+12,
                      context="new_evidence")
        self.assertEqual(MAX_LINKS_PER_GOAL, len(self.goals.attempts(GOAL_ID)))
        for i in range(2, MAX_GOALS+1):
            self.assertTrue(self.create(key=f"g-{i:016x}", at=NOW+i))
        with self.assertRaises(ValueError):
            self.create(key="g-ffffffffffffffff", at=NOW+100)
        self.assertEqual(MAX_GOALS, len(self.goals.recent(limit=MAX_GOALS)))
        self.assertLessEqual(
            self.mem.conn.execute(
                "SELECT COUNT(*) FROM mem1_mock_goal_links"
            ).fetchone()[0], MAX_LINKS_TOTAL,
        )

    def test_stale_revision_illegal_state_bad_times_pii_and_other_memory(self):
        self.active()
        with self.assertRaises(ValueError):
            self.goals.transition(
                goal_id=GOAL_ID, expected_revision=1,
                next_state="suspended", reason="uncertain",
                at_epoch_s=NOW+2,
            )
        for state, reason, at in (
            ("active", "begin_mock_goal", NOW+2),
            ("mock_closed", "fixture_review_only", NOW+2),
            ("suspended", "operator_review", NOW+2),
            ("suspended", "uncertain", NOW-.1),
            ("executed_on_robot", "uncertain", NOW+2),
        ):
            with self.subTest(state=state, reason=reason), self.assertRaises(ValueError):
                self.goals.transition(
                    goal_id=GOAL_ID, expected_revision=2,
                    next_state=state, reason=reason,
                    at_epoch_s=at,
                )
        for key in ("g-privateperson", "g-" + "z" * 16, "", True):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.create(key=key)
        for kind, category in (
            ("inspect_unknown", "cat"), ("observe_category", "unknown"),
            ("observe_category", "person@example.org"), ("kick_left", "ball"),
        ):
            with self.subTest(kind=kind, category=category), self.assertRaises(ValueError):
                self.create(key="g-00000000000000f1",
                            kind=kind, category=category)
        for at in (float("nan"), float("inf"), -1, True):
            with self.subTest(at=at), self.assertRaises(ValueError):
                self.create(key="g-00000000000000f1", at=at)
        with self.assertRaises(ValueError):
            self.create(key="g-00000000000000f1", resume_when="follow_person")
        with self.assertRaises(ValueError):
            self.goals.retract(goal_id=GOAL_ID, reason="forget_evidence")
        with self.assertRaises(ValueError):
            self.goals.recent(limit=True)
        self.event()
        with self.assertRaises(ValueError):
            self.link(context="somebody@example.org")
        with self.assertRaises(ValueError):
            self.link(at=NOW+.5)
        other = ExperienceMemory(":memory:")
        self.addCleanup(other.close)
        another = MockExperienceLedger(other)
        with self.assertRaises(ValueError):
            MockGoalMemory(self.mem, another)
        self.assertEqual(0, self.mem.experience_count())


if __name__ == "__main__":
    unittest.main()
