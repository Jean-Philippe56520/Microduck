"""Apply P10B ONLY to a previously prepared, isolated P10A OEM archive."""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil
from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL, OverlayRefused, replace_once

def apply(archive: Path, segment_source: Path, core_source: Path) -> None:
    archive = archive.resolve(strict=True)
    if (archive / ".git").exists() or (archive / SENTINEL).read_text().strip() != PIN:
        raise OverlayRefused("not a pinned temporary OEM archive")
    old = archive / "duck-detect" / "src" / "rknn" / "segments.rs"
    cargo = archive / "duck-detect" / "Cargo.toml"
    tail = archive / "duck-detect" / "src" / "seg_tail.rs"
    lib = archive / "duck-detect" / "src" / "lib.rs"
    if not old.is_file() or not cargo.is_file() or tail.exists():
        raise OverlayRefused("P10A overlay missing or P10B already applied")
    if not segment_source.is_file() or not core_source.is_dir() or (core_source / ".git").exists():
        raise OverlayRefused("missing local audited source")
    if (archive / "kwipi-seg-mask-core").exists():
        raise OverlayRefused("seg core already present")
    # Prepare and validate all text transformations before writing anything.
    manifest = replace_once(cargo.read_text(), '[dependencies]\n', '[dependencies]\nkwipi-seg-mask-core = { path = "../kwipi-seg-mask-core" }\n')
    contents = replace_once(lib.read_text(), 'pub mod rknn;', 'pub mod rknn;\npub mod seg_tail;')
    shutil.copytree(core_source, archive / "kwipi-seg-mask-core", ignore=shutil.ignore_patterns("target", "__pycache__"))
    tail.write_bytes(segment_source.read_bytes())
    cargo.write_text(manifest)
    lib.write_text(contents)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--core", required=True, type=Path)
    parser.add_argument("--extension", type=Path, default=Path("scripts/per_p10b_oem_ort_tail.rs"))
    a = parser.parse_args()
    try:
        apply(a.archive, a.extension, a.core)
    except (OverlayRefused, OSError, ValueError) as e:
        parser.exit(1, f"PER-P10B refused: {e}\n")
    print("P10B assembled on temporary OEM archive only")
