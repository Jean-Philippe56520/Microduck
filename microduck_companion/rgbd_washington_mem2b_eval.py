"""MEM-2B-WA: fixed, public, host-only three-ball cross-video research.

Source and selection are frozen in docs/mem2b-wa-washington-balls-prereg-2026-11-03.md.
No SQLite, model training, motor code, media export, or camera integration.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import resource
import tarfile
import time

from .compact_multimodal_memory import image_fingerprint, MATCH_IMAGE, AMBIGUITY_GAP
from .r2b2_abo_confusables import _mem2b_policy_candidate

EXPECTED = {
    1: (5742008, "31fa833e059bf248acd1f3cdd8e0da5769bfc300429638d9a363fc9bd7fd7352", (288, 273, 259)),
    2: (6558724, "4d44cebe74da0255d785c9b24ea61967a6d21b94d605c5b11ddb3c0c342cb509", (269, 251, 263)),
    3: (5854518, "41609ef7f541cd879676aa2bcfb1c6c545dfb1eee10d4bc0a8e1d5d841efe479", (265, 261, 283)),
}
VIDEOS = (1, 2, 4)
KINDS = ("crop.png", "maskcrop.png", "depthcrop.png", "loc.txt")
PATTERN = re.compile(
    r"\Argbd-dataset/ball/ball_(\d+)/ball_(\d+)_(\d+)_(\d+)_"
    r"(crop\.png|maskcrop\.png|depthcrop\.png|loc\.txt)\Z"
)


class StopStudy(ValueError):
    """Fail closed; never substitute images or adjust a threshold."""


def choose(frames: tuple[int, ...], reference: bool) -> tuple[int, ...]:
    if not frames or len(set(frames)) != len(frames) or frames != tuple(sorted(frames)):
        raise StopStudy("invalid frame sequence")
    n = len(frames)
    ix = (n // 4, 3 * n // 4) if reference else (n // 4, n // 2, 3 * n // 4)
    if len(set(ix)) != len(ix):
        raise StopStudy("insufficient frame count")
    return tuple(frames[i] for i in ix)


def _fingerprint(archive: tarfile.TarFile, name: str) -> bytes:
    from PIL import Image

    member = archive.getmember(name)
    if not member.isfile() or not 0 < member.size <= 1_000_000:
        raise StopStudy("invalid selected RGB size")
    inp = archive.extractfile(member)
    if inp is None:
        raise StopStudy("invalid selected RGB payload")
    with inp:
        blob = inp.read(1_000_001)
    if len(blob) != member.size:
        raise StopStudy("truncated selected RGB")
    with Image.open(BytesIO(blob)) as rgb:
        if rgb.format != "PNG" or min(rgb.size) < 32 or max(rgb.size) > 1024:
            raise StopStudy("unexpected PNG geometry")
        # Exactly the frozen M1-B brightness/shape baseline; no mask or crop tuning.
        gray32 = rgb.convert("RGB").convert("L").resize(
            (32, 32), Image.Resampling.BILINEAR).tobytes()
    return image_fingerprint(gray32)


def load_features(folder: Path) -> dict[tuple[int, int, int], bytes]:
    features = {}
    for obj, (expected_bytes, digest, counts) in EXPECTED.items():
        path = folder / ("ball_" + str(obj) + ".tar")
        if path.is_symlink() or not path.is_file() or path.stat().st_size != expected_bytes:
            raise StopStudy("unapproved source size")
        h = sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(131072), b""):
                h.update(chunk)
        if h.hexdigest() != digest:
            raise StopStudy("unapproved source checksum")
        with tarfile.open(path, "r:") as archive:
            kinds = {v: {k: {} for k in KINDS} for v in VIDEOS}
            names = set()
            for member in archive.getmembers():
                p = PurePosixPath(member.name)
                if p.is_absolute() or ".." in p.parts or not (
                    member.isfile() or member.isdir()):
                    raise StopStudy("unsafe archive path or member")
                if member.isdir():
                    continue
                if member.name in names or member.size > 2_000_000:
                    raise StopStudy("duplicate or oversized archive member")
                names.add(member.name)
                m = PATTERN.fullmatch(member.name)
                if m is None:
                    raise StopStudy("unexpected archive member")
                directory, declared, video, frame = map(int, m.groups()[:4])
                kind = m.group(5)
                if directory != obj or declared != obj or video not in VIDEOS:
                    raise StopStudy("unapproved object/video")
                if frame in kinds[video][kind]:
                    raise StopStudy("duplicate RGB/depth/mask/loc frame")
                kinds[video][kind][frame] = member.name
            for pos, video in enumerate(VIDEOS):
                rgb = kinds[video]["crop.png"]
                if len(rgb) != counts[pos] or any(
                    set(channel) != set(rgb) for channel in kinds[video].values()
                ):
                    raise StopStudy("source frame count or modalities mismatch")
                for frame in choose(tuple(sorted(rgb)), reference=(video == 1)):
                    features[obj, video, frame] = _fingerprint(archive, rgb[frame])
    if len(features) != 24:
        raise StopStudy("selected view count changed")
    return features


def evaluate(features: dict[tuple[int, int, int], bytes]) -> dict:
    total = Counter()
    folds = []
    videos = {str(v): Counter() for v in (2, 4)}
    for unknown_obj in EXPECTED:
        refs = {}
        for obj in EXPECTED:
            if obj == unknown_obj:
                continue
            enrolled = sorted((frame, sig) for (o, vid, frame), sig in features.items()
                              if o == obj and vid == 1)
            if len(enrolled) != 2:
                raise StopStudy("enrollment count changed")
            refs[str(obj)] = tuple({"legacy": sig} for _, sig in enrolled)
        fold = Counter()
        for obj in EXPECTED:
            for video in (2, 4):
                queries = sorted((frame, sig) for (o, v, frame), sig in features.items()
                                 if o == obj and v == video)
                if len(queries) != 3:
                    raise StopStudy("query count changed")
                for _, sig in queries:
                    guess, status = _mem2b_policy_candidate(refs, {"legacy": sig})
                    if status == "ambiguous_unverified":
                        fold["ambiguity"] += 1
                    label = ("correct" if obj != unknown_obj and guess == str(obj) else
                             "wrong_known" if obj != unknown_obj and guess is not None else
                             "known_abstain" if obj != unknown_obj else
                             "unknown_rejected" if guess is None else "false_unknown")
                    fold[label] += 1
                    videos[str(video)][label] += 1
        if sum(fold[k] for k in ("correct", "wrong_known", "known_abstain")) != 12:
            raise StopStudy("wrong known view count")
        if fold["unknown_rejected"] + fold["false_unknown"] != 6:
            raise StopStudy("wrong unknown view count")
        folds.append({"unknown_ordinal": unknown_obj, **{
            k: fold[k] for k in ("correct", "wrong_known", "known_abstain",
                                "unknown_rejected", "false_unknown", "ambiguity")}})
        total.update(fold)
    passed = total["correct"] >= 18 and total["wrong_known"] == 0 and total["false_unknown"] == 0
    return {
        "study": "MEM2B_WA_frozen_three_ball_host_only",
        "technical_status": "COMPLETE",
        "quality_verdict": "PASS_HOST_ONLY" if passed else "INSUFFICIENT_STOP_NO_TUNING",
        "predeclared_gate_passed": passed,
        "fixed_similarity": MATCH_IMAGE, "fixed_ambiguity_gap": AMBIGUITY_GAP,
        "reference_source": "Washington_RGBD_turntable_video_1",
        "test_videos": [2, 4], "objects": 3,
        "positive_views": 36, "unknown_views": 18,
        "memory_off_positive_abstentions": 36, "memory_off_unknown_rejected": 18,
        **{k: total[k] for k in ("correct", "wrong_known", "known_abstain",
                                "unknown_rejected", "false_unknown", "ambiguity")},
        "folds": folds,
        "by_video": {v: dict(sorted(x.items())) for v, x in videos.items()},
        "selected_rgb_images": 24,
        "sqlite_real_media_writes": 0, "robot_runs": 0, "pc_llm_calls": 0,
        "commercial_license_verified": False, "media_republished": False,
        "physical_identity_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen MEM2B-WA host research, no media artifacts")
    parser.add_argument("--archive-dir", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    try:
        report = evaluate(load_features(args.archive_dir))
        report["wall_s"] = round(time.monotonic() - started, 3)
        report["host_peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(json.dumps(report, sort_keys=True))
        print("MEM2B_WA: COMPLETE_" + report["quality_verdict"])
        return 0  # research quality failure does not mean CI/script failure
    except (StopStudy, OSError, tarfile.TarError, ValueError, TypeError) as exc:
        print("MEM2B_WA: STOP_TECHNICAL_" + type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
