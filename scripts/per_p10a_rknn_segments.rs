//! PER-P10A: ten-output RKNN bridge for the PINNED duck-detect Model.
//!
//! Copied to duck-detect/src/rknn/segments.rs in a throwaway OEM archive by
//! scripts/per_p10a_apply_oem_rknn_overlay.py.  It is a CHILD module of the
//! existing OEM rknn.rs, and reuses its context, librknnrt symbols and input.
//! Never link another RKNN runtime, drive motors or acquire a second camera.

use super::{Model, RKNN_TENSOR_NHWC, RKNN_TENSOR_UINT8, RknnInput, RknnOutput, RknnTensorAttr};
use anyhow::{Result, bail};
use std::ffi::{c_uint, c_void};

const SEG_OUTPUTS: usize = 10;
const SEG_FLOAT_BYTES: usize = 7_174_400;
const DIMS_NCHW: [[c_uint; 4]; SEG_OUTPUTS] = [
    [1, 4, 80, 80],
    [1, 4, 40, 40],
    [1, 4, 20, 20],
    [1, 80, 80, 80],
    [1, 80, 40, 40],
    [1, 80, 20, 20],
    [1, 32, 80, 80],
    [1, 32, 40, 40],
    [1, 32, 20, 20],
    [1, 32, 160, 160],
];
const ELEMENTS: [usize; SEG_OUTPUTS] = [
    25_600, 6_400, 1_600, 512_000, 128_000, 32_000, 204_800, 51_200, 12_800, 819_200,
];

/// A standalone contract: the single-output OEM model must remain single,
/// and this specific model must be exactly one input and ten outputs.
pub(super) fn verify_counts(inputs: c_uint, outputs: c_uint, segments: bool) -> Result<()> {
    let wanted = if segments { SEG_OUTPUTS as c_uint } else { 1 };
    if inputs != 1 || outputs != wanted {
        bail!(
            "expected 1 input and {wanted} output(s), got {inputs} and {outputs}; model type mismatch"
        );
    }
    Ok(())
}

/// Check all ten outputs BEFORE exposing data to the ONNX tail. A different
/// RKNN export/SDK may change layout or dtype: stop, do not reinterpret it.
///
/// The output dimensions and order are the P5 Rockchip 2.3.2 PC observations,
/// not an assertion about an actual NPU. INT8 (type 2), FLOAT32 (0) and FLOAT16
/// (1) are the only accepted RKNN raw types here. The runtime must still
/// return FLOAT32 via rknn_outputs_get(want_float=1).
pub(super) fn verify_attrs(attrs: &[RknnTensorAttr]) -> Result<[usize; SEG_OUTPUTS]> {
    if attrs.len() != SEG_OUTPUTS {
        bail!("expected ten RKNN output attrs, got {}", attrs.len());
    }
    let mut total_bytes = 0usize;
    for (index, attr) in attrs.iter().enumerate() {
        if attr.index as usize != index
            || attr.n_dims != 4
            || attr.dims[..4] != DIMS_NCHW[index]
            || attr.n_elems as usize != ELEMENTS[index]
        {
            bail!("RKNN output {index} has unexpected shape/order/elements");
        }
        let bytes_per_element = match attr.type_ {
            0 => 4, // float32
            1 => 2, // float16
            2 => 1, // int8
            3 => 1, // uint8
            other => bail!("RKNN output {index} unsupported dtype {other}"),
        };
        if attr.size as usize != ELEMENTS[index] * bytes_per_element {
            bail!("RKNN output {index} has inconsistent raw byte count");
        }
        total_bytes += ELEMENTS[index] * std::mem::size_of::<f32>();
    }
    if total_bytes != SEG_FLOAT_BYTES {
        bail!("segmentation float32 output budget violated");
    }
    Ok(ELEMENTS)
}

/// Copies all ten vendor-owned float buffers atomically, BEFORE they are
/// released by the caller. A failed copy never returns partial predictions.
/// Caller must have successfully called rknn_outputs_get(10, want_float=1).
fn copy_outputs(
    raw: &[RknnOutput; SEG_OUTPUTS],
    expected: &[usize; SEG_OUTPUTS],
) -> Result<[Vec<f32>; SEG_OUTPUTS]> {
    let mut copied: [Vec<f32>; SEG_OUTPUTS] = std::array::from_fn(|_| Vec::new());
    for (index, output) in raw.iter().enumerate() {
        let length = expected[index];
        if length != ELEMENTS[index]
            || output.index as usize != index
            || output.want_float != 1
            || output.buf.is_null()
            || (output.buf as usize) % std::mem::align_of::<f32>() != 0
            || output.size as usize != length * std::mem::size_of::<f32>()
        {
            bail!("RKNN output {index} missing, misaligned or wrongly sized");
        }
        // SAFETY: pointer is non-null/aligned and the SDK promised exactly
        // output.size bytes for this index with want_float=1. Runtime/driver
        // ABI still needs an actual RK3566 trial: PC cannot prove C ownership.
        let floats = unsafe { std::slice::from_raw_parts(output.buf.cast::<f32>(), length) };
        if floats.iter().any(|value| !value.is_finite()) {
            bail!("RKNN output {index} has non-finite values");
        }
        copied[index].extend_from_slice(floats);
    }
    Ok(copied)
}

