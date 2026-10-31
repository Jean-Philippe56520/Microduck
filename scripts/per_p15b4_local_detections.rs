//! P15-B4: optional, metadata-only local consumer of mediad's EXISTING detector.
//!
//! No camera grab, inference, additional model, motor RPC, network or daemon.
//! Only media.detections is forwarded; P10C media.region_candidates is refused.
//! The sensor score is not a calibrated probability. No hardware validation.
//! Owner-only socket is not a deployed permission for the separate Kwipi UID.

use std::os::unix::fs::{DirBuilderExt, MetadataExt, PermissionsExt};
use std::path::Path;
use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result, bail};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{UnixListener, UnixStream};
use tokio::sync::{Semaphore, broadcast};

use crate::detect::{self, Sighting};

const MAX_CLIENTS: usize = 2;
const MAX_BOXES: usize = 32;
const MAX_LINE_BYTES: usize = 4096;
const MAX_SIDE: u32 = 4096;
const MAX_LATENCY_MS: f64 = 5000.0;
const MAX_SCORE: f32 = 100.0;
const WRITE_TIMEOUT: Duration = Duration::from_millis(500);

pub const SOCKET: &str = "/run/mediad/kwipi/detections.sock";

fn safe_dir(parent: &Path, private: bool) -> Result<()> {
    let info = std::fs::symlink_metadata(parent).context("metadata directory unavailable")?;
    if !info.file_type().is_dir()
        || info.uid() != unsafe { libc::geteuid() }
        || (info.permissions().mode() & 0o022) != 0
        || (private && (info.permissions().mode() & 0o777) != 0o700)
    {
        bail!("unsafe metadata directory");
    }
    Ok(())
}

/// Private 0700 parent must exist BEFORE bind. /run/mediad may be 0755,
/// and chmod of a new public-parent socket after bind is not race-free.
pub fn bind_default() -> Result<UnixListener> {
    let runtime = Path::new("/run/mediad");
    safe_dir(runtime, false)?;
    let private = runtime.join("kwipi");
    match std::fs::DirBuilder::new().mode(0o700).create(&private) {
        Ok(()) => (),
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => (),
        Err(error) => return Err(error).context("cannot prepare private metadata directory"),
    }
    safe_dir(&private, true)?;
    bind(&private.join("detections.sock"))
}

/// Refuse a pre-existing path (including symlink and stale socket); never
/// remove an endpoint possibly owned by a different process.
pub fn bind(path: &Path) -> Result<UnixListener> {
    if path.file_name().is_none_or(|name| name != "detections.sock") {
        bail!("unexpected local detections socket filename");
    }
    safe_dir(path.parent().context("missing local detections directory")?, true)?;
    match std::fs::symlink_metadata(path) {
        Ok(_) => bail!("existing local detections socket refused"),
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => (),
        Err(error) => return Err(error).context("socket inspection failed"),
    }
    let listener = UnixListener::bind(path).context("local detections bind failed")?;
    if let Err(error) = std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600)) {
        drop(listener);
        let _ = std::fs::remove_file(path);
        return Err(error).context("socket chmod failed");
    }
    Ok(listener)
}

