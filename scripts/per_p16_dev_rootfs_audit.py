"""P16: fail-closed inspection of an existing DEV rootfs, never a builder."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

class Refused(ValueError):
    pass

EXPECTED = ("kwipi-companion", "kwipi-readonly-probe")
PROBE_HASHES = {
    "usr/libexec/kwipi/health_probe.py": "11e48364630b2c063d173cd1884a19a886a2467ddead19af1636e072f24ccc21",
    "usr/lib/systemd/system/kwipi-readonly-probe.service": "ed0c6cd92e2a76a0f687e8bf4b32a22be01a26decb47f70cb432f4eef22e5d9d",
    "usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset": "01a3df8c2b3bd1199c18e1ff126bc96ac818262014030beec792f463c8de8ba8",
}
UNIT = "kwipi-readonly-probe.service"

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

def validate(rootfs: Path, manifest: Path, *, builder_exit: int, source_head: str) -> dict:
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
    # No symlink anywhere in the systemd enablement locations for this unit.
    for rel in ("etc/systemd/system", "usr/lib/systemd/system"):
        folder = rootfs / rel
        if folder.is_symlink():
            raise Refused("systemd directory symlink")
        if folder.exists():
            for p in folder.rglob("*"):
                if p.is_symlink() and p.name == UNIT:
                    raise Refused("probe enabled by symlink")
    return {
        "schema": "kwipi-p16-dev-rootfs-offline-audit-v1",
        "status": "existing_dev_rootfs_probe_and_package_manifest_checked_only",
        "source_head": source_head,
        "packages": {k: packages[k] for k in EXPECTED},
        "probe_sha256": files,
        "do_rootfs_exit_attested_by_operator": True,
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
    p.add_argument("--report", type=Path, required=True)
    a = p.parse_args()
    try:
        if a.report.exists() or a.report.is_symlink():
            raise Refused("refusing to overwrite proof")
        result = validate(a.rootfs, a.manifest, builder_exit=a.do_rootfs_exit,
                          source_head=a.source_head)
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    except (Refused, OSError, UnicodeError) as e:
        p.exit(1, "P16 STOP: " + str(e) + "\n")
    print(json.dumps(result, sort_keys=True))

if __name__ == "__main__":
    main()