/// Unconditionally release after a successful outputs_get, even if a later
/// output is invalid. Injectable release permits a negative PC fixture.
fn copy_then_release<F>(
    raw: &mut [RknnOutput; SEG_OUTPUTS],
    expected: &[usize; SEG_OUTPUTS],
    release: F,
) -> Result<[Vec<f32>; SEG_OUTPUTS]>
where
    F: FnOnce(&mut [RknnOutput; SEG_OUTPUTS]) -> i32,
{
    let copied = copy_outputs(raw, expected);
    let status = release(raw);
    if status != 0 {
        bail!("rknn_outputs_release(10) failed ({status})");
    }
    copied
}

impl Model {
    /// Load the EXACT P5 ten-output RKNN contract via the same OEM dlopen
    /// context. Never use Model::open for a ten-output model.
    pub fn open_segments(path: &std::path::Path) -> Result<Self> {
        Self::open_variant(path, true)
    }

    /// One already-letterboxed 640x640 NHWC RGB frame -> ten float tensors.
    /// No CPU ONNX tail, camera, notifications or memory/identity writes.
    ///
    /// Returns owned temporary buffers, not ten retained per-frame histories.
    pub fn infer_segments(&mut self, frame: &[u8]) -> Result<[Vec<f32>; SEG_OUTPUTS]> {
        let expected = self.segment_output_lens.ok_or_else(|| {
            anyhow::anyhow!("infer_segments requires open_segments, not the OEM single model")
        })?;
        let (h, w, c) = self.input;
        if (h, w, c) != (640, 640, 3) || frame.len() != h * w * c {
            bail!("segmentation input must be 640x640x3 NHWC RGB bytes");
        }
        let mut input = RknnInput {
            index: 0,
            buf: frame.as_ptr() as *mut c_void,
            size: frame.len() as c_uint,
            pass_through: 0,
            type_: RKNN_TENSOR_UINT8,
            fmt: RKNN_TENSOR_NHWC,
        };
        let mut outputs: [RknnOutput; SEG_OUTPUTS] = std::array::from_fn(|index| RknnOutput {
            want_float: 1,
            is_prealloc: 0,
            index: index as c_uint,
            buf: std::ptr::null_mut(),
            size: 0,
        });

        // SAFETY: exclusive &mut self controls the OEM context; frame owns input
        // bytes throughout the synchronous call. All vendor-owned output memory
        // is released BEFORE returning copied Rust-owned float buffers.
        unsafe {
            let status = (self.inputs_set)(self.context, 1, &mut input);
            if status != 0 {
                bail!("rknn_inputs_set failed ({status})");
            }
            let status = (self.run)(self.context, std::ptr::null());
            if status != 0 {
                bail!("rknn_run failed ({status})");
            }
            let status = (self.outputs_get)(
                self.context,
                SEG_OUTPUTS as c_uint,
                outputs.as_mut_ptr(),
                std::ptr::null(),
            );
            if status != 0 {
                // The API does not document how many pointers can be allocated
                // before failure: release if any are non-null, never return data.
                if outputs.iter().any(|o| !o.buf.is_null()) {
                    let _ = (self.outputs_release)(
                        self.context,
                        SEG_OUTPUTS as c_uint,
                        outputs.as_mut_ptr(),
                    );
                }
                bail!("rknn_outputs_get(10) failed ({status})");
            }
            copy_then_release(&mut outputs, &expected, |out| {
                (self.outputs_release)(self.context, SEG_OUTPUTS as c_uint, out.as_mut_ptr())
            })
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::Cell;

    fn fake_attrs() -> [RknnTensorAttr; SEG_OUTPUTS] {
        std::array::from_fn(|i| {
            // SAFETY: all-zero is a valid representation of this vendor C struct
            // for unit-test metadata, and fields are then explicitly populated.
            let mut a: RknnTensorAttr = unsafe { std::mem::zeroed() };
            a.index = i as c_uint;
            a.n_dims = 4;
            a.dims[..4].copy_from_slice(&DIMS_NCHW[i]);
            a.n_elems = ELEMENTS[i] as c_uint;
            a.type_ = 2;
            a.size = ELEMENTS[i] as c_uint;
            a
        })
    }

    fn owned_fake_buffers() -> ([Vec<f32>; SEG_OUTPUTS], [usize; SEG_OUTPUTS]) {
        (
            std::array::from_fn(|i| vec![i as f32; ELEMENTS[i]]),
            ELEMENTS,
        )
    }

    fn fake_outputs(buffers: &[Vec<f32>; SEG_OUTPUTS]) -> [RknnOutput; SEG_OUTPUTS] {
        std::array::from_fn(|i| RknnOutput {
            want_float: 1,
            is_prealloc: 0,
            index: i as c_uint,
            buf: buffers[i].as_ptr().cast::<c_void>() as *mut c_void,
            size: (buffers[i].len() * std::mem::size_of::<f32>()) as c_uint,
        })
    }

    #[test]
    fn preserves_oem_single_output_contract_and_separates_ten_output_mode() {
        assert!(verify_counts(1, 1, false).is_ok());
        assert!(verify_counts(1, 10, true).is_ok());
        assert!(verify_counts(1, 10, false).is_err());
        assert!(verify_counts(1, 1, true).is_err());
        assert!(verify_counts(0, 10, true).is_err());
        assert!(verify_counts(1, 9, true).is_err());
        assert!(verify_counts(1, 11, true).is_err());
    }

    #[test]
    fn exact_p5_shapes_order_and_budget_are_accepted() {
        assert_eq!(verify_attrs(&fake_attrs()).unwrap(), ELEMENTS);
        assert_eq!(ELEMENTS.iter().sum::<usize>(), 1_793_600);
        assert_eq!(SEG_FLOAT_BYTES, 7_174_400);
    }

    #[test]
    fn wrong_tensor_count_shape_order_dtype_and_size_fail_closed() {
        let mut attrs = fake_attrs();
        assert!(verify_attrs(&attrs[..9]).is_err());
        attrs.swap(0, 1);
        assert!(verify_attrs(&attrs).is_err());
        attrs = fake_attrs();
        attrs[6].dims[2] = 40;
        assert!(verify_attrs(&attrs).is_err());
        attrs = fake_attrs();
        attrs[1].n_elems -= 1;
        assert!(verify_attrs(&attrs).is_err());
        attrs = fake_attrs();
        attrs[3].type_ = 999;
        assert!(verify_attrs(&attrs).is_err());
        attrs = fake_attrs();
        attrs[9].size -= 1;
        assert!(verify_attrs(&attrs).is_err());
    }

    #[test]
    fn float_outputs_keep_exact_order_and_release_once() {
        let (buffers, expected) = owned_fake_buffers();
        let mut raw = fake_outputs(&buffers);
        let released = Cell::new(0);
        let copied = copy_then_release(&mut raw, &expected, |_| {
            released.set(released.get() + 1);
            0
        })
        .unwrap();
        assert_eq!(released.get(), 1);
        assert_eq!(copied[0][0], 0.);
        assert_eq!(copied[6][0], 6.);
        assert_eq!(copied[9][0], 9.);
        assert_eq!(copied[9].len(), 819_200);
        assert_eq!(copied.iter().map(Vec::len).sum::<usize>(), 1_793_600);
    }

    #[test]
    fn null_wrong_bytes_nonfinite_and_bad_order_do_not_publish_but_release() {
        let (mut buffers, expected) = owned_fake_buffers();
        buffers[6][0] = f32::NAN;
        let mut raw = fake_outputs(&buffers);
        for failure in 0..4 {
            let mut current = fake_outputs(&buffers);
            match failure {
                0 => current[8].buf = std::ptr::null_mut(),
                1 => current[8].size -= 4,
                2 => current[8].index = 9,
                _ => current[8].want_float = 0,
            }
            let released = Cell::new(0);
            assert!(
                copy_then_release(&mut current, &expected, |_| {
                    released.set(released.get() + 1);
                    0
                })
                .is_err()
            );
            assert_eq!(released.get(), 1);
        }
        let released = Cell::new(0);
        assert!(
            copy_then_release(&mut raw, &expected, |_| {
                released.set(released.get() + 1);
                0
            })
            .is_err()
        );
        assert_eq!(released.get(), 1);
    }

    #[test]
    fn even_valid_outputs_are_discarded_if_vendor_release_fails() {
        let (buffers, expected) = owned_fake_buffers();
        let mut raw = fake_outputs(&buffers);
        assert!(copy_then_release(&mut raw, &expected, |_| -1).is_err());
    }
}
