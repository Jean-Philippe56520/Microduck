"""F5-B: opt-in LOCAL Ollama HTTP client and non-blocking F5-A bridge.

No credentials, DNS discovery, cloud API, camera, audio or motor control.
Requests contain ONLY the fictional categories allowed by F5-A. Replies
remain unverified, never change AutonomyBrain or SQLite, and are rejected by
the existing PC hypothesis parser. No production sensor source is supported.

Network authentication is NOT provided by Ollama's localhost HTTP API.
Prefer an encrypted, authenticated tunnel ending on 127.0.0.1. Direct RFC1918
HTTP needs an explicit lab-only opt-in and MUST NOT carry personal data.
"""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import http.client
import ipaddress
import json
import math
import time
from typing import Callable
from urllib.parse import urlsplit

from .pc_hypothesis_contract import (
    MAX_REPLY_BYTES, OptionalPCAdvisory, PCRequest,
    finish_optional_pc_cycle,
)

ALLOWED_MODELS = frozenset({"qwen3.5:4b", "qwen3.5:9b"})
MAX_ENVELOPE_BYTES = 16384
MAX_HTTP_TIMEOUT_S = 120.0
_MAX_PROMPT_BYTES = 2048
_PRIVATE_IPV4 = tuple(ipaddress.IPv4Network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
))
SYSTEM_PROMPT = (
    "You are an untrusted optional annotation service, not a robot agent. "
    "Input is synthetic category metadata ONLY: no camera image, object "
    "features, identity, scene, floor or sound. It cannot distinguish a dog "
    "from a cat. Do not guess: output only category 'unknown'. "
    "Return only a JSON object with schema_version=1, request_id copied "
    "exactly, source='pc_qwen_unverified', and hypotheses containing one "
    "object_label category 'unknown', confidence 0, ttl_s 1. "
    "Never return commands, personal labels, safety claims or prose."
)


def _positive_timeout(value: object) -> bool:
    return (type(value) in (int, float) and math.isfinite(value)
            and 0 < value <= MAX_HTTP_TIMEOUT_S)


def _strict_json(data: bytes) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    return json.loads(
        data.decode("utf-8"), object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(
            ValueError("nonfinite JSON constant")),
    )


@dataclass(frozen=True)
class OllamaEndpoint:
    """A literal IP, not a general URL or implicit cloud/SSRF endpoint."""

    url: str = "http://127.0.0.1:11434"
    unsafe_private_lan_lab: bool = False

    def __post_init__(self) -> None:
        if type(self.url) is not str or type(self.unsafe_private_lan_lab) is not bool:
            raise ValueError("invalid local endpoint configuration")
        try:
            p = urlsplit(self.url)
            if (p.scheme != "http" or p.username is not None
                    or p.password is not None or p.path or p.query
                    or p.fragment or not p.hostname
                    or not p.port or p.netloc.endswith(":")
                    or any(ch.isspace() for ch in self.url)):
                raise ValueError("endpoint must be an explicit bare HTTP IP:port")
            host = ipaddress.ip_address(p.hostname)
            if "%" in p.hostname:
                raise ValueError("interface scope is not supported")
        except (ValueError, TypeError) as exc:
            raise ValueError("endpoint must be a literal loopback IP:port") from exc
        if not host.is_loopback:
            if not (self.unsafe_private_lan_lab
                    and isinstance(host, ipaddress.IPv4Address)
                    and any(host in subnet for subnet in _PRIVATE_IPV4)):
                raise ValueError("remote HTTP requires explicit private lab opt-in")

    @property
    def host_port(self) -> tuple[str, int]:
        parsed = urlsplit(self.url)
        return parsed.hostname, parsed.port


@dataclass(frozen=True)
class OllamaTransportResult:
    """No model text is retained except a bounded untrusted F5-A wire blob."""

    status: str
    model: str
    elapsed_s: float
    wire: bytes | None = None
    server_total_ns: int | None = None
    load_ns: int | None = None
    eval_tokens: int | None = None
    eval_ns: int | None = None

    def __post_init__(self) -> None:
        if (self.status not in {"ok", "unavailable", "protocol_rejected"}
                or self.model not in ALLOWED_MODELS
                or type(self.elapsed_s) not in (float, int)
                or not math.isfinite(self.elapsed_s) or self.elapsed_s < 0):
            raise ValueError("invalid optional Ollama result")
        if self.status != "ok" and self.wire is not None:
            raise ValueError("failed transport cannot carry model text")
        if self.status == "ok" and (type(self.wire) is not bytes
                                    or not 0 < len(self.wire) <= MAX_REPLY_BYTES):
            raise ValueError("successful transport needs bounded wire")


