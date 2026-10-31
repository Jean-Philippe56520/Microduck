"""P16: fail-closed inspection of an existing DEV rootfs, never a builder."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

from scripts.per_p14b_yocto_python_layer import staged_files

class Refused(ValueError):
    pass

EXPECTED = ("kwipi-companion", "kwipi-readonly-probe")
PROBE_HASHES = {
    "usr/libexec/kwipi/health_probe.py": "11e48364630b2c063d173cd1884a19a886a2467ddead19af1636e072f24ccc21",
    "usr/lib/systemd/system/kwipi-readonly-probe.service": "ed0c6cd92e2a76a0f687e8bf4b32a22be01a26decb47f70cb432f4eef22e5d9d",
    "usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset": "01a3df8c2b3bd1199c18e1ff126bc96ac818262014030beec792f463c8de8ba8",
}
UNIT = "kwipi-readonly-probe.service"
PINNED_P14B_ARCHIVE_SHA256 = "85c583b86f0c8b5c59e9a547762a223c7ab27dee016c3ec604141907b20b2245"
PYTHON_PREFIX = "usr/lib/python3.14/site-packages/"

def _under(root: Path, relative: str) -> Path:
    p = root
    for part in Path(relative).parts:
        p = p / part
        if p.is_symlink():
            raise Refused("symlink refused: " + relative)
    if not p.is_file():
        raise Refused("missing file: " + relative)
    if not p.resolve().is_relative_to(root.resolve()):
        raise Refused("path escapes rootfs")
    return p

def _parse_manifest(path: Path) -> dict[str, str]:
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) < 3:
            raise Refused("malformed package manifest")
        name, arch, version = fields[:3]
        if name in found:
            raise Refused("duplicate package: " + name)
        found[name] = version
    return found


def _verify_python_slice(rootfs: Path, source_root: Path, source_head: str) -> dict[str, str]:
    """Compare all 19 installed modules to the independently packaged P14B slice."""
    if source_root.is_symlink() or not source_root.is_dir():
        raise Refused("source checkout absent or symlinked")
    try:
        _files, proof = staged_files(source_root)
    except (OSError, ValueError, KeyError) as exc:
        raise Refused("P14B audited source slice could not be regenerated") from exc
    if proof["source_revision"] != source_head:
        raise Refused("operator-declared source head differs from git revision")
    if proof["source_archive_sha256"] != PINNED_P14B_ARCHIVE_SHA256:
        raise Refused("P14B audited source archive checksum changed")
    entries = proof["source_sha256"]
    selected = {Path(k).name for k in entries if k.endswith(".py")}
    if len(selected) != 19 or len(entries) != 20:
        raise Refused("P14B 19-module closure changed")
    package = rootfs / PYTHON_PREFIX / "microduck_companion"
    if package.is_symlink() or not package.is_dir():
        raise Refused("target Python 3.14 package directory absent")
    files = {}
    installed = {p.name for p in package.iterdir() if p.suffix == ".py"}
    if installed != selected:
        raise Refused("installed Python module list differs from P14B")
    for rel, expected in entries.items():
        if not rel.endswith(".py"):
            continue
        target = _under(rootfs, PYTHON_PREFIX + rel)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != expected:
            raise Refused("installed Python module bytes differ from P14B: " + rel)
        files[rel] = digest
    return files

def validate(rootfs: Path, manifest: Path, *, builder_exit: int, source_head: str, source_root: Path | None = None) -> dict:
    if builder_exit != 0:
        raise Refused("real do_rootfs exit zero not attested")
    if not re.fullmatch(r"[0-9a-f]{40}", source_head):
        raise Refused("source revision missing")
    if rootfs.is_symlink() or not rootfs.is_dir():
        raise Refused("rootfs directory missing")
    rootfs = rootfs.resolve(strict=True)
    if manifest.is_symlink() or not manifest.is_file():
        raise Refused("actual image manifest missing")
    packages = _parse_manifest(manifest)
    for name in EXPECTED + ("microduck-daemon", "microduck-data"):
        if name not in packages:
            raise Refused("required package absent: " + name)
    if any(name.startswith("kwipi-") and name not in EXPECTED for name in packages):
        raise Refused("unexpected Kwipi package")
    files = {}
    for path, expected in PROBE_HASHES.items():
        p = _under(rootfs, path)
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        if digest != expected:
            raise Refused("packaged probe bytes drift: " + path)
        files[path] = digest
    if source_root is None:
        raise Refused("source checkout required for P14B module provenance")
    python_files = _verify_python_slice(rootfs, source_root, source_head)
    # No symlink anywhere in the systemd enablement locations for this unit.
    for rel in ("etc/systemd/system", "usr/lib/systemd/system"):
        folder = rootfs / rel
        if folder.is_symlink():
            raise Refused("systemd directory symlink")
        if folder.exists():
            for p in folder.rglob("*"):
                if p.name == UNIT and (p.is_symlink() or ".wants" in p.parts or ".requires" in p.parts or ".upholds" in p.parts):
                    raise Refused("probe enabled or required by unit link")
    return {
        "schema": "kwipi-p16-dev-rootfs-offline-audit-v1",
        "status": "existing_dev_rootfs_probe_and_package_manifest_checked_only",
        "source_head_verified_against_checkout": source_head,
        "packages": {k: packages[k] for k in EXPECTED},
        "probe_sha256": files,
        "python_modules_verified": len(python_files),
        "p14b_archive_sha256": PINNED_P14B_ARCHIVE_SHA256,
        "do_rootfs_exit_zero_operator_declared_not_independently_attested": True,
        "probe_systemd_symlink_found": False,
        "shipping_image_checked": False,
        "license_redistribution_approved": False,
        "rauc_signed_or_verified": False,
        "robot_validated": False,
    }

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rootfs", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--do-rootfs-exit", type=int, required=True)
    p.add_argument("--source-head", required=True)
    p.add_argument("--source-root", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    try:
        if a.report.exists() or a.report.is_symlink():
            raise Refused("refusing to overwrite proof")
        result = validate(a.rootfs, a.manifest, builder_exit=a.do_rootfs_exit,
                          source_head=a.source_head, source_root=a.source_root)
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    except (Refused, OSError, UnicodeError) as e:
        p.exit(1, "P16 STOP: " + str(e) + "\n")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
