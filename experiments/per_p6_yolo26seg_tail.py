"""PER-P6: confirm YOLO26n-seg RKNN raw heads -> ONNX CPU tail -> binary masks.

Host and pinned Rockchip SDK simulator only. No model/runtime patch, no robot,
camera, memory write, Qwen, motors or source/model/image artifact publication.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import resource
import sys
import time
import traceback

from experiments.per_p5_yolo26_rknn_compat import (
    INPUT_SIZE,
    MAX_BYTES,
    MODELS,
    _cropped_head_outputs,
    _ok,
    _tensors,
    verify_sources,
)

MODEL_NAME = "yolo26n-seg.pt"
PUBLIC_IMAGE = "000000005001.jpg"
PRECISION_ATOL = 1e-4
PRECISION_RTOL = 1e-4


def _require_finite(outputs, expected_count, label):
    import numpy as np

    if not isinstance(outputs, (list, tuple)) or len(outputs) != expected_count:
        raise ValueError(f"{label}: wrong output count")
    arrays = [np.asarray(value) for value in outputs]
    if any(not x.size or x.dtype.kind not in "fiu" or not np.isfinite(x).all() for x in arrays):
        raise ValueError(f"{label}: invalid, empty, or non-finite tensors")
    return arrays


def make_segment_tail(onnx_path: Path, out_path: Path, heads: list[str]) -> dict:
    """Preserve prototype output1 as an explicit passthrough of the RKNN tenth output.

    The pinned Ultralytics 8.4.192 exporter cuts raw head convolutions but cannot
    extract output1 as both the original graph's output and a tail dependency.
    Only the actual box/score/mask-coefficient decode lives in this extracted graph.
    """
    import onnx

    full = onnx.load(str(onnx_path))
    onnx.checker.check_model(full)
    output_by_name = {x.name: x for x in full.graph.output}
    if set(output_by_name) != {"output0", "output1"} or len(full.graph.output) != 2:
        raise ValueError("segment ONNX must have output0 and output1 only")
    if len(heads) != 9 or len(set(heads)) != 9 or "output1" in heads or "output0" in heads:
        raise ValueError("expected nine distinct raw convolution heads")
    if len(set(heads) - {x for n in full.graph.node for x in n.output}) != 0:
        raise ValueError("a required raw head is not in source ONNX graph")
    prototype = output_by_name["output1"]
    if prototype.type.tensor_type.elem_type != onnx.TensorProto.FLOAT:
        raise ValueError("unexpected prototype tensor dtype")
    dims = [d.dim_value for d in prototype.type.tensor_type.shape.dim]
    if dims != [1, 32, 160, 160]:
        raise ValueError(f"unexpected prototype tensor shape: {dims}")
    out0 = output_by_name["output0"]
    out0_dims = [d.dim_value for d in out0.type.tensor_type.shape.dim]
    if out0_dims != [1, 300, 38]:
        raise ValueError(f"unexpected decoded segment output: {out0_dims}")

    # Let ONNX's standard extractor discover the decoder dependency graph.
    # Prototypes travel separately as an RKNN tensor, not via the box decoder.
    onnx.utils.extract_model(
        str(onnx_path), str(out_path), heads, ["output0"]
    )
    tail = onnx.load(str(out_path))
    if len(tail.graph.input) != 9 or len(tail.graph.output) != 1:
        raise ValueError("extracted decoder has unexpected I/O")
    if {x.name for x in tail.graph.input} != set(heads):
        raise ValueError("extracted decoder raw head names changed")
    proto_input = onnx.helper.make_tensor_value_info(
        "rknn_mask_prototypes", onnx.TensorProto.FLOAT, dims
    )
    tail.graph.input.append(proto_input)  # P5 simulator's tenth output, by position
    tail.graph.node.append(
        onnx.helper.make_node("Identity", ["rknn_mask_prototypes"], ["output1"],
                              name="rknn_prototype_passthrough")
    )
    tail.graph.output.append(prototype)
    onnx.checker.check_model(tail)
    onnx.save(tail, str(out_path))
    return {"tail_bytes": out_path.stat().st_size,
            "tail_inputs": _tensors(tail.graph.input),
            "tail_outputs": _tensors(tail.graph.output)}


def make_onnx_raw_head_probe(source: Path, output: Path, heads: list[str]) -> None:
    """Re-export intermediate raw heads from the same unchanged source ONNX."""
    import onnx

    graph = onnx.shape_inference.infer_shapes(onnx.load(str(source)))
    onnx.checker.check_model(graph)
    infos = {v.name: v for v in graph.graph.value_info}
    if len(heads) != 9 or any(name not in infos for name in heads):
        raise ValueError("ONNX shape inference omitted required raw head metadata")
    for name in heads:
        graph.graph.output.append(infos[name])
    onnx.checker.check_model(graph)
    onnx.save(graph, str(output))


def _mask_digest(decoded, proto, report, key: str) -> None:
    """Use official Ultralytics NMS + process_mask, not a novel mask decoder."""
    import torch
    from ultralytics.utils import nms, ops

    if tuple(decoded.shape) != (1, 300, 38) or tuple(proto.shape) != (1, 32, 160, 160):
        raise ValueError(f"{key}: decoded/prototype shape mismatch")
    pred = nms.non_max_suppression(
        torch.from_numpy(decoded).float(), conf_thres=0.25, iou_thres=0.5,
        max_det=10, nc=80, end2end=True,
    )[0]
    if pred.ndim != 2 or pred.shape[1] != 38:
        raise RuntimeError(f"{key}: unexpected post-NMS shape")
    if len(pred):
        masks = ops.process_mask(
            torch.from_numpy(proto[0]).float(), pred[:, 6:], pred[:, :4],
            (INPUT_SIZE, INPUT_SIZE), upsample=False
        )
    else:
        masks = torch.zeros((0, 160, 160), dtype=torch.uint8)
    if tuple(masks.shape) != (len(pred), 160, 160):
        raise RuntimeError(f"{key}: bad mask dimensions")
    count = int((masks.flatten(1).sum(1) > 0).sum().item()) if len(masks) else 0
    report[f"{key}_detections_conf025"] = int(len(pred))
    report[f"{key}_nonempty_masks"] = count
    report[f"{key}_mask_total_true_pixels"] = int(masks.sum().item())
    report[f"{key}_mask_output_bytes"] = int(masks.numel() * masks.element_size())
    # Zero masks on this single public calibration image is not a quality score.


def run(weight: Path, calibration: Path, report: dict, parity_hook=None) -> None:
    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch
    import ultralytics
    from importlib.metadata import version
    from PIL import Image
    from rknn.api import RKNN
    from ultralytics import YOLO

    if weight.name != MODEL_NAME or ultralytics.__version__ != "8.4.192":
        raise ValueError("wrong weight or Ultralytics version")
    if version("rknn-toolkit2") != "2.3.2" or not str(torch.__version__).startswith("2.4.0"):
        raise ValueError("wrong pinned SDK/Torch versions")
    report.update(verify_sources(weight, calibration))
    image = calibration.parent / "subset" / PUBLIC_IMAGE
    if image.is_symlink() or not image.is_file():
        raise ValueError("the preregistered public diagnostic image is absent")
    with Image.open(image) as pic:
        rgb = np.asarray(pic.convert("RGB").resize(
            (INPUT_SIZE, INPUT_SIZE), Image.Resampling.BILINEAR
        ), dtype=np.uint8)
    if rgb.shape != (640, 640, 3):
        raise ValueError("unexpected input RGB shape")
    model = YOLO(str(weight))
    if model.task != "segment":
        raise ValueError("unexpected official task")
    prefix = f"/model.{len(model.model.model) - 1}/"
    onnx_path = Path(model.export(format="onnx", imgsz=INPUT_SIZE, batch=1,
                                  opset=19, simplify=False, dynamic=False, nms=False))
    full = onnx.load(str(onnx_path))
    onnx.checker.check_model(full)
    heads = _cropped_head_outputs(full.graph, prefix, "segment")
    if len(heads) != 10 or heads[-1] != "output1":
        raise ValueError("unexpected raw seg head order")
    folder = weight.parent / "per-p6-tail-artifacts-local-only"
    folder.mkdir(exist_ok=True)
    tail_path = folder / "tail.onnx"
    report.update(make_segment_tail(onnx_path, tail_path, heads[:-1]))
    probe_path = folder / "raw-head-probe.onnx"
    make_onnx_raw_head_probe(onnx_path, probe_path, heads[:-1])
    tail_session = ort.InferenceSession(str(tail_path), providers=["CPUExecutionProvider"])
    full_session = ort.InferenceSession(str(probe_path), providers=["CPUExecutionProvider"])
    if [t.name for t in tail_session.get_inputs()] != heads[:-1] + ["rknn_mask_prototypes"]:
        raise RuntimeError("ONNX tail input ordering is not RKNN-compatible")
    if [t.name for t in tail_session.get_outputs()] != ["output0", "output1"]:
        raise RuntimeError("tail output ordering is wrong")
    chw = np.transpose(rgb.astype(np.float32) / 255.0, (2, 0, 1))[None]
    started = time.perf_counter()
    full_outputs = full_session.run(None, {"images": chw})
    report["whole_onnx_with_raw_probe_ms"] = round((time.perf_counter()-started)*1000, 2)
    original0, original1, *raw = _require_finite(full_outputs, 11, "full ONNX")
    if len(raw) != 9:
        raise RuntimeError("ONNX raw head extraction lost a head")
    feed = dict(zip(heads[:-1], raw))
    feed["rknn_mask_prototypes"] = original1
    started = time.perf_counter()
    tail_onnx0, tail_onnx1 = _require_finite(
        tail_session.run(None, feed), 2, "tail on original ONNX heads"
    )
    report["tail_cpu_onnx_ms"] = round((time.perf_counter()-started)*1000, 2)
    delta = float(np.max(np.abs(original0-tail_onnx0)))
    report["tail_vs_whole_onnx_max_abs"] = delta
    if not np.allclose(original0, tail_onnx0, atol=PRECISION_ATOL, rtol=PRECISION_RTOL):
        raise RuntimeError("tail decoded boxes/scores/coefficients differ from original ONNX")
    if not np.array_equal(original1, tail_onnx1):
        raise RuntimeError("segment prototype passthrough differs from original")
    report["onnx_tail_graph_parity_passed"] = True

    # Separate model path: raw outputs from toolkit simulator, NOT a physical RK3566.
    builder = RKNN(verbose=False)
    try:
        _ok(builder.config(mean_values=[[0,0,0]], std_values=[[255,255,255]],
                           target_platform="rk3566", auto_hybrid_cos_thresh=0.999),
            "config")
        _ok(builder.load_onnx(model=str(onnx_path), outputs=heads), "load_onnx")
        _ok(builder.build(do_quantization=True, dataset=str(calibration),
                          auto_hybrid=True, rknn_batch_size=1), "build")
        rknn_path = folder / "yolo26n-seg-rk3566.rknn"
        _ok(builder.export_rknn(str(rknn_path)), "export_rknn")
        size = rknn_path.stat().st_size
        if size <= 0 or size >= MAX_BYTES:
            raise RuntimeError("compiled RKNN size outside P6 gate")
        report["rknn_bytes"] = size
        report["host_rknn_conversion_passed"] = True
        _ok(builder.init_runtime(), "host_init_runtime")
        started = time.perf_counter()
        simulated = _require_finite(builder.inference(
            inputs=[rgb], data_format="nhwc"), 10, "RKNN host simulator"
        )
        report["one_host_simulator_raw_ms"] = round((time.perf_counter()-started)*1000, 2)
    finally:
        builder.release()
    for sim, reference in zip(simulated, raw + [original1]):
        if sim.shape != reference.shape:
            raise RuntimeError(f"RKNN raw simulator tensor shape {sim.shape} != {reference.shape}")
    feeds = dict(zip(heads[:-1], simulated[:9]))
    feeds["rknn_mask_prototypes"] = simulated[9]
    started = time.perf_counter()
    decoded, prototype = _require_finite(
        tail_session.run(None, feeds), 2, "tail on simulated RKNN heads"
    )
    report["tail_cpu_rknn_sim_ms"] = round((time.perf_counter()-started)*1000, 2)
    _mask_digest(original0, original1, report, "original_onnx")
    _mask_digest(decoded, prototype, report, "rknn_host_sim")
    if parity_hook is not None:
        parity_hook(decoded, prototype, report)  # P8 optional, same one SDK inference
    report["status"] = "complete_host_rknn_raw_tail_mask_pipeline_tested"
    report["host_tail_and_mask_pipeline_passed"] = True
    report["tail_only_after_sdk_simulation_not_robot"] = True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weight", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report = {
        "study": "PER-P6_one_public_calibration_image",
        "status": "not_executed",
        "robot_validated": False, "physical_robot_available": False,
        "NPU_measured": False, "OEM_detector_integrated": False,
        "license_for_deployment_verified": False,
        "memory_writes": 0, "motor_commands": 0,
        "host_rknn_conversion_passed": False,
        "onnx_tail_graph_parity_passed": False,
        "host_tail_and_mask_pipeline_passed": False,
    }
    exit_code = 0
    try:
        run(args.weight, args.calibration, report)
    except Exception as exc:
        report["status"] = "host_pipeline_failed_stop"
        report["error_type"] = type(exc).__name__
        report["error_text"] = str(exc)[:380]
        print(traceback.format_exc(limit=6), file=sys.stderr)
        exit_code = 1
    report["host_peak_process_rss_kib_including_compiler"] = (
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps(report, sort_keys=True), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
