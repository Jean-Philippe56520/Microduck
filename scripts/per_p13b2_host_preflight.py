"""PER-P13B2-H1: read-only preflight for a PERSISTENT Yocto build host.

Does not download, install, create files, invoke kas/BitBake, or touch robotd.
Uses real OEM/Companion SHA checks and only conservative *local test* resource
thresholds, never robot hardware assertions. --plan does not inspect hardware.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

from scripts.per_p11_v1_source_release import PIN as OEM_SHA, RL_PIN
from scripts.per_p12_yocto_layer import (
    YOCTO_SHA, check_yocto, verify as verify_p12,
)

GIB = 1024 ** 3
MIN_CPU = 4
MIN_RAM_BYTES = 16 * GIB
MIN_AVAILABLE_RAM_BYTES = 8 * GIB
DISK_BUDGET_GIB = {"build": 200, "downloads": 30, "sstate": 60}
SCHEMA = "kwipi-p13b2-h1-local-readonly-host-preflight-v1"


class HostBlocked(ValueError):
    """A local build cannot be claimed ready from this host observation."""


@dataclass(frozen=True)
class HostSnapshot:
    os_name: str
    machine: str
    cpus: int
    total_ram_bytes: int
    available_ram_bytes: int


def machine_snapshot() -> HostSnapshot:
    """One read-only snapshot of Linux kernel-provided capacity, not a benchmark."""
    with Path("/proc/meminfo").open(encoding="ascii") as f:
        lines = f.readlines()
    data = {}
    for line in lines:
        name, _, value = line.partition(":")
        if name in {"MemTotal", "MemAvailable"}:
            number, unit = value.strip().split()
            if unit != "kB" or not number.isdecimal():
                raise HostBlocked("invalid Linux memory capacity format")
            data[name] = int(number) * 1024
    if set(data) != {"MemTotal", "MemAvailable"}:
        raise HostBlocked("Linux RAM snapshot unavailable")
    return HostSnapshot(
        platform.system(), platform.machine(), os.cpu_count() or 0,
        data["MemTotal"], data["MemAvailable"],
    )


def _git(folder: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(folder), *args], check=True, capture_output=True,
            text=True, timeout=15,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError) as exc:
        raise HostBlocked("cannot independently verify git revision") from exc
    return result.stdout.strip()


def _canonical_directory(raw: Path, label: str) -> Path:
    if not raw.is_absolute():
        raise HostBlocked(label + ": require an absolute, canonical directory")
    if raw.is_symlink() or not raw.is_dir():
        raise HostBlocked(label + ": missing directory or symbolic link")
    real = raw.resolve(strict=True)
    if real != raw:
        raise HostBlocked(label + ": alias/parent symlink is not approved")
    return real


def _outside(candidate: Path, protected: tuple[Path, ...], role: str) -> None:
    if any(candidate == p or candidate.is_relative_to(p)
           or p.is_relative_to(candidate) for p in protected):
        raise HostBlocked(role + ": build/cache paths must be outside source checkout")


def _verify_gitlinks(project: Path) -> None:
    if _git(project, "status", "--porcelain", "--untracked-files=no"):
        raise HostBlocked("tracked project source has local modifications")
    for name, sha in (("microduck", OEM_SHA), ("microduck_rl", RL_PIN)):
        rel = "upstream/" + name
        line = _git(project, "ls-tree", "HEAD", rel)
        if line != "160000 commit " + sha + "\t" + rel:
            raise HostBlocked("gitlink differs from pinned OEM/simulator: " + rel)
        child = project / rel
        if child.is_symlink() or not child.is_dir():
            raise HostBlocked("submodule absent or symbolic: " + rel)
        if _git(child, "rev-parse", "HEAD") != sha:
            raise HostBlocked("submodule working tree differs from gitlink: " + rel)
        if _git(child, "status", "--porcelain", "--untracked-files=no"):
            raise HostBlocked("tracked submodule source modified: " + rel)


def available_bytes(folder: Path) -> int:
    fs = os.statvfs(folder)
    if fs.f_bavail < 0 or fs.f_frsize <= 0:
        raise HostBlocked("unreliable filesystem capacity")
    return fs.f_bavail * fs.f_frsize


def device_key(folder: Path) -> int:
    return os.stat(folder).st_dev


def _disk_budget(paths: dict[str, Path]) -> dict:
    groups: dict[int, list[str]] = {}
    for name, path in paths.items():
        groups.setdefault(device_key(path), []).append(name)
    results = []
    for dev, roles in sorted(groups.items(), key=lambda it: sorted(it[1])):
        needed = sum(DISK_BUDGET_GIB[k] for k in roles) * GIB
        # Only compare ONE physical free-space pool per device; aliases cannot
        # silently count the same disk available space multiple times.
        free = min(available_bytes(paths[k]) for k in roles)
        if free < needed:
            raise HostBlocked(
                "insufficient shared filesystem space for "
                + ",".join(sorted(roles)) + ": minimum "
                + str(needed // GIB) + " GiB, available "
                + str(free // GIB) + " GiB")
        results.append({
            "roles": sorted(roles), "free_gib_floor": free // GIB,
            "required_gib": needed // GIB,
        })
    return {"volumes": results, "combined_budget_gib": sum(DISK_BUDGET_GIB.values())}


def preflight(
    project: Path, yocto: Path, p12_layer: Path,
    build: Path, downloads: Path, sstate: Path, *,
    snapshot: HostSnapshot | None = None,
) -> dict:
    project = _canonical_directory(project, "companion checkout")
    yocto = _canonical_directory(yocto, "OEM Yocto checkout")
    p12_layer = _canonical_directory(p12_layer, "P12 source layer")
    roots = (project, yocto, p12_layer)
    if len(set(roots)) != 3 or any(
            a.is_relative_to(b) or b.is_relative_to(a)
            for i, a in enumerate(roots) for b in roots[i + 1:]):
        raise HostBlocked("companion, OEM Yocto and P12 must be separate checkouts")
    paths = {
        name: _canonical_directory(path, name + " cache")
        for name, path in (
            ("build", build), ("downloads", downloads), ("sstate", sstate))
    }
    for role, folder in paths.items():
        _outside(folder, roots, role)
    if len(set(paths.values())) != len(paths) or any(
            a.is_relative_to(b) or b.is_relative_to(a)
            for i, a in enumerate(paths.values())
            for b in list(paths.values())[i + 1:]):
        raise HostBlocked("cache folders overlap; use distinct paths")

    _verify_gitlinks(project)
    try:
        checked = check_yocto(yocto)
        proof = verify_p12(p12_layer)
    except (OSError, ValueError, TypeError, KeyError,
            subprocess.CalledProcessError) as exc:
        raise HostBlocked("OEM/Yocto/P12 source gate rejected checkout") from exc
    if (not checked or proof.get("yocto_sha") != YOCTO_SHA
            or proof.get("oem_sha") != OEM_SHA
            or proof.get("crates_generated") != 568
            or proof.get("source_only") is not True
            or proof.get("detector_enabled_by_default") is not False):
        raise HostBlocked("P12 layer pin/provenance/crate/vision guard failed")

    facts = snapshot if snapshot is not None else machine_snapshot()
    if (facts.os_name != "Linux" or facts.machine != "x86_64"
            or facts.cpus < MIN_CPU
            or facts.total_ram_bytes < MIN_RAM_BYTES
            or facts.available_ram_bytes < MIN_AVAILABLE_RAM_BYTES):
        raise HostBlocked("host CPU, RAM, architecture or OS outside this trial budget")
    if shutil.which("kas") is None or shutil.which("git") is None:
        raise HostBlocked("kas or git absent from host PATH; no installation attempted")
    disks = _disk_budget(paths)
    return {
        "schema": SCHEMA,
        "status": "host_resource_preflight_passed_only",
        "p12_source_revision": proof["companion_sha"],
        "oem_sha": OEM_SHA,
        "yocto_sha": YOCTO_SHA,
        "oem_simulator_sha": RL_PIN,
        "p12_archive_sha256": proof["archive_sha256"],
        "crates_metadata_only": 568,
        "snapshot": {
            "cpus": facts.cpus,
            "total_ram_gib_floor": facts.total_ram_bytes // GIB,
            "available_ram_gib_floor": facts.available_ram_bytes // GIB,
        },
        "disk_budgets": disks,
        "no_files_written": True,
        "bitbake_parse_executed": False,
        "bitbake_build_executed": False,
        "arm64_elf_produced": False,
        "python_package_installed": False,
        "rauc_built_or_signed": False,
        "robot_validated": False,
    }


def plan() -> dict:
    """Informative offline contract. No filesystem, git or hardware access."""
    return {
        "schema": SCHEMA,
        "status": "offline_plan_only_no_host_checked",
        "required_os_arch": "Linux x86_64",
        "min_cpu_count_for_trial": MIN_CPU,
        "min_ram_total_gib_for_trial": MIN_RAM_BYTES // GIB,
        "min_ram_available_gib_for_trial": MIN_AVAILABLE_RAM_BYTES // GIB,
        "disk_free_gib_per_role": DISK_BUDGET_GIB,
        "same_volume_requires_sum_gib": sum(DISK_BUDGET_GIB.values()),
        "requires_pinned_oem_yocto_and_verified_p12_layer": True,
        "requires_kas_git_installed_not_executed": True,
        "do_not_run": ["scripts/build-local.sh", "daemon-release.sh",
                       "bitbake -c update_crates microduck-daemon"],
        "after_preflight": (
            "Manually add only the P12 layer to pinned kas, first verify "
            "bitbake -e microduck-daemon and show-appends; then perform "
            "do_compile/do_package on the persistent, audited host"),
        "source_writes": False,
        "network_calls": False,
        "bitbake_executed": False,
        "robot_validated": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--plan", action="store_true")
    group.add_argument("--check", action="store_true")
    for name in ("project", "yocto", "p12-layer", "build", "downloads", "sstate"):
        parser.add_argument("--" + name, type=Path)
    args = parser.parse_args()
    try:
        if args.plan:
            if any(getattr(args, name.replace("-", "_")) is not None for name in
                   ("project", "yocto", "p12-layer", "build", "downloads", "sstate")):
                raise HostBlocked("--plan never consumes local paths")
            result = plan()
        else:
            names = ("project", "yocto", "p12_layer", "build", "downloads", "sstate")
            if any(getattr(args, x) is None for x in names):
                raise HostBlocked("--check requires all six existing local paths")
            result = preflight(*(getattr(args, x) for x in names))
        print(json.dumps(result, sort_keys=True))
    except (HostBlocked, ValueError, OSError, KeyError) as exc:
        parser.exit(2, "PER-P13B2-H1 STOP: " + str(exc) + "\n")


if __name__ == "__main__":
    main()
