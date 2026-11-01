"""PER-P14B: verify effective BitBake Python recipe and its packaged files.

Requires the REAL BitBake -e output and do_package to have completed. A
synthetic environment test is not an ARM64 package or installed rootfs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from scripts.per_p13a_bitbake_env_gate import bbvar, EnvRefused
from scripts.per_p14b_yocto_python_layer import RUNTIME, SRC_NAME, verify as verify_layer

SCHEMA = "kwipi-p14b-real-bitbake-package-proof-v1"
REQUIRED = frozenset({
    "PV", "S", "UNPACKDIR", "BP", "PKGDEST", "TMPDIR", "LICENSE",
    "SRC_URI", "PYTHON_SITEPACKAGES_DIR", "BBLAYERS",
})


def effective_variables(text: str, layer: Path) -> dict[str, str]:
    values = {name: bbvar(text, name) for name in REQUIRED}
    if values["PV"] != "0.2.0a1":
        raise EnvRefused("wrong Python package version")
    if values["LICENSE"] != "CLOSED":
        raise EnvRefused("unreviewed redistribution license promotion")
    parts = values["SRC_URI"].split()
    if len(parts) != 1 or not parts[0].startswith(
            "file://" + SRC_NAME + ";subdir="):
        raise EnvRefused("Python recipe source is not one P14A tar")
    if values["S"].rstrip("/") != values["UNPACKDIR"].rstrip("/") + "/" + values["BP"]:
        raise EnvRefused("source directory differs from verified tar subdir")
    if not values["PYTHON_SITEPACKAGES_DIR"].endswith("/python3.14/site-packages"):
        raise EnvRefused("unexpected pinned OE target Python version")
    if not values["PYTHON_SITEPACKAGES_DIR"].startswith("/usr/lib"):
        raise EnvRefused("Python target path not under official /usr/lib")
    bblayers = values["BBLAYERS"].replace("\\n", " ").replace("\\t", " ").split()
    if layer.resolve() not in {Path(s).resolve() for s in bblayers}:
        raise EnvRefused("kwipipy source layer missing from actual BitBake resolution")
    # OE-core might append auto-discovered Python runtime deps; requiring this
    # exact subset prevents silently dropping any explicit target dependency.
    runtime = bbvar(text, "RDEPENDS:kwipi-companion").split()
    if not RUNTIME.issubset(runtime):
        raise EnvRefused("target Python core/SQLite/IO runtime dependencies missing")
    return values


def validate_package(root: Path, layer: Path, env_text: str) -> dict:
    layer = layer.resolve(strict=True)
    report = verify_layer(root, layer)
    variables = effective_variables(env_text, layer)
    pkgdest = Path(variables["PKGDEST"])
    tmp = Path(variables["TMPDIR"])
    if (not pkgdest.is_absolute() or not tmp.is_absolute()
            or pkgdest.is_symlink() or not pkgdest.is_dir()
            or tmp.is_symlink() or not tmp.is_dir()
            or not pkgdest.resolve().is_relative_to(tmp.resolve())):
        raise EnvRefused("package split directory not created inside BitBake TMPDIR")
    module_dir = pkgdest / "kwipi-companion" / variables["PYTHON_SITEPACKAGES_DIR"].lstrip("/") / "microduck_companion"
    if not module_dir.is_dir() or module_dir.is_symlink():
        raise EnvRefused("BitBake do_package did not install Companion into site-packages")
    selected = {p.rsplit("/", 1)[-1] for p in report["source_sha256"] if p.endswith(".py")}
    actual = {p.name for p in module_dir.iterdir() if p.suffix == ".py"}
    if actual != selected or len(actual) != 19:
        raise EnvRefused("BitBake package module count/source list disagrees with P14A")
    if any(p.is_symlink() or not p.is_file() for p in module_dir.glob("*.py")):
        raise EnvRefused("symbolic or nonregular Python module installed")
    from hashlib import sha256
    for name in actual:
        rel = "microduck_companion/" + name
        digest = sha256((module_dir / name).read_bytes()).hexdigest()
        if digest != report["source_sha256"].get(rel):
            raise EnvRefused("BitBake package Python source differs from P14A: " + rel)
    package_root = pkgdest / "kwipi-companion"
    suspicious = [str(p.relative_to(package_root)) for p in package_root.rglob("*")
                  if p.is_file() and (p.suffix in {".so", ".rknn", ".onnx", ".service", ".sh"}
                                      or p.name.startswith("mock_"))]
    if suspicious:
        raise EnvRefused("unexpected model/binary/mock/service packaged: " + repr(suspicious[:12]))
    # This is a package proof, not proof of installation to any booted rootfs.
    return {
        "schema": SCHEMA,
        "status": "bitbake_python_package_files_verified_only",
        "source_revision": report["source_revision"],
        "source_archive_sha256": report["source_archive_sha256"],
        "python_modules_packaged": 19,
        "python_target_directory": variables["PYTHON_SITEPACKAGES_DIR"],
        "runtime_dependency_floor": sorted(RUNTIME),
        "source_license_checked": False,
        "package_source_bytes_verified": True,
        "bitbake_task_execution_attested_by_this_script": False,
        "rootfs_installed": False,
        "systemd_installed": False,
        "signed_release": False,
        "robot_validated": False,
        "motor_commands_issued": 0,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--layer", type=Path, required=True)
    p.add_argument("--env-file", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        result = validate_package(args.root, args.layer,
                                  args.env_file.read_text(encoding="utf-8"))
        if args.output.exists() or args.output.is_symlink():
            raise EnvRefused("report already exists")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    except (EnvRefused, ValueError, KeyError, OSError) as error:
        p.exit(1, f"PER-P14B STOP: {error}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
