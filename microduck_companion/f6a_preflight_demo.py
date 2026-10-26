"""F6-A static OEM-readiness demo on FICTIONAL evidence only.

No socket, /proc/mountinfo, disk label or robot resource is accessed.
This does not create the database directory or install a daemon.
"""
from __future__ import annotations

import json

from .embedded_readiness import (
    inspect_embedded_preparation, oem_manifest,
)


def run_demo() -> dict:
    nonexistent = inspect_embedded_preparation()
    # The same path *appearing* on a root filesystem is not a data mount.
    root_only = "25 1 179:2 / / rw,relatime - ext4 /dev/mmcblk0p2 rw\n"
    absent = inspect_embedded_preparation(
        machine="microduck-beta", compatible="pollen,microduck-beta",
        mountinfo_text=root_only,
        partlabel_device="/dev/mmcblk0p5",
    )
    # A fabricated mountinfo and PARTLABEL source only gives a candidate,
    # not verified storage; F6-A ALWAYS chooses in-memory SQLite.
    fake_partition = inspect_embedded_preparation(
        machine="microduck-beta", compatible="pollen,microduck-beta",
        mountinfo_text=(
            root_only + "52 25 179:5 / /var/lib/robot rw,relatime "
            "- ext4 /dev/mmcblk0p5 rw,noatime\n"
        ),
        partlabel_device="/dev/mmcblk0p5",
    )
    if (nonexistent.storage.status != "mount_missing"
            or absent.storage.status != "mount_missing"
            or fake_partition.storage.status != "persistent_mount_candidate"
            or fake_partition.storage.sqlite_selected != ":memory:"
            or fake_partition.robot_hardware_validated
            or fake_partition.installation_authorized
            or fake_partition.navigation_authorized
            or fake_partition.motor_commands_issued
            or fake_partition.oem_sockets_contacted):
        raise RuntimeError("offline-ready inventory improperly enabled I/O")
    return {
        "scenario": "fictional_offline_oem_readiness",
        "documented_oem_interface_count": len(oem_manifest()["interfaces"]),
        "no_mount_status": nonexistent.storage.status,
        "root_only_status": absent.storage.status,
        "fake_data_mount_status": fake_partition.storage.status,
        "selected_database": fake_partition.storage.sqlite_selected,
        "real_service_connections": fake_partition.oem_sockets_contacted,
        "pc_queries": 0,
        "motor_commands_issued": fake_partition.motor_commands_issued,
        "installation_authorized": fake_partition.installation_authorized,
        "hardware_validated": fake_partition.robot_hardware_validated,
    }


def main() -> int:
    print(json.dumps(run_demo(), sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
