"""F5-A: optional PC hypothesis contract, with NO PC/network or actuator I/O.

The existing AutonomyBrain chooses a local, fictional passive intention FIRST.
Only a bounded, sanitized and non-identifying MOCK object category can be
offered to a future PC. The reply is NEVER sensor evidence, memory feedback,
a social interaction, a navigation decision or a motor/speaker command.

This phase performs no Ollama/Qwen calls. A future, separately reviewed PC
adapter may send PCRequest.to_wire() and pass received bytes to
finish_optional_pc_cycle(). Its timeout/transport must be implemented there.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import uuid

from .autonomy import AutonomyBrain
from .passive_intentions import PassiveIntent
from .passive_memory import PassiveObservationJournal
from .passive_observations import PASSIVE_KINDS, summarize_passive
from .passive_sources import PassiveRead
from .perception import PerceptionSnapshot

SCHEMA_VERSION = 1
REQUEST_SOURCE = "mock_fixture_unix"
REPLY_SOURCE = "pc_qwen_unverified"
MAX_REQUEST_OBSERVATIONS = 4
MAX_REPLY_HYPOTHESES = 4
MAX_REPLY_BYTES = 4096
MAX_WAIT_S = 2.0
MAX_HYPOTHESIS_TTL_S = 5.0
# Neither arbitrary text nor personal identities, emergency/safety values or
# instructions are permitted through this F5-A contract.
HYPOTHESIS_CATEGORIES = frozenset({
    "unknown", "ball", "toy", "dog", "cat", "microduck", "other_object",
})
SENSITIVE_SOUND_CATEGORIES = frozenset({
    "speech", "keyword_microduck", "keyword_stop", "keyword_viens",
})


class PCContractError(ValueError):
    """Untrusted, mismatched, late or malformed optional-PC fixture reply."""


def _finite(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _request_id(value: object) -> bool:
    return (type(value) is str and len(value) == 32
            and all(ch in "0123456789abcdef" for ch in value))


@dataclass(frozen=True)
class PCObservation:
    """An unresolved mock category, never an image, track, person or sensor."""

    kind: str
    category: str
    status: str
    claimed_confidence: float

    def __post_init__(self) -> None:
        if (self.kind != "object_label" or self.category != "unknown"
                or self.status not in {"unknown", "conflict"}
                or not _finite(self.claimed_confidence)
                or self.claimed_confidence > 1):
            raise ValueError("only bounded unresolved mock object categories")


@dataclass(frozen=True)
class PCRequest:
    """Transport-neutral fictional request; no PC endpoint/identity included."""

    request_id: str
    observations: tuple[PCObservation, ...]
    created_monotonic_s: float
    expires_monotonic_s: float
    schema_version: int = SCHEMA_VERSION
    source: str = REQUEST_SOURCE

    def __post_init__(self) -> None:
        if (not _request_id(self.request_id)
                or type(self.schema_version) is not int
                or self.schema_version != SCHEMA_VERSION
                or self.source != REQUEST_SOURCE
                or type(self.observations) is not tuple
                or not 1 <= len(self.observations) <= MAX_REQUEST_OBSERVATIONS
                or not all(isinstance(o, PCObservation) for o in self.observations)
                or not _finite(self.created_monotonic_s)
                or not _finite(self.expires_monotonic_s)
                or not 0 < self.expires_monotonic_s - self.created_monotonic_s
                <= MAX_WAIT_S):
            raise ValueError("invalid or unbounded fictional PC request")

    def to_wire(self) -> bytes:
        """Only explicitly allowlisted generic fields leave the local brain."""
        return json.dumps({
            "schema_version": self.schema_version,
            "request_id": self.request_id,
            "source": self.source,
            "task": "hypothesize_object_category",
            "observations": [
                {"kind": o.kind, "category": o.category, "status": o.status,
                 "claimed_confidence": o.claimed_confidence}
                for o in self.observations
            ],
            "hypotheses_are_unverified": True,
        }, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


@dataclass(frozen=True)
class PCUnverifiedHypothesis:
    """A short-lived, uncalibrated PC claim with ZERO authority."""

    kind: str
    category: str
    claimed_confidence: float
    received_monotonic_s: float
    expires_monotonic_s: float
    source: str = REPLY_SOURCE
    verified: bool = False
    physical_actions_authorized: bool = False
    identity_verified: bool = False
    motor_commands_issued: int = 0
    speaker_commands_issued: int = 0

    def __post_init__(self) -> None:
        if (self.kind != "object_label"
                or type(self.category) is not str
                or self.category not in HYPOTHESIS_CATEGORIES
                or not _finite(self.claimed_confidence)
                or self.claimed_confidence > 1
                or not _finite(self.received_monotonic_s)
                or not _finite(self.expires_monotonic_s)
                or not self.expires_monotonic_s > self.received_monotonic_s
                or self.source != REPLY_SOURCE
                or self.verified or self.physical_actions_authorized
                or self.identity_verified or self.motor_commands_issued
                or self.speaker_commands_issued):
            raise ValueError("PC hypotheses can never grant physical authority")


@dataclass(frozen=True)
class OptionalPCAdvisory:
    """A local intention, plus optional separated, unverified annotations."""

    local_intent: PassiveIntent
    request: PCRequest | None
    status: str
    hypotheses: tuple[PCUnverifiedHypothesis, ...] = ()
    motor_commands_issued: int = 0
    speaker_commands_issued: int = 0

    def __post_init__(self) -> None:
        if (not isinstance(self.local_intent, PassiveIntent)
                or self.local_intent.executed
                or type(self.hypotheses) is not tuple
                or any(not isinstance(h, PCUnverifiedHypothesis)
                       for h in self.hypotheses)
                or self.motor_commands_issued or self.speaker_commands_issued
                or self.status not in {
                    "not_needed", "pending_transport", "pc_unavailable",
                    "response_rejected", "hypotheses_unverified",
                }):
            raise ValueError("PC advice cannot execute actions")
        if self.status == "not_needed":
            if self.request is not None or self.hypotheses:
                raise ValueError("no request is allowed for local-only cycle")
        elif not isinstance(self.request, PCRequest):
            raise ValueError("PC status requires an original request")
        if self.status != "hypotheses_unverified" and self.hypotheses:
            raise ValueError("rejected or absent PC reply cannot add knowledge")


def _prepare_request(read: PassiveRead, intent: PassiveIntent,
                     now_monotonic_s: float) -> PCRequest | None:
    """Never use bare claimed sensor provenance, track IDs or free text."""
    if (intent.intention != "inspect" or intent.source != "mock"
            or read.status != "ok" or read.channel != REQUEST_SOURCE
            or type(read.sequence) is not int
            or not 0 <= read.sequence < 2**63
            or not isinstance(read.snapshot, PerceptionSnapshot)
            or read.snapshot.environment != "mock"
            or any(e.kind not in PASSIVE_KINDS or e.source != "mock"
                   for e in read.snapshot.events)
            or any(
                (e.kind == "object_label" and e.value == "person")
                or (e.kind == "sound_label"
                    and e.value in SENSITIVE_SOUND_CATEGORIES)
                for e in read.snapshot.events
            )):
        return None
    try:
        found = summarize_passive(read.snapshot, now=now_monotonic_s)
    except (ValueError, TypeError):
        return None
    if any(o.status in {"stale", "future", "untrusted"}
           or (o.kind == "object_label" and o.category == "person")
           or (o.kind == "sound_label"
               and o.category in SENSITIVE_SOUND_CATEGORIES)
           for o in found):
        return None
    observations = tuple(
        PCObservation(o.kind, o.category, o.status, o.confidence)
        for o in found
        if o.kind == "object_label" and o.status in {"unknown", "conflict"}
    )
    if not 1 <= len(observations) <= MAX_REQUEST_OBSERVATIONS:
        return None
    return PCRequest(
        uuid.uuid4().hex, observations, float(now_monotonic_s),
        float(now_monotonic_s) + MAX_WAIT_S,
    )


def start_optional_pc_cycle(
    brain: AutonomyBrain, reading: PassiveRead, *,
    journal: PassiveObservationJournal,
    now_monotonic_s: float, now_wall_epoch_s: float,
) -> OptionalPCAdvisory:
    """Choose locally first, even if the PC is absent or will hallucinate.

    Reuses the F2-B/F2-C-capable AutonomyBrain; there is no second scheduler.
    Only fictional F1-B observations are eligible. No network I/O occurs.
    """
    if not isinstance(brain, AutonomyBrain):
        raise TypeError("existing AutonomyBrain required")
    local = brain.propose_balanced_passive(
        reading, journal=journal, now_monotonic_s=now_monotonic_s,
        now_wall_epoch_s=now_wall_epoch_s,
    )
    request = _prepare_request(reading, local, now_monotonic_s)
    return OptionalPCAdvisory(
        local, request, "pending_transport" if request else "not_needed"
    )


def _decode_reply(wire: bytes) -> dict:
    if type(wire) is not bytes or not 0 < len(wire) <= MAX_REPLY_BYTES:
        raise PCContractError("PC reply must be bounded UTF-8 bytes")

    def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
        obj: dict[str, object] = {}
        for key, value in pairs:
            if key in obj:
                raise PCContractError("duplicate PC reply property")
            obj[key] = value
        return obj

    try:
        result = json.loads(
            wire.decode("utf-8"), object_pairs_hook=unique_pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                PCContractError("nonfinite PC response")),
        )
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise PCContractError("invalid PC reply JSON") from exc
    if type(result) is not dict:
        raise PCContractError("PC reply must be an object")
    return result


def parse_pc_reply(
    request: PCRequest, wire: bytes, *, received_monotonic_s: float,
) -> tuple[PCUnverifiedHypothesis, ...]:
    """Strictly parse UNTRUSTED mock reply, without using its contents.

    Arrival time is measured by the local caller, not claimed by the PC.
    Remote monotonic clocks are not comparable. A future network adapter
    must enforce the actual I/O timeout independently.
    """
    if not isinstance(request, PCRequest):
        raise TypeError("PCRequest required")
    if (not _finite(received_monotonic_s)
            or not request.created_monotonic_s <= received_monotonic_s
            < request.expires_monotonic_s):
        raise PCContractError("late, future or invalid local receipt time")
    data = _decode_reply(wire)
    if (set(data) != {"schema_version", "request_id", "source", "hypotheses"}
            or type(data["schema_version"]) is not int
            or data["schema_version"] != SCHEMA_VERSION
            or data["request_id"] != request.request_id
            or data["source"] != REPLY_SOURCE):
        raise PCContractError("reply schema, source or correlation mismatch")
    raw_hypotheses = data["hypotheses"]
    if type(raw_hypotheses) is not list or len(raw_hypotheses) > MAX_REPLY_HYPOTHESES:
        raise PCContractError("invalid PC hypothesis count")
    parsed: list[PCUnverifiedHypothesis] = []
    categories: set[str] = set()
    for raw in raw_hypotheses:
        if type(raw) is not dict or set(raw) != {
            "kind", "category", "confidence", "ttl_s",
        }:
            raise PCContractError("unexpected PC hypothesis fields")
        if (raw["kind"] != "object_label"
                or type(raw["category"]) is not str
                or raw["category"] not in HYPOTHESIS_CATEGORIES
                or raw["category"] in categories
                or not _finite(raw["confidence"])
                or raw["confidence"] > 1
                or not _finite(raw["ttl_s"])
                or not 0 < raw["ttl_s"] <= MAX_HYPOTHESIS_TTL_S):
            raise PCContractError("invalid PC hypothesis value")
        categories.add(raw["category"])
        parsed.append(PCUnverifiedHypothesis(
            "object_label", raw["category"], float(raw["confidence"]),
            float(received_monotonic_s),
            min(request.expires_monotonic_s,
                float(received_monotonic_s) + float(raw["ttl_s"])),
        ))
    return tuple(parsed)


def finish_optional_pc_cycle(
    cycle: OptionalPCAdvisory, wire: bytes | None, *,
    received_monotonic_s: float,
) -> OptionalPCAdvisory:
    """No PC: preserve the local decision. Bad PC: discard ALL suggestions.

    Nothing is written to SQLite, passed to robotd, or fed into motors/audio.
    This method never invokes an API or blocks on the PC. The caller supplies
    a local receipt timestamp; real network deadlines are deferred to F5-B/C.
    """
    if not isinstance(cycle, OptionalPCAdvisory):
        raise TypeError("existing local advisory required")
    if cycle.status != "pending_transport" or cycle.request is None:
        raise ValueError("only a pending consultation may be completed")
    if wire is None:
        return OptionalPCAdvisory(cycle.local_intent, cycle.request, "pc_unavailable")
    try:
        hypotheses = parse_pc_reply(
            cycle.request, wire, received_monotonic_s=received_monotonic_s,
        )
    except PCContractError:
        return OptionalPCAdvisory(
            cycle.local_intent, cycle.request, "response_rejected",
        )
    return OptionalPCAdvisory(
        cycle.local_intent, cycle.request, "hypotheses_unverified", hypotheses,
    )
