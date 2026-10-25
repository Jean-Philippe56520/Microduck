"""F3-E: fail-closed metadata ledger for INDEPENDENT human review claims.

No image is opened, downloaded or annotated by this module. Catalogues
F3-B and F3-D contain self-declared Commons CC0 licenses and public-caption
labels, NOT independently verified rights or visual labels. A review record
is only a declaration: opaque reviewer IDs cannot prove independent humans,
and CC0 page claims cannot prove actual legal title to media.

No sample ever becomes training-authorized through this parser. Decisions
requiring consent, human rights verification and independent annotations
must be kept externally in a controlled private workflow.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import re
from typing import Any

from .visual_dataset import _parse_json
from .visual_photo_catalog import PHOTO_CATALOG
from .visual_photo_f3d_catalog import CHALLENGE_CATALOG

REVIEW_SCHEMA = 1
REVIEW_KIND = "public_photo_reviewer_attestations_only"
MAX_REVIEW_BYTES = 64 * 1024
MAX_REVIEW_ENTRIES = 96
_CATEGORIES = frozenset({"cat", "dog", "unknown"})
_ID = re.compile(r"s-[0-9a-f]{16}\Z", re.ASCII)
_REVIEWER = re.compile(r"r-[0-9a-f]{16}\Z", re.ASCII)
_VOTE_FIELDS = frozenset({
    "sample_id", "reviewer_id", "visual_label", "image_review_claimed",
    "cc0_page_claim_checked", "own_work_page_claim_checked",
})
_STATUSES = (
    "missing",
    "needs_second_attestation",
    "rights_claim_incomplete",
    "label_disagreement",
    "attestation_consensus_only",
)


class AnnotationReviewError(ValueError):
    """Invalid or privacy-unsafe review metadata; never certify rights."""


@dataclass(frozen=True)
class ReviewVote:
    sample_id: str
    reviewer_id: str
    visual_label: str
    image_review_claimed: bool
    cc0_page_claim_checked: bool
    own_work_page_claim_checked: bool


@dataclass(frozen=True)
class CatalogReviewReport:
    """Only declarations audited; intentionally no certified sample count."""

    catalog_entries: int
    declared_votes: int
    counts: tuple[tuple[str, int], ...]
    no_reviews_performed_by_software: bool = True
    identities_independently_verified: bool = False
    labels_independently_verified: bool = False
    licenses_legally_verified: bool = False
    images_opened: int = 0
    motor_commands_issued: int = 0
    training_authorizations_granted: int = 0


def catalog_labels() -> dict[str, str]:
    """Deterministic opaque IDs for all 48 public F3-B/D catalogue pages."""
    public = tuple(PHOTO_CATALOG) + tuple(x.photo for x in CHALLENGE_CATALOG)
    labels: dict[str, str] = {}
    for item in public:
        opaque = "s-" + hashlib.sha256(
            item.file_page.encode("utf-8")).hexdigest()[:16]
        if opaque in labels:
            raise AnnotationReviewError("duplicate public catalog ID")
        labels[opaque] = item.category
    if len(labels) != 48:
        raise AnnotationReviewError("expected exactly 48 curated public sources")
    return labels


def _parse_claims(raw: bytes) -> tuple[ReviewVote, ...]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_REVIEW_BYTES:
        raise AnnotationReviewError("invalid or oversized review metadata")
    try:
        data: dict[str, Any] = _parse_json(raw)
    except (ValueError, TypeError, RecursionError) as exc:
        raise AnnotationReviewError("invalid or ambiguous review JSON") from exc
    if (set(data) != {"schema_version", "kind", "votes"}
            or type(data["schema_version"]) is not int
            or data["schema_version"] != REVIEW_SCHEMA
            or data["kind"] != REVIEW_KIND
            or type(data["votes"]) is not list
            or len(data["votes"]) > MAX_REVIEW_ENTRIES):
        raise AnnotationReviewError("unexpected review envelope")
    known = catalog_labels()
    votes: list[ReviewVote] = []
    pairs: set[tuple[str, str]] = set()
    for row in data["votes"]:
        if type(row) is not dict or set(row) != _VOTE_FIELDS:
            raise AnnotationReviewError("unsafe extra/missing review field")
        sid, reviewer, label = (
            row["sample_id"], row["reviewer_id"], row["visual_label"])
        if (type(sid) is not str or not _ID.fullmatch(sid)
                or sid not in known or type(reviewer) is not str
                or not _REVIEWER.fullmatch(reviewer)
                or type(label) is not str or label not in _CATEGORIES):
            raise AnnotationReviewError("unknown sample/reviewer/category")
        if any(type(row[x]) is not bool for x in (
            "image_review_claimed", "cc0_page_claim_checked",
            "own_work_page_claim_checked",
        )):
            raise AnnotationReviewError("attestation values must be true/false")
        if (sid, reviewer) in pairs:
            raise AnnotationReviewError("same reviewer voted twice for source")
        pairs.add((sid, reviewer))
        votes.append(ReviewVote(
            sid, reviewer, label, row["image_review_claimed"],
            row["cc0_page_claim_checked"],
            row["own_work_page_claim_checked"]))
    return tuple(votes)


def summarize_catalog_reviews(raw: bytes) -> CatalogReviewReport:
    """Describe gaps; two matching claims are NOT external verification.

    No attestation is generated for real photos by this function; if none
    have been submitted, all 48 remain pending. A disputed source must be
    reviewed by a person offline, not silently corrected by this code.
    """
    votes = _parse_claims(raw)
    expected = catalog_labels()
    by_sample: dict[str, list[ReviewVote]] = {}
    for vote in votes:
        by_sample.setdefault(vote.sample_id, []).append(vote)
    counts: Counter[str] = Counter()
    for sid, original_label in expected.items():
        rows = by_sample.get(sid, [])
        if not rows:
            status = "missing"
        elif len(rows) < 2:
            status = "needs_second_attestation"
        elif any(not (v.image_review_claimed and v.cc0_page_claim_checked
                      and v.own_work_page_claim_checked) for v in rows):
            status = "rights_claim_incomplete"
        elif len({v.visual_label for v in rows}) != 1 or (
                rows[0].visual_label != original_label):
            status = "label_disagreement"
        else:
            status = "attestation_consensus_only"
        counts[status] += 1
    return CatalogReviewReport(
        catalog_entries=len(expected),
        declared_votes=len(votes),
        counts=tuple((s, counts[s]) for s in _STATUSES),
    )


def empty_review_payload() -> bytes:
    """Initial state: deliberately ZERO human reviews or permissions."""
    import json
    return json.dumps({
        "schema_version": REVIEW_SCHEMA,
        "kind": REVIEW_KIND,
        "votes": [],
    }, sort_keys=True).encode("ascii")
