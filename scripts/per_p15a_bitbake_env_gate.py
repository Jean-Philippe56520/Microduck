"""PER-P15A-M: pinned BitBake metadata gate for manual DEV-only health probe.

A successful report proves only recipe resolution and image package selection.
No do_package, do_rootfs, systemd start, RAUC, motor operation, or robot is tested.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.per_p13a_bitbake_env_gate import EnvRefused, bbvar
from scripts.per_p14c_dev_image_env_gate import source_gate as p14c_source_gate
from scripts.per_p14c_dev_image_env_gate import validate as p14c_validate

SCHEMA = "kwipi-p15a-real-bitbake-metadata-only-v1"
RECIPE = "recipes-kwipi/kwipi-readonly-probe/kwipi-readonly-probe_0.1.bb"
DEV_APPEND = "recipes-core/images/microduck-image-dev.bbappend"
# Git blob IDs for the five reviewed, exact P15A files at PR #235.
# Deliberate revisions require auditing the patch and updating these pins.
REVIEWED_BLOBS = {
    "conf/layer.conf": "379e397de7e65c1b588ed1ddb67bcacec394094b",
    DEV_APPEND: "4684f4ff7035926eac976fef2a345ee99bb05569",
    RECIPE: "a5460d66e8e7c7dfeeb191ae04c6de6f768cf72f",
    "recipes-kwipi/kwipi-readonly-probe/files/health_probe.py":
        "5d6ba04fe96d3366d3d41369195550d1a6f706da",
    "recipes-kwipi/kwipi-readonly-probe/files/kwipi-readonly-probe.service":
        "270795c047fe592e74246bade39189c65314f203",
}
EXPECTED_RDEPENDS = {"kwipi-companion", "python3-core", "python3-json"}
REQUIRED_OEM = {"microduck-daemon", "microduck-data"}


def _tokens(value: str) -> list[str]:
    return value.replace("\\n", " ").replace("\\t", " ").split()


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\x00" + data).hexdigest()


def verify_source(layer: Path) -> dict:
    if layer.is_symlink() or not layer.is_dir():
        raise EnvRefused("P15A source layer missing or symbolic link")
    layer = layer.resolve(strict=True)
    actual = {
        entry.relative_to(layer).as_posix()
        for entry in layer.rglob("*")
        if entry.is_file() or entry.is_symlink()
    }
    if actual != set(REVIEWED_BLOBS):
        raise EnvRefused("P15A layer contains missing or unexpected files")
    for rel, expected in REVIEWED_BLOBS.items():
        file = layer / rel
        if file.is_symlink() or not file.is_file() or _git_blob(file.read_bytes()) != expected:
            raise EnvRefused("P15A reviewed source bytes changed: " + rel)
    return {
        "reviewed_files": len(REVIEWED_BLOBS),
        "reviewed_source_unchanged": True,
    }


def validate(recipe_env: str, dev_env: str, shipping_env: str, appends: str, *,
             p15_layer: Path, dev_layer: Path, py_layer: Path,
             provenance: dict) -> dict:
    """Compare actual -e output with independent pinned source and P14C gate."""
    source = verify_source(p15_layer)
    parent = p14c_validate(
        dev_env, shipping_env, appends, dev_layer=dev_layer,
        py_layer=py_layer, provenance=provenance,
    )
    if parent["status"] != "real_bitbake_dev_only_image_selection_verified":
        raise EnvRefused("parent P14C image selection is unverified")
    p15_layer = p15_layer.resolve(strict=True)
    if bbvar(recipe_env, "PN") != "kwipi-readonly-probe" or bbvar(recipe_env, "PV") != "0.1":
        raise EnvRefused("unexpected P15A package identity")
    if bbvar(recipe_env, "LICENSE") != "CLOSED":
        raise EnvRefused("P15A source license must not be promoted silently")
    if Path(bbvar(recipe_env, "FILE")).resolve() != (p15_layer / RECIPE).resolve():
        raise EnvRefused("P15A recipe came from a different layer")
    if bbvar(recipe_env, "S").rstrip("/") != bbvar(recipe_env, "UNPACKDIR").rstrip("/"):
        raise EnvRefused("unexpected P15A source/unpack directory")
    if _tokens(bbvar(recipe_env, "SRC_URI")) != [
            "file://health_probe.py", "file://kwipi-readonly-probe.service"]:
        raise EnvRefused("unreviewed P15A source was selected")
    if bbvar(recipe_env, "SYSTEMD_SERVICE:kwipi-readonly-probe") != "kwipi-readonly-probe.service":
        raise EnvRefused("P15A is not the reviewed systemd unit")
    if bbvar(recipe_env, "SYSTEMD_AUTO_ENABLE:kwipi-readonly-probe") != "disable":
        raise EnvRefused("P15A could start automatically")
    if "kwipi-readonly-probe" not in _tokens(bbvar(recipe_env, "SYSTEMD_PACKAGES")):
        raise EnvRefused("systemd package class did not select P15A")
    if not EXPECTED_RDEPENDS.issubset(set(
            _tokens(bbvar(recipe_env, "RDEPENDS:kwipi-readonly-probe")))):
        raise EnvRefused("Python or reviewed P14B dependency missing")
    for text, image in ((dev_env, "microduck-image-dev"),
                        (shipping_env, "microduck-image")):
        if bbvar(text, "PN") != image:
            raise EnvRefused("unexpected OEM image recipe")
        tokens = _tokens(bbvar(text, "IMAGE_INSTALL"))
        layer_tokens = {Path(token).resolve() for token in
                        _tokens(bbvar(text, "BBLAYERS"))}
        if p15_layer not in layer_tokens:
            raise EnvRefused("P15A layer not selected by real BitBake")
        if not REQUIRED_OEM.issubset(set(tokens)):
            raise EnvRefused("original OEM packages removed")
        expected = 1 if image.endswith("-dev") else 0
        if tokens.count("kwipi-readonly-probe") != expected:
            raise EnvRefused("P15A must be selected only once and only in dev")
        if tokens.count("kwipi-companion") != expected:
            raise EnvRefused("P14B must remain dev-only")
    if str((p15_layer / DEV_APPEND).resolve()) not in appends:
        raise EnvRefused("P15A exact dev-image bbappend not recognized by BitBake")
    return {
        "schema": SCHEMA,
        "status": "real_bitbake_p15a_metadata_dev_only_verified",
        **source,
        "parent_p14c_verified": True,
        "python_modules_from_p14b": 19,
        "p15a_dev_count": 1,
        "p15a_shipping_count": 0,
        "systemd_auto_enable": "disable",
        "motor_commands_issued": 0,
        "bitbake_package_run": False,
        "rootfs_built": False,
        "service_installed": False,
        "signed_release": False,
        "robot_validated": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("recipe-env", "dev-env", "shipping-env", "appends",
                 "p15-layer", "dev-layer", "py-layer", "yocto", "root", "report"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    try:
        verified_sources = verify_source(args.p15_layer)
        if not verified_sources["reviewed_source_unchanged"]:
            raise EnvRefused("source gate failed")
        provenance = p14c_source_gate(args.yocto, args.dev_layer,
                                     args.py_layer, args.root)
        result = validate(
            args.recipe_env.read_text(encoding="utf-8"),
            args.dev_env.read_text(encoding="utf-8"),
            args.shipping_env.read_text(encoding="utf-8"),
            args.appends.read_text(encoding="utf-8"),
            p15_layer=args.p15_layer, dev_layer=args.dev_layer,
            py_layer=args.py_layer, provenance=provenance,
        )
        if args.report.exists() or args.report.is_symlink():
            raise EnvRefused("refusing to overwrite P15A proof report")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    except (EnvRefused, OSError, ValueError, KeyError) as error:
        parser.exit(1, "PER-P15A-M STOP: " + str(error) + "\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
