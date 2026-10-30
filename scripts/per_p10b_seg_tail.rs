//! PER-P10B — one existing OEM ORT session consumes the ten P10A RKNN heads.
//!
//! Included only in a throwaway archive of pinned duck-detect for CI. Reuses
//! OEM ort 2.0.0-rc.11 and the existing P7/P9 Rust library. No second NPU
//! binding, camera, motor, storage, publisher, decoder or new service.
//! Nothing returned is verified physical presence, identity or navigation.

use std::ffi::OsStr;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::path::Path;

use anyhow::{Context, Result, bail, ensure};
use kwipi_seg_mask_core::oem_region::{ProjectedRegion2d, UprightFrame, project_to_upright};
use kwipi_seg_mask_core::{MAX_MASKS_PER_FRAME, OUTPUT0_LEN, OUTPUT1_LEN, decode};
use ort::session::{Session, builder::GraphOptimizationLevel};
use ort::tensor::TensorElementType;
use ort::value::{Tensor, ValueType};

pub const P10B_HEAD_NAMES: [&str; 10] = [
    "/model.23/one2one_cv2.0/one2one_cv2.0.2/Conv_output_0",
    "/model.23/one2one_cv2.1/one2one_cv2.1.2/Conv_output_0",
    "/model.23/one2one_cv2.2/one2one_cv2.2.2/Conv_output_0",
    "/model.23/one2one_cv3.0/one2one_cv3.0.2/Conv_output_0",
    "/model.23/one2one_cv3.1/one2one_cv3.1.2/Conv_output_0",
    "/model.23/one2one_cv3.2/one2one_cv3.2.2/Conv_output_0",
    "/model.23/one2one_cv4.0/one2one_cv4.0.2/Conv_output_0",
    "/model.23/one2one_cv4.1/one2one_cv4.1.2/Conv_output_0",
    "/model.23/one2one_cv4.2/one2one_cv4.2.2/Conv_output_0",
    "rknn_mask_prototypes",
];

