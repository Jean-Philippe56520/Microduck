"""SIM-VIS-F: strict, model-independent OEM geometry preflight gates."""
from __future__ import annotations

import unittest

from microduck_companion.sim_ball_segmentation_gt import BallGTError
from microduck_companion.sim_vis_f_gt_preflight import (
    BLOCKER, CUBE_FORWARD_M, HIDDEN_BALL_XY, OCCLUDED, SCENES,
    assess_cases,
)


def witness():
    cases = []
    for name, scene, _, _, geom in SCENES:
        blocked = name == OCCLUDED
        cases.append({
            "case": name,
            "scene": scene,
            "source_geom": geom,
            "static_pose_confirmed": True,
            "geom_pixels": 0 if blocked else 300,
            "geom_bbox_xyxy": None if blocked else [10, 20, 80, 140],
            "blocker_geom_pixels": 300 if blocked else None,
            "ray": {"intercepted_by_chair": True} if blocked else None,
        })
    return cases


class OEMVisibilityGateTests(unittest.TestCase):
    def test_preregistered_new_worlds_and_case_count(self):
        self.assertEqual(
            ["cube_south_living", "chair_near",
             "pillar_cyan_near", "ball_hidden_by_chair"],
            [x[0] for x in SCENES])
        self.assertEqual(3, sum(x[1] == "scene_apartment.xml" for x in SCENES))
        self.assertEqual(1, sum(x[1] == "scene_vslam.xml" for x in SCENES))
        self.assertEqual(0.45, CUBE_FORWARD_M)
        self.assertEqual((-1.55, .05), HIDDEN_BALL_XY)
        self.assertEqual("liv_chair_seat", BLOCKER)

    def test_positive_and_physically_occluded_negative_can_pass(self):
        verdict = assess_cases(witness())
        self.assertTrue(verdict["preflight_gate_met"])
        self.assertEqual(4, verdict["cases_valid"])
        self.assertEqual(0, verdict["yolox_inference_attempted"])
        self.assertEqual(0, verdict["motor_commands_issued"])
        self.assertFalse(verdict["sensor_or_robot_validated"])

    def test_invisible_positive_does_not_mask_other_case_results(self):
        rows = witness()
        rows[1]["geom_pixels"] = 0
        rows[1]["geom_bbox_xyxy"] = None
        verdict = assess_cases(rows)
        self.assertFalse(verdict["preflight_gate_met"])
        self.assertEqual(3, verdict["cases_valid"])
        self.assertIn("target_not_visible_enough",
                      verdict["case_decisions"][1]["failed_visibility_reasons"])
        self.assertTrue(verdict["case_decisions"][3][
            "valid_for_future_detector_evaluation"])

    def test_false_empty_mask_on_occluded_ball_is_not_accepted(self):
        rows = witness()
        rows[-1]["geom_pixels"] = 130
        rows[-1]["geom_bbox_xyxy"] = [10, 20, 60, 90]
        verdict = assess_cases(rows)
        self.assertFalse(verdict["preflight_gate_met"])
        self.assertIn("occluded_ball_visible",
                      verdict["case_decisions"][-1]["failed_visibility_reasons"])

    def test_occluder_and_independent_ray_are_both_required(self):
        for field, value in (
            ("blocker_geom_pixels", 0),
            ("ray", {"intercepted_by_chair": False}),
            ("ray", None),
        ):
            with self.subTest(field=field, value=value):
                rows = witness()
                rows[-1][field] = value
                verdict = assess_cases(rows)
                self.assertFalse(verdict["preflight_gate_met"])

    def test_pose_time_change_or_inconsistent_bbox_fails(self):
        rows = witness()
        rows[0]["static_pose_confirmed"] = False
        self.assertFalse(assess_cases(rows)["preflight_gate_met"])
        rows = witness()
        rows[0]["geom_bbox_xyxy"] = None
        self.assertFalse(assess_cases(rows)["preflight_gate_met"])
        rows = witness()
        rows[0]["geom_pixels"] = 0
        self.assertFalse(assess_cases(rows)["preflight_gate_met"])

    def test_missing_or_reordered_or_invalid_evidence_is_rejected(self):
        for rows in (witness()[:-1], list(reversed(witness()))):
            with self.assertRaises(BallGTError):
                assess_cases(rows)
        rows = witness()
        rows[1]["geom_pixels"] = -1
        with self.assertRaises(BallGTError):
            assess_cases(rows)
        rows = witness()
        rows[1]["geom_pixels"] = True
        with self.assertRaises(BallGTError):
            assess_cases(rows)


if __name__ == "__main__":
    unittest.main()