def _counter(data: dict, key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if type(value) is not int or value < 0:
        raise ValueError("invalid Ollama timing/count")
    return value


def _schema() -> dict:
    """JSON schema is just helpful formatting, NOT a security boundary."""
    return {
        "type": "object", "additionalProperties": False,
        "required": ["schema_version", "request_id", "source", "hypotheses"],
        "properties": {
            "schema_version": {"type": "integer", "enum": [1]},
            "request_id": {"type": "string"},
            "source": {"type": "string", "enum": ["pc_qwen_unverified"]},
            "hypotheses": {
                "type": "array", "maxItems": 1, "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["kind", "category", "confidence", "ttl_s"],
                    "properties": {
                        "kind": {"type": "string", "enum": ["object_label"]},
                        "category": {"type": "string", "enum": ["unknown"]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "ttl_s": {"type": "number", "minimum": 0.01, "maximum": 1},
                    },
                },
            },
        },
    }


class OllamaLocalClient:
    """Opt-in HTTP adapter. One synchronous request; NEVER in the motor loop.

    Use OptionalOllamaWorker for nonblocking integration. Even with socket
    timeout a slow-drip HTTP peer might outlive the logical deadline, so the
    worker's poll refuses late results and bounds concurrent work to ONE.
    """

    def __init__(self, endpoint: OllamaEndpoint | None = None, *,
                 model: str = "qwen3.5:4b",
                 keep_alive: str = "0") -> None:
        if type(model) is not str or model not in ALLOWED_MODELS:
            raise ValueError("only pinned local Qwen 4B/9B tags are supported")
        if keep_alive not in {"0", "5m"} or type(keep_alive) is not str:
            raise ValueError("only 0 or 5m keep_alive is allowed")
        self.endpoint = endpoint or OllamaEndpoint()
        if not isinstance(self.endpoint, OllamaEndpoint):
            raise TypeError("OllamaEndpoint required")
        self.model = model
        self.keep_alive = keep_alive

    def _request_body(self, request: PCRequest) -> bytes:
        if not isinstance(request, PCRequest):
            raise TypeError("F5-A PCRequest required")
        only_safe = request.to_wire()
        if len(only_safe) > _MAX_PROMPT_BYTES:
            raise ValueError("synthetic observations exceed protocol bound")
        # The model has NO images or text about the scene to infer dog/cat.
        body = {
            "model": self.model, "stream": False, "think": False,
            "keep_alive": self.keep_alive,
            "format": _schema(),
            "options": {"temperature": 0, "num_predict": 160},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": only_safe.decode("utf-8")},
            ],
        }
        encoded = json.dumps(
            body, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        if len(encoded) > 8192:
            raise ValueError("request body budget exceeded")
        return encoded

    def query(self, request: PCRequest, *,
              timeout_s: float = 2.0) -> OllamaTransportResult:
        """Network call on caller's thread; never a motor-loop callback.

        Timeouts are per socket operation. The caller/worker also enforces
        the independent F5-A monotonic deadline. No proxy, redirect, cookie,
        secrets, prompt log or outbound API beyond literal IP /api/chat.
        """
        if not _positive_timeout(timeout_s):
            raise ValueError("invalid socket timeout")
        body = self._request_body(request)
        started = time.monotonic()
        conn: http.client.HTTPConnection | None = None
        status, wire = "unavailable", None
        metrics: dict[str, int | None] = {}
        try:
            host, port = self.endpoint.host_port
            conn = http.client.HTTPConnection(host, port, timeout=float(timeout_s))
            conn.request("POST", "/api/chat", body, headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "Connection": "close",
            })
            reply = conn.getresponse()
            if reply.status != 200:
                status = "unavailable"
            elif not reply.getheader("Content-Type", "").lower().startswith(
                    "application/json"):
                status = "protocol_rejected"
            else:
                content_length = reply.getheader("Content-Length")
                if content_length is not None and (
                        not content_length.isascii()
                        or not content_length.isdecimal()
                        or int(content_length) > MAX_ENVELOPE_BYTES):
                    raise ValueError("oversize Ollama envelope")
                if conn.sock is not None:
                    remaining = timeout_s - (time.monotonic() - started)
                    if remaining <= 0:
                        raise TimeoutError("expired socket budget")
                    conn.sock.settimeout(remaining)
                envelope_bytes = reply.read(MAX_ENVELOPE_BYTES + 1)
                if len(envelope_bytes) > MAX_ENVELOPE_BYTES:
                    raise ValueError("oversize Ollama response")
                data = _strict_json(envelope_bytes)
                if (type(data) is not dict
                        or data.get("model") != self.model
                        or data.get("done") is not True
                        or data.get("done_reason", "stop") not in ("stop", None)
                        or type(data.get("message")) is not dict):
                    raise ValueError("unexpected Ollama response")
                msg = data["message"]
                if (msg.get("role") != "assistant"
                        or type(msg.get("content")) is not str
                        or msg.get("tool_calls") not in (None, [])
                        or msg.get("images") not in (None, [])):
                    raise ValueError("non-text or tool output is disallowed")
                candidate = msg["content"].encode("utf-8")
                if not 0 < len(candidate) <= MAX_REPLY_BYTES:
                    raise ValueError("model output exceeds F5-A limit")
                # Parse early to reject malformed JSON; F5-A independently
                # rejects commands, sources, correlations, unsafe categories.
                if type(_strict_json(candidate)) is not dict:
                    raise ValueError("model output must be JSON object")
                wire, status = candidate, "ok"
                metrics = {
                    "server_total_ns": _counter(data, "total_duration"),
                    "load_ns": _counter(data, "load_duration"),
                    "eval_tokens": _counter(data, "eval_count"),
                    "eval_ns": _counter(data, "eval_duration"),
                }
        except (OSError, TimeoutError, http.client.HTTPException):
            status, wire = "unavailable", None
        except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
            status, wire = "protocol_rejected", None
        finally:
            if conn is not None:
                conn.close()
        return OllamaTransportResult(
            status=status, model=self.model,
            elapsed_s=max(0.0, time.monotonic() - started),
            wire=wire, **metrics,
        )


