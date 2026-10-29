"""QW-PERF-1F: isolated fake Ollama /api/ps, never real Qwen or private media."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from microduck_companion.ollama_local_client import OllamaEndpoint
from microduck_companion.ollama_device_placement import (
    LocalOllamaModelSampler, _read_local_ps,
)
from microduck_companion.qwen9b_vision_check import run_check


MODEL = "qwen3.5:9b"


def _ps_data(*, size=6_200_000_000, size_vram=0, name=MODEL):
    return json.dumps({"models": [{"model": name, "name": name, "size": size,
                                    "size_vram": size_vram}]}).encode("utf-8")


class _FakeReply:
    status = 200

    def __init__(self, body, *, content_type="application/json", status=200):
        self._body = body
        self._content_type = content_type
        self.status = status

    def getheader(self, key, default=None):
        return {"Content-Type": self._content_type}.get(key, default)

    def read(self, max_bytes):
        return self._body[:max_bytes]


class _FakeConn:
    def __init__(self, *args, body=b'{"models":[]}', **kwargs):
        self._reply = _FakeReply(body)
        self.path = None

    def request(self, method, path, headers=None):
        assert method == "GET", "only read-only GET allowed"
        assert path == "/api/ps", "no other Ollama APIs allowed"
        self.path = path

    def getresponse(self):
        assert self.path == "/api/ps"
        return self._reply

    def close(self):
        pass


class DevicePlacementTests(unittest.TestCase):
    def test_fixed_loopback_get_and_numeric_fields_only(self):
        for vram in (0, 6_000_000_000):
            with self.subTest(vram=vram):
                class Connection(_FakeConn):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, body=_ps_data(size_vram=vram), **kwargs)

                with patch("microduck_companion.ollama_device_placement.http.client.HTTPConnection",
                           Connection):
                    status, value = _read_local_ps(OllamaEndpoint())
                self.assertEqual(status, "model_reported")
                self.assertEqual(value, (6_200_000_000, vram))

    def test_absent_model_is_unknown_not_cpu(self):
        class Connection(_FakeConn):
            pass

        with patch("microduck_companion.ollama_device_placement.http.client.HTTPConnection",
                   Connection):
            self.assertEqual(("model_not_loaded", None),
                             _read_local_ps(OllamaEndpoint()))

    def test_wrong_model_is_never_attributed_to_qwen_9b(self):
        class Connection(_FakeConn):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, body=_ps_data(
                    name="different:model", size_vram=5_000_000_000), **kwargs)

        with patch("microduck_companion.ollama_device_placement.http.client.HTTPConnection",
                   Connection):
            status, sample = _read_local_ps(OllamaEndpoint())
        self.assertEqual("model_not_loaded", status)
        self.assertIsNone(sample)

    def test_bad_envelopes_fail_closed_without_echo(self):
        cases = [
            b"",
            b'{ "models":[ {"name":"qwen3.5:9b","size":64,"size_vram":1,'
            b'"size_vram":2} ] }',
            b'{"models":"sensitive"}',
            b'{"models":[{"name":"qwen3.5:9b","size":6200,"size_vram":"private"}]}',
            b'{"models":[{"name":"qwen3.5:9b","size":0,"size_vram":5}]}',
            b'{"models":[{"name":"qwen3.5:9b","size":6200,"size_vram":-1}]}',
            b'{"models":[{"name":"qwen3.5:9b","size":6200,"size_vram":true}]}',
            b'{"models":[{"name":"qwen3.5:9b","size":6200}]}',
            b"x" * 24_577,
        ]
        for blob in cases:
            with self.subTest(blob=blob[:25]):
                class Connection(_FakeConn):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, body=blob, **kwargs)

                with patch("microduck_companion.ollama_device_placement.http.client.HTTPConnection",
                           Connection):
                    outcome = _read_local_ps(OllamaEndpoint())
                self.assertEqual(("unavailable", None), outcome)
                self.assertNotIn("private", str(outcome))

    def test_timeout_and_bad_http_type_fail_safely(self):
        class Slow:
            def __init__(self, *args, **kwargs): pass
            def request(self, *args, **kwargs): raise TimeoutError("sensitive")
            def close(self): pass
        with patch("microduck_companion.ollama_device_placement.http.client.HTTPConnection",
                   Slow):
            self.assertEqual(("unavailable", None),
                             _read_local_ps(OllamaEndpoint()))
        class Html(_FakeConn):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, body=_ps_data(), **kwargs)
                self._reply = _FakeReply(_ps_data(), content_type="text/html")
        with patch("microduck_companion.ollama_device_placement.http.client.HTTPConnection",
                   Html):
            self.assertEqual(("unavailable", None),
                             _read_local_ps(OllamaEndpoint()))

    def test_non_loopback_refused_even_with_lab_override(self):
        with self.assertRaises(ValueError):
            _read_local_ps(OllamaEndpoint(
                "http://192.168.1.27:11435", unsafe_private_lan_lab=True))
        for port in (0, 65536, True, "11435"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                LocalOllamaModelSampler(port=port)
        for period in (0, float("nan"), 30, "0.5"):
            with self.subTest(period=period), self.assertRaises(ValueError):
                LocalOllamaModelSampler(port=11435, interval_s=period)

    def test_real_local_fake_server_with_gpu_memory(self):
        seen = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_GET(self):
                if self.path != "/api/ps":
                    self.send_error(404)
                    return
                payload = _ps_data(size_vram=4_000_000_000)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                seen.set()

        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        loop = threading.Thread(target=srv.serve_forever, daemon=True)
        loop.start()
        monitor = LocalOllamaModelSampler(
            port=srv.server_address[1], interval_s=0.15)
        try:
            self.assertEqual("not_observed", monitor.report()["placement"])
            monitor.start()
            self.assertTrue(seen.wait(timeout=2), "fake local API was not sampled")
            monitor.stop()
            report = monitor.report()
            self.assertEqual("gpu_memory_reported", report["placement"])
            self.assertGreaterEqual(report["model_samples"], 1)
            self.assertEqual(4_000_000_000, report["max_reported_vram_bytes"])
            self.assertFalse(report["gpu_compute_independently_verified"])
            self.assertFalse(report["gpu_speedup_measured"])
            self.assertNotIn("request", json.dumps(report))
            with self.assertRaises(RuntimeError):
                monitor.start()
        finally:
            monitor.stop()
            srv.shutdown()
            srv.server_close()
            loop.join(timeout=2)

    def test_sampler_cpu_only_and_missing_are_distinct(self):
        for mode, expected in (("model_reported", "cpu_memory_reported"),
                               ("model_not_loaded", "not_observed"),
                               ("unavailable", "not_observed")):
            received = threading.Event()
            def read(_endpoint):
                received.set()
                return (mode, (6200, 0) if mode == "model_reported" else None)
            with self.subTest(mode=mode), patch(
                    "microduck_companion.ollama_device_placement._read_local_ps",
                    side_effect=read):
                monitor = LocalOllamaModelSampler(port=11435)
                monitor.start()
                self.assertTrue(received.wait(timeout=1))
                monitor.stop()
                report = monitor.report()
            self.assertEqual(expected, report["placement"])
            self.assertEqual(0 if mode != "model_reported" else 1,
                             report["model_samples"])
            self.assertFalse(report["gpu_compute_independently_verified"])

    def test_vision_cli_is_optional_and_sampler_never_controls_ollama(self):
        from microduck_companion.qwen9b_vision_check import main
        self.assertTrue(callable(main))
        with self.assertRaises(ValueError):
            run_check(report_placement=1)
        with patch("microduck_companion.qwen9b_vision_check.Qwen9BPCClient") as fake:
            colors = iter(("red", "blue"))
            def answer(*args, **kwargs):
                time.sleep(0.10)
                color = next(colors)
                return SimpleNamespace(status="unverified", probe_color=color,
                                       diagnostic_stage="none", diagnostic_reason="none",
                                       latency_s=0.10)
            fake.return_value.query.side_effect = answer
            with patch("microduck_companion.ollama_device_placement._read_local_ps",
                       return_value=("model_reported", (6200, 5100))):
                report, passed = run_check(report_placement=True, timeout_s=2)
        self.assertTrue(passed)
        self.assertEqual("gpu_memory_reported",
                         report["ollama_placement"]["placement"])
        self.assertGreaterEqual(report["ollama_placement"]["model_samples"], 1)
        self.assertEqual(0, report["memory_writes"])
        self.assertEqual(0, report["motor_commands_issued"])
        self.assertEqual(0, report["private_images_read"])
        self.assertNotIn("model_response", json.dumps(report))

    def test_windows_launcher_opt_in_only_and_preflight(self):
        root = Path(__file__).resolve().parents[1]
        launcher = (root / "scripts" / "kwipi-vision-test.ps1").read_text(
            encoding="utf-8")
        self.assertIn("[switch]$ReportPlacement", launcher)
        self.assertIn("if ($ReportPlacement -and -not $VisionCheck)", launcher)
        self.assertLess(launcher.index("if ($ReportPlacement -and -not $VisionCheck)"),
                        launcher.index("Start-Process -FilePath"))
        self.assertIn('if ($ReportPlacement) { $placementArgs = @("--report-placement") }',
                      launcher)
        self.assertIn("@placementArgs", launcher)
        self.assertNotIn("ollama pull", launcher.lower())
        self.assertNotIn("setx ", launcher.lower())
        self.assertNotIn("api.openai.com", launcher.lower())


if __name__ == "__main__":
    unittest.main()
