"""Opt-in PC-only, read-only Ollama model placement sampling.

This polls ONLY /api/ps on a literal loopback endpoint while an already
authorized synthetic Qwen test is running. It never starts Ollama or an LLM,
reads images, stores raw responses, or touches robotd/SQLite.
size_vram measures server-reported residency, NOT independently measured
GPU compute utilization or a speedup. Model placement can remain unknown.
"""
from __future__ import annotations

import http.client
import math
import threading

from .ollama_local_client import OllamaEndpoint, _strict_json

MODEL = "qwen3.5:9b"
MAX_RESPONSE_BYTES = 24_576
MAX_MODEL_BYTES = 256 * 1024**3
MAX_MODELS = 64
MAX_POLLS = 1024
SOCKET_TIMEOUT_S = 0.4
DEFAULT_INTERVAL_S = 0.4


def _read_local_ps(endpoint: OllamaEndpoint) -> tuple[str, tuple[int, int] | None]:
    """Only fixed schema numeric counters leave the untrusted local response."""
    if not isinstance(endpoint, OllamaEndpoint):
        raise TypeError("validated OllamaEndpoint required")
    host, port = endpoint.host_port
    if host not in ("127.0.0.1", "::1"):
        raise ValueError("PC device observation requires literal loopback")
    connection = None
    try:
        connection = http.client.HTTPConnection(host, port, timeout=SOCKET_TIMEOUT_S)
        connection.request("GET", "/api/ps", headers={
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Connection": "close",
        })
        response = connection.getresponse()
        if (response.status != 200 or
                response.getheader("Content-Type", "").split(";")[0].strip().lower()
                != "application/json" or
                response.getheader("Content-Encoding", "identity").lower()
                not in ("identity", "")):
            return "unavailable", None
        wire = response.read(MAX_RESPONSE_BYTES + 1)
        if not 0 < len(wire) <= MAX_RESPONSE_BYTES:
            return "unavailable", None
        obj = _strict_json(wire)
        if type(obj) is not dict or type(obj.get("models")) is not list:
            return "unavailable", None
        models = obj["models"]
        if len(models) > MAX_MODELS:
            return "unavailable", None
        for item in models:
            if type(item) is not dict:
                return "unavailable", None
            if (item.get("name", MODEL) != MODEL or
                    item.get("model", MODEL) != MODEL or
                    ("name" not in item and "model" not in item)):
                continue
            size = item.get("size")
            vram = item.get("size_vram")
            if (type(size) is not int or type(vram) is not int or
                    not 0 < size <= MAX_MODEL_BYTES or
                    not 0 <= vram <= MAX_MODEL_BYTES):
                return "unavailable", None
            return "model_reported", (size, vram)
        return "model_not_loaded", None
    except (OSError, TimeoutError, http.client.HTTPException, ValueError,
            UnicodeError, RecursionError, OverflowError):
        return "unavailable", None
    finally:
        if connection is not None:
            connection.close()


class LocalOllamaModelSampler:
    """Low-rate daemon sampler; never blocks or controls the inference thread.

    One instance per explicit PC-only diagnostic. A missing or invalid API
    reading is not evidence of CPU fallback. Size_vram > 0 reflects only
    Ollama-reported GPU residency, not verified GPU kernel execution.
    """

    def __init__(self, *, port: int, interval_s: float = DEFAULT_INTERVAL_S):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("invalid localhost Ollama port")
        if (type(interval_s) not in (float, int) or
                not math.isfinite(interval_s) or not 0.15 <= interval_s <= 2.0):
            raise ValueError("invalid bounded sampling period")
        self._endpoint = OllamaEndpoint(f"http://127.0.0.1:{port}")
        self._interval_s = float(interval_s)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._polls = 0
        self._errors = 0
        self._unloaded = 0
        self._seen = 0
        self._seen_cpu = False
        self._seen_vram = False
        self._max_size = 0
        self._max_vram = 0

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("placement sampler can only be started once")
        self._thread = threading.Thread(target=self._loop, daemon=True,
                                        name="kwipi-pc-ollama-ps")
        self._thread.start()

    def _loop(self) -> None:
        for _ in range(MAX_POLLS):
            if self._stop.is_set():
                break
            state, values = _read_local_ps(self._endpoint)
            with self._lock:
                self._polls += 1
                if state == "model_reported" and values is not None:
                    size, vram = values
                    self._seen += 1
                    self._max_size = max(self._max_size, size)
                    self._max_vram = max(self._max_vram, vram)
                    self._seen_cpu |= vram == 0
                    self._seen_vram |= vram > 0
                elif state == "model_not_loaded":
                    self._unloaded += 1
                else:
                    self._errors += 1
            if self._stop.wait(self._interval_s):
                break

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=SOCKET_TIMEOUT_S + 0.5)

    def report(self) -> dict:
        with self._lock:
            if not self._seen:
                placement = "not_observed"
            elif self._seen_cpu and self._seen_vram:
                placement = "mixed_samples"
            elif self._seen_vram:
                placement = "gpu_memory_reported"
            else:
                placement = "cpu_memory_reported"
            return {
                "source": "loopback_ollama_api_ps",
                "placement": placement,
                "model_samples": self._seen,
                "model_not_loaded_samples": self._unloaded,
                "unavailable_samples": self._errors,
                "polls": self._polls,
                "max_model_size_bytes": self._max_size or None,
                "max_reported_vram_bytes": self._max_vram if self._seen else None,
                "gpu_compute_independently_verified": False,
                "gpu_speedup_measured": False,
            }
