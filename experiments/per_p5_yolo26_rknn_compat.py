"""PER-P5: immutable Ultralytics / RK3566 host-only conversion and simulator probe.

No camera, robot, motor, photo publication, Qwen or memory write.
Pass/fail is for the *host environment*, never for the RK3566 board.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import resource
import sys
import time
import traceback

MODELS = {
    "yolo26n.pt": "9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef",
    "yolo26n-seg.pt": "361fbfabab285c3237700b6bb91d7ecfa602cd945fffda8dbe1242829b71e73f",
}
ULTRA_VERSION = "8.4.192"
SDK_VERSION = "2.3.2"
INPUT_SIZE = 640
MAX_BYTES = 128 * 1024 * 1024
CALIBRATION_COUNT = 20


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for part in iter(lambda: source.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


def verify_sources(model_path: Path, calibration_list: Path) -> dict:
    if model_path.name not in MODELS or model_path.is_symlink() or not model_path.is_file():
        raise ValueError("unapproved or missing official model")
    if _sha(model_path) != MODELS[model_path.name]:
        raise ValueError("official model SHA mismatch")
    if calibration_list.is_symlink() or not calibration_list.is_file():
        raise ValueError("missing official calibration list")
    lines = calibration_list.read_text(encoding="utf-8").splitlines()
    if len(lines) != CALIBRATION_COUNT or len(set(lines)) != CALIBRATION_COUNT:
        raise ValueError("official 20-image calibration count invalid")
    base = calibration_list.parent.resolve()
    for line in lines:
        if not line.startswith("./subset/") or not line.endswith(".jpg"):
            raise ValueError("unexpected calibration path")
        image = (base / line).resolve()
        if base not in image.parents or not image.is_file() or image.stat().st_size < 100:
            raise ValueError("missing/unsafe official calibration image")
    return {"weight_sha256": MODELS[model_path.name], "calibration_count": len(lines)}


def _tensors(value_info):
    result = []
    for v in value_info:
        dims = []
        for d in v.type.tensor_type.shape.dim:
            dims.append(d.dim_value if d.HasField("dim_value") else d.dim_param)
        result.append({"name": v.name, "shape": dims})
    return result


def _cropped_head_outputs(graph, head: str, task: str) -> list[str]:
    """Select the same raw per-level outputs as Ultralytics v8.4.192 RKNN exporter.

    This is an evaluation adapter to Rockchip's SAME-INSTANCE simulator, not
    a model modification. Source: ultralytics/utils/export/rknn.py (AGPL-3.0).
    """
    if task not in {"detect", "segment"}:
        raise ValueError("unexpected task")
    cropped_consumers = {"Reshape", "Concat"}
    direct_consumers = {
        input_name
        for node in graph.node if node.op_type in cropped_consumers
        for input_name in node.input
    }
    other_consumers = {
        input_name
        for node in graph.node if node.op_type not in cropped_consumers
        for input_name in node.input
    }
    direct_consumers.difference_update(other_consumers)
    heads = [
        node.output[0]
        for node in graph.node
        if node.op_type == "Conv"
        and head in node.name
        and "/dfl/" not in node.name
        and node.output
        and node.output[0] in direct_consumers
    ]
    expected = 9 if task == "segment" else 6
    if len(heads) != expected or len(set(heads)) != len(heads):
        raise RuntimeError(f"unexpected raw {task} head count {len(heads)}; expected {expected}")
    extras = [out.name for out in graph.output if out.name != "output0"]
    if task == "segment" and extras != ["output1"]:
        raise RuntimeError(f"unexpected segment prototype outputs {extras}")
    if task == "detect" and extras:
        raise RuntimeError(f"unexpected detection outputs {extras}")
    return heads + extras


def _ok(rc, stage):
    if rc not in (0, None):
        raise RuntimeError(f"RKNN {stage} returned {rc}")


def run(model_path: Path, calibration_list: Path, result: dict) -> None:
    from importlib.metadata import version
    import numpy as np
    import onnx
    import torch
    import ultralytics
    from rknn.api import RKNN
    from ultralytics import YOLO

    if ultralytics.__version__ != ULTRA_VERSION:
        raise RuntimeError("unpinned ultralytics runtime")
    if version("rknn-toolkit2") != SDK_VERSION:
        raise RuntimeError("unpinned RKNN toolkit version")
    if not str(torch.__version__).startswith("2.4.0"):
        raise RuntimeError("unexpected Torch version")
    result.update(verify_sources(model_path, calibration_list))
    result.update({"platform": "rk3566",
                   "ultralytics_version": ULTRA_VERSION,
                   "toolkit_version": SDK_VERSION,
                   "torch": str(torch.__version__),
                   "host_arch": platform.machine(),
                   "test": "P5-SIM1_same_instance_sdk_host_only",
                   "motor_commands": 0, "memory_writes": 0,
                   "segmentation_masks_decoded": False,
                   "tail_onnx_usable": False})
    model = YOLO(str(model_path))
    task = "segment" if model_path.name.endswith("-seg.pt") else "detect"
    if model.task != task:
        raise RuntimeError("unexpected official weight task")
    head = f"/model.{len(model.model.model) - 1}/"
    start = time.perf_counter()
    onnx_path = Path(model.export(format="onnx", imgsz=INPUT_SIZE, batch=1,
                                  opset=19, simplify=False, dynamic=False, nms=False))
    result["onnx_export_s"] = round(time.perf_counter() - start, 3)
    graph = onnx.load(str(onnx_path))
    onnx.checker.check_model(graph)
    result["onnx_bytes"] = onnx_path.stat().st_size
    result["onnx_inputs"] = _tensors(graph.graph.input)
    result["onnx_outputs"] = _tensors(graph.graph.output)
    outputs = _cropped_head_outputs(graph.graph, head, task)
    result["rknn_output_head_names"] = outputs
    result["rknn_output_count_expected"] = len(outputs)
    result["raw_output_only_no_tail_decoder"] = True
    out_dir = model_path.parent / f"{model_path.stem}_rknn_model"
    out_dir.mkdir(parents=True, exist_ok=True)
    rknn_path = out_dir / f"{onnx_path.stem}-rk3566.rknn"
    builder = RKNN(verbose=False)
    try:
        started = time.perf_counter()
        _ok(builder.config(mean_values=[[0, 0, 0]], std_values=[[255, 255, 255]],
                           target_platform="rk3566", auto_hybrid_cos_thresh=0.999), "config")
        _ok(builder.load_onnx(model=str(onnx_path), outputs=outputs), "load_onnx")
        _ok(builder.build(do_quantization=True, dataset=str(calibration_list),
                          auto_hybrid=True, rknn_batch_size=1), "build")
        _ok(builder.export_rknn(str(rknn_path)), "export_rknn")
        result["build_export_s"] = round(time.perf_counter() - started, 3)
        size = rknn_path.stat().st_size
        if not 0 < size < MAX_BYTES:
            raise RuntimeError("RKNN model empty or >128 MiB")
        result["rknn_bytes"] = size
        result["rknn_sha256_not_published"] = _sha(rknn_path)
        result["host_conversion_passed"] = True
        result["status"] = "host_conversion_passed_simulation_pending"
        # SDK 2.3.2 supports host simulation only on this builder instance,
        # NOT after another RKNN() calls load_rknn on the export.
        _ok(builder.init_runtime(), "init_runtime_on_builder")
        sample = np.empty((INPUT_SIZE, INPUT_SIZE, 3), dtype=np.uint8)
        sample[:, :, 0] = 37
        sample[:, :, 1] = 109
        sample[:, :, 2] = 173
        started = time.perf_counter()
        inference = builder.inference(inputs=[sample], data_format="nhwc")
        result["one_host_simulator_inference_ms"] = round(
            (time.perf_counter() - started) * 1000, 2)
        if not isinstance(inference, (list, tuple)) or len(inference) != len(outputs):
            raise RuntimeError("unexpected number of simulator output tensors")
        tensors = []
        for value in inference:
            arr = np.asarray(value)
            if arr.size < 1 or not np.issubdtype(arr.dtype, np.number):
                raise RuntimeError("invalid simulator output")
            if not np.isfinite(arr).all():
                raise RuntimeError("nonfinite simulator output")
            tensors.append({"shape": list(arr.shape), "dtype": str(arr.dtype),
                            "bytes": int(arr.nbytes), "elements": int(arr.size)})
        result["simulator_outputs"] = tensors
        result["simulator_output_bytes_total"] = sum(t["bytes"] for t in tensors)
        result["host_simulator_passed"] = True
        result["status"] = "host_compilation_and_raw_head_simulation_passed"
    finally:
        builder.release()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    status = {"study": "PER-P5_RK3566_host_only", "model": args.model.name,
              "robot_validated": False, "NPU_measured": False,
              "status": "not_executed", "host_conversion_passed": False,
              "host_simulator_passed": False, "rights_for_deployment_verified": False,
              "OEM_multioutput_compatible": False}
    code = 0
    try:
        run(args.model, args.calibration, status)
    except Exception as exc:
        status["status"] = "host_simulation_failed_after_conversion" if status["host_conversion_passed"] else "host_conversion_failed"
        status["failure_type"] = type(exc).__name__
        status["failure_text"] = str(exc)[:600]
        status["host_peak_rss_kib_process"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(traceback.format_exc(limit=8), file=sys.stderr)
        code = 1
    status["host_peak_rss_kib_process"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True),
                           encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, sort_keys=True), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
