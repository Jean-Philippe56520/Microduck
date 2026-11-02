"""P15-B19: read-only validation of a supplied BitBake B17 packages-split.

The *caller* (CI or operator) must run real pinned BitBake do_package.
This script NEVER runs BitBake, installs, writes OS files or attests that
the task actually executed. Fixtures cannot qualify a robot or a rootfs.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import stat
import tarfile

from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6
from scripts import per_p15b17_oem_receiver_package as b17
from scripts import per_p15b18_dev_receiver_env_gate as b18
from scripts import per_p15b10_dev_passive_env_gate as b10
from scripts.per_p13a_bitbake_env_gate import EnvRefused, bbvar

SCHEMA = "kwipi-p15b19-real-receiver-package-split-v1"
PASS = "b19_supplied_pkgdest_four_b12_python_files_verified_not_rootfs"
PACKAGE = b17.PACKAGE
PYDIR = b18.PYTHON_DIR.lstrip("/") + "/microduck_companion"


def _checked_package_dir(recipe_env: str) -> tuple[Path, Path]:
    """Refuse a moved/linked build tree; read exclusively under TMPDIR."""
    tmpdir = Path(bbvar(recipe_env, "TMPDIR"))
    pkgdest = Path(bbvar(recipe_env, "PKGDEST"))
    if (not tmpdir.is_absolute() or not pkgdest.is_absolute()
            or not tmpdir.is_dir() or tmpdir.is_symlink()
            or not pkgdest.is_dir() or pkgdest.is_symlink()
            or pkgdest == tmpdir
            or not pkgdest.resolve(strict=True).is_relative_to(
                tmpdir.resolve(strict=True))):
        raise EnvRefused("B19 PKGDEST absent, redirected or outside TMPDIR")
    relative = pkgdest.relative_to(tmpdir) if pkgdest.is_relative_to(tmpdir) else None
    if relative is None or any(
            (tmpdir / Path(*relative.parts[:i])).is_symlink()
            for i in range(1, len(relative.parts) + 1)):
        raise EnvRefused("B19 PKGDEST linked intermediate directory")
    return tmpdir, pkgdest


def inspect_split(recipe_env: str, *, receiver_source: dict, metadata: dict) -> dict:
    """Inspect package source bytes and negative space, never execute a task."""
    if (metadata.get("schema") != b18.SCHEMA
            or metadata.get("status") != b18.STATUS
            or metadata.get("dev_receiver_count") != 1
            or metadata.get("shipping_receiver_count") != 0
            or metadata.get("oem_packages_preserved") is not True
            or metadata.get("kwipi_account_isolated_by_effective_metadata") is not True
            or metadata.get("receiver_rdepends_checked") is not True
            or metadata.get("source_receiver_sha256") != receiver_source.get("archive_sha256")
            or metadata.get("receiver_recipe_license") != "CLOSED"
            or metadata.get("receiver_recipe_version") != b17.VERSION
            or receiver_source.get("schema") != b17.SCHEMA
            or receiver_source.get("new_modules") != 4
            or set(receiver_source.get("new_sha256", {})) != b17.SELECTED
            or receiver_source.get("historical_python_modules") != 24
            or receiver_source.get("license_redistribution_approved") is not False
            or receiver_source.get("service_installed") is not False
            or receiver_source.get("oem_producer_enabled") is not False
            or receiver_source.get("robot_validated") is not False):
        raise EnvRefused("B17/B18 source or DEV-only metadata is not reviewed")

    _, pkgdest = _checked_package_dir(recipe_env)
    package = pkgdest / PACKAGE
    target = package / PYDIR
    if (not package.is_dir() or package.is_symlink()
            or not target.is_dir() or target.is_symlink()
            or not target.resolve(strict=True).is_relative_to(
                package.resolve(strict=True))):
        raise EnvRefused("B19 main package Python directory not present")

    # Every ordinary file in the main package must be one of the four
    # unchanged, nonexecutable sources. No service, module cache, native ELF,
    # local media, SQLite, model, symlink, hidden file or extra directories.
    expected = {target / Path(n).name: n for n in b17.SELECTED}
    if len(expected) != 4:
        raise EnvRefused("B19 duplicate source basenames")
    expected_dirs = set()
    parent = target
    while parent != package:
        expected_dirs.add(parent)
        parent = parent.parent
    actual_files = set()
    actual_dirs = set()
    for path in package.rglob("*"):
        if path.is_symlink():
            raise EnvRefused("B19 symlink in main package")
        if path.is_dir():
            actual_dirs.add(path)
        elif path.is_file() and stat.S_ISREG(path.lstat().st_mode):
            actual_files.add(path)
        else:
            raise EnvRefused("B19 nonregular main package entry")
    if actual_dirs != expected_dirs or actual_files != set(expected):
        raise EnvRefused("B19 package has an extra or missing file/directory")

    sizes = {}
    for path, source_name in sorted(expected.items()):
        attrs = path.lstat()
        if (not stat.S_ISREG(attrs.st_mode)
                or stat.S_IMODE(attrs.st_mode) != 0o644):
            raise EnvRefused("B19 Python module must be an ordinary 0644 file")
        contents = path.read_bytes()
        if sha256(contents).hexdigest() != receiver_source["new_sha256"][source_name]:
            raise EnvRefused("B19 packaged bytes differ from reviewed B17 source")
        sizes[source_name] = len(contents)

    # BitBake normally creates empty -dev/-dbg/-src/... splits. They may exist
    # but no foreign split may contain additional content, links or scripts.
    for other in pkgdest.iterdir():
        if other == package:
            continue
        if other.is_symlink() or not other.is_dir():
            raise EnvRefused("B19 unexpected non-directory package split")
        for path in other.rglob("*"):
            if path.is_symlink() or not path.is_dir():
                raise EnvRefused("B19 unreviewed payload in another package split")

    return {
        "schema": SCHEMA,
        "status": PASS,
        "package": PACKAGE,
        "package_version": b17.VERSION,
        "source_archive_sha256": receiver_source["archive_sha256"],
        "source_revision": receiver_source["source_revision"],
        "oem_yocto_sha": receiver_source["oem_yocto_sha"],
        "historical_python_modules_preserved_in_source": 24,
        "receiver_modules_in_package_split": 4,
        "packaged_source_sha256": dict(sorted(receiver_source["new_sha256"].items())),
        "packaged_source_sizes": dict(sorted(sizes.items())),
        "main_package_has_only_four_python_sources": True,
        "other_splits_contain_no_files": True,
        "dev_selection_effective_metadata_verified": True,
        "shipping_receiver_count": 0,
        "kwipi_account_isolated_in_metadata": True,
        "real_pkgdest_contents_inspected_by_gate": True,
        "bitbake_do_package_execution_attested_by_gate": False,
        "rootfs_built": False,
        "dev_image_installed": False,
        "shipping_image_changed": False,
        "service_installed": False,
        "oem_detector_activated": False,
        "sensor_verified": False,
        "physical_robot_verified": False,
        "motor_commands_issued": 0,
    }


def validate_package(project: Path, *, selection_layer: Path,
                     b10_selection: Path, receiver_layer: Path,
                     addon_layer: Path, dev_layer: Path, python_layer: Path,
                     account_layer: Path, recipe_env: str, dev_env: str,
                     shipping_env: str, appends: str, checksum: str) -> dict:
    """Compose B18 exact effective metadata and B17 exact source, then PKGDEST."""
    base, addon, receiver = b18.source_gate(
        project, selection_layer=selection_layer, b10_selection=b10_selection,
        receiver_layer=receiver_layer, addon_layer=addon_layer,
        dev_layer=dev_layer, python_layer=python_layer,
        account_layer=account_layer,
    )
    metadata = b18.validate(
        dev_env, shipping_env, appends, recipe_env, checksum,
        selection_layer=selection_layer, b10_selection=b10_selection,
        receiver_layer=receiver_layer, addon_layer=addon_layer,
        dev_layer=dev_layer, python_layer=python_layer,
        account_layer=account_layer,
        base_provenance=base, addon_provenance=addon,
        receiver_provenance=receiver,
    )
    return inspect_split(recipe_env, receiver_source=receiver, metadata=metadata)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("project", "selection-layer", "b10-selection",
                 "receiver-layer", "addon-layer", "dev-layer",
                 "python-layer", "account-layer", "recipe-env", "dev-env",
                 "shipping-env", "appends", "checksum-value-file", "report"):
        p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args()
    try:
        if a.report.exists() or a.report.is_symlink():
            raise EnvRefused("refuse to overwrite existing B19 report")
        result = validate_package(
            a.project,
            selection_layer=a.selection_layer,
            b10_selection=a.b10_selection,
            receiver_layer=a.receiver_layer,
            addon_layer=a.addon_layer,
            dev_layer=a.dev_layer,
            python_layer=a.python_layer,
            account_layer=a.account_layer,
            recipe_env=b10._private_env(a.recipe_env),
            dev_env=b10._private_env(a.dev_env),
            shipping_env=b10._private_env(a.shipping_env),
            appends=b18._read_plain(a.appends),
            checksum=b18._read_plain(a.checksum_value_file).strip(),
        )
        a.report.parent.mkdir(parents=True, exist_ok=True)
        with a.report.open("x", encoding="utf-8") as f:
            json.dump(result, f, sort_keys=True, indent=2)
            f.write("\n")
    except (EnvRefused, b6.Refused, b17.Refused, p14b.PackageRefused,
            OSError, ValueError, KeyError, tarfile.TarError) as exc:
        p.exit(1, "P15-B19 STOP: " + type(exc).__name__ + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
