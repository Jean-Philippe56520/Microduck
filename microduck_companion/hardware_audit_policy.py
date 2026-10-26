"""F6-D: static, human-reviewed audit checklist over FICTIONAL claims.

No metric is sampled here. Booleans are operator ASSERTIONS, not verified
certificates or robot telemetry. This policy NEVER starts an audit, vision,
motor, network, service, recording, or hardware installation.

The F6-D shell script separately gates stationary read-only surveys. This
review model cannot grant movement even when every declared item is true.
"""
from __future__ import annotations

from dataclasses import dataclass

CHECKS = frozenset({
    "authorized_operator",
    "physical_board_revision_reviewed",
    "oem_firmware_and_services_reviewed",
    "idle_ram_rss_cpu_reviewed",
    "idle_thermal_frequency_reviewed",
    "data_partition_mount_reviewed",
    "motor_deadline_telemetry_reviewed",
    "stationary_area_supervised",
    "idle_baseline_reviewed",
    "vision_controlled_by_oem",
})
HAZARDS = frozenset({
    "oem_service_unhealthy",
    "sensor_missing_or_inconsistent",
    "memory_pressure_or_rss_regression",
    "thermal_risk_or_throttling",
    "cpu_frequency_collapse",
    "motor_deadline_miss",
    "storage_mounted_wrong_or_readonly",
    "power_or_battery_risk",
    "floor_or_obstacle_uncertain",
    "supervisor_or_stop_unavailable",
})
IDLE_REQUIRED = frozenset({
    "authorized_operator",
    "physical_board_revision_reviewed",
    "oem_firmware_and_services_reviewed",
})
VISION_REQUIRED = IDLE_REQUIRED | frozenset({
    "idle_ram_rss_cpu_reviewed",
    "idle_thermal_frequency_reviewed",
    "data_partition_mount_reviewed",
    "motor_deadline_telemetry_reviewed",
    "stationary_area_supervised",
    "idle_baseline_reviewed",
    "vision_controlled_by_oem",
})


@dataclass(frozen=True)
class AuditClaims:
    """Entirely declared evidence, never a reading or a right to actuate."""

    phase: str = "idle"
    checks: frozenset[str] = frozenset()
    hazards: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.phase not in ("idle", "vision", "movement"):
            raise ValueError("invalid F6-D audit phase")
        if (type(self.checks) is not frozenset
                or not all(type(x) is str for x in self.checks)
                or not self.checks <= CHECKS):
            raise ValueError("unrecognized or malformed audit claims")
        if (type(self.hazards) is not frozenset
                or not all(type(x) is str for x in self.hazards)
                or not self.hazards <= HAZARDS):
            raise ValueError("unrecognized or malformed hazard claims")


@dataclass(frozen=True)
class AuditReview:
    """Status is a checklist verdict, NOT a validated deployment permit."""

    status: str
    phase: str
    missing_declarations: tuple[str, ...]
    hazards: tuple[str, ...]
    snapshot_collected: bool = False
    physical_robot_validated: bool = False
    stationary_vision_started: bool = False
    movement_authorized: bool = False
    oem_sockets_contacted: int = 0
    motor_commands_issued: int = 0
    recorded_private_data: bool = False

    def __post_init__(self) -> None:
        if (self.snapshot_collected or self.physical_robot_validated
                or self.stationary_vision_started or self.movement_authorized
                or self.oem_sockets_contacted or self.motor_commands_issued
                or self.recorded_private_data):
            raise ValueError("F6-D checklist cannot perform external actions")


def review_audit_claims(claims: AuditClaims) -> AuditReview:
    """Fail closed on hazards; movement is blocked even if all flags claimed.

    The only positive status means a HUMAN may separately assess whether
    to launch the read-only script with explicit flags on their own RK3566.
    It cannot authenticate the operator or assert hardware measurements.
    """
    if not isinstance(claims, AuditClaims):
        raise TypeError("AuditClaims required")
    if claims.phase == "movement":
        return AuditReview(
            "movement_disabled_independent_locomotion_validation_required",
            claims.phase, (), tuple(sorted(claims.hazards)),
        )
    required = IDLE_REQUIRED if claims.phase == "idle" else VISION_REQUIRED
    missing = tuple(sorted(required - claims.checks))
    hazards = tuple(sorted(claims.hazards))
    if hazards:
        status = "stop_nonessential_activity_manual_oem_review"
    elif missing:
        status = "blocked_missing_manual_preconditions"
    else:
        status = "declared_snapshot_checklist_only_not_hardware_clearance"
    return AuditReview(status, claims.phase, missing, hazards)
