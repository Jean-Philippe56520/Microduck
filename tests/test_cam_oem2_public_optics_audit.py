"""CAM-OEM-2 host-only optical calculations on published public constants."""
from __future__ import annotations

import ast
import math
from pathlib import Path
import unittest

from scripts.cam_oem2_public_optics_audit import (
    CID_CALIBRATION_BLOB_SHA, CID_WIDTH, CID_FX, TIROD_CLASS_NAMES,
    KWIPI_CATEGORIES, optical_audit, pinhole_fov_deg,
    horizontal_from_vertical_deg,
)


class CamOem2PublicOpticsTests(unittest.TestCase):
    def test_cid_pinhole_calibration_is_not_imx219_or_sim(self):
        report = optical_audit()
        self.assertAlmostEqual(report["cid_sims"]["pinhole_hfov_deg"], 79.242, places=3)
        self.assertAlmostEqual(report["cid_sims"]["pinhole_vfov_deg"], 63.568, places=3)
        self.assertAlmostEqual(report["mujoco_twin"]["pinhole_hfov_deg"], 72.734, places=3)
        self.assertAlmostEqual(report["zero3_imx219"]["nominal_vfov_deg_if_16_9"], 37.349, places=3)
        self.assertAlmostEqual(report["cid_sims"]["hfov_delta_from_zero3_nominal_deg"], 17.242, places=3)
        self.assertEqual(CID_CALIBRATION_BLOB_SHA,
                         report["source_revisions"]["cid_calibration_blob"])
        self.assertAlmostEqual(pinhole_fov_deg(CID_WIDTH, CID_FX), 79.2424406579, places=8)

    def test_tirod_low_is_lighting_and_only_chair_class_is_exact(self):
        report = optical_audit()["tirod"]
        self.assertEqual(sorted(KWIPI_CATEGORIES & TIROD_CLASS_NAMES), ["chair"])
        self.assertEqual(report["exact_kwipi_label_overlap"], ["chair"])
        self.assertTrue(report["low_means_illumination_not_camera_height"])
        self.assertFalse(report["ball_equal_to_coco_sports_ball_verified"])
        self.assertFalse(report["per_capture_camera_height_verified"])

    def test_missing_beta_geometry_never_filled_from_other_lens(self):
        report = optical_audit()
        self.assertIsNone(report["beta_gc2093"]["nominal_hfov_deg"])
        self.assertFalse(report["beta_gc2093"]["individual_unit_calibration_verified"])
        self.assertFalse(report["kwipi_robot_board_identified"])
        self.assertFalse(report["kwipi_camera_height_measured"])

    def test_no_media_license_or_benchmark_is_inferred(self):
        report = optical_audit()
        for source in ("cid_sims", "tirod"):
            self.assertFalse(report[source]["image_license_confirmed"])
        for k in ("real_camera_validated", "detection_benchmark_performed",
                  "eligible_to_claim_kwipi_camera_equivalence"):
            self.assertIs(report[k], False)
        self.assertFalse(report["cid_sims"]["five_class_box_ground_truth_confirmed"])
        self.assertFalse(report["cid_sims"]["camera_geometry_equivalent_to_kwipi"])
        self.assertFalse(report["mujoco_twin"]["camera_geometry_equivalent_to_kwipi"])

    def test_invalid_intrinsics_and_aspect_rejected(self):
        for pixel,focal in ((True, 500), (0, 500), (640, 0),
                            (640, float("nan")), (640, float("inf")),
                            (640, True), (640, -10), (8192, 400)):
            with self.subTest(pixels=pixel, focal=focal), self.assertRaises(ValueError):
                pinhole_fov_deg(pixel,focal)
        for vfov,w,h in ((45, True, 360), (float("nan"),640,360),
                         (180,640,360), (0,640,360), (45,640,0),
                         (45,640,False)):
            with self.subTest(vfov=vfov,width=w,height=h), self.assertRaises(ValueError):
                horizontal_from_vertical_deg(vfov,w,h)

    def test_pinhole_fov_dimension_semantics(self):
        self.assertAlmostEqual(pinhole_fov_deg(640,400), 77.3196165, places=6)
        self.assertAlmostEqual(horizontal_from_vertical_deg(45,640,360), 72.7343514, places=6)
        self.assertGreater(horizontal_from_vertical_deg(45,640,360),45)
        self.assertTrue(math.isfinite(optical_audit()["cid_sims"]["pinhole_hfov_deg"]))

    def test_no_active_or_privacy_sensitive_dependencies(self):
        source=Path(__file__).resolve().parents[1] / "scripts" / "cam_oem2_public_optics_audit.py"
        parsed=ast.parse(source.read_text(encoding="utf-8"))
        imports={x.module for x in ast.walk(parsed) if isinstance(x,ast.ImportFrom)}
        plain={n.name for x in ast.walk(parsed) if isinstance(x,ast.Import) for n in x.names}
        self.assertEqual(imports, {"__future__"})
        self.assertEqual(plain,{"json","math"})


if __name__=="__main__":
    unittest.main()
