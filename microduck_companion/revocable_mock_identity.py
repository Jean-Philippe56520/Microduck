"""F4-D: private, revocable *fixture* associations by voluntary token.

No face, voice, gait, tracking, location, camera, BLE/NFC, biometrics or real
identity verification. This module never learns or detects an individual.
An operator-supplied 32-byte token is HMAC-tagged with an externally provided
32-byte key, and ONLY the digest, a random opaque association ref and a
generic class enter the existing SQLite ExperienceMemory.

The key and token are never persisted or logged here. The test-only consent
flags DO NOT authenticate adults/guardians or prove an individual's assent.
There is no social, media, network or motor adapter. Real-life pairing needs
separate audited hardware, private key protection and consent workflows.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import hmac
import math
import sqlite3
import uuid

from .episodic_memory import ExperienceMemory
from .passive_memory import _check_wall

KINDS = frozenset({"pet_cat", "pet_dog", "child", "adult"})
SOURCE = "fictional_voluntary_token_only"
MAX_ASSOCIATIONS = 24
MAX_LIFETIME_S = 30 * 24 * 3600
DEFAULT_LIFETIME_S = 7 * 24 * 3600
MIN_LIFETIME_S = 60
MAX_PRESENTATION_AGE_S = 2.
MAX_ASSOCIATION_ID_LEN = 32
MAX_PRESENTATION_SEQUENCE = 2**63 - 1


def _bytes32(value: object, name: str) -> bytes:
    # Exact bytes length prevents arbitrary text/name/path/device IDs from
    # becoming the data model. No code can verify actual token entropy.
    if type(value) is not bytes or len(value) != 32 or len(set(value)) < 8:
        raise ValueError(f"{name} must be a nontrivial 32-byte fixture value")
    return value


def _sequence(seq: object) -> int:
    if type(seq) is not int or not 1 <= seq <= MAX_PRESENTATION_SEQUENCE:
        raise ValueError("invalid strictly positive presentation sequence")
    return seq


def _ref(value: object) -> str:
    if (type(value) is not str or len(value) != MAX_ASSOCIATION_ID_LEN
            or any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError("association ref must be 32 lowercase hex characters")
    return value


@dataclass(frozen=True)
class MockOptInContext:
    """Assertions in a fictional scenario; NOT a real consent verifier."""

    operator_opt_in: bool = False
    supervised: bool = False
    privacy_reviewed: bool = False
    token_presented_voluntarily: bool = False
    guardian_approved: bool = False
    child_assent_declared: bool = False

    def __post_init__(self) -> None:
        if any(type(getattr(self, f)) is not bool for f in (
            "operator_opt_in", "supervised", "privacy_reviewed",
            "token_presented_voluntarily", "guardian_approved",
            "child_assent_declared",
        )):
            raise ValueError("mock consent and guardian claims must be bool")

    def permitted(self, *, kind: str | None, needs_presentation: bool) -> bool:
        if not (self.operator_opt_in and self.supervised
                and self.privacy_reviewed):
            return False
        if needs_presentation and not self.token_presented_voluntarily:
            return False
        if kind == "child" and not (
            self.guardian_approved and self.child_assent_declared
        ):
            return False
        return True


@dataclass(frozen=True)
class MockTokenPresentation:
    """Synthetic token gesture, not authenticated NFC/BLE/microphone input."""

    token: bytes = field(repr=False)
    sequence: int
    observed_epoch_s: float
    source: str = SOURCE

    def __post_init__(self) -> None:
        _bytes32(self.token, "test token")
        _sequence(self.sequence)
        _check_wall(self.observed_epoch_s)
        if self.source != SOURCE:
            raise ValueError("no real voluntary-presentation adapter in F4-D")


@dataclass(frozen=True)
class MockAssociation:
    """Opaque, revocable *test* handle; NOT a verified person's identity."""

    association_ref: str
    kind: str
    expires_epoch_s: float
    source: str = SOURCE
    real_identity_verified: bool = False
    real_guardian_verified: bool = False
    camera_or_voice_used: bool = False
    physical_actions_authorized: bool = False
    motor_commands_issued: int = 0
    speaker_commands_issued: int = 0

    def __post_init__(self) -> None:
        _ref(self.association_ref)
        if self.kind not in KINDS or type(self.kind) is not str:
            raise ValueError("only a controlled generic mock class")
        _check_wall(self.expires_epoch_s)
        if (self.source != SOURCE or self.real_identity_verified
                or self.real_guardian_verified or self.camera_or_voice_used
                or self.physical_actions_authorized
                or self.motor_commands_issued or self.speaker_commands_issued):
            raise ValueError("fixture association cannot be physical identity")


