"""Camera-fidelity preflight against the PINNED OEM camera profiles.

This is a host-only metadata check, not a sensor reader or a certificate.
All metadata is caller-declared, even when the source field says oem_mediad.
No camera, media, network, model, database, motor or filesystem access.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

OEM_SHA = "942e58e3aa6dbb28e7037203fff11866122c7567"
SIM_SHA = "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3"
MEDIA_QUALITY_MODES = {
    "1080p30": (1920, 1080, 30),
    "720p30": (1280, 720, 30),
    "720p15": (1280, 720, 15),
    "360p30": (640, 360, 30),
}
LOW_HEIGHT_MM = (100, 300)
SIM_DEFAULT = (640, 360, 15)
SIM_VFOV_DEG = 45.0
# Source: pinned OEM board.rs, mediad/sensor.rs and mediad/camera.rs.
_CAMERA_BY_BOARD = {
    "zero3": ("imx219", 90, 62.0),
    "beta": ("gc2093", 0, None),
}
_SOURCES = frozenset({"public_still", "operator_still", "oem_mediad", "mujoco"})
_INTRINSICS = frozenset({"none", "nominal", "family", "robot", "sim"})


@dataclass(frozen=True)
class CameraDeclaration:
    """Untrusted, non-identifying metadata only; NEVER a real sensor receipt."""

    source: str
    width: int
    height: int
    board: str | None = None
    sensor: str | None = None
    rotate_metadata_deg: int | None = None
    media_quality: str | None = None
    intrinsics_source: str = "none"
    horizontal_fov_deg: float | None = None
    optical_center_height_mm: int | None = None
    height_method: str = "unknown"

    def __post_init__(self) -> None:
        if (type(self.source) is not str or self.source not in _SOURCES
                or type(self.width) is not int or not 1 <= self.width <= 4096
                or type(self.height) is not int or not 1 <= self.height <= 4096
                or (self.board is not None and
                    (type(self.board) is not str or self.board not in _CAMERA_BY_BOARD))
                or (self.sensor is not None and
                    (type(self.sensor) is not str
                     or self.sensor not in {"imx219", "gc2093"}))
                or (self.rotate_metadata_deg is not None and
                    (type(self.rotate_metadata_deg) is not int
                     or self.rotate_metadata_deg not in {0, 90, 180, 270}))
                or (self.media_quality is not None and
                    (type(self.media_quality) is not str
                     or self.media_quality not in MEDIA_QUALITY_MODES))
                or (self.media_quality is not None and self.source != "oem_mediad")
                or type(self.intrinsics_source) is not str
                or self.intrinsics_source not in _INTRINSICS
                or (self.horizontal_fov_deg is not None and
                    (type(self.horizontal_fov_deg) not in (int, float)
                     or not math.isfinite(self.horizontal_fov_deg)
                     or not 0 < self.horizontal_fov_deg < 180))
                or (self.optical_center_height_mm is not None and
                    (type(self.optical_center_height_mm) is not int
                     or not 1 <= self.optical_center_height_mm <= 2000))
                or self.height_method not in {"unknown", "ruler_at_optical_center"}
                or type(self.height_method) is not str):
            raise ValueError("invalid or unbounded camera declaration")


@dataclass(frozen=True)
class CameraFidelityReport:
    """Metadata consistency only. Never proves the target robot is calibrated."""

    status: str
    blockers: tuple[str, ...]
    expected_sensor: str | None
    expected_rotate_metadata_deg: int | None
    reference_horizontal_fov_deg: float | None
    declared_low_height: bool
    declared_oem_metadata_match: bool
    sim_horizontal_fov_deg: float | None
    robot_hardware_verified: bool = False
    real_camera_performance_verified: bool = False

    def __post_init__(self) -> None:
        # Metadata cannot be upgraded to robot validation, even by DTO callers.
        if (self.robot_hardware_verified is not False
                or self.real_camera_performance_verified is not False):
            raise ValueError("camera metadata is not robot hardware proof")


def reference_camera(board: str) -> tuple[str, int, float | None]:
    """Exact pinned OEM family defaults, NOT live device configuration."""
    if type(board) is not str or board not in _CAMERA_BY_BOARD:
        raise ValueError("unknown OEM board; do not assume a variant")
    return _CAMERA_BY_BOARD[board]


def assess_camera_fidelity(
    capture: CameraDeclaration, *, target_board: str | None
) -> CameraFidelityReport:
    """Fail closed on missing board, provenance, optical geometry or height.

    A passing report says ONLY that the supplied declaration is internally
    consistent with one pinned OEM profile. It does not authenticate the
    source, optical calibration, mounting height, ISP or robot performance.
    """
    if not isinstance(capture, CameraDeclaration):
        raise TypeError("CameraDeclaration required")
    if target_board is not None and (
        type(target_board) is not str or target_board not in _CAMERA_BY_BOARD
    ):
        raise ValueError("unknown target board")

    blockers: list[str] = []
    expected_sensor = expected_rotation = reference_hfov = None
    if target_board is None:
        blockers.append("target_board_not_identified")
    else:
        expected_sensor, expected_rotation, reference_hfov = reference_camera(target_board)
        if capture.board != target_board:
            blockers.append("capture_board_mismatch_or_unknown")
        if capture.sensor != expected_sensor:
            blockers.append("capture_sensor_mismatch_or_unknown")
        if capture.rotate_metadata_deg != expected_rotation:
            blockers.append("camera_rotation_metadata_mismatch_or_unknown")

        if capture.horizontal_fov_deg is None:
            blockers.append("horizontal_fov_unreported")
        elif reference_hfov is None:
            # Beta GC2093 has no pinned nominal or family optical solution.
            if capture.intrinsics_source != "robot":
                blockers.append("beta_requires_per_unit_intrinsics")
        elif capture.intrinsics_source in {"nominal", "family"}:
            # This tests a claim about the OEM reference, not a unit calibration.
            if not math.isclose(capture.horizontal_fov_deg, reference_hfov,
                                abs_tol=0.01):
                blockers.append("nominal_fov_does_not_match_oem_reference")
        elif capture.intrinsics_source != "robot":
            blockers.append("unusable_intrinsics_provenance")

    if capture.source != "oem_mediad":
        blockers.append("not_a_declared_oem_mediad_capture")
    elif capture.media_quality is None:
        blockers.append("media_quality_unreported")
    elif (capture.width, capture.height) != MEDIA_QUALITY_MODES[capture.media_quality][:2]:
        blockers.append("media_quality_geometry_mismatch")

    low = (capture.optical_center_height_mm is not None
           and LOW_HEIGHT_MM[0] <= capture.optical_center_height_mm <= LOW_HEIGHT_MM[1]
           and capture.height_method == "ruler_at_optical_center")
    if not low:
        blockers.append("low_optical_center_height_not_documented")

    sim_hfov = None
    if capture.source == "mujoco":
        # The pinned twin uses fovy=45 deg at 640x360 (rendered, NOT sensor).
        sim_hfov = math.degrees(2 * math.atan(
            (SIM_DEFAULT[0] / SIM_DEFAULT[1])
            * math.tan(math.radians(SIM_VFOV_DEG) / 2)))
        blockers.append("mujoco_virtual_camera_not_a_physical_camera")

    consistent = not blockers
    return CameraFidelityReport(
        status=("declared_oem_metadata_consistent_only" if consistent
                else "insufficient_for_oem_camera_comparison"),
        blockers=tuple(blockers), expected_sensor=expected_sensor,
        expected_rotate_metadata_deg=expected_rotation,
        reference_horizontal_fov_deg=reference_hfov,
        declared_low_height=low, declared_oem_metadata_match=consistent,
        sim_horizontal_fov_deg=(round(sim_hfov, 3) if sim_hfov is not None else None),
    )
