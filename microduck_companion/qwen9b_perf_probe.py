"""QW-PERF-1: bounded, opt-in PC-only Qwen3.5 9B performance probe.

Uses one in-memory synthetic image, not a camera, user photo, or SQLite.
No motor, OEM, cloud, model install, transcript logging or learning.
This probe is NOT a production adviser or a semantic benchmark.
"""
from __future__ import annotations

import argparse
import base64
import http.client
import io
import ipaddress
import json
import math
import time
import uuid

from .ollama_local_client import OllamaEndpoint, _strict_json
from .qwen9b_advisor_v2 import prepare_jpeg
from .qwen9b_production_role_v2 import ROLE_VERSION
from .qwen9b_role_preview import MODEL, make_request

PROFILES = (
    "role_v2_first",
    "role_v2_repeat",
    "compact_text",
    "compact_json",
    "compact_json_mock_context",
)
KEEP_ALIVE = "2m"  # Experiment only, existing production defaults remain unchanged.
MAX_BODY = 180_000
MAX_REPLY = 16_384
MAX_TIMEOUT = 180
_SHAPES = ("circle", "square", "unknown")
_COLORS = ("red", "blue", "unknown")
_CONTEXT = (
    "SYNTHETIC FIXTURE ONLY. Goal: observe an unknown colored shape. "
    "History: one earlier mock observation with category unknown; "
    "zero verified physical encounters, actions or effects. "
    "No personal information or camera data."
)
_SYSTEM = (
    "You are a PC-only diagnostic, not a robot controller. Inspect the "
    "synthetic image. Return an uncertain observation only; never suggest "
    "a motor command or an identity. The image depicts a red circle on white."
)
_USER = "Describe the dominant foreground shape and its color."


