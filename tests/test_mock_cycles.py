"""P2a multiple mock cognitive cycles, durable SQLite and strict evidence."""
import tempfile
from pathlib import Path
import sqlite3
import unittest

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.mock_cycles import (
    MockConsequence, MockCycleRunner,
)
from microduck_companion.mock_cycle_demo import mock_snapshot


class MockCycleTests(unittest.TestCase):
    def setUp(self):
        self.memory = ExperienceMemory()
        self.runner = MockCycleRunner(self.memory, session="test-case")

    def tearDown(self):
        self.memory.close()

    def test_offline_four_cycle_journal_blocks_all_motion(self):
        a = self.runner.step(mock_snapshot(100.), now=100.1)
        self.assertEqual(("explore", "blocked_motion"),
                         (a.plan.intention, a.disposition))
        self.assertIsNone(a.reward)
        b = self.runner.step(
            mock_snapshot(102., target="toy"), now=102.5,
            followup=mock_snapshot(102.4, target="toy"),
            consequence=MockConsequence("toy", "positive", 102.3),
        )
        self.assertEqual("inspect_object", b.plan.intention)
        self.assertEqual("mock_feedback", b.disposition)
        self.assertAlmostEqual(.06, b.preference_after)
        c = self.runner.step(mock_snapshot(104., safe=False), now=104.1)
        self.assertEqual("halt", c.plan.intention)
        d = self.runner.step(mock_snapshot(106., target="toy"), now=106.1)
        self.assertEqual("blocked_motion", d.disposition)
        self.assertEqual("play_with_object", d.plan.intention)
        self.assertEqual([1, 2, 3, 4],
                         [v["sequence"] for v in self.runner.history()])
        self.assertEqual(["mock"]*4,
                         [v["source"] for v in self.runner.history()])
        self.assertAlmostEqual(.06, self.memory.get("toy").preference)
        # An intention is not execution: never invoke robotd or an actuator.
        self.assertTrue(all(
            v["disposition"] != "mock_feedback"
            for v in self.runner.history() if v["intention"] in
            {"explore", "play_with_object", "halt"}
        ))

    def test_persists_both_memory_and_cycle_sequence_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "local.sqlite3"
            mem = ExperienceMemory(db)
            first = MockCycleRunner(mem, session="session-a")
            first.step(mock_snapshot(50., target="toy"), now=50.5,
                       followup=mock_snapshot(50.4, target="toy"),
                       consequence=MockConsequence("toy", "positive", 50.3))
            assert mem.get("toy").preference > 0
            mem.close()
            restarted = ExperienceMemory(db)
            try:
                runner = MockCycleRunner(restarted, session="session-a")
                self.assertEqual(2, runner.sequence)
                self.assertEqual("inspect_object", runner.brain.previous_intention)
                self.assertAlmostEqual(.06, restarted.get("toy").preference)
                result = runner.step(mock_snapshot(60., safe=False), now=60.1)
                self.assertEqual("halt", result.plan.intention)
                self.assertEqual(2, len(runner.history()))
                self.assertAlmostEqual(.06, restarted.get("toy").preference)
            finally:
                restarted.close()

    def test_implicit_reobservation_never_gives_a_reward(self):
        c = self.runner.step(mock_snapshot(10., target="toy"), now=10.1)
        self.assertEqual("unverified", c.disposition)
        self.assertEqual(0., self.memory.get("toy").preference)
        self.assertEqual(1, len(self.runner.history()))

    def test_bad_corroboration_never_changes_preferences(self):
        cases = [
            (mock_snapshot(12.4), MockConsequence("toy", "positive", 12.3)),
            (mock_snapshot(15.0, target="toy"),
             MockConsequence("toy", "positive", 12.3)),
            (mock_snapshot(12.4, target="other"),
             MockConsequence("toy", "positive", 12.3)),
            (mock_snapshot(12.4, target="toy"),
             MockConsequence("toy", "positive", 12.5)),
        ]
        for followup, consequence in cases:
            with self.subTest(consequence=consequence, followup=followup):
                with self.assertRaises(ValueError):
                    self.runner.step(
                        mock_snapshot(12., target="toy"), now=15.,
                        followup=followup, consequence=consequence,
                    )
        self.assertEqual([], self.runner.history())
        self.assertIsNone(self.memory.get("toy"))

    def test_mock_source_strictly_required(self):
        from microduck_companion.perception import PerceptionSnapshot, PerceptionEvent
        external = PerceptionSnapshot("simulator", (), 100.)
        with self.assertRaises(ValueError):
            self.runner.step(external, now=100.1)
        mixed = PerceptionSnapshot(
            "mock", (
                PerceptionEvent("object_label", "toy", "llm_suggestion",
                                100., 1., 1., track_id="x"),
            ), 100.,
        )
        with self.assertRaises(ValueError):
            self.runner.step(mixed, now=100.1)
        self.assertEqual([], self.runner.history())

    def test_missing_or_expired_safety_halts_on_next_cycle(self):
        self.runner.step(mock_snapshot(100.), now=100.1)
        halted = self.runner.step(mock_snapshot(103.), now=105.)
        self.assertEqual("halt", halted.plan.intention)
        self.assertEqual("observation_only", halted.disposition)
        self.assertIsNone(halted.reward)

    def test_missing_explicit_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            self.runner.step(mock_snapshot(100., target="toy"), now=100.1,
                             consequence=MockConsequence(
                                 "toy", "positive", 100.05))
        with self.assertRaises(ValueError):
            self.runner.step(mock_snapshot(100., target="toy"), now=100.1,
                             followup=mock_snapshot(100.05, target="toy"))
        self.assertEqual([], self.runner.history())

    def test_duplicate_journal_cycle_never_rewards_twice(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "shared.sqlite3"
            mem1 = ExperienceMemory(db)
            mem2 = ExperienceMemory(db)
            try:
                first = MockCycleRunner(mem1, session="same-session")
                stale = MockCycleRunner(mem2, session="same-session")
                first.step(mock_snapshot(20., target="toy"), now=20.5,
                           followup=mock_snapshot(20.4, target="toy"),
                           consequence=MockConsequence("toy", "positive", 20.3))
                before = mem2.get("toy").preference
                # The other runner selected its plan from an outdated memory
                # state; make inspection win so the atomic UNIQUE constraint,
                # rather than the motor-feedback gate, is tested.
                stale.brain.motives.play = 0.
                with self.assertRaises(sqlite3.IntegrityError):
                    stale.step(mock_snapshot(21., target="toy"), now=21.5,
                               followup=mock_snapshot(21.4, target="toy"),
                               consequence=MockConsequence("toy", "positive", 21.3))
                self.assertAlmostEqual(before, mem2.get("toy").preference)
            finally:
                mem1.close()
                mem2.close()

    def test_negative_fictional_feedback_and_separate_source(self):
        cycle = self.runner.step(
            mock_snapshot(55., target="unknown-toy"), now=55.5,
            followup=mock_snapshot(55.4, target="unknown-toy"),
            consequence=MockConsequence("unknown-toy", "negative", 55.3),
        )
        self.assertEqual(-.4, cycle.reward)
        self.assertAlmostEqual(-.06, self.memory.get("unknown-toy").preference)
        self.assertEqual("mock", self.runner.history()[0]["source"])

    def test_wrong_or_invalid_consequence_never_authorizes_motor(self):
        for make in (
            lambda: MockConsequence("toy", "fabricated", 99.3),
            lambda: MockConsequence("toy", "positive", 99.3, source="llm_suggestion"),
            lambda: MockConsequence("", "positive", 99.3),
        ):
            with self.assertRaises(ValueError):
                make()
        self.runner.step(mock_snapshot(101.), now=101.1)
        self.assertEqual("no_motor_command_issued",
                         self.runner.history()[0]["outcome"])


if __name__ == "__main__":
    unittest.main()