fn notification(sighting: &Sighting) -> Option<String> {
    if sighting.width == 0 || sighting.height == 0
        || sighting.width > MAX_SIDE || sighting.height > MAX_SIDE
        || !sighting.took_ms.is_finite()
        || !(0.0..=MAX_LATENCY_MS).contains(&sighting.took_ms)
        || sighting.found.len() > MAX_BOXES
    {
        return None;
    }
    for found in &sighting.found {
        let [x0, y0, x1, y1] = found.box_;
        if !found.score.is_finite()
            || !(0.0..=MAX_SCORE).contains(&found.score)
            || ![x0, y0, x1, y1].iter().all(|value| value.is_finite())
            || x0 < 0.0 || y0 < 0.0
            || x0 >= x1 || y0 >= y1
            || x1 > sighting.width as f32 || y1 > sighting.height as f32
        {
            return None;
        }
    }
    let wire = detect::notification(sighting); // same OEM WebRTC serializer
    if !wire.starts_with(r#"{"jsonrpc":"2.0","method":"media.detections","params":{"#)
        || wire.len() + 1 > MAX_LINE_BYTES
        || wire.contains('\n')
    {
        return None;
    }
    Some(format!("{wire}\n"))
}

/// Any inbound byte, including a purported RPC, closes the client. Never
/// parse requests. Lagged clients skip to new observations, not old ones.
async fn serve_client(
    stream: UnixStream,
    mut sightings: broadcast::Receiver<Arc<Sighting>>,
) -> Result<()> {
    let (mut reader, mut writer) = stream.into_split();
    let mut inbound = [0_u8; 1];
    loop {
        tokio::select! {
            incoming = reader.read(&mut inbound) => {
                let _ = incoming?;
                return Ok(());
            }
            item = sightings.recv() => match item {
                Ok(sighting) => {
                    let Some(line) = notification(&sighting) else {
                        continue;
                    };
                    tokio::time::timeout(WRITE_TIMEOUT, writer.write_all(line.as_bytes()))
                        .await.context("slow local detections reader")??;
                }
                Err(broadcast::error::RecvError::Lagged(_)) => {
                    sightings = sightings.resubscribe();
                }
                Err(broadcast::error::RecvError::Closed) => return Ok(()),
            },
        }
    }
}

/// Exactly two concurrent readers; additional clients are disconnected.
/// This never blocks the detector worker or the existing WebRTC stream.
pub async fn serve(
    listener: UnixListener,
    sightings: broadcast::Sender<Arc<Sighting>>,
) -> Result<()> {
    let slots = Arc::new(Semaphore::new(MAX_CLIENTS));
    loop {
        let (stream, _) = listener.accept().await?;
        let Ok(permit) = slots.clone().try_acquire_owned() else {
            drop(stream);
            continue;
        };
        let rx = sightings.subscribe();
        tokio::spawn(async move {
            let _permit = permit;
            let _ = serve_client(stream, rx).await;
        });
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use duck_detect::Detection;
    use tokio::io::{AsyncBufReadExt, BufReader};
    use tokio::time::timeout;

    fn sighting() -> Sighting {
        Sighting {
            width: 720,
            height: 1280,
            found: vec![Detection {
                score: 1.38,
                box_: [10.0, 20.0, 110.0, 220.0],
            }],
            region_candidates: None, // existing P10C/P11 segment-aware OEM source
            took_ms: 63.5,
        }
    }

    fn private_path() -> (tempfile::TempDir, std::path::PathBuf) {
        let tmp = tempfile::tempdir().unwrap();
        let private = tmp.path().join("private");
        std::fs::DirBuilder::new().mode(0o700).create(&private).unwrap();
        let path = private.join("detections.sock");
        (tmp, path)
    }

    #[test]
    fn one_class_notification_is_exact_oem_wire_format() {
        let line = notification(&sighting()).unwrap();
        let json: serde_json::Value = serde_json::from_str(&line).unwrap();
        assert_eq!(json["jsonrpc"], "2.0");
        assert_eq!(json["method"], "media.detections");
        assert!(json.get("id").is_none());
        assert_eq!(json["params"]["boxes"][0]["score"], 1.38);
        assert_eq!(json["params"]["width"], 720);
        assert_eq!(json["params"]["height"], 1280);
        assert_eq!(line.matches('\n').count(), 1);
        assert!(!line.contains("robot."));
        assert!(!line.contains("media.frame"));
        assert!(!line.contains("image"));
    }

    #[test]
    fn zero_candidates_does_not_claim_an_object() {
        let mut s = sighting();
        s.found.clear();
        let parsed: serde_json::Value = serde_json::from_str(&notification(&s).unwrap()).unwrap();
        assert_eq!(parsed["params"]["boxes"].as_array().unwrap().len(), 0);
    }

    #[test]
    fn segment_hypotheses_are_not_automatically_exposed_or_recognized() {
        let mut s = sighting();
        s.region_candidates = Some(vec![]);
        assert!(notification(&s).is_none()); // P10C separate method, no broadening
    }

    #[test]
    fn invalid_overbudget_nonfinite_boxes_and_latency_are_rejected() {
        let mut s = sighting();
        s.width = 0;
        assert!(notification(&s).is_none());
        s = sighting();
        s.height = 4097;
        assert!(notification(&s).is_none());
        s = sighting();
        s.took_ms = f64::NAN;
        assert!(notification(&s).is_none());
        s = sighting();
        s.took_ms = f64::INFINITY;
        assert!(notification(&s).is_none());
        s = sighting();
        s.found[0].score = f32::NAN;
        assert!(notification(&s).is_none());
        s = sighting();
        s.found[0].score = 101.0;
        assert!(notification(&s).is_none());
        s = sighting();
        s.found[0].box_[0] = 150.0;
        assert!(notification(&s).is_none());
        s = sighting();
        s.found[0].box_[2] = f32::INFINITY;
        assert!(notification(&s).is_none());
        s = sighting();
        s.found = vec![s.found[0].clone(); 33];
        assert!(notification(&s).is_none());
        s = sighting();
        s.found = vec![s.found[0].clone(); 32];
        assert!(notification(&s).is_some());
    }

    #[test]
    fn unix_mode_is_owner_only_and_existing_paths_are_refused() {
        let (_tmp, path) = private_path();
        let listener = bind(&path).unwrap();
        assert_eq!(std::fs::metadata(&path).unwrap().permissions().mode() & 0o777, 0o600);
        assert!(bind(&path).is_err());
        drop(listener);
        std::fs::remove_file(&path).unwrap();
        std::fs::write(&path, "private file").unwrap();
        assert!(bind(&path).is_err());
        std::fs::remove_file(&path).unwrap();
        std::os::unix::fs::symlink("/tmp/unrelated", &path).unwrap();
        assert!(bind(&path).is_err());
    }

    #[test]
    fn unsafe_directory_and_wrong_endpoint_name_are_refused() {
        let (_tmp, path) = private_path();
        let parent = path.parent().unwrap();
        std::fs::set_permissions(parent, std::fs::Permissions::from_mode(0o755)).unwrap();
        assert!(bind(&path).is_err());
        std::fs::set_permissions(parent, std::fs::Permissions::from_mode(0o700)).unwrap();
        assert!(bind(&parent.join("media.sock")).is_err());
    }

    #[tokio::test]
    async fn unix_reader_gets_only_new_metadata_not_replayed() {
        let (_tmp, path) = private_path();
        let listener = bind(&path).unwrap();
        let (tx, _guard) = broadcast::channel(8);
        let old_rx = tx.subscribe();
        tx.send(Arc::new(sighting())).unwrap();
        let stream = UnixStream::connect(&path).await.unwrap();
        let (server, _) = listener.accept().await.unwrap();
        let reader_task = tokio::spawn(serve_client(server, tx.subscribe()));
        let mut reader = BufReader::new(stream);
        let mut line = String::new();
        assert!(timeout(Duration::from_millis(60), reader.read_line(&mut line)).await.is_err());
        assert!(line.is_empty());
        let mut newer = sighting();
        newer.found[0].score = 0.51;
        tx.send(Arc::new(newer)).unwrap();
        assert!(timeout(Duration::from_secs(1), reader.read_line(&mut line))
            .await.unwrap().unwrap() > 0);
        let object: serde_json::Value = serde_json::from_str(&line).unwrap();
        assert_eq!(object["method"], "media.detections");
        assert_eq!(object["params"]["boxes"][0]["score"], 0.51);
        drop(reader);
        reader_task.await.unwrap().unwrap();
        drop(old_rx);
    }

    #[tokio::test]
    async fn inbound_rpc_bytes_close_connection_without_side_effect() {
        let (_tmp, path) = private_path();
        let listener = bind(&path).unwrap();
        let (tx, _rx) = broadcast::channel(8);
        let mut client = UnixStream::connect(&path).await.unwrap();
        let (server, _) = listener.accept().await.unwrap();
        let task = tokio::spawn(serve_client(server, tx.subscribe()));
        client.write_all(b"{\"method\":\"robot.move\"}\n").await.unwrap();
        timeout(Duration::from_secs(1), task).await.unwrap().unwrap().unwrap();
        let mut one = [0_u8; 1];
        assert_eq!(timeout(Duration::from_secs(1), client.read(&mut one)).await.unwrap().unwrap(), 0);
    }

    #[tokio::test]
    async fn third_client_is_rejected_without_blocking_existing_readers() {
        let (_tmp, path) = private_path();
        let listener = bind(&path).unwrap();
        let (tx, _rx) = broadcast::channel(8);
        let task = tokio::spawn(serve(listener, tx.clone()));
        let mut clients = Vec::new();
        for _ in 0..3 {
            clients.push(BufReader::new(UnixStream::connect(&path).await.unwrap()));
            tokio::task::yield_now().await;
        }
        let mut buf = String::new();
        assert_eq!(timeout(Duration::from_secs(1), clients[2].read_line(&mut buf))
            .await.unwrap().unwrap(), 0);
        tx.send(Arc::new(sighting())).unwrap();
        for client in &mut clients[..2] {
            let mut line = String::new();
            assert!(timeout(Duration::from_secs(1), client.read_line(&mut line))
                .await.unwrap().unwrap() > 0);
            assert!(line.contains("media.detections"));
        }
        task.abort();
        assert!(task.await.unwrap_err().is_cancelled());
    }
}
