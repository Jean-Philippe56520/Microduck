"""P15-B12: carry capture-clock provenance through ONE OEM mediad detector.

Apply strictly to a temporary pinned OEM source AFTER P10A/B/C+B4+B8.
Timestamps are sampled at the GStreamer appsink callback (not sensor exposure).
No new camera, inference, daemon, model, account, motor or SQLite writer.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL
from scripts.per_p10b_apply_oem_tail_overlay import OverlayRefused

SIGHTING_FIELDS = """    /// Time sampled by the appsink handling the analyzed frame, not sensor exposure.
    pub captured_at_monotonic_ns: Option<u64>,
    pub captured_at_unix_us: Option<u64>,
    /// Successful inferences in this worker lifetime; NOT the camera's frame counter.
    pub look_seq: Option<u64>,
"""
SIGHTING_NONE = (
    "            captured_at_monotonic_ns: None,\n"
    "            captured_at_unix_us: None,\n"
    "            look_seq: None,\n"
)

LOCAL_SERIALIZER = r'''    let (Some(capture_ns), Some(capture_us), Some(look_seq)) = (
        sighting.captured_at_monotonic_ns,
        sighting.captured_at_unix_us,
        sighting.look_seq,
    ) else {
        return None;
    };
    if capture_ns == 0 || capture_us == 0 || look_seq == 0
        || capture_ns > now_ns
        || now_ns - capture_ns > MAX_CAPTURE_AGE_NS
    {
        return None;
    }
    let original = detect::notification(sighting); // OEM WebRTC serializer unchanged
    if !original.starts_with(r#"{"jsonrpc":"2.0","method":"media.detections","params":{"#)
        || original.contains('\n')
    {
        return None;
    }
    let mut value: serde_json::Value = serde_json::from_str(&original).ok()?;
    let params = value.get_mut("params")?.as_object_mut()?;
    for (name, number) in [
        ("captured_at_monotonic_ns", capture_ns),
        ("captured_at_unix_us", capture_us),
        ("look_seq", look_seq),
    ] {
        if params.insert(name.to_owned(), serde_json::json!(number)).is_some() {
            return None;
        }
    }
    let wire = serde_json::to_string(&value).ok()?;
    if wire.len() + 1 > MAX_LINE_BYTES || wire.contains('\n') {
        return None;
    }
    Some(format!("{wire}\n"))'''

LOCAL_TESTS = r'''    #[test]
    fn capture_provenance_is_bounded_and_not_motor_permission() {
        let mut s = sighting();
        let stamp = s.captured_at_monotonic_ns.unwrap();
        let packet: serde_json::Value =
            serde_json::from_str(&notification_at(&s, stamp + 10).unwrap()).unwrap();
        assert_eq!(packet["params"]["captured_at_monotonic_ns"], stamp);
        assert_eq!(packet["params"]["captured_at_unix_us"], 1_700_000_000_000_000_u64);
        assert_eq!(packet["params"]["look_seq"], 1);
        assert!(packet["params"].get("motor_permission").is_none());
        assert!(packet["params"].get("category").is_none());
        assert!(notification_at(&s, stamp + MAX_CAPTURE_AGE_NS).is_some());
        assert!(notification_at(&s, stamp + MAX_CAPTURE_AGE_NS + 1).is_none());
        assert!(notification_at(&s, stamp - 1).is_none());
        s.captured_at_monotonic_ns = None;
        assert!(notification_at(&s, stamp).is_none());
        s = sighting();
        s.captured_at_unix_us = None;
        assert!(notification_at(&s, stamp + 10).is_none());
        s = sighting();
        s.look_seq = Some(0);
        assert!(notification_at(&s, stamp + 10).is_none());
    }

    #[tokio::test]
    async fn duplicate_and_regressing_look_sequences_are_silent() {
        let (_tmp, path) = private_path();
        let listener = bind(&path).unwrap();
        let (tx, _guard) = broadcast::channel(8);
        let stream = UnixStream::connect(&path).await.unwrap();
        let (server, _) = listener.accept().await.unwrap();
        let task = tokio::spawn(serve_client(server, tx.subscribe()));
        let mut reader = BufReader::new(stream);
        let mut sample = sighting();
        sample.look_seq = Some(3);
        tx.send(Arc::new(sample.clone())).unwrap();
        let mut first = String::new();
        assert!(timeout(Duration::from_secs(1), reader.read_line(&mut first))
            .await.unwrap().unwrap() > 0);
        tx.send(Arc::new(sample.clone())).unwrap();
        sample.look_seq = Some(2);
        tx.send(Arc::new(sample.clone())).unwrap();
        let mut blocked = String::new();
        assert!(timeout(Duration::from_millis(75), reader.read_line(&mut blocked)).await.is_err());
        sample.look_seq = Some(4);
        tx.send(Arc::new(sample)).unwrap();
        assert!(timeout(Duration::from_secs(1), reader.read_line(&mut blocked))
            .await.unwrap().unwrap() > 0);
        drop(reader);
        task.await.unwrap().unwrap();
    }
'''

PATCHES: dict[str, tuple[tuple[str, str], ...]] = {
    "mediad/src/pipeline.rs": (
        (
            "    pub captured_at: SystemTime,\n    /// Tightly packed",
            "    pub captured_at: SystemTime,\n"
            "    /// Monotonic appsink callback time, not sensor-exposure time.\n"
            "    pub captured_at_monotonic_ns: u64,\n"
            "    /// Tightly packed",
        ),
        (
            "                    captured_at: SystemTime::now(),\n                    data:",
            "                    captured_at: SystemTime::now(),\n"
            "                    captured_at_monotonic_ns: proto::clock::monotonic_ns(),\n"
            "                    data:",
        ),
        (
            "            captured_at: SystemTime::UNIX_EPOCH + std::time::Duration::from_secs(tag as u64),\n            data:",
            "            captured_at: SystemTime::UNIX_EPOCH + std::time::Duration::from_secs(tag as u64),\n"
            "            captured_at_monotonic_ns: 1,\n            data:",
        ),
    ),
    "mediad/src/frame.rs": (
        (
            "                captured_at: UNIX_EPOCH,\n                data:",
            "                captured_at: UNIX_EPOCH,\n                captured_at_monotonic_ns: 1,\n                data:",
        ),
        (
            "                captured_at: UNIX_EPOCH + Duration::from_secs(1),\n                data:",
            "                captured_at: UNIX_EPOCH + Duration::from_secs(1),\n"
            "                captured_at_monotonic_ns: 1,\n                data:",
        ),
    ),
    "mediad/src/exposure.rs": (
        (
            "            captured_at: std::time::SystemTime::UNIX_EPOCH,\n            data,",
            "            captured_at: std::time::SystemTime::UNIX_EPOCH,\n"
            "            captured_at_monotonic_ns: 1,\n            data,",
        ),
    ),
    "mediad/src/detect.rs": (
        (
            "    pub region_candidates: Option<Vec<duck_detect::seg_tail::ProjectedRegion2d>>,\n    /// Inference",
            "    pub region_candidates: Option<Vec<duck_detect::seg_tail::ProjectedRegion2d>>,\n"
            + SIGHTING_FIELDS + "    /// Inference",
        ),
        (
            "            region_candidates: None,\n            took_ms: 0.0,\n        })",
            "            region_candidates: None,\n" + SIGHTING_NONE
            + "            took_ms: 0.0,\n        })",
        ),
        (
            "                if frame.format != crate::pipeline::CAPTURE_FORMAT {",
            "                // Both stamps belong to the SAME frame used for inference.\n"
            "                let capture_monotonic_ns = frame.captured_at_monotonic_ns;\n"
            "                let capture_unix_us = frame.captured_at\n"
            "                    .duration_since(std::time::UNIX_EPOCH).ok()\n"
            "                    .and_then(|d| u64::try_from(d.as_micros()).ok());\n"
            "                if frame.format != crate::pipeline::CAPTURE_FORMAT {",
        ),
        (
            "                        looks.fetch_add(1, Ordering::Relaxed);",
            "                        let look_seq = looks.fetch_add(1, Ordering::Relaxed) + 1;",
        ),
        (
            "                        sighting.took_ms = started.elapsed().as_secs_f64() * 1e3;\n                        took_ms = sighting.took_ms;",
            "                        sighting.took_ms = started.elapsed().as_secs_f64() * 1e3;\n"
            "                        sighting.captured_at_monotonic_ns = Some(capture_monotonic_ns);\n"
            "                        sighting.captured_at_unix_us = capture_unix_us;\n"
            "                        sighting.look_seq = Some(look_seq);\n"
            "                        took_ms = sighting.took_ms;",
        ),
        (
            "            region_candidates: None,\n            took_ms: 63.55,",
            "            region_candidates: None,\n" + SIGHTING_NONE
            + "            took_ms: 63.55,",
        ),
        (
            "            region_candidates: None,\n            took_ms: 60.0,",
            "            region_candidates: None,\n" + SIGHTING_NONE
            + "            took_ms: 60.0,",
        ),
    ),
    "mediad/src/detect/seg.rs": (
        (
            "        region_candidates: Some(regions),\n        took_ms: 0.0,",
            "        region_candidates: Some(regions),\n" + SIGHTING_NONE
            + "        took_ms: 0.0,",
        ),
        (
            "            region_candidates: Some(vec![region]),\n            took_ms: 25.0,",
            "            region_candidates: Some(vec![region]),\n" + SIGHTING_NONE
            + "            took_ms: 25.0,",
        ),
        (
            "            region_candidates: Some(vec![]),\n            took_ms: 2.0,",
            "            region_candidates: Some(vec![]),\n" + SIGHTING_NONE
            + "            took_ms: 2.0,",
        ),
    ),
    "mediad/src/local_detections.rs": (
        (
            "const MAX_SCORE: f32 = 100.0;",
            "const MAX_SCORE: f32 = 100.0;\n"
            "// Host-policy bound, NOT a measured RK3566 guarantee. Old/future => silence.\n"
            "const MAX_CAPTURE_AGE_NS: u64 = 2_000_000_000;",
        ),
        (
            "fn notification(sighting: &Sighting) -> Option<String> {\n",
            "fn notification_at(sighting: &Sighting, now_ns: u64) -> Option<String> {\n",
        ),
        (
            '    let wire = detect::notification(sighting); // same OEM WebRTC serializer\n'
            '    if !wire.starts_with(r#"{"jsonrpc":"2.0","method":"media.detections","params":{"#)\n'
            "        || wire.len() + 1 > MAX_LINE_BYTES\n"
            "        || wire.contains('\\n')\n"
            "    {\n"
            "        return None;\n"
            "    }\n"
            '    Some(format!("{wire}\\n"))',
            LOCAL_SERIALIZER,
        ),
        (
            "/// Any inbound byte, including a purported RPC, closes the client.",
            "fn notification(sighting: &Sighting) -> Option<String> {\n"
            "    notification_at(sighting, duck_ipc_proto::clock::monotonic_ns())\n"
            "}\n\n"
            "/// Any inbound byte, including a purported RPC, closes the client.",
        ),
        (
            "    let mut inbound = [0_u8; 1];",
            "    let mut inbound = [0_u8; 1];\n    let mut last_seq = 0_u64;",
        ),
        (
            "                Ok(sighting) => {\n                    let Some(line) = notification(&sighting) else {\n                        continue;\n                    };",
            "                Ok(sighting) => {\n"
            "                    let Some(seq) = sighting.look_seq else { continue; };\n"
            "                    if seq <= last_seq { continue; }\n"
            "                    let Some(line) = notification(&sighting) else {\n"
            "                        continue;\n"
            "                    };\n"
            "                    last_seq = seq;",
        ),
        (
            "            region_candidates: None, // existing P10C/P11 segment-aware OEM source\n            took_ms: 63.5,",
            "            region_candidates: None, // existing P10C/P11 segment-aware OEM source\n"
            "            captured_at_monotonic_ns: Some(duck_ipc_proto::clock::monotonic_ns()),\n"
            "            captured_at_unix_us: Some(1_700_000_000_000_000),\n"
            "            look_seq: Some(1),\n"
            "            took_ms: 63.5,",
        ),
        (
            "    #[tokio::test]\n    async fn unix_mode_is_owner_only_and_existing_paths_are_refused()",
            LOCAL_TESTS + "    #[tokio::test]\n    async fn unix_mode_is_owner_only_and_existing_paths_are_refused()",
        ),
    ),
}


def substitute(text: str, pairs: tuple[tuple[str, str], ...]) -> str:
    for old, _ in pairs:
        if text.count(old) != 1:
            raise OverlayRefused("P15-B12 source anchor missing or duplicate: " + old[:56])
    updated = text
    for old, new in pairs:
        updated = updated.replace(old, new, 1)
    return updated


def apply(archive: Path, project: Path) -> None:
    if not archive.is_absolute() or not project.is_absolute():
        raise OverlayRefused("P15-B12 requires absolute paths")
    archive = archive.resolve(strict=True)
    project = project.resolve(strict=True)
    marker = archive / SENTINEL
    if (not archive.is_dir() or (archive / ".git").exists()
            or marker.is_symlink() or not marker.is_file()
            or marker.read_text(encoding="utf-8").strip() != PIN):
        raise OverlayRefused("P15-B12 requires marked temporary pinned OEM source")
    changed = {}
    for rel, pairs in PATCHES.items():
        path = archive / rel
        if path.is_symlink() or not path.is_file():
            raise OverlayRefused("missing/non-regular OEM source: " + rel)
        changed[path] = substitute(path.read_text(encoding="utf-8"), pairs)
    # Atomic preflight: no staged file was written before every anchor passed.
    for path, text in changed.items():
        path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        apply(args.archive, args.project)
    except (OverlayRefused, ValueError, OSError) as exc:
        parser.exit(1, f"P15-B12 STOP: {exc}\n")
    print("P15-B12: OEM mediad appsink capture provenance staged in source only.")


if __name__ == "__main__":
    main()
