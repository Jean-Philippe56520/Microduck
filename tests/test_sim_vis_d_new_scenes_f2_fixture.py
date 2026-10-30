"""SIM-VIS-D host fixtures. OEM MuJoCo/ONNX executed ONLY in dedicated CI."""
from __future__ import annotations

import unittest
from unittest.mock import patch

from microduck_companion.perception import DETECTION_CONFIDENCE
from microduck_companion.sim_vis_d_new_scenes_f2_fixture import (
    DISTANCE_AHEAD_M, DISTANCE_BEHIND_M, SCENE_CASES, VSLAM_ROBOT_XY,
    mock_f2_from_regions,
)


def fake_region(score: float, *, cls: int = 56) -> dict:
    return {
        "xyxy": (50., 60., 150., 160.),
        "score": score,
        "untrusted_coco_class_index": cls,
    }


class NewSceneMockF2Tests(unittest.TestCase):
    def test_independent_oem_sources_are_preregistered(self):
        self.assertEqual(
            ("flat_ball_ahead", "flat_ball_behind", "vslam_pillar"),
            tuple(x[0] for x in SCENE_CASES),
        )
        self.assertEqual(
            ("scene_ball.xml", "scene_ball.xml", "scene_vslam.xml"),
            tuple(x[1] for x in SCENE_CASES),
        )
        self.assertEqual(.62, DISTANCE_AHEAD_M)
        self.assertEqual(.70, DISTANCE_BEHIND_M)
        self.assertEqual((1.65, 1.8), VSLAM_ROBOT_XY)

    def test_one_high_confidence_unknown_region_can_cause_cognitive_inspection(self):
        # The raw COCO class 56 (chair) must NEVER promote a semantic label.
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            result = mock_f2_from_regions([fake_region(.91)])
        self.assertEqual("inspect", result["intention"])
        self.assertEqual("unknown", result["target_category"])
        self.assertEqual(1, result["eligible_score_count"])
        self.assertEqual(DETECTION_CONFIDENCE, result["f2_detection_confidence_threshold"])
        self.assertIs(result["known_category_promoted"], False)
        self.assertIs(result["sensor_source_authenticated"], False)
        self.assertEqual(0, result["motor_commands_issued"])
        self.assertEqual(0, result["experience_writes"])

    def test_model_low_confidence_is_not_scaled_up_to_fixture_threshold(self):
        for score in (.25, .50, .799999):
            with self.subTest(score=score):
                response = mock_f2_from_regions([fake_region(score)])
                self.assertEqual("idle", response["intention"])
                self.assertIsNone(response["target_category"])
                self.assertEqual([score], response["model_scores_unverified"])
                self.assertEqual(0, response["eligible_score_count"])

    def test_empty_regions_are_not_a_fabricated_object(self):
        res = mock_f2_from_regions([])
        self.assertEqual("idle", res["intention"])
        self.assertEqual([], res["model_scores_unverified"])
        self.assertEqual(0, res["motor_commands_issued"])

    def test_untrusted_and_out_of_time_snapshots_fail_closed(self):
        cases = [
            {"claimed_source": "sensor"},
            {"sample_at": 118., "now": 120.2},
            {"sample_at": 121., "now": 120.2},
        ]
        for opts in cases:
            with self.subTest(opts=opts):
                ans = mock_f2_from_regions([fake_region(.95)], **opts)
                self.assertEqual("idle", ans["intention"])
                self.assertIsNone(ans["target_category"])
                self.assertFalse(ans["sensor_source_authenticated"])
                self.assertFalse(ans["known_category_promoted"])

    def test_malformed_or_semantically_enriched_regions_are_rejected(self):
        examples = [
            [fake_region(float("nan"))],
            [fake_region(float("inf"))],
            [dict(fake_region(.95), verified_category="ball")],
            [dict(fake_region(.95), xyxy=[50., 60., 150., 160.])],
            [dict(fake_region(.95), score=True)],
            [dict(fake_region(.95), score=1.1)],
            [dict(fake_region(.95), untrusted_coco_class_index="person")],
            [fake_region(.90)] * 4,
        ]
        for bad in examples:
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    mock_f2_from_regions(bad)

    def test_no_identity_or_motion_in_model_scores_even_when_category_is_person(self):
        response = mock_f2_from_regions([fake_region(.93, cls=0)])
        self.assertEqual("inspect", response["intention"])
        self.assertEqual("unknown", response["target_category"])
        self.assertFalse(response["known_category_promoted"])
        self.assertEqual(0, response["motor_commands_issued"])


if __name__ == "__main__":
    unittest.main()
