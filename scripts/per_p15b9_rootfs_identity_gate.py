"""P15-B9-R: independent offline identity audit of an already built DEV rootfs.

This reads only etc/{passwd,group,shadow} and the disabled P15A systemd unit.
No BitBake, mount, service activation, network, actuator or robot is accessed.
Never print or store password fields or OEM hashes.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import stat

from scripts.per_p15b6_cached_package_runner import Refused
from scripts.per_p15a_yocto_package_gate import _unit_active_lines

OEM_GROUPS = frozenset({
    "robot", "sudo", "audio", "video", "dialout", "i2c", "plugdev", "input"
})
PRIVILEGED = OEM_GROUPS | {"wheel", "root", "adm"}
UNIT = "usr/lib/systemd/system/kwipi-readonly-probe.service"
PRESET = "usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset"
STATUS = "p15b9r_dev_rootfs_identity_files_verified_only"


def _read(root: Path, rel: str) -> str:
    f = root / rel
    if f.is_symlink() or not f.is_file():
        raise Refused("missing or linked required rootfs file: " + rel)
    if rel == "etc/shadow" and stat.S_IMODE(f.stat().st_mode) & 0o007:
        raise Refused("rootfs shadow file is world-readable")
    try:
        return f.read_text(encoding="utf-8")
    except (UnicodeError, OSError) as exc:
        raise Refused("cannot read required rootfs file: " + rel) from exc


def _records(text: str, fields: int, rel: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(":")
        if len(parts) != fields or not parts[0] or parts[0] in result:
            raise Refused("invalid or duplicate identity record in " + rel)
        result[parts[0]] = parts
    return result


def verify_rootfs(rootfs: Path) -> dict:
    if not rootfs.is_absolute() or rootfs.is_symlink() or not rootfs.is_dir():
        raise Refused("rootfs must be an existing, absolute, non-linked directory")
    root = rootfs.resolve(strict=True)
    passwd = _records(_read(root, "etc/passwd"), 7, "passwd")
    groups = _records(_read(root, "etc/group"), 4, "group")
    shadows = _records(_read(root, "etc/shadow"), 9, "shadow")

    for name in ("root", "microduck", "kwipi"):
        if name not in passwd:
            raise Refused("missing required account: " + name)
    for name in ("microduck", "kwipi"):
        if name not in shadows:
            raise Refused("missing account shadow entry: " + name)
    if "kwipi" not in groups:
        raise Refused("private kwipi group missing")
    try:
        uid = int(passwd["kwipi"][2])
        gid = int(passwd["kwipi"][3])
        other_uids = [int(p[2]) for name, p in passwd.items() if name != "kwipi"]
        group_gid = int(groups["kwipi"][2])
        other_gids = [int(p[2]) for name, p in groups.items() if name != "kwipi"]
        root_uid = int(passwd["root"][2])
        operator_uid = int(passwd["microduck"][2])
    except ValueError as exc:
        raise Refused("non-numeric UID/GID") from exc
    if (root_uid != 0 or uid <= 0 or uid in other_uids or operator_uid <= 0
            or uid == operator_uid or gid <= 0 or gid != group_gid
            or gid in other_gids or gid == int(passwd["microduck"][3])):
        raise Refused("shared, root or non-private kwipi identity")
    if passwd["kwipi"][1] != "x" or passwd["kwipi"][6] != "/sbin/nologin":
        raise Refused("kwipi login policy differs from P15-B9")
    if not shadows["kwipi"][1].startswith("!"):
        raise Refused("kwipi password is not locked")
    home = passwd["kwipi"][5]
    if (not home.startswith("/") or ".." in Path(home).parts
            or (home != "/" and (root / home.lstrip("/")).exists())):
        raise Refused("invalid home or created home for kwipi")

    membership: set[str] = set()
    oem_membership: set[str] = set()
    for name, record in groups.items():
        members = record[3].split(",") if record[3] else []
        if any(not member for member in members) or len(members) != len(set(members)):
            raise Refused("invalid /etc/group membership")
        if "kwipi" in members:
            membership.add(name)
        if "microduck" in members:
            oem_membership.add(name)
    if membership - {"kwipi"} or (groups["kwipi"][3] not in ("", "kwipi")):
        raise Refused("kwipi is a member of another group")
    if not OEM_GROUPS.issubset(oem_membership):
        raise Refused("OEM microduck operator group membership changed")
    if any(name in membership for name in PRIVILEGED):
        raise Refused("kwipi acquired a privileged group")

    unit = _read(root, UNIT)
    preset = _read(root, PRESET)
    # P15A's reviewed unit mentions [Install] in a comment; only active
    # systemd lines can make the service installable or start other units.
    active = _unit_active_lines(unit)
    forbidden = (
        "[Install]", "WantedBy=", "RequiredBy=", "Alias=", "Also=",
        "Restart=", "Wants=", "Requires=", "BindsTo=", "Requisite=",
        "ExecStartPre=", "ExecStartPost=", "ExecStopPost=",
    )
    if (any(line.startswith(forbidden) for line in active)
            or preset.strip() != "disable kwipi-readonly-probe.service"):
        raise Refused("P15A unit is installable or enabled by preset")
    # No installed activation links, even with a harmless-looking link name.
    for base in ("etc/systemd/system", "usr/lib/systemd/system", "lib/systemd/system"):
        folder = root / base
        if not folder.exists() or folder.is_symlink():
            continue
        for item in folder.rglob("*"):
            rel = item.relative_to(root).as_posix()
            if (item.name.startswith("kwipi")
                    and item.name.endswith((".service", ".socket", ".timer", ".path"))
                    and rel != UNIT):
                raise Refused("unreviewed Kwipi systemd unit in rootfs")
            if item.is_symlink():
                target = os.readlink(item)
                if "kwipi" in item.name.lower() or "kwipi" in target.lower():
                    raise Refused("Kwipi systemd symlink/activation detected")
    if (root / "home/kwipi").exists() or (root / "etc/init.d/kwipi").exists():
        raise Refused("unexpected Kwipi home/init script")

    return {
        "status": STATUS,
        "kwipi_account_present": True,
        "kwipi_uid_isolated_nonroot": True,
        "kwipi_primary_group_private": True,
        "kwipi_no_supplementary_or_motor_group": True,
        "kwipi_password_locked": True,
        "kwipi_shell_noninteractive": True,
        "kwipi_home_not_created": True,
        "oem_operator_preserved": True,
        "oem_operator_group_count": len(OEM_GROUPS),
        "p15a_service_installed_not_enabled_in_rootfs": True,
        "runtime_service_state_verified": False,
        "shipping_rootfs_verified": False,
        "real_socket_acl_verified": False,
        "robot_validated": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rootfs", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    try:
        if args.report.exists() or args.report.is_symlink():
            raise Refused("report already exists or is linked")
        proof = verify_rootfs(args.rootfs)
        # No shared/private file is ever written into the rootfs itself.
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    except (Refused, OSError, ValueError) as exc:
        p.exit(1, "P15-B9-R ROOTFS IDENTITY STOP: " + str(exc) + "\n")
    print(json.dumps(proof, sort_keys=True))


if __name__ == "__main__":
    main()
