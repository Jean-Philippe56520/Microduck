//! Read-only, allocation-bounded segmentation mask projection for Kwipi.
//!
//! The only inputs are decoded ONNX tail outputs from PER-P6:
//! output0 [1, 300, 38] = xyxy, score, COCO class id, 32 coefficients;
//! output1 [1, 32, 160, 160] = mask prototype planes in CHW order.
//!
//! No camera access, NPU ownership, network, filesystem, SQLite, motion or
//! action permissions. OEM mediad integration requires a separate decision.
//! Class ids are uncertain detector hypotheses, not real-world semantics.

pub const IMAGE_SIDE: usize = 640;
pub const MASK_SIDE: usize = 160;
pub const MAX_PROPOSALS: usize = 300;
pub const MASK_CHANNELS: usize = 32;
pub const ROW_WIDTH: usize = 6 + MASK_CHANNELS;
pub const OUTPUT0_LEN: usize = MAX_PROPOSALS * ROW_WIDTH;
pub const MASK_PIXELS: usize = MASK_SIDE * MASK_SIDE;
pub const OUTPUT1_LEN: usize = MASK_CHANNELS * MASK_PIXELS;
pub const MAX_MASKS_PER_FRAME: usize = 10;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DecodeError {
    WrongDecodedShape,
    WrongPrototypeShape,
    InvalidThreshold,
    TooManyMasksRequested,
    NonFiniteScore,
    NonFinitePrototype,
    InvalidScore,
    InvalidClass,
    InvalidBox,
    NonFiniteCoefficient,
}

#[derive(Debug, Clone, PartialEq)]
pub struct MaskCandidate {
    /// A COCO model class *proposal* (0..79), never a confirmed fact.
    pub proposed_class_id: u8,
    pub score: f32,
    /// xyxy in the 640x640 model input, not in the original camera frame.
    pub box_model_xyxy: [f32; 4],
    /// Ephemeral 160x160 binary mask in model coordinates (0/1 per pixel).
    pub mask_160: Vec<u8>,
    pub foreground_pixels: usize,
}

fn checked_box(row: &[f32]) -> Result<[f32; 4], DecodeError> {
    let box_ = [row[0], row[1], row[2], row[3]];
    if box_.iter().any(|v| !v.is_finite())
        || box_.iter().any(|v| *v < 0.0 || *v > IMAGE_SIDE as f32)
        || !(box_[0] < box_[2] && box_[1] < box_[3])
    {
        return Err(DecodeError::InvalidBox);
    }
    Ok(box_)
}

