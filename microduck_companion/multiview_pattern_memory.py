"""M1-B: configurable, bounded multi-exemplar memory on FICTIONAL fixtures.

A 'group' means multiple fingerprints linked by synthetic fixture supervision,
NOT verified same physical object, sound source or individual. Feature
extraction reuses the M1-A 64/16-byte hand-crafted signatures. No trained
embedding, real sensor, speech/person recognition, PC I/O or motor control.
An exhaustive comparison budget is enforced: if it cannot inspect *all*
eligible exemplars, the module refuses to claim novelty or familiarity.

Live signature-byte limits are NOT SQLite database-file size limits. All
tables share the existing ExperienceMemory SQLite connection.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .compact_multimodal_memory import (
    AMBIGUITY_GAP, MATCH_AUDIO, MATCH_IMAGE, OBJECT_CATEGORIES,
    SOUND_CATEGORIES, _interest, _time, audio_fingerprint,
    image_fingerprint,
)
from .episodic_memory import ExperienceMemory

Modality = Literal["image", "audio"]


@dataclass(frozen=True)
class MultiviewLimits:
    """HOST study defaults, not measured or approved RK3566 resources."""

    max_groups: int = 1024
    max_signatures: int = 4096
    max_signatures_per_group: int = 6
    max_fingerprint_bytes: int = 256 * 1024
    max_comparisons: int = 4096
    retention_s: int = 180 * 24 * 3600

    def __post_init__(self) -> None:
        for name, upper in (
            ("max_groups", 16384),
            ("max_signatures", 16384),
            ("max_signatures_per_group", 64),
            ("max_fingerprint_bytes", 16 * 1024 * 1024),
            ("max_comparisons", 16384),
            ("retention_s", 10 * 365 * 24 * 3600),
        ):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= upper:
                raise ValueError(f"invalid M1-B study bound: {name}")
        if (self.max_groups > self.max_signatures
                or self.max_signatures_per_group > self.max_signatures
                or self.max_fingerprint_bytes < 64):
            raise ValueError("inconsistent M1-B limits")


@dataclass(frozen=True)
class MultiviewEncounter:
    status: str
    modality: str
    category: str
    group_id: int | None
    group_sightings: int
    exemplar_count: int
    similarity: float | None
    comparisons: int
    pc_review_suggested: bool
    category_verified: bool = False
    same_physical_source_verified: bool = False
    robot_hardware_validated: bool = False
    real_sensor_reads: int = 0
    media_files_stored: int = 0
    network_requests: int = 0
    motor_commands_issued: int = 0

    def __post_init__(self) -> None:
        if (self.category_verified or self.same_physical_source_verified
                or self.robot_hardware_validated or self.real_sensor_reads
                or self.media_files_stored or self.network_requests
                or self.motor_commands_issued):
            raise ValueError("M1-B never certifies or actuates physical sources")


class MultiviewPatternMemory:
    """One-process evaluation; one SQLite connection is the only persistence.

    Explicit group hints are accepted ONLY with synthetic_same_source_claim
    from a fixture. This deliberately does NOT certify physical identity.
    """

    def __init__(self, memory: ExperienceMemory,
                 limits: MultiviewLimits | None = None) -> None:
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("existing ExperienceMemory required")
        if limits is not None and not isinstance(limits, MultiviewLimits):
            raise TypeError("M1-B limits required")
        self.memory = memory
        self.limits = limits if limits is not None else MultiviewLimits()
        with memory.conn:
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS m1b_groups(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    modality TEXT NOT NULL CHECK(modality IN ('image','audio')),
                    category TEXT NOT NULL,
                    source TEXT NOT NULL CHECK(source='synthetic_fixture_claim'),
                    sightings INTEGER NOT NULL CHECK(sightings BETWEEN 1 AND 2147483647),
                    first_seen_epoch_s REAL NOT NULL,
                    last_seen_epoch_s REAL NOT NULL
                )
            """)
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS m1b_signatures(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL REFERENCES m1b_groups(id),
                    modality TEXT NOT NULL CHECK(modality IN ('image','audio')),
                    feature_version INTEGER NOT NULL CHECK(feature_version=1),
                    fingerprint BLOB NOT NULL CHECK(
                        (modality='image' AND length(fingerprint)=64) OR
                        (modality='audio' AND length(fingerprint)=16)
                    ),
                    sightings INTEGER NOT NULL CHECK(sightings BETWEEN 1 AND 2147483647),
                    last_seen_epoch_s REAL NOT NULL,
                    UNIQUE(modality,feature_version,fingerprint)
                )
            """)
            memory.conn.execute("""
                CREATE INDEX IF NOT EXISTS m1b_signature_modality
                ON m1b_signatures(modality,id)
            """)
            memory.conn.execute("""
                CREATE INDEX IF NOT EXISTS m1b_signature_group
                ON m1b_signatures(group_id)
            """)
            memory.conn.execute("""
                CREATE INDEX IF NOT EXISTS m1b_group_recent
                ON m1b_groups(last_seen_epoch_s,id)
            """)

    def stats(self) -> dict[str, int]:
        c = self.memory.conn
        return {
            "groups": c.execute(
                "SELECT COUNT(*) FROM m1b_groups"
            ).fetchone()[0],
            "signatures": c.execute(
                "SELECT COUNT(*) FROM m1b_signatures"
            ).fetchone()[0],
            "fingerprint_bytes": c.execute(
                "SELECT COALESCE(SUM(length(fingerprint)),0) "
                "FROM m1b_signatures"
            ).fetchone()[0],
            "sqlite_allocated_pages_bytes": (
                c.execute("PRAGMA page_count").fetchone()[0]
                * c.execute("PRAGMA page_size").fetchone()[0]
            ),
        }

    def _delete_group(self, group_id: int) -> None:
        self.memory.conn.execute(
            "DELETE FROM m1b_signatures WHERE group_id=?", (group_id,),
        )
        self.memory.conn.execute(
            "DELETE FROM m1b_groups WHERE id=?", (group_id,),
        )

    def _drop_exemplar(self, exemplar_id: int, *,
                       preserve_group: int | None) -> None:
        c = self.memory.conn
        gid = c.execute(
            "SELECT group_id FROM m1b_signatures WHERE id=?", (exemplar_id,)
        ).fetchone()[0]
        c.execute("DELETE FROM m1b_signatures WHERE id=?", (exemplar_id,))
        if gid != preserve_group:
            still = c.execute(
                "SELECT 1 FROM m1b_signatures WHERE group_id=? LIMIT 1",
                (gid,),
            ).fetchone()
            if still is None:
                c.execute("DELETE FROM m1b_groups WHERE id=?", (gid,))

    def _prune(self, now: float) -> None:
        c = self.memory.conn
        ids = c.execute(
            "SELECT id FROM m1b_groups WHERE last_seen_epoch_s < ?",
            (now - self.limits.retention_s,),
        ).fetchall()
        for item in ids:
            self._delete_group(item["id"])

    def prune(self, *, now_wall_epoch_s: float) -> None:
        with self.memory.conn:
            self._prune(_time(now_wall_epoch_s))

    def _make_room(self, feature_size: int, *, protected_group: int | None,
                   creating_group: bool) -> None:
        """Evict least recently seen exemplars across BOTH modalities.

        When a group disappears because its final signature is dropped,
        delete its metadata as well. A linked target group is preserved even
        when its only exemplar is replaced. All actions are transactional.
        """
        c = self.memory.conn
        if creating_group:
            while c.execute("SELECT COUNT(*) FROM m1b_groups").fetchone()[0] >= (
                self.limits.max_groups
            ):
                oldest = c.execute("""
                    SELECT id FROM m1b_groups
                    ORDER BY last_seen_epoch_s,id LIMIT 1
                """).fetchone()
                if oldest is None:
                    break
                self._delete_group(oldest["id"])
        while True:
            n, occupied = c.execute("""
                SELECT COUNT(*),COALESCE(SUM(length(fingerprint)),0)
                FROM m1b_signatures
            """).fetchone()
            if (n < self.limits.max_signatures
                    and occupied + feature_size <= self.limits.max_fingerprint_bytes):
                return
            victim = c.execute("""
                SELECT id FROM m1b_signatures
                ORDER BY last_seen_epoch_s ASC,sightings ASC,id ASC LIMIT 1
            """).fetchone()
            if victim is None:
                raise ValueError("M1-B capacity cannot fit a single feature")
            self._drop_exemplar(victim["id"], preserve_group=protected_group)

    def observe_image(
        self, gray8: bytes, *, now_wall_epoch_s: float,
        category: str = "unknown", group_hint: int | None = None,
        synthetic_same_source_claim: bool = False,
        pc_opt_in: bool = False, interest: float = 0.,
    ) -> MultiviewEncounter:
        if type(category) is not str or category not in OBJECT_CATEGORIES:
            raise ValueError("invalid generic visual category")
        if category == "person":
            raise ValueError("no person appearance fingerprinting")
        return self._observe(
            "image",image_fingerprint(gray8),category=category,
            now_wall_epoch_s=now_wall_epoch_s,group_hint=group_hint,
            synthetic_same_source_claim=synthetic_same_source_claim,
            pc_opt_in=pc_opt_in,interest=interest,
        )

    def observe_audio(
        self, pcm16le: bytes, *, now_wall_epoch_s: float,
        category: str = "unknown", group_hint: int | None = None,
        synthetic_same_source_claim: bool = False,
        pc_opt_in: bool = False, interest: float = 0.,
    ) -> MultiviewEncounter:
        if type(category) is not str or category not in SOUND_CATEGORIES:
            raise ValueError("invalid generic sound category")
        if category == "speech":
            raise ValueError("no voice or speech fingerprinting")
        return self._observe(
            "audio",audio_fingerprint(pcm16le),category=category,
            now_wall_epoch_s=now_wall_epoch_s,group_hint=group_hint,
            synthetic_same_source_claim=synthetic_same_source_claim,
            pc_opt_in=pc_opt_in,interest=interest,
        )

    def _observe(self, modality: Modality, signature: bytes, *,
                 category: str, now_wall_epoch_s: float,
                 group_hint: int | None, synthetic_same_source_claim: bool,
                 pc_opt_in: bool, interest: float) -> MultiviewEncounter:
        now = _time(now_wall_epoch_s)
        curiosity = _interest(interest)
        if type(pc_opt_in) is not bool or type(synthetic_same_source_claim) is not bool:
            raise ValueError("invalid consent or fixture association flag")
        if group_hint is not None and (
                type(group_hint) is not int or group_hint <= 0):
            raise ValueError("group hint must be a positive integer")
        if (group_hint is None) != (not synthetic_same_source_claim):
            raise ValueError("a group hint requires explicit synthetic supervision")
        c = self.memory.conn
        threshold = MATCH_IMAGE if modality == "image" else MATCH_AUDIO

        def response(status: str, gid: int | None = None,
                     similarity: float | None = None,
                     comparisons: int = 0) -> MultiviewEncounter:
            group = None if gid is None else c.execute(
                "SELECT category,sightings FROM m1b_groups WHERE id=?",
                (gid,),
            ).fetchone()
            n = 0 if gid is None else c.execute(
                "SELECT COUNT(*) FROM m1b_signatures WHERE group_id=?",
                (gid,),
            ).fetchone()[0]
            needs_pc = (status in {
                "new_group_unverified", "ambiguous_unverified",
            } and category in {"unknown","object","ambient"}
                        and pc_opt_in and curiosity >= .7)
            return MultiviewEncounter(
                status,modality,
                category if group is None else group["category"],
                gid,0 if group is None else group["sightings"],
                n,similarity,comparisons,needs_pc,
            )

        # We do not assert concurrency safety of the larger brain; the local
        # pattern decision/eviction is serialized across SQLite processes.
        with c:
            c.execute("BEGIN IMMEDIATE")
            newest = c.execute(
                "SELECT MAX(last_seen_epoch_s) FROM m1b_groups"
            ).fetchone()[0]
            if newest is not None and now + 60 < newest:
                raise ValueError("fixture wall clock rollback")
            self._prune(now)
            target = None
            if group_hint is not None:
                target = c.execute(
                    "SELECT * FROM m1b_groups WHERE id=? AND modality=?",
                    (group_hint,modality),
                ).fetchone()
                if target is None:
                    raise ValueError("unknown or expired fixture group")
                if category != "unknown" and target["category"] not in (
                    "unknown",category,
                ):
                    return response("ambiguous_unverified")

            # Complete, rather than approximate, inspection is REQUIRED for
            # familiarity/novelty claims. Never silently ignore stale rows.
            rows = c.execute("""
                SELECT s.id AS exemplar_id,s.group_id,s.fingerprint,
                       g.category AS group_category
                FROM m1b_signatures s
                JOIN m1b_groups g ON g.id=s.group_id
                WHERE s.modality=?
                ORDER BY s.id
                LIMIT ?
            """,(modality,self.limits.max_comparisons+1)).fetchall()
            if len(rows)>self.limits.max_comparisons:
                return response("search_budget_exhausted",
                                comparisons=self.limits.max_comparisons)
            scores = sorted(
                ((1. - sum(abs(a-b) for a,b in zip(signature,row["fingerprint"]))
                  / (255. * len(signature)),row)
                 for row in rows),
                key=lambda item:(-item[0],item[1]["exemplar_id"]),
            )
            comparisons=len(rows)
            best=scores[0] if scores else None
            if best is not None and best[0]>=threshold:
                best_score,best_row=best
                uncertain=any(
                    (score >= threshold
                     and best_score-score < AMBIGUITY_GAP
                     and other["group_id"] != best_row["group_id"])
                    for score,other in scores[1:]
                )
                if (uncertain or
                    (category != "unknown"
                     and best_row["group_category"] not in ("unknown",category))
                    or (group_hint is not None and
                        best_row["group_id"] != group_hint)):
                    return response("ambiguous_unverified",
                                    similarity=best_score,
                                    comparisons=comparisons)
                gid=best_row["group_id"]
                eid=best_row["exemplar_id"]
                c.execute("""
                    UPDATE m1b_signatures SET
                        sightings=MIN(2147483647,sightings+1),
                        last_seen_epoch_s=MAX(last_seen_epoch_s,?)
                    WHERE id=?
                """,(now,eid))
                c.execute("""
                    UPDATE m1b_groups SET
                        sightings=MIN(2147483647,sightings+1),
                        last_seen_epoch_s=MAX(last_seen_epoch_s,?),
                        category=CASE WHEN category='unknown'
                                      AND ?!='unknown'
                                      THEN ? ELSE category END
                    WHERE id=?
                """,(now,category,category,gid))
                return response("similar_group_unverified",
                                gid,best_score,comparisons)

            if group_hint is not None:
                gid=group_hint
                # Keep at most a few representative angles/sound variants.
                members=c.execute("""
                    SELECT id FROM m1b_signatures WHERE group_id=?
                    ORDER BY sightings ASC,last_seen_epoch_s ASC,id ASC
                """,(gid,)).fetchall()
                if len(members)>=self.limits.max_signatures_per_group:
                    self._drop_exemplar(
                        members[0]["id"],preserve_group=gid,
                    )
            else:
                gid=None
            self._make_room(
                len(signature),protected_group=gid,
                creating_group=(gid is None),
            )
            if gid is None:
                inserted=c.execute("""
                    INSERT INTO m1b_groups(
                        modality,category,source,sightings,
                        first_seen_epoch_s,last_seen_epoch_s)
                    VALUES (?,?,'synthetic_fixture_claim',1,?,?)
                """,(modality,category,now,now))
                gid=inserted.lastrowid
            else:
                c.execute("""
                    UPDATE m1b_groups SET
                        sightings=MIN(2147483647,sightings+1),
                        last_seen_epoch_s=MAX(last_seen_epoch_s,?),
                        category=CASE WHEN category='unknown'
                                    AND ?!='unknown' THEN ? ELSE category END
                    WHERE id=?
                """,(now,category,category,gid))
            c.execute("""
                INSERT INTO m1b_signatures(
                    group_id,modality,feature_version,fingerprint,
                    sightings,last_seen_epoch_s)
                VALUES (?,?,1,?,1,?)
            """,(gid,modality,signature,now))
            return response(
                "new_group_unverified" if group_hint is None
                else "linked_exemplar_fixture_claim",
                gid,comparisons=comparisons,
            )
