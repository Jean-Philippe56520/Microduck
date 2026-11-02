"""P16-B11: read-only inspection of a NEW DEV rootfs with 19+5+4 Python files.

Reuses B17's source closure, B10's immutable historical comparison,
P15-B9's account+inactive-unit policy, and P16's probe and manifest parser.
The actually built B11 daemon is a distinct, precisely pinned release.
Never invokes BitBake, systemctl, robotd, mediad, a camera, an actuator,
a model or SQLite. A caller-declared exit code is not proof of do_rootfs.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import stat

from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6
from scripts import per_p15b17_oem_receiver_package as b17
from scripts import per_p15b18_dev_receiver_env_gate as b18
from scripts import per_p16_dev_rootfs_audit as p16a
from scripts import per_p16b10_dev_rootfs_audit as b10
from scripts.per_p15b9_rootfs_identity_gate import verify_rootfs as verify_identity

SCHEMA = "kwipi-p16b11-independent-dev-28-module-rootfs-offline-v1"
STATUS = "p16b11_supplied_new_dev_rootfs_28_source_modules_verified_only"
B19_ARCHIVE_SHA256 = "0921b7dacd7a683b0b90ba7a979e20e72aa4a5aeaecb4899ba9cc63a46c7ab6c"
# WSL2 B11 do_rootfs succeeded on this exact Companion source; NOT B10.
B11_BUILD_HEAD = "659008ecf5d3a1eccd957e9ea2b1df4abaab21a1"
# P12 derives the daemon PV and embedded DUCK_REVISION from Companion HEAD.
B11_DAEMON_VERSION = "0.17.8+kwipi.p12." + B11_BUILD_HEAD[:12]
# OE-core package_setup_pkgv appends the pinned BMI088 source suffix.
B11_DAEMON_PKG_VERSION = B11_DAEMON_VERSION + "0+bd113f317b"
# The AArch64 installed files matched exactly their B11 PKGDEST splits on WSL2.
# These SHA-256 are operator-supplied measurements, not a proof of robot runtime.
B11_DAEMON_BINARIES = {
    "mediad": (11160240, "9b344b8ad0e503a2d438d8fe70060ace704effa10f689d85924f342574d743b4"),
    "robotd": (6435872, "3006d653fc5a657af2e18fbc12d2b02791c8cefa4658eb743c29c019491cca3b"),
}
NEW_PACKAGE = b17.PACKAGE
KWIPI_PACKAGES = frozenset((*b10.KWIPI_PACKAGES, NEW_PACKAGE))
REQUIRED = frozenset((*b10.REQUIRED_PACKAGES, NEW_PACKAGE))
MANIFEST_REGEX = r"microduck-image-dev-microduck-zero3\.rootfs(?:-[0-9]{14})?\.manifest"


class Refused(ValueError):
    """Fail closed: no distribution or sensor claim."""


def _sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def _distinct_paths(rootfs: Path, historical: Path) -> Path:
    if (not rootfs.is_absolute() or not historical.is_absolute()
            or rootfs.is_symlink() or historical.is_symlink()
            or not rootfs.is_dir() or not historical.is_dir()):
        raise Refused("two existing absolute nonlinked rootfs roots required")
    current = rootfs.resolve(strict=True)
    old = historical.resolve(strict=True)
    if (current == old or current.is_relative_to(old)
            or old.is_relative_to(current)):
        raise Refused("new rootfs overlaps the historical B10 rootfs")
    return current


def _manifest(manifest: Path) -> dict[str, str]:
    if (manifest.is_symlink() or not manifest.is_file()
            or not re.fullmatch(MANIFEST_REGEX, manifest.name)):
        raise Refused("only the regular OEM DEV microduck-zero3 manifest is accepted")
    packages = p16a._parse_manifest(manifest)
    if not REQUIRED.issubset(packages):
        raise Refused("new DEV rootfs manifest missing OEM/B10/B17 packages")
    if any(p.startswith("kwipi-") and p not in KWIPI_PACKAGES for p in packages):
        raise Refused("unreviewed Kwipi package in new DEV rootfs manifest")
    locked = {
        "microduck-daemon": (B11_DAEMON_PKG_VERSION,),
        "kwipi-companion": ("0.2.0a1", "0.2.0a1-r0"),
        "kwipi-passive-fixture": ("0.1.0", "0.1.0-r0"),
        "kwipi-readonly-probe": ("0.1", "0.1-r0"),
        NEW_PACKAGE: ("0.1.0", "0.1.0-r0"),
    }
    for key, allowed in locked.items():
        if packages[key] not in allowed:
            raise Refused("unexpected package version: " + key)
    return packages


def _source_closure(source_root: Path, declared_head: str) -> tuple[dict[str, str], dict]:
    """Actual checked-out source bytes, never invented from manifest claims."""
    if (not re.fullmatch(r"[0-9a-f]{40}", declared_head)
            or source_root.is_symlink() or not source_root.is_dir()):
        raise Refused("source checkout/head missing or invalid")
    new, source = b17.selected(source_root)
    archive = b17.staged_files(source_root)[1]
    if (p14b.repo_sha(source_root) != declared_head
            or source.get("source_revision") != declared_head
            or archive.get("source_revision") != declared_head
            or source.get("historical_python_modules") != 24
            or archive.get("new_modules") != 4
            or archive.get("archive_sha256") != B19_ARCHIVE_SHA256
            or archive.get("historical_p14b_archive_sha256") != p16a.PINNED_P14B_ARCHIVE_SHA256
            or archive.get("historical_b6_sha256") != b10.B6_SHA256
            or archive.get("oem_yocto_sha") != p14b.YOCTO_SHA):
        raise Refused("B19 checked sources, OEM Yocto or archived SHA drifted")
    previous = p14b.selected_bytes(source_root)
    passive = b6.addon_files(source_root)
    base = {k: _sha(v) for k, v in previous.items() if k.endswith(".py")}
    addon = {k: _sha(v) for k, v in passive.items()}
    new_sha = {k: _sha(v) for k, v in new.items()}
    if (len(base) != 19 or len(addon) != 5 or len(new_sha) != 4
            or set(addon) != b6.ADDON or addon != b10.B6_SHA256
            or set(new_sha) != b17.SELECTED
            or new_sha != archive.get("new_sha256")
            or len(set(base) | set(addon) | set(new_sha)) != 28):
        raise Refused("19+5+4 source closure changed")
    return {**base, **addon, **new_sha}, archive


def _verify_python(rootfs: Path, expected: dict[str, str]) -> dict[str, str]:
    folder = rootfs / p16a.PYTHON_PREFIX / "microduck_companion"
    if folder.is_symlink() or not folder.is_dir() or len(expected) != 28:
        raise Refused("28-module Python package missing")
    names: set[str] = set()
    for item in folder.rglob("*"):
        if item.is_symlink():
            raise Refused("unreviewed Python module symlink")
        if not item.is_file() or item.parent != folder or item.suffix != ".py":
            raise Refused("extra directory, bytecode, native binary or non-Python file")
        names.add("microduck_companion/" + item.name)
    if names != set(expected):
        raise Refused("installed Python modules differ from 19+5+4 source closure")
    result = {}
    for name, digest in sorted(expected.items()):
        file = p16a._under(rootfs, p16a.PYTHON_PREFIX + name)
        if stat.S_IMODE(file.stat().st_mode) != 0o644:
            raise Refused("installed Python permissions differ from source policy")
        actual = _sha(file.read_bytes())
        if actual != digest:
            raise Refused("installed Python SHA differs from B19 source: " + name)
        result[name] = actual
    return result



def _b11_binary_checks(rootfs: Path) -> dict[str, str]:
    """Read-only B11 release identity and exact AArch64 ELF payload; never B10."""
    daemon_root = rootfs / "opt/robot/daemon"
    current = daemon_root / "current"
    for directory in (rootfs / "opt", rootfs / "opt/robot", daemon_root):
        if directory.is_symlink() or not directory.is_dir():
            raise Refused("B11 daemon directory unavailable or linked")
    if (not current.is_symlink()
            or current.readlink().as_posix() != "releases/" + B11_DAEMON_VERSION):
        raise Refused("B11 current daemon release differs from pinned source revision")
    release = daemon_root / "releases" / B11_DAEMON_VERSION
    if (release.is_symlink() or not release.is_dir()
            or current.resolve(strict=True) != release.resolve(strict=True)):
        raise Refused("B11 current release escapes pinned directory")
    found = {}
    for name, (size, digest) in B11_DAEMON_BINARIES.items():
        file = p16a._under(rootfs, "opt/robot/daemon/releases/"
                            + B11_DAEMON_VERSION + "/bin/" + name)
        data = file.read_bytes()
        if (len(data) != size or data[:6] != b"\x7fELF\x02\x01"
                or int.from_bytes(data[18:20], "little") != 183
                or not (file.stat().st_mode & stat.S_IXUSR)):
            raise Refused("B11 daemon ELF AArch64, size or execute mode changed: " + name)
        if _sha(data) != digest:
            raise Refused("B11 daemon binary SHA-256 mismatch: " + name)
        found[name] = digest
    return found


def _metadata(proof: dict, source: dict) -> None:
    if (proof.get("schema") != b18.SCHEMA
            or proof.get("status") != b18.STATUS
            or proof.get("dev_receiver_count") != 1
            or proof.get("shipping_receiver_count") != 0
            or proof.get("base_modules") != 19
            or proof.get("passive_modules") != 5
            or proof.get("receiver_modules") != 4
            or proof.get("receiver_recipe_license") != "CLOSED"
            or proof.get("receiver_recipe_version") != b17.VERSION
            or proof.get("receiver_rdepends_checked") is not True
            or proof.get("oem_packages_preserved") is not True
            or proof.get("kwipi_account_isolated_by_effective_metadata") is not True
            or proof.get("source_receiver_sha256") != source["archive_sha256"]
            or proof.get("oem_producer_activated") is not False
            or proof.get("systemd_service_activated") is not False
            or proof.get("robot_validated") is not False
            or proof.get("shipping_image_changed") is not False):
        raise Refused("effective B18 metadata proof missing or inconsistent")


def validate(rootfs: Path, historical_rootfs: Path, manifest: Path,
             source_root: Path, source_head: str, *, builder_exit: int,
             metadata: dict) -> dict:
    if type(builder_exit) is not int or builder_exit != 0:
        raise Refused("do_rootfs exit zero must be separately supplied")
    if source_head != B11_BUILD_HEAD:
        raise Refused("only the built B11 Companion source revision is accepted")
    root = _distinct_paths(rootfs, historical_rootfs)
    packages = _manifest(manifest)
    sources, source_proof = _source_closure(source_root, source_head)
    _metadata(metadata, source_proof)
    installed = _verify_python(root, sources)
    binaries = _b11_binary_checks(root)
    probe = {}
    for name, sha in p16a.PROBE_HASHES.items():
        item = p16a._under(root, name)
        if _sha(item.read_bytes()) != sha:
            raise Refused("P15A unit, preset or script SHA changed")
        probe[name] = sha
    try:
        identity = verify_identity(root)
    except ValueError as exc:
        raise Refused("Kwipi account, groups, home or P15A policy violated") from exc
    if (identity.get("kwipi_no_supplementary_or_motor_group") is not True
            or identity.get("p15a_service_installed_not_enabled_in_rootfs") is not True
            or identity.get("oem_operator_preserved") is not True):
        raise Refused("incomplete OEM/Companion identity proof")
    return {
        "schema": SCHEMA,
        "status": STATUS,
        "source_revision_verified_against_checkout": source_head,
        "oem_yocto_sha": source_proof["oem_yocto_sha"],
        "b19_receiver_archive_sha256": source_proof["archive_sha256"],
        "packages": {k: packages[k] for k in sorted(REQUIRED)},
        "python_modules_verified": 28,
        "p14b_modules_verified": 19,
        "p15b6_modules_verified": 5,
        "b13_b16_modules_verified": 4,
        "python_sha256": installed,
        "b12_release": B11_DAEMON_VERSION,
        "b12_sha256": binaries,
        "b11_daemon_pkgv": B11_DAEMON_PKG_VERSION,
        "b11_built_source_head": B11_BUILD_HEAD,
        "installed_binaries_match_pinned_wsl2_b11_hashes": True,
        "pkgdest_match_independently_attested_by_this_gate": False,
        "probe_sha256": probe,
        "kwipi_account_isolated_from_motor": True,
        "oem_operator_preserved": True,
        "historical_b10_rootfs_distinct_and_unmodified_by_gate": True,
        "dev_only_selection_claim_checked_from_supplied_B18_proof": True,
        "builder_exit_zero_caller_declared_not_independently_attested": True,
        "manifest_rootfs_association_independently_attested": False,
        "bitbake_executed_by_this_gate": False,
        "shipping_rootfs_checked": False,
        "device_runtime_import_verified": False,
        "oem_detector_activated": False,
        "real_socket_acl_verified": False,
        "camera_or_npu_verified": False,
        "license_redistribution_approved": False,
        "rauc_signed_or_verified": False,
        "robot_validated": False,
        "motor_commands_issued": 0,
    }


def _load_proof(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise Refused("B18 proof must be a regular file")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise Refused("invalid B18 proof")
    return data


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("rootfs", "historical-rootfs", "manifest",
                 "source-root", "b18-proof", "report"):
        p.add_argument("--" + name, required=True, type=Path)
    p.add_argument("--source-head", required=True)
    p.add_argument("--do-rootfs-exit", required=True, type=int)
    args = p.parse_args()
    try:
        if args.report.exists() or args.report.is_symlink():
            raise Refused("refuse to overwrite B11 report or historical proof")
        result = validate(
            args.rootfs, args.historical_rootfs, args.manifest,
            args.source_root, args.source_head,
            builder_exit=args.do_rootfs_exit,
            metadata=_load_proof(args.b18_proof),
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as file:
            json.dump(result, file, sort_keys=True, indent=2)
            file.write("\n")
    except (Refused, b17.Refused, p14b.PackageRefused,
            b6.Refused, ValueError, KeyError, OSError, UnicodeError,
            json.JSONDecodeError) as exc:
        p.exit(1, "P16-B11 STOP: " + type(exc).__name__ + "\n")
    print(json.dumps({
        "status": result["status"],
        "python_modules_verified": result["python_modules_verified"],
        "robot_validated": result["robot_validated"],
        "bitbake_executed_by_this_gate": result["bitbake_executed_by_this_gate"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
