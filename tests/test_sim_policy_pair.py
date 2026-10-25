"""P0i: simulated-only policy A/B safety, isolation, reporting and gates.

All fixtures are invented. The actual official daemon pair runs only behind
the explicit P0i CI branch switch. No unit test sends robot.move.
"""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from microduck_companion.sim_motion import SimMotionError
from microduck_companion.sim_policy_pair import (
    EXPERIMENT_ARMS, MODEL_NAMES, PINNED_V8_SHA256,
    WALK_TICKS, WALK_SPEED_MPS,
    _official_files, _read_live_policies, compare_arms,
    main, run_arm, verify_active_arm,
)
from microduck_companion.sim_walk_trial import WalkTrialResult


def fake_report(arm, *, pid=100, distance=.002, stop=True):
    walk = "alpha_walking.onnx" if arm == "alpha" else "velstand.onnx"
    stand = "alpha_stand.onnx" if arm == "alpha" else None
    return {
        "experiment": "p0i_two_independent_official_mujoco_boots",
        "arm": arm,
        "official_body_pid": pid,
        "policy": {
            "walk_model": walk, "stand_model": stand,
            "bundle_sha256": dict(PINNED_V8_SHA256),
            "selected_from_live_robotd_policy_list": True,
        },
        "stop_confirmed": stop,
        "commands_sent": WALK_TICKS,
        "requested_vx_mps": WALK_SPEED_MPS,
        "measured_xy_displacement_m": distance,
        "measured_forward_x_m": distance,
        "measured_lateral_y_m": 0.,
        "baseline_drift_m": .0002,
        "policy_feedback": {
            "policy_samples": WALK_TICKS,
            "walk_policy_samples": WALK_TICKS-1,
            "max_applied_vx_mps": .12,
        },
        "reported_outcome": ("translation_observed"
                             if distance >= .01 else "no_progress_observed"),
        "gait_validated": False,
        "root_cause": "undetermined",
    }


def fake_trial():
    return WalkTrialResult(
        commands_sent=WALK_TICKS, stop_confirmed=True,
        requested_speed_mps=WALK_SPEED_MPS,
        measured_displacement_m=.0012, baseline_displacement_m=.0002,
        simulated_duration_s=2.5,
        measured_forward_x_m=.0012, measured_lateral_y_m=0.,
        outcome="no_progress_observed", reward=-.5,
        preference_before=0., preference_after=-.05,
        next_intention="idle", trials_in_memory=1,
        memory_source="mujoco_verified_pose",
        policy_diagnostics={
            "policy_samples": WALK_TICKS,
            "walk_policy_samples": WALK_TICKS-1,
            "max_applied_vx_mps": .12,
        },
    )


class ActivePolicyTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.state = self.root / "state"
        release = self.state / "policies/releases/seed-v8"
        release.mkdir(parents=True)
        (self.state / "policies/current").symlink_to("releases/seed-v8")
        (release / ".source").write_text(
            "repo=pollen-robotics/microduck-policies\nversion=v8\n")
        (release / "manifest.json").write_text(json.dumps({
            "policies": [{"file": name} for name in MODEL_NAMES.values()]
        }))
        for n in MODEL_NAMES.values():
            (release / n).write_bytes(b"dummy-onnx" * 200)
        self.config = self.state / "robotd.toml"
        self.roles = {
            "alpha": {"walk": "alpha_walking.onnx",
                      "stand": "alpha_stand.onnx"},
            "velstand": {"walk": "velstand.onnx", "stand": None},
        }

    def write_arm(self, arm):
        names = self.roles[arm]
        release = self.state / "policies/current"
        stand = ('"' + str(release / names["stand"]) + '"'
                 if names["stand"] else '"none"')
        self.config.write_text(
            '[policy]\nenabled = true\n'
            + 'walk = "' + str(release / names["walk"]) + '"\n'
            + "stand = " + stand + "\n")

    def live(self, arm):
        names = self.roles[arm]
        rows = [
            {"slot": "walk", "path":
             str(self.state / "policies/current" / names["walk"]), "error": None},
            {"slot": "stand", "path": (
                str(self.state / "policies/current" / names["stand"])
                if names["stand"] else None), "error": None},
        ]
        return {"mode": "walk", "enabled": True, "slots": rows}

    def test_pinned_bundle_hashes_and_required_manifest(self):
        with patch("microduck_companion.sim_policy_pair._sha256_file",
                   side_effect=lambda path: PINNED_V8_SHA256[
                       next(k for k,v in MODEL_NAMES.items() if v == path.name)]):
            paths = _official_files(self.state)
        self.assertEqual(set(MODEL_NAMES), set(paths))

    def test_bad_hash_refused_before_motor(self):
        with self.assertRaisesRegex(SimMotionError, "ONNX bytes"):
            _official_files(self.state)

    def test_corrupt_missing_or_duplicate_manifest_refused(self):
        manifest = self.state / "policies/current/manifest.json"
        old = manifest.read_text()
        for payload in (
            '{"policies":[]}', '{"policies":[{"file":"velstand.onnx"}]}',
            '{"policies":[{"file":"x"},{"file":"x"}]}',
            '{"other":[]}', '{"policies":[null]}',
        ):
            manifest.write_text(payload)
            with self.subTest(payload=payload), self.assertRaises(SimMotionError):
                _official_files(self.state)
        manifest.write_text(old)

    def test_both_configs_require_matching_daemon_slots(self):
        with patch("microduck_companion.sim_policy_pair._sha256_file",
                   side_effect=lambda path: PINNED_V8_SHA256[
                       next(k for k,v in MODEL_NAMES.items() if v == path.name)]):
            for arm in ("alpha", "velstand"):
                self.write_arm(arm)
                with patch("microduck_companion.sim_policy_pair._read_live_policies",
                           return_value=self.live(arm)):
                    x = verify_active_arm(self.state, self.root, arm)
                    self.assertTrue(x["selected_from_live_robotd_policy_list"])
                    self.assertEqual(self.roles[arm]["walk"], x["walk_model"])
                    self.assertEqual(self.roles[arm]["stand"], x["stand_model"])

    def test_slot_mismatch_and_tuning_override_fail_closed(self):
        self.write_arm("velstand")
        with patch("microduck_companion.sim_policy_pair._sha256_file",
                   side_effect=lambda path: PINNED_V8_SHA256[
                       next(k for k,v in MODEL_NAMES.items() if v == path.name)]):
            with patch("microduck_companion.sim_policy_pair._read_live_policies",
                       return_value=self.live("alpha")):
                with self.assertRaises(SimMotionError):
                    verify_active_arm(self.state, self.root, "velstand")
            self.config.write_text(self.config.read_text() + "gain = 250\n")
            with patch("microduck_companion.sim_policy_pair._read_live_policies",
                       return_value=self.live("velstand")):
                with self.assertRaisesRegex(SimMotionError, "tuning override"):
                    verify_active_arm(self.state, self.root, "velstand")

    def test_invalid_or_degraded_live_policy_is_rejected(self):
        self.write_arm("alpha")
        with patch("microduck_companion.sim_policy_pair._sha256_file",
                   side_effect=lambda path: PINNED_V8_SHA256[
                       next(k for k,v in MODEL_NAMES.items() if v == path.name)]):
            bad = self.live("alpha")
            bad["slots"][0]["error"] = "load failed"
            with patch("microduck_companion.sim_policy_pair._read_live_policies",
                       return_value=bad):
                with self.assertRaises(SimMotionError):
                    verify_active_arm(self.state, self.root, "alpha")


