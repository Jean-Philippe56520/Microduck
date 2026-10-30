"""PER-P10A: exact-anchor overlay on a THROWAWAY ARCHIVE of pinned OEM sources.

The real upstream/microduck submodule MUST NOT be changed, and the script
refuses an OEM checkout, a changed source blob, absent anchors or reapplication.
No SDK/runtime/robot/device is ever invoked by this source-only operation.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

PIN = "942e58e3aa6dbb28e7037203fff11866122c7567"
RKN_SOURCE_BLOB = "6260c49f0df9a048d42dca229e53467c77f8139c"
SENTINEL = ".per-p10a-throwaway-pin"

# Every anchor MUST match exactly once. Source is the pinned OEM duck-detect,
# not the upstream main branch, whose changes must be reviewed separately.
REWRITES = (
    (
        "use anyhow::{Context, Result, anyhow, bail};\n",
        "use anyhow::{Context, Result, anyhow, bail};\n\n"
        "// Companion PER-P10A overlay on a temporary pinned OEM source tree.\n"
        "mod segments;\n",
    ),
    (
        "    pub output_len: usize,\n    pub api_version: String,",
        "    pub output_len: usize,\n"
        "    // None for the unchanged OEM one-output detection mode.\n"
        "    segment_output_lens: Option<[usize; 10]>,\n"
        "    pub api_version: String,",
    ),
    (
        "    pub fn open(path: &Path) -> Result<Self> {\n"
        "        let bytes =",
        "    pub fn open(path: &Path) -> Result<Self> {\n"
        "        Self::open_variant(path, false)\n"
        "    }\n\n"
        "    // Reuse the SAME vendor dlopen/context with the optional 10-head mode.\n"
        "    fn open_variant(path: &Path, segmentation: bool) -> Result<Self> {\n"
        "        let bytes =",
    ),
    (
        '            if counts.n_input != 1 || counts.n_output != 1 {\n'
        '                destroy(context);\n'
        '                bail!(\n'
        '                    "expected one input and one output, got {} and {} — this decoder only knows \\\n'
        '                     the single-tensor YOLO head",\n'
        '                    counts.n_input,\n'
        '                    counts.n_output\n'
        '                );\n'
        '            }',
        "            if let Err(error) = segments::verify_counts(\n"
        "                counts.n_input, counts.n_output, segmentation,\n"
        "            ) {\n"
        "                destroy(context);\n"
        "                return Err(error);\n"
        "            }",
    ),
    (
        "            let input = attr(RKNN_QUERY_INPUT_ATTR, 0)?;\n"
        "            let output = attr(RKNN_QUERY_OUTPUT_ATTR, 0)?;",
        "            let input = match attr(RKNN_QUERY_INPUT_ATTR, 0) {\n"
        "                Ok(a) => a,\n"
        "                Err(error) => { destroy(context); return Err(error); }\n"
        "            };\n"
        "            if input.n_dims as usize > RKNN_MAX_DIMS {\n"
        '                destroy(context);\n'
        '                bail!("RKNN input dimension count exceeds ABI");\n'
        '            }\n'
        "            let segment_output_lens = if segmentation {\n"
        "                let mut attrs = Vec::with_capacity(10);\n"
        "                for index in 0..10 {\n"
        "                    match attr(RKNN_QUERY_OUTPUT_ATTR, index) {\n"
        "                        Ok(a) => attrs.push(a),\n"
        "                        Err(error) => { destroy(context); return Err(error); }\n"
        "                    }\n"
        "                }\n"
        "                match segments::verify_attrs(&attrs) {\n"
        "                    Ok(lens) => Some(lens),\n"
        "                    Err(error) => { destroy(context); return Err(error); }\n"
        "                }\n"
        "            } else {\n"
        "                None\n"
        "            };\n"
        "            let output_len = if segmentation { 0 } else {\n"
        "                match attr(RKNN_QUERY_OUTPUT_ATTR, 0) {\n"
        "                    Ok(a) => a.n_elems as usize,\n"
        "                    Err(error) => { destroy(context); return Err(error); }\n"
        "                }\n"
        "            };",
    ),
    (
        "            Ok(Self {\n                context,",
        '            if segmentation && shape != (640, 640, 3) {\n'
        '                destroy(context);\n'
        '                bail!("YOLO26n-seg expects 640x640x3 input, got {shape:?}");\n'
        '            }\n\n'
        "            Ok(Self {\n                context,",
    ),
    (
        "                output_len: output.n_elems as usize,\n                api_version:",
        "                output_len,\n                segment_output_lens,\n                api_version:",
    ),
    (
        "    pub fn infer(&mut self, frame: &[u8], out: &mut Vec<f32>) -> Result<()> {\n"
        "        let (height, width, channels) = self.input;",
        "    pub fn infer(&mut self, frame: &[u8], out: &mut Vec<f32>) -> Result<()> {\n"
        "        if self.segment_output_lens.is_some() {\n"
        '            bail!("OEM one-output infer is unavailable for a ten-output segment model");\n'
        "        }\n"
        "        let (height, width, channels) = self.input;",
    ),
)


class OverlayRefused(ValueError):
    """Stop rather than editing the wrong OEM source, gitlink or model."""


def replace_once(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise OverlayRefused("pinned OEM anchor mismatch or already patched")
    return source.replace(before, after, 1)


def apply(archive: Path, extension: Path) -> tuple[Path, Path]:
    archive = archive.resolve(strict=True)
    marker = archive / SENTINEL
    # An unpacked git archive has no .git anywhere at its root. A normal
    # upstream checkout or the real gitlinked source is forbidden.
    if (not archive.is_dir() or (archive / ".git").exists()
            or not marker.is_file() or marker.is_symlink()
            or marker.read_text(encoding="utf-8").strip() != PIN):
        raise OverlayRefused("not an explicitly marked throwaway OEM archive")
    target = archive / "duck-detect" / "src" / "rknn.rs"
    dest = archive / "duck-detect" / "src" / "rknn" / "segments.rs"
    if target.is_symlink() or not target.is_file() or dest.exists():
        raise OverlayRefused("OEM source missing/unsafe or overlay already exists")
    if extension.is_symlink() or not extension.is_file():
        raise OverlayRefused("extension source missing/unsafe")
    blob = subprocess.run(
        ["git", "hash-object", "--", str(target)],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    if blob != RKN_SOURCE_BLOB:
        raise OverlayRefused("OEM rknn.rs blob is not the audited pin")
    original = target.read_text(encoding="utf-8")
    updated = original
    for before, after in REWRITES:
        updated = replace_once(updated, before, after)
    # Atomic preparation: do not alter rknn.rs until EVERY anchor passed.
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(extension.read_bytes())
    target.write_text(updated, encoding="utf-8")
    return target, dest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--extension", type=Path, default=Path(__file__).with_name(
        "per_p10a_rknn_segments.rs"))
    args = parser.parse_args()
    try:
        source, dest = apply(args.archive, args.extension)
    except (OSError, OverlayRefused, subprocess.CalledProcessError) as error:
        parser.exit(1, f"PER-P10A STOP: {error}\n")
    print(f"PER-P10A exact pin overlay prepared: {source.relative_to(args.archive.resolve())}")
    print(f"PER-P10A Rust extension: {dest.relative_to(args.archive.resolve())}")
    print("Source-only CI fixture: no NPU, model, camera, robot or gitlink modified.")


if __name__ == "__main__":
    main()
