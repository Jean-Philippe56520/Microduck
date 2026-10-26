"""F5-B optional Qwen 4B then 9B PC benchmark; LIVE mode is explicit.

Measures only actual host-side Ollama HTTP timings and F5-A acceptance of
fictional generic categories. No vision, image/video/voice, identifiable
examples, learned identity, real PC power readings or robot sensors are used.
The default DRY RUN does not contact any server or download models.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import time

from .ollama_local_client import OllamaEndpoint, OllamaLocalClient, advisory_from_transport
from .passive_intentions import PassiveIntent
from .pc_hypothesis_contract import OptionalPCAdvisory, PCObservation, PCRequest

MODELS = ("qwen3.5:4b", "qwen3.5:9b")


def _p95(samples: list[float]) -> float | None:
    if not samples:
        return None
    values = sorted(samples)
    index = (len(values) - 1) * .95
    low = int(index)
    high = min(low + 1, len(values) - 1)
    return round(values[low] + (values[high] - values[low]) * (index - low), 6)


def benchmark(model: str, *, endpoint: OllamaEndpoint,
              samples: int = 3, timeout_s: float = 30.,
              keep_alive: str = "0") -> dict:
    """BLOCKING DIAGNOSTIC for an opt-in local PC, never the robot's loop."""
    if model not in MODELS or type(samples) is not int or not 1 <= samples <= 5:
        raise ValueError("unsupported model or sample budget")
    if (type(timeout_s) not in (float, int) or not math.isfinite(timeout_s)
            or not 0 < timeout_s <= 120):
        raise ValueError("invalid diagnostic network timeout")
    client = OllamaLocalClient(endpoint,model=model,keep_alive=keep_alive)
    trials = []
    for _ in range(samples):
        now = time.monotonic()
        request = PCRequest(
            __import__("uuid").uuid4().hex,
            (PCObservation("object_label", "unknown", "unknown", .95),),
            now, now + 2,
        )
        cycle = OptionalPCAdvisory(
            PassiveIntent("inspect","fictive_unresolved_category",
                          "object_label","unknown"),
            request,"pending_transport",
        )
        response = client.query(request,timeout_s=timeout_s)
        finished = time.monotonic()
        advisory = advisory_from_transport(cycle,response,
                                          now_monotonic_s=finished)
        trials.append({
            "transport_status": response.status,
            "f5a_status": advisory.status,
            "http_elapsed_ms": round(response.elapsed_s * 1000, 3),
            "server_total_ms": (
                round(response.server_total_ns / 1_000_000, 3)
                if response.server_total_ns is not None else None),
            "model_load_ms": (
                round(response.load_ns / 1_000_000, 3)
                if response.load_ns is not None else None),
            "tokens_generated": response.eval_tokens,
            "eval_ms": (
                round(response.eval_ns / 1_000_000, 3)
                if response.eval_ns is not None else None),
            "accepted_unverified_unknown": bool(
                advisory.status == "hypotheses_unverified"
                and len(advisory.hypotheses) == 1
                and advisory.hypotheses[0].category == "unknown"
                and advisory.hypotheses[0].claimed_confidence == 0
                and not advisory.hypotheses[0].verified),
        })
        # No response body, image, identity, token, IP or prompt is logged.
    timings = [t["http_elapsed_ms"] for t in trials]
    return {
        "model": model,
        "samples": samples,
        "pc_host_benchmark_executed": True,
        "images_or_real_observations": 0,
        "recognized_individuals": 0,
        "correct_animal_identifications_measured": False,
        "host_http_latency_ms_p50": round(statistics.median(timings), 3),
        "host_http_latency_ms_p95": _p95(timings),
        "f5a_accepted_unverified_unknown_count": sum(
            t["accepted_unverified_unknown"] for t in trials),
        "f5a_deadline_s": 2.0,
        "real_server_power_or_RSS_measured": False,
        "trials": trials,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live",action="store_true",
                        help="Explicit consent to actual local Ollama queries")
    parser.add_argument("--model",choices=("4b","9b","both"),default="both")
    parser.add_argument("--endpoint",default="http://127.0.0.1:11434",
                        help="literal HTTP loopback IP:port (SSH tunnel recommended)")
    parser.add_argument("--unsafe-private-lan-lab",action="store_true",
                        help="UNENCRYPTED private IPv4 lab only, no personal data")
    parser.add_argument("--samples",type=int,default=3)
    parser.add_argument("--timeout-s",type=float,default=30.)
    parser.add_argument("--keep-alive",choices=("0","5m"),default="0")
    args = parser.parse_args(argv)
    try:
        endpoint = OllamaEndpoint(args.endpoint,
                        unsafe_private_lan_lab=args.unsafe_private_lan_lab)
        if not 1 <= args.samples <= 5 or not 0 < args.timeout_s <= 120 or not math.isfinite(args.timeout_s):
            parser.error("samples must be 1..5 and timeout 0..120 s")
        targets = (MODELS if args.model == "both" else (
            "qwen3.5:" + args.model,))
        if args.run_live:
            report = {
                "mode":"real_local_ollama_diagnostic_not_robot",
                "metrics_from":"actual_PC_host_and_Ollama_reported_values",
                "comparison":[benchmark(
                    name,endpoint=endpoint,samples=args.samples,
                    timeout_s=args.timeout_s,keep_alive=args.keep_alive)
                    for name in targets],
            }
        else:
            report = {
                "mode":"dry_run_no_network",
                "pc_host_benchmark_executed":False,
                "model_candidates":list(targets),
                "samples_planned_per_model":args.samples,
                "pc_model_installed_or_accelerated":"not_checked",
                "real_latency_RSS_power":"not_measured",
                "next_step":"run explicitly on the local PC with --run-live",
            }
    except (ValueError,TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(report,sort_keys=True,allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
