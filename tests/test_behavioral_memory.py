"""F4-A: only P2a corroborated MOCK followups produce behavioral summaries."""
from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.mock_cycles import MockConsequence, MockCycleRunner
from microduck_companion.mock_cycle_demo import mock_snapshot
from microduck_companion.behavioral_memory import (
    BehavioralMemory, MAX_BIAS, RETENTION_S, STEP,
)

WALL=1_770_000_000.


class BehaviorMemoryTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db=Path(folder.name)/"brain.sqlite3"
        self.mem=ExperienceMemory(self.db)
        self.addCleanup(self.mem.close)
        self.runner=MockCycleRunner(self.mem,session="f4a-fiction")
        self.behavior=BehavioralMemory(self.mem)

    def step(self,result="positive",*,t=100.,target="toy-fiction"):
        outcome=self.runner.step(
            mock_snapshot(t,target=target),now=t+.5,
            followup=mock_snapshot(t+.4,target=target),
            consequence=MockConsequence(target,result,t+.3),
        )
        self.assertEqual("inspect_object",outcome.plan.intention)
        self.assertEqual("mock_feedback",outcome.disposition)
        return outcome.sequence

    def test_empty_behavior_memory_never_implies_execution(self):
        s=self.behavior.summary(now_wall_epoch_s=WALL)
        self.assertEqual((0,0,0.),(s.positive,s.negative,s.bias))
        self.assertFalse(s.verified_on_robot)
        self.assertEqual((0,0),(s.executed_actions,s.motor_commands_issued))
        self.assertEqual((),self.behavior.history(now_wall_epoch_s=WALL))

    def test_one_positive_mock_followup_is_small_and_historical(self):
        seq=self.step()
        self.assertTrue(self.behavior.record(
            runner=self.runner,sequence=seq,now_wall_epoch_s=WALL))
        s=self.behavior.summary(now_wall_epoch_s=WALL)
        self.assertEqual((1,0,STEP),(s.positive,s.negative,s.bias))
        self.assertEqual("explicit_mock_followup_only",s.source)
        (trace,)=self.behavior.history(now_wall_epoch_s=WALL)
        self.assertEqual("positive",trace.result)
        self.assertTrue(trace.historical_only)
        self.assertNotIn("toy-fiction",str(trace))
        self.assertEqual(0,trace.executed_actions)
        self.assertEqual(0,self.mem.intent_preference("simulator","explore"))

    def test_replayed_cycle_is_idempotent(self):
        seq=self.step()
        self.assertTrue(self.behavior.record(
            runner=self.runner,sequence=seq,now_wall_epoch_s=WALL))
        self.assertFalse(self.behavior.record(
            runner=self.runner,sequence=seq,now_wall_epoch_s=WALL))
        self.assertEqual(1,self.behavior.summary(
            now_wall_epoch_s=WALL).positive)
        self.assertEqual(1,self.mem.conn.execute(
            "SELECT COUNT(*) FROM f4a_mock_behavior_outcomes").fetchone()[0])

    def test_negative_explicit_followup_reduces_behavior_bias(self):
        a=self.step("positive",t=100.,target="toy-first")
        b=self.step("negative",t=103.,target="toy-second")
        for seq in (a,b):
            self.assertTrue(self.behavior.record(
                runner=self.runner,sequence=seq,now_wall_epoch_s=WALL))
        report=self.behavior.summary(now_wall_epoch_s=WALL)
        self.assertEqual((1,1,0.),(report.positive,report.negative,report.bias))

    def test_unverified_intention_does_not_become_success(self):
        cycle=self.runner.step(
            mock_snapshot(100.,target="toy-fiction"),now=100.1)
        self.assertEqual("unverified",cycle.disposition)
        self.assertFalse(self.behavior.record(
            runner=self.runner,sequence=cycle.sequence,
            now_wall_epoch_s=WALL))
        self.assertEqual(0.,self.behavior.summary(
            now_wall_epoch_s=WALL).bias)

    def test_blocked_motion_and_halt_are_not_rewards(self):
        first=self.runner.step(mock_snapshot(100.),now=100.1)
        second=self.runner.step(mock_snapshot(103.,safe=False),now=103.1)
        self.assertEqual("blocked_motion",first.disposition)
        self.assertEqual("halt",second.plan.intention)
        for cycle in (first,second):
            self.assertFalse(self.behavior.record(
                runner=self.runner,sequence=cycle.sequence,
                now_wall_epoch_s=WALL))
        self.assertEqual((),self.behavior.history(now_wall_epoch_s=WALL))

    def test_mock_success_does_not_train_robot_or_motor(self):
        seq=self.step()
        before=self.mem.conn.execute(
            "SELECT COUNT(*) FROM experiences").fetchone()[0]
        self.behavior.record(runner=self.runner,sequence=seq,
                             now_wall_epoch_s=WALL)
        self.assertEqual(before,self.mem.conn.execute(
            "SELECT COUNT(*) FROM experiences").fetchone()[0])
        self.assertEqual(0,self.mem.intent_preference("robot","explore"))
        self.assertFalse(self.behavior.summary(
            now_wall_epoch_s=WALL).verified_on_robot)

    def test_wrong_runner_or_another_database_is_rejected(self):
        with self.assertRaises(TypeError):
            self.behavior.record(runner="fake",sequence=1,
                now_wall_epoch_s=WALL)
        alien=ExperienceMemory()
        self.addCleanup(alien.close)
        alien_runner=MockCycleRunner(alien,session="different")
        with self.assertRaises(ValueError):
            self.behavior.record(runner=alien_runner,sequence=1,
                now_wall_epoch_s=WALL)

    def test_nonexistent_and_invalid_sequence_cannot_reward(self):
        self.assertFalse(self.behavior.record(
            runner=self.runner,sequence=23,now_wall_epoch_s=WALL))
        for invalid in (True,-1,0,1.5,"2"):
            with self.subTest(seq=invalid),self.assertRaises(ValueError):
                self.behavior.record(runner=self.runner,sequence=invalid,
                    now_wall_epoch_s=WALL)

    def test_bad_or_inconsistent_reward_from_ledger_rejected(self):
        seq=self.step()
        self.mem.conn.execute(
            "UPDATE mock_cognitive_cycles SET reward=1.0 WHERE sequence=?",
            (seq,))
        self.assertFalse(self.behavior.record(
            runner=self.runner,sequence=seq,now_wall_epoch_s=WALL))
        self.assertEqual(0.,self.behavior.summary(
            now_wall_epoch_s=WALL).bias)

    def test_original_ledger_corruption_inactivates_behavior_summary(self):
        seq=self.step()
        self.behavior.record(runner=self.runner,sequence=seq,
                             now_wall_epoch_s=WALL)
        self.mem.conn.execute(
            "UPDATE mock_cognitive_cycles SET reward=0.0 WHERE sequence=?",
            (seq,))
        self.assertEqual(0.,self.behavior.summary(
            now_wall_epoch_s=WALL).bias)
        self.assertEqual((),self.behavior.history(now_wall_epoch_s=WALL))

    def test_manual_retraction_recomputes_without_reward_replay(self):
        seq=self.step()
        self.behavior.record(runner=self.runner,sequence=seq,
                             now_wall_epoch_s=WALL)
        (trace,)=self.behavior.history(now_wall_epoch_s=WALL)
        self.assertTrue(self.behavior.retract(
            trace.mock_cycle_id,reason="fixture_annotation_error"))
        self.assertFalse(self.behavior.retract(
            trace.mock_cycle_id,reason="fixture_annotation_error"))
        self.assertEqual((),self.behavior.history(now_wall_epoch_s=WALL))
        self.assertEqual(0.,self.behavior.summary(
            now_wall_epoch_s=WALL).bias)
        self.assertFalse(self.behavior.record(
            runner=self.runner,sequence=seq,now_wall_epoch_s=WALL))

    def test_persisted_mock_outcome_survives_restart_as_mock_only(self):
        seq=self.step()
        self.behavior.record(runner=self.runner,sequence=seq,
                             now_wall_epoch_s=WALL)
        self.mem.close()
        restarted=ExperienceMemory(self.db)
        try:
            behavior=BehavioralMemory(restarted)
            s=behavior.summary(now_wall_epoch_s=WALL+1)
            self.assertEqual(1,s.positive)
            self.assertAlmostEqual(STEP,s.bias)
            self.assertFalse(s.verified_on_robot)
        finally:
            restarted.close()

    def test_no_preference_from_stale_or_pruned_behavior(self):
        seq=self.step()
        self.behavior.record(runner=self.runner,sequence=seq,
                             now_wall_epoch_s=WALL)
        self.assertEqual(0.,self.behavior.summary(
            now_wall_epoch_s=WALL+RETENTION_S+1).bias)
        self.behavior.prune(now_wall_epoch_s=WALL+RETENTION_S+1)
        self.assertEqual(0,self.mem.conn.execute(
            "SELECT COUNT(*) FROM f4a_mock_behavior_outcomes").fetchone()[0])

    def test_invalid_wall_clock_and_limits_rejected(self):
        for now in (True,-1,float("inf"),float("nan"),"yesterday"):
            with self.subTest(now=now),self.assertRaises(ValueError):
                self.behavior.summary(now_wall_epoch_s=now)
        for limit in (0,True,51):
            with self.assertRaises(ValueError):
                self.behavior.history(now_wall_epoch_s=WALL,limit=limit)
        for identity in (True,0,-1):
            with self.assertRaises(ValueError):
                self.behavior.retract(identity,reason="source_retracted")
        with self.assertRaises(ValueError):
            self.behavior.retract(1,reason="promote_to_robot")

    def test_closed_database_cannot_supply_a_motor_preference(self):
        self.mem.close()
        with self.assertRaises(sqlite3.Error):
            self.behavior.summary(now_wall_epoch_s=WALL)


if __name__=="__main__":
    unittest.main()
