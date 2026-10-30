"""PER-P13A: fail-closed verification of real BitBake -e environment.

This does not build a package, install a service, or issue robot commands.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from scripts.per_p12_yocto_layer import (
    BMI_URI, DAEMON_URI, OEM_FILES, SCHEMA as P12_SCHEMA, verify as verify_p12,
)


class EnvRefused(ValueError):
    pass


def bbvar(text: str, name: str) -> str:
    found = re.findall(r"^" + re.escape(name) + r'="(.*)"$', text, re.M)
    if len(found) != 1:
        raise EnvRefused(f"effective BitBake variable missing/duplicate: {name}")
    return found[0]


def validate(env: str, p12: dict, *, layer: Path) -> dict:
    if (p12.get("schema") != P12_SCHEMA
            or p12.get("source_only") is not True
            or p12.get("bitbake_parsed") is not False
            or p12.get("robot_validated") is not False):
        raise EnvRefused("candidate was promoted without a real build")
    uri = bbvar(env, "SRC_URI")
    parts = uri.split()
    tar_uri = "file://kwipi-v1-oem-source.tar.gz"
    if sum(x.startswith(tar_uri + ";") for x in parts) != 1:
        raise EnvRefused("BitBake source tar is not uniquely selected")
    tar_entry = next(x for x in parts if x.startswith(tar_uri + ";"))
    if ";name=kwipisrc" not in tar_entry or ";subdir=" not in tar_entry:
        raise EnvRefused("BitBake source tar missing subdir or named checksum")
    if any(DAEMON_URI in x or "microduck_daemon.git" in x for x in parts):
        raise EnvRefused("original OEM daemon Git URI still fetched")
    if parts.count(BMI_URI) != 1:
        raise EnvRefused("pinned BMI088 source missing/duplicated")
    for name in OEM_FILES:
        if parts.count("file://" + name) != 1:
            raise EnvRefused(f"OEM-local resource missing/duplicated: {name}")
    crates = sorted(x for x in parts if x.startswith("crate://crates.io/"))
    if len(crates) != p12.get("crates_generated") or len(set(crates)) != len(crates):
        raise EnvRefused("effective BitBake crate list differs from P11 Cargo.lock")
    if not crates:
        raise EnvRefused("zero crates in effective BitBake SRC_URI")
    version = bbvar(env, "PV")
    if version != "0.17.8+kwipi.p12." + p12["companion_sha"][:12]:
        raise EnvRefused("unrelated OEM release version or false identity")
    if bbvar(env, "MICRODUCK_DAEMON_SRCREV") != p12["companion_sha"]:
        raise EnvRefused("source revision does not identify Companion code")
    if bbvar(env, "SRCREV_FORMAT") != "bmi088":
        raise EnvRefused("remaining vendor Git revision format differs")
    source_dir = bbvar(env, "S")
    unpack = bbvar(env, "UNPACKDIR")
    bp = bbvar(env, "BP")
    if source_dir.rstrip("/") != (unpack.rstrip("/") + "/" + bp):
        raise EnvRefused("BitBake S does not reference the chosen tar subdirectory")
    if layer.resolve().as_posix() not in bbvar(env, "BBLAYERS").split():
        raise EnvRefused("companion layer absent from BitBake layer resolution")
    return {
        "status": "real_bitbake_metadata_parsed_only",
        "archive_sha256": p12["archive_sha256"],
        "companion_sha": p12["companion_sha"],
        "effective_crates": len(crates),
        "vendor_bmi088_kept": True,
        "original_daemon_git_removed": True,
        "oem_resources_kept": True,
        "package_version": version,
        "bitbake_parse_passed": True,
        "bitbake_compile_run": False,
        "rauc_built": False,
        "signed_release": False,
        "physical_robot_verified": False,
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--env-file", type=Path, required=True)
    cli.add_argument("--p12-layer", type=Path, required=True)
    cli.add_argument("--output", type=Path, required=True)
    args = cli.parse_args()
    try:
        layer = args.p12_layer.resolve(strict=True)
        p12 = verify_p12(layer)
        data = args.env_file.read_text(encoding="utf-8")
        report = validate(data, p12, layer=layer)
        if args.output.exists():
            raise EnvRefused("output already exists")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    except (EnvRefused, ValueError, OSError, KeyError) as error:
        cli.exit(1, f"PER-P13A STOP: {error}\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
