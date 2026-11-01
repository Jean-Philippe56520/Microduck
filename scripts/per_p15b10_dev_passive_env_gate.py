"""P15-B10: fail-closed DEV-only BitBake selection of P15-B6 passive addon.

This gate reads source packages and private effective BitBake metadata.
It never executes BitBake, starts systemd, touches /run or issues motor commands.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import stat
import tarfile

from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6
from scripts.per_p13a_bitbake_env_gate import (
    EnvRefused, bbvar, show_appends_selects_file,
)
from scripts.per_p14c_dev_image_env_gate import validate as p14c_validate
from scripts.per_p15b9_dev_account_env_gate import validate as b9_validate

LAYER_REL = "yocto/meta-kwipi-p15-passive-selection"
CONF = "conf/layer.conf"
APPEND = "recipes-core/images/microduck-image-dev.bbappend"
SCHEMA = "kwipi-p15b10-dev-only-passive-selection-v1"
PACKAGE = "kwipi-passive-fixture"
LAYER_CONF = (
    'BBPATH .= ":${LAYERDIR}"\n'
    'BBFILES += "${LAYERDIR}/recipes-*/*/*.bbappend"\n'
    'BBFILE_COLLECTIONS += "kwipib10"\n'
    'BBFILE_PATTERN_kwipib10 := "^${LAYERDIR}/"\n'
    'BBFILE_PRIORITY_kwipib10 = "25"\n'
    'LAYERVERSION_kwipib10 = "1"\n'
    'LAYERDEPENDS_kwipib10 = "core microduck kwipipy kwipidev kwipipassive kwipiaccount"\n'
    'LAYERSERIES_COMPAT_kwipib10 = "wrynose"\n'
)
IMAGE_APPEND = (
    "# P15-B10: optional DEV-only selection of the already reviewed P15-B6 package.\n"
    "# Keep OEM shipping image untouched; no service, model, permission or motor access.\n"
    'IMAGE_INSTALL:append = " kwipi-passive-fixture"\n'
)


def _tokens(value: str) -> list[str]:
    return value.replace("\\n", " ").replace("\\t", " ").split()


def _real_layer(path: Path) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise EnvRefused("required layer missing or linked")
    return path.resolve(strict=True)


def source_gate(project: Path, *, selection_layer: Path,
                addon_layer: Path, python_layer: Path) -> tuple[dict, dict]:
    """Validate byte-exact selection and both existing packaged source layers."""
    if project.is_symlink() or not project.is_dir():
        raise EnvRefused("project checkout absent or linked")
    layer = _real_layer(selection_layer)
    expected = {CONF: LAYER_CONF, APPEND: IMAGE_APPEND}
    actual = {
        f.relative_to(layer).as_posix()
        for f in layer.rglob("*") if f.is_file() or f.is_symlink()
    }
    if actual != set(expected):
        raise EnvRefused("selection layer has missing/unreviewed files")
    for rel, data in expected.items():
        file = layer / rel
        if file.is_symlink() or not file.is_file() or file.read_text() != data:
            raise EnvRefused("selection layer content changed")
    base = p14b.verify(project, _real_layer(python_layer))
    addon = b6.verify(project, _real_layer(addon_layer))
    if (base.get("schema") != p14b.SCHEMA
            or base.get("selected_python_modules") != 19
            or addon.get("schema") != b6.SCHEMA
            or addon.get("addon_modules") != 5
            or addon.get("base_modules") != 19
            or addon.get("base_sha256") != base.get("source_sha256")
            or addon.get("oem_yocto_sha") != base.get("oem_yocto_sha")
            or addon.get("source_revision") != base.get("source_revision")):
        raise EnvRefused("passive add-on does not match the 19-module baseline")
    return base, addon


def validate(dev_env: str, shipping_env: str, appends: str, *,
             selection_layer: Path, addon_layer: Path, dev_layer: Path,
             python_layer: Path, account_layer: Path,
             base_provenance: dict, addon_provenance: dict) -> dict:
    """Only effective DEV selection, never an image or real OEM service claim."""
    if (addon_provenance.get("schema") != b6.SCHEMA
            or addon_provenance.get("status") != "host_addon_source_candidate_not_bitbake"
            or addon_provenance.get("addon_modules") != 5
            or addon_provenance.get("base_modules") != 19
            or addon_provenance.get("base_sha256") != base_provenance.get("source_sha256")
            or addon_provenance.get("dev_image_selected") is not False
            or addon_provenance.get("shipping_image_selected") is not False
            or addon_provenance.get("systemd_installed") is not False
            or addon_provenance.get("robot_validated") is not False):
        raise EnvRefused("P15-B6 unselected source provenance was not preserved")
    base = p14c_validate(
        dev_env, shipping_env, appends,
        dev_layer=dev_layer, py_layer=python_layer,
        provenance=base_provenance,
    )
    identity = b9_validate(
        dev_env, shipping_env, appends, account_layer=account_layer,
    )
    if (base.get("dev_image_package_count") != 1
            or base.get("shipping_image_package_count") != 0
            or identity.get("dev_identity_commands") != 3
            or identity.get("shipping_identity_commands") != 1):
        raise EnvRefused("existing DEV package or identity protections lost")

    selected_layer = _real_layer(selection_layer)
    addon = _real_layer(addon_layer)
    for env, image, count in (
        (dev_env, "microduck-image-dev", 1),
        (shipping_env, "microduck-image", 0),
    ):
        if bbvar(env, "PN") != image:
            raise EnvRefused("unexpected image target")
        installed = _tokens(bbvar(env, "IMAGE_INSTALL"))
        if installed.count(PACKAGE) != count:
            raise EnvRefused("passive package absent/duplicated/leaked to shipping")
        layers = {Path(x).resolve() for x in _tokens(bbvar(env, "BBLAYERS"))}
        if not {selected_layer, addon}.issubset(layers):
            raise EnvRefused("passive selection or source layer not in BitBake BBLAYERS")
    _require_dev_only_append(appends, selected_layer / APPEND)
    return {
        "schema": SCHEMA,
        "status": "dev_only_passive_selection_effective_metadata_verified",
        "dev_base_package_count": 1,
        "dev_passive_package_count": 1,
        "shipping_base_package_count": 0,
        "shipping_passive_package_count": 0,
        "base_modules": 19,
        "addon_modules": 5,
        "oem_packages_preserved": True,
        "kwipi_identity_dev_only_without_motor_group": True,
        "selection_layer_source_verified": True,
        "addon_source_verified": True,
        "bitbake_metadata_supplied_by_caller": True,
        "bitbake_executed_by_gate": False,
        "rootfs_built_by_gate": False,
        "package_installed_in_new_rootfs": False,
        "systemd_service_activated": False,
        "oem_socket_acl_verified": False,
        "robot_validated": False,
        "motor_commands_issued": 0,
    }



def _require_dev_only_append(appends: str, selected: Path) -> None:
    """Reject the reviewed append under ANY non-DEV recipe section.

    The reused helper verifies one exact DEV selection. This additional guard
    refuses a second occurrence under shipping or another recipe even if the
    correct DEV entry remains present.
    """
    if not show_appends_selects_file(
        appends, recipe="microduck-image-dev.bb", expected=selected
    ):
        raise EnvRefused("BitBake did not select the exact DEV-only passive append")
    expected = selected.resolve(strict=True)
    section = None
    for line in appends.splitlines():
        entry = line.strip()
        if not entry:
            continue
        if not line[0].isspace():
            section = (Path(entry[:-1]).name
                       if entry.endswith(".bb:") else None)
            continue
        if not entry.startswith("/") or not entry.endswith(".bbappend"):
            continue
        candidate = Path(entry)
        if candidate.is_file() and candidate.resolve(strict=True) == expected:
            if section != "microduck-image-dev.bb":
                raise EnvRefused("passive DEV append also selected outside DEV")



def _private_env(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise EnvRefused("effective BitBake environment missing or linked")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise EnvRefused("effective BitBake environment is not private")
    return path.read_text(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project", "selection-layer", "addon-layer", "dev-layer",
                 "python-layer", "account-layer", "dev-env",
                 "shipping-env", "appends", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.report.exists() or args.report.is_symlink():
            raise EnvRefused("report target already exists or linked")
        base, addon = source_gate(
            args.project, selection_layer=args.selection_layer,
            addon_layer=args.addon_layer, python_layer=args.python_layer,
        )
        result = validate(
            _private_env(args.dev_env), _private_env(args.shipping_env),
            args.appends.read_text(encoding="utf-8"),
            selection_layer=args.selection_layer, addon_layer=args.addon_layer,
            dev_layer=args.dev_layer, python_layer=args.python_layer,
            account_layer=args.account_layer,
            base_provenance=base, addon_provenance=addon,
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                               encoding="utf-8")
    except (EnvRefused, b6.Refused, p14b.PackageRefused,
            OSError, ValueError, KeyError, tarfile.TarError) as exc:
        parser.exit(1, "P15-B10 STOP: " + type(exc).__name__ + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
