"""P15-B18: audit opt-in DEV-only B17 source package selection in BitBake -e.

Composes the existing B10, B17, P14C and B9 guards. Does NOT call BitBake,
build, install, enable mediad, change permissions, write SQLite or touch the
original B10 rootfs. The CI separately supplies *real* pinned -p/-e output;
unit tests use synthetic metadata and are not evidence of a BitBake run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import stat
import tarfile

from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6
from scripts import per_p15b10_dev_passive_env_gate as b10
from scripts import per_p15b17_oem_receiver_package as b17
from scripts.per_p13a_bitbake_env_gate import EnvRefused, bbvar

LAYER_REL = "yocto/meta-kwipi-p15-b12-receiver-selection"
CONF = "conf/layer.conf"
APPEND = "recipes-core/images/microduck-image-dev.bbappend"
SCHEMA = "kwipi-p15b18-dev-only-b12-receiver-metadata-v1"
STATUS = "p15b18_supplied_effective_dev_only_metadata_verified_not_image"
PACKAGE = b17.PACKAGE
PYTHON_DIR = "/usr/lib/python3.14/site-packages"
LAYER_CONF = (
    'BBPATH .= ":@{LAYERDIR}"\n'
    'BBFILES += "@{LAYERDIR}/recipes-*/*/*.bbappend"\n'
    'BBFILE_COLLECTIONS += "kwipib18"\n'
    'BBFILE_PATTERN_kwipib18 := "^@{LAYERDIR}/"\n'
    'BBFILE_PRIORITY_kwipib18 = "27"\n'
    'LAYERVERSION_kwipib18 = "1"\n'
    'LAYERDEPENDS_kwipib18 = "core microduck kwipipy kwipidev kwipipassive kwipiaccount kwipib10 kwipib17"\n'
    'LAYERSERIES_COMPAT_kwipib18 = "wrynose"\n'
).replace("@{", "\x24{")
IMAGE_APPEND = (
    "# P15-B18: opt-in, DEV-only selection of the reviewed four B13-B16 source modules.\n"
    "# No service, executable enable flag, camera, model, account or motor permission.\n"
    "# Existing rootfs B10 remains a distinct, unmodified historical artifact.\n"
    'IMAGE_INSTALL:append = " kwipi-b12-receiver"\n'
)


def tokens(value: str) -> list[str]:
    return value.replace("\\n", " ").replace("\\t", " ").split()


def closed_layer(layer: Path) -> Path:
    if layer.is_symlink() or not layer.is_dir():
        raise EnvRefused("B18 selection layer missing or symlinked")
    expected = {CONF: LAYER_CONF, APPEND: IMAGE_APPEND}
    actual = {p.relative_to(layer).as_posix()
              for p in layer.rglob("*") if p.is_file() or p.is_symlink()}
    if actual != set(expected):
        raise EnvRefused("B18 selection layer contains missing or extra files")
    for name, text in expected.items():
        p = layer / name
        if p.is_symlink() or not p.is_file() or p.read_text(encoding="utf-8") != text:
            raise EnvRefused("B18 selection layer differs from exact reviewed source")
    return layer.resolve(strict=True)


def source_gate(project: Path, *, selection_layer: Path,
                b10_selection: Path, receiver_layer: Path, addon_layer: Path,
                dev_layer: Path, python_layer: Path, account_layer: Path
                ) -> tuple[dict, dict, dict]:
    if project.is_symlink() or not project.is_dir():
        raise EnvRefused("project checkout absent or symlinked")
    root = project.resolve(strict=True)
    closed_layer(selection_layer)
    if (account_layer.is_symlink() or not account_layer.is_dir()
            or dev_layer.is_symlink() or not dev_layer.is_dir()):
        raise EnvRefused("required DEV account or image selection layer absent")
    base, addon = b10.source_gate(
        root, selection_layer=b10_selection, addon_layer=addon_layer,
        python_layer=python_layer,
    )
    receiver = b17.verify(root, receiver_layer)
    if (receiver.get("schema") != b17.SCHEMA
            or receiver.get("status") != "b17_source_only_b12_receiver_candidate_not_bitbake"
            or receiver.get("new_modules") != 4
            or set(receiver.get("new_sha256", {})) != b17.SELECTED
            or receiver.get("historical_python_modules") != 24
            or receiver.get("historical_b6_sha256") != b17.b10.B6_SHA256
            or receiver.get("historical_p14b_archive_sha256") != b17.p16a.PINNED_P14B_ARCHIVE_SHA256
            or receiver.get("source_revision") != base.get("source_revision")
            or receiver.get("source_revision") != addon.get("source_revision")
            or receiver.get("oem_yocto_sha") != p14b.YOCTO_SHA
            or receiver.get("license_redistribution_approved") is not False
            or any(receiver.get(key) is not False for key in (
                "bitbake_executed", "bitbake_parsed", "dev_image_selected",
                "shipping_image_selected", "rootfs_modified",
                "service_installed", "oem_producer_enabled", "oem_sensor_verified",
                "robot_validated"))
            or receiver.get("motor_commands_issued") != 0):
        raise EnvRefused("B17 source is no longer the unselected 24+4 candidate")
    return base, addon, receiver


def validate(dev_env: str, shipping_env: str, appends: str, recipe_env: str,
             checksum: str, *, selection_layer: Path, b10_selection: Path,
             receiver_layer: Path, addon_layer: Path, dev_layer: Path,
             python_layer: Path, account_layer: Path,
             base_provenance: dict, addon_provenance: dict,
             receiver_provenance: dict) -> dict:
    """Check supplied *effective* metadata, not that BitBake was run."""
    previous = b10.validate(
        dev_env, shipping_env, appends,
        selection_layer=b10_selection, addon_layer=addon_layer,
        dev_layer=dev_layer, python_layer=python_layer,
        account_layer=account_layer, base_provenance=base_provenance,
        addon_provenance=addon_provenance,
    )
    if (previous["status"] != "dev_only_passive_selection_effective_metadata_verified"
            or previous["base_modules"] != 19
            or previous["addon_modules"] != 5
            or previous["kwipi_identity_dev_only_without_motor_group"] is not True
            or previous["oem_packages_preserved"] is not True):
        raise EnvRefused("B10 baseline gate failed")

    # A test can inject an untrustworthy provenance object. Reject it even if
    # the fixed selection recipe and synthetic BitBake environment look fine.
    if (receiver_provenance.get("schema") != b17.SCHEMA
            or receiver_provenance.get("status") != "b17_source_only_b12_receiver_candidate_not_bitbake"
            or receiver_provenance.get("new_modules") != 4
            or set(receiver_provenance.get("new_sha256", {})) != b17.SELECTED
            or receiver_provenance.get("historical_python_modules") != 24
            or receiver_provenance.get("historical_b6_sha256") != b17.b10.B6_SHA256
            or receiver_provenance.get("historical_p14b_archive_sha256") != b17.p16a.PINNED_P14B_ARCHIVE_SHA256
            or receiver_provenance.get("source_revision") != base_provenance.get("source_revision")
            or receiver_provenance.get("source_revision") != addon_provenance.get("source_revision")
            or receiver_provenance.get("oem_yocto_sha") != p14b.YOCTO_SHA
            or receiver_provenance.get("license_redistribution_approved") is not False
            or any(receiver_provenance.get(key) is not False for key in (
                "bitbake_executed", "bitbake_parsed", "dev_image_selected",
                "shipping_image_selected", "rootfs_modified", "service_installed",
                "oem_producer_enabled", "oem_sensor_verified", "robot_validated"))
            or receiver_provenance.get("motor_commands_issued") != 0):
        raise EnvRefused("B17 provenance changed or was promoted")
    selected = closed_layer(selection_layer)
    source = receiver_layer.resolve(strict=True)
    required_layers = {selected, source}
    for env, expected_pn, count in ((dev_env, "microduck-image-dev", 1),
                                     (shipping_env, "microduck-image", 0)):
        if bbvar(env, "PN") != expected_pn:
            raise EnvRefused("wrong image recipe")
        packages = tokens(bbvar(env, "IMAGE_INSTALL"))
        if packages.count(PACKAGE) != count:
            raise EnvRefused("B17 receiver absent/duplicated/leaked into shipping")
        if not required_layers.issubset({
                Path(x).resolve() for x in tokens(bbvar(env, "BBLAYERS"))}):
            raise EnvRefused("B17 recipe or B18 selection layer not effective")
    b10._require_dev_only_append(appends, selected / APPEND)

    # The selected *recipe* must be the same 4-file B17 tar, not a different
    # source/version/architecture hidden behind an accepted image append.
    keys = ("PN", "PV", "LICENSE", "PACKAGE_ARCH", "SRC_URI", "BP",
            "S", "UNPACKDIR", "PYTHON_SITEPACKAGES_DIR", "BBLAYERS")
    vals = {name: bbvar(recipe_env, name) for name in keys}
    if (vals["PN"] != PACKAGE or vals["PV"] != b17.VERSION
            or vals["LICENSE"] != "CLOSED" or vals["PACKAGE_ARCH"] != "all"
            or vals["PYTHON_SITEPACKAGES_DIR"] != PYTHON_DIR
            or vals["BP"] != PACKAGE + "-" + b17.VERSION):
        raise EnvRefused("wrong receiver package, license or target Python ABI")
    expected_uri = f"file://{b17.ARCHIVE};subdir={vals['BP']};name=p15b17"
    if tokens(vals["SRC_URI"]) != [expected_uri]:
        raise EnvRefused("receiver source archive missing, duplicated or mixed")
    if (vals["S"] != vals["UNPACKDIR"].rstrip("/") + "/" + vals["BP"]
            or not vals["UNPACKDIR"].startswith("/")):
        raise EnvRefused("receiver source unpack directory not pinned")
    if (not re.fullmatch(r"[0-9a-f]{64}", checksum.strip())
            or checksum.strip() != receiver_provenance.get("archive_sha256")):
        raise EnvRefused("effective named B17 checksum differs from exact source tar")
    resolved_rdepends = tokens(bbvar(recipe_env, "RDEPENDS:" + PACKAGE))
    if set(resolved_rdepends) != set(b17.RUNTIME) or len(resolved_rdepends) != len(b17.RUNTIME):
        raise EnvRefused("receiver runtime dependencies changed or include privileges")
    if not required_layers.issubset({
            Path(x).resolve() for x in tokens(vals["BBLAYERS"])}):
        raise EnvRefused("receiver recipe did not use selected source layers")

    return {
        "schema": SCHEMA,
        "status": STATUS,
        "base_modules": 19,
        "passive_modules": 5,
        "receiver_modules": 4,
        "dev_receiver_count": 1,
        "shipping_receiver_count": 0,
        "oem_packages_preserved": True,
        "kwipi_account_isolated_by_effective_metadata": True,
        "source_receiver_sha256": receiver_provenance["archive_sha256"],
        "receiver_recipe_version": b17.VERSION,
        "receiver_recipe_license": "CLOSED",
        "receiver_rdepends_checked": True,
        "selected_dev_only_append_checked": True,
        "bitbake_environment_supplied_by_caller": True,
        "bitbake_executed_by_this_gate": False,
        "rootfs_or_package_built_by_this_gate": False,
        "new_dev_rootfs_installed": False,
        "shipping_image_changed": False,
        "systemd_service_activated": False,
        "oem_producer_activated": False,
        "robot_sensor_validated": False,
        "robot_validated": False,
        "motor_commands_issued": 0,
    }


def _read_plain(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise EnvRefused("input metadata missing or symlinked")
    return path.read_text(encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("project", "selection-layer", "b10-selection",
                 "receiver-layer", "addon-layer", "dev-layer",
                 "python-layer", "account-layer", "dev-env", "shipping-env",
                 "recipe-env", "checksum-value-file", "appends", "report"):
        p.add_argument("--" + name, type=Path, required=True)
    args = p.parse_args()
    try:
        if args.report.exists() or args.report.is_symlink():
            raise EnvRefused("refuse to overwrite B18 metadata report")
        base, addon, receiver = source_gate(
            args.project, selection_layer=args.selection_layer,
            b10_selection=args.b10_selection, receiver_layer=args.receiver_layer,
            addon_layer=args.addon_layer, dev_layer=args.dev_layer,
            python_layer=args.python_layer, account_layer=args.account_layer,
        )
        result = validate(
            b10._private_env(args.dev_env),
            b10._private_env(args.shipping_env),
            _read_plain(args.appends),
            b10._private_env(args.recipe_env),
            _read_plain(args.checksum_value_file).strip(),
            selection_layer=args.selection_layer,
            b10_selection=args.b10_selection, receiver_layer=args.receiver_layer,
            addon_layer=args.addon_layer, dev_layer=args.dev_layer,
            python_layer=args.python_layer, account_layer=args.account_layer,
            base_provenance=base, addon_provenance=addon,
            receiver_provenance=receiver,
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True)
            f.write("\n")
    except (EnvRefused, b6.Refused, b17.Refused, p14b.PackageRefused,
            ValueError, OSError, KeyError, tarfile.TarError) as exc:
        p.exit(1, "P15-B18 STOP: " + type(exc).__name__ + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
