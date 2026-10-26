"""R2-B+1: prepare *locally licensed* DCASE2020 ToyADMOS IND WAVs.

A source is one published physical toy-machine ID, not an acoustic category.
Each original WAV is a separate start-to-stop operating clip, not an
independently proven date/session. This tool never downloads media, writes
inside the Git repository, trains a model, or accesses the robot.

Output is consumed by the EXISTING r2b_independent_capture_eval.py runner.
All audio and provenance stay in an explicit private directory off-repo.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import wave

from .r2b_independent_capture_eval import R2BEvidenceError, _audio_manifest

DATASET_DOI = "https://doi.org/10.5281/zenodo.3678171"
LICENSE = "CC BY-NC-SA 4.0"
# DCASE 2020 uses ToyADMOS IND: each clip covers one start-to-stop operation.
# Machine IDs are separate individuals within their *own* machine type.
FAMILIES = (("ToyCar", "car", "validation"),
            ("ToyConveyor", "conv", "test_known"))
ORIGINAL_RE = re.compile(r"normal_id_(\d{2})_(\d{8})\.wav\Z", re.ASCII)
SAMPLES = 16_000
MAX_INPUT_BYTES = 1_000_000


def _is_inside(child: Path, directory: Path) -> bool:
    return child == directory or directory in child.parents


def _private_path(path: Path, project: Path) -> Path:
    if not isinstance(path, Path) or path.is_symlink():
        raise R2BEvidenceError("private non-symlink path required")
    resolved = path.resolve()
    if _is_inside(resolved, project):
        raise R2BEvidenceError("WAV/manifest must be outside Git checkout")
    return resolved


def _recording_paths(directory: Path) -> dict[str, Path]:
    if not directory.is_dir() or directory.is_symlink():
        raise R2BEvidenceError("extracted DCASE source directory required")
    by_id: dict[str, Path] = {}
    for file in sorted(directory.iterdir()):
        match = ORIGINAL_RE.fullmatch(file.name)
        if match and match[1] not in by_id:
            if (file.is_symlink() or not file.is_file()
                    or not 1 <= file.stat().st_size <= MAX_INPUT_BYTES):
                raise R2BEvidenceError("invalid or linked original recording")
            by_id[match[1]] = file
    return by_id


def _center_wav(path: Path) -> tuple[bytes, str]:
    # Hash the complete original and make one fixed one-second crop; never
    # choose a favorable crop using the (frozen) evaluation labels.
    if (path.is_symlink() or not path.is_file()
            or not 1 <= path.stat().st_size <= MAX_INPUT_BYTES):
        raise R2BEvidenceError("unsafe or missing DCASE WAV")
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            h.update(chunk)
    try:
        with wave.open(str(path), "rb") as audio:
            if (audio.getnchannels() != 1 or audio.getsampwidth() != 2
                    or audio.getframerate() != SAMPLES
                    or audio.getcomptype() != "NONE"
                    or not 6 * SAMPLES <= audio.getnframes() <= 15 * SAMPLES):
                raise R2BEvidenceError("DCASE WAV needs 16kHz mono PCM16 6-15 s")
            start = (audio.getnframes() - SAMPLES) // 2
            audio.setpos(start)
            raw = audio.readframes(SAMPLES)
    except (wave.Error, EOFError, OSError) as exc:
        raise R2BEvidenceError("invalid source WAV") from exc
    if len(raw) != 2 * SAMPLES:
        raise R2BEvidenceError("truncated original WAV")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLES)
        out.writeframes(raw)
    return buffer.getvalue(), h.hexdigest()


def _selection(base: Path):
    items = []
    provenance = []
    original_hashes: set[str] = set()
    crop_hashes: set[str] = set()
    for family, prefix, known_split in FAMILIES:
        folder = base / family
        if folder.is_symlink() or not folder.is_dir():
            raise R2BEvidenceError("ToyADMOS family missing or symlinked")
        train = _recording_paths(folder / "train")
        test = _recording_paths(folder / "test")
        common = sorted(set(train).intersection(test))
        if len(common) < 3:
            raise R2BEvidenceError(
                "at least 3 distinct machine IDs with train/test WAV required")
        # Two enrolled individuals and an unseen third individual *of the
        # SAME TYPE* ensure that unknown detection isn't only type detection.
        for index, machine_id in enumerate(common[:3]):
            split = known_split if index < 2 else (
                "validation_unknown" if known_split == "validation"
                else "test_unknown")
            selected = (("reference", train[machine_id]), ("query", test[machine_id])) \
                if index < 2 else (("query", test[machine_id]),)
            for role, original in selected:
                crop, original_hash = _center_wav(original)
                digest = hashlib.sha256(crop).hexdigest()
                if original_hash in original_hashes or digest in crop_hashes:
                    raise R2BEvidenceError("duplicate original WAV or 1s crop")
                original_hashes.add(original_hash)
                crop_hashes.add(digest)
                part = "tr" if role == "reference" else "te"
                match = ORIGINAL_RE.fullmatch(original.name)
                if match is None:
                    raise R2BEvidenceError("unexpected original name")
                clip = match[2]
                token = f"{prefix}{machine_id}{part}{clip}"
                name = f"{prefix}{machine_id}-{role}.wav"
                items.append((name, crop, {
                    "file": name, "source_id": f"s-{prefix}{machine_id}",
                    # Logical recording-file IDs, NOT evidence of distinct days.
                    "session_id": f"t-{token}", "take_id": f"t-{token}",
                    "split": split, "role": role, "sha256": digest,
                }))
                provenance.append({
                    "derived_file": name, "original_machine_type": family,
                    "original_machine_id": machine_id,
                    "original_partition": part,
                    "original_filename": original.name,
                    "original_sha256": original_hash,
                    "derived_sha256": digest,
                    "fixed_crop": "middle_second",
                })
    manifest = {
        "schema_version": 1, "rights_basis": "locally_reviewed_license",
        "source_evidence": "independent_takes_reviewed_locally",
        "recordings": [entry for _, _, entry in items],
    }
    _audio_manifest(json.dumps(manifest, sort_keys=True).encode("utf-8"))
    return items, provenance, manifest


def prepare(
    dataset_root: Path, media_root: Path, manifest_path: Path, *,
    reviewed_noncommercial_rights: bool = False,
    reviewed_individual_operations: bool = False,
) -> dict:
    if reviewed_noncommercial_rights is not True or reviewed_individual_operations is not True:
        raise R2BEvidenceError("explicit license and independent-operations review required")
    project = Path(__file__).resolve().parents[1]
    original = _private_path(dataset_root, project)
    dest = _private_path(media_root, project)
    manifest_file = _private_path(manifest_path, project)
    if (not original.is_dir() or original.is_symlink()
            or (original / "dev_data").is_symlink()
            or not (original / "dev_data").is_dir()):
        raise R2BEvidenceError("extracted DCASE2020 dev_data required")
    if (dest.exists() or manifest_file.exists()
            or not dest.parent.is_dir()
            or not manifest_file.parent.is_dir()
            or _is_inside(manifest_file, dest)
            or _is_inside(dest, original)
            or _is_inside(original, dest)):
        raise R2BEvidenceError("fresh private output directory and manifest required")
    items, provenance, manifest = _selection(original / "dev_data")
    # All source files, licences, hashes and split constraints are validated
    # BEFORE creating the output directory; a failed preflight writes nothing.
    dest.mkdir(mode=0o700)
    created: list[Path] = []
    try:
        for name, raw, _ in items:
            output = dest / name
            with output.open("xb") as fp:
                fp.write(raw)
            output.chmod(0o600)
            created.append(output)
        lineage = {
            "dataset": DATASET_DOI, "license": LICENSE,
            "rights_and_operation_independence": "user_reviewed_not_authenticated",
            "independent_original_recordings": True,
            "distinct_dates_or_capture_sessions_verified": False,
            "onboard_robot_results": False,
            "no_media_committed": True,
            "source_files": provenance,
        }
        audit = dest / "provenance-local.json"
        with audit.open("x", encoding="utf-8") as fp:
            json.dump(lineage, fp, indent=2, sort_keys=True)
        audit.chmod(0o600)
        created.append(audit)
        with manifest_file.open("x", encoding="utf-8") as fp:
            json.dump(manifest, fp, indent=2, sort_keys=True)
        manifest_file.chmod(0o600)
    except BaseException:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        dest.rmdir()
        raise
    return {
        "status": "preprocessed_not_evaluated",
        "derived_wav_files": len(items),
        "family_count": len(FAMILIES),
        "license": LICENSE,
        "independent_original_files": "reviewed_but_not_audited_by_software",
        "independent_dates_or_recording_sessions": False,
        "real_audio_recognition_measured": False,
        "robot_validated": False,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--audio-root", type=Path, required=True)
    parser.add_argument("--audio-manifest", type=Path, required=True)
    parser.add_argument("--noncommercial-license-reviewed", action="store_true")
    parser.add_argument("--independent-operations-reviewed", action="store_true")
    args = parser.parse_args(argv)
    result = prepare(
        args.dataset_root, args.audio_root, args.audio_manifest,
        reviewed_noncommercial_rights=args.noncommercial_license_reviewed,
        reviewed_individual_operations=args.independent_operations_reviewed)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
