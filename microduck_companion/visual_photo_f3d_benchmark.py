"""F3-D: *frozen* MobileNetV2 CPU holdout on additional public CC0 photos.

Never tune on this new holdout. Score threshold is pinned to the exact F3-B
validation-only result, GitHub Actions run 40243269608. This experiment
does not test Microduck RK3566, NPU, real sensors, speech or motor safety.

The model comes from Apache-2.0 ONNX Model Zoo and is SHA256 checked. JPEG
thumbnail data are acquired in RAM and never stored or logged, while
public Wikimedia source pages are enumerated in visual_photo_f3d_catalog.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import hashlib
import json
import math
import platform
import statistics
import time

from .visual_photo_catalog import PublicPhoto
from .visual_photo_f3d_catalog import CHALLENGE_CATALOG, validate_challenge_catalog
from .visual_photo_baseline import (
    PhotoBaselineError, MAX_JPEG_BYTES, _check_jpeg_bytes,
)
from .visual_photo_mobilenet_demo import (
    check_model_file, MODEL_SHA256, classify_score, reduce_imagenet_scores,
    _classification_metrics, _frame_to_tensor,
)

# Exact F3-B validation-selected mass (NOT chosen using F3-D test photos).
FROZEN_F3B_THRESHOLD = 0.7059010988271212
FROZEN_THRESHOLD_EVIDENCE = (
    "https://github.com/Jean-Philippe56520/Microduck/actions/runs/40243269608"
)
MAX_RETRIES = 2
FETCH_TIMEOUT_S = 10


def fetch_challenge_photo(
    photo: PublicPhoto, *, opener=urlopen, sleeper=time.sleep,
) -> bytes:
    """Only specifically curated public Commons items, no arbitrary URLs.

    The *final* redirect host is checked BEFORE reading image bytes.
    Fails closed on HTML, oversized images, network errors or vanished
    sources. No score is printed if ANY input is unavailable.
    """
    if not any(item.photo == photo for item in CHALLENGE_CATALOG):
        raise PhotoBaselineError("photo absent from curated F3-D catalog")
    req = Request(
        photo.thumbnail_url,
        headers={"User-Agent": "MicroduckCompanionF3D/0.1 (public CC0 research)",
                 "Accept": "image/jpeg"},
    )
    last: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            with opener(req, timeout=FETCH_TIMEOUT_S) as response:
                return _check_jpeg_bytes(response)
        except PhotoBaselineError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last = exc
            if attempt + 1 < MAX_RETRIES:
                sleeper(float(attempt + 1))
    raise PhotoBaselineError("F3-D photo unavailable: no partial metric") from last


def wilson_interval(correct: int, total: int) -> tuple[float, float] | None:
    """95% Wilson score interval for a binomial proportion.

    Descriptive only: small, non-random CC0 convenience sample; not an
    estimate of performance in any home, or true ImageNet independence.
    """
    if (type(correct) is not int or type(total) is not int or
            total < 0 or correct < 0 or correct > total):
        raise ValueError("invalid successes/total")
    if total == 0:
        return None
    z = 1.959963984540054
    p = correct / total
    den = 1 + z*z/total
    centre = (p + z*z/(2*total))/den
    margin = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total))/den
    return max(0., centre-margin), min(1., centre+margin)


def summarize_challenge(
    rows: tuple[tuple[str, str, str], ...]
) -> dict:
    """Category and out-of-domain breakdown from an already frozen test."""
    if not rows or any(
        truth not in ("cat", "dog", "unknown")
        or prediction not in ("cat", "dog", "unknown")
        or group not in ("cat", "dog", "chair", "flower", "bird", "ball")
        or truth != (group if group in ("cat", "dog") else "unknown")
        for truth, prediction, group in rows
    ):
        raise PhotoBaselineError("invalid challenge rows/ground truth")
    scores = _classification_metrics(tuple((a,b) for a,b,_ in rows))
    n = len(rows)
    correct = scores["correct"]
    known = [r for r in rows if r[0] in ("cat","dog")]
    unknown = [r for r in rows if r[0] == "unknown"]
    false_positive = sum(pred != "unknown" for _,pred,_ in unknown)
    scores["accuracy_wilson95_descriptive"] = wilson_interval(correct, n)
    scores["known_recall_wilson95_descriptive"] = wilson_interval(
        sum(a==b for a,b,_ in known), len(known))
    scores["unknown_recall_wilson95_descriptive"] = wilson_interval(
        len(unknown)-false_positive, len(unknown))
    scores["unknown_false_known_rate"] = (
        false_positive / len(unknown) if unknown else None)
    scores["unknown_false_known_wilson95_descriptive"] = wilson_interval(
        false_positive, len(unknown))
    by_group = []
    for group in ("cat","dog","chair","flower","bird","ball"):
        group_rows = [(a,b) for a,b,g in rows if g==group]
        if not group_rows:
            continue
        n_group=len(group_rows)
        success=sum(a==b for a,b in group_rows)
        fp=sum(a=="unknown" and b!="unknown" for a,b in group_rows)
        by_group.append({
            "group":group,
            "support":n_group,
            "correct":success,
            "correct_fraction":success/n_group,
            "false_known_on_unknown":fp,
        })
    scores["by_public_subject_group"] = by_group
    scores["independent_label_audit_completed"] = False
    scores["overlap_with_imagenet_pretraining_audited"] = False
    return scores


def host_rss_kib() -> int:
    """Current RSS of THIS test process on Linux, not the model-only RSS."""
    if platform.system() != "Linux":
        raise PhotoBaselineError("host RSS measurement requires Linux")
    try:
        with open("/proc/self/status",encoding="ascii") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    parts=line.split()
                    if len(parts)!=3 or parts[2]!="kB":
                        break
                    return int(parts[1])
    except OSError as exc:
        raise PhotoBaselineError("host current RSS unavailable") from exc
    raise PhotoBaselineError("host current RSS unavailable")


def host_peak_rss_kib() -> int:
    """Linux ru_maxrss in KiB; includes Python, Pillow, ORT and decoder."""
    if platform.system() != "Linux":
        raise PhotoBaselineError("host peak RSS measurement requires Linux")
    import resource
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if not isinstance(value,(int,float)) or not math.isfinite(value) or value < 0:
        raise PhotoBaselineError("invalid ru_maxrss")
    return int(value)


def _latency_summary(samples: list[float]) -> dict:
    if (not samples or any(type(x) is not float or
                           not math.isfinite(x) or x < 0 for x in samples)):
        raise PhotoBaselineError("empty/invalid latency samples")
    ordered=sorted(samples)
    return {
        "n":len(ordered),
        "median_ms":round(statistics.median(ordered),3),
        "p95_nearest_rank_ms":round(ordered[math.ceil(.95*len(ordered))-1],3),
        "max_ms":round(ordered[-1],3),
        "min_ms":round(ordered[0],3),
    }


def run_f3d_benchmark(model_path: Path) -> dict:
    """One read of the new test set, without modifying the F3-B threshold."""
    validate_challenge_catalog()
    check_model_file(model_path)
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise PhotoBaselineError("onnxruntime not installed") from exc

    rss_before=host_rss_kib()
    cpu_before=time.process_time()
    wall_before=time.perf_counter()
    session_start=time.perf_counter()
    options=ort.SessionOptions()
    options.intra_op_num_threads=1
    options.inter_op_num_threads=1
    session=ort.InferenceSession(
        str(model_path),sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    providers=session.get_providers()
    if providers != ["CPUExecutionProvider"]:
        raise PhotoBaselineError("unexpected ONNX execution provider")
    if len(session.get_inputs())!=1 or len(session.get_outputs())<1:
        raise PhotoBaselineError("unsupported ONNX classifier signature")
    load_ms=(time.perf_counter()-session_start)*1000
    rss_after_load=host_rss_kib()
    input_name=session.get_inputs()[0].name
    rows=[]
    image_shas=set()
    sample_times=[]
    prep_times=[]
    fetch_times=[]
    jpeg_bytes_total=0
    for entry in CHALLENGE_CATALOG:
        started=time.perf_counter()
        jpeg=fetch_challenge_photo(entry.photo)
        fetch_times.append((time.perf_counter()-started)*1000)
        sha=hashlib.sha256(jpeg).digest()
        if sha in image_shas:
            raise PhotoBaselineError("duplicate JPEG bytes in held-out catalog")
        image_shas.add(sha)
        jpeg_bytes_total+=len(jpeg)

        started=time.perf_counter()
        tensor=_frame_to_tensor(jpeg)
        prep_times.append((time.perf_counter()-started)*1000)
        # At most one current thumbnail is retained; never persist or log it.
        del jpeg
        started=time.perf_counter()
        raw=session.run(None,{input_name:tensor})[0]
        sample_times.append(float((time.perf_counter()-started)*1000))
        if tuple(raw.shape)!=(1,1000):
            raise PhotoBaselineError("unexpected ONNX classifier output")
        label,mass=reduce_imagenet_scores(tuple(float(v) for v in raw[0]))
        classified=classify_score(label,mass,FROZEN_F3B_THRESHOLD)
        rows.append((entry.photo.category,classified,entry.group))
        del raw, tensor
    scored=summarize_challenge(tuple(rows))
    return {
        "scenario":"f3d_new_cc0_holdout_frozen_threshold_host_cpu",
        "scope":"host_only_real_public_jpeg_no_robot",
        "source":"Wikimedia_Commons_public_CC0_claims_not_legal_warranty",
        "model":"ImageNet1k_MobileNetV2_ONNX_Model_Zoo",
        "model_sha256":MODEL_SHA256,
        "model_bytes_on_disk":model_path.stat().st_size,
        "model_pretrained_not_finetuned_here":True,
        "execution_provider":providers[0],
        "threshold_source":"F3-B_six_validation_images_only",
        "frozen_threshold":FROZEN_F3B_THRESHOLD,
        "threshold_selected_on_new_test":False,
        "test_photos":len(rows),
        "unique_public_authors":len({x.photo.author for x in CHALLENGE_CATALOG}),
        "ground_truth_is_public_caption_not_double_annotated":True,
        "test_results":scored,
        "linux_host_process_resources_not_model_only":{
            "rss_before_session_kib":rss_before,
            "rss_after_session_load_kib":rss_after_load,
            "peak_process_rss_kib":host_peak_rss_kib(),
            "wall_total_s":round(time.perf_counter()-wall_before,3),
            "cpu_process_total_s":round(time.process_time()-cpu_before,3),
            "onnx_session_load_wall_ms":round(load_ms,3),
            "inference_28_samples":_latency_summary(sample_times),
            "preprocess_28_samples":_latency_summary(prep_times),
            "downloads_28_samples":_latency_summary(fetch_times),
            "total_public_jpeg_bytes_processed":jpeg_bytes_total,
        },
        "images_saved_to_disk":0,
        "audio_samples_recorded":0,
        "microduck_rk3566_validated":False,
        "robot_motors_issued":0,
    }


def main() -> int:
    import argparse
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--model",type=Path,required=True)
    args=cli.parse_args()
    print(json.dumps(run_f3d_benchmark(args.model),
                     sort_keys=True,allow_nan=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
