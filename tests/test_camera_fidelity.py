"""Host-only camera metadata gates: synthetic declarations; no media or hardware."""
from __future__ import annotations

from dataclasses import replace
import ast
from pathlib import Path
import unittest

from microduck_companion.camera_fidelity import (
    CameraDeclaration, MEDIA_QUALITY_MODES, OEM_SHA, SIM_SHA, SIM_DEFAULT,
    assess_camera_fidelity, reference_camera,
)


def zero3(**overrides):
    fields = dict(
        source="oem_mediad", width=1280, height=720,
        board="zero3", sensor="imx219", rotate_metadata_deg=90,
        media_quality="720p30", intrinsics_source="family",
        horizontal_fov_deg=62.0, optical_center_height_mm=180,
        height_method="ruler_at_optical_center",
    )
    fields.update(overrides)
    return CameraDeclaration(**fields)


class CameraFidelityTests(unittest.TestCase):
    def test_pinned_profiles_and_default_mediad_ladder(self):
        self.assertEqual("942e58e3", OEM_SHA[:8])
        self.assertEqual("b02fdea4", SIM_SHA[:8])
        self.assertEqual(("imx219", 90, 62.0), reference_camera("zero3"))
        self.assertEqual(("gc2093", 0, None), reference_camera("beta"))
        self.assertEqual((1280, 720, 30), MEDIA_QUALITY_MODES["720p30"])
        self.assertEqual((640, 360, 15), SIM_DEFAULT)
        for value in ("unknown", "microduck", "zero3-imx219", None, True):
            with self.subTest(board=value), self.assertRaises(ValueError):
                reference_camera(value)

    def test_nominal_zero3_declaration_cannot_certify_robot(self):
        verdict = assess_camera_fidelity(zero3(), target_board="zero3")
        self.assertEqual("declared_oem_metadata_consistent_only", verdict.status)
        self.assertEqual((), verdict.blockers)
        self.assertTrue(verdict.declared_low_height)
        self.assertTrue(verdict.declared_oem_metadata_match)
        self.assertEqual(90, verdict.expected_rotate_metadata_deg)
        self.assertFalse(verdict.robot_hardware_verified)
        self.assertFalse(verdict.real_camera_performance_verified)

    def test_target_variant_not_inferred_from_apparent_sensor(self):
        verdict = assess_camera_fidelity(zero3(), target_board=None)
        self.assertIn("target_board_not_identified", verdict.blockers)
        self.assertFalse(verdict.declared_oem_metadata_match)
        with self.assertRaises(ValueError):
            assess_camera_fidelity(zero3(), target_board="auto")

    def test_board_sensor_and_rotation_have_separate_failure_causes(self):
        cases = (
            ("beta", "capture_board_mismatch_or_unknown"),
            (None, "capture_board_mismatch_or_unknown"),
            ("gc2093", "capture_sensor_mismatch_or_unknown"),
            (None, "capture_sensor_mismatch_or_unknown"),
            (0, "camera_rotation_metadata_mismatch_or_unknown"),
            (None, "camera_rotation_metadata_mismatch_or_unknown"),
        )
        for value, expected in cases:
            field = ("board" if expected.startswith("capture_board") else
                     "sensor" if expected.startswith("capture_sensor") else
                     "rotate_metadata_deg")
            with self.subTest(field=field, value=value):
                verdict = assess_camera_fidelity(
                    replace(zero3(), **{field: value}), target_board="zero3")
                self.assertIn(expected, verdict.blockers)
                self.assertFalse(verdict.declared_oem_metadata_match)

    def test_fov_not_silently_transplanted_to_beta(self):
        beta = replace(
            zero3(), board="beta", sensor="gc2093",
            rotate_metadata_deg=0, horizontal_fov_deg=None,
            intrinsics_source="none")
        blocked = assess_camera_fidelity(beta, target_board="beta")
        self.assertIn("horizontal_fov_unreported", blocked.blockers)
        supplied = replace(beta, horizontal_fov_deg=74.0, intrinsics_source="family")
        self.assertIn("beta_requires_per_unit_intrinsics",
                      assess_camera_fidelity(supplied, target_board="beta").blockers)
        declared = replace(supplied, intrinsics_source="robot")
        verdict = assess_camera_fidelity(declared, target_board="beta")
        self.assertEqual("declared_oem_metadata_consistent_only", verdict.status)
        self.assertIsNone(verdict.reference_horizontal_fov_deg)
        self.assertFalse(verdict.robot_hardware_verified)

    def test_mediad_modes_and_sensor_frame_not_conflated(self):
        good = replace(zero3(), width=640, height=360, media_quality="360p30")
        self.assertTrue(assess_camera_fidelity(
            good, target_board="zero3").declared_oem_metadata_match)
        bad = replace(zero3(), width=640, height=360)
        self.assertIn("media_quality_geometry_mismatch", assess_camera_fidelity(
            bad, target_board="zero3").blockers)
        missing = replace(zero3(), media_quality=None)
        self.assertIn("media_quality_unreported", assess_camera_fidelity(
            missing, target_board="zero3").blockers)

    def test_nominal_intrinsics_and_optical_height_are_only_declarations(self):
        scenarios = (
            (dict(horizontal_fov_deg=None), "horizontal_fov_unreported"),
            (dict(horizontal_fov_deg=45.0), "nominal_fov_does_not_match_oem_reference"),
            (dict(intrinsics_source="none"), "unusable_intrinsics_provenance"),
            (dict(optical_center_height_mm=None), "low_optical_center_height_not_documented"),
            (dict(optical_center_height_mm=301), "low_optical_center_height_not_documented"),
            (dict(optical_center_height_mm=99), "low_optical_center_height_not_documented"),
            (dict(height_method="unknown"), "low_optical_center_height_not_documented"),
        )
        for fields, reason in scenarios:
            with self.subTest(fields=fields):
                verdict = assess_camera_fidelity(
                    replace(zero3(), **fields), target_board="zero3")
                self.assertIn(reason, verdict.blockers)
                self.assertFalse(verdict.robot_hardware_verified)

    def test_public_and_operator_images_never_assume_oem_equivalence(self):
        for source in ("public_still", "operator_still"):
            with self.subTest(source=source):
                declared = replace(zero3(), source=source, media_quality=None)
                verdict = assess_camera_fidelity(declared, target_board="zero3")
                self.assertIn("not_a_declared_oem_mediad_capture", verdict.blockers)
                self.assertFalse(verdict.declared_oem_metadata_match)

    def test_sim_camera_uses_vertical_45_degrees_not_imx219_hfov(self):
        sim = CameraDeclaration(
            source="mujoco", width=640, height=360,
            intrinsics_source="sim")
        verdict = assess_camera_fidelity(sim, target_board="zero3")
        self.assertIn("mujoco_virtual_camera_not_a_physical_camera", verdict.blockers)
        self.assertGreater(verdict.sim_horizontal_fov_deg, 70)
        self.assertLess(verdict.sim_horizontal_fov_deg, 75)
        self.assertNotEqual(verdict.sim_horizontal_fov_deg, 62.0)
        self.assertFalse(verdict.declared_oem_metadata_match)

    def test_malformed_numeric_enum_and_provenance_rejected(self):
        for field, bad in (
            ("width", True), ("width", 0), ("height", 0),
            ("horizontal_fov_deg", float("nan")),
            ("horizontal_fov_deg", float("inf")),
            ("horizontal_fov_deg", True),
            ("horizontal_fov_deg", 180),
            ("optical_center_height_mm", True),
            ("optical_center_height_mm", -1),
            ("rotate_metadata_deg", 45),
            ("media_quality", "640x360"),
            ("intrinsics_source", "trusted_by_qwen"),
            ("source", "user_live_camera"),
            ("height_method", "measured_by_llm"),
        ):
            with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                replace(zero3(), **{field: bad})
        with self.assertRaises(ValueError):
            replace(zero3(), source="public_still")
        with self.assertRaises(TypeError):
            assess_camera_fidelity({}, target_board="zero3")

    def test_no_sensor_motor_sqlite_or_network_dependencies(self):
        source = Path(__file__).resolve().parents[1] / "microduck_companion" / "camera_fidelity.py"
        parsed = ast.parse(source.read_text(encoding="utf-8"))
        names = {node.module for node in ast.walk(parsed)
                 if isinstance(node, ast.ImportFrom)}
        plain = {alias.name for node in ast.walk(parsed)
                 if isinstance(node, ast.Import)
                 for alias in node.names}
        self.assertEqual({"__future__", "dataclasses"}, names)
        self.assertEqual({"math"}, plain)
        self.assertNotIn("robotd", source.read_text(encoding="utf-8").split("import"))


if __name__ == "__main__":
    unittest.main()
