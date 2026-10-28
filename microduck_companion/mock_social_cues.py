"""F4-C: bounded, mostly silent social *proposals* from the EXISTING brain.

No robotd, mediad, speaker, microphone, cameras, physical gaze, network,
Qwen, or identity matching. A plan is a mock-only description: even when
an operator claims opt-in, it authorizes NO hardware output.

This layer wraps AutonomyBrain.propose_balanced_passive, which itself checks
F1-B mock provenance and F2-A/F2-B freshness. F4-C never treats old SQLite
categories, a predicted pet, a voice cue, or an LLM property as a person.
Only anonymous category, cue type and wall timestamp are persisted.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import sqlite3

from .autonomy import AutonomyBrain
from .episodic_memory import ExperienceMemory
from .passive_memory import PassiveObservationJournal, _check_wall
from .passive_sources import PassiveRead
from .passive_observations import PASSIVE_KINDS
from .perception import PerceptionSnapshot
from .social_context import MockSocialContext  # stable historical re-export

ALLOWED_OBJECT_CUES = frozenset({"cat", "dog", "ball", "toy"})
ALLOWED_SOUND_CUES = frozenset({"bark", "meow"})
PLAN_KINDS = frozenset({"silence", "rest", "glance", "chirp", "play_cue"})
PLAN_DURATIONS_MS = {"silence": 0, "rest": 0, "glance": 250,
                     "chirp": 180, "play_cue": 300}
MIN_GLOBAL_GAP_S = 10.
MIN_SAME_CUE_GAP_S = 60.
SOUND_WINDOW_S = 600.
MAX_SOUNDS_PER_WINDOW = 2
RETENTION_S = 7 * 24 * 3600
MAX_LOG_ROWS = 128
MIN_PLAY_MOTIVATION = .70


@dataclass(frozen=True)
class MockSocialPlan:
    """A fictional interaction description, NEVER an executable command."""

    kind: str
    reason: str
    category: str | None = None
    duration_ms: int = 0
    source: str = "mock_social_proposal_only"
    executed: bool = False
    real_consent_verified: bool = False
    real_sensor_authenticated: bool = False
    identity_verified: bool = False
    gaze_motor_commands_issued: int = 0
    speaker_commands_issued: int = 0
    audio_bytes_stored: int = 0
    motor_commands_issued: int = 0
    physical_execution_authorized: bool = False

    def __post_init__(self) -> None:
        if (self.kind not in PLAN_KINDS or self.duration_ms !=
                PLAN_DURATIONS_MS[self.kind]):
            raise ValueError("unsupported mock social plan")
        if type(self.reason) is not str or not self.reason.isascii() or len(self.reason) > 90:
            raise ValueError("reason must be a small generic ASCII code")
        if self.kind in {"silence", "rest"} and self.category is not None:
            raise ValueError("silence/rest cannot identify a target")
        if self.kind in {"glance", "play_cue"} and self.category not in ALLOWED_OBJECT_CUES:
            raise ValueError("gaze/play cues only support generic mock categories")
        if self.kind == "chirp" and self.category not in ALLOWED_SOUND_CUES:
            raise ValueError("brief mock audio requires generic non-speech cue")
        if (self.source != "mock_social_proposal_only" or self.executed
                or self.real_consent_verified or self.real_sensor_authenticated
                or self.identity_verified or self.gaze_motor_commands_issued
                or self.speaker_commands_issued or self.audio_bytes_stored
                or self.motor_commands_issued or self.physical_execution_authorized):
            raise ValueError("social proposals cannot authorize output")


class MockSocialComposer:
    """One cautious social presentation layer around an existing brain.

    SQLite is shared with F1-C, F2-B and F4-A/B. It stores ONLY the generic
    *proposals* for cross-process cooldowns. It cannot record execution or
    results. Revocation blocks any future candidate even if old cues remain.
    """

    def __init__(self, brain: AutonomyBrain,
                 journal: PassiveObservationJournal) -> None:
        if not isinstance(brain, AutonomyBrain):
            raise TypeError("the existing autonomy brain is required")
        if not isinstance(journal, PassiveObservationJournal):
            raise TypeError("F1-C journal required")
        if brain.memory is not journal._memory:
            raise ValueError("social composer and journal must share one SQLite")
        self._brain, self._journal = brain, journal
        self._memory: ExperienceMemory = brain.memory
        with self._memory.conn:
            self._memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS f4c_mock_social_proposals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kind TEXT NOT NULL CHECK(kind IN
                        ('glance','chirp','play_cue')),
                    category TEXT NOT NULL CHECK(category IN
                        ('cat','dog','ball','toy','bark','meow')),
                    recorded_epoch_s REAL NOT NULL CHECK(recorded_epoch_s>=0),
                    source TEXT NOT NULL CHECK(
                        source='mock_social_proposal_only')
                )
            """)
            self._memory.conn.execute("""
                CREATE INDEX IF NOT EXISTS f4c_mock_social_when
                ON f4c_mock_social_proposals(recorded_epoch_s DESC,id DESC)
            """)

    @staticmethod
    def _silent(reason: str) -> MockSocialPlan:
        return MockSocialPlan("silence", reason)

    @staticmethod
    def _valid_reading(reading: PassiveRead) -> bool:
        """A receipt is a mock fixture, not an authenticated microphone."""
        if (reading.status != "ok" or reading.channel != "mock_fixture_unix"
                or type(reading.sequence) is not int
                or not 0 <= reading.sequence < 2**63
                or not isinstance(reading.snapshot, PerceptionSnapshot)
                or reading.snapshot.environment != "mock"):
            return False
        return all(
            event.kind in PASSIVE_KINDS and event.source == "mock"
            for event in reading.snapshot.events)

    def _persist_if_allowed(self, proposal: MockSocialPlan, now: float) -> str | None:
        """Single SQLite write decision: rate gates persist across processes.

        Return one generic refusal code, or None if the proposal was logged.
        SQLite failure is handled by caller as silence. No action is emitted.
        """
        with self._memory.conn:
            db = self._memory.conn
            # The external computer uses one process in CI; BEGIN IMMEDIATE
            # serializes concurrent local proposal processes for cooldowns.
            db.execute("BEGIN IMMEDIATE")
            last = db.execute("""
                SELECT MAX(recorded_epoch_s) AS ts FROM f4c_mock_social_proposals
            """).fetchone()["ts"]
            if last is not None:
                if now < float(last):
                    return "wall_clock_regression"
                if now - float(last) < MIN_GLOBAL_GAP_S:
                    return "social_global_cooldown"
            same = db.execute("""
                SELECT MAX(recorded_epoch_s) AS ts FROM f4c_mock_social_proposals
                WHERE kind=? AND category=?
            """, (proposal.kind, proposal.category)).fetchone()["ts"]
            if same is not None and now - float(same) < MIN_SAME_CUE_GAP_S:
                return "social_same_cue_cooldown"
            if proposal.kind == "chirp":
                num = db.execute("""
                    SELECT COUNT(*) FROM f4c_mock_social_proposals
                    WHERE kind='chirp' AND recorded_epoch_s > ?
                """, (now - SOUND_WINDOW_S,)).fetchone()[0]
                if num >= MAX_SOUNDS_PER_WINDOW:
                    return "social_sound_budget"
            db.execute("""
                INSERT INTO f4c_mock_social_proposals(
                    kind,category,recorded_epoch_s,source)
                VALUES (?,?,?,'mock_social_proposal_only')
            """, (proposal.kind, proposal.category, now))
            db.execute("""
                DELETE FROM f4c_mock_social_proposals
                WHERE recorded_epoch_s < ?
            """, (now - RETENTION_S,))
            db.execute("""
                DELETE FROM f4c_mock_social_proposals WHERE id NOT IN (
                    SELECT id FROM f4c_mock_social_proposals
                    ORDER BY recorded_epoch_s DESC,id DESC LIMIT ?
                )
            """, (MAX_LOG_ROWS,))
            return None

    def propose(self, reading: PassiveRead, *,
                context: MockSocialContext,
                now_monotonic_s: float, now_wall_epoch_s: float) -> MockSocialPlan:
        """Only hypothetical social cues. Missing consent => silent by default.

        F2-B remains the decision engine. Its energy accounting is still
        simulated motivation, not battery consumption or executed actions.
        """
        if not isinstance(reading, PassiveRead):
            raise TypeError("F1-B PassiveRead required")
        if not isinstance(context, MockSocialContext):
            raise TypeError("explicit mock social context required")
        if (type(now_monotonic_s) not in (int,float)
                or not math.isfinite(now_monotonic_s) or now_monotonic_s < 0):
            raise ValueError("invalid monotonic decision clock")
        now = _check_wall(now_wall_epoch_s)
        if not (context.operator_opt_in and context.supervised
                and context.privacy_reviewed):
            return self._silent("no_operator_opt_in_or_supervision")
        if not self._valid_reading(reading):
            return self._silent("invalid_mock_source")
        if not reading.snapshot.events:
            return self._silent("no_current_social_fixture")
        # No identity, speech, keyword, unrecognized animal/unknown labels
        # or ambiguous combinations get even a sound/turn proposal.
        categories: set[tuple[str, str]] = set()
        for event in reading.snapshot.events:
            allowed = (ALLOWED_OBJECT_CUES if event.kind == "object_label"
                       else ALLOWED_SOUND_CUES)
            if type(event.value) is not str or event.value not in allowed:
                return self._silent("sensitive_or_ambiguous_category")
            categories.add((event.kind,event.value))
        if len(categories) != 1:
            return self._silent("multiple_social_categories")
        try:
            base = self._brain.propose_balanced_passive(
                reading, journal=self._journal,
                now_monotonic_s=now_monotonic_s,
                now_wall_epoch_s=now,
            )
        except (sqlite3.Error,ValueError):
            return self._silent("brain_or_history_unavailable")
        if base.intention == "rest":
            return MockSocialPlan("rest", "simulated_energy_only")
        if base.intention == "idle":
            return self._silent("brain_chose_idle")
        if context.quiet_mode:
            return self._silent("quiet_mode")
        if (base.intention in {"observe","inspect"}
                and base.target_kind == "object_label"
                and base.target_category in ALLOWED_OBJECT_CUES):
            if (base.target_category in {"ball","toy"}
                    and context.play_invitation_opt_in
                    and self._brain.motives.play >= MIN_PLAY_MOTIVATION):
                proposal=MockSocialPlan(
                    "play_cue", "mock_only_play_invitation",
                    base.target_category, PLAN_DURATIONS_MS["play_cue"])
            else:
                proposal=MockSocialPlan(
                    "glance", "mock_only_brief_visual_attention",
                    base.target_category,PLAN_DURATIONS_MS["glance"])
        elif (base.intention == "listen" and
              base.target_kind == "sound_label"
              and base.target_category in ALLOWED_SOUND_CUES):
            if not context.brief_audio_opt_in:
                return self._silent("brief_audio_not_opted_in")
            proposal=MockSocialPlan(
                "chirp", "mock_only_short_nonspeech_chirp",
                base.target_category,PLAN_DURATIONS_MS["chirp"])
        else:
            return self._silent("no_safe_social_candidate")
        try:
            blocked = self._persist_if_allowed(proposal,now)
        except sqlite3.Error:
            return self._silent("social_history_unavailable")
        return self._silent(blocked) if blocked else proposal

    def count_proposals(self) -> int:
        """Diagnostic only: counts plans, not actions or sound emissions."""
        return int(self._memory.conn.execute(
            "SELECT COUNT(*) FROM f4c_mock_social_proposals").fetchone()[0])
