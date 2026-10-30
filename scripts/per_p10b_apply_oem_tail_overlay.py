"""Apply PER-P10B ONLY after PER-P10A inside a marked throwaway OEM archive.

No modification of upstream/ gitlinks, robot drivers, models, mediad or
the parent Cargo.lock. The local P7/P9 crate is copied without changes.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL, replace_once

OEM_LIB_BLOB = "74ce1267322876e8394e736d3b13988ad358ea61"
OEM_CARGO_BLOB = "466ad903d61a73358b3ecf3a5fc3808dde363a8"
CORE_BLOBS = {
    "Cargo.toml": "3df8a77677a6218aad8c6419210de21c6adf151c",
    "src/lib.rs": "f2aa38c8f9784b02073fbb1227eaf8cc53c2ac90",
    "src/oem_region.rs": "1d6a1f9f2714c3dda4e0f2dba3436542fbc54030",
}
OEM_LIB_ANCHOR = "pub mod onnx;\npub mod rknn;\n"
OEM_CARGO_ANCHOR = '[dependencies]\nanyhow = "1"\n'


class OverlayRefused(ValueError):
    pass


def git_hash(path: Path) -> str:
    return subprocess.run(["git", "hash-object", "--", str(path)],
                          check=True, capture_output=True, text=True).stdout.strip()


def apply(archive: Path, source: Path, project: Path) -> None:
    archive = archive.resolve(strict=True)
    source = source.resolve(strict=True)
    project = project.resolve(strict=True)

    if (not archive.is_dir() or (archive / ".git").exists()
            or not (archive / SENTINEL).is_file()
            or (archive / SENTINEL).is_symlink()
            or (archive / SENTINEL).read_text(encoding="utf-8").strip() != PIN):
        raise OverlayRefused("not a marked and pinned throwaway OEM archive")

    oem_src = archive / "duck-detect" / "src"
    oem_cargo = archive / "duck-detect" / "Cargo.toml"
    oem_lib = oem_src / "lib.rs"
    p10a_rust = oem_src / "rknn" / "segments.rs"
    p10a_ref = project / "scripts" / "per_p10a_rknn_segments.rs"
    p10b_dst = oem_src / "seg_tail.rs"
    core_src = project / "rust" / "kwipi-seg-mask-core"
    core_dst = archive / "kwipi-seg-mask-core"

    if any(p.is_symlink() for p in [oem_src, oem_cargo, oem_lib, p10a_rust,
                                      p10b_dst, core_src, core_dst, source]):
        raise OverlayRefused("symlink in source or destination")
    if (p10b_dst.exists() or core_dst.exists() or not p10a_rust.is_file()
            or not p10a_ref.is_file() or not oem_lib.is_file()
            or not oem_cargo.is_file() or not source.is_file()):
        raise OverlayRefused("missing P10A extension or P10B is already present")

    # P10A's owned extension must be byte-identical, not a guessed compatible API.
    if p10a_rust.read_bytes() != p10a_ref.read_bytes():
        raise OverlayRefused("P10A wrapper differs from the audited branch")
    if git_hash(oem_lib) != OEM_LIB_BLOB or git_hash(oem_cargo) != OEM_CARGO_BLOB:
        raise OverlayRefused("OEM lib or Cargo source differs from pinned revision")
    for rel, expected in CORE_BLOBS.items():
        p = core_src / rel
        if p.is_symlink() or not p.is_file() or git_hash(p) != expected:
            raise OverlayRefused("P7/P9 local core differs from the tested revision")

    updated_lib = replace_once(
        oem_lib.read_text(encoding="utf-8"), OEM_LIB_ANCHOR,
        OEM_LIB_ANCHOR + "pub mod seg_tail;\n"
    )
    updated_cargo = replace_once(
        oem_cargo.read_text(encoding="utf-8"), OEM_CARGO_ANCHOR,
        OEM_CARGO_ANCHOR + 'kwipi-seg-mask-core = { path = "../kwipi-seg-mask-core" }\n'
    )

    # All integrity checks and anchors pass BEFORE any mutation of the archive.
    core_dst.mkdir(parents=True)
    (core_dst / "src").mkdir()
    for rel in CORE_BLOBS:
        shutil.copy2(core_src / rel, core_dst / rel)
    p10b_dst.write_bytes(source.read_bytes())
    oem_lib.write_text(updated_lib, encoding="utf-8")
    oem_cargo.write_text(updated_cargo, encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--source", type=Path, default=Path(__file__).with_name(
        "per_p10b_seg_tail.rs"))
    p.add_argument("--project", type=Path, default=Path(__file__).resolve().parent.parent)
    args = p.parse_args()
    try:
        apply(args.archive, args.source, args.project)
    except (OSError, OverlayRefused, subprocess.CalledProcessError) as exc:
        p.exit(1, f"PER-P10B STOP: {exc}\n")
    print("PER-P10B: P10A + ORT tail + P7/P9 assembled in temporary pinned OEM archive.")
    print("No modification of upstream/, no model, camera, daemon or robot.")


if __name__ == "__main__":
    main()
