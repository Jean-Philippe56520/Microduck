"""Operator-invoked, PC-only Qwen3.5 9B synthetic color vision smoke test.

No user media, images on disk, internet calls, motor or SQLite. A pass only
suggests the model distinguishes two simple image inputs; it is NOT a claim
of real-object recognition, NPU support or safe autonomous behavior.
"""
from __future__ import annotations

import argparse
import io
import json
import time
import uuid

from .ollama_local_client import OllamaEndpoint
from .ollama_device_placement import LocalOllamaModelSampler
from .qwen9b_advisor_v2 import ImageQuestion, Qwen9BPCClient, prepare_jpeg


def make_synthetic_color_question(color: str, *, timeout_s: float = 120) -> ImageQuestion:
    """Build a uniform red/blue JPEG fully in memory; no private file reads."""
    if color not in ("red", "blue"):
        raise ValueError("only known synthetic calibration colors")
    if not 0 < timeout_s <= 180:
        raise ValueError("timeout must be bounded")
    from PIL import Image
    image = Image.new("RGB", (256, 256), (255, 0, 0) if color == "red" else (0, 0, 255))
    output = io.BytesIO()
    image.save(output, format="PNG")
    jpeg = prepare_jpeg(output.getvalue())
    now = time.monotonic()
    # Consent and review are implicit ONLY for these programmatically constructed
    # constant-color images, explicitly requested by running this test command.
    return ImageQuestion(uuid.uuid4().hex, jpeg, "unknown", True, True,
                         now, now + timeout_s)


def run_check(*, port: int = 11435, timeout_s: float = 120,
              report_placement: bool = False) -> tuple[dict, bool]:
    """Two synthetic-only color inferences; optional sampled PC model placement.

    The sampler reads only localhost /api/ps in a daemon thread. It cannot
    change the Ollama runner, preload weights or authorize a robot action.
    """
    if type(port) is not int or not 1 <= port <= 65535 or not 0 < timeout_s <= 180:
        raise ValueError("invalid local port or timeout")
    if type(report_placement) is not bool:
        raise ValueError("explicit boolean placement reporting required")
    client = Qwen9BPCClient(OllamaEndpoint(f"http://127.0.0.1:{port}"))
    sampler = LocalOllamaModelSampler(port=port) if report_placement else None
    if sampler is not None:
        sampler.start()
    samples = []
    try:
        for expected in ("red", "blue"):
            question = make_synthetic_color_question(expected, timeout_s=timeout_s)
            result = client.query(question, timeout_s=timeout_s, mode="color_probe")
            samples.append({
                "expected": expected,
                "observed": result.probe_color,  # closed enum, never raw model text
                "status": result.status,
                "diagnostic_stage": result.diagnostic_stage,
                "diagnostic_reason": result.diagnostic_reason,
                "latency_s": round(result.latency_s or 0.0, 3),
            })
            if result.status != "unverified":
                # Do not issue a second request after a rejected/failed first call.
                break
    finally:
        if sampler is not None:
            sampler.stop()
    passed = (len(samples) == 2 and all(
        item["status"] == "unverified" and item["observed"] == item["expected"]
        for item in samples))
    report = {
        "test": "qwen9b_synthetic_color_vision",
        "result": "two_colors_distinguished" if passed else "not_demonstrated",
        "samples": samples,
        "motor_commands_issued": 0,
        "memory_writes": 0,
        "private_images_read": 0,
    }
    if sampler is not None:
        report["ollama_placement"] = sampler.report()
    return report, passed


def main() -> int:
    p = argparse.ArgumentParser(description="PC-only synthetic image vision diagnostic")
    p.add_argument("--ollama-port", type=int, default=11435)
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--report-placement", action="store_true",
                   help="opt-in loopback read-only Ollama GPU memory residency sampling")
    args = p.parse_args()
    if not 1 <= args.ollama_port <= 65535 or not 0 < args.timeout <= 180:
        p.error("bounded local port and timeout required")
    result, passed = run_check(port=args.ollama_port, timeout_s=args.timeout,
                               report_placement=args.report_placement)
    print(json.dumps(result, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())