"""P15A: one bounded, manual, read-only OEM health observation; no motors.

This is an installed developer-image *probe*, not Kwipi autonomy, nor an
independent health or physical safety oracle. No service loop or memory writes.
"""
from __future__ import annotations

import json

from microduck_companion.sim_ipc import TelemetryError, read_health

SCHEMA = "kwipi-p15a-readonly-health-probe-v1"
OEM_ROBOTD_SOCKET = "/run/robotd.sock"


def probe(socket_path: str = OEM_ROBOTD_SOCKET, *, reader=read_health) -> dict:
    """Make exactly one already-audited robot.health request, else idle.

    A boolean from the socket is a *report*, not proof of physical health,
    and never grants any action or motor permission.
    """
    try:
        health = reader(socket_path, timeout_s=1.0)
    except (TelemetryError, TimeoutError, OSError):
        state = "idle_no_verified_telemetry"
    else:
        if type(health.healthy) is not bool:
            state = "idle_invalid_health"
        elif health.healthy:
            state = "reported_healthy_unverified"
        else:
            state = "idle_reported_unhealthy"
    return {
        "schema": SCHEMA,
        "status": state,
        "motor_commands_issued": 0,
        "memory_writes": 0,
        "physical_safety_verified": False,
        "autonomy_executed": False,
    }


def main() -> int:
    print(json.dumps(probe(), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
