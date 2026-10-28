"""SIM-E1 fixture tests; these DO NOT run MuJoCo or authorize robot motion."""
from __future__ import annotations

from dataclasses import replace
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from microduck_companion.autonomy import Scene
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.sim_e1_active_experience import (
    SimE1Error, compare_decisions, main, run_e1, validate_experience,
)
from microduck_companion.sim_walk_trial import WALK_SPEED_MPS, WALK_TICKS, WalkTrialResult


def scene(**changes):
    data = dict(environment="simulator", battery_pct=80, safe_area=True,
                floor_clear=True, obstacle_m=0.70, perception_valid=True)
    data.update(changes)
    return Scene(**data)


def recorded_trial(memory: ExperienceMemory, *, measured=.02, baseline=.0001,
                   healthy=True, safe=True, stop=True):
    outcome = memory.record_simulated_motion(
        measured_m=measured, baseline_m=baseline, simulated_duration_s=1.2,
        stop_confirmed=stop, healthy_after=healthy, safe_after=safe,
    )
    return WalkTrialResult(
        commands_sent=WALK_TICKS, stop_confirmed=stop,
        requested_speed_mps=WALK_SPEED_MPS,
        measured_displacement_m=measured, baseline_displacement_m=baseline,
        simulated_duration_s=1.2,
        measured_forward_x_m=measured, measured_lateral_y_m=0.,
        outcome=outcome.outcome, reward=outcome.reward, preference_before=0.,
        preference_after=outcome.updated_preference,
        next_intention="explore", trials_in_memory=outcome.observed_trials,
        memory_source=outcome.source, policy_diagnostics={"policy_samples": WALK_TICKS},
    )


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "memory.sqlite3"
        self.memory = ExperienceMemory(self.db)
        self.addCleanup(self.memory.close)

    def test_one_correlated_simulated_translation_not_a_robot_success(self):
        trial = recorded_trial(self.memory)
        decisions = compare_decisions(scene(), self.memory)
        report = validate_experience(trial, self.memory, decisions)
        self.assertEqual(1, report["sqlite_sim_motion_rows"])
        self.assertTrue(report["trial"]["stop_confirmed"])
        self.assertEqual("translation_observed", report["trial"]["outcome"])
        self.assertFalse(report["gait_validated"])
        self.assertFalse(report["real_robot_validated"])
        self.assertFalse(report["causal_effect_on_object_proven"])
        self.assertEqual(0, report["motor_commands_from_counterfactual"])
        self.assertEqual("explore", decisions["counterfactual_without_sim_preference"])
        self.assertEqual(0, self.memory.experience_count())

    def test_one_negative_result_changes_preference_but_not_necessarily_choice(self):
        trial = recorded_trial(self.memory, measured=.0002)
        report = validate_experience(
            trial, self.memory, compare_decisions(scene(), self.memory))
        self.assertEqual("no_progress_observed", trial.outcome)
        self.assertLess(report["simulated_preference_only"], 0)
        self.assertEqual("same-choice-after-one-trial", report["conclusion"])
        self.assertFalse(report["decisions"]["choice_changed"])

    def test_ambiguous_baseline_no_reward(self):
        trial = recorded_trial(self.memory, measured=.02, baseline=.006)
        report = validate_experience(
            trial, self.memory, compare_decisions(scene(), self.memory))
        self.assertEqual("inconclusive_drift", report["trial"]["outcome"])
        self.assertEqual(0, report["simulated_preference_only"])
        self.assertIsNone(report["trial"]["reward"])

    def test_unconfirmed_stop_or_bad_final_safety_cannot_pass(self):
        for kwargs in ({"stop": False}, {"healthy": False}, {"safe": False}):
            with self.subTest(kwargs=kwargs):
                local = ExperienceMemory(":memory:")
                try:
                    t = recorded_trial(local, **kwargs)
                    with self.assertRaises(SimE1Error):
                        validate_experience(t, local, compare_decisions(scene(), local))
                    self.assertEqual(0., local.intent_preference("simulator", "explore"))
                finally:
                    local.close()

    def test_tampered_reward_source_command_count_or_pose_rejected(self):
        t = recorded_trial(self.memory)
        decisions = compare_decisions(scene(), self.memory)
        for fake in (
            replace(t, memory_source="robot"),
            replace(t, commands_sent=WALK_TICKS - 1),
            replace(t, stop_confirmed=False),
            replace(t, measured_displacement_m=.99),
            replace(t, reward=1.0),
            replace(t, preference_after=.6),
            replace(t, preference_before=.1),
            replace(t, policy_diagnostics={"policy_samples": 0}),
        ):
            with self.subTest(fake=fake), self.assertRaises(SimE1Error):
                validate_experience(fake, self.memory, decisions)

    def test_repeated_episode_is_not_one_trial(self):
        t = recorded_trial(self.memory)
        recorded_trial(self.memory)
        with self.assertRaises(SimE1Error):
            validate_experience(t, self.memory, compare_decisions(scene(), self.memory))

    def test_false_counterfactual_claim_rejected(self):
        t = recorded_trial(self.memory)
        decisions = compare_decisions(scene(), self.memory)
        decisions["choice_changed"] = not decisions["choice_changed"]
        with self.assertRaises(SimE1Error):
            validate_experience(t, self.memory, decisions)

    def test_counterfactual_never_writes_or_observes_object(self):
        with self.assertRaises(SimE1Error):
            compare_decisions(scene(object_id="ball"), self.memory)
        with self.assertRaises(SimE1Error):
            compare_decisions(scene(environment="robot"), self.memory)
        with self.assertRaises(SimE1Error):
            compare_decisions(scene(person_visible=True), self.memory)
        with self.assertRaises(SimE1Error):
            compare_decisions(scene(perception_valid=False), self.memory)
        with self.assertRaises(SimE1Error):
            compare_decisions(scene(safe_area=False), self.memory)
        with self.assertRaises(SimE1Error):
            compare_decisions(scene(floor_clear=False), self.memory)
        with self.assertRaises(SimE1Error):
            compare_decisions(scene(battery_pct=10), self.memory)
        before = self.memory.conn.total_changes
        for _ in range(3):
            compare_decisions(scene(), self.memory)
        self.assertEqual(before, self.memory.conn.total_changes)
        self.assertEqual([], self.memory.simulated_motion_history())


