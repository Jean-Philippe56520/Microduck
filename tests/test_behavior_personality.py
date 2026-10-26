"""Read-only OEM 16-state personality portrait on private fictional fixtures."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.behavior_personality import (
    BehaviorPortrait, HISTORICAL_OEM_STATES, DESCRIPTIVE_ONLY,
    behavior_catalog,
)
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.mock_social_cues import (
    MockSocialComposer, MockSocialContext, MockSocialPlan,
)
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_learning import PassiveLearning
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot

WALL = 1_780_000_000.0


def scene(category="ball", *, t=100., seq=1, kind="object_label",
          source="mock", channel="mock_fixture_unix", status="ok"):
    event = PerceptionEvent(kind, category, source, t, 1., .96,
                            track_id="disposable-track" if kind == "object_label" else None)
    return PassiveRead(status, PerceptionSnapshot("mock", (event,), t), seq, channel)


class BehaviorPortraitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "existing.sqlite"
        self.memory = ExperienceMemory(self.path)
        self.addCleanup(self.memory.close)
        self.journal = PassiveObservationJournal(self.memory)
        self.brain = AutonomyBrain(self.memory)

    def describe(self, intent, **opts):
        return self.brain.describe_behavior(
            intent, journal=self.journal, now_wall_epoch_s=WALL, **opts,
        )

    def test_historical_catalog_exactly_sixteen_not_sixteen_active_skills(self):
        self.assertEqual(16, len(HISTORICAL_OEM_STATES))
        self.assertEqual(16, len(set(HISTORICAL_OEM_STATES)))
        self.assertEqual({"Chill", "LookAround", "Nap", "BallPlay"}, DESCRIPTIVE_ONLY)
        catalog = dict(behavior_catalog())
        self.assertEqual(set(HISTORICAL_OEM_STATES), set(catalog))
        self.assertEqual("requires_oem_m9_or_sensor_review", catalog["Held"])
        self.assertEqual("requires_oem_m9_or_sensor_review", catalog["Startle"])
        self.assertEqual("mock_description_only", catalog["BallPlay"])

    def test_existing_brain_decides_and_portrait_only_describes(self):
        reading = scene()
        decision = self.brain.propose_balanced_passive(
            reading, journal=self.journal,
            now_monotonic_s=100.1, now_wall_epoch_s=WALL,
        )
        self.assertEqual("observe", decision.intention)
        before = self.memory.conn.total_changes
        portrait = self.describe(decision)
        self.assertEqual("LookAround", portrait.state)
        self.assertEqual("curious", portrait.affect)
        self.assertEqual("new_category", portrait.familiarity)
        self.assertEqual(0, portrait.category_observations)
        self.assertEqual(before, self.memory.conn.total_changes)
        self.assertFalse(portrait.executed)
        self.assertFalse(portrait.physical_execution_authorized)
        self.assertEqual(0, portrait.motor_commands_issued)
        self.assertEqual(0, portrait.speaker_commands_issued)

    def test_history_after_restart_changes_f2_choice_without_second_memory(self):
        first = scene()
        result = self.brain.propose_balanced_passive(
            first, journal=self.journal,
            now_monotonic_s=100.1, now_wall_epoch_s=WALL)
        self.assertEqual("observe", result.intention)
        self.assertEqual(1, self.journal.append(
            first, now_monotonic_s=100.1, now_wall_epoch_s=WALL))
        self.memory.close()
        restored = ExperienceMemory(self.path)
        self.addCleanup(restored.close)
        old_journal = PassiveObservationJournal(restored)
        new_brain = AutonomyBrain(restored)
        second = scene(t=105., seq=2)
        remembered = new_brain.propose_balanced_passive(
            second, journal=old_journal,
            now_monotonic_s=105.1, now_wall_epoch_s=WALL + 10)
        self.assertEqual("idle", remembered.intention)
        portrait = new_brain.describe_behavior(
            remembered, journal=old_journal,
            now_wall_epoch_s=WALL + 10)
        self.assertEqual("Chill", portrait.state)
        self.assertEqual(1, old_journal.category_count(
            "object_label", "ball", now_wall_epoch_s=WALL + 10))
        self.assertFalse(portrait.executed)
        # Historical familiarity is category-level only; never ball instance ID.

    def test_recalled_category_count_and_attention_bias_are_descriptive(self):
        reading = scene("bark", kind="sound_label")
        self.assertEqual(1, self.journal.append(
            reading, now_monotonic_s=100.1, now_wall_epoch_s=WALL))
        learning = PassiveLearning(self.memory)
        selected = PassiveIntent(
            "listen", "fictional_sound_category", "sound_label", "bark")
        before = self.memory.conn.total_changes
        portrait = self.describe(selected, learning=learning)
        self.assertEqual(("LookAround", "attentive"),
                         (portrait.state, portrait.affect))
        self.assertEqual(("seen_once", 1),
                         (portrait.familiarity, portrait.category_observations))
        self.assertEqual(0.0, portrait.attention_bias)
        self.assertEqual(before, self.memory.conn.total_changes)

    def test_existing_f4_social_cue_maps_to_ballplay_only_as_description(self):
        self.brain.motives.play = 0.91
        composer = MockSocialComposer(self.brain, self.journal)
        plan = composer.propose(scene(), context=MockSocialContext(
            operator_opt_in=True, supervised=True, privacy_reviewed=True,
            quiet_mode=False, play_invitation_opt_in=True),
            now_monotonic_s=100.1, now_wall_epoch_s=WALL)
        self.assertEqual("play_cue", plan.kind)
        before = self.memory.conn.total_changes
        portrait = self.describe(plan)
        self.assertEqual(("BallPlay", "playful"),
                         (portrait.state, portrait.affect))
        self.assertFalse(portrait.executed)
        self.assertEqual(0, portrait.motor_commands_issued)
        self.assertEqual(before, self.memory.conn.total_changes)
        self.assertEqual(1, composer.count_proposals())

    def test_silence_rest_and_unrecognized_cues_cannot_act(self):
        outcomes = [
            (PassiveIntent("rest", "low_simulated_motivational_energy"), "Nap"),
            (PassiveIntent("idle", "no_current_observation"), "Chill"),
            (MockSocialPlan("silence", "default"), "Chill"),
            (MockSocialPlan("rest", "default"), "Nap"),
        ]
        for proposal, expected in outcomes:
            with self.subTest(proposal=proposal):
                p = self.describe(proposal)
                self.assertEqual(expected, p.state)
                self.assertFalse(p.physical_execution_authorized)
                self.assertEqual(0, p.pc_requests_issued)

    def test_cross_database_memory_and_learning_rejected(self):
        alien = ExperienceMemory()
        self.addCleanup(alien.close)
        other_journal = PassiveObservationJournal(alien)
        other_learning = PassiveLearning(alien)
        with self.assertRaises(ValueError):
            self.brain.describe_behavior(
                PassiveIntent("idle", "mock"), journal=other_journal,
                now_wall_epoch_s=WALL)
        with self.assertRaises(ValueError):
            self.describe(PassiveIntent("idle", "mock"),
                          learning=other_learning)

    def test_stale_or_missing_history_cannot_claim_familiarity(self):
        self.memory.close()
        p = self.describe(PassiveIntent(
            "observe", "mock", "object_label", "ball"))
        self.assertEqual(("Chill", "quiet", "unavailable"),
                         (p.state, p.affect, p.familiarity))
        self.assertEqual(0, p.category_observations)
        self.assertEqual(0, p.motor_commands_issued)

    def test_unbounded_or_forged_output_rejected(self):
        p = self.describe(PassiveIntent("idle", "mock"))
        with self.assertRaises(ValueError):
            BehaviorPortrait(p.state, p.affect, p.dominant_motivation,
                             p.familiarity, 0, 0.0, p.reason,
                             motor_commands_issued=1)
        with self.assertRaises(ValueError):
            BehaviorPortrait("Zoomies", p.affect, p.dominant_motivation,
                             p.familiarity, 0, 0.0, p.reason)
        with self.assertRaises(TypeError):
            self.describe({"intention": "wander"})
        with self.assertRaises(ValueError):
            self.brain.describe_behavior(
                PassiveIntent("idle", "mock"), journal=self.journal,
                now_wall_epoch_s=float("nan"))

    def test_motivation_changes_affect_without_writing_rewards(self):
        p = PassiveIntent("idle", "no_new_safe_passive_attention")
        self.brain.motives.caution = 0.76
        portrait = self.describe(p)
        self.assertEqual("watchful", portrait.affect)
        self.assertNotEqual("Petted", portrait.state)
        self.assertEqual(0, self.memory.conn.execute(
            "SELECT COUNT(*) FROM experiences").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
