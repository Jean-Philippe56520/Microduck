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
from .qwen9b_production_role_v2 import (
    ROLE_VERSION as ROLE_VERSION_V2,
    SCENARIO_USER_PROMPT as SCENARIO_USER_PROMPT_V2,
    SYSTEM_PROMPT as SYSTEM_PROMPT_V2,
)

MODEL = "qwen3.5:9b"
MAX_WIRE_BYTES = 180_000
MAX_RESPONSE_BYTES = 16_384
MAX_TEXT_CHARS = 1_200
MAX_TIMEOUT = 180.0


def _role_prompts(version: str) -> tuple[str, str]:
    if type(version) is not str:
        raise ValueError("invalid role version")
    if version == ROLE_VERSION:
        return SYSTEM_PROMPT, SCENARIO_USER_PROMPT
    if version == ROLE_VERSION_V2:
        return SYSTEM_PROMPT_V2, SCENARIO_USER_PROMPT_V2
    raise ValueError("unrecognized role version")


def make_request(image: bytes, *, role_version: str = ROLE_VERSION) -> bytes:
    if type(image) is not bytes or not 0 < len(image) <= MAX_IMAGE_BYTES:
        raise ValueError("invalid approved JPEG budget")
    system_prompt, scenario_prompt = _role_prompts(role_version)
    request = {
        "model": MODEL, "stream": False, "think": False, "keep_alive": "0",
        "options": {"temperature": 0, "num_predict": 180, "num_ctx": 4096},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": scenario_prompt,
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


def _envelope_diagnostic(envelope: Any) -> str | None:
    """Explain only protocol failure class. Never expose Ollama output or image."""
    if type(envelope) is not dict:
        return "envelope_invalid"
    if envelope.get("model") != MODEL:
        return "model_mismatch"
    if envelope.get("done") is not True:
        return "response_incomplete"
    reason = envelope.get("done_reason")
    if reason == "length":
        return "generation_truncated"
    if reason not in (None, "stop"):
        return "stop_reason_invalid"
    message = envelope.get("message")
    if type(message) is not dict or message.get("role") != "assistant":
        return "message_invalid"
    if message.get("tool_calls"):
        return "tool_calls_rejected"
    if message.get("thinking") not in (None, ""):
        return "thinking_rejected"
    return None


def evaluate_local_image(source: bytes, *, consent: bool, reviewed: bool,
                         port: int = 11435, timeout_s: float = 120,
                         endpoint: OllamaEndpoint | None = None,
                         role_version: str = ROLE_VERSION) -> dict[str, Any]:
    """Return a bounded human-preview transcript, NEVER validated robot facts."""
    if consent is not True or reviewed is not True:
        raise ValueError("explicit operator review and single-image consent required")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError("invalid local port")
    if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or not 0 < timeout_s <= MAX_TIMEOUT:
        raise ValueError("invalid bounded timeout")
    if type(source) is not bytes or not 0 < len(source) <= MAX_SOURCE_BYTES:
        raise ValueError("invalid image input")
    _role_prompts(role_version)
    target = endpoint if endpoint is not None else OllamaEndpoint(f"http://127.0.0.1:{port}")
    if not isinstance(target, OllamaEndpoint):
        raise ValueError("only shared F5-B endpoint allowed")
    host, dest_port = target.host_port
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError("image transfer restricted to loopback")
    jpeg = prepare_jpeg(source)  # Remove metadata; no file persistence.
    request = make_request(jpeg, role_version=role_version)
    start = time.monotonic()
    conn = None
    base = {"role_version": role_version, "model": MODEL, "status": "unavailable",
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
        diagnostic = _envelope_diagnostic(envelope)
        if diagnostic is not None:
            rejected = {**base, "status": "rejected", "diagnostic": diagnostic}
            if diagnostic == "generation_truncated":
                # Numeric-only telemetry helps tune the token budget safely.
                rejected["elapsed_s"] = round(time.monotonic() - start, 3)
                rejected["server_total_s"] = _positive_nano(envelope, "total_duration")
                rejected["generated_tokens"] = (envelope.get("eval_count")
                                                if type(envelope.get("eval_count")) is int else None)
            return rejected
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
    p.add_argument("--role", choices=("v1", "v2"), default="v1")
    p.add_argument("--authorize-image", action="store_true")
    p.add_argument("--reviewed-no-private-subjects", action="store_true")
    args = p.parse_args()
    if not args.authorize_image or not args.reviewed_no_private_subjects:
        p.error("explicit review and consent required")
    try:
        if args.image.stat().st_size > MAX_SOURCE_BYTES:
            p.error("source image exceeds 2 MB")
        source = args.image.read_bytes()
        role_version = ROLE_VERSION_V2 if args.role == "v2" else ROLE_VERSION
        report = evaluate_local_image(source, consent=True, reviewed=True,
                                      port=args.ollama_port, timeout_s=args.timeout,
                                      role_version=role_version)
    except (OSError, ValueError) as exc:
        p.error("image unavailable or invalid; no Ollama request was sent")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report["status"] == "unverified" else 2


if __name__ == "__main__":
    raise SystemExit(main())