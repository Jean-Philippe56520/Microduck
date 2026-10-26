"""F5-B diagnostic exercises safe defaults and never contacts real Ollama."""
from __future__ import annotations

import json
import unittest

from microduck_companion.f5b_benchmark import _p95, benchmark, main
from microduck_companion.ollama_local_client import OllamaEndpoint


class BenchmarkTests(unittest.TestCase):
    def test_p95_empty_single_and_interpolated(self):
        self.assertIsNone(_p95([]))
        self.assertEqual(2.,_p95([2.]))
        self.assertEqual(9.55,_p95([1,10]))

    def test_opt_in_diagnostic_only_and_no_model_at_default(self):
        from contextlib import redirect_stdout
        import io
        stream=io.StringIO()
        with redirect_stdout(stream):
            self.assertEqual(0,main([]))
        record=json.loads(stream.getvalue())
        self.assertEqual("dry_run_no_network",record["mode"])
        self.assertFalse(record["pc_host_benchmark_executed"])
        self.assertEqual(["qwen3.5:4b","qwen3.5:9b"],record["model_candidates"])
        self.assertEqual("not_measured",record["real_latency_RSS_power"])

    def test_dry_run_single_model_supported(self):
        from contextlib import redirect_stdout
        import io
        stream=io.StringIO()
        with redirect_stdout(stream):
            main(["--model","4b","--samples","2"])
        record=json.loads(stream.getvalue())
        self.assertEqual(["qwen3.5:4b"],record["model_candidates"])
        self.assertEqual(2,record["samples_planned_per_model"])

    def test_reject_bad_budget_before_any_network(self):
        for params in (
            ["--samples","0"],["--samples","9"],
            ["--timeout-s","nan"],["--timeout-s","121"],
            ["--endpoint","http://example.com:11434"],
        ):
            with self.subTest(params=params),self.assertRaises(SystemExit):
                main(params)

    def test_benchmark_rejects_invalid_models_without_network(self):
        for mod,samp in (("qwen3.5:27b",1),("qwen3.5:4b",0)):
            with self.assertRaises(ValueError):
                benchmark(mod,endpoint=OllamaEndpoint(),samples=samp)


if __name__=="__main__":
    unittest.main()