/// Project the already-decoded P6 tensor pair to at most ten ephemeral masks.
///
/// The reference is Ultralytics 8.4.192's non-upsampled segmentation topology:
/// for a selected end-to-end row, threshold the scalar product of its 32
/// coefficients with the 32-channel prototype at (y,x), then crop to its box
/// scaled from 640x640 to 160x160. This is independent implementation of the
/// mathematical contract, not a copy of vendor code.
///
/// The inputs are *borrowed*. The only per-frame masks allocated are at most
/// 10*160*160 = 256,000 bytes; no source images or full-frame history are
/// retained. YOLO26's 300 end-to-end rows do not require a second NMS.
///
/// Failure is fail-closed: invalid shape, confidences, finite values, class
/// ids or model-space geometry never turn into candidate observations.
pub fn decode(
    output0: &[f32],
    output1: &[f32],
    score_min: f32,
    max_det: usize,
) -> Result<Vec<MaskCandidate>, DecodeError> {
    if output0.len() != OUTPUT0_LEN {
        return Err(DecodeError::WrongDecodedShape);
    }
    if output1.len() != OUTPUT1_LEN {
        return Err(DecodeError::WrongPrototypeShape);
    }
    if !score_min.is_finite() || !(0.0..=1.0).contains(&score_min) {
        return Err(DecodeError::InvalidThreshold);
    }
    if max_det > MAX_MASKS_PER_FRAME {
        return Err(DecodeError::TooManyMasksRequested);
    }
    if output1.iter().any(|v| !v.is_finite()) {
        return Err(DecodeError::NonFinitePrototype);
    }

    // Even a non-selected NaN score must never be mistaken for a low score.
    let mut eligible: Vec<(usize, f32)> = Vec::with_capacity(MAX_PROPOSALS);
    for i in 0..MAX_PROPOSALS {
        let score = output0[i * ROW_WIDTH + 4];
        if !score.is_finite() {
            return Err(DecodeError::NonFiniteScore);
        }
        if !(0.0..=1.0).contains(&score) {
            return Err(DecodeError::InvalidScore);
        }
        if score > score_min && max_det != 0 {
            eligible.push((i, score));
        }
    }
    eligible
        .sort_by(|(a, a_score), (b, b_score)| b_score.total_cmp(a_score).then_with(|| a.cmp(b)));
    let mut items = Vec::with_capacity(max_det.min(eligible.len()));

    for (index, score) in eligible.into_iter().take(max_det) {
        let row = &output0[index * ROW_WIDTH..(index + 1) * ROW_WIDTH];
        let box_ = checked_box(row)?;
        let class = row[5];
        if !class.is_finite() || !(0.0..80.0).contains(&class) || class.fract() != 0.0 {
            return Err(DecodeError::InvalidClass);
        }
        let coeff = &row[6..ROW_WIDTH];
        if coeff.iter().any(|value| !value.is_finite()) {
            return Err(DecodeError::NonFiniteCoefficient);
        }
        let mut mask = vec![0_u8; MASK_PIXELS];
        let mut foreground = 0_usize;

        // Pixel-index crop matches the non-upsampled 160x160 reference.
        let bx0 = box_[0] * (MASK_SIDE as f32 / IMAGE_SIDE as f32);
        let by0 = box_[1] * (MASK_SIDE as f32 / IMAGE_SIDE as f32);
        let bx1 = box_[2] * (MASK_SIDE as f32 / IMAGE_SIDE as f32);
        let by1 = box_[3] * (MASK_SIDE as f32 / IMAGE_SIDE as f32);
        for y in 0..MASK_SIDE {
            if (y as f32) < by0 || (y as f32) >= by1 {
                continue;
            }
            for x in 0..MASK_SIDE {
                if (x as f32) < bx0 || (x as f32) >= bx1 {
                    continue;
                }
                let offset = y * MASK_SIDE + x;
                let mut value = 0.0_f32;
                for (k, weight) in coeff.iter().enumerate() {
                    value += *weight * output1[k * MASK_PIXELS + offset];
                }
                if value > 0.0 {
                    mask[offset] = 1;
                    foreground += 1;
                }
            }
        }
        items.push(MaskCandidate {
            proposed_class_id: class as u8,
            score,
            box_model_xyxy: box_,
            mask_160: mask,
            foreground_pixels: foreground,
        });
    }
    Ok(items)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn blank() -> (Vec<f32>, Vec<f32>) {
        (vec![0.0; OUTPUT0_LEN], vec![0.0; OUTPUT1_LEN])
    }

    fn add_candidate(
        rows: &mut [f32],
        index: usize,
        score: f32,
        class: f32,
        bbox: [f32; 4],
        k: usize,
        coeff: f32,
    ) {
        let row = &mut rows[index * ROW_WIDTH..(index + 1) * ROW_WIDTH];
        row[..4].copy_from_slice(&bbox);
        row[4] = score;
        row[5] = class;
        row[6 + k] = coeff;
    }

    #[test]
    fn no_candidate_returns_no_mask_or_knowledge() {
        let (rows, proto) = blank();
        assert!(decode(&rows, &proto, 0.25, 10).unwrap().is_empty());
    }

    #[test]
    fn square_inside_box_has_exact_binary_mask() {
        let (mut rows, mut proto) = blank();
        add_candidate(&mut rows, 7, 0.91, 32.0, [40.0, 80.0, 200.0, 240.0], 0, 1.0);
        proto[..MASK_PIXELS].fill(1.0);
        let out = decode(&rows, &proto, 0.25, 10).unwrap();
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].proposed_class_id, 32);
        // 40..200 => mask x 10..50, 80..240 => y 20..60
        assert_eq!(out[0].foreground_pixels, 1600);
        assert_eq!(out[0].mask_160[20 * MASK_SIDE + 10], 1);
        assert_eq!(out[0].mask_160[59 * MASK_SIDE + 49], 1);
        assert_eq!(out[0].mask_160[60 * MASK_SIDE + 49], 0);
        assert_eq!(out[0].mask_160[19 * MASK_SIDE + 10], 0);
        assert_eq!(out[0].mask_160.len(), MASK_PIXELS);
    }

    #[test]
    fn nonpositive_logits_do_not_fabricate_a_mask() {
        let (mut rows, mut proto) = blank();
        add_candidate(&mut rows, 0, 0.8, 0.0, [0.0, 0.0, 640.0, 640.0], 0, -1.0);
        proto[..MASK_PIXELS].fill(1.0);
        let out = decode(&rows, &proto, 0.25, 10).unwrap();
        assert_eq!(out.len(), 1);
        assert_eq!(out[0].foreground_pixels, 0);
        assert!(out[0].mask_160.iter().all(|v| *v == 0));
    }

    #[test]
    fn top_k_is_stable_and_allocates_at_most_ten_masks() {
        let (mut rows, mut proto) = blank();
        proto[..MASK_PIXELS].fill(1.0);
        for i in 0..20 {
            add_candidate(
                &mut rows,
                i,
                (60 + i) as f32 / 100.0,
                (i % 80) as f32,
                [0., 0., 40., 40.],
                0,
                1.0,
            );
        }
        let out = decode(&rows, &proto, 0.25, 10).unwrap();
        assert_eq!(out.len(), 10);
        assert_eq!(out[0].proposed_class_id, 19);
        assert_eq!(out[9].proposed_class_id, 10);
        assert_eq!(out.iter().map(|v| v.mask_160.len()).sum::<usize>(), 256000);
    }

    #[test]
    fn wrong_shapes_and_unbounded_limits_are_rejected() {
        let (rows, proto) = blank();
        assert_eq!(
            decode(&rows[1..], &proto, 0.25, 10),
            Err(DecodeError::WrongDecodedShape)
        );
        assert_eq!(
            decode(&rows, &proto[1..], 0.25, 10),
            Err(DecodeError::WrongPrototypeShape)
        );
        assert_eq!(
            decode(&rows, &proto, 0.25, 11),
            Err(DecodeError::TooManyMasksRequested)
        );
        assert_eq!(
            decode(&rows, &proto, f32::NAN, 10),
            Err(DecodeError::InvalidThreshold)
        );
        assert_eq!(
            decode(&rows, &proto, -0.1, 10),
            Err(DecodeError::InvalidThreshold)
        );
    }

    #[test]
    fn nonfinite_and_invalid_candidates_fail_closed() {
        let (mut rows, mut proto) = blank();
        rows[4] = f32::NAN;
        assert_eq!(
            decode(&rows, &proto, 0.25, 10),
            Err(DecodeError::NonFiniteScore)
        );
        rows[4] = 1.1;
        assert_eq!(
            decode(&rows, &proto, 0.25, 10),
            Err(DecodeError::InvalidScore)
        );
        rows[4] = 0.0;
        proto[0] = f32::INFINITY;
        assert_eq!(
            decode(&rows, &proto, 0.25, 10),
            Err(DecodeError::NonFinitePrototype)
        );
        proto[0] = 0.0;
        add_candidate(&mut rows, 0, 0.9, 80.0, [0., 0., 40., 40.], 0, 1.0);
        assert_eq!(
            decode(&rows, &proto, 0.25, 10),
            Err(DecodeError::InvalidClass)
        );
        rows[5] = 1.5;
        assert_eq!(
            decode(&rows, &proto, 0.25, 10),
            Err(DecodeError::InvalidClass)
        );
        rows[5] = 1.0;
        rows[0] = 80.0;
        rows[2] = 40.0;
        assert_eq!(
            decode(&rows, &proto, 0.25, 10),
            Err(DecodeError::InvalidBox)
        );
        rows[0] = 0.0;
        rows[6] = f32::INFINITY;
        assert_eq!(
            decode(&rows, &proto, 0.25, 10),
            Err(DecodeError::NonFiniteCoefficient)
        );
    }

    #[test]
    fn tie_break_is_source_row_order() {
        let (mut rows, mut proto) = blank();
        proto[..MASK_PIXELS].fill(1.0);
        add_candidate(&mut rows, 7, 0.8, 7.0, [0., 0., 40., 40.], 0, 1.0);
        add_candidate(&mut rows, 2, 0.8, 2.0, [0., 0., 40., 40.], 0, 1.0);
        let out = decode(&rows, &proto, 0.25, 2).unwrap();
        assert_eq!((out[0].proposed_class_id, out[1].proposed_class_id), (2, 7));
    }
}
