"""P15-B4: apply opt-in local OEM metadata endpoint to an ephemeral P11 tree.

Requires the EXACT pinned OEM mediad main/lib, plus P10A/B/C already staged.
Never edits the OEM gitlink, robotd, sensors, systemd, models or Yocto.
All anchors are checked before writing any of the three files.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL, replace_once
from scripts.per_p10b_apply_oem_tail_overlay import OverlayRefused, git_hash

MAIN_BLOB = "58ce574c8ff52d35a0c1d1999553b2115c86f8ed"
LIB_BLOB = "e99c50d33a171ee14c2ed8363a4ea029ed2f75e7"
MODULE_NAME = "local_detections.rs"
ARGS_FROM = """    /// Local raw camera snapshot endpoint (not the control datachannel).
    #[arg(long, default_value = duck_ipc_proto::socket::MEDIA)]
    frame_socket: std::path::PathBuf,
}"""
ARGS_TO = """    /// Local raw camera snapshot endpoint (not the control datachannel).
    #[arg(long, default_value = duck_ipc_proto::socket::MEDIA)]
    frame_socket: std::path::PathBuf,
    /// P15-B4: optional local OEM mono detection metadata, off by default.
    /// No raw image, no motor RPC and no extra inference.
    #[arg(long, default_value_t = false)]
    kwipi_local_detections: bool,
}"""
MAIN_ANCHOR = """        // What every peer is told about the picture. The geometry is the *encoded* frame — the"""
MAIN_ADDITION = """        // P15-B4: a SECOND SUBSCRIBER to the SAME detector, no second
        // camera or inference. The private Unix endpoint is opt-in only.
        if args.kwipi_local_detections {
            if let Some(ref existing) = detector {
                match mediad::local_detections::bind_default() {
                    Ok(listener) => {
                        let sightings = existing.sightings.clone();
                        tokio::spawn(async move {
                            if let Err(error) =
                                mediad::local_detections::serve(listener, sightings).await
                            {
                                tracing::warn!(
                                    error = %error, "local detections-only endpoint stopped"
                                );
                            }
                        });
                    }
                    Err(error) => tracing::warn!(
                        error = %error, "local detections-only endpoint unavailable"
                    ),
                }
            } else {
                tracing::info!("local detections not started: OEM detector is off");
            }
        }

"""
LIB_FROM = """#[cfg(any(target_os = "linux", feature = "gstreamer"))]
pub mod frame;"""
LIB_TO = """#[cfg(any(target_os = "linux", feature = "gstreamer"))]
pub mod frame;

/// Metadata-only output from the EXISTING OEM detection broadcast.
#[cfg(any(target_os = "linux", feature = "gstreamer"))]
pub mod local_detections;"""


def apply(archive: Path, project: Path) -> None:
    archive = archive.resolve(strict=True)
    project = project.resolve(strict=True)
    marker = archive / SENTINEL
    if (not archive.is_dir() or (archive / ".git").exists()
            or marker.is_symlink() or not marker.is_file()
            or marker.read_text(encoding="utf-8").strip() != PIN):
        raise OverlayRefused("P15-B4 requires an ephemeral OEM pin-marked tree")
    main = archive / "mediad" / "src" / "main.rs"
    lib = archive / "mediad" / "src" / "lib.rs"
    detect = archive / "mediad" / "src" / "detect.rs"
    module = archive / "mediad" / "src" / MODULE_NAME
    rust = project / "scripts" / "per_p15b4_local_detections.rs"
    for path in (main, lib, detect, rust):
        if not path.is_file() or path.is_symlink():
            raise OverlayRefused("required source absent or symlinked: " + path.name)
    if module.exists() or module.is_symlink():
        raise OverlayRefused("refuse duplicate or pre-existing endpoint")
    if git_hash(main) != MAIN_BLOB or git_hash(lib) != LIB_BLOB:
        raise OverlayRefused("pinned mediad main/lib changed; re-review OEM source")
    detector = detect.read_text(encoding="utf-8")
    if ("pub region_candidates: Option" not in detector
            or "pub(crate) mod seg;" not in detector
            or detector.count("frames.next_frame()") != 1
            or detector.count("pub fn notification(sighting: &Sighting)") != 1):
        raise OverlayRefused("P11/P10C detector contract not present")
    if "region_candidates: None" not in rust.read_text(encoding="utf-8"):
        raise OverlayRefused("Rust test fixture not aligned with P10C")
    current_main = main.read_text(encoding="utf-8")
    current_lib = lib.read_text(encoding="utf-8")
    # Apply strict transformations fully in RAM before touching any source.
    next_main = replace_once(current_main, ARGS_FROM, ARGS_TO)
    next_main = replace_once(next_main, MAIN_ANCHOR, MAIN_ADDITION + MAIN_ANCHOR)
    next_lib = replace_once(current_lib, LIB_FROM, LIB_TO)
    if "robot.move" in MAIN_ADDITION or "media.frame" in MAIN_ADDITION:
        raise OverlayRefused("unapproved local endpoint payload")
    # All gates have passed. Touch only three files inside throwaway archive.
    main.write_text(next_main, encoding="utf-8")
    lib.write_text(next_lib, encoding="utf-8")
    shutil.copyfile(rust, module)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    try:
        apply(args.archive, args.project)
    except (OSError, ValueError, shutil.Error) as exc:
        parser.exit(1, f"P15-B4 STOP: {exc}\n")
    print("P15-B4 local metadata endpoint staged only in a temporary OEM source tree")


if __name__ == "__main__":
    main()
