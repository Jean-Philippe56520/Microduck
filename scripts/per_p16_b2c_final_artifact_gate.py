"""P16-B2c: read-only integrity gate for a private Yocto DEV image release.

Validates staging and DEPLOY_DIR_IMAGE with exact release stems, checksums,
well-formed bmap ranges and physical archive equivalence; no BitBake or writes.
Does not establish bootability, secondary GPT validity, licenses or RAUC trust.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import xml.etree.ElementTree as ET
from pathlib import Path

IMAGE_STEM = "microduck-image-dev-microduck-zero3.rootfs-20261031195334"
ALIAS_STEM = "microduck-image-dev-microduck-zero3.rootfs"
RAW_BYTES = 12968805376
RAW_SHA256 = "c1140e7508559ebc9467c3f97d3c9891452228f05b3baf999ccaa3c0a5f11bc8"
SUFFIXES = (".wic", ".wic.bmap", ".wic.zst", ".wic.zst.sha256sum")


class AuditStop(Exception):
    pass


def fail(message: str) -> None:
    raise AuditStop(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect(directory: Path, stem: str, alias: str) -> dict[str, Path]:
    if not directory.is_dir() or directory.is_symlink():
        fail("missing or symlinked release directory: " + str(directory))
    expected = {stem + s for s in SUFFIXES} | {alias + s for s in SUFFIXES}
    actual = {p.name for p in directory.glob("microduck-image-dev-microduck-zero3.rootfs*.wic*")}
    if actual != expected:
        fail("unexpected release entries: missing=" + repr(sorted(expected - actual))
             + " extra=" + repr(sorted(actual - expected)))
    originals = {}
    for suffix in SUFFIXES:
        physical = directory / (stem + suffix)
        link = directory / (alias + suffix)
        if not physical.is_file() or physical.is_symlink():
            fail("not a regular physical artifact: " + physical.name)
        if not link.is_symlink():
            fail("missing symlink alias: " + link.name)
        try:
            resolved = link.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise AuditStop("broken or cyclic alias: " + link.name) from exc
        if resolved != physical.resolve() or resolved.parent != directory.resolve():
            fail("wrong symlink target: " + link.name)
        if stat.S_IMODE(physical.stat().st_mode) & 0o002:
            fail("world writable release artifact: " + physical.name)
        if physical.stat().st_size < 1:
            fail("empty artifact: " + physical.name)
        originals[suffix] = physical
    return originals


def validate_bmap(path: Path, image_bytes: int) -> dict[str, int]:
    if path.stat().st_size > 1024 * 1024:
        fail("bmap XML unexpectedly large")
    try:
        root = ET.fromstring(path.read_bytes())
        if root.tag != "bmap":
            fail("unexpected bmap XML root")
        def num(name: str) -> int:
            val = root.findtext(name)
            if val is None:
                fail("missing bmap field: " + name)
            return int(val.strip())
        size, block, count, mapped = map(num, ("ImageSize", "BlockSize", "BlocksCount", "MappedBlocksCount"))
        if size != image_bytes:
            fail("bmap image size differs from WIC")
        if block < 512 or block > 1024 * 1024 or block & (block - 1):
            fail("bmap block size invalid")
        if count != (size + block - 1) // block or not 0 < mapped <= count:
            fail("bmap block counts invalid")
        spans = root.findall("./BlockMap/Range")
        if not spans:
            fail("bmap lacks mapped ranges")
        last = -1
        total = 0
        for r in spans:
            val = (r.text or "").strip()
            if not re.fullmatch(r"\d+(?:-\d+)?", val):
                fail("bmap invalid range")
            lo, hi = (int(t) for t in val.split("-")) if "-" in val else (int(val), int(val))
            if lo <= last or hi < lo or hi >= count:
                fail("bmap overlapping or out-of-range blocks")
            total += hi - lo + 1
            last = hi
        if total != mapped:
            fail("bmap mapped ranges disagree with MappedBlocksCount")
        return {"block_size": block, "mapped_blocks": mapped, "block_count": count}
    except (ET.ParseError, ValueError) as exc:
        raise AuditStop("unparseable bmap XML") from exc


def audit(base: Path, *, stem: str = IMAGE_STEM, expected_bytes: int = RAW_BYTES,
          expected_sha256: str = RAW_SHA256) -> dict:
    base = base.resolve(strict=True)
    roots = [p for p in (base / "build/tmp/work").glob("*/microduck-image-dev/*/rootfs")
             if p.is_dir() and not p.is_symlink()]
    if len(roots) != 1:
        fail("expected exactly one existing DEV rootfs")
    stage_dir = roots[0].parent / "deploy-microduck-image-dev-image-complete"
    final_dir = base / "build/tmp/deploy/images/microduck-zero3"
    stage = collect(stage_dir, stem, ALIAS_STEM)
    final = collect(final_dir, stem, ALIAS_STEM)
    if any(stage[s].stat().st_size != final[s].stat().st_size for s in SUFFIXES):
        fail("stage/final artifact size differs")
    if final[".wic"].stat().st_size != expected_bytes:
        fail("raw WIC size mismatch")
    if final[".wic.zst"].stat().st_size >= expected_bytes:
        fail("compressed WIC size unexpected")
    for s in (".wic.bmap", ".wic.zst.sha256sum"):
        if stage[s].read_bytes() != final[s].read_bytes():
            fail("stage/final metadata content differs: " + s)
    line = final[".wic.zst.sha256sum"].read_text(encoding="ascii")
    match = re.fullmatch(r"([0-9a-fA-F]{64}) [ *]([^\r\n]+)\r?\n?", line)
    if not match or match.group(2) != stem + ".wic.zst":
        fail("unexpected compressed checksum filename or format")
    expected_zst = match.group(1).lower()
    final_zst = sha256(final[".wic.zst"])
    if final_zst != expected_zst:
        fail("final ZST SHA-256 mismatch")
    if not stage[".wic.zst"].samefile(final[".wic.zst"]):
        if sha256(stage[".wic.zst"]) != expected_zst:
            fail("staged ZST SHA-256 mismatch")
    bmap = validate_bmap(final[".wic.bmap"], expected_bytes)
    raw_hash = sha256(final[".wic"])
    if raw_hash != expected_sha256:
        fail("deployed raw WIC differs from previously verified digest")
    return {
        "status": "p16_b2c_final_dev_artifacts_integrity_pass",
        "physical_files": 4,
        "symlinks": 4,
        "raw_wic_bytes": expected_bytes,
        "raw_wic_sha256": raw_hash,
        "compressed_wic_bytes": final[".wic.zst"].stat().st_size,
        "compressed_wic_sha256": final_zst,
        "bmap": bmap,
        "stage_final_metadata_equal": True,
        "stage_final_zst_sha256_equal": True,
        "robot_boot_verified": False,
        "rauc_bundle_signed_or_verified": False,
        "secondary_gpt_verified": False,
        "zst_decompressed_equivalent_to_wic_verified": False,
        "distribution_license_approved": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path.cwd())
    a = parser.parse_args()
    try:
        result = audit(a.base)
    except (AuditStop, OSError, ValueError, UnicodeError) as exc:
        parser.exit(1, "P16_B2C_STOP: " + str(exc) + "\n")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
