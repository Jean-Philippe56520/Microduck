"""Kwipi's on-demand, read-only PC viewer for EX1/EX2/EX3 MOCK evidence.

Reads an existing SQLite snapshot (or a stable database available locally).
Does not open ExperienceMemory, create tables, start daemons, contact a robot,
poll continuously, or join independent P2a/F4-A evidence into fake causality.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import csv
import io
import json
import math
from pathlib import Path
import sqlite3
import sys
import time

from .experience_ledger import RETENTION_S, _key
from .experience_expectations import compute_mock_attention_trend
from .passive_observations import OBJECT_CATEGORIES
from .perception import _SOUND_CATEGORIES

MAX_ROWS = 50
STATUSES = frozenset({"proposed", "mock_executed", "refused", "interrupted"})
CATEGORIES = OBJECT_CATEGORIES | _SOUND_CATEGORIES
FIELDS = (
    "session", "sequence", "time_epoch_s", "intention", "category",
    "status", "effect_status", "cue_kind", "before", "after",
    "association_status", "reason_code", "corrected",
    "source", "causality_established", "verified_on_robot",
    "motor_commands_issued",
)


def _time(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("invalid nonnegative timestamp")
    return float(value)


def read_journal(
    path: str | Path, *, now_wall_epoch_s: float,
    limit: int = 20, category: str | None = None,
    status: str | None = None, include_withdrawn: bool = False,
) -> tuple[dict, ...]:
    """Query only retained, existing fictional evidence, without mutating it.

    Parent/child correction is visible as 'withdrawn' when requested, not as
    a verified outcome. The viewer tolerates an EX1-only database.
    """
    now = _time(now_wall_epoch_s)
    if type(limit) is not int or not 1 <= limit <= MAX_ROWS:
        raise ValueError("limit must be an integer 1..50")
    if category is not None and (type(category) is not str
                                 or category not in CATEGORIES):
        raise ValueError("unsupported category filter")
    if status is not None and (type(status) is not str
                               or status not in STATUSES):
        raise ValueError("unsupported status filter")
    if type(include_withdrawn) is not bool:
        raise ValueError("include_withdrawn must be boolean")
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError("SQLite file not found")
    # The read-only URI and query-only mode exclude schema creation and writes.
    conn = sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only=ON")
        schema = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND "
                "name IN ('ex1_mock_experiences','ex2_mock_effects')"
            )
        }
        if "ex1_mock_experiences" not in schema:
            raise ValueError("not an EX1 experience database")
        has_effects = "ex2_mock_effects" in schema
        extra = (
            "e.cue_kind AS cue_kind,e.before_value AS before_value,"
            "e.after_value AS after_value,e.effect_status AS effect_status,"
            "e.association_status AS association_status,"
            "e.reason_code AS reason_code,e.active AS effect_active"
            if has_effects else
            "NULL AS cue_kind,NULL AS before_value,NULL AS after_value,"
            "NULL AS effect_status,NULL AS association_status,"
            "NULL AS reason_code,NULL AS effect_active"
        )
        join = (
            "LEFT JOIN ex2_mock_effects e ON e.ex1_id=p.id"
            if has_effects else ""
        )
        filters = [
            "p.source='mock_fixture_only'",
            "p.proposed_at_epoch_s BETWEEN ? AND ?",
        ]
        args: list[object] = [now - RETENTION_S, now]
        if not include_withdrawn:
            filters.append("p.active=1")
        if category is not None:
            filters.append("p.target_category=?")
            args.append(category)
        if status is not None:
            filters.append("p.status=?")
            args.append(status)
        args.append(limit)
        sql = (
            "SELECT p.session,p.sequence,p.intention,p.target_category,"
            "p.status,p.proposed_at_epoch_s,p.active AS proposal_active,"
            + extra + " FROM ex1_mock_experiences p " + join +
            " WHERE " + " AND ".join(filters) +
            " ORDER BY p.proposed_at_epoch_s DESC,p.id DESC LIMIT ?"
        )
        rows = conn.execute(sql, args).fetchall()
        result: list[dict] = []
        for r in rows:
            parent_active = r["proposal_active"] == 1
            effect_active = r["effect_active"] == 1
            corrected = not parent_active or (
                r["effect_active"] is not None and not effect_active
            )
            if not parent_active:
                effect_status = "withdrawn"
                reason = "proposal_withdrawn"
                assoc = "indeterminate"
                before = after = cue = None
            elif r["effect_active"] is not None and not effect_active:
                effect_status = "withdrawn"
                reason = "effect_withdrawn"
                assoc = "indeterminate"
                before = after = cue = None
            elif effect_active:
                effect_status = r["effect_status"]
                reason = r["reason_code"]
                assoc = r["association_status"]
                before = r["before_value"]
                after = r["after_value"]
                cue = r["cue_kind"]
            else:
                effect_status = "not_recorded"
                reason = "no_effect_evidence"
                assoc = "indeterminate"
                before = after = cue = None
            result.append({
                "session": r["session"],
                "sequence": int(r["sequence"]),
                "time_epoch_s": float(r["proposed_at_epoch_s"]),
                "intention": r["intention"],
                "category": r["target_category"],
                "status": r["status"] if parent_active else "withdrawn",
                "effect_status": effect_status,
                "cue_kind": cue,
                "before": before,
                "after": after,
                "association_status": assoc,
                "reason_code": reason,
                "corrected": corrected,
                "source": "mock_fixture_only",
                "causality_established": False,
                "verified_on_robot": False,
                "motor_commands_issued": 0,
            })
        return tuple(result)
    finally:
        conn.close()


def read_attention_trend(
    path: str | Path, *, intention: str, category: str,
    now_wall_epoch_s: float,
) -> dict:
    """Read one EX3 mock tendency from an existing EX1+EX2 SQLite only.

    This voluntary operation is read-only, not ongoing telemetry. A
    fictional temporal correlation is never an authenticated cause or reward.
    """
    now = _time(now_wall_epoch_s)
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError("SQLite file not found")
    conn = sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name IN ('ex1_mock_experiences','ex2_mock_effects')"
            )
        }
        if not {"ex1_mock_experiences", "ex2_mock_effects"} <= tables:
            raise ValueError("EX1 and EX2 fixture tables are required")
        return asdict(compute_mock_attention_trend(
            conn, intention=intention, category=category,
            now_wall_epoch_s=now,
        ))
    finally:
        conn.close()


TREND_FIELDS = (
    "intention", "category", "distinct_mock_sessions", "changed", "unchanged",
    "attention_bias", "status", "source", "causality_established",
    "verified_on_robot", "motor_commands_issued",
)


def render_attention_trend(row: dict, *, format: str = "jsonl") -> str:
    """Explicitly label derived mock hints as fictional in JSONL/CSV."""
    if format not in ("jsonl", "csv"):
        raise ValueError("unsupported output format")
    selected = {field: row[field] for field in TREND_FIELDS}
    if format == "jsonl":
        return json.dumps(
            selected, ensure_ascii=True, separators=(",", ":"),
        ) + "\n"
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=TREND_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerow(selected)
    return output.getvalue()


def render_journal(rows: tuple[dict, ...], *, format: str = "jsonl") -> str:
    """Return limited, fixed-schema JSONL or CSV; never enrich with PII."""
    if format not in ("jsonl", "csv"):
        raise ValueError("unsupported output format")
    output = io.StringIO()
    if format == "csv":
        writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row[name] for name in FIELDS})
    else:
        for row in rows:
            output.write(json.dumps(
                {name: row[name] for name in FIELDS},
                ensure_ascii=True, separators=(",", ":"),
            ) + "\n")
    return output.getvalue()



# OBS-1: conservative diagnostic projection of the EXISTING read-only EX1/EX2
# fixture viewer, not a new logger or a real robot execution trace.
OBS1_SCHEMA_VERSION = 1
OBS1_REASON_CODES = frozenset({
    "no_effect_evidence", "proposal_withdrawn", "effect_withdrawn",
    "unknown_cue_or_category", "low_mock_confidence",
    "scene_not_correlated", "no_observed_change",
    "competing_event", "after_mock_resolution",
})
OBS1_ASSOCIATIONS = frozenset({
    "indeterminate", "none", "temporal_only", "confounded",
})
OBS1_EFFECTS = frozenset({
    "not_recorded", "withdrawn", "indeterminate", "unchanged", "changed",
})


def render_episode_diagnostics(rows: tuple[dict, ...]) -> str:
    """Project EX1/EX2 MOCK read_journal rows as bounded diagnostic JSONL.

    No database, network, camera, motor, Qwen or free-text source is read here.
    Refuse unsupported, malicious or contradictory rows instead of upgrading a
    fictional resolution to an actual OEM receipt or measured consequence.
    """
    if type(rows) is not tuple or len(rows) > MAX_ROWS:
        raise ValueError("OBS-1 requires a bounded journal tuple")
    seen: set[tuple[str, int]] = set()
    last_time = float("inf")
    out = io.StringIO()
    for row in rows:
        if type(row) is not dict or set(row) != set(FIELDS):
            raise ValueError("OBS-1 requires exact EX1/EX2 journal fields")
        key = _key(row["session"], row["sequence"])
        at = _time(row["time_epoch_s"])
        if key in seen or at > last_time:
            raise ValueError("duplicate or unordered OBS-1 episode")
        seen.add(key)
        last_time = at
        if (row["source"] != "mock_fixture_only"
                or row["causality_established"] is not False
                or row["verified_on_robot"] is not False
                or type(row["motor_commands_issued"]) is not int
                or row["motor_commands_issued"] != 0):
            raise ValueError("OBS-1 cannot import real execution claims")
        if (type(row["intention"]) is not str
                or row["intention"] not in {
                    "observe", "inspect", "listen", "idle", "rest"
                }
                or (row["category"] is not None and
                    (type(row["category"]) is not str
                     or row["category"] not in CATEGORIES))):
            raise ValueError("unsupported OBS-1 fixture target")
        status, effect = row["status"], row["effect_status"]
        association, reason = row["association_status"], row["reason_code"]
        corrected = row["corrected"]
        if (type(status) is not str
                or status not in STATUSES | {"withdrawn"}
                or type(effect) is not str or effect not in OBS1_EFFECTS
                or type(association) is not str
                or association not in OBS1_ASSOCIATIONS
                or type(reason) is not str or reason not in OBS1_REASON_CODES
                or type(corrected) is not bool):
            raise ValueError("invalid OBS-1 resolution or reason")
        if status == "withdrawn":
            valid = corrected and (effect, association, reason) == (
                "withdrawn", "indeterminate", "proposal_withdrawn")
        elif corrected:
            valid = status == "mock_executed" and (
                effect, association, reason) == (
                    "withdrawn", "indeterminate", "effect_withdrawn")
        elif effect == "not_recorded":
            valid = association == "indeterminate" and reason == "no_effect_evidence"
        else:
            valid = status == "mock_executed" and (
                (effect == "changed" and (
                    (association, reason) in {
                        ("temporal_only", "after_mock_resolution"),
                        ("confounded", "competing_event"),
                    }))
                or (effect == "unchanged" and (
                    association, reason) == ("none", "no_observed_change"))
                or (effect == "indeterminate"
                    and association == "indeterminate"
                    and reason in {
                        "unknown_cue_or_category",
                        "low_mock_confidence", "scene_not_correlated",
                    }))
        if not valid:
            raise ValueError("contradictory OBS-1 fixture lifecycle")
        # These are assertions about *absence of proof* in the mock viewer,
        # not statements about any real robot. Never upgrade mock_executed.
        record = {
            "schema_version": OBS1_SCHEMA_VERSION,
            "episode_id": f"{key[0]}:{key[1]}",
            "proposed_at_epoch_s": at,
            "intention": row["intention"],
            "category": row["category"] or "unknown",
            "fixture_resolution": status,
            "mock_effect": effect,
            "mock_association": association,
            "reason_code": reason,
            "corrected": corrected,
            "decision_context": "not_recorded",
            "qwen_context": "not_recorded",
            "oem_authorization": "not_attested",
            "oem_execution": "not_attested",
            "physical_effect": "not_attested",
            "causality": "unproven",
            "source": "mock_fixture_only",
            "verified_on_robot": False,
            "motor_commands_issued": 0,
        }
        out.write(json.dumps(record, ensure_ascii=True,
                             separators=(",", ":")) + "\n")
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Journal de Kwipi : lecture locale EX1/EX2 et tendances EX3 fictives uniquement"
    )
    parser.add_argument("database", help="SQLite existante, locale, en lecture seule")
    parser.add_argument("--at", type=float, default=None,
                        help="heure de consultation, epoch UTC (fixtures)")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--category")
    parser.add_argument("--status", choices=sorted(STATUSES))
    parser.add_argument("--format", choices=("jsonl", "csv"), default="jsonl")
    parser.add_argument("--include-withdrawn", action="store_true")
    parser.add_argument("--diagnostic", action="store_true",
                        help="OBS-1 fictional episode diagnostics as bounded JSONL")
    parser.add_argument("--trend", choices=("observe", "listen"),
                        help="résumé EX3 fictif (nécessite --category)")
    args = parser.parse_args(argv)
    try:
        if args.diagnostic and (args.trend is not None
                                or args.format != "jsonl"):
            raise ValueError("--diagnostic requires JSONL without --trend")
        now = time.time() if args.at is None else args.at
        if args.trend is not None:
            if args.category is None:
                raise ValueError("--trend requires --category")
            row = read_attention_trend(
                args.database, intention=args.trend,
                category=args.category, now_wall_epoch_s=now,
            )
            output = render_attention_trend(row, format=args.format)
        else:
            rows = read_journal(
                args.database, now_wall_epoch_s=now,
                limit=args.limit, category=args.category,
                status=args.status, include_withdrawn=args.include_withdrawn,
            )
            output = (render_episode_diagnostics(rows) if args.diagnostic
                      else render_journal(rows, format=args.format))
    except (ValueError, FileNotFoundError, sqlite3.Error, OSError) as exc:
        print("Journal non disponible : " + str(exc), file=sys.stderr)
        return 2
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
