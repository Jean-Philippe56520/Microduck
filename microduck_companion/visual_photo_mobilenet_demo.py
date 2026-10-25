"""F3-B optional, host-only MobileNetV2 ONNX baseline on CC0 photographs.

Pretrained Apache-2.0 ONNX Model Zoo MobileNet v2-12, ImageNet-1k.
No train/fine-tune on the 20 photos; train split is a reference only.
Only validation chooses a single abstention threshold; held-out test is
scored ONCE. No robotd/mediad, no RKNN/NPU, no motor or identity output.
Files are ephemeral CI runner downloads, not committed to the repository.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import argparse
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import time

from .visual_photo_catalog import PHOTO_CATALOG
from .visual_photo_baseline import (
    PhotoBaselineError, fetch_thumbnail, _CLASSES,
)
from .visual_dataset import parse_visual_manifest
from .visual_photo_baseline_demo import _metadata_manifest
from .visual_photo_baseline import ImageFeature, validate_catalog

MODEL_URL = ("https://huggingface.co/onnxmodelzoo/mobilenetv2-12/"
             "resolve/main/mobilenetv2-12.onnx")
MODEL_SHA256 = "c0c3f76d93fa3fd6580652a45618618a220fced18babf65774ed169de0432ad5"
DOG_INDICES = tuple(range(151,269))
CAT_INDICES = tuple(range(281,286))
INPUT_SIZE = 224


def check_model_file(path: Path) -> None:
    if not isinstance(path, Path) or not path.is_file():
        raise PhotoBaselineError("ONNX model path is required")
    if not 13_000_000 <= path.stat().st_size <= 15_000_000:
        raise PhotoBaselineError("unexpected ONNX model size")
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(128 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != MODEL_SHA256:
        raise PhotoBaselineError("ONNX model fingerprint mismatch")


def reduce_imagenet_scores(scores: tuple[float, ...]) -> tuple[str, float]:
    """Collapse ImageNet-1k dog breeds/cat breeds into two labels + reject mass.

    Label mapping: 151..268 = dog breeds, 281..285 = domestic cats.
    Reported 'known mass' is a score, not a calibrated confidence or
    a guarantee of detecting any cat/dog.
    """
    if (type(scores) is not tuple or len(scores) != 1000
            or any(type(x) is not float or not math.isfinite(x)
                   for x in scores)):
        raise PhotoBaselineError("ImageNet-1k logits required")
    if min(scores) >= 0 and max(scores) <= 1 and abs(sum(scores)-1) <= .001:
        probs=scores
    else:
        peak=max(scores)
        exps=[math.exp(x-peak) for x in scores]
        total=sum(exps)
        probs=tuple(x/total for x in exps)
    dog=sum(probs[i] for i in DOG_INDICES)
    cat=sum(probs[i] for i in CAT_INDICES)
    label="dog" if dog >= cat else "cat"
    known=dog+cat
    return label, min(1.,max(0.,known))


def classify_score(label: str, mass: float, threshold: float) -> str:
    if (label not in _CLASSES or type(mass) is not float
            or type(threshold) is not float or not math.isfinite(mass)
            or not math.isfinite(threshold)
            or not 0 <= mass <= 1 or not 0 <= threshold <= 1):
        raise PhotoBaselineError("invalid confidence/rejection score")
    return label if mass >= threshold else "unknown"


def select_validation_threshold(
    predictions: tuple[tuple[str, str, float], ...]
) -> float:
    if (not predictions
            or not any(truth == "unknown" for truth,_,_ in predictions)
            or not any(truth in _CLASSES for truth,_,_ in predictions)):
        raise PhotoBaselineError("need known and unknown validation samples")
    candidates={0.,1.}
    for _,_,confidence in predictions:
        if not isinstance(confidence,float) or not math.isfinite(confidence):
            raise PhotoBaselineError("malformed validation mass")
        candidates.add(confidence)
        candidates.add(min(1.,confidence + .000001))
    winner=None
    value=None
    for threshold in sorted(candidates):
        pairs=[(truth,classify_score(label,mass,float(threshold)))
               for truth,label,mass in predictions]
        known=[(a,b) for a,b in pairs if a in _CLASSES]
        unknown=[(a,b) for a,b in pairs if a=="unknown"]
        kr=sum(a==b for a,b in known)/len(known)
        ur=sum(b=="unknown" for _,b in unknown)/len(unknown)
        score=(kr+ur,ur,kr,threshold)
        if value is None or score>value:
            value=score
            winner=float(threshold)
    assert winner is not None
    return winner


def _classification_metrics(pairs: tuple[tuple[str, str], ...]) -> dict:
    if (not pairs or any(a not in (*_CLASSES,"unknown")
                        or b not in (*_CLASSES,"unknown") for a,b in pairs)):
        raise PhotoBaselineError("invalid evaluation pair")
    conf=Counter(pairs)
    n=len(pairs)
    known=[(a,b) for a,b in pairs if a in _CLASSES]
    unknown=[(a,b) for a,b in pairs if a=="unknown"]
    def pr(label):
        sup=sum(a==label for a,_ in pairs)
        pred=sum(b==label for _,b in pairs)
        tp=conf[(label,label)]
        precision=tp/pred if pred else 0.
        recall=tp/sup if sup else 0.
        return {"support":sup, "predicted":pred, "precision":precision,
                "recall":recall, "f1":(2*precision*recall/(precision+recall)
                                     if precision+recall else 0.)}
    return {
        "test_or_validation_samples":n,
        "correct":sum(a==b for a,b in pairs),
        "accuracy":sum(a==b for a,b in pairs)/n,
        "known_support":len(known),
        "known_recall":(sum(a==b for a,b in known)/len(known)) if known else None,
        "unknown_support":len(unknown),
        "unknown_recall":(sum(b=="unknown" for _,b in unknown)/len(unknown))
            if unknown else None,
        "false_known_on_unknown":sum(b!="unknown" for _,b in unknown),
        "coverage":sum(b!="unknown" for _,b in pairs)/n,
        "confusion":tuple(sorted((a,b,count) for (a,b),count in conf.items())),
        "cat":pr("cat"),"dog":pr("dog"),
    }


def _frame_to_tensor(jpeg: bytes):
    """ImageNet normalization and center crop; external Pillow+numpy only."""
    try:
        import numpy as np
        from PIL import Image, ImageOps
        with Image.open(BytesIO(jpeg)) as img:
            if img.format != "JPEG" or img.width < 32 or img.height < 32:
                raise PhotoBaselineError("unexpected input image")
            rgb=ImageOps.exif_transpose(img).convert("RGB")
            scale=256. / min(rgb.width,rgb.height)
            resized=rgb.resize((round(rgb.width*scale),round(rgb.height*scale)),
                               Image.Resampling.BILINEAR)
            x=(resized.width-INPUT_SIZE)//2
            y=(resized.height-INPUT_SIZE)//2
            cropped=resized.crop((x,y,x+INPUT_SIZE,y+INPUT_SIZE))
            a=np.asarray(cropped,dtype=np.float32)/255.
            a=(a-np.array([.485,.456,.406],dtype=np.float32))/np.array(
                [.229,.224,.225],dtype=np.float32)
            return np.transpose(a,(2,0,1))[None,...].astype(np.float32)
    except (ImportError,OSError,ValueError) as exc:
        raise PhotoBaselineError("Pillow/NumPy decoding failed") from exc


def run_mobilenet_demo(model_file: Path) -> dict:
    check_model_file(model_file)
    validate_catalog()
    try:
        import onnxruntime as ort
    except ImportError as exc:
        raise PhotoBaselineError("onnxruntime unavailable") from exc
    opts=ort.SessionOptions()
    opts.intra_op_num_threads=1
    opts.inter_op_num_threads=1
    sess=ort.InferenceSession(str(model_file),sess_options=opts,
                              providers=["CPUExecutionProvider"])
    if (len(sess.get_inputs())!=1 or len(sess.get_outputs())<1):
        raise PhotoBaselineError("unsupported ImageNet ONNX signature")
    input_name=sess.get_inputs()[0].name
    output=[]
    real_samples=[]
    sample_times=[]
    acquisition_started=time.perf_counter_ns()
    for photo in PHOTO_CATALOG:
        image_data=fetch_thumbnail(photo)
        digest=hashlib.sha256(image_data).hexdigest()
        # Uses the F3-A contract later: 34 finite fields required but
        # classification is performed by ONNX, not this placeholder.
        real_samples.append(ImageFeature(
            photo.category,photo.split,photo.author,digest,(0.,)*34))
        x=_frame_to_tensor(image_data)
        started=time.perf_counter_ns()
        raw=sess.run(None,{input_name:x})[0]
        sample_times.append((time.perf_counter_ns()-started)/1e6)
        if tuple(raw.shape)!=(1,1000):
            raise PhotoBaselineError("unexpected ImageNet output shape")
        label,mass=reduce_imagenet_scores(tuple(float(i) for i in raw[0]))
        output.append((photo.split,photo.category,label,mass))
    all_ms=(time.perf_counter_ns()-acquisition_started)/1e6
    manifest=parse_visual_manifest(
        _metadata_manifest(tuple(real_samples)),allow_external=True)
    if manifest.synthetic_only or len(manifest.samples)!=20:
        raise PhotoBaselineError("F3-A split/fingerprint audit failed")
    validation=tuple((truth,label,mass) for split,truth,label,mass in output
                     if split=="validation")
    threshold=select_validation_threshold(validation)
    def pairs_for(split):
        return tuple((truth,classify_score(label,mass,threshold))
                     for x,truth,label,mass in output if x==split)
    val_report=_classification_metrics(pairs_for("validation"))
    test_report=_classification_metrics(pairs_for("test"))
    return {
        "scenario":"f3b_real_cc0_mobilenetv2_onnx_cpu_host",
        "model":"ONNX_Model_Zoo_MobileNetV2_ImageNet1k",
        "model_license":"Apache-2.0",
        "model_sha256":MODEL_SHA256,
        "model_size_bytes":model_file.stat().st_size,
        "model_pretrained_on":"ImageNet1k_external_not_our_20_photos",
        "photos_used_for_finetuning":0,
        "images_count_processed":len(output),
        "dataset_splits":{"train":8,"validation":6,"test":6},
        "threshold_selected_on_validation_only":threshold,
        "validation_diagnostic":val_report,
        "independent_test_metrics":test_report,
        "median_inference_ms_host_cpu":sorted(sample_times)[len(sample_times)//2],
        "max_inference_ms_host_cpu":max(sample_times),
        "total_download_and_inference_ms_host":round(all_ms,3),
        "model_execution":"CPUExecutionProvider_only_not_RK3566",
        "source":"Wikimedia Commons CC0 uploader declarations; author grouped",
        "licenses_not_cryptographically_guaranteed":True,
        "media_bytes_persisted":0,
        "camera_connected":False,
        "individual_identity":False,
        "motors_issued":0,
    }


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model",required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(run_mobilenet_demo(args.model),sort_keys=True,allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
