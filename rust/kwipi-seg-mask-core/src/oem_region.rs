//! Bounded, read-only geometry projection from P7 masks into OEM upright image space.
//!
//! This is NOT an authenticated mediad observation. It does not infer identity,
//! depth, physical presence or collision clearance, nor does it grant motor
//! permission. The caller supplies the letterbox computed by the pinned OEM
//! uyvy::letterbox_from_uyvy and the dimensions AFTER Turn::upright.
//! No camera, model, ONNX runtime, NPU, filesystem or SQLite is accessed.

use crate::{IMAGE_SIDE, MASK_PIXELS, MASK_SIDE, MAX_MASKS_PER_FRAME, MaskCandidate};

pub const MAX_UPRIGHT_SIDE: u32 = 4096;

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct UprightFrame {
    pub width: u32,
    pub height: u32,
    /// Exactly the scale returned by OEM uyvy::letterbox_from_uyvy(…, 640, …).
    pub scale: f32,
    pub pad_x: f32,
    pub pad_y: f32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RegionError {
    InvalidFrame,
    InvalidLetterbox,
    TooManyCandidates,
    InvalidCandidate,
    InvalidMask,
    MaskOutsideCandidateBox,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ProjectedRegion2d {
    /// Unverified COCO numeric proposal, NOT an object's identity or real presence.
    pub proposed_class_id: u8,
    /// Uncalibrated model output, NOT a measurement of real-world certainty.
    pub score: f32,
    /// Approximate mask footprint on the OEM upright image, [x0, y0, x1, y1].
    /// This is NOT an obstacle distance or permission to move.
    pub box_upright_xyxy: [f32; 4],
    /// Area-weighted centre of visible mask cells, image coordinates.
    pub centroid_upright_xy: [f32; 2],
    /// Number of nonzero cells in the original 160x160 mask.
    pub source_mask_cells: usize,
    /// Number of cells with nonzero overlap with the actual OEM image.
    pub visible_mask_cells: usize,
}

struct ValidatedFrame {
    scale: f32,
    px: f32,
    py: f32,
    x1: f32,
    y1: f32,
    w: f32,
    h: f32,
}

fn validate_frame(frame: UprightFrame) -> Result<ValidatedFrame, RegionError> {
    if frame.width == 0
        || frame.height == 0
        || frame.width > MAX_UPRIGHT_SIDE
        || frame.height > MAX_UPRIGHT_SIDE
    {
        return Err(RegionError::InvalidFrame);
    }
    if !frame.scale.is_finite()
        || !frame.pad_x.is_finite()
        || !frame.pad_y.is_finite()
        || frame.scale <= 0.0
    {
        return Err(RegionError::InvalidLetterbox);
    }
    let w = frame.width as f32;
    let h = frame.height as f32;
    // Validate against the pinned OEM's actual round-to-nearest + integer-pad
    // geometry. This is not a second pixel sampler or a different resize.
    let expected = (IMAGE_SIDE as f32 / w).min(IMAGE_SIDE as f32 / h);
    let fitted_w = ((w * expected).round() as usize)
        .max(1)
        .min(IMAGE_SIDE);
    let fitted_h = ((h * expected).round() as usize)
        .max(1)
        .min(IMAGE_SIDE);
    let expected_px = ((IMAGE_SIDE - fitted_w) / 2) as f32;
    let expected_py = ((IMAGE_SIDE - fitted_h) / 2) as f32;
    if (frame.scale - expected).abs() > 1e-5
        || frame.pad_x != expected_px
        || frame.pad_y != expected_py
    {
        return Err(RegionError::InvalidLetterbox);
    }
    Ok(ValidatedFrame {
        scale: frame.scale,
        px: frame.pad_x,
        py: frame.pad_y,
        x1: frame.pad_x + fitted_w as f32,
        y1: frame.pad_y + fitted_h as f32,
        w,
        h,
    })
}

fn valid_candidate(candidate: &MaskCandidate) -> bool {
    let b = candidate.box_model_xyxy;
    candidate.proposed_class_id < 80
        && candidate.score.is_finite()
        && (0.0..=1.0).contains(&candidate.score)
        && b.iter().all(|v| v.is_finite())
        && b[0] < b[2]
        && b[1] < b[3]
        && candidate.mask_160.len() == MASK_PIXELS
        && candidate.foreground_pixels <= MASK_PIXELS
}

/// Project *existing* temporary masks. P7 does the inference-independent
/// segmentation; this only maps its results to the OEM's upright coordinates.
///
/// 1 cell represents a 4x4 patch of model pixels. At odd letterbox padding
/// boundaries, partially overlapping cells remain visible; their intersection
/// area weights the centroid. The enclosing box is clipped to the real frame.
/// Never promote a padding-only or empty mask to a region. Bad candidate
/// metadata fails the whole frame rather than publishing partial observations.
/// No source authentication, category confirmation, tracking or memory writes.
pub fn project_to_upright(
    candidates: &[MaskCandidate],
    frame: UprightFrame,
) -> Result<Vec<ProjectedRegion2d>, RegionError> {
    let g = validate_frame(frame)?;
    if candidates.len() > MAX_MASKS_PER_FRAME {
        return Err(RegionError::TooManyCandidates);
    }
    let mut regions = Vec::with_capacity(candidates.len());
    let factor = IMAGE_SIDE as f32 / MASK_SIDE as f32;

    for candidate in candidates {
        if !valid_candidate(candidate) {
            return Err(RegionError::InvalidCandidate);
        }
        let bounds = candidate.box_model_xyxy;
        let mut observed = 0usize;
        let mut visible = 0usize;
        let mut x0 = g.w;
        let mut y0 = g.h;
        let mut x1 = 0.0f32;
        let mut y1 = 0.0f32;
        let mut area = 0.0f64;
        let mut cx = 0.0f64;
        let mut cy = 0.0f64;

        for (index, &pixel) in candidate.mask_160.iter().enumerate() {
            if pixel > 1 {
                return Err(RegionError::InvalidMask);
            }
            if pixel == 0 {
                continue;
            }
            observed += 1;
            let mx = index % MASK_SIDE;
            let my = index / MASK_SIDE;

            // P7 thresholds its prototype at this cell's integer location,
            // then crops according to the vendor's non-upsampled convention.
            if (mx as f32) < bounds[0] / factor
                || (mx as f32) >= bounds[2] / factor
                || (my as f32) < bounds[1] / factor
                || (my as f32) >= bounds[3] / factor
            {
                return Err(RegionError::MaskOutsideCandidateBox);
            }

            let sx0 = ((mx as f32) * factor).max(g.px);
            let sy0 = ((my as f32) * factor).max(g.py);
            let sx1 = (((mx + 1) as f32) * factor).min(g.x1);
            let sy1 = (((my + 1) as f32) * factor).min(g.y1);
            if sx1 <= sx0 || sy1 <= sy0 {
                continue;
            }

            visible += 1;
            let left = ((sx0 - g.px) / g.scale).clamp(0.0, g.w);
            let top = ((sy0 - g.py) / g.scale).clamp(0.0, g.h);
            let right = ((sx1 - g.px) / g.scale).clamp(0.0, g.w);
            let bottom = ((sy1 - g.py) / g.scale).clamp(0.0, g.h);
            x0 = x0.min(left);
            y0 = y0.min(top);
            x1 = x1.max(right);
            y1 = y1.max(bottom);

            // Area-weighted over the true image/letterbox intersection.
            let weight = f64::from((sx1 - sx0) * (sy1 - sy0));
            area += weight;
            cx += f64::from((left + right) * 0.5) * weight;
            cy += f64::from((top + bottom) * 0.5) * weight;
        }
        if observed != candidate.foreground_pixels {
            return Err(RegionError::InvalidMask);
        }
        if visible == 0 {
            continue; // padding, out-of-frame, or nonpositive mask logits
        }
        if area <= 0.0 {
            return Err(RegionError::InvalidMask);
        }
        regions.push(ProjectedRegion2d {
            proposed_class_id: candidate.proposed_class_id,
            score: candidate.score,
            box_upright_xyxy: [x0, y0, x1, y1],
            centroid_upright_xy: [(cx / area) as f32, (cy / area) as f32],
            source_mask_cells: observed,
            visible_mask_cells: visible,
        });
    }

    Ok(regions)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{OUTPUT0_LEN, OUTPUT1_LEN, ROW_WIDTH, decode};

    fn portrait() -> UprightFrame {
        UprightFrame {
            width: 720,
            height: 1280,
            scale: 0.5,
            pad_x: 140.0,
            pad_y: 0.0,
        }
    }

    fn from_core(bbox: [f32; 4]) -> MaskCandidate {
        let mut rows = vec![0.0; OUTPUT0_LEN];
        let mut proto = vec![0.0; OUTPUT1_LEN];
        rows[..4].copy_from_slice(&bbox);
        rows[4] = 0.9;
        rows[5] = 32.0;
        rows[6] = 1.0;
        proto[..MASK_PIXELS].fill(1.0);
        decode(&rows, &proto, 0.25, 1).unwrap().remove(0)
    }

    #[test]
    fn p7_mask_maps_to_oem_upright_image_not_model_pixels() {
        let c = from_core([240.0, 80.0, 280.0, 120.0]);
        assert_eq!(c.foreground_pixels, 100);
        let regions = project_to_upright(&[c], portrait()).unwrap();
        assert_eq!(regions.len(), 1);
        assert_eq!(regions[0].box_upright_xyxy, [200.0, 160.0, 280.0, 240.0]);
        assert_eq!(regions[0].centroid_upright_xy, [240.0, 200.0]);
        assert_eq!(regions[0].visible_mask_cells, 100);
        assert_eq!(regions[0].source_mask_cells, 100);
        assert_eq!(regions[0].proposed_class_id, 32);
    }

    #[test]
    fn out_of_model_frame_box_is_clipped_by_oem_padding_without_false_region() {
        let c = from_core([-40.0, 80.0, 200.0, 240.0]);
        assert_eq!(c.foreground_pixels, 2000);
        let regions = project_to_upright(&[c], portrait()).unwrap();
        assert_eq!(regions.len(), 1);
        assert_eq!(regions[0].visible_mask_cells, 600);
        assert_eq!(regions[0].source_mask_cells, 2000);
        assert_eq!(regions[0].box_upright_xyxy, [0.0, 160.0, 120.0, 480.0]);
        assert_eq!(regions[0].centroid_upright_xy, [60.0, 320.0]);
    }

    #[test]
    fn no_foreground_or_padding_only_never_becomes_an_object() {
        let empty = from_core([700.0, 700.0, 800.0, 800.0]);
        assert_eq!(empty.foreground_pixels, 0);
        let padding = from_core([0.0, 80.0, 120.0, 240.0]);
        assert_eq!(padding.foreground_pixels, 1200);
        assert!(project_to_upright(&[empty, padding], portrait()).unwrap().is_empty());
    }

    #[test]
    fn rejects_inconsistent_geometry_and_oversize_frames() {
        let frame = portrait();
        assert_eq!(
            project_to_upright(&[], UprightFrame { scale: 0.51, ..frame }),
            Err(RegionError::InvalidLetterbox)
        );
        assert_eq!(
            project_to_upright(&[], UprightFrame { pad_x: 141.0, ..frame }),
            Err(RegionError::InvalidLetterbox)
        );
        assert_eq!(
            project_to_upright(&[], UprightFrame { scale: f32::NAN, ..frame }),
            Err(RegionError::InvalidLetterbox)
        );
        assert_eq!(
            project_to_upright(&[], UprightFrame { width: 4097, ..frame }),
            Err(RegionError::InvalidFrame)
        );
        assert_eq!(
            project_to_upright(&[], UprightFrame { height: 0, ..frame }),
            Err(RegionError::InvalidFrame)
        );
    }

    #[test]
    fn rejects_bad_masks_counts_and_candidate_metadata_without_partial_publish() {
        let mut c = from_core([240.0, 80.0, 280.0, 120.0]);
        assert_eq!(
            project_to_upright(&[c.clone(); 11], portrait()),
            Err(RegionError::TooManyCandidates)
        );
        c.mask_160.pop();
        assert_eq!(
            project_to_upright(&[c.clone()], portrait()),
            Err(RegionError::InvalidCandidate)
        );

        let mut c = from_core([240.0, 80.0, 280.0, 120.0]);
        c.mask_160[20 * MASK_SIDE + 60] = 2;
        assert_eq!(
            project_to_upright(&[c], portrait()),
            Err(RegionError::InvalidMask)
        );
        let mut c = from_core([240.0, 80.0, 280.0, 120.0]);
        c.foreground_pixels = 99;
        assert_eq!(
            project_to_upright(&[c], portrait()),
            Err(RegionError::InvalidMask)
        );
        let mut c = from_core([240.0, 80.0, 280.0, 120.0]);
        c.mask_160[10 * MASK_SIDE + 10] = 1;
        c.foreground_pixels += 1;
        assert_eq!(
            project_to_upright(&[c], portrait()),
            Err(RegionError::MaskOutsideCandidateBox)
        );
        let mut c = from_core([240.0, 80.0, 280.0, 120.0]);
        c.score = f32::INFINITY;
        assert_eq!(
            project_to_upright(&[c], portrait()),
            Err(RegionError::InvalidCandidate)
        );
        let mut c = from_core([240.0, 80.0, 280.0, 120.0]);
        c.proposed_class_id = 80;
        assert_eq!(
            project_to_upright(&[c], portrait()),
            Err(RegionError::InvalidCandidate)
        );
        let mut c = from_core([240.0, 80.0, 280.0, 120.0]);
        c.box_model_xyxy[0] = f32::NAN;
        assert_eq!(
            project_to_upright(&[c], portrait()),
            Err(RegionError::InvalidCandidate)
        );
        let mut c = from_core([240.0, 80.0, 280.0, 120.0]);
        c.box_model_xyxy[0] = 400.0;
        assert_eq!(
            project_to_upright(&[c], portrait()),
            Err(RegionError::InvalidCandidate)
        );
    }

    #[test]
    fn keeps_end2end_source_row_order_without_invented_tracking() {
        let a = from_core([240.0, 80.0, 280.0, 120.0]);
        let mut b = from_core([320.0, 80.0, 360.0, 120.0]);
        b.proposed_class_id = 3;
        let regions = project_to_upright(&[a, b], portrait()).unwrap();
        assert_eq!(regions.len(), 2);
        assert_eq!(regions[0].proposed_class_id, 32);
        assert_eq!(regions[1].proposed_class_id, 3);
        assert!(regions[0].box_upright_xyxy[0] < regions[1].box_upright_xyxy[0]);
    }

    #[test]
    fn odd_oem_letterbox_padding_keeps_partial_cells_but_no_outside_coordinates() {
        let frame = UprightFrame {
            width: 721,
            height: 1280,
            scale: 0.5,
            pad_x: 139.0,
            pad_y: 0.0,
        };
        let c = from_core([136.0, 80.0, 144.0, 120.0]);
        let regions = project_to_upright(&[c], frame).unwrap();
        assert_eq!(regions.len(), 1);
        assert_eq!(regions[0].visible_mask_cells, 20);
        assert_eq!(regions[0].box_upright_xyxy, [0.0, 160.0, 10.0, 240.0]);
        assert_eq!(regions[0].centroid_upright_xy, [5.0, 200.0]);
    }

    #[test]
    fn source_row_size_is_frozen_by_p7_contract() {
        assert_eq!(ROW_WIDTH, 38);
        assert_eq!(MASK_PIXELS, 25600);
        assert_eq!(MAX_MASKS_PER_FRAME, 10);
    }
}
