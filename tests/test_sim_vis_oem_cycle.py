"""SIM-1B host qualification: real data flow, fake model and OEM signals only.

No live MuJoCo/mediad run and no ONNX CPU benchmark is claimed by these tests.
"""
from __future__ import annotations

from io import BytesIO
import math
import time
import unittest

from microduck_companion.sim_bridge import SimulatorTelemetry
from microduck_companion.sim_ipc import (
    DepthReading, HealthReading, StateReading,
)
from microduck_companion.sim_media_frame import EphemeralMediaFrame, MediaFrameError
from microduck_companion.sim_vis_oem_cycle import (
    evaluate_simulated_camera_cycle, uyvy_to_upright_jpeg,
)


def frame(*, width=64, height=64, rotate=90, luma=128):
    # Neutral chroma, one value for each of the two packed Y samples.
    pixels = bytes((128, luma, 128, luma)) * (width * height // 2)
    return EphemeralMediaFrame(
        width, height, rotate, int(time.time() * 1_000_000),
        pixels, None,
    )


def coherent(now):
    return SimulatorTelemetry(
        HealthReading(True, 80.0, 50.0, 50.0, 0, now),
        StateReading(False, False, 50.0, 0, 1000, now),
        DepthReading(1, (900,) * 64, (0,) * 64, 1000, now),
    )


class FakeYolox:
    """Exactly one synthetic YOLOX proposal at ~15px; no semantic proof."""

    def __init__(self, confidence=0.94, class_index=32):
        self.confidence = confidence
        self.class_index = class_index
        self.calls = 0

    def run(self, outputs, feeds):
        import numpy as np

        self.calls += 1
        assert outputs is None
        assert feeds["images"].shape == (1, 3, 416, 416)
        raw = np.zeros((1, 3549, 85), dtype=np.float32)
        raw[0, 0, 2:4] = math.log(25.0)
        raw[0, 0, 4] = float(self.confidence)
        raw[0, 0, 5 + self.class_index] = 1.0
        return [raw]


class SimVisOemCycleTests(unittest.TestCase):
    def test_full_range_of_neutral_luma_and_mount_rotation(self):
        from PIL import Image

        for luma, expected in ((16, 0), (235, 255)):
            with self.subTest(luma=luma):
                jpeg, w, h = uyvy_to_upright_jpeg(
                    frame(width=64, height=32, rotate=90, luma=luma)
                )
                self.assertTrue(jpeg.startswith(bytes((255, 216))))
                self.assertEqual((w, h), (32, 64))
                with Image.open(BytesIO(jpeg)) as image:
                    pixel = image.convert("RGB").getpixel((16, 32))
                self.assertTrue(all(abs(v - expected) <= 2 for v in pixel))

    def test_visible_region_yields_mock_unknown_inspection(self):
        at = time.monotonic()
        model = FakeYolox(confidence=0.94, class_index=32)
        report = evaluate_simulated_camera_cycle(
            frame(), coherent(at), model, now_monotonic_s=at,
        )
        self.assertEqual(model.calls, 1)
        self.assertEqual(report["status"], "HOST_SIM_MEDIAD_PIXELS_TO_MOCK_F2")
        self.assertEqual(report["telemetry_quality"], "coherent")
        self.assertTrue(report["regions_untrusted"])
        self.assertEqual(report["f2_mock_projection"]["intention"], "inspect")
        self.assertEqual(report["f2_mock_projection"]["target_category"], "unknown")
        self.assertFalse(report["semantic_category_verified"])
        self.assertFalse(report["sensor_source_authenticated"])
        self.assertFalse(report["same_mujoco_step_verified"])
        self.assertFalse(report["memory_effect_verified"])
        self.assertFalse(report["media_written_to_disk"])
        self.assertEqual(report["motor_commands_issued"], 0)
        self.assertEqual(report["f2_mock_projection"]["experience_writes"], 0)

    def test_low_score_is_not_f2_inspection(self):
        at = time.monotonic()
        report = evaluate_simulated_camera_cycle(
            frame(), coherent(at), FakeYolox(confidence=0.50),
            now_monotonic_s=at,
        )
        self.assertEqual(report["f2_mock_projection"]["intention"], "idle")
        self.assertEqual(report["f2_mock_projection"]["eligible_score_count"], 0)

    def test_model_person_hypothesis_cannot_become_verified_person(self):
        at = time.monotonic()
        report = evaluate_simulated_camera_cycle(
            frame(), coherent(at), FakeYolox(confidence=0.93, class_index=0),
            now_monotonic_s=at,
        )
        self.assertEqual(report["regions_untrusted"][0]["untrusted_coco_class_index"], 0)
        self.assertEqual(report["f2_mock_projection"]["target_category"], "unknown")
        self.assertFalse(report["semantic_category_verified"])

    def test_telemetry_missing_blocks_image_and_model(self):
        at = time.monotonic()
        model = FakeYolox()
        report = evaluate_simulated_camera_cycle(
            frame(), SimulatorTelemetry(), model, now_monotonic_s=at,
        )
        self.assertEqual(report["status"], "STOP_UNSAFE_OR_INCOMPLETE_TELEMETRY")
        self.assertEqual(report["telemetry_quality"], "missing_stream")
        self.assertEqual(report["intention"], "idle")
        self.assertFalse(report["inference_attempted"])
        self.assertEqual(model.calls, 0)

    def test_slow_control_blocks_inference(self):
        at = time.monotonic()
        t = coherent(at)
        t = SimulatorTelemetry(
            HealthReading(True, 80.0, 50.0, 30.0, 0, at),
            t.state, t.depth,
        )
        model = FakeYolox()
        report = evaluate_simulated_camera_cycle(
            frame(), t, model, now_monotonic_s=at,
        )
        self.assertEqual(report["telemetry_quality"], "slow_control")
        self.assertEqual(model.calls, 0)

    def test_stale_telemetry_blocks_inference(self):
        at = time.monotonic()
        model = FakeYolox()
        report = evaluate_simulated_camera_cycle(
            frame(), coherent(at - 4.0), model, now_monotonic_s=at,
        )
        self.assertEqual(report["telemetry_quality"], "stale_sample")
        self.assertEqual(model.calls, 0)

    def test_truncated_image_fails_before_inference(self):
        at = time.monotonic()
        actual = frame()
        wrong = EphemeralMediaFrame(
            actual.width, actual.height, actual.rotate,
            actual.captured_at_unix_us, b"x" * 16, None,
        )
        model = FakeYolox()
        with self.assertRaises(MediaFrameError):
            evaluate_simulated_camera_cycle(
                wrong, coherent(at), model, now_monotonic_s=at,
            )
        self.assertEqual(model.calls, 0)

    def test_invalid_mount_rotation_fails_before_inference(self):
        at = time.monotonic()
        actual = frame()
        wrong = EphemeralMediaFrame(
            actual.width, actual.height, 45,
            actual.captured_at_unix_us, actual.pixels_uyvy, None,
        )
        model = FakeYolox()
        with self.assertRaises(MediaFrameError):
            evaluate_simulated_camera_cycle(
                wrong, coherent(at), model, now_monotonic_s=at,
            )
        self.assertEqual(model.calls, 0)

    def test_stale_camera_fails_before_inference(self):
        at = time.monotonic()
        actual = frame()
        wrong = EphemeralMediaFrame(
            actual.width, actual.height, actual.rotate,
            int((time.time() - 30) * 1_000_000),
            actual.pixels_uyvy, None,
        )
        model = FakeYolox()
        with self.assertRaises(MediaFrameError):
            evaluate_simulated_camera_cycle(
                wrong, coherent(at), model, now_monotonic_s=at,
            )
        self.assertEqual(model.calls, 0)


if __name__ == "__main__":
    unittest.main()
