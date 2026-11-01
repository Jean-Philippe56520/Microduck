"""P15-B6-P: inspect REAL BitBake do_package split, never a robot/rootfs proof.

The validator can also be run on deliberate synthetic fixtures, which are
not proof of do_package execution; only the CI job can attest task completion.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from scripts.per_p13a_bitbake_env_gate import EnvRefused, bbvar
from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6
from scripts.per_p15b6_bitbake_unpack_gate import validate_metadata

SCHEMA = "kwipi-p15b6-real-bitbake-package-files-v1"
PASS = "bitbake_passive_addon_package_files_verified_only"


def validate_package(root: Path, base_layer: Path, addon_layer: Path,
                     dev_layer: Path, recipe: str, dev: str, shipping: str,
                     checksum: str) -> dict:
    root = root.resolve(strict=True)
    base_layer = base_layer.resolve(strict=True)
    addon_layer = addon_layer.resolve(strict=True)
    dev_layer = dev_layer.resolve(strict=True)
    base_report = p14b.verify(root, base_layer)
    addon_report = b6.verify(root, addon_layer)
    if (base_report["selected_python_modules"] != 19
            or addon_report["base_sha256"] != {
                p: sha256((root / p).read_bytes()).hexdigest()
                for p in p14b.p14a.SELECTED
            } or addon_report["addon_modules"] != 5):
        raise EnvRefused("P14B/P15-B6 source sets changed")
    values = validate_metadata(
        recipe, dev, shipping,
        base_layer=base_layer, addon_layer=addon_layer, dev_layer=dev_layer,
        digest=addon_report["archive_sha256"], checksum=checksum)

    pkgdest = Path(bbvar(recipe, "PKGDEST"))
    tmpdir = Path(values["TMPDIR"])
    if (not pkgdest.is_absolute() or not tmpdir.is_absolute()
            or not pkgdest.is_dir() or not tmpdir.is_dir()
            or pkgdest.is_symlink() or tmpdir.is_symlink()
            or not pkgdest.resolve().is_relative_to(tmpdir.resolve())):
        raise EnvRefused("do_package split missing/outside TMPDIR")
    package_root = pkgdest / b6.PN
    target = package_root / values["PYTHON_SITEPACKAGES_DIR"].lstrip("/") / "microduck_companion"
    if (not package_root.is_dir() or package_root.is_symlink()
            or not target.is_dir() or target.is_symlink()
            or not target.resolve().is_relative_to(package_root.resolve())):
        raise EnvRefused("main package has no reviewed target Python module directory")

    files = sorted(p for p in package_root.rglob("*") if p.is_file() or p.is_symlink())
    expected = {target / Path(p).name for p in b6.ADDON}
    if set(files) != expected or len(files) != 5:
        raise EnvRefused("main BitBake package has extra/missing files (five .py expected)")
    if any(p.is_symlink() or not p.is_file() for p in package_root.rglob("*")
           if p.is_symlink() or p.is_file()):
        raise EnvRefused("package contains symlink/non-regular file")
    if any(p.is_symlink() for p in package_root.rglob("*")):
        raise EnvRefused("package contains unreviewed symlink")
    if any(p.stat().st_mode & 0o111 for p in files):
        raise EnvRefused("Python sources must not be executable")
    for rel in sorted(b6.ADDON):
        file = target / Path(rel).name
        if sha256(file.read_bytes()).hexdigest() != addon_report["addon_sha256"][rel]:
            raise EnvRefused("packaged Python source SHA differs: " + rel)
    # Ensure the package directory tree contains no additional invisible
    # directories, scripts or models masquerading as empty content.
    expected_dirs = {package_root}
    p = target
    while p != package_root:
        expected_dirs.add(p)
        p = p.parent
    actual_dirs = {p for p in package_root.rglob("*") if p.is_dir()}
    if actual_dirs != expected_dirs - {package_root}:
        raise EnvRefused("package contains an extra directory")

    return {
        "schema": SCHEMA,
        "status": PASS,
        "source_revision": addon_report["source_revision"],
        "oem_yocto_sha": p14b.YOCTO_SHA,
        "base_modules_preserved": 19,
        "addon_modules_packaged": 5,
        "addon_archive_sha256": addon_report["archive_sha256"],
        "packaged_sha256": {p: addon_report["addon_sha256"][p] for p in sorted(b6.ADDON)},
        "target_python_sitepackages": values["PYTHON_SITEPACKAGES_DIR"],
        "addon_rdepends_base": True,
        "dev_image_selects_addon": False,
        "shipping_image_selects_addon": False,
        "package_split_files_verified": True,
        "bitbake_task_execution_attested_by_this_script": False,
        "bitbake_do_package_run_attested_by_this_script": False,
        "rootfs_installed": False,
        "service_installed": False,
        "oem_sensor_validated": False,
        "signed_release": False,
        "robot_validated": False,
        "motor_commands_issued": 0,
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    for arg in ("root", "base-layer", "addon-layer", "dev-layer", "recipe-env",
                "dev-env", "shipping-env", "checksum-value-file", "output"):
        cli.add_argument("--" + arg, type=Path, required=True)
    args = cli.parse_args()
    try:
        report = validate_package(
            args.root, args.base_layer, args.addon_layer, args.dev_layer,
            args.recipe_env.read_text(encoding="utf-8"),
            args.dev_env.read_text(encoding="utf-8"),
            args.shipping_env.read_text(encoding="utf-8"),
            args.checksum_value_file.read_text(encoding="utf-8").strip())
        if args.output.exists() or args.output.is_symlink():
            raise EnvRefused("report exists already")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                               encoding="utf-8")
    except (EnvRefused, p14b.PackageRefused, b6.Refused, OSError, ValueError, KeyError) as err:
        cli.exit(1, "P15-B6-P STOP: " + type(err).__name__ + ": " + str(err) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