@dataclass(frozen=True)
class MockResolution:
    """One intentionally narrow result of an explicit mock token gesture."""

    status: str
    association_ref: str | None = None
    kind: str | None = None
    source: str = SOURCE
    voluntary_fixture_only: bool = True
    real_identity_verified: bool = False
    real_guardian_verified: bool = False
    physical_actions_authorized: bool = False
    motor_commands_issued: int = 0
    speaker_commands_issued: int = 0

    def __post_init__(self) -> None:
        if self.status not in {
            "unknown", "no_operator_permission", "untrusted_presentation",
            "stale_or_future", "replayed_presentation",
            "guardian_or_assent_missing", "mock_token_association_only",
            "history_unavailable",
        }:
            raise ValueError("invalid association resolution")
        if self.status == "mock_token_association_only":
            if self.association_ref is None or self.kind not in KINDS:
                raise ValueError("matched fixture requires an opaque reference")
            _ref(self.association_ref)
        elif self.association_ref is not None or self.kind is not None:
            raise ValueError("unmatched fixture cannot disclose identity")
        if (self.source != SOURCE or not self.voluntary_fixture_only
                or self.real_identity_verified or self.real_guardian_verified
                or self.physical_actions_authorized
                or self.motor_commands_issued or self.speaker_commands_issued):
            raise ValueError("fixture cannot authorize social or motor output")


