"""PER-P13B1: verify source files really extracted by BitBake do_unpack.

The workflow must first run real BitBake do_fetch and do_unpack tasks. This
validator alone never calls a daemon, builds ARM64, flashes or installs anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

from scripts.per_p12_yocto_layer import BMI_SHA, MODEL_NAME, verify as verify_p12
from scripts.per_p13a_bitbake_env_gate import (
    EnvRefused, bbvar, validate as validate_p13a,
)

REQUIRED_MEMBERS = (
    "Cargo.toml",
    "Cargo.lock",
    "LICENSE",
    "mediad/Cargo.toml",
    "duck-detect/Cargo.toml",
    "kwipi-seg-mask-core/Cargo.toml",
)
MAX_MANIFEST_BYTES = 512_000
SCHEMA = "kwipi-p13b1-real-bitbake-unpack-gate-v1"


def _regular(root: Path, relative: str) -> Path:
    file = root / relative
    if (file.is_symlink() or not file.is_file()
            or not file.resolve(strict=True).is_relative_to(root.resolve(strict=True))):
        raise EnvRefused("unsafe/missing unpacked source: " + relative)
    return file


def _vendor_revision(vendor: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(vendor), "rev-parse", "--verify", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise EnvRefused("unpacked BMI088 git checkout cannot be verified") from exc


def validate_unpacked(*, env_text: str, layer: Path,
                      build_dir: Path) -> dict:
    """Compare BitBake's S against the authenticated P11 tar byte-for-byte."""
    layer = layer.resolve(strict=True)
    build_dir = build_dir.resolve(strict=True)
    if not layer.is_dir() or not build_dir.is_dir():
        raise EnvRefused("invalid layer/build directories")
    provenance = verify_p12(layer)
    env_proof = validate_p13a(env_text, provenance, layer=layer)
    if env_proof["bitbake_compile_run"] or not env_proof["bitbake_parse_passed"]:
        raise EnvRefused("BitBake metadata was not approved")
    s = Path(bbvar(env_text, "S"))
    unpack = Path(bbvar(env_text, "UNPACKDIR"))
    tmpdir = Path(bbvar(env_text, "TMPDIR"))
    if not all(x.is_absolute() for x in (s, unpack, tmpdir)):
        raise EnvRefused("BitBake paths must be absolute")
    if any(x.is_symlink() or not x.is_dir() for x in (s, unpack, tmpdir)):
        raise EnvRefused("BitBake source, unpack or TMPDIR missing/symlinked")
    s_real, unpack_real, tmp_real = (
        s.resolve(strict=True), unpack.resolve(strict=True), tmpdir.resolve(strict=True))
    if (not tmp_real.is_relative_to(build_dir)
            or not unpack_real.is_relative_to(tmp_real)
            or not s_real.is_relative_to(unpack_real)):
        raise EnvRefused("BitBake unpack/source path escapes scratch build")
    if bbvar(env_text, "SRCREV_bmi088") != BMI_SHA:
        raise EnvRefused("BMI088 revision differs from OEM pin")

    archive = layer / "recipes-microduck/microduck-daemon/files" / MODEL_NAME
    out: dict[str, str] = {}
    with tarfile.open(archive, "r:gz") as tar:
        for name in REQUIRED_MEMBERS:
            member = tar.getmember(name)
            if not member.isfile() or member.size > MAX_MANIFEST_BYTES:
                raise EnvRefused("unsafe/large P11 manifest: " + name)
            source = tar.extractfile(member)
            if source is None:
                raise EnvRefused("P11 source member cannot be read: " + name)
            expected = source.read()
            actual = _regular(s_real, name).read_bytes()
            if actual != expected:
                raise EnvRefused("BitBake-unpacked source differs from P11: " + name)
            out[name] = hashlib.sha256(actual).hexdigest()
    vendor = unpack_real / "bmi088-rs"
    if not vendor.is_dir() or vendor.is_symlink():
        raise EnvRefused("BMI088 unpacked directory absent/unsafe")
    if not vendor.resolve(strict=True).is_relative_to(unpack_real):
        raise EnvRefused("BMI088 unpacked directory escapes UNPACKDIR")
    revision = _vendor_revision(vendor)
    if revision != BMI_SHA:
        raise EnvRefused("unpacked BMI088 checkout has unexpected revision")
    return {
        "schema": SCHEMA,
        "status": "bitbake_unpacked_source_verified",
        "archive_sha256": provenance["archive_sha256"],
        "companion_sha": provenance["companion_sha"],
        "oem_sha": provenance["oem_sha"],
        "yocto_sha": provenance["yocto_sha"],
        "source_members_sha256": out,
        "source_members_verified": len(out),
        "registry_crates_metadata": provenance["crates_generated"],
        "vendor_bmi088_unpacked_sha": revision,
        "p13a_metadata_verified": True,
        "bitbake_compile_run": False,
        "bitbake_package_run": False,
        "rauc_built": False,
        "signed_release": False,
        "python_companion_installed": False,
        "robot_tested": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("--p12-layer", required=True, type=Path)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = validate_unpacked(
            env_text=args.env_file.read_text(encoding="utf-8"),
            layer=args.p12_layer, build_dir=args.build_dir,
        )
        if args.output.exists() or args.output.is_symlink():
            raise EnvRefused("report already exists")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8")
    except (EnvRefused, OSError, KeyError, TypeError, ValueError,
            tarfile.TarError) as exc:
        parser.exit(1, "PER-P13B1 STOP: " + str(exc) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
