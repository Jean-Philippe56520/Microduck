"""Host-only real-image probe of already recorded YOLOX region proposals.

The pre-existing JSON boxes are NOT independent truth, and the output is
descriptive only. Does not run a second model, connect sensors, write SQLite,
make Qwen calls or control OEM.
"""
import hashlib
import json
import os
from pathlib import Path
import statistics
import time

from PIL import Image, ImageOps

from experiments.visual_region_descriptors import describe_region


ROOT = Path("tests/assets/public_vision_smoke")


def main():
    sources = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["images"]
    previous = json.loads((ROOT / "yolox_raw_head_diagnostic.json").read_text(
        encoding="utf-8"
    ))["raw_prediction_probe_per_image"]
    by_file = {record["file"]: record for record in previous}
    if len(sources) != 13 or len(by_file) != 13:
        raise SystemExit("unexpected source count")
    rows, durations = [], []
    for source in sources:
        name = source["file"]
        rec = by_file.get(name)
        if rec is None:
            raise SystemExit("missing pinned ROI for " + name)
        data = (ROOT / name).read_bytes()
        sig = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if sig != source["source_git_blob_sha"]:
            raise SystemExit("source image was modified: " + name)
        with Image.open(ROOT / name) as original:
            im = ImageOps.exif_transpose(original)
            tw, th = rec["expected_input_dims"]
            if max(im.size) > 4096:
                im.thumbnail((2048, 2048), Image.Resampling.LANCZOS)
            if im.size != (tw, th):
                raise SystemExit("ROI dimensional mismatch for " + name)
            box = rec["top_any_of_80_xyxy"]
            ts = time.perf_counter()
            descriptor = describe_region(im, box)
            durations.append((time.perf_counter() - ts) * 1000.0)
        rows.append({
            "image": name,
            "image_label_for_human_review_only": source["category"],
            "roi_from_existing_raw_yolox_diagnostic": box,
            "raw_top_80_coco_index": rec["top_any_of_80_class_idx"],
            "raw_top_joint_score": rec["top_any_of_80_joint"],
            "descriptor": descriptor,
        })
    report = {
        "status": "host_visual_region_experiment",
        "source": "existing_static_public_photos_and_pinned_raw_yolox_boxes",
        "source_diagnostic": "tests/assets/public_vision_smoke/yolox_raw_head_diagnostic.json",
        "number_of_images": len(rows),
        "synthetic_tests_separate": True,
        "real_photos_are_diagnostic_not_independent_holdout": True,
        "ground_truth_pixel_masks_absent": True,
        "source_class_names_not_used_to_extract_descriptors": True,
        "new_detector_models": 0,
        "modified_onnx_or_oem": False,
        "robot_or_npu_validated": False,
        "motor_commands": 0,
        "memory_writes": 0,
        "qwen_calls": 0,
        "descriptor_median_elapsed_ms_host": round(statistics.median(durations), 3),
        "candidate_foreground_count": sum(
            r["descriptor"]["status"] == "foreground_candidate" for r in rows
        ),
        "rounded_shape_count": sum(
            r["descriptor"]["shape"] == "ronde_probable" for r in rows
        ),
        "rows": rows,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path = Path(os.environ.get("VISUAL_REGION_SMOKE_REPORT", "/tmp/visual_region_smoke.json"))
    path.write_text(text, encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return report


if __name__ == "__main__":
    main()
