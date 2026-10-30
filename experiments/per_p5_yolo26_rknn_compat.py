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


def run(model_path: Path, calibration_list: Path) -> dict:
    import numpy as np
    import onnx
    import torch
    import ultralytics
    import rknn
    from rknn.api import RKNN
    from ultralytics import YOLO
    from ultralytics.utils.export.rknn import onnx2rknn

    if ultralytics.__version__ != ULTRA_VERSION:
        raise RuntimeError("unpinned ultralytics runtime")
    if not str(getattr(rknn, "__version__", SDK_VERSION)).startswith(SDK_VERSION):
        raise RuntimeError("unpinned RKNN toolkit version")
    if not str(torch.__version__).startswith("2.4.0"):
        raise RuntimeError("unexpected Torch version")
    proof = verify_sources(model_path, calibration_list)
    result = {"model": model_path.name, **proof, "platform": "rk3566",
              "runtime": ULTRA_VERSION, "toolkit_expected": SDK_VERSION,
              "torch": str(torch.__version__), "host_arch": platform.machine(),
              "device": "host_only", "NPU_measured": False, "robot_validated": False,
              "motor_commands": 0, "memory_writes": 0}
    model = YOLO(str(model_path))
    expected = "segment" if model_path.name.endswith("-seg.pt") else "detect"
    if model.task != expected:
        raise RuntimeError("unexpected weight task")
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
    out_dir = model_path.parent / f"{model_path.stem}_rknn_model"
    start = time.perf_counter()
    created = Path(onnx2rknn(
        onnx_file=str(onnx_path), output_dir=out_dir,
        name="rk3566", quantize=8, batch=1,
        dataset=str(calibration_list), head=head,
        metadata={"task": expected, "imgsz": INPUT_SIZE},
    ))
    result["conversion_s"] = round(time.perf_counter() - start, 3)
    rknns = sorted(created.glob("*.rknn"))
    if len(rknns) != 1:
        raise RuntimeError("expected exactly one compiled RKNN file")
    rknn_path = rknns[0]
    nbytes = rknn_path.stat().st_size
    if not 0 < nbytes < MAX_BYTES:
        raise RuntimeError("invalid/oversized compiled RKNN file")
    result["rknn_bytes"] = nbytes
    result["rknn_sha256_not_published"] = _sha(rknn_path)
    tail = created / "tail.onnx"
    result["tail_present"] = tail.is_file()
    result["tail_bytes"] = tail.stat().st_size if tail.exists() else 0
    if result["tail_present"]:
        tail_graph = onnx.load(str(tail))
        onnx.checker.check_model(tail_graph)
        result["tail_inputs"] = _tensors(tail_graph.graph.input)
        result["tail_outputs"] = _tensors(tail_graph.graph.output)
    result["host_conversion_passed"] = True
    # Host simulator only, not the board's NPU or driver.
    simulator = RKNN(verbose=False)
    initialized = False
    try:
        rc = simulator.load_rknn(str(rknn_path))
        if rc not in (0, None):
            raise RuntimeError(f"load_rknn returned {rc}")
        rc = simulator.init_runtime()  # simulator, NO target= or device_id
        if rc not in (0, None):
            raise RuntimeError(f"init_runtime returned {rc}")
        initialized = True
        # Deterministic synthetic array is a transport test, not a detection benchmark.
        sample = np.zeros((INPUT_SIZE, INPUT_SIZE, 3), dtype=np.uint8)
        sample[:, :, 0] = 37
        sample[:, :, 1] = 109
        sample[:, :, 2] = 173
        started = time.perf_counter()
        outputs = simulator.inference(inputs=[sample], data_format="nhwc")
        result["simulator_inference_ms_one_sample"] = round(
            (time.perf_counter() - started) * 1000, 2)
        if not isinstance(outputs, (list, tuple)) or not outputs:
            raise RuntimeError("empty simulated output collection")
        checked = []
        for value in outputs:
            array = np.asarray(value)
            if array.size == 0 or not np.issubdtype(array.dtype, np.number):
                raise RuntimeError("invalid simulated output")
            if not np.isfinite(array).all():
                raise RuntimeError("nonfinite simulated output")
            checked.append({"shape": list(array.shape), "dtype": str(array.dtype),
                            "elements": int(array.size), "bytes": int(array.nbytes)})
        result["simulator_outputs"] = checked
        result["simulated_output_bytes_total"] = sum(x["bytes"] for x in checked)
        result["host_simulator_passed"] = True
        result["status"] = "host_conversion_and_simulation_passed"
    finally:
        simulator.release()
    result["host_peak_rss_kib_process"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return result


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
        outcome = run(args.model, args.calibration)
        status.update(outcome)
    except Exception as exc:
        status["status"] = "conversion_or_simulation_failed"
        status["failure_type"] = type(exc).__name__
        status["failure_text"] = str(exc)[:600]
        status["host_peak_rss_kib_process"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(traceback.format_exc(limit=8), file=sys.stderr)
        code = 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True),
                           encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, sort_keys=True), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
