"""PER-QUAL-1C1: GT-only, positive and adversarial fixtures (zero media)."""
import unittest
from unittest.mock import patch

from experiments.per80_yolox_coco_public import COCO80_ID_ORDER
from experiments.per_qual1_sama_gt_gate import (
    SEED, SEED_C1, TARGETS, SourceGateError, choose_paired_cohort,
)
from experiments.per_qual1c1_new42_source import (
    FAILED_RUN_CONSUMED, NEW_COUNT, PREVIOUS_COUNT, TOTAL_EXCLUSIONS,
    select_new_after_consumed,
)

OFFICIAL_COCO_IDS = {
    "person": 1, "cat": 17, "dog": 18, "sports_ball": 37,
    "bottle": 44, "chair": 62, "book": 84,
}


def synthetic_sources(images_per_class=13):
    """Realistic COCO ID domain, no photographs or prediction scores."""
    categories = [{"id": ident, "name": name.replace("_", " ")}
                  for name, ident in OFFICIAL_COCO_IDS.items()]
    orig = {"categories": categories, "images": [], "annotations": []}
    sama = {"categories": list(categories), "images": [], "annotations": []}
    names = [f"other_class_{i}" for i in range(80)]
    for name, coco_id in OFFICIAL_COCO_IDS.items():
        names[COCO80_ID_ORDER.index(coco_id)] = name
    ident_ann = 0
    for k, name in enumerate(TARGETS):
        coco_id = OFFICIAL_COCO_IDS[name]
        for j in range(images_per_class):
            ident = 30000 + k * 100 + j
            rec = {"id": ident, "width": 320, "height": 240,
                   "file_name": f"{ident:012d}.jpg", "license": 4}
            for source in (orig, sama):
                source["images"].append(dict(rec))
                ident_ann += 1
                source["annotations"].append({
                    "id": ident_ann, "image_id": ident,
                    "category_id": coco_id, "iscrowd": 0,
                    "bbox": [20, 40, 70, 90]})
    history = frozenset(range(100000, 100000 + PREVIOUS_COUNT))
    return orig, sama, tuple(names), history


def select_fixture(orig, sama, names, history):
    prior = choose_paired_cohort(
        orig, sama, old_ids=history, allowed_license_ids=frozenset({4}))[0]
    # Only fixtures bypass a prior-REAL-roster digest; no production bypass.
    with patch("experiments.per_qual1c1_new42_source._frozen_sha256"):
        newer = select_new_after_consumed(
            orig, sama, names=names, historical_ids=history,
            old_cases=prior, allowed_license_ids=frozenset({4}))
    return prior, newer


