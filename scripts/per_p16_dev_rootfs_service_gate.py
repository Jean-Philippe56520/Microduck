"""P16-S1: inspect installed DEV rootfs services without starting anything.

Scope: the P15A unit, systemd references, preset, and deferred-postinst
indicators. Package scriptlet bodies, boot-time behavior and privileges are
NOT certified by this check. No BitBake, writes, sockets or robot operations.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

UNIT_NAME = "kwipi-readonly-probe.service"
UNIT_REL = "usr/lib/systemd/system/" + UNIT_NAME
PRESET_REL = "usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset"
PROBE_REL = "usr/libexec/kwipi/health_probe.py"
EXPECTED_SHA256 = {
    UNIT_REL: "ed0c6cd92e2a76a0f687e8bf4b32a22be01a26decb47f70cb432f4eef22e5d9d",
    PRESET_REL: "01a3df8c2b3bd1199c18e1ff126bc96ac818262014030beec792f463c8de8ba8",
    PROBE_REL: "11e48364630b2c063d173cd1884a19a886a2467ddead19af1636e072f24ccc21",
}
REPORT_STATUS = "existing_dev_rootfs_probe_and_package_manifest_checked_only"
SYSTEMD_DIRS = (
    "etc/systemd/system", "usr/lib/systemd/system", "lib/systemd/system",
    "usr/local/lib/systemd/system",
)
PRESET_DIRS = (
    "etc/systemd/system-preset", "usr/lib/systemd/system-preset",
    "lib/systemd/system-preset",
)
POSTINST_DIRS = ("etc/opkg-postinsts", "etc/rpm-postinsts", "etc/postinsts")
REF = re.compile(r"kwipi-readonly-probe(?:\.service)?|/usr/libexec/kwipi/health_probe\.py")
SECTION_INSTALL = re.compile(r"[ \t]*\[Install\][ \t]*")
UNIT_EXTENSIONS = {".service", ".socket", ".target", ".path", ".timer", ".mount",
                   ".automount", ".swap", ".slice", ".conf", ".busname"}

class Stop(ValueError):
    pass


def _fail(message: str) -> None:
    raise Stop(message)


def _safe_file(root: Path, relative: str) -> Path:
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            _fail("symbolic link in audited file: " + relative)
    if not current.is_file():
        _fail("audited file missing: " + relative)
    if not current.resolve().is_relative_to(root.resolve()):
        _fail("audited file escapes rootfs")
    return current


def _image_dir(root: Path, relative: str) -> Path | None:
    """Resolve /lib -> /usr/lib style links *inside* the offline image."""
    current = root
    for part in Path(relative).parts:
        current = current / part
        for _ in range(8):
            if not current.is_symlink():
                break
            link = current.readlink()
            current = ((root / str(link).lstrip("/")) if link.is_absolute()
                       else (current.parent / link))
        else:
            _fail("symlink chain too deep in scanned directory: " + relative)
        if not current.resolve().is_relative_to(root.resolve()):
            _fail("systemd directory escapes rootfs: " + relative)
        if not current.exists():
            return None
    if not current.is_dir():
        _fail("scanned systemd location is not a directory: " + relative)
    return current.resolve()


def _real_dirs(root: Path, paths: tuple[str, ...]) -> list[Path]:
    selected: list[Path] = []
    seen: set[Path] = set()
    for rel in paths:
        resolved = _image_dir(root, rel)
        if resolved is not None and resolved not in seen:
            seen.add(resolved)
            selected.append(resolved)
    return selected


def _text_lines(path: Path) -> list[str]:
    if path.stat().st_size > 512 * 1024:
        _fail("systemd file too large for bounded check: " + path.name)
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def validate(base: Path) -> dict:
    base = base.resolve(strict=True)
    roots = [p for p in (base / "build/tmp/work").glob(
        "*/microduck-image-dev/*/rootfs") if p.is_dir() and not p.is_symlink()]
    if len(roots) != 1:
        _fail("expected exactly one existing DEV rootfs")
    root = roots[0].resolve(strict=True)
    report_path = base / "proofs/p16-rootfs-audit.json"
    if not report_path.is_file() or report_path.is_symlink():
        _fail("P16-A report not found or symlinked")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if (report.get("status") != REPORT_STATUS or
        report.get("python_modules_verified") != 19 or
        report.get("probe_systemd_symlink_found") is not False or
        len(report.get("probe_sha256", {})) != 3):
        _fail("existing P16-A proof does not match expected scope")
    for rel, digest in EXPECTED_SHA256.items():
        file = _safe_file(root, rel)
        if report["probe_sha256"].get(rel) != digest:
            _fail("P16-A report checksum mismatch: " + rel)
        if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            _fail("rootfs installed bytes changed: " + rel)

    unit = _text_lines(root / UNIT_REL)
    if any(SECTION_INSTALL.fullmatch(line) for line in unit):
        _fail("real [Install] section in unit")
    preset = _text_lines(root / PRESET_REL)
    if "\n".join(preset).strip() != "disable " + UNIT_NAME:
        _fail("probe preset is not exactly disable")
    if not any(line.strip() == "SupplementaryGroups=robot" for line in unit):
        _fail("reviewed privileged group was silently changed")

    systemd_dirs = _real_dirs(root, SYSTEMD_DIRS)
    if not systemd_dirs:
        _fail("systemd directories not available")
    examined = 0
    for folder in systemd_dirs:
        for path in folder.rglob("*"):
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                target = path.readlink().as_posix()
                if path.name == UNIT_NAME or REF.search(target):
                    _fail("probe referenced by systemd symlink: " + rel)
                continue
            if path.is_dir() and path.name == UNIT_NAME + ".d":
                _fail("probe unit drop-in override found: " + rel)
            if not path.is_file():
                continue
            if path.name == UNIT_NAME:
                if path.resolve() != (root / UNIT_REL).resolve():
                    _fail("probe unit override or duplicate: " + rel)
                continue
            if path.suffix not in UNIT_EXTENSIONS:
                continue
            examined += 1
            for line in _text_lines(path):
                clean = line.lstrip()
                if clean.startswith(("#", ";")):
                    continue
                if REF.search(clean):
                    _fail("other unit contains live probe reference: " + rel)

    checked_presets = 0
    for folder in _real_dirs(root, PRESET_DIRS):
        for path in folder.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            checked_presets += 1
            if path.resolve() == (root / PRESET_REL).resolve():
                continue
            for line in _text_lines(path):
                clean = line.strip()
                if clean.startswith(("#", ";")):
                    continue
                if REF.search(clean):
                    _fail("unreviewed systemd preset references probe: " + path.name)

    pending = []
    for folder in _real_dirs(root, POSTINST_DIRS):
        pending.extend(x for x in folder.rglob("*") if x.is_file() or x.is_symlink())
    if pending:
        _fail("deferred postinst entries remain in known rootfs locations")

    return {
        "status": "p16_s1_no_observed_probe_autostart_references_in_scanned_rootfs",
        "p16_a_report_rechecked": True,
        "installed_probe_files_rehashed": 3,
        "other_systemd_files_examined": examined,
        "systemd_preset_files_examined": checked_presets,
        "probe_autostart_references_found": 0,
        "deferred_postinst_entries_in_known_dirs": 0,
        "postinst_package_scriptlets_audited": False,
        "systemd_runtime_or_boot_verified": False,
        "robot_socket_group_full_rpc_access_risk_open": True,
        "license_redistribution_approved": False,
        "image_built": False,
        "robot_validated": False,
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        result = validate(args.base)
    except (Stop, OSError, UnicodeError, json.JSONDecodeError) as exc:
        parser.exit(1, "P16_S1_STOP: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
