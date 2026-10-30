//! PER-P10B: strictly bounded ORT tail on the pinned OEM duck-detect runtime.
//! Not an OEM camera feed, verified recognition, physical presence or permission.
use anyhow::{Context, Result, bail};
use kwipi_seg_mask_core::{decode, oem_region::{UprightFrame, ProjectedRegion2d, project_to_upright}, OUTPUT0_LEN, OUTPUT1_LEN};
use ort::{session::{Session, builder::GraphOptimizationLevel}, value::{Tensor, ValueType}, tensor::TensorElementType};
use std::path::Path;

pub const SHAPES: [[usize;4];10] = [
    [1,4,80,80], [1,4,40,40], [1,4,20,20],
    [1,80,80,80], [1,80,40,40], [1,80,20,20],
    [1,32,80,80], [1,32,40,40], [1,32,20,20],
    [1,32,160,160],
];
pub const NAMES: [&str;10] = [
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

fn validate_raw(raw: &[Vec<f32>]) -> Result<()> {
    if raw.len() != 10 { bail!("expected exactly ten P10A tensors"); }
    for (i, (buffer, shape)) in raw.iter().zip(SHAPES).enumerate() {
        let expected = shape.iter().product::<usize>();
        if buffer.len() != expected || buffer.iter().any(|x| !x.is_finite()) {
            bail!("tensor {i} has wrong length or non-finite elements");
        }
    }
    Ok(())
}

fn validate_outlets(outlets: &[ort::value::Outlet], names: &[&str], shapes: &[[usize;4]]) -> Result<()> {
    if outlets.len() != names.len() { bail!("ORT outlet count mismatch"); }
    for (index, ((out, name), shape)) in outlets.iter().zip(names).zip(shapes).enumerate() {
        if out.name() != *name { bail!("ORT outlet name/order mismatch at {index}"); }
        match out.dtype() {
            ValueType::Tensor { ty: TensorElementType::Float32, shape: actual, .. }
                if actual.as_ref() == shape.map(|x| x as i64).as_slice() => (),
            _ => bail!("ORT outlet type/shape mismatch at {index}"),
        }
    }
    Ok(())
}

pub struct Tail {
    session: Session,
}

impl Tail {
    pub fn open(path: &Path) -> Result<Self> {
        // Same OEM ort crate and session options as duck-detect/src/onnx.rs.
        // Missing or incompatible native library must remain an explicit error.
        if !path.is_file() || path.is_symlink() { bail!("tail ONNX path invalid"); }
        let session = Session::builder().context("tail session builder")?
            .with_optimization_level(GraphOptimizationLevel::Level3)?
            .with_intra_threads(2)?.commit_from_file(path)
            .context("tail ONNX load failed")?;
        validate_outlets(session.inputs(), &NAMES, &SHAPES)?;
        if session.outputs().len() != 2 { bail!("tail must produce exactly two outputs"); }
        for (output, (name, dims)) in session.outputs().iter().zip([
            ("output0", vec![1_i64,300,38]),
            ("output1", vec![1_i64,32,160,160]),
        ]) {
            if output.name() != name { bail!("tail output name/order mismatch"); }
            match output.dtype() {
                ValueType::Tensor { ty: TensorElementType::Float32, shape, .. }
                    if shape.as_ref() == dims.as_slice() => (),
                _ => bail!("tail output shape/type mismatch"),
            }
        }
        Ok(Self { session })
    }

    pub fn process(&mut self, raw: [Vec<f32>;10], frame: UprightFrame) -> Result<Vec<ProjectedRegion2d>> {
        validate_raw(&raw)?;
        // Construct all ten input tensors as owned buffers; avoid another full copy.
        let mut values = Vec::with_capacity(10);
        for (shape, buf) in SHAPES.into_iter().zip(raw) {
            values.push(Tensor::from_array((shape, buf.into_boxed_slice()))
                .context("ORT input tensor allocation")?.into_dyn());
        }
        let inputs: Vec<(&str, ort::value::DynValue)> =
            NAMES.iter().copied().zip(values).collect();
        let output = self.session.run(inputs).context("ORT tail inference")?;
        let (shape0, boxes) = output[0].try_extract_tensor::<f32>().context("ORT decoded output0")?;
        let (shape1, proto) = output[1].try_extract_tensor::<f32>().context("ORT prototype output1")?;
        if shape0.as_ref() != [1,300,38] || boxes.len() != OUTPUT0_LEN ||
           shape1.as_ref() != [1,32,160,160] || proto.len() != OUTPUT1_LEN {
            bail!("ORT returned invalid tensor dimensions");
        }
        let masks = decode(boxes, proto, 0.25, 10)
            .map_err(|e| anyhow::anyhow!("mask core rejected tail output: {e:?}"))?;
        project_to_upright(&masks, frame).map_err(|e| anyhow::anyhow!("OEM projection refused: {e:?}"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn p5_contract_uses_exactly_ten_bounded_shapes() {
        assert_eq!(SHAPES.iter().map(|s| s.iter().product::<usize>()).sum::<usize>(), 1_793_600);
        assert_eq!(NAMES.len(), 10);
        assert_eq!(NAMES[9], "rknn_mask_prototypes");
        let valid: Vec<Vec<f32>> = SHAPES.iter().map(|s| vec![0.;s.iter().product()]).collect();
        assert!(validate_raw(&valid).is_ok());
        let mut invalid = valid.clone();
        invalid[3].pop();
        assert!(validate_raw(&invalid).is_err());
        invalid = valid.clone();
        invalid[8][0] = f32::NAN;
        assert!(validate_raw(&invalid).is_err());
        invalid = valid.clone();
        invalid[9][0] = f32::INFINITY;
        assert!(validate_raw(&invalid).is_err());
        assert!(validate_raw(&valid[..9]).is_err());
    }
}