class ControlledTrialTests(unittest.TestCase):
    def test_one_single_existing_trial_and_stop_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "body.pid").write_text("12345\n")
            record = fake_report("velstand")["policy"]
            with patch("microduck_companion.sim_policy_pair.verify_oem_sources"):
                with patch("microduck_companion.sim_policy_pair.read_sources"):
                    with patch("microduck_companion.sim_policy_pair.verify_body_process"):
                        with patch("microduck_companion.sim_policy_pair.verify_active_arm",
                                   return_value=record):
                            with patch("microduck_companion.sim_policy_pair.run_walk_trial",
                                       return_value=fake_trial()) as move:
                                result = run_arm(root, root, root, root/"memory.sqlite",
                                                 "velstand")
            move.assert_called_once()
            self.assertEqual("velstand", result["arm"])
            self.assertEqual(WALK_TICKS, result["commands_sent"])
            self.assertTrue(result["stop_confirmed"])
            self.assertFalse(result["gait_validated"])
            self.assertEqual("undetermined", result["root_cause"])

    def test_no_trial_if_config_not_verified_or_port_wrong(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with patch("microduck_companion.sim_policy_pair.verify_oem_sources",
                       side_effect=SimMotionError("unverified")):
                with patch("microduck_companion.sim_policy_pair.run_walk_trial") as move:
                    with self.assertRaises(SimMotionError):
                        run_arm(root,root,root,root/"m.sqlite","alpha")
                    with self.assertRaises(SimMotionError):
                        run_arm(root,root,root,root/"m.sqlite","alpha",port=9999)
                    move.assert_not_called()

    def test_missing_stop_or_missing_policy_stream_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/"body.pid").write_text("12345\n")
            for bad in (
                replace(fake_trial(), stop_confirmed=False),
                replace(fake_trial(), commands_sent=WALK_TICKS-1),
                replace(fake_trial(), policy_diagnostics={}),
            ):
                with patch("microduck_companion.sim_policy_pair.verify_oem_sources"):
                    with patch("microduck_companion.sim_policy_pair.read_sources"):
                        with patch("microduck_companion.sim_policy_pair.verify_body_process"):
                            with patch("microduck_companion.sim_policy_pair.verify_active_arm",
                                       return_value=fake_report("alpha")["policy"]):
                                with patch("microduck_companion.sim_policy_pair.run_walk_trial",
                                           return_value=bad):
                                    with self.subTest(bad=bad), self.assertRaises(SimMotionError):
                                        run_arm(root,root,root,root/"m.sqlite","alpha")


class ComparisonTests(unittest.TestCase):
    def test_no_progress_does_not_claim_cause_or_gait(self):
        report = compare_arms(fake_report("alpha",pid=101),
                              fake_report("velstand",pid=202,distance=.0023))
        self.assertTrue(report["both_arms_observed_requested_control"])
        self.assertEqual(48, report["motor_commands_total"])
        self.assertEqual(2, report["explicit_stop_confirmations"])
        self.assertFalse(report["causal_root_cause_proven"])
        self.assertFalse(report["velstand_exceeds_10mm_threshold"])
        self.assertFalse(report["simulated_displacement_is_not_validated_gait"] is False)

    def test_candidate_exceeds_threshold_but_gait_remains_unproven(self):
        record = compare_arms(fake_report("alpha",pid=101),
                              fake_report("velstand",pid=202,distance=.017))
        self.assertTrue(record["velstand_exceeds_10mm_threshold"])
        self.assertFalse(record["alpha_exceeds_10mm_threshold"])
        self.assertAlmostEqual(.015,record["distance_difference_velstand_minus_alpha_m"])
        self.assertFalse(record["causal_root_cause_proven"])

    def test_wrong_arm_pid_model_stop_and_numeric_values_rejected(self):
        for left, right in (
            (fake_report("velstand"),fake_report("alpha",pid=202)),
            (fake_report("alpha"),fake_report("velstand")),
            (fake_report("alpha"),fake_report("velstand",pid=202,stop=False)),
            (fake_report("alpha"),fake_report("velstand",pid=202,distance=float("nan"))),
        ):
            with self.subTest(left=left["arm"],right=right["arm"]):
                with self.assertRaises(SimMotionError):
                    compare_arms(left,right)

    def test_disconnected_policy_report_is_inconclusive(self):
        candidate = fake_report("velstand",pid=202)
        candidate["policy_feedback"]["walk_policy_samples"] = 2
        candidate["policy_feedback"]["max_applied_vx_mps"] = 0.
        report = compare_arms(fake_report("alpha"),candidate)
        self.assertFalse(report["both_arms_observed_requested_control"])
        self.assertFalse(report["causal_root_cause_proven"])

    def test_cli_refuses_motor_without_both_opt_ins(self):
        with tempfile.TemporaryDirectory() as d:
            output = Path(d)/"result.json"
            argv=["--arm","alpha","--state-dir",d,"--robot-root",d,
                  "--rl-root",d,"--memory",str(Path(d)/"memory"),
                  "--output",str(output)]
            with patch("microduck_companion.sim_policy_pair.run_arm") as motion:
                self.assertEqual(1, main(argv))
                self.assertEqual(1, main(argv+["--enable-once"]))
                motion.assert_not_called()
            self.assertFalse(output.exists())


if __name__=="__main__":
    unittest.main()
