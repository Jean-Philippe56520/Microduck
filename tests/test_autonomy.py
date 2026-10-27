import tempfile
import unittest
from pathlib import Path

from microduck_companion import (
    AutonomyBrain, Motivations, Scene, ExperienceMemory,
)


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        self.memory = ExperienceMemory()
        self.brain = AutonomyBrain(self.memory)
        self.safe = dict(safe_area=True, floor_clear=True)

    def tearDown(self):
        self.memory.close()

    def test_default_is_not_safe_to_move(self):
        self.assertEqual("halt", self.brain.choose(Scene()).intention)

    def test_legacy_chosen_plans_are_not_logged_as_executed_experiences(self):
        # A proposed inspect/explore is not a robotd acknowledgement.
        self.brain.choose(Scene(**self.safe, object_id="toy", object_label="toy"))
        self.brain.choose(Scene(**self.safe))
        self.assertEqual(0, self.memory.experience_count())

    def test_floor_not_confirmed(self):
        self.assertEqual("halt", self.brain.choose(
            Scene(safe_area=True)
        ).intention)

    def test_battery_gates_decisions(self):
        self.assertEqual("rest", self.brain.choose(
            Scene(**self.safe, battery_pct=12)
        ).intention)

    def test_obstacle_gates_decisions(self):
        self.assertEqual("halt", self.brain.choose(
            Scene(**self.safe, obstacle_m=.1)
        ).intention)

    def test_new_object_asks_pc_once(self):
        scene = Scene(**self.safe, object_id="new", pc_connected=True)
        first = self.brain.choose(scene)
        self.assertEqual("inspect_object", first.intention)
        self.assertTrue(first.request_pc_analysis)
        self.assertFalse(self.brain.choose(scene).request_pc_analysis)

    def test_without_pc_continues_locally(self):
        plan = self.brain.choose(Scene(**self.safe, object_id="x"))
        self.assertEqual("inspect_object", plan.intention)
        self.assertFalse(plan.request_pc_analysis)

    def test_social_not_chatty(self):
        social = AutonomyBrain(
            self.memory, Motivations(sociability=.99, curiosity=.2)
        )
        self.assertEqual("look_at_person", social.choose(
            Scene(**self.safe, person_visible=True)
        ).intention)

    def test_exploration_when_no_event(self):
        self.assertEqual("explore", self.brain.choose(
            Scene(**self.safe)
        ).intention)

    def test_legacy_feedback_does_not_reward_unverified_proposal(self):
        self.memory.observe("ball", "ball")
        initial = self.memory.get("ball").preference
        play = self.brain.motives.play
        with self.assertRaises(PermissionError):
            self.brain.feedback("ball", "play_with_object", .8)
        self.assertEqual(initial, self.memory.get("ball").preference)
        self.assertEqual(play, self.brain.motives.play)
        self.assertEqual(0, self.memory.experience_count())

    def test_legacy_memory_rejects_valid_reward_without_execution_evidence(self):
        self.memory.observe("ball", "ball")
        with self.assertRaises(PermissionError):
            self.memory.learn_from_outcome("ball", "play_with_object", -.8)
        self.assertEqual(0., self.memory.get("ball").preference)

    def test_legacy_memory_rejects_nonfinite_and_boolean_rewards(self):
        self.memory.observe("ball", "ball")
        for reward in (float("nan"), float("inf"), True, None):
            with self.subTest(reward=reward), self.assertRaises(ValueError):
                self.memory.learn_from_outcome("ball", "play_with_object", reward)
        self.assertEqual(0, self.memory.experience_count())

    def test_llm_guess_is_marked_unverified(self):
        self.memory.observe("obj")
        self.memory.suggest_label("obj", "ball")
        self.assertEqual(
            "llm_suggestion", self.memory.get("obj").label_source
        )

    def test_sensor_overrides_llm_guess(self):
        self.memory.observe("obj")
        self.memory.suggest_label("obj", "unknown_box")
        self.memory.observe("obj", "ball")
        entity = self.memory.get("obj")
        self.assertEqual("ball", entity.label)
        self.assertEqual("sensor", entity.label_source)

    def test_memory_persists(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "test.sqlite"
            first = ExperienceMemory(path)
            first.observe("thing", "toy")
            first.close()
            second = ExperienceMemory(path)
            self.assertEqual(1, second.get("thing").sightings)
            second.close()

    def test_rejects_invalid_rewards(self):
        self.memory.observe("toy", "toy")
        with self.assertRaises(ValueError):
            self.memory.learn_from_outcome("toy", "play", 1.5)


if __name__ == "__main__":
    unittest.main()