def advisory_from_transport(
    cycle: OptionalPCAdvisory, transport: OllamaTransportResult | None,
    *, now_monotonic_s: float,
) -> OptionalPCAdvisory:
    """The existing F5-A parser is the ONLY gate for returned hypotheses."""
    if not isinstance(cycle, OptionalPCAdvisory) or cycle.status != "pending_transport":
        raise ValueError("pending F5-A cycle required")
    if type(now_monotonic_s) not in (float, int) or not math.isfinite(now_monotonic_s):
        raise ValueError("invalid monotonic time")
    if transport is None or transport.status == "unavailable":
        return finish_optional_pc_cycle(cycle, None, received_monotonic_s=now_monotonic_s)
    if transport.status == "protocol_rejected":
        return finish_optional_pc_cycle(cycle, b"{}", received_monotonic_s=now_monotonic_s)
    return finish_optional_pc_cycle(
        cycle, transport.wire, received_monotonic_s=now_monotonic_s,
    )


class OptionalOllamaWorker:
    """A single opt-in background HTTP worker; poll NEVER blocks cognition.

    At most one network task may be in flight. A timed-out task can continue
    until its socket yields; it is never queued again, and cannot modify
    the brain or a late decision. close() does not wait for network I/O.
    """

    def __init__(self, client: OllamaLocalClient, *,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if not isinstance(client, OllamaLocalClient) or not callable(clock):
            raise TypeError("client and monotonic clock required")
        self.client, self.clock = client, clock
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="f5b-ollama")
        self._future: Future[OllamaTransportResult] | None = None
        self._cycle: OptionalPCAdvisory | None = None
        self._closed = False

    def submit(self, cycle: OptionalPCAdvisory) -> bool:
        """False => immediate offline fallback; no queued network task."""
        if self._closed:
            raise RuntimeError("worker closed")
        if not isinstance(cycle, OptionalPCAdvisory) or cycle.status != "pending_transport":
            raise ValueError("pending F5-A cycle required")
        now = self.clock()
        if (type(now) not in (float, int) or not math.isfinite(now)
                or self._cycle is not None
                or self._future is not None and not self._future.done()
                or cycle.request is None
                or not cycle.request.created_monotonic_s <= now
                < cycle.request.expires_monotonic_s):
            return False
        budget = cycle.request.expires_monotonic_s - now
        self._cycle = cycle
        self._future = self._pool.submit(
            self.client.query, cycle.request, timeout_s=min(budget, 2.0),
        )
        return True

    def poll(self) -> OptionalPCAdvisory | None:
        """None means no outcome yet; returned result retains local intent."""
        cycle = self._cycle
        if cycle is None:
            return None
        now = self.clock()
        if type(now) not in (float, int) or not math.isfinite(now):
            raise ValueError("monotonic clock invalid")
        if now >= cycle.request.expires_monotonic_s:
            self._cycle = None
            if self._future is not None:
                self._future.cancel()  # cannot kill an already-running socket
            return advisory_from_transport(cycle, None, now_monotonic_s=now)
        if self._future is None or not self._future.done():
            return None
        try:
            result = self._future.result()  # already completed; no wait
        except Exception:
            result = None
        self._cycle = None
        self._future = None
        return advisory_from_transport(cycle, result, now_monotonic_s=now)

    def close(self) -> None:
        self._closed = True
        self._cycle = None
        self._pool.shutdown(wait=False, cancel_futures=True)

    def __enter__(self) -> "OptionalOllamaWorker":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