class EntrypointTests(unittest.TestCase):
    def test_cli_disabled_by_default(self):
        with (patch.dict("os.environ", {}, clear=True),
              contextlib.redirect_stderr(io.StringIO()) as err):
            self.assertEqual(2, main([
                "--state-dir", "/nonexistent",
                "--rl-root", "/nonexistent",
                "--database", "/tmp/sim-e1-unreachable.sqlite",
                "--output", "/tmp/sim-e1-unreachable.json",
            ]))
        self.assertIn("disabled", err.getvalue())

    def test_existing_database_refuses_before_motor(self):
        with tempfile.TemporaryDirectory() as root:
            d = Path(root) / "memory.sqlite"
            d.write_bytes(b"already exists")
            with patch("microduck_companion.sim_e1_active_experience.run_walk_trial") as run:
                with self.assertRaises(SimE1Error):
                    run_e1(Path(root), Path(root), d)
                run.assert_not_called()

    def test_exactly_one_reused_trial_and_only_one_database(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            database = root / "sim-e1.sqlite3"
            calls = []
            def sim_trial(state, rl, db, *, port):
                calls.append((state, rl, db, port))
                memory = ExperienceMemory(db)
                try:
                    return recorded_trial(memory, measured=.0002)
                finally:
                    memory.close()
            snap = Mock()
            snap.to_scene.return_value = scene()
            with (patch("microduck_companion.sim_e1_active_experience.run_walk_trial",
                        side_effect=sim_trial),
                  patch("microduck_companion.sim_e1_active_experience.read_simulator_telemetry",
                        return_value=Mock()),
                  patch("microduck_companion.sim_e1_active_experience.read_verified_flat_ground",
                        return_value=Mock()),
                  patch("microduck_companion.sim_e1_active_experience.flat_zone_snapshot",
                        return_value=snap)):
                report = run_e1(root, root, database, port=17801)
            self.assertEqual(1, len(calls))
            self.assertEqual(1, report["sqlite_sim_motion_rows"])
            self.assertFalse(report["decisions"]["choice_changed"])
            self.assertTrue(database.exists())
            self.assertFalse((root / "other.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
