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


def run_check(*, port: int = 11435, timeout_s: float = 120) -> tuple[dict, bool]:
    if not 1 <= port <= 65535 or not 0 < timeout_s <= 180:
        raise ValueError("invalid local port or timeout")
    client = Qwen9BPCClient(OllamaEndpoint(f"http://127.0.0.1:{port}"))
    samples = []
    for expected in ("red", "blue"):
        question = make_synthetic_color_question(expected, timeout_s=timeout_s)
        result = client.query(question, timeout_s=timeout_s, mode="color_probe")
        samples.append({
            "expected": expected,
            "observed": result.probe_color,  # accepted closed enum, never raw text
            "status": result.status,
            "diagnostic_stage": result.diagnostic_stage,
            "diagnostic_reason": result.diagnostic_reason,
            "latency_s": round(result.latency_s or 0.0, 3),
        })
        if result.status != "unverified":
            # Do not issue a second request after an invalid/failed first call.
            break
    passed = (len(samples) == 2 and all(
        item["status"] == "unverified" and item["observed"] == item["expected"]
        for item in samples))
    return ({
        "test": "qwen9b_synthetic_color_vision",
        "result": "two_colors_distinguished" if passed else "not_demonstrated",
        "samples": samples,
        "motor_commands_issued": 0,
        "memory_writes": 0,
        "private_images_read": 0,
    }, passed)


def main() -> int:
    p = argparse.ArgumentParser(description="PC-only synthetic image vision diagnostic")
    p.add_argument("--ollama-port", type=int, default=11435)
    p.add_argument("--timeout", type=float, default=120)
    args = p.parse_args()
    if not 1 <= args.ollama_port <= 65535 or not 0 < args.timeout <= 180:
        p.error("bounded local port and timeout required")
    result, passed = run_check(port=args.ollama_port, timeout_s=args.timeout)
    print(json.dumps(result, sort_keys=True))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())