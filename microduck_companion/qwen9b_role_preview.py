"""Operator-opt-in local dry-run of the versioned Qwen3.5 9B production role.

Not a deployed robot service. One authorized image, no motor, memory, cloud,
robot hardware, automated feedback or second inference. Text is untrusted.
"""
from __future__ import annotations

import argparse
import base64
import http.client
import ipaddress
import json
import math
from pathlib import Path
import socket
import time
from typing import Any

from .ollama_local_client import OllamaEndpoint
from .qwen9b_advisor_v2 import MAX_SOURCE_BYTES, MAX_IMAGE_BYTES, prepare_jpeg
from .qwen9b_production_role import ROLE_VERSION, SCENARIO_USER_PROMPT, SYSTEM_PROMPT

MODEL = "qwen3.5:9b"
MAX_WIRE_BYTES = 180_000
MAX_RESPONSE_BYTES = 16_384
MAX_TEXT_CHARS = 1_200
MAX_TIMEOUT = 180.0


def make_request(image: bytes) -> bytes:
    if type(image) is not bytes or not 0 < len(image) <= MAX_IMAGE_BYTES:
        raise ValueError("invalid approved JPEG budget")
    request = {
        "model": MODEL, "stream": False, "think": False, "keep_alive": "0",
        "options": {"temperature": 0, "num_predict": 180, "num_ctx": 4096},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": SCENARIO_USER_PROMPT,
             "images": [base64.b64encode(image).decode("ascii")]},
        ],
    }
    data = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_WIRE_BYTES:
        raise ValueError("wire budget exceeded")
    return data


def _positive_nano(obj: dict[str, Any], key: str) -> float | None:
    value = obj.get(key)
    if type(value) is int and value >= 0:
        return round(value / 1_000_000_000, 3)
    return None


def evaluate_local_image(source: bytes, *, consent: bool, reviewed: bool,
                         port: int = 11435, timeout_s: float = 120,
                         endpoint: OllamaEndpoint | None = None) -> dict[str, Any]:
    """Return a bounded human-preview transcript, NEVER validated robot facts."""
    if consent is not True or reviewed is not True:
        raise ValueError("explicit operator review and single-image consent required")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid local port")
    if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or not 0 < timeout_s <= MAX_TIMEOUT:
        raise ValueError("invalid bounded timeout")
    if type(source) is not bytes or not 0 < len(source) <= MAX_SOURCE_BYTES:
        raise ValueError("invalid image input")
    target = endpoint if endpoint is not None else OllamaEndpoint(f"http://127.0.0.1:{port}")
    if not isinstance(target, OllamaEndpoint):
        raise ValueError("only shared F5-B endpoint allowed")
    host, dest_port = target.host_port
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError("image transfer restricted to loopback")
    jpeg = prepare_jpeg(source)  # Remove metadata; no file persistence.
    request = make_request(jpeg)
    start = time.monotonic()
    conn = None
    base = {"role_version": ROLE_VERSION, "model": MODEL, "status": "unavailable",
            "unverified": True, "motor_commands_issued": 0, "memory_writes": 0,
            "photos_saved_by_companion": 0}
    try:
        conn = http.client.HTTPConnection(host, dest_port, timeout=float(timeout_s))
        conn.request("POST", "/api/chat", body=request,
                     headers={"Content-Type": "application/json", "Connection": "close"})
        resp = conn.getresponse()
        if resp.status != 200 or resp.getheader("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return {**base, "status": "rejected", "diagnostic": "http_protocol"}
        body = resp.read(MAX_RESPONSE_BYTES + 1)
        if not 0 < len(body) <= MAX_RESPONSE_BYTES:
            return {**base, "status": "rejected", "diagnostic": "envelope_size"}
        envelope = json.loads(body.decode("utf-8"))
        if (type(envelope) is not dict or envelope.get("model") != MODEL
                or envelope.get("done") is not True
                or envelope.get("done_reason") not in (None, "stop")
                or type(envelope.get("message")) is not dict
                or envelope["message"].get("role") != "assistant"
                or envelope["message"].get("tool_calls")
                or envelope["message"].get("thinking") not in (None, "")):
            return {**base, "status": "rejected", "diagnostic": "envelope_invalid"}
        answer = envelope["message"].get("content")
        if type(answer) is not str or not 0 < len(answer) <= MAX_TEXT_CHARS:
            return {**base, "status": "rejected", "diagnostic": "model_text_size"}
        # A syntactically valid answer is NOT a verified observation.
        return {**base, "status": "unverified", "advisor_text": answer,
                "elapsed_s": round(time.monotonic() - start, 3),
                "server_total_s": _positive_nano(envelope, "total_duration"),
                "load_s": _positive_nano(envelope, "load_duration"),
                "image_prompt_s": _positive_nano(envelope, "prompt_eval_duration"),
                "generation_s": _positive_nano(envelope, "eval_duration"),
                "generated_tokens": envelope.get("eval_count") if type(envelope.get("eval_count")) is int else None}
    except (OSError, TimeoutError, socket.timeout):
        return {**base, "status": "unavailable", "diagnostic": "transport_or_timeout"}
    except (UnicodeError, json.JSONDecodeError, ValueError):
        return {**base, "status": "rejected", "diagnostic": "envelope_invalid"}
    finally:
        if conn is not None:
            conn.close()


def main() -> int:
    p = argparse.ArgumentParser(description="Opt-in production ROLE dry-run on PC, never a robot deployment")
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--ollama-port", type=int, default=11435)
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--authorize-image", action="store_true")
    p.add_argument("--reviewed-no-private-subjects", action="store_true")
    args = p.parse_args()
    if not args.authorize_image or not args.reviewed_no_private_subjects:
        p.error("explicit review and consent required")
    try:
        if args.image.stat().st_size > MAX_SOURCE_BYTES:
            p.error("source image exceeds 2 MB")
        source = args.image.read_bytes()
        report = evaluate_local_image(source, consent=True, reviewed=True,
                                      port=args.ollama_port, timeout_s=args.timeout)
    except (OSError, ValueError) as exc:
        p.error("image unavailable or invalid; no Ollama request was sent")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "unverified" else 2


if __name__ == "__main__":
    raise SystemExit(main())