class NewCohortFixtures(unittest.TestCase):
    def test_frozen_new_roster_digest_rejects_any_changed_selection(self):
        from experiments.per_qual1_sama_gt_gate import _frozen_sha256
        from experiments.per_qual1c1_new42_source import FROZEN_NEW_COHORT_SHA256
        self.assertEqual(len(FROZEN_NEW_COHORT_SHA256), 64)
        self.assertNotEqual(
            FROZEN_NEW_COHORT_SHA256,
            "709718feba6185ddd79e2aa492c7eaf74bb2d904dfa6c30e81a25c31dbdb53d5",
        )
        with self.assertRaisesRegex(SourceGateError, "frozen SHA256 mismatch"):
            _frozen_sha256(b"altered source-only prospective cohort",
                           FROZEN_NEW_COHORT_SHA256, "prospective roster")

    def test_positive_42_new_and_1274_excluded(self):
        original, sama, names, hist = synthetic_sources()
        prior, (next_cases, maps, paired, _inventory) = select_fixture(
            original, sama, names, hist)
        old_ids = {i for i, _ in prior}
        new_ids = {i for i, _ in next_cases}
        self.assertEqual(FAILED_RUN_CONSUMED, len(old_ids))
        self.assertEqual(NEW_COUNT, len(new_ids))
        self.assertEqual(TOTAL_EXCLUSIONS, len(hist | old_ids))
        self.assertFalse(old_ids & new_ids)
        self.assertFalse(hist & new_ids)
        for name in TARGETS:
            self.assertEqual(sum(label == name for _, label in next_cases), 6)
            self.assertEqual(paired[name]["allocated_photos"], 6)
            self.assertGreaterEqual(paired[name]["original_gt_boxes"], 6)
            self.assertGreaterEqual(paired[name]["sama_gt_boxes"], 6)
            self.assertEqual(maps[name]["coco_category_id"], OFFICIAL_COCO_IDS[name])
            self.assertEqual(maps[name]["yolox_head_idx"],
                             COCO80_ID_ORDER.index(OFFICIAL_COCO_IDS[name]))

    def test_permutations_and_frozen_seed_do_not_change_roster(self):
        orig, sama, names, hist = synthetic_sources()
        before, (new_before, _, _, _) = select_fixture(orig, sama, names, hist)
        for data in (orig, sama):
            data["images"].reverse()
            data["annotations"].reverse()
        after, (new_after, _, _, _) = select_fixture(orig, sama, names, hist)
        self.assertEqual(before, after)
        self.assertEqual(new_before, new_after)

    def test_original_pre_registered_seed_unchanged(self):
        orig, sama, _, hist = synthetic_sources()
        first = choose_paired_cohort(orig, sama, old_ids=hist,
                                     allowed_license_ids=frozenset({4}))[0]
        explicit = choose_paired_cohort(orig, sama, old_ids=hist,
                         allowed_license_ids=frozenset({4}),
                         selection_seed=SEED)[0]
        self.assertEqual(first, explicit)
        self.assertNotEqual(SEED, SEED_C1)

    def test_unknown_seed_is_rejected_instead_of_tuning(self):
        orig, sama, _, hist = synthetic_sources()
        with self.assertRaisesRegex(SourceGateError, "invalid frozen"):
            choose_paired_cohort(orig, sama, old_ids=hist,
                allowed_license_ids=frozenset({4}),
                selection_seed="arbitrary-image-selection")

    def test_insufficient_second_cohort_is_stop_not_smaller_sample(self):
        orig, sama, names, hist = synthetic_sources(images_per_class=11)
        with self.assertRaisesRegex(SourceGateError, "STOP_SOURCE"):
            select_fixture(orig, sama, names, hist)

    def test_real_previous_roster_sha_required_before_new_cohort(self):
        orig, sama, names, hist = synthetic_sources()
        prior = choose_paired_cohort(orig, sama, old_ids=hist,
                                     allowed_license_ids=frozenset({4}))[0]
        with self.assertRaisesRegex(SourceGateError, "frozen SHA256 mismatch"):
            select_new_after_consumed(orig, sama, names=names,
                historical_ids=hist, old_cases=prior,
                allowed_license_ids=frozenset({4}))

    def test_swapped_old_ids_and_wrong_old_count_refused(self):
        orig, sama, names, hist = synthetic_sources()
        prior = choose_paired_cohort(orig, sama, old_ids=hist,
                                     allowed_license_ids=frozenset({4}))[0]
        with self.assertRaisesRegex(SourceGateError, "old cohort counts"):
            select_new_after_consumed(orig, sama, names=names,
                historical_ids=frozenset(), old_cases=prior,
                allowed_license_ids=frozenset({4}))
        with self.assertRaisesRegex(SourceGateError, "duplicate or leaked"):
            select_new_after_consumed(orig, sama, names=names,
                historical_ids=frozenset((hist - {min(hist)}) | {prior[0][0]}),
                old_cases=prior, allowed_license_ids=frozenset({4}))

    def test_coarse_class_ids_or_missing_gt_are_not_accepted(self):
        orig, sama, names, hist = synthetic_sources()
        wrong_names = list(names)
        i = COCO80_ID_ORDER.index(OFFICIAL_COCO_IDS["cat"])
        j = COCO80_ID_ORDER.index(OFFICIAL_COCO_IDS["person"])
        wrong_names[i], wrong_names[j] = wrong_names[j], wrong_names[i]
        with self.assertRaisesRegex(SourceGateError, "STOP_SCHEMA"):
            select_fixture(orig, sama, tuple(wrong_names), hist)
        orig, sama, names, hist = synthetic_sources()
        sama["annotations"] = [a for a in sama["annotations"]
                 if a["category_id"] != OFFICIAL_COCO_IDS["cat"]]
        with self.assertRaisesRegex(SourceGateError, "STOP_SOURCE"):
            select_fixture(orig, sama, names, hist)

    def test_license_gate_disallows_unauthorized_images(self):
        orig, sama, names, hist = synthetic_sources()
        prior = choose_paired_cohort(
            orig, sama, old_ids=hist, allowed_license_ids=frozenset({4}))[0]
        with patch("experiments.per_qual1c1_new42_source._frozen_sha256"):
            with self.assertRaisesRegex(SourceGateError, "STOP_SOURCE"):
                select_new_after_consumed(orig, sama, names=names,
                    historical_ids=hist, old_cases=prior,
                    allowed_license_ids=frozenset())


if __name__ == "__main__":
    unittest.main()