pub const P10B_SHAPES: [[usize; 4]; 10] = [
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

const MAX_TAIL_ONNX_BYTES: u64 = 8 * 1024 * 1024;
const EXPECTED_OUTPUTS: [(&str, &[i64]); 2] =
    [("output0", &[1, 300, 38]), ("output1", &[1, 32, 160, 160])];

/// Validate raw P10A tensors before constructing ONNX Runtime input buffers.
/// A "frame" is atomic: any invalid part means zero published regions.
pub fn validate_raw_heads(raw: &[Vec<f32>]) -> Result<()> {
    ensure!(
        raw.len() == 10,
        "segmentation tail needs exactly 10 RKNN heads"
    );
    for (index, (arr, shape)) in raw.iter().zip(P10B_SHAPES).enumerate() {
        let size: usize = shape.iter().product();
        ensure!(
            arr.len() == size,
            "RKNN raw tensor {index} has wrong length"
        );
        ensure!(
            arr.iter().all(|value| value.is_finite()),
            "RKNN raw tensor {index} has non-finite values"
        );
    }
    Ok(())
}

fn check_outlets(actual: &[ort::value::Outlet], expected: &[(&str, &[i64])]) -> Result<()> {
    ensure!(
        actual.len() == expected.len(),
        "tail ONNX I/O count mismatch"
    );
    for (index, (outlet, (name, dims))) in actual.iter().zip(expected).enumerate() {
        ensure!(
            outlet.name() == *name,
            "tail ONNX tensor {index} name/order mismatch"
        );
        match outlet.dtype() {
            ValueType::Tensor {
                ty: TensorElementType::Float32,
                shape,
                ..
            } => {
                ensure!(
                    shape.as_ref() == *dims,
                    "tail ONNX tensor {index} f32 dimensions mismatch"
                );
            }
            _ => bail!("tail ONNX tensor {index} must be float32"),
        }
    }
    Ok(())
}

fn probe_runtime(path: &OsStr) -> Result<()> {
    // Same dlopen strategy as OEM duck-control's policy loader. Never silently
    // install a new runtime or alter robotd's library path.
    let runtime = unsafe { libloading::Library::new(path) }
        .with_context(|| format!("ONNX Runtime unavailable at {path:?}"))?;
    drop(runtime);
    Ok(())
}

/// The tail belongs to the pre-existing perception worker only. Opening a
/// session outside that worker, or keeping multiple sessions, is not provided.
pub struct Tail {
    session: Session,
}

impl Tail {
    pub fn open(path: &Path) -> Result<Self> {
        let metadata = std::fs::symlink_metadata(path)
            .with_context(|| format!("cannot stat tail ONNX {}", path.display()))?;
        ensure!(
            metadata.is_file()
                && !metadata.file_type().is_symlink()
                && (1..=MAX_TAIL_ONNX_BYTES).contains(&metadata.len()),
            "unapproved or oversized ONNX tail file"
        );
        let library =
            std::env::var_os("ORT_DYLIB_PATH").unwrap_or_else(|| "libonnxruntime.so".into());
        probe_runtime(library.as_os_str())?;

        // The OEM's policy loader explicitly documents that ort can panic on
        // a runtime/ABI mismatch despite a successful dlopen. Fail closed.
        let session = catch_unwind(AssertUnwindSafe(|| -> Result<Session> {
            Session::builder()
                .context("OEM ort session builder")?
                .with_optimization_level(GraphOptimizationLevel::Level3)
                .context("OEM ort optimisation")?
                .with_intra_threads(2)
                .context("OEM ort two-thread cap")?
                .commit_from_file(path)
                .with_context(|| format!("cannot load ONNX tail {}", path.display()))
        }))
        .map_err(|_| anyhow::anyhow!("ONNX Runtime panic while opening tail"))??;

        let expected_inputs: Vec<(&str, Vec<i64>)> = P10B_HEAD_NAMES
            .iter()
            .zip(P10B_SHAPES.iter())
            .map(|(name, dims)| (*name, dims.iter().map(|&v| v as i64).collect()))
            .collect();
        let input_refs: Vec<(&str, &[i64])> = expected_inputs
            .iter()
            .map(|(name, dims)| (*name, dims.as_slice()))
            .collect();
        check_outlets(session.inputs(), &input_refs)?;
        check_outlets(session.outputs(), &EXPECTED_OUTPUTS)?;
        Ok(Self { session })
    }

    /// Consumes the owned outputs of P10A and returns ONLY ephemeral 2D
    /// proposals. Never considers a score a fact, never commands motors.
    pub fn process(
        &mut self,
        heads: [Vec<f32>; 10],
        upright: UprightFrame,
        score_min: f32,
    ) -> Result<Vec<ProjectedRegion2d>> {
        validate_raw_heads(&heads)?;
        ensure!(
            score_min.is_finite() && (0.0..=1.0).contains(&score_min),
            "invalid segmentation confidence threshold"
        );
        // Geometry must be verified *before* potentially costly inference.
        project_to_upright(&[], upright).map_err(|e| anyhow::anyhow!("{e:?}"))?;
        let [h0, h1, h2, h3, h4, h5, h6, h7, h8, prototype] = heads;

        let tensors = ort::inputs![
            Tensor::from_array((P10B_SHAPES[0], h0.into_boxed_slice()))?,
            Tensor::from_array((P10B_SHAPES[1], h1.into_boxed_slice()))?,
            Tensor::from_array((P10B_SHAPES[2], h2.into_boxed_slice()))?,
            Tensor::from_array((P10B_SHAPES[3], h3.into_boxed_slice()))?,
            Tensor::from_array((P10B_SHAPES[4], h4.into_boxed_slice()))?,
            Tensor::from_array((P10B_SHAPES[5], h5.into_boxed_slice()))?,
            Tensor::from_array((P10B_SHAPES[6], h6.into_boxed_slice()))?,
            Tensor::from_array((P10B_SHAPES[7], h7.into_boxed_slice()))?,
            Tensor::from_array((P10B_SHAPES[8], h8.into_boxed_slice()))?,
            Tensor::from_array((P10B_SHAPES[9], prototype.into_boxed_slice()))?,
        ];
        let predictions = catch_unwind(AssertUnwindSafe(|| self.session.run(tensors)))
            .map_err(|_| anyhow::anyhow!("ONNX Runtime panic during tail inference"))??;
        let (_, decoded) = predictions[0]
            .try_extract_tensor::<f32>()
            .context("ONNX output0 is not float32")?;
        let (_, proto) = predictions[1]
            .try_extract_tensor::<f32>()
            .context("ONNX output1 is not float32")?;
        ensure!(
            decoded.len() == OUTPUT0_LEN && proto.len() == OUTPUT1_LEN,
            "unexpected ORT decoded/prototype output length"
        );
        ensure!(
            decoded.iter().all(|v| v.is_finite()) && proto.iter().all(|v| v.is_finite()),
            "ONNX tail produced non-finite data"
        );
        let masks = decode(decoded, proto, score_min, MAX_MASKS_PER_FRAME)
            .map_err(|e| anyhow::anyhow!("P7 refused output: {e:?}"))?;
        project_to_upright(&masks, upright)
            .map_err(|e| anyhow::anyhow!("P9 refused projection: {e:?}"))
    }

    /// Compile-time bridge to the P10A RKNN wrapper; not executed in host CI
    /// since no NPU runtime/board is present. mediad may call it later from
    /// its *existing* paced worker, once the model/permissions are approved.
    pub fn infer_from_rknn(
        &mut self,
        rknn: &mut crate::rknn::Model,
        frame_rgb_640: &[u8],
        upright: UprightFrame,
        score_min: f32,
    ) -> Result<Vec<ProjectedRegion2d>> {
        let heads = rknn.infer_segments(frame_rgb_640)?;
        self.process(heads, upright, score_min)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn synthetic_path(name: &str) -> std::path::PathBuf {
        Path::new(
            &std::env::var("KWIPI_P10B_TEST_MODELS")
                .expect("P10B ONNX fixtures must be generated in the CI temp directory"),
        )
        .join(name)
    }

    fn portrait() -> UprightFrame {
        UprightFrame {
            width: 720,
            height: 1280,
            scale: 0.5,
            pad_x: 140.0,
            pad_y: 0.0,
        }
    }

    fn heads(score_on: bool, proto_on: bool) -> [Vec<f32>; 10] {
        std::array::from_fn(|i| {
            let size: usize = P10B_SHAPES[i].iter().product();
            let mut data = vec![if i == 0 && !score_on { 0.0 } else { 1.0 }; size];
            if i == 9 {
                data.fill(0.0);
                if proto_on {
                    data[..160 * 160].fill(1.0);
                }
            }
            data
        })
    }

    #[test]
    fn real_rust_ort_session_produces_one_p7_mask_and_one_p9_upright_region() {
        let mut tail = Tail::open(&synthetic_path("valid.onnx")).unwrap();
        let valid = tail.process(heads(true, true), portrait(), 0.25).unwrap();
        assert_eq!(valid.len(), 1);
        assert_eq!(valid[0].proposed_class_id, 32);
        assert_eq!(valid[0].source_mask_cells, 100);
        assert_eq!(valid[0].visible_mask_cells, 100);
        assert_eq!(valid[0].box_upright_xyxy, [200.0, 160.0, 280.0, 240.0]);
        assert_eq!(valid[0].centroid_upright_xy, [240.0, 200.0]);
        assert!(
            tail.process(heads(false, true), portrait(), 0.25)
                .unwrap()
                .is_empty()
        );
        assert!(
            tail.process(heads(true, false), portrait(), 0.25)
                .unwrap()
                .is_empty()
        );
    }

    #[test]
    fn real_ort_graph_must_match_ten_exact_names_shapes_float_types_and_outputs() {
        for invalid in [
            "wrong_name.onnx",
            "wrong_shape.onnx",
            "wrong_proto_dtype.onnx",
            "wrong_output.onnx",
            "wrong_proto_shape.onnx",
        ] {
            assert!(
                Tail::open(&synthetic_path(invalid)).is_err(),
                "invalid ONNX model {invalid} was accepted"
            );
        }
    }

    #[test]
    fn bad_raw_lengths_counts_nan_and_inf_fail_before_inference() {
        let good = heads(true, true);
        assert!(validate_raw_heads(&good[..9]).is_err());
        let mut too_many = good.to_vec();
        too_many.push(vec![1.0]);
        assert!(validate_raw_heads(&too_many).is_err());
        let mut wrong = heads(true, true);
        wrong[8].pop();
        assert!(validate_raw_heads(&wrong).is_err());
        let mut nan = heads(true, true);
        nan[4][3] = f32::NAN;
        assert!(validate_raw_heads(&nan).is_err());
        let mut inf = heads(true, true);
        inf[0][0] = f32::INFINITY;
        assert!(validate_raw_heads(&inf).is_err());
    }

    #[test]
    fn invalid_geometry_or_threshold_never_produces_a_region() {
        let mut tail = Tail::open(&synthetic_path("valid.onnx")).unwrap();
        assert!(
            tail.process(heads(true, true), portrait(), f32::NAN)
                .is_err()
        );
        assert!(
            tail.process(
                heads(true, true),
                UprightFrame {
                    pad_x: 139.0,
                    ..portrait()
                },
                0.25
            )
            .is_err()
        );
    }

    #[test]
    fn missing_model_or_missing_native_runtime_is_an_explicit_error() {
        assert!(Tail::open(&synthetic_path("nonexistent.onnx")).is_err());
        assert!(
            probe_runtime(OsStr::new(
                "/this-path-must-not-exist/kwipi-libonnxruntime.so"
            ))
            .is_err()
        );
    }
}
