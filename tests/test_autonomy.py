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

    def test_feedback_affects_preference(self):
        self.memory.observe("ball", "ball")
        old = self.memory.get("ball").preference
        updated = self.brain.feedback("ball", "play_with_object", .8)
        self.assertGreater(updated, old)

    def test_llm_guess_is_marked_unverified(self):
        self.memory.observe("obj")
        self.memory.suggest_label("obj", "ball")
        self.assertEqual(
            "llm_suggestion", self.memory.get("obj").label_source
        )

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
