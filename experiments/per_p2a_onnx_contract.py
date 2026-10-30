"""PER-P2A: read official Rockchip PP-YOLOE-s ONNX METADATA, never run AI.

Research gate only. Does not quantize, import rknn, invoke ONNX Runtime,
open camera, write model/media or connect to a robot. Vendor bench != Kwipi.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import resource
import sys
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

# Frozen source: Rockchip rknn_model_zoo@837db8e, examples/ppyoloe/model.
OFFICIAL_URL = (
    "https://ftrg.zbox.filez.com/v2/delivery/data/"
    "95f00b0fc900458ba134f8b180b3f7a1/examples/ppyoloe/ppyoloe_s.onnx"
)
AUTHORIZED_HOST = "ftrg.zbox.filez.com"
MAX_MODEL_BYTES = 64 * 1024 * 1024
MIN_MODEL_BYTES = 128 * 1024
EXPECTED_INPUT = (1, 3, 640, 640)
EXPECTED_SCALES = (80, 40, 20)
OUTPUT_CHANNELS = frozenset((1, 4, 80))


def require_authorized_url(url: str) -> None:
    """Only public HTTPS Rockchip-hosted file, no arbitrary model or redirect."""
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname != AUTHORIZED_HOST
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in (None, 443)
            or not parsed.path.startswith(
                "/v2/delivery/data/95f00b0fc900458ba134f8b180b3f7a1/"
            ) or parsed.query or parsed.fragment):
        raise ValueError("model endpoint not the preapproved Rockchip source")


def bounded_read(reader) -> bytes:
    """Fail closed on missing, empty or oversized public model bytes."""
    chunks = []
    count = 0
    while True:
        chunk = reader.read(min(1024 * 1024, MAX_MODEL_BYTES - count + 1))
        if not chunk:
            break
        count += len(chunk)
        if count > MAX_MODEL_BYTES:
            raise ValueError("public model exceeds preregistered 64 MiB limit")
        chunks.append(chunk)
    if count < MIN_MODEL_BYTES:
        raise ValueError("public model too small to inspect")
    return b"".join(chunks)


def validate_shapes(inputs: list[list[int]], outputs: list[list[int]]) -> dict:
    """Exact Rockchip *example* Ppyoloe_s tensor expectations; NOT OEM head."""
    if inputs != [list(EXPECTED_INPUT)]:
        raise ValueError("unexpected ONNX input shape; 640 NCHW required")
    if type(outputs) is not list or len(outputs) not in (6, 9):
        raise ValueError("expected 6 or 9 Rockchip branch outputs")
    scales: dict[int, list[int]] = {s: [] for s in EXPECTED_SCALES}
    for dims in outputs:
        if (type(dims) is not list or len(dims) != 4
                or any(type(x) is not int or x <= 0 for x in dims)):
            raise ValueError("ONNX outputs must be static positive NCHW")
        batch, channel, h, w = dims
        if (batch != 1 or h != w or h not in scales
                or channel not in OUTPUT_CHANNELS):
            raise ValueError("non-PPYOLOE output scale, shape or channel count")
        scales[h].append(channel)
    count_per_scale = len(outputs) // len(EXPECTED_SCALES)
    for s, channels in scales.items():
        if (len(channels) != count_per_scale
                or set(channels) not in ({4, 80}, {1, 4, 80})
                or len(set(channels)) != count_per_scale):
            raise ValueError(f"missing or duplicated box/class branch at {s}")
    return {
        "branch_scales": list(EXPECTED_SCALES),
        "channels_by_scale": {str(s): sorted(chs)
                              for s, chs in scales.items()},
        "class_channels": 80,
        "outputs": len(outputs),
        "rockchip_ppyoloe_example_shape_match": True,
        "oem_duck_detect_head_compatible": False,
    }


def _tensor_shape(value) -> list[int]:
    shape = value.type.tensor_type.shape
    dims = []
    for entry in shape.dim:
        if entry.WhichOneof("value") != "dim_value" or entry.dim_value <= 0:
            raise ValueError("dynamic / unbounded tensor dimension refused")
        dims.append(int(entry.dim_value))
    return dims


def probe() -> dict:
    require_authorized_url(OFFICIAL_URL)
    import onnx  # Optional isolated host-only dependency, never on the robot.

    started = time.perf_counter()
    req = Request(OFFICIAL_URL, headers={"User-Agent": "kwipi-public-metadata-check/1.0"})
    with urlopen(req, timeout=30) as response:
        require_authorized_url(response.geturl())  # refuse external redirects
        payload = bounded_read(response)
    size = len(payload)
    digest = hashlib.sha256(payload).hexdigest()
    downloaded_s = time.perf_counter() - started
    model = onnx.load_from_string(payload)
    onnx.checker.check_model(model)
    inputs = [_tensor_shape(x) for x in model.graph.input]
    outputs = [_tensor_shape(x) for x in model.graph.output]
    compat = validate_shapes(inputs, outputs)
    elapsed = time.perf_counter() - started
    return {
        "study": "PER-P2A_official_Rockchip_ppyoloes_ONNX_metadata_only",
        "source_repository_sha": "837db8e992815ff8647eadb709f07067f4bc3a71",
        "model": "ppyoloe_s",
        "original_model_url_host": AUTHORIZED_HOST,
        "downloaded_sha256_FIRST_OBSERVATION_NOT_PINNED": digest,
        "downloaded_bytes": size,
        "downloaded_mib": round(size / 1048576, 3),
        "onnx_ir_version": int(model.ir_version),
        "onnx_opset_imports": [{"domain": x.domain, "version": x.version}
                               for x in model.opset_import],
        "inputs": inputs,
        "outputs": outputs,
        "rockchip_contract": compat,
        "download_seconds_runner": round(downloaded_s, 3),
        "total_seconds_runner": round(elapsed, 3),
        "peak_host_process_rss_kib": resource.getrusage(
            resource.RUSAGE_SELF).ru_maxrss,
        "benchmark_vendor_rk3566_rk3568_int8_fps_not_robot": 17.6,
        "weights_rights_verified_for_public_redistribution": False,
        "robot_npu_driver_memory_thermal_or_accuracy_validated": False,
        "no_model_saved_or_published": True,
        "inferences_executed": 0,
        "motor_commands": 0,
        "next_status": "host_structure_probed_only_not_selected",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-public-download", action="store_true")
    args = parser.parse_args(argv)
    if not args.approve_public_download:
        parser.error("explicit Rockchip public ONNX metadata download required")
    try:
        result = probe()
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, RuntimeError, OSError, TimeoutError) as exc:
        print(f"PER-P2A STOP: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
