"""PER-OI-V7-OVERLAP-1: audit frozen GT-only Open Images roster vs 288 used OI photos.

HOST METADATA ONLY. Never download pixels or model weights, publish image IDs,
claim source-owner rights, certify COCO pixel disjointness, or control a robot.
Depends on the frozen-42 selector from PR #312; this is a stacked candidate.
"""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path

from experiments.per_oi_v7_source_inventory import (
    _file, _rows, _HEX_ID, OpenImagesSourceStop,
)
from experiments.per_oi_v7_frozen_cohort import (
    EXPECTED_SOURCE_SHA, EXPECTED_TOTAL, PER_TARGET, TARGETS,
    _eligible_images, _taxonomy, _valid_boxes, select_frozen_roster,
)
from experiments.cata2d_openimages_bbox_public import _load_sources
from experiments.per_oi_w1_openimages_stress import choose_cases
from microduck_companion.cata2c_openimages_human_labels import (
    SOURCE_SHA256, select_human_verified_cases,
)

EXPECTED_ROSTER_SHA256 = "1026cb395a8b817c43d8e03fbafa695aabc0b9c927464cf9f81d39e686703bc3"
EXPECTED_W1_SHA256 = "6954c9a0136d262a01eeba44b1da35319cf5323d270c73bc306cfd7f5f33179a"
EXPECTED_OLD = (48, 192, 48)
EXPECTED_OLD_TOTAL = sum(EXPECTED_OLD)
MAX_BYTES = {
    "classes": 1_000_000, "images": 40_000_000,
    "human": 55_000_000, "boxes": 180_000_000,
}


def roster_sha(roster) -> str:
    return sha256("|".join(
        f"{label}/{ident}" for ident, label in roster
    ).encode("ascii")).hexdigest()


def w1_sha(cases) -> str:
    return sha256("|".join(
        f"{x.image_id}/{x.category}/{int(x.present)}" for x in cases
    ).encode("ascii")).hexdigest()


def _read_human_positive(human: Path, chosen: tuple, mids: dict[str, str]) -> set[str]:
    """Read only votes for the allocated label; zero/missing is NOT a negative photo."""
    assigned = {ident: label for ident, label in chosen}
    by_label = {name: mid for mid, name in mids.items()}
    votes: dict[str, set[int]] = {}
    for row in _rows(human, ("ImageID", "Source", "LabelName", "Confidence")):
        ident = row["ImageID"]
        if ident not in assigned or row["LabelName"] != by_label[assigned[ident]]:
            continue
        if row["Source"] not in ("verification", "crowdsource-verification"):
            raise OpenImagesSourceStop("STOP_SCHEMA: selected label not human verified")
        raw = row["Confidence"]
        if (not raw or len(raw) > 12 or
                any(ch not in "0123456789." for ch in raw)):
            raise OpenImagesSourceStop("STOP_SCHEMA: nonbinary human label encoding")
        try:
            numeric = Decimal(raw)
        except InvalidOperation as exc:
            raise OpenImagesSourceStop("STOP_SCHEMA: bad human label decimal") from exc
        if (not numeric.is_finite() or numeric not in (0, 1)
                or not _HEX_ID.fullmatch(ident)):
            raise OpenImagesSourceStop("STOP_SCHEMA: nonbinary or invalid human vote")
        votes.setdefault(ident, set()).add(int(numeric))
    return {ident for ident, states in votes.items() if states == {1}}


def _selected_https_landing(images: Path, chosen: tuple) -> set[str]:
    selected = {ident for ident, _ in chosen}
    good = set()
    for row in _rows(images, ("ImageID", "OriginalLandingURL")):
        ident = row["ImageID"]
        if ident in selected and row["OriginalLandingURL"].startswith("https://"):
            good.add(ident)
    return good


