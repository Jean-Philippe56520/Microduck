"""F6-B: host-only, deterministic Python/Rust parity and cost probe.

Compares JUST PassiveRhythm._score with a Rust standard-library experiment.
It never invokes an OEM daemon, robot motors, SQLite, camera, Ollama or Qwen.
No workload result certifies a robot's available memory or real-time behavior.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import time

from .autonomy import Motivations
from .passive_rhythm import PassiveRhythm

INTENTS = ("observe", "inspect", "listen")
CATEGORIES = ("ball", "toy", "dog", "unknown", "knock")
BENCH_ITERATIONS = 120_000
MAX_ERROR = 1e-12


def cases() -> tuple[tuple[str, str, tuple[float, ...]], ...]:
    """Publicly reproducible, synthetic motive configurations; no identities."""
    edges = (
        (0., 0., 0., 0., 0.),
        (1., 1., 1., 1., 1.),
        (0.75, 0.55, 0.60, 0.80, 0.35),
        (0.42, 0.51, 0.99, 0.22, 0.34),
        (0.20, 0.30, 0.45, 0.34, 0.22),
    )
    varied = tuple(
        tuple(((i * multiplier + offset) % 101) / 100.0
              for multiplier, offset in
              ((17, 3), (31, 10), (23, 22), (43, 49), (19, 7)))
        for i in range(95)
    )
    return tuple(
        (intention, category, vector)
        for vector in edges + varied
        for intention in INTENTS
        for category in CATEGORIES
    )


def python_score(item: tuple[str, str, tuple[float, ...]]) -> float:
    intent, category, vec = item
    motives = Motivations(*vec)
    return PassiveRhythm._score(intent, category, motives)


def probe_rust(rust_bin: str | Path, *, timeout_s: float = 15.) -> dict:
    """Run ONLY an explicitly supplied compiled local fixture executable."""
    executable = Path(rust_bin)
    if not executable.is_file():
        raise ValueError("compiled Rust scoring probe executable missing")
    dataset = cases()
    text = "".join(
        f"{intent}\t{category}\t" + "\t".join(str(x) for x in m) + "\n"
        for intent, category, m in dataset
    )
    result = subprocess.run(
        [str(executable.resolve()), "--tsv"],
        input=text, text=True, encoding="utf-8",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout_s, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("Rust scorer rejected the bounded fixture")
    rows = result.stdout.splitlines()
    if len(rows) != len(dataset):
        raise RuntimeError("Rust scorer returned wrong number of scores")
    rust_scores = tuple(float(v) for v in rows)
    python_scores = tuple(python_score(v) for v in dataset)
    if not all(math.isfinite(v) for v in rust_scores):
        raise RuntimeError("Rust scorer generated nonfinite values")
    maximum = max(
        abs(rust_value - py_value)
        for rust_value, py_value in zip(rust_scores, python_scores)
    )
    if maximum > MAX_ERROR:
        raise RuntimeError("Rust score drifted from the existing Python brain")
    return {
        "fixture_cases": len(dataset),
        "max_absolute_error": maximum,
        "tolerance": MAX_ERROR,
        "scope": "isolated_F2B_score_not_whole_brain",
        "real_sensor_reads": 0,
        "motor_commands": 0,
        "real_robot_validated": False,
    }


def benchmark_python() -> dict:
    """Host-only warm in-process loop, not an energy/RK3566 measurement."""
    motives = Motivations(0.75, 0.55, 0.60, 0.80, 0.35)
    checksum = 0.0
    start = time.perf_counter()
    for i in range(BENCH_ITERATIONS):
        checksum += PassiveRhythm._score(
            INTENTS[i % len(INTENTS)],
            CATEGORIES[i % len(CATEGORIES)],
            motives,
        )
    elapsed_ms = (time.perf_counter() - start) * 1000
    return {
        "kind": "host_python_existing_brain_score_only",
        "iterations": BENCH_ITERATIONS,
        "checksum": checksum,
        "loop_wall_ms": elapsed_ms,
        "physical_robot_validated": False,
    }


def benchmark_both(rust_bin: str | Path) -> dict:
    """Same score sequence; runtimes/packaging still NOT equivalent."""
    parity = probe_rust(rust_bin)
    rust = subprocess.run(
        [str(Path(rust_bin).resolve()), "--bench"],
        capture_output=True, text=True, timeout=10, check=True,
    )
    rust_info = json.loads(rust.stdout)
    python_info = benchmark_python()
    if (rust_info["iterations"] != BENCH_ITERATIONS
            or rust_info["kind"] != "host_rust_pure_probe"
            or rust_info["physical_robot_validated"] is not False
            or not math.isclose(rust_info["checksum"],
                                python_info["checksum"],
                                rel_tol=1e-10, abs_tol=1e-8)):
        raise RuntimeError("benchmarks did not compute same fictional checksum")
    return {
        "parity": parity, "python": python_info, "rust": rust_info,
        "comparison_status": "host_microbenchmark_only_not_an_embedded_decision",
        "rust_runtime_integration": False, "network_calls": 0,
        "actual_qwen_runs": 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rust-bin", type=Path, help="explicit local rustc output")
    parser.add_argument(
        "--benchmark", action="store_true",
        help="collect host-only score loop timings (not comparable RSS)",
    )
    parser.add_argument(
        "--python-only-bench", action="store_true",
        help="time only the Python scorer in its own HOST process",
    )
    args = parser.parse_args(argv)
    if args.python_only_bench:
        if args.rust_bin is not None or args.benchmark:
            parser.error("--python-only-bench excludes --rust-bin and --benchmark")
        print(json.dumps(benchmark_python(), allow_nan=False, sort_keys=True))
        return 0
    if args.rust_bin is None:
        parser.error("--rust-bin is required; never download/compile automatically")
    outcome = (benchmark_both(args.rust_bin) if args.benchmark
               else {"parity": probe_rust(args.rust_bin)})
    print(json.dumps(outcome, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
