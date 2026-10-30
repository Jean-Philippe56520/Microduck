"""PER-P10D: read-only audit of pinned OEM Yocto source contract.

Does NOT run BitBake, install packages, bundle models, rebase a submodule,
or claim that Companion's overlay is included in the OEM image.
The result must remain BLOCKED until the complete V1 release is verified.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

YOCTO_SHA = "1ee58387810cebb67ae0d634c351d95024483bce"
OEM_SHA = "942e58e3aa6dbb28e7037203fff11866122c7567"
YOCTO_PATHS = {
    "daemon": (
        "meta-microduck/recipes-microduck/microduck-daemon/microduck-daemon.bb",
        "f6aa890d3e6f417020cad3a31c8dbd9a31619e58",
    ),
    "onnx": (
        "meta-microduck/recipes-microduck/onnxruntime/onnxruntime_1.28.0.bb",
        "c700cd00e01b38c698be91714352bc73b9c304e4",
    ),
    "kas": (
        "kas/microduck.yml",
        "2c638f0b6346a6b318634d61553399238c5c1460",
    ),
}
OEM_PARAMS_PATH = "robotd-params/src/lib.rs"
OEM_PARAMS_BLOB = "71007de3095e488d81e7880a39fa753e49c15ff1"
ONNX_ARM64_SHA256 = "e15ff8b5d85afe6c144d97c6fd432254bf76a219daaf17658087d6ecb3e8f0bb"
BLOCKED = "source_contract_verified_deployment_blocked"


class ContractRefused(ValueError):
    """A contract is missing, modified, contradicted or not pinned."""


def ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ContractRefused(message)


def contains_unique(source: str, needle: str, context: str) -> None:
    ensure(source.count(needle) == 1, f"{context}: absent or duplicated literal")


def _git(repo: Path, *parts: str) -> str:
    p = subprocess.run(
        ["git", "-C", str(repo), *parts],
        check=True, capture_output=True, text=True,
    )
    return p.stdout.strip()


def read_pinned_sources(yocto: Path, oem: Path) -> dict[str, str]:
    yocto = yocto.resolve(strict=True)
    oem = oem.resolve(strict=True)
    ensure(yocto.is_dir() and oem.is_dir(), "source directory missing")
    ensure(_git(yocto, "rev-parse", "HEAD") == YOCTO_SHA, "Yocto git revision mismatch")
    ensure(_git(oem, "rev-parse", "HEAD") == OEM_SHA, "OEM git revision mismatch")
    data: dict[str, str] = {}
    for name, (relative, expected_blob) in YOCTO_PATHS.items():
        p = yocto / relative
        ensure(p.is_file() and not p.is_symlink(), f"{name}: missing/symlink file")
        ensure(_git(yocto, "hash-object", "--", relative) == expected_blob,
               f"{name}: pinned Yocto file blob mismatch")
        data[name] = p.read_text(encoding="utf-8")
    params = oem / OEM_PARAMS_PATH
    ensure(params.is_file() and not params.is_symlink(), "OEM parameters unavailable")
    ensure(_git(oem, "hash-object", "--", OEM_PARAMS_PATH) == OEM_PARAMS_BLOB,
           "pinned OEM detector defaults mismatch")
    data["params"] = params.read_text(encoding="utf-8")
    return data


def validate_contract(docs: dict[str, str]) -> dict[str, object]:
    ensure(set(docs) == {"daemon", "onnx", "kas", "params"},
           "source bundle incomplete/extra")
    daemon, onnx, kas, params = (
        docs["daemon"], docs["onnx"], docs["kas"], docs["params"]
    )
    for needle in (
        'MICRODUCK_DAEMON_VERSION ??= ""',
        'MICRODUCK_DAEMON_SRCREV ??= ""',
        'SRCREV_daemon = "${MICRODUCK_DAEMON_SRCREV}"',
        'git://git@github.com/pollen-robotics/microduck_daemon.git',
        'inherit cargo cargo-update-recipe-crates pkgconfig systemd useradd',
        'DEPENDS += "glib-2.0 gstreamer1.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-bad"',
        'CARGO_BUILD_FLAGS += "--workspace --exclude xtask --exclude test-support --exclude duckctl --exclude duck-ether"',
        'RRECOMMENDS:${PN}:append:aarch64 = " onnxruntime"',
        'RDEPENDS:${PN} += "gstreamer1.0-plugins-rs gstreamer1.0-rockchip"',
    ):
        contains_unique(daemon, needle, "daemon recipe")
    ensure('RDEPENDS:${PN}:append:aarch64 = " onnxruntime"' not in daemon,
           "do not mistake hard-dependence for the current recommendation")
    ensure('SRCREV_daemon = "${AUTOREV}"' not in daemon,
           "unreproducible AUTOREV is forbidden")
    ensure("per_p10a" not in daemon and "per_p10b" not in daemon and "per_p10c" not in daemon
           and "kwipi_seg" not in daemon,
           "OEM recipe unexpectedly includes Kwipi overlay/model")
    for needle in (
        'LICENSE = "MIT"',
        'SRC_URI = "https://github.com/microsoft/onnxruntime/releases/download/v${PV}/onnxruntime-linux-aarch64-${PV}.tgz"',
        f'SRC_URI[sha256sum] = "{ONNX_ARM64_SHA256}"',
        'COMPATIBLE_HOST = "aarch64.*-linux"',
        'ln -sf libonnxruntime.so.1 ${D}${libdir}/libonnxruntime.so',
    ):
        contains_unique(onnx, needle, "ONNX Runtime recipe")
    for needle in (
        "machine: microduck-zero3",
        "target: microduck-image-dev",
        "MICRODUCK_DAEMON_VERSION: null",
        "MICRODUCK_DAEMON_SRCREV: null",
    ):
        contains_unique(kas, needle, "kas build config")
    match = re.search(
        r"impl Default for DuckDetectorParams\s*\{\s*fn default\(\) -> Self\s*\{\s*"
        r"Self\s*\{\s*enabled:\s*(false|true)\s*,",
        params, flags=re.S,
    )
    ensure(match is not None and match.group(1) == "false",
           "pinned OEM detector no longer disabled by default")
    ensure('return vec![path.clone()];' in params,
           "explicit OEM detection model no longer selected exclusively")
    ensure('pub const DETECTOR_FILES: [&str; 2] = ["duck_detect.rknn", "duck_detect.onnx"];' in params,
           "unknown default detector names")
    return {
        "status": BLOCKED,
        "yocto_sha": YOCTO_SHA,
        "oem_sha": OEM_SHA,
        "full_mediad_package": "OEM_release_only_not_Companion_overlay",
        "mediad_gstreamer": "recipe_declares_required_native_dependencies",
        "onnxruntime": "ARM64_recipe_exists_but_RRECOMMENDS_not_guaranteed",
        "npu_rknn": "runtime_setup_not_proven_on_target",
        "segmentation_model": "absent_no_license_approval",
        "source_revision": "release_commit_selected_outside_Companion",
        "physical_robot_validated": False,
        "yocto_image_built": False,
        "kwipi_detection_enabled_by_default": False,
        "motor_commands_issued": 0,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--yocto", type=Path, required=True,
                   help="checked-out pinned official Yocto repository")
    p.add_argument("--oem", type=Path, required=True,
                   help="checked-out pinned OEM gitlinked repository")
    args = p.parse_args()
    try:
        report = validate_contract(read_pinned_sources(args.yocto, args.oem))
    except (ContractRefused, OSError, subprocess.CalledProcessError) as error:
        p.exit(1, f"PER-P10D STOP: {error}\n")
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