def assess_frozen_metadata(
    chosen: tuple[tuple[str, str], ...],
    old_a2c: frozenset[str],
    old_a2d: frozenset[str],
    old_w1: frozenset[str],
    positive: set[str],
    landing: set[str],
    *,
    frozen_sha256: str,
) -> dict:
    """Unit-testable fail-closed gate. Output contains only aggregate statistics."""
    if (len(chosen) != EXPECTED_TOTAL or
            any(not _HEX_ID.fullmatch(ident) or label not in TARGETS
                for ident, label in chosen) or
            len({ident for ident, _ in chosen}) != EXPECTED_TOTAL or
            any(Counter(label for _, label in chosen)[label] != PER_TARGET
                for label in TARGETS) or
            roster_sha(chosen) != frozen_sha256):
        raise OpenImagesSourceStop("STOP_ROSTER: not the exact sealed 42-photo selection")
    old_sets = (old_a2c, old_a2d, old_w1)
    if (any(type(s) is not frozenset or len(s) != expected
            for s, expected in zip(old_sets, EXPECTED_OLD))
            or len(old_a2c | old_a2d | old_w1) != EXPECTED_OLD_TOTAL):
        raise OpenImagesSourceStop("STOP_HISTORY: 288 historic OI cases not reconstructed")
    ids = {ident for ident, _ in chosen}
    used = old_a2c | old_a2d | old_w1
    overlap = len(ids & used)
    human_verified = len(ids & positive)
    https_landing = len(ids & landing)
    clean = overlap == 0 and human_verified == EXPECTED_TOTAL and https_landing == EXPECTED_TOTAL
    return {
        "status": ("OI_42_DISJOINT_FROM_288_WITH_HUMAN_GT_METADATA_ONLY"
                   if clean else "STOP_FROZEN_42_SOURCE_NOT_QUALIFIED"),
        "roster_sha256": frozen_sha256,
        "frozen_candidate_images": EXPECTED_TOTAL,
        "historical_openimages_ids_reconstructed": EXPECTED_OLD_TOTAL,
        "reused_known_openimages_count": overlap,
        "assigned_human_positive_with_bbox_count": human_verified,
        "assigned_human_unknown_or_contradictory_count": EXPECTED_TOTAL-human_verified,
        "selected_original_landing_https_count": https_landing,
        "known_oi_source_gate_pass": clean,
        "no_reselection_after_results": True,
        "coco_val_5000_flickr_overlap_checked": False,
        "old_1316_coco_pixel_overlap_checked": False,
        "other_corpus_pixel_near_duplicates_checked": False,
        "individual_photo_rights_verified": False,
        "tennis_ball_equivalent_to_all_sports_ball": False,
        "cohort_commercially_approved": False,
        "jpeg_downloaded": 0,
        "model_inferences": 0,
        "scores_measured": False,
        "robot_rknn_validated": False,
        "motor_commands": 0,
        "sqlite_writes": 0,
    }


def audit(classes: Path, images: Path, human: Path, boxes: Path) -> dict:
    paths = {"classes": classes, "images": images, "human": human, "boxes": boxes}
    hashes = {k: _file(p, MAX_BYTES[k]) for k, p in paths.items()}
    if (hashes["classes"] != EXPECTED_SOURCE_SHA["class_descriptions_sha256"] or
            hashes["images"] != EXPECTED_SOURCE_SHA["validation_images_sha256"] or
            hashes["boxes"] != EXPECTED_SOURCE_SHA["validation_bbox_sha256"] or
            hashes["human"] != SOURCE_SHA256["human_labels"]):
        raise OpenImagesSourceStop("STOP_SOURCE: official CSV SHA mismatch")

    mids = _taxonomy(classes)
    eligible = _eligible_images(images)
    gt = _valid_boxes(boxes, mids, eligible)
    chosen, _ = select_frozen_roster(mids, eligible, gt)
    if roster_sha(chosen) != EXPECTED_ROSTER_SHA256:
        raise OpenImagesSourceStop("STOP_ROSTER: upstream 42 digest changed")

    # Existing historical selectors; their actual IDs stay in volatile runner RAM.
    old_a2d, historical_source_sha, _ = _load_sources(classes, images, human, boxes)
    if historical_source_sha["human_labels"] != hashes["human"]:
        raise OpenImagesSourceStop("STOP_HISTORY: old human-label pin drift")
    class_raw, images_raw, human_raw, boxes_raw = (
        classes.read_bytes(), images.read_bytes(), human.read_bytes(), boxes.read_bytes())
    old_a2c = select_human_verified_cases(class_raw, images_raw, human_raw)
    first_240 = frozenset(
        [x.image_id for x in old_a2c] + [x.image_id for x in old_a2d])
    if len(first_240) != 240:
        raise OpenImagesSourceStop("STOP_HISTORY: A2c/A2d historical overlap")
    old_w1 = choose_cases(
        class_raw, images_raw, human_raw, boxes_raw, excluded_ids=first_240)
    if w1_sha(old_w1) != EXPECTED_W1_SHA256:
        raise OpenImagesSourceStop("STOP_HISTORY: W1 48-photo SHA mismatch")
    positive = _read_human_positive(human, chosen, mids)
    landing = _selected_https_landing(images, chosen)
    result = assess_frozen_metadata(
        chosen,
        frozenset(x.image_id for x in old_a2c),
        frozenset(x.image_id for x in old_a2d),
        frozenset(x.image_id for x in old_w1),
        positive, landing, frozen_sha256=EXPECTED_ROSTER_SHA256)
    result["official_csv_sha256"] = hashes
    result["historical_w1_sha256"] = EXPECTED_W1_SHA256
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-public-metadata", action="store_true")
    for field in ("classes", "images", "human", "boxes"):
        p.add_argument("--"+field, type=Path, required=True)
    a=p.parse_args(argv)
    if not a.approved_public_metadata:
        p.error("public source metadata authorization required")
    print(json.dumps(audit(a.classes,a.images,a.human,a.boxes),
                     allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
