"""N4: bounded SQLite/WAL profile of a temporary fictional memory only.

No database pathname input, no real photos/audio, no robot/model or network.
The ONLY write-capable database is a TemporaryDirectory SQLite owned by
ExperienceMemory. PRAGMA checkpoint is allowed on this disposable fixture.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import sqlite3
from tempfile import TemporaryDirectory

from microduck_companion.category_semantics import (
    CategorySemantics, HYPOTHESIS_CATEGORIES, PROPERTIES, RETENTION_S,
)
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.m1a_multimodal_demo import (
    _synthetic_audio, _synthetic_pixels,
)
from microduck_companion.multiview_pattern_memory import MultiviewPatternMemory

FIXTURE_WALL = 1_780_000_000.0
ACTIVE_KEY = ("ball", "texture", "soft")
EXPECTED_KEYS = sum(len(values) for values in PROPERTIES.values()) * len(HYPOTHESIS_CATEGORIES)


def _file_sizes(path: Path, connection: sqlite3.Connection) -> dict:
    """Byte counts at a single point in time; not an ARM/robot estimate."""
    db = path.stat().st_size if path.exists() else 0
    wal = Path(str(path) + "-wal")
    shm = Path(str(path) + "-shm")
    wal_size = wal.stat().st_size if wal.exists() else 0
    shm_size = shm.stat().st_size if shm.exists() else 0
    return {
        "db_bytes": db, "wal_bytes": wal_size, "shm_bytes": shm_size,
        "combined_bytes": db + wal_size + shm_size,
        "page_size": int(connection.execute("PRAGMA page_size").fetchone()[0]),
        "page_count": int(connection.execute("PRAGMA page_count").fetchone()[0]),
        "freelist_count": int(connection.execute("PRAGMA freelist_count").fetchone()[0]),
    }


def _counts(connection: sqlite3.Connection) -> dict:
    table_names = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    rows = connection.execute(
        "SELECT active,correction_reason,COUNT(*) FROM f4a_property_hypotheses "
        "GROUP BY active,correction_reason"
    ).fetchall()
    corrected = sum(n for active, reason, n in rows
                    if active == 0 and reason == "fixture_annotation_error")
    active = sum(n for flag, _reason, n in rows if flag == 1)
    if any(not (a == 1 or a == 0 and r == "fixture_annotation_error")
           for a, r, _ in rows):
        raise AssertionError("unexpected correction status")
    blobs = connection.execute(
        "SELECT COUNT(*),COALESCE(SUM(LENGTH(fingerprint)),0),"
        "SUM(CASE WHEN (modality='image' AND LENGTH(fingerprint)=64) "
        "OR (modality='audio' AND LENGTH(fingerprint)=16) THEN 0 ELSE 1 END) "
        "FROM m1b_signatures"
    ).fetchone()
    return {
        "table_count": len(table_names),
        "m1a_legacy_table_present": "m1a_compact_patterns" in table_names,
        "hypothesis_active": active, "hypothesis_corrected": corrected,
        "m1b_groups": connection.execute("SELECT COUNT(*) FROM m1b_groups").fetchone()[0],
        "m1b_signatures": blobs[0], "m1b_fingerprint_bytes": blobs[1],
        "invalid_signature_sizes": blobs[2] or 0,
        "legacy_experience_rows": connection.execute("SELECT COUNT(*) FROM experiences").fetchone()[0],
        "sim_motion_rows": connection.execute("SELECT COUNT(*) FROM sim_motion_trials").fetchone()[0],
    }


def _validate_rows(counts: dict, *, corrected: int, active: int) -> None:
    if not (counts["hypothesis_corrected"] == corrected
            and counts["hypothesis_active"] == active
            and counts["m1b_signatures"] == 2
            and counts["m1b_groups"] == 2
            and counts["m1b_fingerprint_bytes"] == 80
            and counts["invalid_signature_sizes"] == 0
            and counts["legacy_experience_rows"] == 0
            and counts["sim_motion_rows"] == 0
            and counts["m1a_legacy_table_present"] is False):
        raise AssertionError("memory provenance or retention invariant failed")


def run_fixture() -> dict:
    """Return aggregate host measurements only; temporary SQLite is erased."""
    if EXPECTED_KEYS != 54:
        raise ValueError("C2 closed vocabulary changed; redo retention review")
    result = {
        "schema": "n4-host-sqlite-wal-fixture-v1",
        "host_platform": platform.system(),
        "sqlite_version": sqlite3.sqlite_version,
        "scope": "temporary synthetic core+F4-A+M1-B; NOT 22-table deployment or ARM",
        "fixture_hypothesis_keys": EXPECTED_KEYS,
        "fixture_ttl_seconds": RETENTION_S,
        "raw_media_persisted": False,
        "real_sensor_reads": 0, "pc_requests": 0, "motor_commands": 0,
    }
    with TemporaryDirectory(prefix="kwipi-n4-fixture-") as folder:
        path = Path(folder) / "memory.sqlite3"
        memory = ExperienceMemory(path)
        try:
            conn = memory.conn
            if conn.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
                raise RuntimeError("host SQLite WAL unavailable")
            conn.execute("PRAGMA wal_autocheckpoint=0")
            semantics = CategorySemantics(memory)
            patterns = MultiviewPatternMemory(memory, r2a_single_writer=True)
            result["baseline"] = _file_sizes(path, conn)
            for category in sorted(HYPOTHESIS_CATEGORIES):
                for prop, allowed in sorted(PROPERTIES.items()):
                    for value in sorted(allowed):
                        hid = semantics.hypothesize(
                            category=category, property=prop, value=value,
                            confidence=0.75, now_wall_epoch_s=FIXTURE_WALL,
                        )
                        if not isinstance(hid, int):
                            raise AssertionError("synthetic hypothesis insertion failed")
                        if (category, prop, value) != ACTIVE_KEY:
                            if not semantics.retract_hypothesis(
                                    hid, reason="fixture_annotation_error"):
                                raise AssertionError("fixture retraction failed")
            image = patterns.observe_image(
                _synthetic_pixels(), now_wall_epoch_s=FIXTURE_WALL + 1,
                category="object")
            audio = patterns.observe_audio(
                _synthetic_audio(), now_wall_epoch_s=FIXTURE_WALL + 2,
                category="ambient")
            if (image.status != "new_group_unverified"
                    or audio.status != "new_group_unverified"):
                raise AssertionError("expected distinct synthetic modality groups")
            result["before_restart"] = _counts(conn)
            _validate_rows(result["before_restart"], corrected=53, active=1)
            result["after_fixture_writes"] = _file_sizes(path, conn)
            if result["after_fixture_writes"]["wal_bytes"] <= 0:
                raise AssertionError("WAL not captured while writer open")
        finally:
            memory.close()
        result["after_first_close_bytes"] = path.stat().st_size
        reopened = ExperienceMemory(path)
        try:
            semantics = CategorySemantics(reopened)
            patterns = MultiviewPatternMemory(reopened, r2a_single_writer=True)
            if reopened.conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise AssertionError("fixture SQLite integrity check failed")
            result["after_restart"] = _counts(reopened.conn)
            _validate_rows(result["after_restart"], corrected=53, active=1)
            later = FIXTURE_WALL + RETENTION_S * 5
            semantics.prune(now_wall_epoch_s=later)
            result["after_prune"] = _counts(reopened.conn)
            _validate_rows(result["after_prune"], corrected=53, active=0)
            if semantics.hypothesize(category="cat", property="texture",
                                     value="hard", confidence=0.95,
                                     now_wall_epoch_s=later) is not None:
                raise AssertionError("retracted claim revived after restart/TTL")
            if semantics.hypotheses(category="cat", now_wall_epoch_s=later):
                raise AssertionError("expired/withdrawn hypotheses surfaced")
            if patterns.stats()["fingerprint_bytes"] != 80:
                raise AssertionError("M1-B signatures changed during reopen")
            result["after_restart_prune_sizes"] = _file_sizes(path, reopened.conn)
            checkpoint = reopened.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            if checkpoint[0] != 0:
                raise AssertionError("fixture checkpoint reported busy")
            result["checkpoint_busy"] = int(checkpoint[0])
            result["after_checkpoint"] = _file_sizes(path, reopened.conn)
            if result["after_checkpoint"]["wal_bytes"] != 0:
                raise AssertionError("WAL not truncated on disposable fixture")
        finally:
            reopened.close()
        result["after_final_close_bytes"] = path.stat().st_size
    result["temporary_database_removed"] = not path.exists()
    if not result["temporary_database_removed"]:
        raise AssertionError("fixture leaked on host")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="aggregate JSON report only")
    args = parser.parse_args()
    report = run_fixture()
    serial = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serial, encoding="utf-8")
    else:
        print(serial)


if __name__ == "__main__":
    main()
