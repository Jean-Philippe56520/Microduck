"""CAM-OEM-2: source-pinned optical geometry, OFFLINE and HOST ONLY.

Numbers are transcribed from published OEM and CID-SIMS sources with their
GitHub revision identifiers. The calculation is descriptive, not a lens
calibration, license grant, annotation audit or eligibility certificate.
No images, downloads, robot, inference, filesystem or motors are accessed.
"""
from __future__ import annotations

import json
import math

OEM_SHA = "942e58e3aa6dbb28e7037203fff11866122c7567"
RL_SHA = "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3"
CID_SITE_SHA = "9e7610abf8320062cf810484dd0fc4fdb58682ae"
CID_CALIBRATION_BLOB_SHA = "52daae23d4d9daf65fb40e73dddc6e1a145290a9"
TIROD_CODE_SHA = "ca74712c857e63956e608626c3ab0967a6373522"

# CID-SIMS calibration/calibration.yaml, cam_width/height and cam_k (fx/fy).
CID_WIDTH = 640
CID_HEIGHT = 480
CID_FX = 386.52199190267083
CID_FY = 387.32300428823663
# CID overview: approximate camera view heights for the wheeled robot.
CID_APPROX_VIEW_HEIGHTS_MM = (120, 260)

# Pinned OEM mediad/sensor.rs and mediad/camera.rs: family/nominal, not unit.
ZERO3_IMX219_NOMINAL_HFOV_DEG = 62.0
# Pinned OEM mediad/camera.rs: MuJoCo MJCF default 45 deg vertical.
TWIN_SIM_VFOV_DEG = 45.0
TWIN_IMAGE_SIZE = (640, 360)

# Pinned TiROD_code/eclod/cfg/TiROD.yml; no automatic semantic equivalence.
TIROD_CLASS_NAMES = frozenset({
    "bag", "bottle", "cardboard box", "chair", "potted plant",
    "traffic cone", "trashcan", "ball", "broom", "garden hose",
    "bucket", "bycicle", "gardening tool",
})
KWIPI_CATEGORIES = frozenset({"person", "cat", "dog", "chair", "sports_ball"})


def pinhole_fov_deg(pixels: int, focal_px: float) -> float:
    """Pinhole angle only: no distortion, per-image calibration, or crop model."""
    if (type(pixels) is not int or not 1 <= pixels <= 4096
            or type(focal_px) not in (int, float)
            or not math.isfinite(focal_px) or focal_px <= 0):
        raise ValueError("finite pixel geometry and positive focal length required")
    return math.degrees(2 * math.atan(pixels / (2 * focal_px)))


def horizontal_from_vertical_deg(vfov_deg: float, width: int, height: int) -> float:
    """Horizontal pinhole field from a vertical field and frame aspect."""
    if (type(vfov_deg) not in (int, float)
            or not math.isfinite(vfov_deg) or not 0 < vfov_deg < 179
            or type(width) is not int or not 1 <= width <= 4096
            or type(height) is not int or not 1 <= height <= 4096):
        raise ValueError("invalid field or aspect")
    return math.degrees(2 * math.atan(
        (width / height) * math.tan(math.radians(vfov_deg) / 2)
    ))


def optical_audit() -> dict:
    """Published geometry alone MUST NEVER yield a validated robot verdict."""
    cid_h = pinhole_fov_deg(CID_WIDTH, CID_FX)
    cid_v = pinhole_fov_deg(CID_HEIGHT, CID_FY)
    sim_h = horizontal_from_vertical_deg(TWIN_SIM_VFOV_DEG, *TWIN_IMAGE_SIZE)
    imx_v = math.degrees(2 * math.atan(
        (720 / 1280) * math.tan(math.radians(ZERO3_IMX219_NOMINAL_HFOV_DEG) / 2)
    ))
    exact_overlap = sorted(KWIPI_CATEGORIES & TIROD_CLASS_NAMES)
    return {
        "scope": "offline_published_geometry_not_robot_performance",
        "source_revisions": {
            "oem": OEM_SHA, "rl": RL_SHA, "cid_site": CID_SITE_SHA,
            "cid_calibration_blob": CID_CALIBRATION_BLOB_SHA,
            "tirod_code": TIROD_CODE_SHA,
        },
        "zero3_imx219": {
            "nominal_hfov_deg": ZERO3_IMX219_NOMINAL_HFOV_DEG,
            "nominal_vfov_deg_if_16_9": round(imx_v, 3),
            "individual_unit_calibration_verified": False,
        },
        "beta_gc2093": {
            "nominal_hfov_deg": None,
            "individual_unit_calibration_verified": False,
        },
        "cid_sims": {
            "frame": [CID_WIDTH, CID_HEIGHT],
            "source_sensor": "intel_realsense_d455",
            "pinhole_hfov_deg": round(cid_h, 3),
            "pinhole_vfov_deg": round(cid_v, 3),
            "nominal_height_mm_approximately": list(CID_APPROX_VIEW_HEIGHTS_MM),
            "hfov_delta_from_zero3_nominal_deg": round(cid_h - ZERO3_IMX219_NOMINAL_HFOV_DEG, 3),
            "image_license_confirmed": False,
            "five_class_box_ground_truth_confirmed": False,
            "camera_geometry_equivalent_to_kwipi": False,
        },
        "mujoco_twin": {
            "frame": list(TWIN_IMAGE_SIZE),
            "source_vertical_fov_deg": TWIN_SIM_VFOV_DEG,
            "pinhole_hfov_deg": round(sim_h, 3),
            "hfov_delta_from_zero3_nominal_deg": round(sim_h - ZERO3_IMX219_NOMINAL_HFOV_DEG, 3),
            "camera_geometry_equivalent_to_kwipi": False,
        },
        "tirod": {
            "sensor": "esp32_cam_rover",
            "image_size": [640, 480],
            "exact_kwipi_label_overlap": exact_overlap,
            "ball_equal_to_coco_sports_ball_verified": False,
            "per_capture_camera_height_verified": False,
            "intrinsics_verified": False,
            "image_license_confirmed": False,
            "low_means_illumination_not_camera_height": True,
        },
        "kwipi_robot_board_identified": False,
        "kwipi_camera_height_measured": False,
        "real_camera_validated": False,
        "detection_benchmark_performed": False,
        "eligible_to_claim_kwipi_camera_equivalence": False,
    }


def main() -> None:
    print(json.dumps(optical_audit(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
