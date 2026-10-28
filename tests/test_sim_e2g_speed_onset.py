"""SIM-E2G simulated-only onset test: guards and reports, no motor or model."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.sim_motion import SimMotionError
from microduck_companion.sim_walk_trial import (
    ONSET_PROBE_SPEED_MPS, ONSET_PROBE_TICKS, WALK_TICKS, WalkTrialResult,
)
from microduck_companion.sim_policy_pair import PINNED_V8_SHA256
from microduck_companion.sim_e2g_speed_onset import main, run_probe


def fake_trial(*, m=.075, applied=.30, limits=None):
    return WalkTrialResult(
        commands_sent=ONSET_PROBE_TICKS, stop_confirmed=True,
        requested_speed_mps=ONSET_PROBE_SPEED_MPS,
        measured_displacement_m=m, baseline_displacement_m=.0003,
        simulated_duration_s=2.85,
        measured_forward_x_m=m-.0003, measured_lateral_y_m=.0003,
        outcome="translation_observed", reward=.5,
        preference_before=0., preference_after=.075,
        next_intention="explore", trials_in_memory=1,
        memory_source="mujoco_verified_pose",
        policy_diagnostics={
            "policy_samples": ONSET_PROBE_TICKS,
            "walk_policy_samples": ONSET_PROBE_TICKS - 1,
            "stand_policy_samples": 1,
            "max_applied_vx_mps": applied,
            "max_requested_vx_mps": .30,
            "limited_by": [] if limits is None else limits,
        },
    )


class SpeedOnsetGateTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.state = self.root / "sim"
        self.robot = self.root / "microduck"
        self.rl = self.root / "microduck_rl"
        for p in (self.state, self.robot, self.rl):
            p.mkdir()
        self.memory = self.state / "sim-e2g-disposable.sqlite3"
        self.output = self.state / "sim-e2g-report.json"

    def arm(self):
        return {
            "walk_model": "alpha_walking.onnx",
            "stand_model": "alpha_stand.onnx",
            "selected_from_live_robotd_policy_list": True,
            "bundle_sha256": dict(PINNED_V8_SHA256),
        }

    def patched(self, *, arm=None, trial=None):
        import contextlib
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for target in ("verify_oem_sources", "read_sources", "verify_body_process"):
            stack.enter_context(patch(
                "microduck_companion.sim_e2g_speed_onset." + target
            ))
        stack.enter_context(patch(
            "microduck_companion.sim_e2g_speed_onset.verify_active_arm",
            return_value=self.arm() if arm is None else arm,
        ))
        mover = stack.enter_context(patch(
            "microduck_companion.sim_e2g_speed_onset.run_walk_trial",
            return_value=fake_trial() if trial is None else trial,
        ))
        return mover

    def test_measured_030_translation_is_sim_only_not_a_gait(self):
        move = self.patched()
        data = run_probe(self.state, self.robot, self.rl, self.memory)
        move.assert_called_once()
        self.assertEqual(ONSET_PROBE_SPEED_MPS, move.call_args.kwargs["speed_mps"])
        self.assertEqual(ONSET_PROBE_TICKS, move.call_args.kwargs["ticks"])
        self.assertEqual(.075, data["net_xy_displacement_m"])
        self.assertEqual(.30, data["sampled_policy"]["max_applied_vx_mps"])
        self.assertEqual("simulated_translation_above_10mm_not_gait", data["verdict"])
        self.assertTrue(data["over_10mm_signal"])
        self.assertFalse(data["gait_validated"])
        self.assertFalse(data["root_cause_proven"])
        self.assertTrue(data["stop_confirmed"])
        self.assertEqual(ONSET_PROBE_TICKS, data["commands_sent"])
        self.assertTrue(data["disposable_memory_only_not_product_experience"])
        self.assertNotIn("reward", data)
        self.assertNotIn("next_intention", data)
        self.assertFalse(self.memory.exists())  # mock hasn't written

    def test_unchanged_policy_bytes_and_live_slots_are_preconditions(self):
        for invalid in (
            {**self.arm(), "walk_model": "velstand.onnx"},
            {**self.arm(), "stand_model": None},
            {**self.arm(), "bundle_sha256": {}},
            {**self.arm(), "selected_from_live_robotd_policy_list": False},
        ):
            with self.subTest(invalid=invalid):
                move = self.patched(arm=invalid)
                with self.assertRaisesRegex(SimMotionError, "model identity"):
                    run_probe(self.state, self.robot, self.rl, self.memory)
                move.assert_not_called()

    def test_bad_isolation_or_port_denied_before_motion(self):
        move = self.patched()
        for wrong in (
            self.root / "product.sqlite3",
            self.state / "arbitrary.sqlite",
        ):
            with self.subTest(wrong=str(wrong)), self.assertRaises(SimMotionError):
                run_probe(self.state, self.robot, self.rl, wrong)
        with self.assertRaises(SimMotionError):
            run_probe(self.state, self.robot, self.rl, self.memory, port=40000)
        self.memory.write_bytes(b"old")
        with self.assertRaisesRegex(SimMotionError, "stale"):
            run_probe(self.state, self.robot, self.rl, self.memory)
        move.assert_not_called()

    def test_control_limitation_or_small_motion_is_inconclusive(self):
        for t, verdict in (
            (fake_trial(m=.001), "no_10mm_translation_observed"),
            (fake_trial(m=.07, applied=.10), "control_inconclusive"),
            (fake_trial(m=.07, limits=["deadman"]), "control_inconclusive"),
            (replace(fake_trial(), policy_diagnostics={"policy_samples": ONSET_PROBE_TICKS}),
             "control_inconclusive"),
        ):
            with self.subTest(verdict=verdict):
                move = self.patched(trial=t)
                data = run_probe(self.state, self.robot, self.rl, self.memory)
                self.assertEqual(verdict, data["verdict"])
                self.assertFalse(data["gait_validated"])
                self.assertFalse(data["over_10mm_signal"])
                move.assert_called_once()

    def test_failed_stop_or_incomplete_stream_never_generates_report(self):
        bad_cases = (
            replace(fake_trial(), stop_confirmed=False),
            replace(fake_trial(), commands_sent=10),
            replace(fake_trial(), requested_speed_mps=.12),
            replace(fake_trial(), policy_diagnostics={"policy_samples": 2}),
        )
        for trial in bad_cases:
            with self.subTest(trial=trial):
                self.patched(trial=trial)
                with self.assertRaises(SimMotionError):
                    run_probe(self.state, self.robot, self.rl, self.memory)
                self.assertFalse(self.output.exists())

    def args(self, output=None):
        return [
            "--state-dir", str(self.state),
            "--robot-root", str(self.robot),
            "--rl-root", str(self.rl),
            "--memory", str(self.memory),
            "--output", str(output or self.output),
            "--enable-once",
        ]

    def test_cli_refuses_without_optin_or_bad_output_path_before_trial(self):
        with patch("microduck_companion.sim_e2g_speed_onset.run_probe") as run:
            with patch.dict("os.environ", {}, clear=True):
                self.assertEqual(2, main(self.args()))
                run.assert_not_called()
            with patch.dict("os.environ", {"MICRODUCK_SIM_E2G": "YES"}):
                bad = self.root / "outside.json"
                self.assertEqual(1, main(self.args(bad)))
                run.assert_not_called()

    def test_cli_success_writes_only_one_approved_diagnostic(self):
        sample = {"verdict": "no_10mm_translation_observed", "speed_mps": .30,
                  "net_xy_displacement_m": .001, "forward_x_m": .001,
                  "baseline_drift_m": .0003,
                  "sampled_policy": {
                      "policy_samples": ONSET_PROBE_TICKS, "walk_policy_samples": ONSET_PROBE_TICKS - 1,
                      "max_applied_vx_mps": .30, "limited_by": [],
                  }, "stop_confirmed": True}
        with patch.dict("os.environ", {"MICRODUCK_SIM_E2G": "YES"}):
            with patch("microduck_companion.sim_e2g_speed_onset.run_probe",
                       return_value=sample) as move:
                self.assertEqual(0, main(self.args()))
                move.assert_called_once()
                self.assertEqual(sample["verdict"],
                                 json.loads(self.output.read_text())["verdict"])
                self.assertEqual(1, len(list(self.state.glob("*.json"))))


if __name__ == "__main__":
    unittest.main()
