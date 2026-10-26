"""M1-B2 optional, HOST-ONLY study of pretrained visual/audio descriptors.

Downloads are opt-in and restricted to existing curated Wikimedia CC0 sources.
Weights are supplied separately and checked by SHA-256. No robot, OEM
service, identity, command, raw-media persistence, or automatic PC call.
The photographs are DIFFERENT photos, not verified views of one individual.
Cross-file matches are only a suspicious-merge proxy, not ground truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics
import struct
import subprocess
import time
from itertools import combinations

from .compact_multimodal_memory import (
    MATCH_AUDIO, MATCH_IMAGE, audio_fingerprint, image_fingerprint,
)
from .m1b_public_media_eval import (
    PUBLIC_SOUNDS, _host_ffmpeg, load_cc0_ogg,
)
from .visual_photo_catalog import PHOTO_CATALOG
from .visual_photo_baseline import fetch_thumbnail, validate_catalog
from .visual_photo_mobilenet_demo import check_model_file

# Converted, unretrained Google YAMNet Apache-2.0; this ONNX export comes
# from an external publisher, NOT Google. License/provenance must be reviewed.
YAMNET_URL = (
    "https://huggingface.co/audiomagic/yamnet-onnx/resolve/"
    "f25b741c2f0bdc6d7e6db24b5fddda23347dbafd/yamnet.onnx"
)
YAMNET_SHA256 = "d3835ffbbd4a1bb3e777f0ca217b5007907f5171dd5d17c4236b95b2af8f908e"
AUDIO_HZ = 16000
AUDIO_WINDOW = 16000
MAX_PCM16_BYTES = AUDIO_HZ * 2 * 5
M1B2_AUDIO_THRESHOLD = .95  # UNCALIBRATED pilot; two sounds are insufficient.
PHOTO_SPLITS = ("validation", "test")
VARIATIONS = ("brightness", "rotation_12deg", "crop_9pct")


def check_audio_model(path: Path) -> None:
    if not isinstance(path, Path) or not path.is_file():
        raise ValueError("pinned YAMNet ONNX file required")
    if not 15_000_000 <= path.stat().st_size <= 18_000_000:
        raise ValueError("unexpected audio model size")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(131072), b""):
            digest.update(chunk)
    if digest.hexdigest() != YAMNET_SHA256:
        raise ValueError("audio model SHA-256 mismatch")


def similarity(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    """Cosine of normalized model descriptors; NOT a calibrated probability."""
    if (not isinstance(a, tuple) or not isinstance(b, tuple)
            or len(a) != len(b) or not a
            or any(type(x) is not float or not math.isfinite(x)
                   for x in a + b)):
        raise ValueError("invalid embedding input")
    aa = sum(x*x for x in a)
    bb = sum(x*x for x in b)
    if aa <= 0 or bb <= 0:
        raise ValueError("empty embedding norm")
    return max(-1., min(1., sum(x*y for x, y in zip(a, b)) /
                              math.sqrt(aa * bb)))


def conservative_threshold(negative_proxy_scores: tuple[float, ...]) -> float:
    """Freeze a strict cutoff from VALIDATION cross-file pairs only.

    This deliberately rejects any candidate no safer than the most similar
    unrelated *file*. It is not a calibrated rate of false physical identity.
    """
    if (not negative_proxy_scores or any(
            type(x) is not float or not math.isfinite(x) or x < -1 or x > 1
            for x in negative_proxy_scores)):
        raise ValueError("validation negative file proxies required")
    return min(1., max(0., max(negative_proxy_scores)))


def _image_variants(jpeg: bytes):
    from io import BytesIO
    from PIL import Image, ImageEnhance, ImageOps
    with Image.open(BytesIO(jpeg)) as source:
        if source.format != "JPEG" or min(source.size) < 32:
            raise ValueError("unreviewed image shape or format")
        image = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGB"),
                             (224, 224), method=Image.Resampling.BILINEAR)
    return {
        "original": image,
        "brightness": ImageEnhance.Brightness(image).enhance(1.10),
        "rotation_12deg": image.rotate(12, Image.Resampling.BILINEAR,
                                        fillcolor=(128, 128, 128)),
        "crop_9pct": image.crop((20, 20, 204, 204)).resize(
            (224, 224), Image.Resampling.BILINEAR),
    }


def _image_baseline(image) -> bytes:
    from PIL import Image
    return image.convert("L").resize((32, 32), Image.Resampling.BILINEAR) \
        .tobytes()


def imagenet_distribution(values: tuple[float, ...]) -> tuple[float, ...]:
    """Retain class probabilities, or softmax logits exactly once."""
    if (type(values) is not tuple or len(values) != 1000 or
            any(type(v) is not float or not math.isfinite(v) for v in values)):
        raise ValueError("expected finite 1000-class ImageNet output")
    if min(values) >= 0. and max(values) <= 1. and abs(sum(values)-1.) <= .001:
        total = sum(values)
        return tuple(x / total for x in values)
    top = max(values)
    weights = tuple(math.exp(x-top) for x in values)
    total = sum(weights)
    if not math.isfinite(total) or total <= 0:
        raise ValueError("invalid ImageNet normalization")
    return tuple(x/total for x in weights)


def _image_learned(session, image, np, timings: list[float]):
    inputs = session.get_inputs()
    if len(inputs) != 1:
        raise ValueError("unsupported visual ONNX input signature")
    x = np.asarray(image, dtype=np.float32) / 255.
    x = (x - np.asarray((.485, .456, .406), dtype=np.float32)) / \
        np.asarray((.229, .224, .225), dtype=np.float32)
    x = np.transpose(x, (2, 0, 1))[None, ...].astype(np.float32)
    started = time.perf_counter_ns()
    raw = session.run(None, {inputs[0].name: x})[0]
    timings.append((time.perf_counter_ns() - started) / 1e6)
    if tuple(raw.shape) != (1, 1000) or not np.isfinite(raw).all():
        raise ValueError("unexpected or nonfinite ImageNet output")
    # ImageNet class DISTRIBUTION as a learned descriptor, not an instance
    # recognition embedding. Similar cats may be incorrectly merged.
    return imagenet_distribution(tuple(float(v) for v in raw[0]))


def _decode_audio_16k(ogg: bytes) -> tuple[int, ...]:
    if type(ogg) is not bytes or not ogg.startswith(b"OggS"):
        raise ValueError("curated OGG data required")
    process = subprocess.run([
        _host_ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
        "-protocol_whitelist", "file,pipe", "-i", "pipe:0", "-t", "5",
        "-ac", "1", "-ar", str(AUDIO_HZ), "-f", "s16le", "pipe:1",
    ], input=ogg, capture_output=True, timeout=15, check=False)
    data = process.stdout
    if (process.returncode or len(data) % 2 or
            not 1024 * 2 <= len(data) <= MAX_PCM16_BYTES):
        raise ValueError("invalid/oversized decoded public sound")
    samples = struct.unpack("<" + str(len(data)//2) + "h", data)
    if len(samples) < AUDIO_WINDOW:
        samples += (0,) * (AUDIO_WINDOW - len(samples))
    candidates = range(0, len(samples)-AUDIO_WINDOW+1, AUDIO_WINDOW//2)
    start = max(candidates,
                key=lambda i: sum(v*v for v in samples[i:i+AUDIO_WINDOW]))
    return samples[start:start+AUDIO_WINDOW]


def _audio_variants(samples: tuple[int, ...]):
    if type(samples) is not tuple or len(samples) != AUDIO_WINDOW or any(
            type(v) is not int or not -32768 <= v <= 32767
            for v in samples):
        raise ValueError("16-kHz 1-s PCM16 input required")
    gain = tuple(round(.8*v) for v in samples)
    shifted = (0,)*256 + samples[:-256]  # 16 ms at 16 kHz
    # Seeded pseudo-noise is a controlled perturbation, NOT a real
    # room/animal/background recording; reproducible without I/O.
    import random
    rng = random.Random(20261026)
    rms = math.sqrt(sum(v*v for v in samples) / len(samples))
    sigma = .05 * rms  # approximately 26 dB SNR if no clipping
    noisy = tuple(max(-32768, min(32767, round(v + rng.gauss(0, sigma))))
                  for v in samples)
    return {"original": samples, "gain_80pct": gain,
            "shift_16ms": shifted, "synthetic_noise_26dB": noisy}


def _audio_baseline(samples: tuple[int, ...]) -> bytes:
    downsampled = samples[::2]  # 8kHz PCM; no persisted waveform
    starts = range(0, len(downsampled)-1024+1, 256)
    best = max(starts, key=lambda i: sum(
        v*v for v in downsampled[i:i+1024]))
    snippet = struct.pack("<1024h", *downsampled[best:best+1024])
    return audio_fingerprint(snippet)


def _audio_learned(session, samples, np, timings: list[float]):
    inp = session.get_inputs()
    outputs = session.get_outputs()
    if len(inp) != 1 or len(outputs) < 2:
        raise ValueError("unsupported YAMNet ONNX signature")
    waveform = np.asarray(samples, dtype=np.float32) / 32768.
    started = time.perf_counter_ns()
    embeddings = session.run([outputs[1].name],
                             {inp[0].name: waveform})[0]
    timings.append((time.perf_counter_ns() - started) / 1e6)
    if (len(embeddings.shape) != 2 or embeddings.shape[1] != 1024
            or embeddings.shape[0] < 1 or
            not np.isfinite(embeddings).all()):
        raise ValueError("invalid YAMNet embedding tensor")
    pooled = np.mean(embeddings, axis=0)
    if np.linalg.norm(pooled) <= 0:
        raise ValueError("silent embedding")
    return tuple(float(v) for v in pooled)


def _score(a, b, kind):
    if kind == "legacy":
        return 1. - sum(abs(x-y) for x, y in zip(a, b)) / (255.*len(a))
    if kind == "learned":
        return similarity(a, b)
    raise ValueError("unknown candidate")


def _pairs(records: dict, names: tuple[str, ...], variations: tuple[str, ...],
           *, kind: str, threshold: float) -> dict:
    if type(threshold) is not float or not 0 <= threshold <= 1:
        raise ValueError("threshold must be in [0, 1]")
    hits = {}
    for variant in variations:
        hits[variant] = sum(
            _score(records[name]["original"][kind],
                   records[name][variant][kind], kind) > threshold
            for name in names)
    # Cross-FILE score is NOT ground truth of distinct physical individuals.
    cross = sum(_score(records[a]["original"][kind],
                       records[b]["original"][kind], kind) > threshold
                for a, b in combinations(names, 2))
    return {"sources": len(names), "same_file_hits": hits,
            "same_file_trials_per_variant": len(names),
            "cross_file_merges_proxy": cross,
            "cross_file_pairs_proxy": len(names)*(len(names)-1)//2}


def _latency(timings):
    if not timings:
        raise ValueError("no actual host inference")
    ordered = sorted(timings)
    return {"calls": len(ordered), "median_ms": statistics.median(ordered),
            "p95_ms": ordered[math.ceil(.95*len(ordered))-1],
            "max_ms": ordered[-1]}


def run_public_study(image_model: Path, audio_model: Path) -> dict:
    """Opt-in test of PUBLIC media. Never updates M1-B SQLite or robotd."""
    check_model_file(image_model)
    check_audio_model(audio_model)
    validate_catalog()
    _host_ffmpeg()
    import numpy as np
    import onnxruntime as ort
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.inter_op_num_threads = 1
    visual = ort.InferenceSession(str(image_model), sess_options=opts,
                                  providers=["CPUExecutionProvider"])
    audio = ort.InferenceSession(str(audio_model), sess_options=opts,
                                 providers=["CPUExecutionProvider"])
    images = {}
    image_times = []
    selected = [p for p in PHOTO_CATALOG if p.split in PHOTO_SPLITS]
    if (len(selected) != 12 or
            sum(p.split == "validation" for p in selected) != 6 or
            sum(p.split == "test" for p in selected) != 6 or
            any(p.license != "CC0-1.0" for p in selected)):
        raise ValueError("exact curated holdout image roster required")
    distinct_media = set()
    cpu_before = resource.getrusage(resource.RUSAGE_SELF)
    for item in selected:
        jpeg = fetch_thumbnail(item)
        fingerprint = hashlib.sha256(jpeg).hexdigest()
        if fingerprint in distinct_media:
            raise ValueError("duplicate media bytes among holdout photos")
        distinct_media.add(fingerprint)
        variants = _image_variants(jpeg)
        images[item.filename] = {}
        for variant, value in variants.items():
            pixels = _image_baseline(value)
            images[item.filename][variant] = {
                "legacy": image_fingerprint(pixels),
                "learned": _image_learned(visual, value, np, image_times),
            }
    val = tuple(p.filename for p in selected if p.split == "validation")
    test = tuple(p.filename for p in selected if p.split == "test")
    learned_val_neg = tuple(_score(images[a]["original"]["learned"],
                                   images[b]["original"]["learned"],
                                   "learned") for a, b in combinations(val, 2))
    frozen_threshold = conservative_threshold(learned_val_neg)
    photo_report = {}
    for split, names in (("validation", val), ("test", test)):
        photo_report[split] = {
            "m1b_legacy_64bytes": _pairs(
                images, names, VARIATIONS, kind="legacy",
                threshold=float(MATCH_IMAGE) - 1e-10),
            "mobilenetv2_class_scores_4000bytes": _pairs(
                images, names, VARIATIONS, kind="learned",
                threshold=frozen_threshold),
        }
    sounds = {}
    sound_times = []
    for filename, category, _ in PUBLIC_SOUNDS:
        samples = _decode_audio_16k(load_cc0_ogg(filename))
        sounds[filename] = {}
        for variant, value in _audio_variants(samples).items():
            sounds[filename][variant] = {
                "legacy": _audio_baseline(value),
                "learned": _audio_learned(audio, value, np, sound_times),
            }
    audio_names = tuple(filename for filename, _, _ in PUBLIC_SOUNDS)
    audio_report = {
        "m1b_legacy_16bytes": _pairs(
            sounds, audio_names,
            ("gain_80pct", "shift_16ms", "synthetic_noise_26dB"),
            kind="legacy", threshold=float(MATCH_AUDIO) - 1e-10),
        "yamnet_1024_float32_4096bytes": _pairs(
            sounds, audio_names,
            ("gain_80pct", "shift_16ms", "synthetic_noise_26dB"),
            kind="learned", threshold=M1B2_AUDIO_THRESHOLD),
        "yamnet_cutoff_heuristic_not_calibrated": M1B2_AUDIO_THRESHOLD,
    }
    cpu_after = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "scenario": "m1b2_public_cc0_host_onnx_descriptors_pilot",
        "images": photo_report, "sounds": audio_report,
        "visual_learned_validation_only_cross_file_cutoff": frozen_threshold,
        "image_model_sha256":
            "c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5",
        "audio_model_sha256": YAMNET_SHA256,
        "weight_bytes": {"vision": image_model.stat().st_size,
                         "sound": audio_model.stat().st_size},
        "descriptor_bytes_per_observation": {
            "legacy_image": 64, "learned_image_float32": 4000,
            "legacy_sound": 16, "learned_sound_float32": 4096},
        "onnx_cpu_vision": _latency(image_times),
        "onnx_cpu_sound": _latency(sound_times),
        "host_peak_rss_kib_whole_process_not_per_model":
            cpu_after.ru_maxrss,
        "host_cpu_user_s_after_model_load_excludes_fetch_setup":
            round(cpu_after.ru_utime - cpu_before.ru_utime, 3),
        "host_cpu_system_s_after_model_load_excludes_fetch_setup":
            round(cpu_after.ru_stime - cpu_before.ru_stime, 3),
        "total_host_on_cpu_not_rk3566": True,
        "different_natural_views_of_same_individual": False,
        "cross_file_proxy_is_verified_distinct_physical_object": False,
        "candidate_ready_for_embedded": False,
        "silence_person_and_speech_filter_real": False,
        "microduck_hardware_tested": False,
        "raw_media_saved": False,
        "sqlite_written": False, "pc_contacted": False,
        "motor_commands": 0,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-cc0", action="store_true")
    parser.add_argument("--image-model", type=Path, required=True)
    parser.add_argument("--audio-model", type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.public_cc0:
        parser.error("opt-in --public-cc0 required; no network by default")
    print(json.dumps(run_public_study(args.image_model, args.audio_model),
                     sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
