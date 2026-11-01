"""P15-B8: strengthen P15-B4 mediad ACL binder on an isolated OEM archive.

Adds exactly one Rust ACL helper and patches only local_detections.rs after
P10A/B/C + P15-B4 have been staged. Never edits real OEM submodules, units,
Yocto, socket permissions in /run, models, or a robot.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL
from scripts.per_p10b_apply_oem_tail_overlay import OverlayRefused
from scripts.per_p15b4_apply_oem_local_detections import ARGS_TO, MAIN_ADDITION, MODULE_NAME


HELPER_NAME = "local_detections_acl.rs"
HELPER = "per_p15b8_acl_policy.rs"
ANCHOR_MODULE = "use crate::detect::{self, Sighting};\n"
MODULE_INSERT = """use crate::detect::{self, Sighting};

// P15-B8: strict Linux access ACL on the *existing* mediad local metadata
// endpoint; no additional daemon, client, camera, inference or motor control.
mod acl_policy {
    include!("local_detections_acl.rs");
}
"""
DEFAULT_FROM = """    safe_dir(&private, true)?;
    bind(&private.join("detections.sock"))
"""
DEFAULT_TO = """    // Named local-only identity, never the broad OEM 'robot' group.
    // Opt-in mediad without a dedicated kwipi account fails closed.
    let uid = acl_policy::observer_uid()?;
    acl_policy::check_dir(&private, uid)?;
    bind_with_uid(&private.join("detections.sock"), uid)
"""
BIND_FROM = "pub fn bind(path: &Path) -> Result<UnixListener> {\n"
BIND_TO = """pub fn bind(path: &Path) -> Result<UnixListener> {
    bind_checked(path, None)
}

// Used by the OEM owner after it has selected an independent Kwipi UID.
// The numeric variant is exercised ONLY by ephemeral host Rust fixtures.
fn bind_with_uid(path: &Path, uid: u32) -> Result<UnixListener> {
    bind_checked(path, Some(uid))
}

fn bind_checked(path: &Path, observer_uid: Option<u32>) -> Result<UnixListener> {
"""
DIR_FROM = """    safe_dir(path.parent().context("missing local detections directory")?, true)?;
"""
DIR_TO = """    let parent = path.parent().context("missing local detections directory")?;
    if let Some(uid) = observer_uid {
        acl_policy::check_dir(parent, uid)?;
    } else {
        safe_dir(parent, true)?;
    }
"""
SOCKET_FROM = """    let listener = UnixListener::bind(path).context("local detections bind failed")?;
"""
SOCKET_TO = """    // The observer MUST NOT traverse this directory between bind(2) and
    // chmod(0600). On rebind, revoke our exact prior ACL before creating an
    // inode; later restore the directory grant as the VERY LAST step.
    if let Some(uid) = observer_uid {
        acl_policy::hide_private_dir_before_bind(parent, uid)?;
    }
    let listener = UnixListener::bind(path).context("local detections bind failed")?;
"""
RETURN_FROM = """        return Err(error).context("socket chmod failed");
    }
    Ok(listener)
}
"""
RETURN_TO = """        return Err(error).context("socket chmod failed");
    }
    if let Some(uid) = observer_uid {
        // Apply/read back the exact five-entry socket ACL BEFORE returning a
        // listener; caller cannot accept a connection until this succeeds.
        let result = acl_policy::grant_socket(path, uid)
            .and_then(|()| acl_policy::grant_private_dir(parent, uid));
        if let Err(error) = result {
            drop(listener);
            let _ = std::fs::remove_file(path);
            return Err(error).context("metadata socket/dir ACL grant refused");
        }
    }
    Ok(listener)
}
"""


def _one(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise OverlayRefused("expected exactly one pinned B4 anchor: " + old[:60])
    return text.replace(old, new)


def apply(archive: Path, project: Path) -> None:
    if not archive.is_absolute() or not project.is_absolute():
        raise OverlayRefused("use explicit absolute scratch and project paths")
    archive = archive.resolve(strict=True)
    project = project.resolve(strict=True)
    marker = archive / SENTINEL
    local = archive / "mediad/src" / MODULE_NAME
    helper_out = archive / "mediad/src" / HELPER_NAME
    source_b4 = project / "scripts/per_p15b4_local_detections.rs"
    source_helper = project / "scripts" / HELPER
    main = archive / "mediad/src/main.rs"
    if (not archive.is_dir() or (archive / ".git").exists()
            or marker.is_symlink() or not marker.is_file()
            or marker.read_text(encoding="utf-8").strip() != PIN
            or any(p.is_symlink() or not p.is_file() for p in
                   (local, source_b4, source_helper, main))):
        raise OverlayRefused("requires an exact pinned and already B4-staged temporary OEM tree")
    if helper_out.exists() or helper_out.is_symlink():
        raise OverlayRefused("P15-B8 already applied or unexpected helper path")
    if local.read_bytes() != source_b4.read_bytes():
        raise OverlayRefused("P15-B4 staged Rust source differs from audited original")
    existing_main = main.read_text(encoding="utf-8")
    if existing_main.count(ARGS_TO) != 1 or existing_main.count(MAIN_ADDITION) != 1:
        raise OverlayRefused("P15-B4 opt-in main.rs source contract missing")
    helper_content = source_helper.read_text(encoding="utf-8")
    if ("system.posix_acl_access" not in helper_content
            or "getpwnam_r" not in helper_content
            or "lsetxattr" not in helper_content
            or "group" not in helper_content):
        raise OverlayRefused("strict Linux ACL source helper contract missing")

    text = local.read_text(encoding="utf-8")
    for before, after in (
        (ANCHOR_MODULE, MODULE_INSERT),
        (DEFAULT_FROM, DEFAULT_TO),
        (BIND_FROM, BIND_TO),
        (DIR_FROM, DIR_TO),
        (SOCKET_FROM, SOCKET_TO),
        (RETURN_FROM, RETURN_TO),
    ):
        text = _one(text, before, after)
    # Existing B4 negative tests contain the forbidden literal "robot.move".
    # Check only the code introduced by B8, not trusted B4 test fixtures.
    insertion = MODULE_INSERT + DEFAULT_TO + BIND_TO + DIR_TO + SOCKET_TO + RETURN_TO
    if any(forbidden in insertion for forbidden in ("robot.do", "robot.move", "media.frame")):
        raise OverlayRefused("B8 injection unexpectedly introduced motor/raw-camera code")

    # All gates pass before either file is modified; touch only a scratch OEM
    # source copy. Never change robotd, mediad main/lib, gitlinks, or service.
    local.write_text(text, encoding="utf-8")
    shutil.copyfile(source_helper, helper_out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--project", type=Path,
                        default=Path(__file__).resolve().parents[1])
    opt = parser.parse_args()
    try:
        apply(opt.archive, opt.project)
    except (OSError, ValueError, shutil.Error) as exc:
        parser.exit(1, "P15-B8 STOP: " + str(exc) + "\n")
    print("P15-B8: exact strict ACL guard staged only in temporary OEM mediad tree")


if __name__ == "__main__":
    main()
