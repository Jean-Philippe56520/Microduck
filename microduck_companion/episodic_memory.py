"""Local experience memory: an LLM suggestion is never a verified observation."""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3
import math
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


@dataclass(frozen=True)
class SimulatedMotionExperience:
    """Observed MuJoCo outcome, never a physical-robot measurement."""

    outcome: str
    measured_m: float
    baseline_m: float
    simulated_duration_s: float
    source: str
    reward: float | None
    updated_preference: float
    observed_trials: int


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
            CREATE TABLE IF NOT EXISTS sim_motion_trials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                source TEXT NOT NULL CHECK(source='mujoco_verified_pose'),
                action TEXT NOT NULL CHECK(action='explore'),
                measured_m REAL NOT NULL CHECK(measured_m>=0),
                baseline_m REAL NOT NULL CHECK(baseline_m>=0),
                simulated_duration_s REAL NOT NULL CHECK(simulated_duration_s>0),
                stop_confirmed INTEGER NOT NULL,
                healthy_after INTEGER NOT NULL,
                safe_after INTEGER NOT NULL,
                outcome TEXT NOT NULL,
                reward REAL
            );
            CREATE TABLE IF NOT EXISTS intent_preferences (
                environment TEXT NOT NULL,
                action TEXT NOT NULL,
                preference REAL NOT NULL DEFAULT 0,
                observations INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(environment, action)
            );
        """)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def observe(self, identifier: str, label: str = "unknown",
                source: str = "sensor") -> KnownObject:
        if not identifier:
            raise ValueError("identifier cannot be empty")
        if source not in {"sensor", "simulator", "mock"}:
            raise ValueError("observation source must be sensor, simulator or mock")
        source = source if label != "unknown" else "unknown"
        with self.conn:
            self.conn.execute("""
                INSERT INTO objects(identifier,label,label_source,sightings,last_seen)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(identifier) DO UPDATE SET
                    sightings=sightings+1,
                    last_seen=excluded.last_seen,
                    label=CASE WHEN excluded.label!='unknown' AND (
                        objects.label_source IN ('unknown','llm_suggestion')
                        OR (excluded.label_source='sensor'
                            AND objects.label_source IN ('simulator','mock'))
                        OR (excluded.label_source='simulator'
                            AND objects.label_source='mock')
                    ) THEN excluded.label ELSE objects.label END,
                    label_source=CASE WHEN excluded.label!='unknown' AND (
                        objects.label_source IN ('unknown','llm_suggestion')
                        OR (excluded.label_source='sensor'
                            AND objects.label_source IN ('simulator','mock'))
                        OR (excluded.label_source='simulator'
                            AND objects.label_source='mock')
                    ) THEN excluded.label_source ELSE objects.label_source END
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

    def intent_preference(self, environment: str, action: str) -> float:
        """Only verified trials can affect this simulator-specific preference."""
        row = self.conn.execute(
            """SELECT preference FROM intent_preferences
               WHERE environment=? AND action=?""", (environment, action)
        ).fetchone()
        return float(row["preference"]) if row is not None else 0.0

    def record_simulated_motion(
        self, *, measured_m: float, baseline_m: float,
        simulated_duration_s: float, stop_confirmed: bool,
        healthy_after: bool, safe_after: bool,
    ) -> SimulatedMotionExperience:
        """Persist an observed simulator trial and learn *only* when verified.

        Measured translation is not proof of walking: contact/gait and motor
        effectiveness are not independently observed here. A large baseline
        drift makes the result inconclusive. Unknown/unsafe cases are logged
        but never used as reward. No LLM hypothesis enters this path.
        """
        for key, value in (
            ("measured_m", measured_m), ("baseline_m", baseline_m),
            ("simulated_duration_s", simulated_duration_s),
        ):
            if type(value) not in (float, int) or not math.isfinite(value):
                raise ValueError(f"{key} must be a finite number")
        if measured_m < 0 or baseline_m < 0 or not 0 < simulated_duration_s <= 10:
            raise ValueError("invalid simulated trial measurements")
        if any(type(x) is not bool for x in
               (stop_confirmed, healthy_after, safe_after)):
            raise ValueError("attestations must be booleans")
        verified = stop_confirmed and healthy_after and safe_after
        reward: float | None = None
        if not verified:
            outcome = "unverified"
        elif baseline_m > 0.005:
            outcome = "inconclusive_drift"
        elif measured_m >= max(0.01, 3 * baseline_m + 0.005):
            outcome, reward = "translation_observed", 0.5
        else:
            outcome, reward = "no_progress_observed", -0.5

        with self.conn:
            self.conn.execute(
                """INSERT INTO sim_motion_trials(
                      timestamp,source,action,measured_m,baseline_m,
                      simulated_duration_s,stop_confirmed,healthy_after,
                      safe_after,outcome,reward)
                   VALUES (?,'mujoco_verified_pose','explore',?,?,?,?,?,?,?,?)""",
                (time.time(), measured_m, baseline_m, simulated_duration_s,
                 int(stop_confirmed), int(healthy_after), int(safe_after),
                 outcome, reward),
            )
            if reward is not None:
                previous = self.intent_preference("simulator", "explore")
                # Small observed adjustment; never interpreted as model training.
                updated = max(-1., min(1., previous * 0.85 + reward * 0.15))
                self.conn.execute(
                    """INSERT INTO intent_preferences(
                         environment,action,preference,observations)
                       VALUES ('simulator','explore',?,1)
                       ON CONFLICT(environment,action) DO UPDATE SET
                         preference=excluded.preference,
                         observations=observations+1""",
                    (updated,),
                )
        pref = self.intent_preference("simulator", "explore")
        observed = self.conn.execute(
            """SELECT COUNT(*) FROM sim_motion_trials
               WHERE source='mujoco_verified_pose' AND action='explore'"""
        ).fetchone()[0]
        return SimulatedMotionExperience(
            outcome, float(measured_m), float(baseline_m),
            float(simulated_duration_s), "mujoco_verified_pose",
            reward, pref, observed,
        )

    def simulated_motion_history(self) -> list[SimulatedMotionExperience]:
        """Source-labelled trials; read without inferring anything about hardware."""
        rows = self.conn.execute(
            """SELECT measured_m,baseline_m,simulated_duration_s,outcome,reward
               FROM sim_motion_trials ORDER BY id"""
        ).fetchall()
        preference = self.intent_preference("simulator", "explore")
        return [
            SimulatedMotionExperience(
                r["outcome"], r["measured_m"], r["baseline_m"],
                r["simulated_duration_s"], "mujoco_verified_pose",
                r["reward"], preference, len(rows),
            )
            for r in rows
        ]
