"""Apply P10C only to a marked throwaway pinned OEM tree AFTER P10A/B.

The real gitlinked constructor sources, camera, robotd, memory, models,
system configuration and Cargo.lock are untouched. This file performs
exact-anchor replacements only after all checks pass; refusal is atomic.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL, replace_once
from scripts.per_p10b_apply_oem_tail_overlay import OverlayRefused, git_hash

DETECT_BLOB = "2383f297533fe775a39b6452ed528c4087f82d89"
ROOT_CARGO_BLOB = "e74d350cb81259bd531a437294927df5ce99f131"  # exact pinned tree gate; set from CI evidence
SEG_SENTINEL = "pub(crate) mod seg;"
SIGHTING_BEGIN = """    pub found: Vec<Detection>,
    /// Inference plus decode, in milliseconds — on the frame, not averaged."""
SIGHTING_END = """    pub found: Vec<Detection>,
    /// Unverified temporary 2D hypotheses, ONLY for explicitly selected SEG model.
    pub region_candidates: Option<Vec<duck_detect::seg_tail::ProjectedRegion2d>>,
    /// Inference plus decode, in milliseconds — on the frame, not averaged."""
BACKEND_BEGIN = """enum Backend {
    Npu(duck_detect::rknn::Model),
    Cpu(duck_detect::onnx::Model),
}"""
BACKEND_END = """enum Backend {
    Npu(duck_detect::rknn::Model),
    Cpu(duck_detect::onnx::Model),
    SegNpu {
        model: duck_detect::rknn::Model,
        tail: duck_detect::seg_tail::Tail,
    },
}"""
OPEN_BEGIN = """    fn open(path: &Path) -> Result<Self> {
        let rknn = path.extension().is_some_and(|ext| ext == "rknn");"""
OPEN_END = """    fn open(path: &Path) -> Result<Self> {
        if seg::is_segment_model(path) {
            let (model, tail) = seg::open(path)?;
            tracing::info!(model = %path.display(), "Kwipi SEG opt-in; OEM single detector preserved");
            return Ok(Self::SegNpu { model, tail });
        }
        let rknn = path.extension().is_some_and(|ext| ext == "rknn");"""
INPUT_BEGIN = """            Self::Npu(model) => model.input,
            Self::Cpu(model) => model.input,"""
INPUT_END = """            Self::Npu(model) => model.input,
            Self::Cpu(model) => model.input,
            Self::SegNpu { model, .. } => model.input,"""
INFER_BEGIN = """            Self::Npu(model) => model.infer(frame, out),
            Self::Cpu(model) => model.infer(frame, out),"""
INFER_END = """            Self::Npu(model) => model.infer(frame, out),
            Self::Cpu(model) => model.infer(frame, out),
            Self::SegNpu { .. } => anyhow::bail!("segmentation cannot use the OEM mono decoder"),"""
BACKEND_END_ANCHOR = """    }
}

/// Start looking, on its own thread."""
BACKEND_ADD = """    }

    fn is_segment(&self) -> bool {
        matches!(self, Self::SegNpu { .. })
    }

    /// A single branch from the EXISTING worker, not a new camera reader.
    fn infer_sighting(
        &mut self,
        frame_rgb: &[u8],
        raw: &mut Vec<f32>,
        fit: uyvy::Letterbox,
        threshold: f32,
        upright_w: u32,
        upright_h: u32,
    ) -> Result<Sighting> {
        if let Self::SegNpu { model, tail } = self {
            let heads = model.infer_segments(frame_rgb)?;
            return seg::from_heads(tail, heads, fit, upright_w, upright_h, threshold);
        }
        self.infer(frame_rgb, raw)?;
        Ok(Sighting {
            width: upright_w,
            height: upright_h,
            found: decode(raw, fit, threshold, 0.5),
            region_candidates: None,
            took_ms: 0.0,
        })
    }
}

/// Start looking, on its own thread."""
SPAWN_BEGIN = """    let mut backend = Backend::open(model)?;
    let (height, width, channels) = backend.input();"""
SPAWN_END = """    let mut backend = Backend::open(model)?;
    if backend.is_segment() {
        seg::validate_seg_hz(hz)?;
    }
    let (height, width, channels) = backend.input();"""
FRAME_BEGIN = """                let started = Instant::now();
                // One pass from the tee's 4:2:2 straight into the model's square."""
FRAME_END = """                // P10C refuses torn/invalid UYVY in SEG; OEM mono retains its exact behaviour.
                if backend.is_segment()
                    && !seg::complete_uyvy(frame.width, frame.height, frame.data.len())
                {
                    tracing::warn!("incomplete or malformed UYVY SEG frame; no observation");
                    continue;
                }

                let started = Instant::now();
                // One pass from the tee's 4:2:2 straight into the model's square."""
WORKER_BEGIN = """                match backend.infer(&square, &mut raw) {
                    Ok(()) => {
                        let found = decode(&raw, fit, threshold, 0.5);
                        looks.fetch_add(1, Ordering::Relaxed);
                        if !found.is_empty() {
                            seen.fetch_add(1, Ordering::Relaxed);
                        }
                        last_error = None;
                        // Ignored on purpose: nobody watching is the ordinary state of a robot with
                        // no console open, and it is not a reason to stop looking.
                        // Upright, because that is the space the boxes are in — a consumer
                        // scaling them against the *camera's* dimensions would have them sideways.
                        let (upright_w, upright_h) =
                            turn.upright(frame.width as usize, frame.height as usize);
                        took_ms = started.elapsed().as_secs_f64() * 1e3;
                        let _ = sightings.send(Arc::new(Sighting {
                            width: upright_w as u32,
                            height: upright_h as u32,
                            found,
                            took_ms,
                        }));
                    }
                    Err(error) => {"""
