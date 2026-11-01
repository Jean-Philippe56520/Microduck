"""P11: reproducible SOURCE candidate from the exact OEM pin plus P10A/B/C.

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
from scripts.per_p15b4_apply_oem_local_detections import apply as apply_b4
from scripts.per_p15b8_apply_oem_acl_binder import apply as apply_b8

RL_PIN = "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3"
ARCHIVE_NAME = "kwipi-v1-oem-source.tar.gz"
MANIFEST_NAME = "kwipi-source-manifest.json"
SOURCE_STATUS = "source_candidate_only_bitbake_licence_and_robot_blocked"
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


LOCAL_SOURCE_FILES = (
    "mediad/src/main.rs", "mediad/src/lib.rs",
    "mediad/src/local_detections.rs", "mediad/src/local_detections_acl.rs",
)


def local_detections_profile(files: dict[str, bytes]) -> bool:
    """Audit P15-B4/B8 source *presence*, not runtime or sensor provenance.

    Fail closed on half patches, a missing opt-in default or an unexpected
    source profile. No caller may infer that a board is running this code.
    """
    main = files.get(LOCAL_SOURCE_FILES[0], b"").decode("utf-8")
    lib = files.get(LOCAL_SOURCE_FILES[1], b"").decode("utf-8")
    local = files.get(LOCAL_SOURCE_FILES[2])
    acl = files.get(LOCAL_SOURCE_FILES[3])
    if (local is None) != (acl is None):
        raise ReleaseRefused("partial P15-B4/B8 OEM source profile")
    active = local is not None
    if not active:
        if ("kwipi_local_detections: bool" in main
                or "pub mod local_detections;" in lib):
            raise ReleaseRefused("P15-B4 option present without the exact B8 helper")
        return False
    body = local.decode("utf-8")
    policy = acl.decode("utf-8")
    if (main.count("kwipi_local_detections: bool") != 1
            or main.count("if args.kwipi_local_detections") != 1
            or not 'default_value_t = false' in main
            or lib.count("pub mod local_detections;") != 1
            or 'include!("local_detections_acl.rs")' not in body
            or "acl_policy::observer_uid()?" not in body
            or "acl_policy::hide_private_dir_before_bind" not in body
            or "acl_policy::grant_socket(path, uid)" not in body
            or "acl_policy::grant_private_dir(parent, uid)" not in body
            or "system.posix_acl_access" not in policy
            or "getpwnam_r(" not in policy):
        raise ReleaseRefused("P15-B4/B8 source profile is incomplete or not opt-in")
    return True


def local_profile_from_source(source: Path) -> bool:
    files = {}
    for name in LOCAL_SOURCE_FILES:
        path = source / name
        if path.is_symlink():
            raise ReleaseRefused("P15 source symlink refused: " + name)
        if path.is_file():
            files[name] = path.read_bytes()
    return local_detections_profile(files)


def manifest_for(source: Path, project_sha: str) -> dict:
    profile = local_profile_from_source(source)
    return {
        "format": "kwipi-oem-source-v1", "companion_sha": project_sha,
        "oem_sha": PIN, "mujoco_sha": RL_PIN,
        "status": SOURCE_STATUS,
        "code": ("P10A_P10B_P10C_P15B4_P15B8_without_test_harness" if profile
                 else "P10A_P10B_P10C_without_test_harness"),
        "local_detections_acl_candidate": profile,
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
                or obj.get("kwipi_seg_weights_included") is not False
                or obj.get("oem_onnx_sources_preserved") is not True
                or obj.get("detector_enabled_by_default") is not False
                or obj.get("bitbake_built") is not False):
            raise ReleaseRefused("invalid source provenance and safety state")
        records = obj.get("files")
        if not isinstance(records, list) or any(not isinstance(x, dict) for x in records):
            raise ReleaseRefused("missing source hashes")
        actual = []
        for m in members:
            if m.name == MANIFEST_NAME or m.isdir():
                continue
            if m.isfile():
                content = tar.extractfile(m)
                if content is None:
                    raise ReleaseRefused("regular file has no content")
                actual.append({"path": m.name, "sha256": hashlib.sha256(content.read()).hexdigest()})
            elif m.issym():
                actual.append({"path": m.name, "link": m.linkname})
        if sorted(actual, key=lambda x: x["path"]) != records:
            raise ReleaseRefused("source content differs from provenance hashes")
        inspected = {}
        for name in LOCAL_SOURCE_FILES:
            if name not in names:
                continue
            member = tar.getmember(name)
            if not member.isfile() or member.size > 150_000:
                raise ReleaseRefused("unsafe P15 source member: " + name)
            fp = tar.extractfile(member)
            if fp is None:
                raise ReleaseRefused("unreadable P15 source member: " + name)
            inspected[name] = fp.read()
        detected = local_detections_profile(inspected)
        expected = obj.get("local_detections_acl_candidate", False)
        if type(expected) is not bool or expected != detected:
            raise ReleaseRefused("P15-B8 source profile manifest mismatch")
        code = ("P10A_P10B_P10C_P15B4_P15B8_without_test_harness" if detected
                else "P10A_P10B_P10C_without_test_harness")
        if obj.get("code") != code:
            raise ReleaseRefused("P15 source code profile marker mismatch")
        return obj


def build(project: Path, oem: Path, output_dir: Path, *, with_p15b8_source: bool = False) -> dict:
    if type(with_p15b8_source) is not bool:
        raise ReleaseRefused("P15-B8 source selection must be an explicit boolean")
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
        if with_p15b8_source:
            apply_b4(source, project)
            apply_b8(source, project)
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
            "kwipi_seg_weights_included": False, "bitbake_built": False,
            "local_detections_acl_candidate": manifest["local_detections_acl_candidate"]}


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--project", type=Path, default=Path(__file__).resolve().parent.parent)
    cli.add_argument("--oem-checkout", type=Path)
    cli.add_argument("--output-dir", type=Path)
    cli.add_argument("--verify", type=Path)
    cli.add_argument("--with-p15b8-source", action="store_true",
                     help="source-only optional OEM mediad B4/B8 ACL profile; runtime stays off")
    args = cli.parse_args()
    try:
        if args.verify:
            if args.output_dir or args.oem_checkout or args.with_p15b8_source:
                raise ReleaseRefused("verification is independent of source checkout")
            result = verify_archive(args.verify)
            print(json.dumps({"status": result["status"], "files": len(result["files"])}))
        else:
            if args.oem_checkout is None or args.output_dir is None:
                raise ReleaseRefused("building requires OEM checkout and an unused output directory")
            print(json.dumps(build(args.project, args.oem_checkout, args.output_dir,
                with_p15b8_source=args.with_p15b8_source), sort_keys=True))
    except (ReleaseRefused, OSError, subprocess.CalledProcessError, tarfile.TarError,
            ValueError) as error:
        cli.exit(1, f"PER-P11 STOP: {error}\n")


if __name__ == "__main__":
    main()