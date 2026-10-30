"""SIM-VIS-E: positive/negative predeclared gate tests, no camera or PC."""
from __future__ import annotations

import importlib.util
import unittest

from microduck_companion.sim_ball_segmentation_gt import BallGTError
from microduck_companion.sim_vis_e_multi_object_occlusion import (
    CASES, NON_BALL, POSITIVES, OCCLUDED, BLOCKER_GEOM,
    CUBE_FORWARD_M, LIVING_ROBOT_XY, VSLAM_ROBOT_XY,
    SIDE_BALL_XY, HIDDEN_BALL_XY, assess_gate, ray_blocker,
)

HAS_NUMPY = importlib.util.find_spec("numpy") is not None
HAS_MUJOCO = importlib.util.find_spec("mujoco") is not None


def report(*, good_nonball=True, good_ball=True):
    cases = []
    for i, (name, scene, target) in enumerate(CASES):
        occluded = name == OCCLUDED
        hit = ((name == NON_BALL[0] and good_nonball)
               or (name == "ball_beside_chair" and good_ball))
        region = {"region_count": 0 if occluded else 1,
                  "best_target_iou": None if occluded else (.84 if hit else .12),
                  "target_located_iou50": bool(hit)}
        cases.append({
            "case": name,
            "oem_scene": scene,
            "target_gt_visible_pixels": 0 if occluded else 100,
            "target_gt_bbox": None if occluded else [10, 20, 40, 50],
            "geom_ray_occlusion_oracle": ({
                "ball_mask_empty": True,
                "chair_physically_intercepts_ray": True,
                "occluder_visible_pixels": 101,
            } if occluded else None),
            "regions_top1_top3_top5": {
                str(cap): dict(region) for cap in (1, 3, 5)
            },
            "f2_fixture": {
                "fixture_source": "mock_fixture_unix_host_projection_only",
                "known_category_promoted": False,
                "sensor_source_authenticated": False,
                "motor_commands_issued": 0,
                "experience_writes": 0,
                "intention": "inspect" if hit else "idle",
            },
        })
    return cases


class SIMVISEContractTests(unittest.TestCase):
    def test_predeclared_scenes_and_positions_do_not_reuse_ball_only_views(self):
        self.assertEqual(
            ["box_corridor", "chair_living", "pillar_yellow",
             "ball_beside_chair", "ball_behind_chair"],
            [c[0] for c in CASES],
        )
        self.assertEqual(3, len(NON_BALL))
        self.assertEqual(4, len(POSITIVES))
        self.assertEqual(("scene_apartment.xml", "scene_vslam.xml"),
                         tuple(dict.fromkeys(c[1] for c in CASES)))
        self.assertEqual("liv_chair_seat", BLOCKER_GEOM)
        self.assertEqual(0.52, CUBE_FORWARD_M)
        self.assertEqual((-2.90, 0.05), LIVING_ROBOT_XY)
        self.assertEqual((1.90, -4.10), VSLAM_ROBOT_XY)
        self.assertEqual((-1.70, 0.45), SIDE_BALL_XY)
        self.assertEqual((-1.70, 0.05), HIDDEN_BALL_XY)

    def test_success_requires_new_nonball_region_plus_another_positive(self):
        result = assess_gate(report())
        self.assertTrue(result["preregistered_gate_met"])
        self.assertEqual(1, result["nonball_hits_top3_iou50"])
        self.assertEqual(2, result["all_positive_hits_top3_iou50"])

    def test_ball_only_success_fails_transfer_gate(self):
        result = assess_gate(report(good_nonball=False, good_ball=True))
        self.assertFalse(result["preregistered_gate_met"])
        self.assertEqual(0, result["nonball_hits_top3_iou50"])

    def test_nonball_only_success_fails_total_positive_gate(self):
        result = assess_gate(report(good_nonball=True, good_ball=False))
        self.assertFalse(result["preregistered_gate_met"])
        self.assertEqual(1, result["all_positive_hits_top3_iou50"])

    def test_inconsistent_geom_ray_or_visible_occluded_ball_is_rejected(self):
        for field, value in (
            ("chair_physically_intercepts_ray", False),
            ("occluder_visible_pixels", 5),
            ("ball_mask_empty", False),
        ):
            with self.subTest(field=field):
                sample = report()
                sample[-1]["geom_ray_occlusion_oracle"][field] = value
                with self.assertRaisesRegex(BallGTError, "occlusion"):
                    assess_gate(sample)
        sample = report()
        sample[-1]["target_gt_visible_pixels"] = 10
        with self.assertRaisesRegex(BallGTError, "occlusion"):
            assess_gate(sample)

    def test_wrong_oracle_falsification_or_missing_case_is_rejected(self):
        for rows in (report()[:-1], list(reversed(report()))):
            with self.assertRaises(BallGTError):
                assess_gate(rows)
        sample = report()
        sample[0]["target_gt_visible_pixels"] = 2
        with self.assertRaisesRegex(BallGTError, "visibility"):
            assess_gate(sample)

    def test_lying_about_iou_greater_than_half_is_rejected(self):
        sample = report()
        sample[0]["regions_top1_top3_top5"]["3"]["best_target_iou"] = 0.12
        # Decision still says matched, which contradicts independent overlap.
        with self.assertRaisesRegex(BallGTError, "IoU"):
            assess_gate(sample)

    def test_mock_f2_must_not_promote_category_or_motor_effect(self):
        for key, bad in (
            ("known_category_promoted", True),
            ("sensor_source_authenticated", True),
            ("motor_commands_issued", 1),
            ("experience_writes", 1),
            ("intention", "walk"),
            ("fixture_source", "oem_sensor"),
        ):
            with self.subTest(key=key):
                sample = report()
                sample[0]["f2_fixture"][key] = bad
                with self.assertRaisesRegex(BallGTError, "mock F2"):
                    assess_gate(sample)

    @unittest.skipUnless(HAS_NUMPY and HAS_MUJOCO, "numpy and mujoco optional in general Python CI")
    def test_ray_oracle_rejects_nonfinite_coordinates(self):
        with self.assertRaises(BallGTError):
            ray_blocker(None, None, camera_xyz=[0., 0., 0.],
                        target_xyz=[float("nan"), 0., 1.],
                        blocker_id=2)


if __name__ == "__main__":
    unittest.main()
