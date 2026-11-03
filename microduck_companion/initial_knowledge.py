"""COG-A1: bounded, read-only *candidate* general references; no robot control.

This is not an observation, an individual object identity, a verified effect,
an OEM capability negotiation, a safety clearance, or a second memory store.
An F1 label is permitted only as an index into general reference candidates.
Neither this module nor its dataset writes to ExperienceMemory or calls F2.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
import json
import re

SCHEMA_VERSION = 1
MAX_REFERENCE_BYTES = 16_384
MAX_RULES = 32
MAX_SOURCES = 8
MAX_TERMS = 6
_TOKEN = re.compile(r"[a-z][a-z0-9_.-]{1,63}\Z")
_KIND = frozenset({"property", "possible_use", "limitation"})
_SOURCE_KIND = frozenset({"author_draft", "pinned_oem_documentation"})
# Exact allowlisted document; a correct commit with an unrelated/nonexistent
# path is NOT evidence that an OEM skill is documented.
_OEM_APPROVED_CHEATSHEET = (
    "https://github.com/pollen-robotics/microduck/blob/"
    "942e58e3aa6dbb28e7037203fff11866122c7567/"
    "docs/robot/cheatsheet.md"
)
_OEM_REFERENCED_SKILLS = frozenset({
    "kick_left", "kick_right", "ground_pick", "sit_toggle",
})


@dataclass(frozen=True)
class ReferenceSource:
    id: str
    kind: str
    citation: str


@dataclass(frozen=True)
class GeneralReference:
    id: str
    concept: str
    kind: str
    statement: str
    conditions: tuple[str, ...]
    counterexamples: tuple[str, ...]
    source_ids: tuple[str, ...]
    oem_skill_reference: str | None

    # Fixed design constraints: these claims can NEVER be made true by a JSON
    # payload, caller-supplied label, repeated encounter, or OEM name alone.
    @property
    def source_status(self) -> str:
        return "candidate_not_operator_approved"

    @property
    def physical_observation_verified(self) -> bool:
        return False

    @property
    def skill_loaded_verified(self) -> bool:
        return False

    @property
    def motor_action_authorized(self) -> bool:
        return False

    @property
    def causality_established(self) -> bool:
        return False


@dataclass(frozen=True)
class GeneralReferenceCatalog:
    sources: tuple[ReferenceSource, ...]
    rules: tuple[GeneralReference, ...]
    version: int = SCHEMA_VERSION

    def for_concept(self, concept: str) -> tuple[GeneralReference, ...]:
        """General references only; this does not establish presence/identity."""
        if type(concept) is not str or _TOKEN.fullmatch(concept) is None:
            return ()
        return tuple(rule for rule in self.rules if rule.concept == concept)

    def for_f1_label(self, label: str) -> tuple[GeneralReference, ...]:
        """Strictly index already-known F1 vocabulary, NOT authenticate F1.

        Especially: other_object cannot be silently mapped to chair or
        cloth, and a caller saying person is not proof of a live human.
        A2 must separately validate the actual observation/provenance first.
        """
        from .passive_observations import OBJECT_CATEGORIES

        if (type(label) is not str or label in {"unknown", "other_object"}
                or label not in OBJECT_CATEGORIES):
            return ()
        return self.for_concept(label)


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    out: dict = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate key in reference JSON")
        out[key] = value
    return out


def _token(value: object) -> str:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise ValueError("invalid bounded reference token")
    return value


def _text(value: object) -> str:
    if (type(value) is not str or not 1 <= len(value) <= 260
            or value != value.strip() or not value.isprintable()):
        raise ValueError("invalid reference text")
    return value


def _texts(value: object, *, nonempty: bool) -> tuple[str, ...]:
    if (type(value) is not list or len(value) > MAX_TERMS
            or (nonempty and not value)):
        raise ValueError("invalid reference qualifier list")
    return tuple(_text(item) for item in value)


def _exact_keys(value: object, expected: set[str]) -> dict:
    if type(value) is not dict or set(value) != expected:
        raise ValueError("reference schema mismatch")
    return value


def parse_reference_bytes(raw: bytes) -> GeneralReferenceCatalog:
    """Pure fail-closed parser for versioned candidates; no SQLite or IO."""
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_REFERENCE_BYTES:
        raise ValueError("reference byte budget exceeded or invalid")
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              ValueError("nonfinite reference value")))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ValueError("invalid reference JSON") from exc
    _exact_keys(data, {"schema_version", "status", "sources", "rules"})
    if (type(data["schema_version"]) is not int
            or data["schema_version"] != SCHEMA_VERSION
            or data["status"] != "candidate_for_operator_review"):
        raise ValueError("unsupported reference version or review status")
    if (type(data["sources"]) is not list or not 1 <= len(data["sources"]) <= MAX_SOURCES
            or type(data["rules"]) is not list or not 1 <= len(data["rules"]) <= MAX_RULES):
        raise ValueError("reference count limit")
    sources: list[ReferenceSource] = []
    source_ids: set[str] = set()
    oem_source_ids: set[str] = set()
    for entry in data["sources"]:
        _exact_keys(entry, {"id", "kind", "citation"})
        source_id = _token(entry["id"])
        kind = entry["kind"]
        citation = _text(entry["citation"])
        if source_id in source_ids or type(kind) is not str or kind not in _SOURCE_KIND:
            raise ValueError("duplicate or invalid source")
        if kind == "pinned_oem_documentation":
            if citation != _OEM_APPROVED_CHEATSHEET:
                raise ValueError("OEM citation must be pinned to reviewed source")
            oem_source_ids.add(source_id)
        sources.append(ReferenceSource(source_id, kind, citation))
        source_ids.add(source_id)
    rules: list[GeneralReference] = []
    rule_ids: set[str] = set()
    for entry in data["rules"]:
        _exact_keys(entry, {"id", "concept", "kind", "statement", "conditions",
                            "counterexamples", "source_ids", "oem_skill_reference"})
        rule_id = _token(entry["id"])
        concept = _token(entry["concept"])
        kind = entry["kind"]
        statement = _text(entry["statement"])
        conditions = _texts(entry["conditions"], nonempty=True)
        counterexamples = _texts(entry["counterexamples"], nonempty=True)
        sources_for_rule = entry["source_ids"]
        if (rule_id in rule_ids or type(kind) is not str or kind not in _KIND
                or type(sources_for_rule) is not list
                or not 1 <= len(sources_for_rule) <= MAX_SOURCES):
            raise ValueError("invalid rule identity, kind or evidence")
        evidence = tuple(_token(source_id) for source_id in sources_for_rule)
        if len(set(evidence)) != len(evidence) or not set(evidence) <= source_ids:
            raise ValueError("unreviewed/missing reference source")
        skill = entry["oem_skill_reference"]
        if skill is not None:
            skill = _token(skill)
            if skill not in _OEM_REFERENCED_SKILLS or not set(evidence) & oem_source_ids:
                raise ValueError("OEM name must cite pinned OEM documentation")
        rules.append(GeneralReference(rule_id, concept, kind, statement,
                                      conditions, counterexamples, evidence, skill))
        rule_ids.add(rule_id)
    return GeneralReferenceCatalog(tuple(sources), tuple(rules))


def read_bundled_references() -> GeneralReferenceCatalog:
    """Read the one versioned packaged source. No network or DB."""
    raw = resources.files("microduck_companion").joinpath(
        "initial_knowledge_v1.json").read_bytes()
    return parse_reference_bytes(raw)