WORKER_END = """                let (upright_w, upright_h) =
                    turn.upright(frame.width as usize, frame.height as usize);
                match backend.infer_sighting(
                    &square,
                    &mut raw,
                    fit,
                    threshold,
                    upright_w as u32,
                    upright_h as u32,
                ) {
                    Ok(mut sighting) => {
                        looks.fetch_add(1, Ordering::Relaxed);
                        let has_candidates = !sighting.found.is_empty()
                            || sighting.region_candidates.as_ref().is_some_and(|r| !r.is_empty());
                        if has_candidates {
                            seen.fetch_add(1, Ordering::Relaxed);
                        }
                        last_error = None;
                        sighting.took_ms = started.elapsed().as_secs_f64() * 1e3;
                        took_ms = sighting.took_ms;
                        let _ = sightings.send(Arc::new(sighting));
                    }
                    Err(error) => {"""
NOTIFICATION_BEGIN = """pub fn notification(sighting: &Sighting) -> String {
    let boxes: Vec<String> = sighting"""
NOTIFICATION_END = """pub fn notification(sighting: &Sighting) -> String {
    if sighting.region_candidates.is_some() {
        return seg::notification(sighting);
    }
    let boxes: Vec<String> = sighting"""
FIXTURE_ONE = """            took_ms: 63.55,
        };
        let line = notification(&sighting);"""
FIXTURE_ONE_NEW = """            region_candidates: None,
            took_ms: 63.55,
        };
        let line = notification(&sighting);"""
FIXTURE_TWO = """            found: Vec::new(),
            took_ms: 60.0,
        });"""
FIXTURE_TWO_NEW = """            found: Vec::new(),
            region_candidates: None,
            took_ms: 60.0,
        });"""


def apply(archive: Path, project: Path) -> None:
    archive = archive.resolve(strict=True)
    project = project.resolve(strict=True)
    marker = archive / SENTINEL
    if (not archive.is_dir() or (archive / ".git").exists()
            or marker.is_symlink() or not marker.is_file()
            or marker.read_text(encoding="utf-8").strip() != PIN):
        raise OverlayRefused("P10C requires a marked ephemeral OEM git archive")
    path = archive / "mediad" / "src" / "detect.rs"
    target = archive / "mediad" / "src" / "detect" / "seg.rs"
    source = project / "scripts" / "per_p10c_mediad_segment.rs"
    p10b = archive / "duck-detect" / "src" / "seg_tail.rs"
    harness = archive / "p10c-harness"
    cargo = archive / "Cargo.toml"
    for p in (path, source, p10b, cargo):
        if p.is_symlink() or not p.is_file():
            raise OverlayRefused(f"missing or symlinked required source: {p.name}")
    if target.exists() or harness.exists():
        raise OverlayRefused("P10C already applied or destination exists")
    if git_hash(path) != DETECT_BLOB:
        raise OverlayRefused("mediad detector is not the pinned OEM source")
    if "pub use kwipi_seg_mask_core::oem_region" not in p10b.read_text(encoding="utf-8"):
        raise OverlayRefused("P10B public region types missing")
    original = path.read_text(encoding="utf-8")
    updates = [
        ("use crate::pipeline::Frames;\n", "use crate::pipeline::Frames;\n\n#[path = \"detect/seg.rs\"]\npub(crate) mod seg;\n"),
        (SIGHTING_BEGIN, SIGHTING_END),
        (BACKEND_BEGIN, BACKEND_END),
        (OPEN_BEGIN, OPEN_END),
        (INPUT_BEGIN, INPUT_END),
        (INFER_BEGIN, INFER_END),
        (BACKEND_END_ANCHOR, BACKEND_ADD),
        (SPAWN_BEGIN, SPAWN_END),
        (FRAME_BEGIN, FRAME_END),
        (WORKER_BEGIN, WORKER_END),
        (NOTIFICATION_BEGIN, NOTIFICATION_END),
        (FIXTURE_ONE, FIXTURE_ONE_NEW),
        (FIXTURE_TWO, FIXTURE_TWO_NEW),
    ]
    updated = original
    for before, after in updates:
        updated = replace_once(updated, before, after)
    root_src = cargo.read_text(encoding="utf-8")
    # Add ONLY a test harness member to the copy; no new daemon or service.
    changed_root = replace_once(root_src, '"uyvy", "xtask"]',
                                '"uyvy", "xtask", "p10c-harness"]')
    harness_src = project / "scripts" / "per_p10c_harness.rs"
    harness_manifest = project / "scripts" / "per_p10c_harness.toml"
    if (not harness_src.is_file() or not harness_manifest.is_file()
            or harness_src.is_symlink() or harness_manifest.is_symlink()):
        raise OverlayRefused("test harness files unavailable")
    # All anchors and source checks verified. Only the throwaway archive mutates.
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(source.read_bytes())
    path.write_text(updated, encoding="utf-8")
    cargo.write_text(changed_root, encoding="utf-8")
    harness.joinpath("src").mkdir(parents=True)
    shutil.copy2(harness_src, harness / "src" / "lib.rs")
    shutil.copy2(harness_manifest, harness / "Cargo.toml")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        apply(args.archive, args.project)
    except (OverlayRefused, ValueError, OSError) as exc:
        parser.exit(1, f"PER-P10C STOP: {exc}\n")
    print("PER-P10C assembled in temporary pinned OEM, same mediad detector thread.")
    print("No actual mediad process, NPU, robot, camera, service or SQLite changed.")


if __name__ == "__main__":
    main()
