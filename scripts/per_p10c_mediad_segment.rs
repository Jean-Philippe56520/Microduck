//! PER-P10C: opt-in segmentation in the EXISTING OEM mediad detector worker.
//! No new frame acquisition, thread, servo driver, network listener or memory.
//! All regions are hypotheses, not verified presence, identity or motor permission.

use std::ffi::OsStr;
use std::path::Path;

use anyhow::{Result, ensure};
use duck_detect::rknn::Model;
use duck_detect::seg_tail::{ProjectedRegion2d, Tail, UprightFrame};
use uyvy::Letterbox;

use super::Sighting;

pub(super) const SEG_MODEL: &str = "kwipi_seg.rknn";
const SEG_TAIL: &str = "kwipi_seg_tail.onnx";
const MAX_SEG_HZ: f64 = 2.0;
const MAX_REGIONS: usize = 10;

/// The OEM model defaults do not contain this exact opt-in filename.
pub(super) fn is_segment_model(path: &Path) -> bool {
    path.file_name() == Some(OsStr::new(SEG_MODEL))
}

pub(super) fn tail_path(path: &Path) -> Result<std::path::PathBuf> {
    ensure!(is_segment_model(path), "not an explicitly selected Kwipi seg .rknn");
    Ok(path.with_file_name(SEG_TAIL))
}

pub(super) fn validate_seg_hz(hz: f64) -> Result<()> {
    ensure!(
        hz.is_finite() && hz > 0.0 && hz <= MAX_SEG_HZ,
        "segmentation requires sampling rate (0, 2] Hz"
    );
    Ok(())
}

/// Fail before opening NPU if its paired ORT tail cannot be loaded.
/// No silent fallback to the wrong model class or CPU detector.
pub(super) fn open(path: &Path) -> Result<(Model, Tail)> {
    let tail = Tail::open(&tail_path(path)?)?;
    let rknn = Model::open_segments(path)?;
    Ok((rknn, tail))
}

/// The OEM sampler tolerates torn frames by padding. This conservative branch
/// must reject them instead of presenting positive hypotheses on padded data.
pub(super) fn complete_uyvy(width: u32, height: u32, size: usize) -> bool {
    width > 0
        && width <= 4096
        && height > 0
        && height <= 4096
        && width % 2 == 0
        && (width as usize)
            .checked_mul(height as usize)
            .and_then(|count| count.checked_mul(2))
            == Some(size)
}

/// The common in-process path for NPU output and a test ONNX-only fixture.
/// The OEM UYVY letterbox remains the unique geometry/camera sampler.
pub(super) fn from_heads(
    tail: &mut Tail,
    heads: [Vec<f32>; 10],
    fit: Letterbox,
    upright_w: u32,
    upright_h: u32,
    score_min: f32,
) -> Result<Sighting> {
    let frame = UprightFrame {
        width: upright_w,
        height: upright_h,
        scale: fit.scale,
        pad_x: fit.pad_x,
        pad_y: fit.pad_y,
    };
    let regions = tail.process(heads, frame, score_min)?;
    Ok(Sighting {
        width: upright_w,
        height: upright_h,
        found: Vec::new(),
        region_candidates: Some(regions),
        took_ms: 0.0,
    })
}

fn region_valid(region: &ProjectedRegion2d, width: u32, height: u32) -> bool {
    let [x0, y0, x1, y1] = region.box_upright_xyxy;
    let [cx, cy] = region.centroid_upright_xy;
    region.proposed_class_id < 80
        && region.score.is_finite()
        && (0.0..=1.0).contains(&region.score)
        && [x0, y0, x1, y1, cx, cy].iter().all(|v| v.is_finite())
        && 0.0 <= x0 && x0 < x1 && x1 <= width as f32
        && 0.0 <= y0 && y0 < y1 && y1 <= height as f32
        && x0 <= cx && cx <= x1
        && y0 <= cy && cy <= y1
        && region.source_mask_cells <= 25_600
        && (1..=region.source_mask_cells).contains(&region.visible_mask_cells)
}