class RevocableMockAssociations:
    """Small registry in existing SQLite, deliberately not connected to AI.

    Source is an explicit, test-only token gesture. Only mock context flags
    permit a pseudonymous binding, and they are not real authentication.
    A matching token cannot grant any physical movement, speech, social
    output, or training label. No names, raw tokens or secrets are persisted.
    """

    def __init__(self, memory: ExperienceMemory, *, key: bytes) -> None:
        if not isinstance(memory, ExperienceMemory):
            raise TypeError("requires existing ExperienceMemory")
        self._memory = memory
        self._key = _bytes32(key, "local test HMAC key")
        with memory.conn:
            memory.conn.execute("""
                CREATE TABLE IF NOT EXISTS f4d_mock_optin_associations (
                    association_ref TEXT PRIMARY KEY,
                    token_tag TEXT NOT NULL UNIQUE CHECK(length(token_tag)=64),
                    kind TEXT NOT NULL CHECK(
                        kind IN ('pet_cat','pet_dog','child','adult')),
                    enrolled_epoch_s REAL NOT NULL CHECK(enrolled_epoch_s>=0),
                    expires_epoch_s REAL NOT NULL CHECK(expires_epoch_s>0),
                    last_sequence INTEGER NOT NULL DEFAULT 0
                        CHECK(last_sequence>=0),
                    last_presented_epoch_s REAL,
                    source TEXT NOT NULL CHECK(
                        source='fictional_voluntary_token_only')
                )
            """)
            memory.conn.execute("""
                CREATE INDEX IF NOT EXISTS f4d_mock_optin_expiry
                ON f4d_mock_optin_associations(expires_epoch_s)
            """)

    def _tag(self, token: bytes) -> str:
        token = _bytes32(token, "test token")
        return hmac.new(
            self._key, b"microduck-f4d-fixture-v1\x00" + token,
            hashlib.sha256,
        ).hexdigest()

    def _prune(self, now: float) -> int:
        changed = self._memory.conn.execute("""
            DELETE FROM f4d_mock_optin_associations
            WHERE expires_epoch_s <= ?
        """, (now,))
        return changed.rowcount

    def prune(self, *, now_wall_epoch_s: float) -> int:
        with self._memory.conn:
            return self._prune(_check_wall(now_wall_epoch_s))

    def count(self, *, now_wall_epoch_s: float) -> int:
        """Counts mock bindings, not identified living beings."""
        now = _check_wall(now_wall_epoch_s)
        row = self._memory.conn.execute("""
            SELECT COUNT(*) AS n FROM f4d_mock_optin_associations
            WHERE expires_epoch_s > ?
        """, (now,)).fetchone()
        return int(row["n"])

    def enroll(self, *, token: bytes, kind: str, context: MockOptInContext,
               now_wall_epoch_s: float,
               lifetime_s: float = DEFAULT_LIFETIME_S) -> MockAssociation | None:
        """Register a synthetic presentation, or refuse with no entry.

        Caller must supply generated bytes from *outside* this package; do
        not use a real person's name/voice/photo/biometric as a token.
        A distinct token is needed to re-enroll after explicit revocation.
        """
        tok = _bytes32(token, "test token")
        if type(kind) is not str or kind not in KINDS:
            raise ValueError("only bounded generic mock subject classes")
        if not isinstance(context, MockOptInContext):
            raise TypeError("mock operator context required")
        now = _check_wall(now_wall_epoch_s)
        if (type(lifetime_s) not in (int,float)
                or not math.isfinite(lifetime_s)
                or not MIN_LIFETIME_S <= lifetime_s <= MAX_LIFETIME_S):
            raise ValueError("invalid mock lifetime")
        if not context.permitted(kind=kind, needs_presentation=True):
            return None
        expiry = now + float(lifetime_s)
        digest = self._tag(tok)
        with self._memory.conn:
            self._memory.conn.execute("BEGIN IMMEDIATE")
            self._prune(now)
            count = self._memory.conn.execute("""
                SELECT COUNT(*) FROM f4d_mock_optin_associations
            """).fetchone()[0]
            if count >= MAX_ASSOCIATIONS:
                return None
            # A collision or repeat cannot silently rebind a token, even
            # if the user presents it for a different generic category.
            existing = self._memory.conn.execute("""
                SELECT association_ref FROM f4d_mock_optin_associations
                WHERE token_tag=?
            """, (digest,)).fetchone()
            if existing is not None:
                return None
            identifier = uuid.uuid4().hex
            self._memory.conn.execute("""
                INSERT INTO f4d_mock_optin_associations(
                    association_ref,token_tag,kind,enrolled_epoch_s,
                    expires_epoch_s,source
                ) VALUES (?,?,?,?,?,?)
            """, (identifier,digest,kind,now,expiry,SOURCE))
        return MockAssociation(identifier,kind,expiry)

    def present(self, presentation: MockTokenPresentation, *,
                context: MockOptInContext, now_wall_epoch_s: float
                ) -> MockResolution:
        """Validate one *declared* voluntary token handoff. No biometrics."""
        if not isinstance(presentation, MockTokenPresentation):
            raise TypeError("MockTokenPresentation required")
        if not isinstance(context, MockOptInContext):
            raise TypeError("mock operator context required")
        now = _check_wall(now_wall_epoch_s)
        if not context.permitted(kind=None, needs_presentation=True):
            return MockResolution("no_operator_permission")
        if presentation.source != SOURCE:
            return MockResolution("untrusted_presentation")
        age = now - float(presentation.observed_epoch_s)
        if not 0 <= age <= MAX_PRESENTATION_AGE_S:
            return MockResolution("stale_or_future")
        digest = self._tag(presentation.token)
        try:
            with self._memory.conn:
                self._memory.conn.execute("BEGIN IMMEDIATE")
                self._prune(now)
                row = self._memory.conn.execute("""
                    SELECT association_ref,kind,last_sequence,
                           last_presented_epoch_s
                    FROM f4d_mock_optin_associations WHERE token_tag=?
                      AND enrolled_epoch_s <= ? AND expires_epoch_s > ?
                      AND source=?
                """, (digest,now,now,SOURCE)).fetchone()
                if row is None:
                    return MockResolution("unknown")
                if not context.permitted(kind=row["kind"], needs_presentation=True):
                    return MockResolution("guardian_or_assent_missing")
                if presentation.sequence <= int(row["last_sequence"]):
                    return MockResolution("replayed_presentation")
                last_epoch = row["last_presented_epoch_s"]
                if last_epoch is not None and now < float(last_epoch):
                    return MockResolution("stale_or_future")
                self._memory.conn.execute("""
                    UPDATE f4d_mock_optin_associations
                    SET last_sequence=?,last_presented_epoch_s=?
                    WHERE association_ref=?
                """, (presentation.sequence,now,row["association_ref"]))
                return MockResolution(
                    "mock_token_association_only",
                    row["association_ref"],row["kind"],
                )
        except sqlite3.Error:
            return MockResolution("history_unavailable")

    def revoke(self, *, association_ref: str, token: bytes,
               context: MockOptInContext) -> bool:
        """Hard-delete one binding; require matching token and operator claim.

        Not forensic erasure of old SQLite/WAL/backups: physical-data
        management, secure deletion, key storage and backups remain unbuilt.
        """
        reference = _ref(association_ref)
        digest = self._tag(token)
        if not isinstance(context, MockOptInContext):
            raise TypeError("mock operator context required")
        if not context.permitted(kind=None, needs_presentation=False):
            return False
        with self._memory.conn:
            row = self._memory.conn.execute("""
                DELETE FROM f4d_mock_optin_associations
                WHERE association_ref=? AND token_tag=?
            """, (reference,digest))
            return row.rowcount == 1

    def forget_all(self, *, context: MockOptInContext) -> int:
        """Opt-out failsafe: locally clear every mock association, even child.

        For actual data a future UI must verify the real operator/guardian,
        enforce encrypted storage, and manage journals/backups.
        """
        if not isinstance(context, MockOptInContext):
            raise TypeError("mock operator context required")
        if not context.permitted(kind=None,needs_presentation=False):
            return 0
        with self._memory.conn:
            result = self._memory.conn.execute(
                "DELETE FROM f4d_mock_optin_associations"
            )
            return result.rowcount
