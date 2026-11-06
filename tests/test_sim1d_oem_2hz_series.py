"""SIM-1D/A: offline timing/STOP fixtures, NOT OEM camera measurements."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from experiments.sim1d_launch_context import LaunchContextError

from experiments.sim1d_oem_2hz_series import (
    CYCLES, PERIOD_S, SUCCESS, run_series,
)
from microduck_companion.sim_media_frame import MediaFrameError


class VirtualClock:
    def __init__(self):
        self.now = 10.0

    def monotonic(self):
        return self.now

    def sleep(self, delay):
        assert 0 < delay <= PERIOD_S
        self.now += delay


def harness(*, world_case="ball", bad_quality=None, duplicate=False,
            unsafe=False, skip_frame=False, overrun=False, score=0.4,
            missing_context=False, changed_context=False, lost_context=False):
    clock = VirtualClock()
    read_calls = []
    frame_calls = []
    model_calls = []
    context_calls = []

    def verify_context(state_dir, case):
        context_calls.append((state_dir, case))
        if missing_context or (lost_context and len(context_calls) == 2):
            raise LaunchContextError("fixture launch cannot be verified")
        return {
            "source": "offline_fixture_not_OEM",
            "launch_scene_contains_ball_xml": case == "ball",
            "process_start": len(context_calls) if changed_context else 1,
        }

    def read(state_dir, *, timeout_s, hz):
        read_calls.append((str(state_dir), timeout_s, hz))
        clock.now += 0.015
        state = bad_quality if bad_quality and len(read_calls) == 2 else "coherent"
        return SimpleNamespace(
            assess=lambda *, now, max_age_s: SimpleNamespace(status=state)
        )

    def acquire(path, *, timeout_s, max_age_s):
        frame_calls.append((str(path), timeout_s, max_age_s))
        clock.now += 0.015
        if skip_frame:
            raise MediaFrameError("missing media.frame")
        stamp = 1_800_000_000_000_000 + int(clock.now * 1_000_000)
        if duplicate and len(frame_calls) == 2:
            stamp = 1_800_000_000_000_000 + int(10.030 * 1_000_000)
        return SimpleNamespace(captured_at_unix_us=stamp)

    def evaluate(frame, telemetry, session, *, now_monotonic_s):
        model_calls.append(frame.captured_at_unix_us)
        clock.now += 0.69 if overrun else 0.030
        intent = "inspect" if score > 0.8 else "idle"
        return {
            "status": "HOST_UNVERIFIED_CAMERA_FRAME_TO_MOCK_F2",
            "capture_age_s_at_decision": 0.085,
            "inference_ms_cpu_host": 15.0,
            "telemetry_quality": "coherent",
            "motor_commands_issued": 0,
            "semantic_category_verified": False,
            "sensor_source_authenticated": False,
            "same_mujoco_step_verified": False,
            "media_written_to_disk": False,
            "memory_effect_verified": False,
            "regions_untrusted": [{
                "xyxy": (0.0, 0.0, 40.0, 40.0),
                "score": float(score),
                "untrusted_coco_class_index": 25,
            }],
            "f2_mock_projection": {
                "intention": intent,
                "reason": "fixture_high_region" if score > 0.8
                          else "no_high_scoring_passive_attention",
                "target_category": "unknown" if intent == "inspect" else None,
                "sensor_source_authenticated": False,
                "known_category_promoted": False,
                "motor_commands_issued": 1 if unsafe else 0,
                "experience_writes": 0,
            },
        }

    result = run_series(
        Path("/tmp/kwipi-sim1d-fixture"), object(), world_case=world_case,
        count=CYCLES, clock=clock.monotonic, pause=clock.sleep,
        observe=read, acquire=acquire, evaluate=evaluate,
        verify_context=verify_context,
    )
    return result, read_calls, frame_calls, model_calls


class Sim1DBoundedSeriesTests(unittest.TestCase):
    def test_ball_world_ten_unique_frames_2hz_idle(self):
        report, r, f, m = harness()
        self.assertEqual(report["status"], SUCCESS)
        self.assertEqual(report["completed_cycles"], 10)
        self.assertEqual(report["unique_frame_timestamps"], 10)
        self.assertEqual(report["on_time_samples"], 10)
        self.assertTrue(report["capture_interval_criteria_met"])
        self.assertTrue(report["world_contains_ball_xml"])
        self.assertFalse(report["frame_ball_visibility_known"])
        self.assertFalse(report["pixel_gt_synchronised"])
        self.assertFalse(report["gt_eligible_for_detection_accuracy"])
        self.assertEqual(report["f2_idle_count"], 10)
        self.assertEqual(report["f2_inspect_unknown_count"], 0)
        self.assertEqual(report["motor_commands_issued"], 0)
        self.assertEqual(report["experience_writes"], 0)
        self.assertEqual(len(r), len(f))
        self.assertEqual(len(f), len(m))
        self.assertEqual({x[2] for x in r}, {10})

    def test_empty_world_still_cannot_claim_absent_category(self):
        report, *_ = harness(world_case="empty", score=0.95)
        self.assertEqual(report["status"], SUCCESS)
        self.assertFalse(report["world_contains_ball_xml"])
        self.assertEqual(report["f2_inspect_unknown_count"], 10)
        self.assertFalse(report["semantic_category_verified"])
        self.assertFalse(report["gt_eligible_for_detection_accuracy"])

    def test_duplicate_frame_immediately_stops_before_model(self):
        report, reads, frames, models = harness(duplicate=True)
        self.assertEqual(report["status"], "STOP_DUPLICATE_OR_REVERSED_FRAME")
        self.assertEqual(report["completed_cycles"], 1)
        self.assertEqual(len(frames), 2)
        self.assertEqual(len(models), 1)

    def test_slow_oem_telemetry_stops_before_camera(self):
        report, reads, frames, models = harness(bad_quality="slow_control")
        self.assertEqual(report["status"], "STOP_TELEMETRY_UNSAFE_OR_MISSING")
        self.assertEqual(report["error"]["quality"], "slow_control")
        self.assertEqual(len(reads), 2)
        self.assertEqual(len(frames), 1)
        self.assertEqual(len(models), 1)

    def test_camera_missing_stops_without_extra_model(self):
        report, reads, frames, models = harness(skip_frame=True)
        self.assertEqual(report["status"], "STOP_OEM_READER_OR_MODEL")
        self.assertEqual(report["completed_cycles"], 0)
        self.assertEqual(len(reads), 1)
        self.assertEqual(len(frames), 1)
        self.assertEqual(len(models), 0)

    def test_mock_motor_claim_triggers_critical_stop(self):
        report, reads, frames, models = harness(unsafe=True, score=0.95)
        self.assertEqual(report["status"], "STOP_UNSUPPORTED_F2_AUTHORITY")
        self.assertEqual(report["completed_cycles"], 0)
        self.assertEqual(len(reads), 1)
        self.assertEqual(len(frames), 1)
        self.assertEqual(len(models), 1)

    def test_overrun_must_not_be_called_2hz(self):
        report, reads, frames, models = harness(overrun=True)
        self.assertEqual(report["status"], "STOP_CADENCE_SLIP")
        self.assertEqual(report["completed_cycles"], 1)
        self.assertFalse(report["capture_interval_criteria_met"])
        self.assertGreater(report["error"]["start_delay_s"], 0.125)

    def test_unverified_context_stops_before_any_observation_or_inference(self):
        report, reads, frames, models = harness(missing_context=True)
        self.assertEqual(report["status"], "STOP_ACTIVE_WORLD_UNVERIFIED")
        self.assertEqual(report["completed_cycles"], 0)
        self.assertIsNone(report["world_contains_ball_xml"])
        self.assertFalse(report["launch_context_verified"])
        self.assertEqual((reads, frames, models), ([], [], []))

    def test_changed_context_never_passes_despite_ten_completed_cycles(self):
        report, reads, frames, models = harness(changed_context=True)
        self.assertEqual(report["status"], "STOP_ACTIVE_WORLD_CHANGED")
        self.assertEqual(report["completed_cycles"], 10)
        self.assertEqual(len(models), 10)
        self.assertIsNone(report["scene_xml_changed"])
        self.assertIsNone(report["world_contains_ball_xml"])
        self.assertFalse(report["launch_context_verified"])
        self.assertFalse(report["capture_interval_criteria_met"])

    def test_lost_context_preserves_previous_stop_without_promoting_world(self):
        report, *_ = harness(lost_context=True, unsafe=True)
        self.assertEqual(report["status"], "STOP_ACTIVE_WORLD_CHANGED")
        self.assertEqual(report["error"]["previous_error"]["status"],
                         "STOP_UNSUPPORTED_F2_AUTHORITY")
        self.assertIsNone(report["world_contains_ball_xml"])
        self.assertFalse(report["launch_context_verified"])

    def test_no_credit_for_invalid_case_or_diluted_sample_count(self):
        for case, count in (("video", 10), ("ball", 1), ("ball", 11)):
            with self.subTest(case=case, count=count):
                with self.assertRaises(ValueError):
                    run_series(Path("/tmp/fixture"), object(),
                               world_case=case, count=count)


if __name__ == "__main__":
    unittest.main()
