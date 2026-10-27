"""X2-C: offline verification of two *real-daemon CI* passive session reports.

This verifier does NOT start/attest the simulator, import an actuator, infer a
safe floor, issue motor RPCs, query Qwen or learn a causal result. CI must
independently start the pinned official duck-sim and collect fresh reports.
No images, ToF grids, audio or personal identities are read or archived.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sqlite3
import statistics
import subprocess
import sys

PINNED_OEM = {
    "microduck": "942e58e3aa6dbb28e7037203fff11866122c7567",
    "microduck_rl": "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3",
}
REPORT_SOURCE = "official_simulator_sockets_unverified_hardware"
ATTENTION = frozenset(("idle", "rest", "observe_status", "abstain"))
COMPARISONS = frozenset((
    "no_reference", "interrupted", "incompatible_clock", "expired",
    "unknown_battery", "stable_band", "low_to_normal", "normal_to_low",
))
ALLOWED_INTENTIONS = frozenset(("halt", "rest"))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _finite_nonnegative(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _percentile(values: list[float], proportion: float) -> float:
    _require(bool(values), "missing latency samples")
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(proportion * len(ordered)) - 1)], 3)


def _revisions(repo_root: Path) -> dict[str, str]:
    """Check both gitlinks AND the real checked-out OEM commits, fail closed."""
    result: dict[str, str] = {}
    for name, wanted in PINNED_OEM.items():
        path = "upstream/" + name
        tree = subprocess.run(
            ["git", "-C", str(repo_root), "ls-tree", "HEAD", "--", path],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        pieces = tree.split()
        _require(len(pieces) >= 4 and pieces[:2] == ["160000", "commit"]
                 and pieces[2] == wanted and pieces[3] == path,
                 "OEM gitlink changed for " + name)
        actual = subprocess.run(
            ["git", "-C", str(repo_root / path), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.strip()
        _require(actual == wanted, "OEM checkout does not match pinned " + name)
        result[name] = actual
    return result


def validate_acceptance(database: Path, first: dict, second: dict) -> dict:
    """Pure verifier for reports and existing SQLite; no writers or simulator.

    Real OEM daemon execution is a responsibility of the independently
    configured CI job, not something that JSON or a socket can authenticate.
    """
    reports = (first, second)
    session_names: list[str] = []
    samples: list[dict] = []
    for index, report in enumerate(reports):
        _require(type(report) is dict, "session report must be an object")
        session = report.get("session")
        _require(type(session) is str
                 and session == ("x2c-session-a", "x2c-session-b")[index],
                 "wrong or duplicate session")
        session_names.append(session)
        _require(report.get("source") == REPORT_SOURCE,
                 "unrecognized declared data provenance")
        _require(report.get("hardware_validated") is False
                 and report.get("floor_certified") is False,
                 "simulator cannot certify physical robot or safe floor")
        _require(report.get("motor_commands_issued") == 0
                 and report.get("verified_consequences") == 0,
                 "a passive session cannot report an executed action")
        rows = report.get("cycles")
        _require(type(rows) is list and len(rows) == 3,
                 "each session must have exactly three cycles")
        _require(report.get("journal_count") == (index + 1) * 3
                 and report.get("coherent_cycles") == 3,
                 "missing or incoherent cycle; cannot accept simulator run")
        for n, row in enumerate(rows, 1):
            _require(type(row) is dict and row.get("sequence") == n,
                     "cycle sequence invalid")
            _require(row.get("quality") == "coherent"
                     and row.get("intention") in ALLOWED_INTENTIONS
                     and row.get("disposition") == "observation_only",
                     "invalid, unsafe or motor-capable cognitive cycle")
            _require(type(row.get("depth_seq")) is int
                     and row["depth_seq"] >= 0,
                     "depth sequence missing")
            _require(row.get("attention") in ATTENTION
                     and row.get("comparison") in COMPARISONS,
                     "missing X2-B memory interpretation")
            ref = row.get("reference_id")
            _require(ref is None or (type(ref) is int and ref > 0),
                     "malformed memory reference")
        m = report.get("host_metrics")
        _require(type(m) is dict
                 and m.get("latency_basis")
                     == "host_perf_counter_ms_nearest_rank_p95",
                 "host measurement metadata missing")
        _require(_finite_nonnegative(m.get("process_cpu_ms"))
                 and _finite_nonnegative(m.get("session_wall_ms"))
                 and m["session_wall_ms"] > 0,
                 "invalid host CPU or elapsed time")
        rss = m.get("process_peak_rss_kib")
        _require(rss is None or (type(rss) is int and rss > 0),
                 "invalid host RSS")
        _require(type(m.get("sqlite_file_bytes")) is int
                 and m["sqlite_file_bytes"] >= 0
                 and type(m.get("sqlite_wal_bytes")) is int
                 and m["sqlite_wal_bytes"] >= 0,
                 "invalid session storage metadata")
        trace = m.get("samples")
        _require(type(trace) is list and len(trace) == 3,
                 "missing per-cycle latency samples")
        for n, s in enumerate(trace, 1):
            _require(type(s) is dict and s.get("sequence") == n
                     and _finite_nonnegative(s.get("acquisition_ms"))
                     and _finite_nonnegative(s.get("decision_ms")),
                     "invalid or missing measured cycle")
            samples.append(s)
        for key, field in (
            ("acquisition_ms_p50", "acquisition_ms"),
            ("decision_ms_p50", "decision_ms"),
        ):
            values = [float(x[field]) for x in trace]
            _require(_finite_nonnegative(m.get(key))
                     and abs(m[key] - statistics.median(values)) <= 0.0011,
                     "incorrect latency median: " + key)
        for key, field in (
            ("acquisition_ms_p95", "acquisition_ms"),
            ("decision_ms_p95", "decision_ms"),
        ):
            _require(_finite_nonnegative(m.get(key))
                     and abs(m[key] - _percentile(
                         [float(x[field]) for x in trace], .95)) <= 0.0011,
                     "incorrect latency p95: " + key)

    _require(database.is_file(), "missing shared SQLite database")
    # Read-only URI: the verifier must NEVER create/alter another memory DB.
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        _require(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
                 "SQLite integrity check failed")
        rows = db.execute(
            """SELECT id,session,sequence,observed_at,quality,intention,
                      disposition,source,outcome,reward,motor_commands,
                      battery_pct,depth_seq,state_t_ns,depth_t_ns,
                      attention,comparison,reference_id
               FROM sim_passive_cycles ORDER BY id"""
        ).fetchall()
        _require(len(rows) == 6, "not exactly six persisted cycles in same SQLite")
        _require(db.execute("SELECT count(*) FROM experiences").fetchone()[0] == 0,
                 "unverified legacy experience was persisted")
        _require(db.execute(
            "SELECT count(*) FROM sim_motion_trials").fetchone()[0] == 0,
            "motion trial unexpectedly written")
        _require(db.execute(
            "SELECT count(*) FROM intent_preferences").fetchone()[0] == 0,
            "non-executed intention changed preferences")
        _require(db.execute("SELECT count(*) FROM objects").fetchone()[0] == 0,
                 "simulated battery cannot create semantic object identities")

        by_id = {row["id"]: row for row in rows}
        links, cross_links = 0, 0
        for position, row in enumerate(rows):
            session_index, offset = divmod(position, 3)
            from_report = reports[session_index]["cycles"][offset]
            _require(row["session"] == session_names[session_index]
                     and row["sequence"] == offset + 1
                     and row["quality"] == "coherent"
                     and row["source"] == "simulator_ipc"
                     and row["outcome"] == "no_action_executed"
                     and row["reward"] is None
                     and row["motor_commands"] == 0
                     and row["intention"] in ALLOWED_INTENTIONS
                     and row["disposition"] == "observation_only",
                     "SQLite journal lacks trustworthy passive provenance")
            for key in ("intention", "depth_seq", "attention",
                        "comparison", "reference_id"):
                _require(row[key] == from_report[key],
                         "session report differs from persisted row: " + key)
            ref = row["reference_id"]
            if ref is not None:
                prior = by_id.get(ref)
                _require(prior is not None and prior["id"] < row["id"]
                         and prior["quality"] == "coherent"
                         and prior["source"] == "simulator_ipc"
                         and prior["motor_commands"] == 0
                         and prior["outcome"] == "no_action_executed"
                         and prior["reward"] is None,
                         "unverifiable historical memory reference")
                _require(prior["battery_pct"] is not None
                         and row["battery_pct"] is not None
                         and 0 < row["observed_at"] - prior["observed_at"] <= 60
                         and row["depth_seq"] > prior["depth_seq"]
                         and all(x is not None and y is not None and x > y
                                 for x, y in (
                                     (row["state_t_ns"], prior["state_t_ns"]),
                                     (row["depth_t_ns"], prior["depth_t_ns"]))),
                         "stale, reset, unknown or non-advancing memory source")
                low0, low1 = prior["battery_pct"] <= 15, row["battery_pct"] <= 15
                expected = ("stable_band" if low0 == low1 else
                            "low_to_normal" if low0 else "normal_to_low")
                _require(row["comparison"] == expected,
                         "memory comparison contradicts source observations")
                links += 1
                cross_links += int(prior["session"] != row["session"])
            else:
                _require(row["comparison"] not in
                         {"stable_band", "low_to_normal", "normal_to_low"},
                         "unreferenced memory is being reported as verified")

    def summarize(field: str) -> dict[str, float]:
        vals = [float(s[field]) for s in samples]
        return {
            "p50_ms": round(statistics.median(vals), 3),
            "p95_ms": _percentile(vals, .95),
            "max_ms": round(max(vals), 3),
        }

    return {
        "contract": "X2-C-read-only-passive-official-MuJoCo-CI",
        "accepted": True,
        "sessions": session_names,
        "cycles": 6,
        "coherent_cycles": 6,
        "simulator_source_claim": REPORT_SOURCE,
        "hardware_validated": False,
        "floor_certified": False,
        "motor_commands_issued_by_companion": 0,
        "verified_consequences": 0,
        "local_pc_transport_configured": False,
        "memory_context": {
            "linked_observations": links,
            "cross_session_links": cross_links,
            "status": "observed" if links else "not_demonstrated",
        },
        "host_latency": {
            "acquisition": summarize("acquisition_ms"),
            "decision": summarize("decision_ms"),
        },
        "host_resources": {
            "session_cpu_ms": [
                r["host_metrics"]["process_cpu_ms"] for r in reports],
            "session_wall_ms": [
                r["host_metrics"]["session_wall_ms"] for r in reports],
            "process_peak_rss_kib": [
                r["host_metrics"]["process_peak_rss_kib"] for r in reports],
        },
        "storage": {
            "sqlite_bytes": database.stat().st_size,
            "sqlite_wal_bytes": Path(str(database) + "-wal").stat().st_size
                if Path(str(database) + "-wal").is_file() else 0,
            "journal_rows": 6,
            "integrity": "ok",
        },
        "evidence_limit": (
            "OEM daemons are started by CI; socket and JSON do not "
            "authenticate physical hardware. No causal action was executed."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="X2-C: verify passive MuJoCo reports without motor authority")
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        # This is evidence of pinned *checkout*, not of sensor identity.
        revisions = _revisions(args.repo_root)
        first = json.loads(args.first.read_text(encoding="utf-8"))
        second = json.loads(args.second.read_text(encoding="utf-8"))
        result = validate_acceptance(args.database, first, second)
        result["pinned_checkout"] = revisions
    except (ValueError, OSError, sqlite3.Error, subprocess.SubprocessError,
            json.JSONDecodeError, KeyError, TypeError) as exc:
        print("X2-C acceptance FAILED: " + str(exc), file=sys.stderr)
        return 1
    # Output contains only coarse simulator status and host metrics. No media.
    output = json.dumps(result, indent=2, sort_keys=True)
    args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
