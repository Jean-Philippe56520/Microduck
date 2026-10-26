"""F6-D offline preparation: synthetic claims, never device measurements.

This executable is safe on a CI host without a Microduck: no /proc or /sys
reads, OEM sockets, service management, installation, network or motor I/O.
"""
from __future__ import annotations

import json

from .hardware_audit_policy import (
    AuditClaims, CHECKS, HAZARDS, IDLE_REQUIRED, VISION_REQUIRED,
    review_audit_claims,
)


def run_demo() -> dict:
    idle_unknown = review_audit_claims(AuditClaims())
    claimed_idle = review_audit_claims(
        AuditClaims("idle", IDLE_REQUIRED),
    )
    vision_missing = review_audit_claims(
        AuditClaims("vision", IDLE_REQUIRED),
    )
    vision_hazard = review_audit_claims(
        AuditClaims("vision", VISION_REQUIRED,
                    frozenset({"motor_deadline_miss"})),
    )
    movement = review_audit_claims(
        AuditClaims("movement", frozenset(CHECKS), frozenset()),
    )
    if (idle_unknown.status != "blocked_missing_manual_preconditions"
            or claimed_idle.physical_robot_validated
            or claimed_idle.snapshot_collected
            or vision_missing.status != "blocked_missing_manual_preconditions"
            or vision_hazard.status != "stop_nonessential_activity_manual_oem_review"
            or movement.movement_authorized
            or movement.status !=
            "movement_disabled_independent_locomotion_validation_required"):
        raise RuntimeError("F6-D audit checklist promoted fictional claims")
    return {
        "kind": "synthetic_static_audit_checklist",
        "idle_missing": len(idle_unknown.missing_declarations),
        "claimed_idle_status": claimed_idle.status,
        "vision_missing": len(vision_missing.missing_declarations),
        "hazard_response": vision_hazard.status,
        "movement_status": movement.status,
        "catalogued_hazard_types": len(HAZARDS),
        "real_device_queries": 0,
        "real_robot_validated": False,
        "motor_commands": 0,
        "vision_started": False,
        "physical_snapshots_collected": 0,
    }


def main() -> int:
    print(json.dumps(run_demo(), allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