def make_synthetic_jpeg() -> bytes:
    """Reuse the existing F5 v2 EXIF stripping and image limits."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (256, 256), "white")
    ImageDraw.Draw(image).ellipse((56, 56, 200, 200), fill="red")
    sink = io.BytesIO()
    image.save(sink, format="PNG")
    return prepare_jpeg(sink.getvalue())


def _compact_schema(request_id: str) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["request_id", "shape", "color"],
        "properties": {
            "request_id": {"type": "string", "enum": [request_id]},
            "shape": {"type": "string", "enum": list(_SHAPES)},
            "color": {"type": "string", "enum": list(_COLORS)},
        },
    }


def make_probe_request(profile: str, jpeg: bytes, request_id: str) -> bytes:
    if profile not in PROFILES or type(profile) is not str:
        raise ValueError("unrecognized performance profile")
    if type(request_id) is not str or len(request_id) != 32 or any(
            c not in "0123456789abcdef" for c in request_id):
        raise ValueError("invalid synthetic request id")
    if profile.startswith("role_v2"):
        payload = _strict_json(make_request(jpeg, role_version=ROLE_VERSION))
    else:
        user_text = _USER
        if profile == "compact_json_mock_context":
            user_text += "\n" + _CONTEXT
        payload = {
            "model": MODEL,
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 96, "num_ctx": 4096},
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_text,
                 "images": [base64.b64encode(jpeg).decode("ascii")]},
            ],
        }
        if profile.startswith("compact_json"):
            payload["format"] = _compact_schema(request_id)
    payload["keep_alive"] = KEEP_ALIVE
    wire = json.dumps(payload, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")
    if len(wire) > MAX_BODY:
        raise ValueError("bounded PC performance request exceeded")
    return wire


def _metric(data: dict, key: str, *, nanoseconds: bool = False) -> float | int | None:
    value = data.get(key)
    if type(value) is not int or value < 0:
        return None
    return round(value / 1_000_000_000, 4) if nanoseconds else value


def classify_envelope(data: object, *, profile: str, request_id: str) -> dict:
    """Fail closed; never return or record model text."""
    result = {"status": "rejected", "diagnostic": "envelope_invalid",
              "fixture_shape_color_match": None}
    if type(data) is not dict or data.get("model") != MODEL:
        return result
    msg = data.get("message")
    if (data.get("done") is not True or
            data.get("done_reason", "stop") not in ("stop", None) or
            type(msg) is not dict or msg.get("role") != "assistant" or
            msg.get("tool_calls") not in (None, []) or
            msg.get("images") not in (None, []) or
            msg.get("thinking") not in (None, "")):
        return {**result, "diagnostic": "model_protocol_rejected"}
    answer = msg.get("content")
    if type(answer) is not str or not 0 < len(answer) <= 1200:
        return {**result, "diagnostic": "response_size"}
    if profile.startswith("compact_json"):
        try:
            response = _strict_json(answer.encode("utf-8"))
        except (ValueError, UnicodeError, RecursionError):
            return {**result, "diagnostic": "json_invalid"}
        if (type(response) is not dict or
                set(response) != {"request_id", "shape", "color"} or
                response.get("request_id") != request_id or
                response.get("shape") not in _SHAPES or
                response.get("color") not in _COLORS):
            return {**result, "diagnostic": "schema_invalid"}
        return {"status": "unverified", "diagnostic": "none",
                "fixture_shape_color_match": (response["shape"] == "circle"
                                              and response["color"] == "red")}
    return {"status": "unverified", "diagnostic": "none",
            "fixture_shape_color_match": None}


def _read_one(endpoint: OllamaEndpoint, request: bytes, profile: str,
              request_id: str, timeout_s: float) -> dict:
    host, port = endpoint.host_port
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError("benchmark only supports loopback Ollama")
    start = time.monotonic()
    connection = None
    reply = None
    result = {"status": "unavailable", "diagnostic": "transport_or_timeout",
              "fixture_shape_color_match": None}
    try:
        connection = http.client.HTTPConnection(host, port, timeout=timeout_s)
        connection.request("POST", "/api/chat", request, headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Connection": "close",
        })
        reply = connection.getresponse()
        if reply.status != 200 or reply.getheader(
                "Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return {**result, "diagnostic": "http_rejected",
                    "wall_s": round(time.monotonic() - start, 4)}
        if (reply.getheader("Transfer-Encoding") is not None or
                reply.getheader("Content-Encoding", "identity").lower() not in
                ("identity", "") or
                not (reply.getheader("Content-Length") or "").isascii() or
                not (reply.getheader("Content-Length") or "").isdecimal()):
            return {**result, "diagnostic": "headers_rejected",
                    "wall_s": round(time.monotonic() - start, 4)}
        expected = int(reply.getheader("Content-Length"))
        if not 0 < expected <= MAX_REPLY:
            return {**result, "diagnostic": "envelope_size",
                    "wall_s": round(time.monotonic() - start, 4)}
        chunks = []
        received = 0
        while received < expected:
            remaining = start + timeout_s - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("absolute benchmark response deadline")
            raw = getattr(getattr(reply, "fp", None), "raw", None)
            sock = connection.sock if connection.sock is not None else getattr(
                raw, "_sock", None)
            if sock is None:
                raise ValueError("missing bounded read socket")
            sock.settimeout(remaining)
            block = reply.read1(min(4096, expected - received))
            if not block:
                raise ValueError("truncated envelope")
            chunks.append(block)
            received += len(block)
        if time.monotonic() >= start + timeout_s:
            raise TimeoutError("absolute benchmark deadline")
        data = _strict_json(b"".join(chunks))
        result = classify_envelope(data, profile=profile, request_id=request_id)
        if type(data) is dict and data.get("model") == MODEL:
            for field in ("total_duration", "load_duration",
                          "prompt_eval_duration", "eval_duration"):
                result[field.replace("_duration", "_s")] = _metric(
                    data, field, nanoseconds=True)
            for field in ("prompt_eval_count", "eval_count"):
                result[field] = _metric(data, field)
    except (OSError, TimeoutError, ValueError, UnicodeError,
            http.client.HTTPException, RecursionError):
        result = {"status": "unavailable", "diagnostic": "transport_or_protocol",
                  "fixture_shape_color_match": None}
    finally:
        if reply is not None:
            reply.close()
        if connection is not None:
            connection.close()
    result["wall_s"] = round(max(0.0, time.monotonic() - start), 4)
    return result


def run_probe(*, consent: bool, port: int = 11435, timeout_s: float = 120,
              endpoint: OllamaEndpoint | None = None,
              profiles: tuple[str, ...] = PROFILES) -> dict:
    """Explicit opt-in; at most five synthetic calls, no raw response export."""
    if consent is not True:
        raise ValueError("five synthetic model calls require explicit opt-in")
    if (type(port) is not int or not 1 <= port <= 65535 or
            type(timeout_s) not in (int, float) or
            not math.isfinite(timeout_s) or not 0 < timeout_s <= MAX_TIMEOUT):
        raise ValueError("invalid local experiment boundaries")
    if (type(profiles) is not tuple or not 1 <= len(profiles) <= len(PROFILES) or
            len(set(profiles)) != len(profiles) or
            any(x not in PROFILES or type(x) is not str for x in profiles)):
        raise ValueError("unsupported experimental profiles")
    target = endpoint or OllamaEndpoint(f"http://127.0.0.1:{port}")
    if not isinstance(target, OllamaEndpoint):
        raise ValueError("reuse the validated F5-B endpoint")
    if not ipaddress.ip_address(target.host_port[0]).is_loopback:
        raise ValueError("no LAN or cloud endpoints")
    jpeg = make_synthetic_jpeg()
    observations = []
    for profile in profiles:
        rid = uuid.uuid4().hex
        body = make_probe_request(profile, jpeg, rid)
        measurement = _read_one(target, body, profile, rid, timeout_s)
        observations.append({"profile": profile, **measurement})
    return {
        "study": "QW-PERF-1-PC-synthetic-only",
        "model": MODEL,
        "mode": "real_pc_opt_in",
        "profiles": observations,
        "same_synthetic_pixels": True,
        "response_content_recorded": False,
        "memory_used": False,
        "synthetic_context_only": True,
        "model_was_previously_loaded": "unknown",
        "rss_and_gpu_placement_measured": False,
        "robot_hardware_validated": False,
        "qwen_pc_model_measured": True,
        "motor_commands_issued": 0,
        "memory_writes": 0,
        "private_images_read": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="QW-PERF-1 bounded synthetic PC-only Qwen3.5 9B profiling")
    parser.add_argument("--run", action="store_true",
                        help="actually call the real local 9B up to five times")
    parser.add_argument("--authorize-five-synthetic-calls", action="store_true")
    parser.add_argument("--ollama-port", type=int, default=11435)
    parser.add_argument("--timeout", type=float, default=120)
    args = parser.parse_args(argv)
    if not args.run:
        print(json.dumps({"study": "QW-PERF-1-PC-synthetic-only",
                          "mode": "dry_run_no_network", "model": MODEL,
                          "profiles": list(PROFILES),
                          "qwen_pc_model_measured": False,
                          "no_media_and_no_sqlite": True}, sort_keys=True))
        return 0
    if not args.authorize_five_synthetic_calls:
        parser.error("operator must explicitly authorize five synthetic Ollama calls")
    try:
        report = run_probe(consent=True, port=args.ollama_port,
                           timeout_s=args.timeout)
    except (ValueError, OSError) as exc:
        parser.error("local PC probe could not start; no private data used")
    print(json.dumps(report, sort_keys=True))
    return 0 if all(s["status"] == "unverified" for s in report["profiles"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
