"""F4-B: uncertain *fictional* spatial landmarks in existing SQLite.

This is NOT SLAM, a map, a relative robot pose, navigation, obstacle
detection, a floor-clearance decision, or a real coordinate measurement.
No sensor has been authenticated. Input is an explicit mock fixture with
a declared local frame, reported circular uncertainty and confidence;
all output is historical and non-actionable.

Only a small fixed vocabulary of non-person categories and TWO artificial
frames is supported. Never persist a person's/pet's identity, arbitrary
place name, ephemeral track, images, audio, robot pose, or occupancy grid.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sqlite3
import uuid

from .episodic_memory import ExperienceMemory
from .passive_memory import _check_wall

LANDMARKS = frozenset({"toy", "ball", "table", "door", "wall"})
FRAMES = frozenset({"mock_zone_a", "mock_zone_b"})
CORRECTION_REASONS = frozenset({"fixture_annotation_error", "source_retracted"})
RETAIN_SECONDS = 14 * 24 * 3600
MAX_ROWS = 256
MAX_QUERY = 50
MAX_COORD_M = 10.0
MIN_RADIUS_M = 0.05
MAX_RADIUS_M = 2.0
MIN_REPORT_CONFIDENCE = 0.70
MAX_FIXTURE_AGE_S = 1.0
MAX_CLOCK_DELTA_S = 2.0


class SpatialMemoryError(ValueError):
    """Malformed mock spatial evidence; cannot be used for navigation."""


def _number(value: object, name: str, *, lo: float, hi: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise SpatialMemoryError(f"invalid {name}")
    f = float(value)
    if not lo <= f <= hi:
        raise SpatialMemoryError(f"out-of-range {name}")
    return f


@dataclass(frozen=True)
class MockSpatialObservation:
    """A declared fixture, not a sensor report, with circular error radius.

    Coordinate axes belong to the named *fictional* frame and have no
    transform to the robot body or a real room. No spatial path is inferred.
    """

    frame: str
    landmark: str
    x_m: float
    y_m: float
    uncertainty_radius_m: float
    reported_confidence: float
    observed_monotonic_s: float
    observed_epoch_s: float
    sequence: int
    source: str = "mock"
    channel: str = "mock_spatial_fixture"
    environment: str = "mock"

    def __post_init__(self) -> None:
        if (type(self.frame) is not str or self.frame not in FRAMES
                or type(self.landmark) is not str or self.landmark not in LANDMARKS):
            raise SpatialMemoryError("only anonymous, fixed mock landmark categories")
        if (self.source != "mock" or self.channel != "mock_spatial_fixture"
                or self.environment != "mock"):
            raise SpatialMemoryError("no authenticated spatial sensor adapter")
        if type(self.sequence) is not int or not 1 <= self.sequence < 2**63:
            raise SpatialMemoryError("invalid mock session sequence")
        _number(self.x_m, "x", lo=-MAX_COORD_M, hi=MAX_COORD_M)
        _number(self.y_m, "y", lo=-MAX_COORD_M, hi=MAX_COORD_M)
        _number(self.uncertainty_radius_m, "uncertainty radius",
                lo=MIN_RADIUS_M, hi=MAX_RADIUS_M)
        _number(self.reported_confidence, "reported confidence", lo=0., hi=1.)
        _number(self.observed_monotonic_s, "monotonic stamp", lo=0., hi=1e15)
        _number(self.observed_epoch_s, "wall stamp", lo=0., hi=1e15)


@dataclass(frozen=True)
class SpatialRecall:
    frame: str
    landmark: str
    status: str
    observations: int
    x_m: float | None = None
    y_m: float | None = None
    uncertainty_radius_m: float | None = None
    reported_confidence: float | None = None
    source: str = "mock_spatial_fixture_only"
    historical_only: bool = True
    real_reference_frame_verified: bool = False
    real_sensor_authenticated: bool = False
    floor_clearance_verified: bool = False
    navigation_authorized: bool = False
    motor_commands_issued: int = 0


class UncertainSpatialMemory:
    """Historical mock landmarks, independent of any motion control path.

    A new instance creates a new per-process session. Replaying sequences
    does not count again. Returned coordinates are NEVER a current
    observation and cannot authorize locomotion or a room-scale map.
    """

    def __init__(self, memory: ExperienceMemory) -> None:
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("requires existing ExperienceMemory")
        self._memory = memory
        self.session_id = uuid.uuid4().hex
        with memory.conn:
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS f4b_mock_spatial_observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL CHECK(sequence>=1),
                    frame TEXT NOT NULL CHECK(frame IN ('mock_zone_a','mock_zone_b')),
                    landmark TEXT NOT NULL CHECK(
                        landmark IN ('toy','ball','table','door','wall')),
                    x_m REAL NOT NULL CHECK(x_m BETWEEN -10 AND 10),
                    y_m REAL NOT NULL CHECK(y_m BETWEEN -10 AND 10),
                    uncertainty_radius_m REAL NOT NULL CHECK(
                        uncertainty_radius_m BETWEEN 0.05 AND 2),
                    reported_confidence REAL NOT NULL CHECK(
                        reported_confidence BETWEEN 0 AND 1),
                    observed_epoch_s REAL NOT NULL CHECK(observed_epoch_s>=0),
                    source TEXT NOT NULL CHECK(source='mock_spatial_fixture'),
                    active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
                    correction_reason TEXT CHECK(correction_reason IS NULL
                        OR correction_reason IN (
                            'fixture_annotation_error','source_retracted')),
                    UNIQUE(session_id,sequence)
                )
            """)
            memory.conn.execute("""
                CREATE INDEX IF NOT EXISTS f4b_spatial_by_frame_and_time
                ON f4b_mock_spatial_observations(
                    frame,landmark,observed_epoch_s DESC,id DESC)
            """)

    def _prune(self, now: float) -> int:
        db = self._memory.conn
        old = db.execute(
            "SELECT COUNT(*) FROM f4b_mock_spatial_observations"
        ).fetchone()[0]
        db.execute("""
            DELETE FROM f4b_mock_spatial_observations
            WHERE observed_epoch_s < ? OR observed_epoch_s > ?
        """, (now - RETAIN_SECONDS, now + MAX_CLOCK_DELTA_S))
        db.execute("""
            DELETE FROM f4b_mock_spatial_observations WHERE id NOT IN (
                SELECT id FROM f4b_mock_spatial_observations
                ORDER BY observed_epoch_s DESC,id DESC LIMIT ?
            )
        """, (MAX_ROWS,))
        retained = db.execute(
            "SELECT COUNT(*) FROM f4b_mock_spatial_observations"
        ).fetchone()[0]
        return int(old - retained)

    def prune(self, *, now_wall_epoch_s: float) -> int:
        with self._memory.conn:
            return self._prune(_check_wall(now_wall_epoch_s))

    def append(self, reading: MockSpatialObservation, *,
               now_monotonic_s: float, now_wall_epoch_s: float) -> bool:
        """Persist one *fresh fixture only*, never an inferred robot position.

        Same-session sequence must strictly grow. Identical replay is
        idempotent, conflicting replay fails closed, even when retracted.
        """
        if not isinstance(reading, MockSpatialObservation):
            raise TypeError("requires MockSpatialObservation")
        now_wall = _check_wall(now_wall_epoch_s)
        now_mono = _number(now_monotonic_s, "decision monotonic clock",
                           lo=0., hi=1e15)
        lag = now_mono - float(reading.observed_monotonic_s)
        wall_lag = now_wall - float(reading.observed_epoch_s)
        if not 0 <= lag <= MAX_FIXTURE_AGE_S:
            raise SpatialMemoryError("stale/future mock monotonic stamp")
        if not 0 <= wall_lag <= MAX_CLOCK_DELTA_S:
            raise SpatialMemoryError("stale/future mock wall timestamp")
        with self._memory.conn:
            db = self._memory.conn
            prior = db.execute("""
                SELECT frame,landmark,x_m,y_m,uncertainty_radius_m,
                       reported_confidence,observed_epoch_s
                FROM f4b_mock_spatial_observations
                WHERE session_id=? AND sequence=?
            """, (self.session_id, reading.sequence)).fetchone()
            fields = ("frame","landmark","x_m","y_m","uncertainty_radius_m",
                      "reported_confidence","observed_epoch_s")
            values = (reading.frame,reading.landmark,float(reading.x_m),
                      float(reading.y_m),float(reading.uncertainty_radius_m),
                      float(reading.reported_confidence),float(reading.observed_epoch_s))
            if prior is not None:
                if tuple(prior[key] for key in fields) != values:
                    raise SpatialMemoryError("conflicting replay of fixture sequence")
                return False
            newest = db.execute("""
                SELECT sequence,observed_epoch_s FROM f4b_mock_spatial_observations
                WHERE session_id=? ORDER BY sequence DESC LIMIT 1
            """, (self.session_id,)).fetchone()
            if newest is not None and (
                reading.sequence <= int(newest["sequence"])
                or float(reading.observed_epoch_s) < float(newest["observed_epoch_s"])
            ):
                raise SpatialMemoryError("out-of-order spatial fixture")
            db.execute("""
                INSERT INTO f4b_mock_spatial_observations(
                    session_id,sequence,frame,landmark,x_m,y_m,
                    uncertainty_radius_m,reported_confidence,
                    observed_epoch_s,source)
                VALUES (?,?,?,?,?,?,?,?,?,'mock_spatial_fixture')
            """, (self.session_id,reading.sequence,*values))
            self._prune(now_wall)
        return True

    def retract(self, record_id: int, *, reason: str) -> bool:
        if (type(record_id) is not int or record_id <= 0
                or type(reason) is not str or reason not in CORRECTION_REASONS):
            raise ValueError("invalid mock correction")
        with self._memory.conn:
            changed = self._memory.conn.execute("""
                UPDATE f4b_mock_spatial_observations
                SET active=0,correction_reason=?
                WHERE id=? AND active=1
            """, (reason,record_id))
            return changed.rowcount == 1

    def records(self, *, now_wall_epoch_s: float,
                frame: str, landmark: str, limit: int = 20) -> tuple[int, ...]:
        """Return opaque row IDs only, for explicit correction/inspection."""
        now = _check_wall(now_wall_epoch_s)
        if frame not in FRAMES or landmark not in LANDMARKS:
            raise ValueError("unrecognized mock frame/landmark")
        if type(limit) is not int or not 1 <= limit <= MAX_QUERY:
            raise ValueError("invalid record limit")
        rows=self._memory.conn.execute("""
            SELECT id FROM f4b_mock_spatial_observations
            WHERE frame=? AND landmark=? AND active=1
              AND source='mock_spatial_fixture'
              AND observed_epoch_s BETWEEN ? AND ?
            ORDER BY observed_epoch_s DESC,id DESC LIMIT ?
        """,(frame,landmark,now-RETAIN_SECONDS,now,limit)).fetchall()
        return tuple(int(row["id"]) for row in rows)

    def recall(self, *, frame: str, landmark: str,
               now_wall_epoch_s: float) -> SpatialRecall:
        """Conservatively summarize historical mock disks in ONE frame.

        If any disks are pairwise disjoint, confidence is low, or a combined
        radius would exceed our representable 2 m uncertainty, coordinates
        are omitted. We NEVER average away ambiguity or assert floor safety.
        """
        now = _check_wall(now_wall_epoch_s)
        if type(frame) is not str or frame not in FRAMES:
            raise ValueError("unknown fictional reference frame")
        if type(landmark) is not str or landmark not in LANDMARKS:
            raise ValueError("unknown anonymous landmark category")
        rows=self._memory.conn.execute("""
            SELECT frame,landmark,x_m,y_m,uncertainty_radius_m,
                   reported_confidence,observed_epoch_s,source
            FROM f4b_mock_spatial_observations
            WHERE frame=? AND landmark=? AND active=1
              AND observed_epoch_s BETWEEN ? AND ?
            ORDER BY observed_epoch_s DESC,id DESC LIMIT ?
        """,(frame,landmark,now-RETAIN_SECONDS,now,MAX_ROWS)).fetchall()
        def blocked(status: str) -> SpatialRecall:
            return SpatialRecall(frame,landmark,status,len(rows))
        if not rows:
            return blocked("no_historical_fixture")
        # Do not trust malformed persisted rows (e.g. after manual DB edits).
        try:
            for r in rows:
                if r["source"] != "mock_spatial_fixture" or (
                    r["frame"],r["landmark"]) != (frame,landmark):
                    return blocked("invalid_persisted_fixture")
                _number(r["x_m"],"persisted x",lo=-MAX_COORD_M,hi=MAX_COORD_M)
                _number(r["y_m"],"persisted y",lo=-MAX_COORD_M,hi=MAX_COORD_M)
                _number(r["uncertainty_radius_m"],"persisted radius",
                        lo=MIN_RADIUS_M,hi=MAX_RADIUS_M)
                _number(r["reported_confidence"],"persisted confidence",lo=0.,hi=1.)
        except (SpatialMemoryError,TypeError):
            return blocked("invalid_persisted_fixture")
        if any(float(r["reported_confidence"]) < MIN_REPORT_CONFIDENCE
               for r in rows):
            return blocked("insufficient_mock_confidence")
        for i,a in enumerate(rows):
            for b in rows[i+1:]:
                d=math.hypot(a["x_m"]-b["x_m"],a["y_m"]-b["y_m"])
                if d > a["uncertainty_radius_m"] + b["uncertainty_radius_m"] + 1e-10:
                    return blocked("conflicting_mock_landmarks")
        newest=rows[0]
        # Conservative display disk around latest fixture center: NO
        # precision gain from repetition. Not a calibrated confidence region.
        upper=max(
            math.hypot(newest["x_m"]-r["x_m"],newest["y_m"]-r["y_m"])
            + r["uncertainty_radius_m"] for r in rows)
        if upper > MAX_RADIUS_M:
            return blocked("uncertainty_too_large")
        return SpatialRecall(
            frame,landmark,"bounded_historical_mock_only",len(rows),
            float(newest["x_m"]),float(newest["y_m"]),float(upper),
            min(float(r["reported_confidence"]) for r in rows),
        )
