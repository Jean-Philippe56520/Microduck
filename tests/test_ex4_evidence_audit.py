"""EX4-A: provenance-only checks. All fixtures, never actual robot receipts."""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import sqlite3
import tempfile
import unittest

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.behavioral_memory import BehavioralMemory
from microduck_companion.experience_ledger import MockExperienceLedger, MockResolution
from microduck_companion.experience_effects import (
    MockCue, MockEffectJournal, MockEffectPair,
)
from microduck_companion.ex4_evidence_audit import ExecutionEvidenceAudit
from microduck_companion.mock_cycles import MockCycleRunner
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.sim_passive_cycles import PassiveSimCycleRunner

WALL = 1_780_000_000.0


class Ex4EvidenceAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "kwipi.sqlite3"
        self.memory = ExperienceMemory(self.db)
        self.addCleanup(self.memory.close)
        self.audit = ExecutionEvidenceAudit(self.memory)

    def proposal(self, *, session: str = "s-0000000000000001",
                 status: str = "mock_executed",
                 after: str | None = "moving",
                 competing: bool = False,
                 same_scene: bool = True) -> None:
        ledger = MockExperienceLedger(self.memory)
        self.assertTrue(ledger.record_proposal(
            PassiveIntent("observe", "fiction only", "object_label", "ball"),
            session=session, sequence=1, proposed_at_epoch_s=WALL,
        ))
        if status != "proposed":
            self.assertTrue(ledger.resolve(MockResolution(
                session, 1, status, WALL + 1,
            )))
        if status == "mock_executed" and after is not None:
            effects = MockEffectJournal(ledger)
            self.assertTrue(effects.record(MockEffectPair(
                session, 1,
                MockCue("motion", "still", WALL - .5, .9),
                MockCue("motion", after, WALL + 1.5, .9),
                same_scene, competing,
            )))

    @staticmethod
    def no_robot(verdict) -> None:
        assert verdict.authorized == "not_attested"
        assert verdict.verified_on_robot is False
        assert verdict.causality_established is False
        assert verdict.physical_learning_allowed is False

    def test_only_one_existing_sqlite_no_creation_on_audit(self):
        names = tuple(r[0] for r in self.memory.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ))
        changes = self.memory.conn.total_changes
        self.assertIs(self.audit._memory, self.memory)
        self.assertEqual("missing", self.audit.review_ex1(
            session="s-0000000000000001", sequence=1,
        ).status)
        self.assertEqual("missing", self.audit.review_p2a(
            session="unit", sequence=1,
        ).status)
        self.assertEqual("missing", self.audit.review_sim_passive(
            session="unit", sequence=1,
        ).status)
        self.assertEqual("missing", self.audit.review_sim_motion(
            trial_id=1,
        ).status)
        self.assertEqual("missing", self.audit.review_legacy_action(
            action_id=1,
        ).status)
        self.assertEqual(changes, self.memory.conn.total_changes)
        self.assertEqual(names, tuple(r[0] for r in self.memory.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )))

    def test_ex1_proposed_and_refused_are_never_executions(self):
        self.proposal(status="proposed")
        v = self.audit.review_ex1(
            session="s-0000000000000001", sequence=1,
        )
        self.assertEqual(("proposed", "not_attested"), (v.status, v.executed))
        self.no_robot(v)
        self.memory.close()
        self.memory = ExperienceMemory(self.db)
        self.addCleanup(self.memory.close)
        self.audit = ExecutionEvidenceAudit(self.memory)
        # Reopen real SQLite, no transient verdict cache.
        v = self.audit.review_ex1(
            session="s-0000000000000001", sequence=1,
        )
        self.assertEqual("proposed", v.status)
        self.no_robot(v)

    def test_ex1_mock_execution_without_effect_is_only_scripted(self):
        self.proposal(after=None)
        v = self.audit.review_ex1(
            session="s-0000000000000001", sequence=1,
        )
        self.assertEqual("mock_resolution_only", v.status)
        self.assertEqual("scripted_mock_only", v.executed)
        self.assertEqual("not_attested", v.observed)
        self.no_robot(v)

    def test_ex2_temporal_change_not_causal(self):
        self.proposal()
        v = self.audit.review_ex1(
            session="s-0000000000000001", sequence=1,
        )
        self.assertEqual("mock_temporal_only", v.status)
        self.assertEqual("synthetic_cue", v.observed)
        self.assertEqual("changed", v.effect)
        self.no_robot(v)

    def test_ex2_confounded_not_a_reward(self):
        self.proposal(competing=True)
        v = self.audit.review_ex1(
            session="s-0000000000000001", sequence=1,
        )
        self.assertEqual("mock_confounded", v.status)
        self.no_robot(v)

    def test_ex2_unchanged_not_a_reward(self):
        self.proposal(after="still")
        v = self.audit.review_ex1(
            session="s-0000000000000001", sequence=1,
        )
        self.assertEqual("mock_unchanged", v.status)
        self.assertEqual("unchanged", v.effect)
        self.no_robot(v)

    def test_ex2_different_scene_inconclusive(self):
        self.proposal(same_scene=False)
        v = self.audit.review_ex1(
            session="s-0000000000000001", sequence=1,
        )
        self.assertEqual("mock_indeterminate", v.status)
        self.no_robot(v)

    def test_rejected_and_interrupted_ex1(self):
        for i, status in enumerate(("refused", "interrupted"), 1):
            s = "s-" + format(i, "016x")
            self.proposal(session=s, status=status, after=None)
            v = self.audit.review_ex1(session=s, sequence=1)
            self.assertEqual(status, v.status)
            self.assertEqual("not_attested", v.executed)
            self.no_robot(v)

    def test_retracted_ex1_remains_historical_but_never_valid(self):
        session = "s-0000000000000001"
        self.proposal()
        self.assertTrue(MockExperienceLedger(self.memory).retract(
            session=session, sequence=1, reason="source_retracted",
        ))
        v = self.audit.review_ex1(session=session, sequence=1)
        self.assertEqual("withdrawn", v.status)
        self.assertTrue(v.corrected)
        self.no_robot(v)
        self.assertEqual(1, self.memory.conn.execute(
            "SELECT count(*) FROM ex1_mock_experiences"
        ).fetchone()[0])

    def test_retracted_ex2_keeps_parent_history(self):
        session = "s-0000000000000001"
        self.proposal()
        effects = MockEffectJournal(MockExperienceLedger(self.memory))
        self.assertTrue(effects.retract(
            session=session, sequence=1, reason="fixture_annotation_error",
        ))
        v = self.audit.review_ex1(session=session, sequence=1)
        self.assertEqual("withdrawn_effect", v.status)
        self.assertTrue(v.corrected)
        self.no_robot(v)
        self.assertEqual(1, self.memory.conn.execute(
            "SELECT count(*) FROM ex2_mock_effects"
        ).fetchone()[0])

    def test_tampered_ex2_is_refused(self):
        self.proposal()
        with self.memory.conn:
            self.memory.conn.execute(
                "UPDATE ex2_mock_effects SET after_value='still'"
            )
        v = self.audit.review_ex1(
            session="s-0000000000000001", sequence=1,
        )
        self.assertEqual("invalid_provenance", v.status)
        self.no_robot(v)

    def test_simulator_passive_no_action(self):
        PassiveSimCycleRunner(self.memory, session="simulation")
        with self.memory.conn:
            self.memory.conn.execute("""
                INSERT INTO sim_passive_cycles(
                    session,sequence,observed_at,quality,intention,disposition,
                    source,outcome,reward,motor_commands
                ) VALUES ('simulation',1,?,'coherent','halt','blocked',
                          'simulator_ipc','no_action_executed',NULL,0)
            """, (WALL,))
        v = self.audit.review_sim_passive(session="simulation", sequence=1)
        self.assertEqual("no_action_executed", v.status)
        self.assertEqual("simulated_telemetry", v.observed)
        self.no_robot(v)
        with self.memory.conn:
            self.memory.conn.execute(
                "UPDATE sim_passive_cycles SET quality='invalid_or_missing'"
            )
        self.no_robot(self.audit.review_sim_passive(
            session="simulation", sequence=1,
        ))

    def test_mujoco_pose_and_reward_stay_simulator_only(self):
        self.memory.record_simulated_motion(
            measured_m=.02, baseline_m=0., simulated_duration_s=1.,
            stop_confirmed=True, healthy_after=True, safe_after=True,
        )
        v = self.audit.review_sim_motion(trial_id=1)
        self.assertEqual("simulated_effect_only", v.status)
        self.assertEqual("simulated_pose", v.observed)
        self.assertEqual("translation_observed", v.effect)
        self.no_robot(v)
        self.assertEqual(0., self.memory.intent_preference(
            "robot", "explore"
        ))
        # The original simulator-specific score remains untouched.
        self.assertGreater(self.memory.intent_preference(
            "simulator", "explore"
        ), 0)

    def test_mujoco_unverified_flags_never_reward(self):
        self.memory.record_simulated_motion(
            measured_m=.02, baseline_m=0., simulated_duration_s=1.,
            stop_confirmed=False, healthy_after=True, safe_after=True,
        )
        v = self.audit.review_sim_motion(trial_id=1)
        self.assertEqual("simulated_inconclusive", v.status)
        self.no_robot(v)

    def test_mujoco_inconsistent_record_is_refused(self):
        self.memory.record_simulated_motion(
            measured_m=.02, baseline_m=0., simulated_duration_s=1.,
            stop_confirmed=True, healthy_after=True, safe_after=True,
        )
        with self.memory.conn:
            self.memory.conn.execute(
                "UPDATE sim_motion_trials SET reward=-.5"
            )
        v = self.audit.review_sim_motion(trial_id=1)
        self.assertEqual("invalid_provenance", v.status)
        self.no_robot(v)

    def test_p2a_mock_reward_is_not_physical(self):
        MockCycleRunner(self.memory, session="fixture")
        with self.memory.conn:
            self.memory.conn.execute("""
                INSERT INTO mock_cognitive_cycles(
                    session,sequence,observed_at,intention,target,
                    disposition,outcome,reward,source
                ) VALUES ('fixture',1,?,'inspect_object','object_anon',
                          'mock_feedback','explicit_mock_positive',.4,'mock')
            """, (WALL,))
        v = self.audit.review_p2a(session="fixture", sequence=1)
        self.assertEqual("mock_feedback_only", v.status)
        self.assertEqual("synthetic_followup", v.observed)
        self.no_robot(v)
        with self.memory.conn:
            self.memory.conn.execute(
                "UPDATE mock_cognitive_cycles SET reward=-.4"
            )
        v = self.audit.review_p2a(session="fixture", sequence=1)
        self.assertEqual("invalid_provenance", v.status)
        self.no_robot(v)

    def test_f4a_retraction_revokes_visible_mock_followup(self):
        MockCycleRunner(self.memory, session="fixture")
        BehavioralMemory(self.memory)
        with self.memory.conn:
            self.memory.conn.execute("""
                INSERT INTO mock_cognitive_cycles(
                    session,sequence,observed_at,intention,target,
                    disposition,outcome,reward,source
                ) VALUES ('fixture',1,?,'inspect_object','object_anon',
                          'mock_feedback','explicit_mock_positive',.4,'mock')
            """, (WALL,))
            self.memory.conn.execute("""
                INSERT INTO f4a_mock_behavior_outcomes(
                    mock_cycle_id,outcome,source,recorded_epoch_s,
                    active,correction_reason
                ) VALUES (1,'positive','explicit_mock_followup_only',?,0,
                          'source_retracted')
            """, (WALL,))
        v = self.audit.review_p2a(session="fixture", sequence=1)
        self.assertEqual("withdrawn_mock_followup", v.status)
        self.assertTrue(v.corrected)
        self.no_robot(v)
        # Correction marks a historical row instead of deleting it.
        self.assertEqual(1, self.memory.conn.execute(
            "SELECT count(*) FROM f4a_mock_behavior_outcomes"
        ).fetchone()[0])

    def test_p2a_malformed_reward_is_invalid_not_exception(self):
        MockCycleRunner(self.memory, session="fixture")
        with self.memory.conn:
            self.memory.conn.execute("""
                INSERT INTO mock_cognitive_cycles(
                    session,sequence,observed_at,intention,target,
                    disposition,outcome,reward,source
                ) VALUES ('fixture',1,?,'inspect_object','object_anon',
                          'mock_feedback','explicit_mock_positive','bogus','mock')
            """, (WALL,))
        v = self.audit.review_p2a(session="fixture", sequence=1)
        self.assertEqual("invalid_provenance", v.status)
        self.no_robot(v)

    def test_legacy_history_is_never_an_authenticated_receipt(self):
        self.memory.record_action("explore", note="historical")
        self.assertEqual(1, self.memory.experience_count())
        v = self.audit.review_legacy_action(action_id=1)
        self.assertEqual("legacy_unverifiable", v.status)
        self.no_robot(v)
        with self.assertRaises(PermissionError):
            self.memory.learn_from_outcome("toy", "explore", .5)
        self.assertEqual(1, self.memory.experience_count())

    def test_invalid_keys_refused_without_writes(self):
        cases = (
            lambda: self.audit.review_ex1(session="../secret", sequence=1),
            lambda: self.audit.review_ex1(
                session="s-0000000000000001", sequence=True,
            ),
            lambda: self.audit.review_sim_motion(trial_id=True),
            lambda: self.audit.review_sim_passive(
                session="two/path", sequence=1,
            ),
            lambda: self.audit.review_legacy_action(action_id=0),
        )
        changes = self.memory.conn.total_changes
        for call in cases:
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()
        self.assertEqual(changes, self.memory.conn.total_changes)

    def test_all_results_have_no_physical_learnable_fields(self):
        safe_fields = {f.name for f in fields(
            self.audit.review_legacy_action(action_id=1)
        )}
        self.assertTrue({
            "verified_on_robot", "causality_established",
            "physical_learning_allowed",
        } <= safe_fields)


if __name__ == "__main__":
    unittest.main()
