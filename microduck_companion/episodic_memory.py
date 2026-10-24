"""Local experience memory: an LLM suggestion is never a verified observation."""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3
import time
from pathlib import Path


@dataclass(frozen=True)
class KnownObject:
    identifier: str
    label: str
    label_source: str
    sightings: int
    preference: float
    analysis_requested: bool


class ExperienceMemory:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS objects (
                identifier TEXT PRIMARY KEY,
                label TEXT NOT NULL DEFAULT 'unknown',
                label_source TEXT NOT NULL DEFAULT 'unknown',
                sightings INTEGER NOT NULL DEFAULT 0,
                preference REAL NOT NULL DEFAULT 0,
                analysis_requested INTEGER NOT NULL DEFAULT 0,
                last_seen REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                object_id TEXT,
                action TEXT NOT NULL,
                outcome REAL,
                note TEXT NOT NULL DEFAULT ''
            );
        """)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def observe(self, identifier: str, label: str = "unknown") -> KnownObject:
        if not identifier:
            raise ValueError("identifier cannot be empty")
        source = "sensor" if label != "unknown" else "unknown"
        with self.conn:
            self.conn.execute("""
                INSERT INTO objects(identifier,label,label_source,sightings,last_seen)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(identifier) DO UPDATE SET
                    sightings=sightings+1,
                    last_seen=excluded.last_seen,
                    label=CASE WHEN objects.label='unknown' AND excluded.label!='unknown'
                               THEN excluded.label ELSE objects.label END,
                    label_source=CASE WHEN objects.label='unknown' AND excluded.label!='unknown'
                                      THEN excluded.label_source ELSE objects.label_source END
            """, (identifier, label, source, time.time()))
        return self.get(identifier)

    def get(self, identifier: str) -> KnownObject | None:
        row = self.conn.execute(
            "SELECT * FROM objects WHERE identifier=?", (identifier,)
        ).fetchone()
        if row is None:
            return None
        return KnownObject(
            row["identifier"], row["label"], row["label_source"],
            row["sightings"], row["preference"], bool(row["analysis_requested"])
        )

    def ask_analysis_once(self, identifier: str) -> bool:
        with self.conn:
            result = self.conn.execute("""
                UPDATE objects SET analysis_requested=1
                WHERE identifier=? AND analysis_requested=0 AND label='unknown'
            """, (identifier,))
        return result.rowcount == 1

    def suggest_label(self, identifier: str, suggestion: str) -> None:
        """Store a model hypothesis as such; never give it the status of sensor truth."""
        if not suggestion or suggestion == "unknown":
            return
        with self.conn:
            self.conn.execute("""
                UPDATE objects SET label=?, label_source='llm_suggestion'
                WHERE identifier=? AND label_source='unknown'
            """, (suggestion, identifier))

    def record_action(self, action: str, object_id: str | None = None,
                      note: str = "") -> None:
        with self.conn:
            self.conn.execute("""
                INSERT INTO experiences(timestamp,object_id,action,note)
                VALUES (?, ?, ?, ?)
            """, (time.time(), object_id, action, note))

    def learn_from_outcome(self, identifier: str, action: str, reward: float) -> float:
        """Only verified observed outcomes should be passed as feedback."""
        if not -1 <= reward <= 1:
            raise ValueError("reward must be in [-1, 1]")
        previous = self.get(identifier)
        if previous is None:
            raise KeyError(identifier)
        updated = max(-1.0, min(1.0, previous.preference * 0.85 + 0.15 * reward))
        with self.conn:
            self.conn.execute(
                "UPDATE objects SET preference=? WHERE identifier=?",
                (updated, identifier)
            )
            self.conn.execute("""
                INSERT INTO experiences(timestamp,object_id,action,outcome,note)
                VALUES (?, ?, ?, ?, 'observed_outcome')
            """, (time.time(), identifier, action, reward))
        return updated

    def experience_count(self) -> int:
        return self.conn.execute("SELECT count(*) FROM experiences").fetchone()[0]
