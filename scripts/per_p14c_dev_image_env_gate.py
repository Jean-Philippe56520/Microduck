"""PER-P14C: validate dev-only BitBake package selection, not image/rootfs.

This gate checks that source layers stay pristine and kwipi-companion is never
selected in the OEM shipping image.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from scripts.per_p13a_bitbake_env_gate import EnvRefused, bbvar
from scripts.per_p14b_yocto_python_layer import (
    verify as verify_python_layer,
)

YOCTO_SHA = "1ee58387810cebb67ae0d634c351d95024483bce"
OEM_DEV_RECIPE = "meta-microduck/recipes-core/images/microduck-image-dev.bb"
OEM_SHIP_RECIPE = "meta-microduck/recipes-core/images/microduck-image.bb"
DEV_BLOB = "ec7fa8f82b7685a7da1807c2fee597f9e98e4f8d"
SHIP_BLOB = "6ee5d14f7a8ebca2441bdff525ce41705bec935e"
LAYER_CONF = "conf/layer.conf"
DEV_APPEND = "recipes-core/images/microduck-image-dev.bbappend"
SCHEMA = "kwipi-p14c-dev-only-image-select-v1"
REQUIRED_BASE = frozenset({"microduck-daemon", "microduck-data"})
UNSAFE_PROD_FEATURES = frozenset({
    "allow-empty-password", "allow-root-login", "empty-root-password",
})
EXPECTED_APPEND = (
    "# PER-P14C: only the official microduck-image-dev.bb (no recipe version suffix).\n"
    "# This layer is optional, and deliberately never matches microduck-image.bb.\n"
    "# No daemon service, model, motor privileges or production package.\n"
    'IMAGE_INSTALL:append = " kwipi-companion"\n'
)
EXPECTED_LAYER_CONF = (
    'BBPATH .= ":${LAYERDIR}"\n'
    'BBFILES += "${LAYERDIR}/recipes-*/*/*.bbappend"\n'
    'BBFILE_COLLECTIONS += "kwipidev"\n'
    'BBFILE_PATTERN_kwipidev := "^${LAYERDIR}/"\n'
    'BBFILE_PRIORITY_kwipidev = "23"\n'
    'LAYERVERSION_kwipidev = "1"\n'
    'LAYERDEPENDS_kwipidev = "core microduck kwipipy"\n'
    'LAYERSERIES_COMPAT_kwipidev = "wrynose"\n'
)


def _git(repo: Path, *arguments: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), *arguments],
                              check=True, capture_output=True,
                              text=True, timeout=12).stdout.strip()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise EnvRefused("cannot verify pinned OEM Yocto checkout") from exc


def source_gate(yocto: Path, dev_layer: Path, py_layer: Path, root: Path) -> dict:
    yocto, dev_layer, py_layer = (
        yocto.resolve(strict=True), dev_layer.resolve(strict=True),
        py_layer.resolve(strict=True))
    if _git(yocto, "rev-parse", "HEAD") != YOCTO_SHA:
        raise EnvRefused("unpinned Yocto")
    if _git(yocto, "status", "--porcelain", "--untracked-files=no"):
        raise EnvRefused("original Yocto tracked files changed")
    for rel, blob in ((OEM_DEV_RECIPE, DEV_BLOB),
                      (OEM_SHIP_RECIPE, SHIP_BLOB)):
        if _git(yocto, "hash-object", "--", rel) != blob:
            raise EnvRefused("original Yocto image recipe changed: " + rel)
    found = {
        path.relative_to(dev_layer).as_posix()
        for path in dev_layer.rglob("*") if path.is_file() or path.is_symlink()
    }
    if found != {LAYER_CONF, DEV_APPEND}:
        raise EnvRefused("unreviewed/missing dev layer member")
    for rel, expected in ((LAYER_CONF, EXPECTED_LAYER_CONF),
                          (DEV_APPEND, EXPECTED_APPEND)):
        file = dev_layer / rel
        if file.is_symlink() or not file.is_file() or file.read_text() != expected:
            raise EnvRefused("dev layer content differed: " + rel)
    py = verify_python_layer(root, py_layer)
    if (py["selected_python_modules"] != 19
            or py["license_recipe_closed"] is not True
            or py["source_license_checked"] is not False):
        raise EnvRefused("Python candidate was promoted without source review")
    return py


def _tokens(value: str) -> list[str]:
    return value.replace("\\n", " ").replace("\\t", " ").split()


def validate(dev_env: str, shipping_env: str, appends: str, *,
             dev_layer: Path, py_layer: Path, provenance: dict) -> dict:
    if (provenance.get("selected_python_modules") != 19
            or provenance.get("license_recipe_closed") is not True):
        raise EnvRefused("source-reviewed Python layer absent")
    for text, expected_pn in ((dev_env, "microduck-image-dev"),
                              (shipping_env, "microduck-image")):
        if bbvar(text, "PN") != expected_pn:
            raise EnvRefused("incorrect image recipe selected")
        installed = _tokens(bbvar(text, "IMAGE_INSTALL"))
        if not REQUIRED_BASE.issubset(set(installed)):
            raise EnvRefused("original OEM daemon/data packages missing")
        required_count = 1 if expected_pn.endswith("-dev") else 0
        if installed.count("kwipi-companion") != required_count:
            raise EnvRefused("Kwipi package not selected exclusively in dev image")
        layers = {Path(s).resolve() for s in _tokens(bbvar(text, "BBLAYERS"))}
        if dev_layer.resolve() not in layers or py_layer.resolve() not in layers:
            raise EnvRefused("required opt-in layer absent from BitBake")
        if expected_pn == "microduck-image" and (
                set(_tokens(bbvar(text, "IMAGE_FEATURES"))) & UNSAFE_PROD_FEATURES):
            raise EnvRefused("development root-login features leaked to product")
    if (DEV_APPEND not in appends or "microduck-image-dev.bb" not in appends):
        raise EnvRefused("BitBake does not acknowledge exact dev-image bbappend")
    return {
        "schema": SCHEMA,
        "status": "real_bitbake_dev_only_image_selection_verified",
        "selected_python_modules": 19,
        "dev_image_package_count": 1,
        "shipping_image_package_count": 0,
        "oem_daemon_preserved": True,
        "oem_data_package_preserved": True,
        "original_image_recipes_unchanged": True,
        "packaged_in_rootfs": False,
        "service_installed": False,
        "production_shipping_approved": False,
        "robot_validated": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("dev-env", "shipping-env", "appends", "dev-layer",
                "py-layer", "yocto", "root", "report"):
        p.add_argument("--" + key, type=Path, required=True)
    args = p.parse_args()
    try:
        py = source_gate(args.yocto, args.dev_layer, args.py_layer, args.root)
        result = validate(
            args.dev_env.read_text(encoding="utf-8"),
            args.shipping_env.read_text(encoding="utf-8"),
            args.appends.read_text(encoding="utf-8"),
            dev_layer=args.dev_layer, py_layer=args.py_layer,
            provenance=py)
        if args.report.exists() or args.report.is_symlink():
            raise EnvRefused("report exists")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    except (EnvRefused, OSError, KeyError, ValueError) as exc:
        p.exit(1, "PER-P14C STOP: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
