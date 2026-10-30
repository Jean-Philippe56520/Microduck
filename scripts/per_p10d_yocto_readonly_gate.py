"""PER-P10D read-only audit of the exact OEM Yocto source contract.

No BitBake, signed release, model installation or hardware validation.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

PIN = "1ee58387810cebb67ae0d634c351d95024483bce"
BLOBS = {
    "meta-microduck/recipes-microduck/microduck-daemon/microduck-daemon.bb":
        "f6aa890d3e6f417020cad3a31c8dbd9a31619e58",
    "meta-microduck/recipes-microduck/onnxruntime/onnxruntime_1.28.0.bb":
        "c700cd00e01b38c698be91714352bc73b9c304e4",
    "kas/microduck.yml": "2c638f0b6346a6b318634d61553399238c5c1460",
}


class YoctoGateRefused(ValueError):
    """Unpinned, changed or unsupported source."""


def _require(text: str, needle: str, reason: str) -> None:
    if needle not in text:
        raise YoctoGateRefused(reason)


def audit_texts(recipe: str, ort: str, kas: str) -> dict[str, object]:
    """Assert build/release boundaries, not actual installation success."""
    for var in ("MICRODUCK_DAEMON_SRCREV", "MICRODUCK_DAEMON_VERSION"):
        _require(recipe, f'd.getVar("{var}")', "missing release guard: " + var)
        _require(kas, f"{var}: null", "missing kas source variable: " + var)
    _require(recipe, 'SRCREV_daemon = "${MICRODUCK_DAEMON_SRCREV}"',
             "daemon source no longer selected by pinned release")
    _require(recipe, "git://git@github.com/pollen-robotics/microduck_daemon.git",
             "OEM daemon source URI changed")
    _require(recipe, 'CARGO_BUILD_FLAGS += "--workspace', "full workspace build missing")
    for exclude in ("--exclude xtask", "--exclude test-support",
                    "--exclude duckctl", "--exclude duck-ether"):
        _require(recipe, exclude, "expected OEM exclusion missing: " + exclude)
    if "--exclude mediad" in recipe:
        raise YoctoGateRefused("mediad excluded from the OEM image")
    _require(recipe, 'DEPENDS += "glib-2.0 gstreamer1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-bad"',
             "GStreamer build dependency changed")
    _require(recipe, 'RDEPENDS:${PN} += "gstreamer1.0-plugins-rs gstreamer1.0-rockchip"',
             "GStreamer runtime package requirement changed")
    _require(recipe, 'RRECOMMENDS:${PN}:append:aarch64 = " onnxruntime"',
             "ORT is no longer a recommended optional dependency")
    _require(recipe, "mediad.service", "mediad service is no longer packaged")
    _require(recipe, "/opt/robot/daemon/releases/${PV}/bin",
             "OEM release binary layout changed")
    _require(ort, 'COMPATIBLE_HOST = "aarch64.*-linux"', "ORT host constraint changed")
    _require(ort, 'SRC_URI[sha256sum] = "e15ff8b5d85afe6c144d97c6fd432254bf76a219daaf17658087d6ecb3e8f0bb"',
             "ARM64 ORT source checksum changed")
    _require(ort, 'SRC_URI = "https://github.com/microsoft/onnxruntime/releases/download/v${PV}/onnxruntime-linux-aarch64-${PV}.tgz"',
             "ORT release archive changed")
    _require(ort, "libonnxruntime.so.${PV}", "ORT shared library layout changed")
    _require(kas, "target: microduck-image-dev", "default image target changed")
    if any(x in recipe for x in (
            "per_p10a_", "per_p10b_", "per_p10c_",
            "kwipi_seg.rknn", "kwipi_seg_tail.onnx")):
        raise YoctoGateRefused("unapproved Companion overlay/model in OEM recipe")
    return {
        "source_contract": "pinned_yocto_read_only",
        "daemon_source": "official_release_not_companion_overlays",
        "mediad_gstreamer_build_and_runtime": "declared_by_oem_recipe",
        "ort_aarch64": "recipe_present_but_only_rrecommended",
        "companion_overlays_in_recipe": False,
        "model_weights_in_recipe": False,
        "bitbake_run": False,
        "yocto_image_created": False,
        "status": "source_contract_ok_deployment_blocked",
    }


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def audit_checkout(root: Path) -> dict[str, object]:
    if root.is_symlink():
        raise YoctoGateRefused("checkout must not be a symlink")
    root = root.resolve(strict=True)
    if not root.is_dir() or not (root / ".git").exists():
        raise YoctoGateRefused("a real Git checkout is required")
    revision = _git(root, "rev-parse", "HEAD")
    if revision != PIN:
        raise YoctoGateRefused(f"wrong OEM Yocto revision: {revision}")
    contents = {}
    for name, expected in BLOBS.items():
        p = root / name
        if not p.is_file() or p.is_symlink():
            raise YoctoGateRefused(f"missing/symlinked recipe: {name}")
        found = _git(root, "hash-object", "--", name)
        if found != expected:
            raise YoctoGateRefused(f"unexpected recipe bytes: {name}: {found}")
        contents[name] = p.read_text(encoding="utf-8")
    result = audit_texts(*[contents[name] for name in BLOBS])
    result["yocto_pin"] = revision
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--yocto-root", type=Path, required=True)
    args = p.parse_args()
    try:
        print(json.dumps(audit_checkout(args.yocto_root), sort_keys=True))
    except (YoctoGateRefused, OSError, subprocess.SubprocessError) as error:
        p.exit(1, f"PER-P10D STOP: {error}\n")


if __name__ == "__main__":
    main()
