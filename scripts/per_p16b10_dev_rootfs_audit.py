"""P16-A/B10: fail-closed OFFLINE audit of an EXISTING DEV rootfs only.

No BitBake, installation, motor command, service start, WIC or RAUC is run.
The caller must separately attest the actual do_rootfs exit and recheck P15-B10
DEV/shipping effective metadata before any build. An offline audit is not boot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat

from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6
from scripts import per_p16_dev_rootfs_audit as p16a
from scripts.per_p15b9_rootfs_identity_gate import verify_rootfs as verify_identity

SOURCE_HEAD = "e2e9bfef7d7c4f46fe51924937e7939d78d00383"
B12_VERSION = "0.17.8+kwipi.p12.e2e9bfef7d7c"
B12_BINARIES = {
    "mediad": (11160240, "2e1319a17072f0c4a7ae1594a785aa987873d15e01d50a435b6772c873c99c1f"),
    "robotd": (6435872, "0aa212501839d766d7f138bae25db85949b8eb7a1dac72d70cd7d8db147982dc"),
}
B6_SHA256 = {
    "microduck_companion/offline_resource_budget.py": "0dada90173be2877fb25be2c99c24944f017fc9e7181cca508f4d7e42338cc38",
    "microduck_companion/passive_fixture_runtime.py": "75e632284f93be06208903bf091a88c42bd4bc0f773b909c4d5d71e49fa09306",
    "microduck_companion/passive_media_fixture_reader.py": "a019b5f744a6e95cb5de84d0e58ddff6c1f4513bc97962acef43a9e5eb9212bf",
    "microduck_companion/passive_media_router.py": "6e95975ee701d93b6b69e01cc8d5fb5959f2e4ec12e76110bcb2425415b15d6e",
    "microduck_companion/passive_resilience.py": "154567e81fb3eef8d26fa4fc129d819cd59ca58e1885b03deaf4dd2cd572774b",
}
KWIPI_PACKAGES = ("kwipi-companion", "kwipi-passive-fixture", "kwipi-readonly-probe")
REQUIRED_PACKAGES = KWIPI_PACKAGES + ("microduck-daemon", "microduck-data")
STATUS = "p16b10_dev_rootfs_24_modules_and_b12_files_checked_only"


class Refused(ValueError):
    pass


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest(rootfs: Path, manifest: Path) -> dict[str, str]:
    if manifest.is_symlink() or not manifest.is_file():
        raise Refused("DEV image manifest missing or linked")
    if (not manifest.name.startswith("microduck-image-dev-")
            or not manifest.name.endswith(".rootfs.manifest")):
        raise Refused("not an OEM DEV rootfs manifest")
    packages = p16a._parse_manifest(manifest)
    if any(x not in packages for x in REQUIRED_PACKAGES):
        raise Refused("missing P16-B10 or OEM package")
    if any(x.startswith("kwipi-") and x not in KWIPI_PACKAGES for x in packages):
        raise Refused("unexpected Kwipi package")
    for name, version in {
        "microduck-daemon": B12_VERSION,
        "kwipi-companion": "0.2.0a1",
        "kwipi-passive-fixture": "0.1.0",
    }.items():
        if packages[name] not in (version, version + "-r0"):
            raise Refused("package version mismatch: " + name)
    return packages


def _source_hashes(source_root: Path, source_head: str) -> dict[str, str]:
    if (source_head != SOURCE_HEAD or source_root.is_symlink()
            or not source_root.is_dir()):
        raise Refused("source must be pinned B12 checkout")
    _, base = p14b.staged_files(source_root)
    _, addon = b6.staged_files(source_root)
    if (base["source_revision"] != SOURCE_HEAD
            or addon["source_revision"] != SOURCE_HEAD
            or base["source_archive_sha256"] != p16a.PINNED_P14B_ARCHIVE_SHA256
            or base["selected_python_modules"] != 19
            or addon["base_modules"] != 19
            or addon["addon_modules"] != 5):
        raise Refused("P14B/B6 source or archive provenance mismatch")
    base_files = {n: h for n, h in base["source_sha256"].items()
                  if n.endswith(".py")}
    if (len(base_files) != 19 or len(base["source_sha256"]) != 20
            or addon["base_sha256"] != base_files
            or addon["addon_sha256"] != B6_SHA256
            or set(base_files).intersection(B6_SHA256)):
        raise Refused("P14B/B6 source closure is not 19+5")
    return {**base_files, **B6_SHA256}


def _installed_modules(rootfs: Path, expected: dict[str, str]) -> dict[str, str]:
    package = rootfs / p16a.PYTHON_PREFIX / "microduck_companion"
    if package.is_symlink() or not package.is_dir():
        raise Refused("Python package missing or symlinked")
    seen: set[str] = set()
    for entry in package.rglob("*"):
        if entry.is_symlink():
            raise Refused("unreviewed link in installed Python package")
        if entry.is_file():
            # Unreviewed bytecode can override trusted source files at runtime;
            # the B10 recipe installs only .py. Refuse .pyc until audited.
            if entry.suffix != ".py":
                raise Refused("unexpected installed Python package file or bytecode")
            seen.add(entry.relative_to(rootfs / p16a.PYTHON_PREFIX).as_posix())
        elif not entry.is_dir():
            raise Refused("unexpected Python package entry type")
    if set(expected) != seen or len(expected) != 24:
        raise Refused("installed Python set differs from 24-module closure")
    digests = {}
    for rel, digest in sorted(expected.items()):
        file = p16a._under(rootfs, p16a.PYTHON_PREFIX + rel)
        if stat.S_IMODE(file.stat().st_mode) != 0o644:
            raise Refused("installed Python module mode drift: " + rel)
        actual = _hash(file)
        if actual != digest:
            raise Refused("installed module SHA-256 mismatch: " + rel)
        digests[rel] = actual
    return digests


def _binary_checks(rootfs: Path) -> dict[str, str]:
    daemon_root = rootfs / "opt/robot/daemon"
    current = daemon_root / "current"
    for directory in (rootfs / "opt", rootfs / "opt/robot", daemon_root):
        if directory.is_symlink() or not directory.is_dir():
            raise Refused("daemon directory unavailable or linked")
    if not current.is_symlink() or current.readlink().as_posix() != "releases/" + B12_VERSION:
        raise Refused("daemon current does not point to pinned B12")
    release = daemon_root / "releases" / B12_VERSION
    if current.resolve(strict=True) != release.resolve(strict=True):
        raise Refused("daemon current escapes expected B12 release")
    found = {}
    for name, (size, digest) in B12_BINARIES.items():
        file = p16a._under(rootfs, "opt/robot/daemon/releases/" + B12_VERSION + "/bin/" + name)
        data = file.read_bytes()
        if (len(data) != size or data[:6] != b"\x7fELF\x02\x01"
                or int.from_bytes(data[18:20], "little") != 183
                or not (file.stat().st_mode & stat.S_IXUSR)):
            raise Refused("B12 binary size, ELF AArch64 or mode mismatch: " + name)
        if hashlib.sha256(data).hexdigest() != digest:
            raise Refused("B12 binary SHA-256 mismatch: " + name)
        found[name] = digest
    return found


def validate(rootfs: Path, manifest: Path, *, builder_exit: int,
             source_head: str, source_root: Path) -> dict:
    if builder_exit != 0:
        raise Refused("real do_rootfs exit zero not attested")
    if not rootfs.is_absolute() or rootfs.is_symlink() or not rootfs.is_dir():
        raise Refused("existing absolute DEV rootfs required")
    rootfs = rootfs.resolve(strict=True)
    packages = _manifest(rootfs, manifest)
    expected = _source_hashes(source_root, source_head)
    installed = _installed_modules(rootfs, expected)
    binaries = _binary_checks(rootfs)
    probe = {}
    for rel, expected_hash in p16a.PROBE_HASHES.items():
        actual_hash = _hash(p16a._under(rootfs, rel))
        if actual_hash != expected_hash:
            raise Refused("P15A packaged bytes drift: " + rel)
        probe[rel] = actual_hash
    try:
        identity = verify_identity(rootfs)
    except ValueError as exc:
        raise Refused("P15-B9 identity or disabled-service gate failed") from exc
    if (identity.get("kwipi_no_supplementary_or_motor_group") is not True
            or identity.get("p15a_service_installed_not_enabled_in_rootfs") is not True
            or identity.get("oem_operator_preserved") is not True):
        raise Refused("P15-B9 protection proof incomplete")
    return {
        "schema": "kwipi-p16b10-existing-dev-rootfs-audit-v1",
        "status": STATUS,
        "source_head_verified_against_checkout": SOURCE_HEAD,
        "packages": {x: packages[x] for x in REQUIRED_PACKAGES},
        "python_modules_verified": 24,
        "p14b_modules_verified": 19,
        "p15b6_modules_verified": 5,
        "python_sha256": installed,
        "p14b_archive_sha256": p16a.PINNED_P14B_ARCHIVE_SHA256,
        "b12_release": B12_VERSION,
        "b12_sha256": binaries,
        "current_points_to_b12": True,
        "probe_sha256": probe,
        "probe_systemd_symlink_found": False,
        "kwipi_account_isolated_from_motor": True,
        "oem_operator_preserved": True,
        "do_rootfs_exit_zero_operator_declared_not_independently_attested": True,
        "dev_shipping_effective_metadata_rechecked_by_this_gate": False,
        "shipping_image_checked": False,
        "manifest_rootfs_association_independently_attested": False,
        "runtime_service_or_socket_acl_verified": False,
        "license_redistribution_approved": False,
        "rauc_signed_or_verified": False,
        "robot_validated": False,
        "motor_commands_issued": 0,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rootfs", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--do-rootfs-exit", required=True, type=int)
    p.add_argument("--source-head", required=True)
    p.add_argument("--source-root", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    try:
        if a.report.exists() or a.report.is_symlink():
            raise Refused("report already exists or linked")
        result = validate(a.rootfs, a.manifest, builder_exit=a.do_rootfs_exit,
                          source_head=a.source_head, source_root=a.source_root)
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    except (Refused, ValueError, OSError, UnicodeError, KeyError) as exc:
        p.exit(1, "P16_B10_STOP: " + type(exc).__name__ + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
