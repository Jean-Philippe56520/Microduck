//! PER-P10C HOST-ONLY compile/test wrapper for the ACTUAL mediad/src/detect.rs.
//! The only substitution is a minimal in-memory Frames interface so GStreamer
//! hardware/board is not required. No actual media stream or NPU can be used.

pub mod pipeline {
    #[derive(Clone)]
    pub struct Frame {
        pub width: u32,
        pub height: u32,
        pub format: &'static str,
        pub data: Vec<u8>,
    }

    pub const CAPTURE_FORMAT: &str = "UYVY";

    /// The real pinned OEM's mediad::detect.rs is compiled against this inert
    /// interface, but no additional frame reader or thread is started in CI.
    #[derive(Clone, Default)]
    pub struct Frames;

    impl Frames {
        pub fn next_frame(&self) -> Option<Frame> {
            None
        }
    }
}

#[allow(dead_code)]
#[path = "../../mediad/src/detect.rs"]
pub mod detect;

#[cfg(test)]
mod tests {
    use std::path::Path;

    use super::*;
    use duck_detect::seg_tail::{Tail, P10B_SHAPES};
    use uyvy::{Turn, letterbox_from_uyvy};

    fn models(name: &str) -> std::path::PathBuf {
        Path::new(
            &std::env::var("KWIPI_P10B_TEST_MODELS")
                .expect("CI must generate ONNX fixtures outside the repository"),
        )
        .join(name)
    }

    fn synthetic_heads(active_score: bool, active_prototype: bool) -> [Vec<f32>; 10] {
        std::array::from_fn(|index| {
            let elements: usize = P10B_SHAPES[index].iter().product();
            let mut result = vec![
                if index == 0 && !active_score { 0.0 } else { 1.0 };
                elements
            ];
            if index == 9 {
                result.fill(0.0);
                if active_prototype {
                    result[..160 * 160].fill(1.0);
                }
            }
            result
        })
    }

    #[test]
    fn one_uyvy_tee_letterbox_feeds_actual_rust_ort_and_p7_p9_regions() {
        let width = 1280;
        let height = 720;
        let uyvy = vec![128, 60, 128, 60]
            .into_iter()
            .cycle()
            .take(width * height * 2)
            .collect::<Vec<u8>>();
        assert!(detect::seg::complete_uyvy(
            width as u32,
            height as u32,
            uyvy.len()
        ));
        let mut rgb = Vec::new();
        let turn = Turn::Right;
        let fit = letterbox_from_uyvy(&uyvy, width, height, 640, turn, &mut rgb);
        assert_eq!(rgb.len(), 640 * 640 * 3);
        assert_eq!((fit.scale, fit.pad_x, fit.pad_y), (0.5, 140.0, 0.0));
        let (upright_w, upright_h) = turn.upright(width, height);
        assert_eq!((upright_w, upright_h), (720, 1280));

        let mut tail = Tail::open(&models("valid.onnx")).unwrap();
        let mut sighting = detect::seg::from_heads(
            &mut tail,
            synthetic_heads(true, true),
            fit,
            upright_w as u32,
            upright_h as u32,
            0.25,
        )
        .unwrap();
        assert!(sighting.found.is_empty());
        let region = &sighting.region_candidates.as_ref().unwrap()[0];
        assert_eq!(region.source_mask_cells, 100);
        assert_eq!(region.visible_mask_cells, 100);
        assert_eq!(region.box_upright_xyxy, [200.0, 160.0, 280.0, 240.0]);
        assert_eq!(region.centroid_upright_xy, [240.0, 200.0]);
        sighting.took_ms = 31.0;
        let message: serde_json::Value =
            serde_json::from_str(&detect::notification(&sighting)).unwrap();
        assert_eq!(message["method"], "media.region_candidates");
        assert_eq!(message["params"]["regions"][0]["proposed_class_id"], 32);
        assert_eq!(message["params"]["motor_permission"], false);
        assert_eq!(message["params"]["verified_physical_presence"], false);
        assert!(message["params"].get("boxes").is_none());
    }

    #[test]
    fn empty_candidates_are_distinct_from_failed_capture_or_inference() {
        let mut tail = Tail::open(&models("valid.onnx")).unwrap();
        let uyvy = vec![128, 60, 128, 60]
            .into_iter()
            .cycle()
            .take(1280 * 720 * 2)
            .collect::<Vec<u8>>();
        let mut rgb = vec![];
        let fit = letterbox_from_uyvy(&uyvy, 1280, 720, 640, Turn::Right, &mut rgb);
        let empty = detect::seg::from_heads(
            &mut tail, synthetic_heads(false, true), fit, 720, 1280, 0.25,
        )
        .unwrap();
        assert!(empty.region_candidates.as_ref().unwrap().is_empty());
        let parsed: serde_json::Value =
            serde_json::from_str(&detect::notification(&empty)).unwrap();
        assert_eq!(parsed["params"]["status"], "candidate_hypotheses");
        assert_eq!(parsed["params"]["regions"].as_array().unwrap().len(), 0);

        assert!(!detect::seg::complete_uyvy(1280, 720, uyvy.len() - 1));
        let bad = detect::seg::from_heads(
            &mut tail, synthetic_heads(true, true), fit, 720, 1280, f32::NAN,
        );
        assert!(bad.is_err());
        // The actual worker does not send a sighting for Err; no success
        // payload can be manufactured by the failed test branch.
    }

    #[test]
    fn oem_single_class_notification_remains_unchanged_and_distinct() {
        let sighting = detect::Sighting {
            width: 720,
            height: 1280,
            found: vec![duck_detect::Detection {
                score: 1.38,
                box_: [10.0, 20.0, 110.0, 220.0],
            }],
            region_candidates: None,
            took_ms: 63.55,
        };
        let line = detect::notification(&sighting);
        let value: serde_json::Value = serde_json::from_str(&line).unwrap();
        assert_eq!(value["method"], "media.detections");
        assert_eq!(value["params"]["boxes"][0]["score"], 1.38);
        assert!(value["params"].get("regions").is_none());
        assert!(line.starts_with(r#"{"jsonrpc":"2.0","method":"media.detections""#));
    }
}
