"""QW-PERF-1H: mock-only placement during existing Qwen PC benchmark.

No real Ollama, network, personal media, robot or sqlite.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from microduck_companion.qwen9b_perf_probe import main, run_probe


class PerfPlacementTests(unittest.TestCase):
    def test_default_benchmark_does_not_create_sampler(self):
        with patch(
            "microduck_companion.qwen9b_perf_probe.LocalOllamaModelSampler",
            side_effect=AssertionError("sampler not opt-in"),
        ), patch(
            "microduck_companion.qwen9b_perf_probe._read_one",
            return_value={"status": "unverified", "diagnostic": "none"},
        ):
            record = run_probe(consent=True, profiles=("compact_json",))
        self.assertNotIn("ollama_placement", record)
        self.assertFalse(record["rss_and_gpu_placement_measured"])
        self.assertEqual(0, record["memory_writes"])

    def test_opt_in_sampler_reports_only_numeric_residency(self):
        sampled = []
        class Sampler:
            def __init__(self, *, port):
                self.port = port
                sampled.append("init")
            def start(self):
                sampled.append("start")
            def stop(self):
                sampled.append("stop")
            def report(self):
                sampled.append("report")
                return {
                    "placement": "gpu_memory_reported",
                    "model_samples": 2,
                    "max_reported_vram_bytes": 5000,
                    "gpu_compute_independently_verified": False,
                    "gpu_speedup_measured": False,
                }
        def read_one(_endpoint, _body, profile, _id, _timeout):
            sampled.append(profile)
            return {
                "status": "unverified",
                "diagnostic": "none",
                "wall_s": 0.1,
                "fixture_shape_color_match": True,
            }
        with patch(
            "microduck_companion.qwen9b_perf_probe.LocalOllamaModelSampler",
            Sampler,
        ), patch(
            "microduck_companion.qwen9b_perf_probe._read_one",
            side_effect=read_one,
        ):
            record = run_probe(
                consent=True,
                port=11435,
                profiles=("compact_json", "compact_json_mock_context"),
                report_placement=True,
            )
        self.assertEqual(
            ["init", "start", "compact_json",
             "compact_json_mock_context", "stop", "report"],
            sampled,
        )
        self.assertEqual("gpu_memory_reported",
                         record["ollama_placement"]["placement"])
        self.assertFalse(
            record["ollama_placement"]["gpu_compute_independently_verified"])
        self.assertFalse(record["ollama_placement"]["gpu_speedup_measured"])
        self.assertFalse(record["rss_and_gpu_placement_measured"])
        self.assertEqual(0, record["private_images_read"])
        self.assertEqual(0, record["motor_commands_issued"])
        self.assertNotIn("model_response", json.dumps(record))
        self.assertNotIn("PRIVATE", json.dumps(record))

    def test_failure_always_stops_sampler_before_returning(self):
        operations = []
        class Sampler:
            def __init__(self, *, port):
                operations.append("init")
            def start(self):
                operations.append("start")
            def stop(self):
                operations.append("stop")
            def report(self):
                raise AssertionError("must not report after exception")
        with patch(
            "microduck_companion.qwen9b_perf_probe.LocalOllamaModelSampler",
            Sampler,
        ), patch(
            "microduck_companion.qwen9b_perf_probe._read_one",
            side_effect=ValueError("private information not to be printed"),
        ):
            with self.assertRaises(ValueError):
                run_probe(consent=True, report_placement=True,
                          profiles=("compact_json",))
        self.assertEqual(["init", "start", "stop"], operations)

    def test_opt_in_requires_explicit_run_and_consent(self):
        with self.assertRaises(ValueError):
            run_probe(consent=False, report_placement=True)
        with self.assertRaises(ValueError):
            run_probe(consent=True, report_placement=1)
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(["--report-placement"])
            with self.assertRaises(SystemExit):
                main(["--run", "--report-placement"])

    def test_cli_gates_report_and_passes_flag_only_on_run(self):
        fake = {
            "profiles": [{"profile": "compact_json", "status": "unverified"}],
            "ollama_placement": {
                "placement": "not_observed",
                "gpu_compute_independently_verified": False,
                "gpu_speedup_measured": False,
            },
            "private_images_read": 0,
            "memory_writes": 0,
            "motor_commands_issued": 0,
        }
        stream = io.StringIO()
        with patch(
            "microduck_companion.qwen9b_perf_probe.run_probe",
            return_value=fake,
        ) as fn, redirect_stdout(stream):
            exit_code = main(["--run", "--authorize-five-synthetic-calls",
                              "--ollama-port", "11435", "--report-placement"])
        self.assertEqual(0, exit_code)
        fn.assert_called_once_with(
            consent=True, port=11435, timeout_s=120,
            report_placement=True,
        )
        self.assertEqual("not_observed",
                         json.loads(stream.getvalue())["ollama_placement"]["placement"])

    def test_powershell_launcher_is_bounded_and_explicit(self):
        script = (Path(__file__).resolve().parents[1]
                  / "scripts" / "kwipi-vision-test.ps1").read_text("utf-8")
        for token in (
            "[switch]$PerfCheck",
            "[switch]$AuthorizeFiveSyntheticCalls",
            "if ($PerfCheck -and -not $AuthorizeFiveSyntheticCalls)",
            "if ($AuthorizeFiveSyntheticCalls -and -not $PerfCheck)",
            "if ($PerfCheck -and $Port -ne 11435)",
            "if ($VisionCheck -and $Image)",
            "if ($PerfCheck -and $Image)",
            "Get-NetTCPConnection -LocalPort $Port -State Listen",
            "--run --authorize-five-synthetic-calls",
            "-m microduck_companion.qwen9b_perf_probe",
            "Stop-OnlyStartedOllama -ServerProcess $serverWeStarted",
        ):
            self.assertIn(token, script)
        self.assertLess(
            script.index("if ($PerfCheck -and -not $AuthorizeFiveSyntheticCalls)"),
            script.index("Start-Process -FilePath"),
        )
        self.assertNotIn("setx ", script.lower())
        self.assertNotIn("ollama pull", script.lower())


if __name__ == "__main__":
    unittest.main()
