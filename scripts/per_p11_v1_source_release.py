"""P11: reproducible OEM source candidate with P10A/B/C and P15-B4/B8.

Not an installer, Yocto BitBake image, signed updater release or licensed model.
Read-only on both Git checkouts; every modification occurs in a scratch archive.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import posixpath
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile

from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL, apply as apply_a, replace_once
from scripts.per_p10b_apply_oem_tail_overlay import apply as apply_b
from scripts.per_p10c_apply_oem_mediad_overlay import apply as apply_c
from scripts.per_p15b4_apply_oem_local_detections import (
    ARGS_TO as B4_ARGS_TO, LIB_TO as B4_LIB_TO,
    MAIN_ADDITION as B4_MAIN_ADDITION, apply as apply_b4,
)
from scripts.per_p15b8_apply_oem_acl_binder import (
    DEFAULT_TO as B8_DEFAULT_TO, MODULE_INSERT as B8_MODULE_INSERT,
    RETURN_TO as B8_RETURN_TO, SOCKET_TO as B8_SOCKET_TO,
    apply as apply_b8,
)
from scripts.per_p15b12_apply_oem_capture_provenance import apply as apply_capture

RL_PIN = "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3"
ARCHIVE_NAME = "kwipi-v1-oem-source.tar.gz"
MANIFEST_NAME = "kwipi-source-manifest.json"
SOURCE_STATUS = "source_candidate_only_bitbake_licence_and_robot_blocked"
SOURCE_COMPOSITION = "P10A_P10B_P10C_P15B4_P15B8_P15B12_without_test_harness"
LOCAL_REQUIRED_PATHS = (
    "mediad/src/main.rs",
    "mediad/src/lib.rs",
    "mediad/src/detect.rs",
    "mediad/src/local_detections.rs",
    "mediad/src/local_detections_acl.rs",
    "robotd-params/src/lib.rs",
    "mediad/src/pipeline.rs",
    "mediad/src/detect/seg.rs",
)
MODEL_SUFFIXES = {".rknn", ".onnx", ".pt", ".safetensors"}
# These ONNX inputs are already tracked in the pinned OEM git tree; preserve,
# rather than misclassifying them as new Kwipi weights.
OEM_ONNX_PATHS = {
    "duck-control/models/pickup_detector.onnx",
    "pet-detect/models/pet_detect.onnx",
    *(f"duck-control/tests/fixtures/{name}.onnx" for name in (
        "bad_action_count", "bad_batch", "bad_rank", "bad_state_shape",
        "bad_width", "dynamic_batch", "dynamic_hidden", "extra_input",
        "feedforward", "lstm", "lstm_changed", "missing_state", "nan_state",
        "wrong_type")),
}


class ReleaseRefused(ValueError):
    """Fail closed if source provenance or emitted payload is inconsistent."""


def git(path: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(path), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def check_revisions(project: Path, oem: Path) -> str:
    project_sha = git(project, "rev-parse", "HEAD")
    if len(project_sha) != 40 or git(oem, "rev-parse", "HEAD") != PIN:
        raise ReleaseRefused("checkout is not the pinned OEM source")
    if git(project, "rev-parse", "HEAD:upstream/microduck") != PIN:
        raise ReleaseRefused("Companion OEM gitlink differs from the audited pin")
    if git(project, "rev-parse", "HEAD:upstream/microduck_rl") != RL_PIN:
        raise ReleaseRefused("Companion MuJoCo gitlink differs from the audited pin")
    if git(project, "status", "--porcelain", "--untracked-files=no"):
        raise ReleaseRefused("Companion tracked working tree or gitlinks changed")
    if git(oem, "status", "--porcelain", "--untracked-files=no"):
        raise ReleaseRefused("OEM checkout has tracked modifications")
    return project_sha


def extract_pin(oem: Path, source: Path, scratch: Path) -> None:
    raw = scratch / "oem-pin.tar"
    with raw.open("wb") as fp:
        subprocess.run(["git", "-C", str(oem), "archive", "--format=tar", PIN],
                       check=True, stdout=fp)
    with tarfile.open(raw, "r:") as tar:
        for member in tar.getmembers():
            safe_member(member.name)
        tar.extractall(source, filter="data")
    (source / SENTINEL).write_text(PIN + "\n", encoding="utf-8")


def drop_test_harness(source: Path, project: Path) -> None:
    harness = source / "p10c-harness"
    expected = {
        "Cargo.toml": (project / "scripts/per_p10c_harness.toml").read_bytes(),
        "src/lib.rs": (project / "scripts/per_p10c_harness.rs").read_bytes(),
    }
    actual = {str(p.relative_to(harness)) for p in harness.rglob("*") if p.is_file()}
    if actual != set(expected) or any(p.is_symlink() for p in harness.rglob("*")):
        raise ReleaseRefused("unexpected harness contents in production candidate")
    if any((harness / rel).read_bytes() != content for rel, content in expected.items()):
        raise ReleaseRefused("test harness differs from the reviewed source")
    cargo = source / "Cargo.toml"
    original = cargo.read_text(encoding="utf-8")
    cargo.write_text(replace_once(original,
        '"uyvy", "xtask", "p10c-harness"]\n\n# Everything except',
        '"uyvy", "xtask"]\n\n# Everything except'), encoding="utf-8")
    shutil.rmtree(harness)
    marker = source / SENTINEL
    if marker.read_text(encoding="utf-8").strip() != PIN or marker.is_symlink():
        raise ReleaseRefused("invalid ephemeral marker")
    marker.unlink()


def normalize_lockfile(source: Path) -> None:
    # Cargo resolves the new local dependency once against the existing lockfile.
    # It MUST stay locked afterwards; Yocto's frozen build cannot repair this.
    manifest = str(source / "Cargo.toml")
    subprocess.run(["cargo", "metadata", "--manifest-path", manifest,
                    "--format-version", "1"], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["cargo", "metadata", "--manifest-path", manifest,
                    "--format-version", "1", "--locked"], check=True,
                   stdout=subprocess.DEVNULL)


def require_local_detection_contract(parts: dict[str, bytes]) -> None:
    """Reject absent/widened B4+B8 endpoint in a source tree OR archive.

    These markers are safety invariants, not evidence of an OEM runtime or ACL
    installed on a robot. The real exported Rust source is compiled in P11 CI.
    """
    if set(parts) != set(LOCAL_REQUIRED_PATHS):
        raise ReleaseRefused("P15-B4/B8 source files missing or unexpected")
    try:
        main, lib, detect, local, acl, params, pipeline, seg = (
            parts[name].decode("utf-8") for name in LOCAL_REQUIRED_PATHS
        )
    except UnicodeDecodeError as error:
        raise ReleaseRefused("P15-B4/B8 source is not UTF-8") from error

    required = (
        (main, B4_ARGS_TO),
        (main, B4_MAIN_ADDITION),
        (lib, B4_LIB_TO),
        (local, B8_MODULE_INSERT),
        (local, B8_DEFAULT_TO),
        (local, B8_SOCKET_TO),
        (local, B8_RETURN_TO),
        (local, "const MAX_CLIENTS: usize = 2;"),
        (local, "const MAX_LINE_BYTES: usize = 4096;"),
        (detect, "pub region_candidates: Option"),
        (detect, "pub captured_at_monotonic_ns: Option<u64>"),
        (detect, "pub captured_at_unix_us: Option<u64>"),
        (detect, "pub look_seq: Option<u64>"),
        (detect, "sighting.captured_at_monotonic_ns = Some(capture_monotonic_ns);"),
        (detect, "sighting.captured_at_unix_us = capture_unix_us;"),
        (detect, "sighting.look_seq = Some(look_seq);"),
        (pipeline, "pub captured_at_monotonic_ns: u64"),
        (pipeline, "captured_at_monotonic_ns: proto::clock::monotonic_ns(),"),
        (local, "const MAX_CAPTURE_AGE_NS: u64 = 2_000_000_000;"),
        (local, "fn notification_at(sighting: &Sighting, now_ns: u64)"),
        (local, "if seq <= last_seq { continue; }"),
    )
    # The Rust helper legitimately mentions certain functions more than once,
    # and the OEM parameter source has several unrelated "enabled: false".
    # Exact-once is reserved for structural insertion anchors.
    present = (
        (acl, "system.posix_acl_access"),
        (acl, "getpwnam_r"),
        (acl, "lsetxattr"),
        (acl, "hide_private_dir_before_bind"),
        (acl, "grant_socket"),
        (acl, "grant_private_dir"),
        (params, "enabled: false"),
        (seg, "captured_at_monotonic_ns: None,"),
        (seg, "captured_at_unix_us: None,"),
    )
    if (any(source.count(anchor) != 1 for source, anchor in required)
            or any(anchor not in source for source, anchor in present)):
        raise ReleaseRefused("P15-B4/B8 opt-in, one-detector or strict ACL contract changed")
    if (main.count("kwipi_local_detections: bool") != 1
            or main.count("if args.kwipi_local_detections {") != 1
            or lib.count("pub mod local_detections;") != 1
            or local.count('include!("local_detections_acl.rs")') != 1
            or local.count("let listener = UnixListener::bind(path)") != 1
            or detect.count("frames.next_frame()") != 1
            or detect.count('name("duck-detect"') != 1):
        raise ReleaseRefused("P15-B4/B8 duplicated detector, endpoint or binder")
    production = local.split("#[cfg(test)]", 1)[0]
    if any(value in production for value in (
            "robot.do", "robot.move", "media.frame", "cmd_vel")):
        raise ReleaseRefused("P15-B4/B8 local endpoint contains raw camera or motor access")


def no_models_or_harness(source: Path) -> None:
    necessary = ("mediad/src/detect/seg.rs", "duck-detect/src/seg_tail.rs",
                 "duck-detect/src/rknn/segments.rs", "kwipi-seg-mask-core/src/lib.rs",
                 "Cargo.lock", "LICENSE")
    if any(not (source / p).is_file() for p in necessary):
        raise ReleaseRefused("missing P10 source or OEM legal/lockfile component")
    if (source / "p10c-harness").exists() or (source / SENTINEL).exists():
        raise ReleaseRefused("test-only harness or scratch marker would ship")
    cargo = (source / "Cargo.toml").read_text(encoding="utf-8")
    lock = (source / "Cargo.lock").read_text(encoding="utf-8")
    detect = (source / "mediad/src/detect.rs").read_text(encoding="utf-8")
    params = (source / "robotd-params/src/lib.rs").read_text(encoding="utf-8")
    if ("p10c-harness" in cargo or 'name = "p10c-harness"' in lock
            or lock.count('name = "kwipi-seg-mask-core"') != 1
            or '"kwipi-seg-mask-core",' not in lock
            or detect.count("frames.next_frame()") != 1
            or detect.count('name("duck-detect"') != 1
            or "pub(crate) mod seg;" not in detect
            or "enabled: false" not in params):
        raise ReleaseRefused("cargo, tee or OEM disabled-by-default invariant failed")
    # P15-B4/B8 must be present in the ORIGINAL exported source, not only
    # in a separate scratch prototype. No symlink is accepted for these files.
    local_parts = {}
    for rel in LOCAL_REQUIRED_PATHS:
        target = source / rel
        if not target.is_file() or target.is_symlink():
            raise ReleaseRefused("required B4/B8 OEM source absent or symlinked: " + rel)
        local_parts[rel] = target.read_bytes()
    require_local_detection_contract(local_parts)
    for p in source.rglob("*"):
        rel = p.relative_to(source)
        is_unapproved_model = p.suffix.lower() in MODEL_SUFFIXES and rel.as_posix() not in OEM_ONNX_PATHS
        if (is_unapproved_model or p.name in {".git", ".env"}
                or p.name.startswith("kwipi_seg")):
            raise ReleaseRefused(f"new model or private source not allowed: {rel}")
        if p.is_symlink():
            if not p.resolve().is_relative_to(source.resolve()):
                raise ReleaseRefused(f"escaping symlink: {rel}")
        elif not p.is_dir() and not p.is_file():
            raise ReleaseRefused(f"unsupported file: {rel}")


def safe_member(name: str) -> None:
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts
            or name.startswith("./") or "\\" in name):
        raise ReleaseRefused("unsafe archive member path")


def source_index(source: Path) -> list[dict[str, str]]:
    entries = []
    for p in sorted(source.rglob("*"), key=lambda x: x.relative_to(source).as_posix()):
        if p.is_dir() and not p.is_symlink():
            continue
        rel = p.relative_to(source).as_posix()
        safe_member(rel)
        if p.is_symlink():
            if not p.resolve().is_relative_to(source.resolve()):
                raise ReleaseRefused("unsafe source symlink")
            entries.append({"path": rel, "link": os.readlink(p)})
        elif p.is_file():
            entries.append({"path": rel, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
        else:
            raise ReleaseRefused("unsupported source type")
    return entries


def manifest_for(source: Path, project_sha: str) -> dict:
    return {
        "format": "kwipi-oem-source-v1", "companion_sha": project_sha,
        "oem_sha": PIN, "mujoco_sha": RL_PIN,
        "status": SOURCE_STATUS,
        "code": SOURCE_COMPOSITION,
        "local_detections_opt_in_only": True,
        "local_detections_installed_on_robot": False,
        "acl_validated_on_robot": False,
        "capture_timestamp_origin": "mediad_appsink_callback_not_exposure",
        "capture_provenance_validated_on_robot": False,
        "kwipi_seg_weights_included": False, "oem_onnx_sources_preserved": True,
        "detector_enabled_by_default": False,
        "bitbake_built": False, "robot_validated": False,
        "signed_ota_release": False,
        "files": source_index(source),
    }


def write_tar(source: Path, output: Path) -> None:
    with output.open("xb") as fp, gzip.GzipFile(filename="", mode="wb", fileobj=fp, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
            for p in sorted(source.rglob("*"), key=lambda x: x.relative_to(source).as_posix()):
                name = p.relative_to(source).as_posix()
                safe_member(name)
                info = tar.gettarinfo(str(p), arcname=name)
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                info.pax_headers = {}
                if info.isfile():
                    with p.open("rb") as input_file:
                        tar.addfile(info, input_file)
                else:
                    tar.addfile(info)


def verify_archive(path: Path) -> dict:
    with tarfile.open(path, "r:gz") as tar:
        members = tar.getmembers()
        names = [m.name for m in members]
        if len(names) != len(set(names)) or MANIFEST_NAME not in names:
            raise ReleaseRefused("duplicated or missing source manifest")
        for m in members:
            safe_member(m.name)
            if ((PurePosixPath(m.name).suffix.lower() in MODEL_SUFFIXES
                 and m.name not in OEM_ONNX_PATHS)
                    or m.name.startswith("p10c-harness")
                    or PurePosixPath(m.name).name.startswith("kwipi_seg")):
                raise ReleaseRefused("unapproved model or harness in source archive")
            if not (m.isfile() or m.isdir() or m.issym()):
                raise ReleaseRefused("unsupported archive member type")
            if m.issym():
                dest = PurePosixPath(m.name).parent / m.linkname
                canonical = posixpath.normpath(str(dest))
                if (dest.is_absolute() or canonical == ".." or canonical.startswith("../")):
                    raise ReleaseRefused("nonlocal symlink in source archive")
        manifest_file = tar.extractfile(MANIFEST_NAME)
        if manifest_file is None:
            raise ReleaseRefused("source manifest not regular")
        obj = json.load(manifest_file)
        if (obj.get("format") != "kwipi-oem-source-v1"
                or obj.get("status") != SOURCE_STATUS
                or obj.get("oem_sha") != PIN
                or obj.get("code") != SOURCE_COMPOSITION
                or obj.get("local_detections_opt_in_only") is not True
                or obj.get("local_detections_installed_on_robot") is not False
                or obj.get("acl_validated_on_robot") is not False
                or obj.get("capture_timestamp_origin") != "mediad_appsink_callback_not_exposure"
                or obj.get("capture_provenance_validated_on_robot") is not False
                or obj.get("kwipi_seg_weights_included") is not False
                or obj.get("oem_onnx_sources_preserved") is not True
                or obj.get("detector_enabled_by_default") is not False
                or obj.get("bitbake_built") is not False
                or obj.get("robot_validated") is not False
                or obj.get("signed_ota_release") is not False):
            raise ReleaseRefused("invalid source provenance and safety state")
        records = obj.get("files")
        if not isinstance(records, list) or any(not isinstance(x, dict) for x in records):
            raise ReleaseRefused("missing source hashes")
        actual = []
        local_parts = {}
        for m in members:
            if m.name == MANIFEST_NAME or m.isdir():
                continue
            if m.isfile():
                content = tar.extractfile(m)
                if content is None:
                    raise ReleaseRefused("regular file has no content")
                raw = content.read()
                actual.append({"path": m.name, "sha256": hashlib.sha256(raw).hexdigest()})
                if m.name in LOCAL_REQUIRED_PATHS:
                    local_parts[m.name] = raw
            elif m.issym():
                actual.append({"path": m.name, "link": m.linkname})
        if sorted(actual, key=lambda x: x["path"]) != records:
            raise ReleaseRefused("source content differs from provenance hashes")
        require_local_detection_contract(local_parts)
        return obj


def build(project: Path, oem: Path, output_dir: Path) -> dict:
    project = project.resolve(strict=True)
    oem = oem.resolve(strict=True)
    project_sha = check_revisions(project, oem)
    output_dir.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="kwipi-v1-src-") as scratch_name:
        scratch = Path(scratch_name)
        source = scratch / "src"
        source.mkdir()
        extract_pin(oem, source, scratch)
        apply_a(source, project / "scripts/per_p10a_rknn_segments.rs")
        apply_b(source, project / "scripts/per_p10b_seg_tail.rs", project)
        apply_c(source, project)
        # Both approved overlays require the temporary OEM pin marker. Apply
        # B4 before B8, then remove the test-only harness and marker.
        apply_b4(source, project)
        apply_b8(source, project)
        apply_capture(source, project)  # Same OEM worker, no new frame reader.
        drop_test_harness(source, project)
        normalize_lockfile(source)
        no_models_or_harness(source)
        manifest = manifest_for(source, project_sha)
        (source / MANIFEST_NAME).write_text(json.dumps(manifest, sort_keys=True,
                separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
        archive = output_dir / ARCHIVE_NAME
        write_tar(source, archive)
        verified = verify_archive(archive)
        if verified != manifest:
            raise ReleaseRefused("archive verification differs from source manifest")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        sidecar = {"archive_sha256": digest, "archive_name": ARCHIVE_NAME,
                   "source_manifest": manifest}
        (output_dir / "manifest.json").write_text(json.dumps(sidecar, sort_keys=True,
            indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (output_dir / (ARCHIVE_NAME + ".sha256")).write_text(
            digest + "  " + ARCHIVE_NAME + "\n", encoding="ascii")
    if git(project, "status", "--porcelain", "--untracked-files=no"):
        raise ReleaseRefused("source export unexpectedly modified Companion")
    return {"status": SOURCE_STATUS, "archive_sha256": digest,
            "files": len(manifest["files"]), "companion_sha": project_sha,
            "kwipi_seg_weights_included": False, "bitbake_built": False}


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--project", type=Path, default=Path(__file__).resolve().parent.parent)
    cli.add_argument("--oem-checkout", type=Path)
    cli.add_argument("--output-dir", type=Path)
    cli.add_argument("--verify", type=Path)
    args = cli.parse_args()
    try:
        if args.verify:
            if args.output_dir or args.oem_checkout:
                raise ReleaseRefused("verification is independent of source checkout")
            result = verify_archive(args.verify)
            print(json.dumps({"status": result["status"], "files": len(result["files"])}))
        else:
            if args.oem_checkout is None or args.output_dir is None:
                raise ReleaseRefused("building requires OEM checkout and an unused output directory")
            print(json.dumps(build(args.project, args.oem_checkout, args.output_dir), sort_keys=True))
    except (ReleaseRefused, OSError, subprocess.CalledProcessError, tarfile.TarError,
            ValueError) as error:
        cli.exit(1, f"PER-P11 STOP: {error}\n")


if __name__ == "__main__":
    main()