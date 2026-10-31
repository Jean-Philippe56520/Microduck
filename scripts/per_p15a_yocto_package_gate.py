"""P15A-P: read-only audit of the REAL BitBake do_package output.

Input: BitBake -e for the target recipe and package-split files on the
operator's persistent builder. The script does NOT invoke BitBake or claim that
the independent shell command ran; no rootfs, unit activation, RAUC or robot.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import re
from pathlib import Path, PurePosixPath
import stat

from scripts.per_p13a_bitbake_env_gate import EnvRefused, bbvar
from scripts.per_p15a_bitbake_env_gate import (
    RECIPE, verify_source,
)

SCHEMA = "kwipi-p15a-real-bitbake-package-proof-v1"
PN = "kwipi-readonly-probe"
UNIT = PN + ".service"
PROBE_REL = "recipes-kwipi/kwipi-readonly-probe/files/health_probe.py"
UNIT_REL = "recipes-kwipi/kwipi-readonly-probe/files/" + UNIT
RUNTIME = frozenset({"kwipi-companion", "python3-core", "python3-json"})
# OE-core bitbake.conf exports these directories in effective BitBake -e.
EXPORTED_DIRECTORIES = frozenset({
    "libexecdir", "systemd_unitdir", "systemd_system_unitdir",
})
REQUIRED = (
    "PN", "PV", "FILE", "LICENSE", "PKGDEST", "TMPDIR", "S", "UNPACKDIR",
    "libexecdir", "systemd_unitdir", "systemd_system_unitdir", "BBLAYERS",
    "SYSTEMD_SERVICE:kwipi-readonly-probe",
    "SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe",
    "RDEPENDS:kwipi-readonly-probe",
)


def _install_path(value: str) -> Path:
    path = PurePosixPath(value)
    if (not value.startswith("/") or value == "/" or
            ".." in value.split("/") or
            "//" in value):
        raise EnvRefused("unexpected BitBake installation directory")
    return Path(str(path).lstrip("/"))


def _effective_directory(env: str, name: str) -> str:
    """Accept one effective exported or plain OE installation directory."""
    if name not in EXPORTED_DIRECTORIES:
        raise EnvRefused("unexpected exported directory key")
    found = re.findall(
        r"^(?:export[ \t]+)?" + re.escape(name) + r'="(.*)"$',
        env, re.M,
    )
    if len(found) != 1:
        raise EnvRefused("effective BitBake directory missing/duplicate: " + name)
    return found[0]


def _effective(env: str, layer: Path) -> dict[str, str]:
    values = {
        key: (_effective_directory(env, key)
              if key in EXPORTED_DIRECTORIES else bbvar(env, key))
        for key in REQUIRED
    }
    if (values["PN"] != PN or values["PV"] != "0.1"
            or values["LICENSE"] != "CLOSED"):
        raise EnvRefused("P15A recipe identity or closed license changed")
    if Path(values["FILE"]).resolve() != (layer / RECIPE).resolve():
        raise EnvRefused("BitBake used a substituted P15A recipe")
    if values["S"].rstrip("/") != values["UNPACKDIR"].rstrip("/"):
        raise EnvRefused("P15A unpack directory changed")
    if (values["SYSTEMD_SERVICE:kwipi-readonly-probe"] != UNIT or
            values["SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe"] != "disable"):
        raise EnvRefused("P15A systemd service or auto-enable drift")
    if not RUNTIME.issubset(set(
            values["RDEPENDS:kwipi-readonly-probe"].split())):
        raise EnvRefused("P15A runtime dependency floor missing")
    names = values["BBLAYERS"].replace("\\n", " ").replace("\\t", " ").split()
    if layer.resolve() not in {Path(n).resolve() for n in names}:
        raise EnvRefused("P15A layer missing from effective BitBake BBLAYERS")
    for key in ("libexecdir", "systemd_unitdir", "systemd_system_unitdir"):
        _install_path(values[key])
    return values


def _unit_active_lines(unit_text: str) -> list[str]:
    return [line.strip() for line in unit_text.splitlines()
            if line.strip() and not line.lstrip().startswith(("#", ";"))]


def validate_package(source_root: Path, env_text: str) -> dict:
    source_root = source_root.resolve(strict=True)
    layer = source_root / "yocto/meta-kwipi-p15-readonly"
    reviewed = verify_source(layer)
    if reviewed["reviewed_files"] != 5:
        raise EnvRefused("P15A source closure differs from reviewed recipe")
    v = _effective(env_text, layer)
    pkgdest, tmpdir = Path(v["PKGDEST"]), Path(v["TMPDIR"])
    if (not pkgdest.is_absolute() or not tmpdir.is_absolute() or
            pkgdest.is_symlink() or tmpdir.is_symlink() or
            not pkgdest.is_dir() or not tmpdir.is_dir() or
            not pkgdest.resolve().is_relative_to(tmpdir.resolve())):
        raise EnvRefused("BitBake PKGDEST is missing or outside TMPDIR")
    pkgroot = pkgdest / PN
    if pkgroot.is_symlink() or not pkgroot.is_dir():
        raise EnvRefused("P15A package-split directory absent")
    probe_rel = _install_path(v["libexecdir"]) / "kwipi/health_probe.py"
    unit_rel = _install_path(v["systemd_system_unitdir"]) / UNIT
    # OE-core pinned systemd.bbclass generates one disabled system preset.
    preset_rel = (_install_path(v["systemd_unitdir"]) / "system-preset" /
                  ("98-" + PN + ".preset"))
    expected = {probe_rel, unit_rel, preset_rel}
    actual = set()
    for path in pkgroot.rglob("*"):
        if path.is_symlink():
            raise EnvRefused("symbolic link in P15A packaged files")
        if path.is_file():
            actual.add(path.relative_to(pkgroot))
    if actual != expected:
        raise EnvRefused("P15A package file list is missing or unexpected: " +
                         repr(sorted(str(x) for x in (actual ^ expected))))
    files = {}
    for rel in sorted(expected):
        file = pkgroot / rel
        if not file.is_file() or stat.S_IMODE(file.stat().st_mode) != 0o644:
            raise EnvRefused("P15A packaged file type/mode differs: " + str(rel))
        files[str(rel)] = {
            "bytes": file.stat().st_size,
            "sha256": sha256(file.read_bytes()).hexdigest(),
            "mode": "0644",
        }
    probe = pkgroot / probe_rel
    unit = pkgroot / unit_rel
    preset = pkgroot / preset_rel
    if probe.read_bytes() != (layer / PROBE_REL).read_bytes():
        raise EnvRefused("P15A script bytes differ from reviewed source")
    libexec = v["libexecdir"].rstrip("/")
    expected_unit = ((layer / UNIT_REL).read_text(encoding="utf-8")
                     .replace("@LIBEXECDIR@", libexec))
    actual_unit = unit.read_text(encoding="utf-8")
    if actual_unit != expected_unit:
        raise EnvRefused("P15A installed systemd unit differs from source template")
    active = _unit_active_lines(actual_unit)
    if (active.count("[Service]") != 1 or
            active.count("ExecStart=/usr/bin/python3 -I -B " +
                         libexec + "/kwipi/health_probe.py") != 1):
        raise EnvRefused("P15A ExecStart or service declaration changed")
    for required in (
        "Type=oneshot", "TimeoutStartSec=4s", "DynamicUser=yes",
        "NoNewPrivileges=yes", "ProtectSystem=strict",
        "RestrictAddressFamilies=AF_UNIX", "SupplementaryGroups=robot",
        "After=robotd.service",
    ):
        if active.count(required) != 1:
            raise EnvRefused("P15A hardening or lifecycle changed: " + required)
    forbidden = (
        "[Install]", "WantedBy=", "RequiredBy=", "Alias=", "Also=",
        "Restart=", "Wants=", "Requires=", "BindsTo=", "Requisite=",
        "ExecStartPre=", "ExecStartPost=", "ExecStopPost=",
    )
    if any(line.startswith(forbidden) for line in active):
        raise EnvRefused("P15A packaged systemd unit can auto-start or chain OEM")
    if preset.read_bytes() != ("disable " + UNIT + "\n").encode("utf-8"):
        raise EnvRefused("P15A systemd preset missing explicit disable")
    return {
        "schema": SCHEMA,
        "status": "bitbake_p15a_package_files_verified_only",
        "reviewed_source_files": reviewed["reviewed_files"],
        "package_files_verified": len(expected),
        "files": files,
        "systemd_unit_packaged": True,
        "service_auto_enable": "disable",
        "oem_socket_group_is_not_readonly_acl": True,
        "bitbake_task_execution_attested_by_this_script": False,
        "rootfs_installed": False,
        "service_executed_on_target": False,
        "signed_release": False,
        "robot_validated": False,
        "motor_commands_issued": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.report.exists() or args.report.is_symlink():
            raise EnvRefused("report already exists; no overwrite")
        result = validate_package(
            args.root, args.env_file.read_text(encoding="utf-8"))
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (EnvRefused, OSError, ValueError, KeyError, UnicodeError) as exc:
        parser.exit(1, "P15A-P STOP: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
