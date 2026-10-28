"""PC-only opt-in A/B of two 9B image classification prompts.

The same approved, EXIF-stripped JPEG is sent twice to the same local Ollama,
without saving a photo, model transcript or memory. A/B acceptance is NOT a
claim of correct recognition. The physical robot is never contacted.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time
import uuid

from .ollama_local_client import OllamaEndpoint
from .qwen9b_advisor_v2 import (
    ImageQuestion, MAX_SOURCE_BYTES, Qwen9BPCClient, prepare_jpeg,
)


def compare_approved_image(
        source: bytes, *, consent: bool, operator_reviewed: bool,
        port: int = 11435, timeout_s: float = 120,
        client: Qwen9BPCClient | None = None) -> tuple[dict, bool]:
    """Two authorized local calls, identical pixels and schemas, differing prompts.

    Only closed enums and local timing reach the returned report. A rejected,
    stale or unavailable first request prevents a second request.
    """
    if type(consent) is not bool or not consent or type(operator_reviewed) is not bool or not operator_reviewed:
        raise ValueError("explicit operator approval for two calls is required")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid local Ollama port")
    if (type(timeout_s) not in (int, float) or not math.isfinite(timeout_s)
            or not 0 < timeout_s <= 180):
        raise ValueError("timeout must be bounded")
    if type(source) is not bytes or not 0 < len(source) <= MAX_SOURCE_BYTES:
        raise ValueError("invalid bounded input image")
    jpeg = prepare_jpeg(source)
    if client is None:
        client = Qwen9BPCClient(OllamaEndpoint(f"http://127.0.0.1:{port}"))
    if not isinstance(client, Qwen9BPCClient):
        raise TypeError("F5 v2 PC-only client required")

    samples = []
    for mode in ("simple", "balanced"):
        now = time.monotonic()
        question = ImageQuestion(
            uuid.uuid4().hex, jpeg, "unknown", True, True, now, now + timeout_s)
        result = client.query(question, timeout_s=timeout_s, mode=mode)
        observation = result.visual_observation
        samples.append({
            "mode": mode,
            "status": result.status,
            "visual_observation": ({
                "category": observation.category,
                "depiction": observation.depiction,
                "visibility": observation.visibility,
                "verified": False,
            } if observation is not None else None),
            "diagnostic_stage": result.diagnostic_stage,
            "diagnostic_reason": result.diagnostic_reason,
            "latency_s": round(result.latency_s or 0.0, 3),
        })
        if result.status != "unverified" or observation is None:
            break
    complete = len(samples) == 2 and all(s["status"] == "unverified" for s in samples)
    return ({
        "test": "qwen9b_same_image_prompt_comparison",
        "result": "comparison_completed" if complete else "comparison_incomplete",
        "samples": samples,
        "model": "qwen3.5:9b",
        "memory_writes": 0,
        "motor_commands_issued": 0,
        "photos_saved_by_companion": 0,
        "verified_recognition": False,
    }, complete)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two untrusted visual prompts for the same authorized photo")
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--authorize-image", action="store_true")
    parser.add_argument("--reviewed-no-private-subjects", action="store_true")
    parser.add_argument("--ollama-port", type=int, default=11435)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args()
    if not args.authorize_image or not args.reviewed_no_private_subjects:
        parser.error("operator must explicitly approve this photo and both local calls")
    try:
        if args.image.stat().st_size > MAX_SOURCE_BYTES:
            parser.error("source image exceeds 2 MB")
        source = args.image.read_bytes()
    except OSError:
        parser.error("image file not found or unreadable")
    try:
        report, complete = compare_approved_image(
            source, consent=True, operator_reviewed=True,
            port=args.ollama_port, timeout_s=args.timeout)
    except ValueError as exc:
        # Fixed local input error, never a raw model transcript.
        parser.error(str(exc))
    print(json.dumps(report, sort_keys=True))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())