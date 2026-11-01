"""P15-B6-M: audit REAL BitBake metadata and do_unpack result, never a package proof.

Synthetic inputs are valid for negative/unit tests only. A passing report from
GitHub requires a preceding *real* pinned kas/BitBake step to create the files.
No do_install, do_package, do_rootfs, RAUC or OEM access is attempted here.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from scripts.per_p13a_bitbake_env_gate import EnvRefused, bbvar
from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6

SCHEMA = "kwipi-p15b6-real-bitbake-metadata-unpack-v1"
PASS = "bitbake_metadata_and_unpack_verified_only"
REQUIRED_RECIPE = (
    "PN", "PV", "LICENSE", "PACKAGE_ARCH", "SRC_URI", "S", "BP", "UNPACKDIR",
    "TMPDIR", "PYTHON_SITEPACKAGES_DIR", "BBLAYERS",
)


def _tokens(value: str) -> set[str]:
    return set(value.replace("\\n", " ").replace("\\t", " ").split())


def validate_metadata(recipe: str, dev: str, shipping: str, *,
                      base_layer: Path, addon_layer: Path, dev_layer: Path,
                      digest: str, checksum: str) -> dict[str, str]:
    values = {key: bbvar(recipe, key) for key in REQUIRED_RECIPE}
    if values["PN"] != b6.PN or values["PV"] != b6.PV:
        raise EnvRefused("wrong resolved P15-B6 recipe identity")
    if values["LICENSE"] != "CLOSED" or values["PACKAGE_ARCH"] != "all":
        raise EnvRefused("license or allarch contract changed")
    uri = f"file://{b6.SRC_NAME};subdir={values['BP']};name=p15b6"
    if _tokens(values["SRC_URI"]) != {uri}:
        raise EnvRefused("extra, missing or retargeted P15-B6 source")
    if checksum != digest:
        raise EnvRefused("effective archive SHA does not match staged source")
    expected_py = "/usr/lib/python3.14/site-packages"
    if values["PYTHON_SITEPACKAGES_DIR"] != expected_py:
        raise EnvRefused("unexpected pinned OE Python target directory")
    layers = {Path(part).resolve() for part in _tokens(values["BBLAYERS"])}
    if not {base_layer.resolve(), addon_layer.resolve(), dev_layer.resolve()} <= layers:
        raise EnvRefused("one of the reviewed opt-in layers is absent")
    if "kwipi-companion" not in _tokens(bbvar(recipe, f"RDEPENDS:{b6.PN}")):
        raise EnvRefused("missing reviewed P14B runtime dependency")
    if values["BP"] != f"{b6.PN}-{b6.PV}":
        raise EnvRefused("unexpected BitBake base package directory")
    if Path(values["S"]) != Path(values["UNPACKDIR"]) / values["BP"]:
        raise EnvRefused("unpacked source directory not pinned to UNPACKDIR/BP")

    if bbvar(dev, "PN") != "microduck-image-dev":
        raise EnvRefused("DEV image metadata is not the official DEV recipe")
    if bbvar(shipping, "PN") != "microduck-image":
        raise EnvRefused("shipping image metadata is not the official release recipe")
    dev_pkgs = _tokens(bbvar(dev, "IMAGE_INSTALL"))
    shipping_pkgs = _tokens(bbvar(shipping, "IMAGE_INSTALL"))
    if "kwipi-companion" not in dev_pkgs:
        raise EnvRefused("P14C DEV baseline unexpectedly absent")
    if b6.PN in dev_pkgs or b6.PN in shipping_pkgs:
        raise EnvRefused("passive add-on was selected in an image")
    if "kwipi-companion" in shipping_pkgs:
        raise EnvRefused("P14C companion was unexpectedly selected for shipping")
    return values


def validate_unpack(root: Path, base_layer: Path, addon_layer: Path,
                    dev_layer: Path, recipe: str, dev: str, shipping: str,
                    checksum: str) -> dict:
    root = root.resolve(strict=True)
    base_layer = base_layer.resolve(strict=True)
    addon_layer = addon_layer.resolve(strict=True)
    dev_layer = dev_layer.resolve(strict=True)
    source_base = p14b.verify(root, base_layer)
    source_addon = b6.verify(root, addon_layer)
    if source_base["selected_python_modules"] != 19:
        raise EnvRefused("P14B source contract was changed")
    if (source_addon["base_sha256"] != {
            path: sha256((root / path).read_bytes()).hexdigest()
            for path in p14b.p14a.SELECTED
        } or source_addon["addon_modules"] != 5):
        raise EnvRefused("19+5 source contract was changed")
    values = validate_metadata(
        recipe, dev, shipping,
        base_layer=base_layer, addon_layer=addon_layer, dev_layer=dev_layer,
        digest=source_addon["archive_sha256"], checksum=checksum)
    unpack = Path(values["UNPACKDIR"])
    source = Path(values["S"])
    tmpdir = Path(values["TMPDIR"])
    if (not unpack.is_absolute() or not source.is_absolute()
            or not tmpdir.is_absolute()
            or any(p.is_symlink() for p in (unpack, source, tmpdir))
            or not source.is_dir() or not unpack.is_dir() or not tmpdir.is_dir()
            or not unpack.resolve().is_relative_to(tmpdir.resolve())
            or not source.resolve().is_relative_to(unpack.resolve())):
        raise EnvRefused("real unpack directory is missing, linked or outside TMPDIR")
    package = source / "microduck_companion"
    if package.is_symlink() or not package.is_dir():
        raise EnvRefused("unpacked Python package directory absent/linked")
    expected = {Path(p).name: p for p in b6.ADDON}
    if len(expected) != 5:
        raise EnvRefused("five reviewed source names required")
    actual = list(source.rglob("*"))
    if (set(actual) != {package} | {package / name for name in expected}
            or any(p.is_symlink() for p in actual)):
        raise EnvRefused("unpacked source contains a missing, extra or linked file")
    for name, rel in sorted(expected.items()):
        file = package / name
        if not file.is_file() or sha256(file.read_bytes()).hexdigest() != source_addon["addon_sha256"][rel]:
            raise EnvRefused("unpacked source bytes do not match reviewed archive: " + name)

    return {
        "schema": SCHEMA,
        "status": PASS,
        "source_revision": source_addon["source_revision"],
        "yocto_source_sha": p14b.YOCTO_SHA,
        "base_python_modules_unchanged": 19,
        "addon_python_modules_unpacked": 5,
        "addon_archive_sha256": source_addon["archive_sha256"],
        "unpacked_sha256": {p: source_addon["addon_sha256"][p] for p in sorted(b6.ADDON)},
        "effective_python_sitepackages": values["PYTHON_SITEPACKAGES_DIR"],
        "addon_rdepends_base": True,
        "dev_image_selects_addon": False,
        "shipping_image_selects_addon": False,
        "unpacked_source_bytes_verified": True,
        "bitbake_task_execution_attested_by_this_script": False,
        "bitbake_do_install_run": False,
        "bitbake_do_package_run": False,
        "rootfs_installed": False,
        "service_installed": False,
        "real_oem_observation": False,
        "signed_release": False,
        "physical_robot_verified": False,
        "motor_commands_issued": 0,
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    for arg in ("root", "base-layer", "addon-layer", "dev-layer",
                "recipe-env", "dev-env", "shipping-env", "checksum-value-file", "output"):
        cli.add_argument("--" + arg, type=Path, required=True)
    args = cli.parse_args()
    try:
        result = validate_unpack(
            args.root, args.base_layer, args.addon_layer, args.dev_layer,
            args.recipe_env.read_text(encoding="utf-8"),
            args.dev_env.read_text(encoding="utf-8"),
            args.shipping_env.read_text(encoding="utf-8"),
            args.checksum_value_file.read_text(encoding="utf-8").strip())
        if args.output.exists() or args.output.is_symlink():
            raise EnvRefused("proof report already exists")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                               encoding="utf-8")
    except (EnvRefused, b6.Refused, p14b.PackageRefused, ValueError, OSError, KeyError) as error:
        cli.exit(1, "P15-B6-M STOP: " + type(error).__name__ + ": " + str(error) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