/// A new method, never the OEM single-class media.detections method.
/// The WebRTC transport is not proof of local sensor provenance. Invalid
/// payloads report "no_measurement" rather than an object-free measurement.
pub(super) fn notification(sighting: &Sighting) -> String {
    let regions = sighting.region_candidates.as_deref().unwrap_or(&[]);
    let valid = sighting.width > 0
        && sighting.height > 0
        && sighting.width <= 4096
        && sighting.height <= 4096
        && sighting.took_ms.is_finite()
        && (0.0..=5000.0).contains(&sighting.took_ms)
        && regions.len() <= MAX_REGIONS
        && regions.iter().all(|r| region_valid(r, sighting.width, sighting.height));

    if !valid {
        return format!(
            r#"{{"jsonrpc":"2.0","method":"media.region_candidates","params":{{"schema_version":1,"width":{},"height":{},"status":"no_measurement","source":"mediad_tee_transport_unverified","verified_physical_presence":false,"motor_permission":false,"regions":[]}}}}"#,
            sighting.width, sighting.height
        );
    }
    let descriptions: Vec<String> = regions
        .iter()
        .map(|r| {
            let [x0, y0, x1, y1] = r.box_upright_xyxy;
            let [cx, cy] = r.centroid_upright_xy;
            format!(
                r#"{{"proposed_class_id":{},"model_score_uncalibrated":{:.4},"x0":{x0:.2},"y0":{y0:.2},"x1":{x1:.2},"y1":{y1:.2},"cx":{cx:.2},"cy":{cy:.2},"visible_cells":{}}}"#,
                r.proposed_class_id,
                r.score,
                r.visible_mask_cells
            )
        })
        .collect();
    format!(
        r#"{{"jsonrpc":"2.0","method":"media.region_candidates","params":{{"schema_version":1,"width":{},"height":{},"took_ms":{:.1},"status":"candidate_hypotheses","source":"mediad_tee_transport_unverified","verified_physical_presence":false,"motor_permission":false,"regions":[{}]}}}}"#,
        sighting.width,
        sighting.height,
        sighting.took_ms,
        descriptions.join(",")
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn exact_filename_and_missing_tail_fail_without_npu() {
        assert!(is_segment_model(Path::new("/approved/kwipi_seg.rknn")));
        for bad in ["duck_detect.rknn", "kwipi_seg.rknn.bak", "kwipi_seg.onnx", "other_seg.rknn"] {
            assert!(!is_segment_model(Path::new(bad)));
        }
        assert_eq!(
            tail_path(Path::new("/approved/kwipi_seg.rknn"))
                .unwrap()
                .to_str(),
            Some("/approved/kwipi_seg_tail.onnx")
        );
        assert!(open(Path::new("/missing-test/kwipi_seg.rknn")).is_err());
    }

    #[test]
    fn bounded_hz_and_complete_uyvy_only() {
        for hz in [0.0, -1.0, 2.01, 10.0, f64::NAN, f64::INFINITY] {
            assert!(validate_seg_hz(hz).is_err());
        }
        assert!(validate_seg_hz(2.0).is_ok());
        assert!(validate_seg_hz(0.5).is_ok());
        assert!(complete_uyvy(1280, 720, 1280 * 720 * 2));
        assert!(!complete_uyvy(1280, 720, 1280 * 720 * 2 - 4));
        assert!(!complete_uyvy(1281, 720, 1281 * 720 * 2));
        assert!(!complete_uyvy(0, 720, 0));
        assert!(!complete_uyvy(5000, 720, 5000 * 720 * 2));
    }

    #[test]
    fn region_notification_distinct_from_oem_single_class_and_untrusted() {
        let region = ProjectedRegion2d {
            proposed_class_id: 32,
            score: 0.9,
            box_upright_xyxy: [200.0, 160.0, 280.0, 240.0],
            centroid_upright_xy: [240.0, 200.0],
            source_mask_cells: 100,
            visible_mask_cells: 100,
        };
        let sample = Sighting {
            width: 720,
            height: 1280,
            found: vec![],
            region_candidates: Some(vec![region]),
            took_ms: 25.0,
        };
        let data: serde_json::Value =
            serde_json::from_str(&notification(&sample)).unwrap();
        assert_eq!(data["method"], "media.region_candidates");
        assert_eq!(data["params"]["status"], "candidate_hypotheses");
        assert_eq!(data["params"]["source"], "mediad_tee_transport_unverified");
        assert_eq!(data["params"]["regions"][0]["proposed_class_id"], 32);
        assert_eq!(data["params"]["regions"][0]["visible_cells"], 100);
        assert_eq!(data["params"]["regions"][0]["x0"], 200.0);
        assert_eq!(data["params"]["motor_permission"], false);
        assert_eq!(data["params"]["verified_physical_presence"], false);
        assert!(data["params"].get("boxes").is_none());

        let mut invalid = sample.clone();
        invalid.region_candidates.as_mut().unwrap()[0].centroid_upright_xy[0] = f32::NAN;
        let rejected: serde_json::Value =
            serde_json::from_str(&notification(&invalid)).unwrap();
        assert_eq!(rejected["params"]["status"], "no_measurement");
        assert_eq!(rejected["params"]["regions"].as_array().unwrap().len(), 0);
    }

    #[test]
    fn successful_zero_candidates_distinct_from_error() {
        let sighting = Sighting {
            width: 720,
            height: 1280,
            found: vec![],
            region_candidates: Some(vec![]),
            took_ms: 2.0,
        };
        let data: serde_json::Value =
            serde_json::from_str(&notification(&sighting)).unwrap();
        assert_eq!(data["params"]["status"], "candidate_hypotheses");
        assert_eq!(data["params"]["regions"].as_array().unwrap().len(), 0);
    }
}
