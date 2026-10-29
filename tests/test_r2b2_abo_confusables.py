"""R2-B+2 contract tests using invented catalogue entries and descriptors only.

No real dataset/photograph is downloaded by unit tests. No inference,
model, identity, robot, or recognition performance is established here.
"""
from __future__ import annotations

import gzip
import io
import hashlib
import json
import random
import unittest
from unittest.mock import patch

from microduck_companion.r2b_independent_capture_eval import (
    ABO_POSES, ABO_REFS, ABO_QUERIES, R2BEvidenceError,
    _abo_spin_sample,
)
from microduck_companion.r2b2_abo_confusables import (
    CATEGORY, LISTING_BASE, SOURCE_COUNT, SHARDS, TEST_KNOWN, TEST_UNKNOWN,
    VAL_KNOWN, VAL_UNKNOWN, _parse_listings, _read_metadata,
    _splits, evaluate_vectors, _anonymized_confusions,
    evaluate_mem2b_candidates, _mem2b_policy_candidate,
)


def fake_metadata(*, duplicate_item=False, count=50):
    lines = []
    for k in range(count):
        iid = f"B{k:09d}"
        if duplicate_item and k == 1:
            iid = "B000000000"
        lines.append(json.dumps({
            "spin_id": f"{k+1:08x}",
            "item_id": iid,
            "product_type": [{"value": "CHAIR"}],
            "item_name": [{"language_tag": "en_US", "value": "private-not-used"}],
        }))
    lines.append(json.dumps({
        "spin_id": "abcdabcd", "item_id": "A000000000",
        "product_type": [{"value": "SOFA"}],
    }))
    return gzip.compress(("\n".join(lines) + "\n").encode())


def fake_roster():
    return tuple(
        (f"{i+1:08x}", {a: f"{i+1:08x}-{a}" for a in ABO_POSES})
        for i in range(SOURCE_COUNT)
    )


def fake_vectors(roster, *, learned=False):
    out = {}
    for i, (sid, _) in enumerate(roster):
        rng = random.Random(i * 37 + 9001)
        b = bytes(rng.randrange(5, 251) for _ in range(64))
        for a in ABO_POSES:
            rec = {"legacy": b}
            if learned:
                rec["learned"] = tuple(1. if j == i else 0.
                                       for j in range(SOURCE_COUNT))
            out[(sid, a)] = rec
    return out


class _Remote(io.BytesIO):
    def __init__(self, raw, *, url, redirect=False):
        super().__init__(raw)
        self._url = "https://evil.invalid/meta" if redirect else url

    def geturl(self):
        return self._url


class R2B2ConfusableProtocolTests(unittest.TestCase):
    def test_listing_requires_same_category_and_unique_catalogue_ids(self):
        first = fake_metadata(duplicate_item=True, count=49)
        second = gzip.compress(b'')
        roster = _parse_listings((first, second))
        self.assertEqual(48, len(roster))
        self.assertEqual(48, len(set(roster.values())))
        self.assertNotIn("abcdabcd", roster)
        self.assertEqual(CATEGORY, "CHAIR")
        self.assertEqual(SOURCE_COUNT, 30)
        self.assertEqual(len(SHARDS), 2)

    def test_disjoint_30_source_cohorts_are_predeclared(self):
        selected = fake_roster()
        mapping = {sid: f"B{i:09d}" for i, (sid, _) in enumerate(selected)}
        groups = _splits(selected, mapping)
        self.assertEqual({
            "validation_known": VAL_KNOWN,
            "validation_unknown": VAL_UNKNOWN,
            "test_known": TEST_KNOWN,
            "test_unknown": TEST_UNKNOWN,
        }, {k: len(v) for k, v in groups.items()})
        self.assertEqual(SOURCE_COUNT, len(set().union(*map(set,groups.values()))))

    def test_same_product_with_two_spins_rejected(self):
        selected = fake_roster()
        mapping = {sid: f"B{i:09d}" for i, (sid, _) in enumerate(selected)}
        mapping[selected[1][0]] = mapping[selected[0][0]]
        with self.assertRaisesRegex(R2BEvidenceError, "reused product"):
            _splits(selected, mapping)

    def test_incomplete_view_and_missing_source_rejected(self):
        selected = fake_roster()
        mapping = {sid: f"B{i:09d}" for i, (sid, _) in enumerate(selected)}
        bad = list(selected)
        sid, poses = bad[-1]
        poses = dict(poses)
        poses.pop(ABO_POSES[0])
        bad[-1] = (sid, poses)
        with self.assertRaisesRegex(R2BEvidenceError, "incomplete"):
            _splits(tuple(bad), mapping)
        del mapping[selected[-1][0]]
        with self.assertRaisesRegex(R2BEvidenceError, "reused product"):
            _splits(selected, mapping)

    def test_same_class_unknowns_and_threshold_not_fitted_on_test(self):
        selected = fake_roster()
        mapping = {sid: f"B{i:09d}" for i, (sid, _) in enumerate(selected)}
        groups = _splits(selected, mapping)
        vectors = fake_vectors(selected, learned=True)
        results = evaluate_vectors(
            vectors, groups, kinds=("legacy","learned"))
        for kind in results:
            stats = results[kind]
            self.assertEqual(VAL_KNOWN * 4, stats["validation"]["known_queries"])
            self.assertEqual(TEST_KNOWN * 4, stats["test"]["known_queries"])
            self.assertEqual(VAL_UNKNOWN * 4, stats["validation"]["unknown_queries"])
            self.assertEqual(TEST_UNKNOWN * 4, stats["test"]["unknown_queries"])
            self.assertEqual(0, stats["test"]["cross_object_misidentifications"])
            self.assertEqual(0, stats["test"]["false_known_on_unknown"])
            self.assertEqual([], stats["test_confusions"]["pair_errors_anonymous"])
            self.assertTrue(0 <= stats["threshold_frozen_on_validation_only"] <= 1)

    def test_forced_wrong_match_is_counted_without_exposing_item_id(self):
        selected = fake_roster()
        mapping = {sid: f"B{i:09d}" for i, (sid, _) in enumerate(selected)}
        groups = _splits(selected, mapping)
        vectors = fake_vectors(selected)
        refs = {sid: tuple(vectors[(sid, a)] for a in (0, 36))
                for sid in groups["test_known"]}
        actual = groups["test_unknown"][0]
        wrong = groups["test_known"][0]
        queries = ((actual, 9, vectors[(wrong, 0)]),)
        report = _anonymized_confusions(
            refs, queries, kind="legacy", threshold=0.0)
        self.assertEqual(1, report["wrong_pair_total"])
        self.assertEqual(1, len(report["pair_errors_anonymous"]))
        self.assertNotIn("B000000", json.dumps(report))


    def test_mem2b_fixed_policy_known_unknown_screen_on_synthetic_vectors(self):
        selected = fake_roster()
        mapping = {s: f"B{i:09d}" for i, (s, _) in enumerate(selected)}
        groups = _splits(selected, mapping)
        vectors = fake_vectors(selected)
        result = evaluate_mem2b_candidates(vectors, groups)
        measured = result["test"]
        self.assertEqual(0.94, result["fixed_probe_similarity_min"])
        self.assertEqual(0.025, result["fixed_probe_ambiguity_gap"])
        self.assertEqual(48, measured["known_views"])
        self.assertEqual(48, measured["correct_candidates"])
        self.assertEqual(0, measured["wrong_known_candidates"])
        self.assertEqual(0, measured["known_abstentions"])
        self.assertEqual(24, measured["unknown_views"])
        self.assertEqual(24, measured["unknown_rejected"])
        self.assertEqual(0, measured["false_candidates_for_unknown"])
        self.assertTrue(result["screening_gate_predeclared_24_of_48_zero_errors"])
        self.assertFalse(result["hardware_validated"])
        self.assertTrue(result["actual_sqlite_probe_not_run_on_real_media"])

    def test_mem2b_same_category_impostor_counted_not_verified(self):
        selected = fake_roster()
        mapping = {s: f"B{i:09d}" for i, (s, _) in enumerate(selected)}
        groups = _splits(selected, mapping)
        vectors = fake_vectors(selected)
        unknown = groups["test_unknown"][0]
        known = groups["test_known"][0]
        # An independent catalogue fixture impersonates the enrolled source.
        vectors[(unknown, ABO_QUERIES[0])] = {
            "legacy": vectors[(known, ABO_REFS[0])]["legacy"]
        }
        output = evaluate_mem2b_candidates(vectors, groups)
        self.assertEqual(1, output["test"]["false_candidates_for_unknown"])
        self.assertEqual(23, output["test"]["unknown_rejected"])
        self.assertFalse(output["screening_gate_predeclared_24_of_48_zero_errors"])
        self.assertNotIn("B0000000", json.dumps(output))

    def test_mem2b_exact_tie_between_groups_abstains(self):
        selected = fake_roster()
        mapping = {s: f"B{i:09d}" for i, (s, _) in enumerate(selected)}
        groups = _splits(selected, mapping)
        vectors = fake_vectors(selected)
        a, b = groups["test_known"][:2]
        # Two declared DIFFERENT products can have identical descriptors.
        for angle in ABO_REFS:
            vectors[(b, angle)] = {"legacy": vectors[(a, angle)]["legacy"]}
        stats = evaluate_mem2b_candidates(vectors, groups)["test"]
        self.assertGreaterEqual(stats["ambiguous_abstentions_included_in_rejections"], 4)
        self.assertEqual(0, stats["wrong_known_candidates"])

    def test_mem2b_parity_with_real_probe_on_artificial_fixtures(self):
        from microduck_companion.episodic_memory import ExperienceMemory
        from microduck_companion.multiview_pattern_memory import MultiviewPatternMemory
        from microduck_companion.compact_multimodal_memory import image_fingerprint
        def square(y=3, x=4):
            data = [30]*1024
            for row in range(y, y+12):
                for col in range(x, x+12):
                    data[row*32+col] = 195
            return bytes(data)
        a, b, unseen = square(), square(16, 16), bytes(
            [25 if (i//32) % 2 == 0 else 225 for i in range(1024)])
        db = ExperienceMemory(":memory:")
        try:
            store = MultiviewPatternMemory(db)
            one = store.observe_image(a, now_wall_epoch_s=1780000000.,
                                      category="object")
            store.observe_image(b, now_wall_epoch_s=1780000001.,
                                category="object", group_hint=one.group_id,
                                synthetic_same_source_claim=True)
            references = {"declared_a": (
                {"legacy": image_fingerprint(a)},
                {"legacy": image_fingerprint(b)},
            )}
            for observation in (a, b, unseen):
                predicted, status = _mem2b_policy_candidate(
                    references, {"legacy": image_fingerprint(observation)})
                actual = store.probe_image(
                    observation, now_wall_epoch_s=1780000002.,
                    category="unknown")
                self.assertEqual(status, actual.status)
                self.assertEqual(predicted is not None,
                                 actual.group_id is not None)
                self.assertFalse(actual.same_physical_source_verified)
        finally:
            db.close()

    def test_mem2b_refuses_wrong_provenance_and_partial_descriptors(self):
        selected = fake_roster()
        mapping = {s: f"B{i:09d}" for i, (s, _) in enumerate(selected)}
        groups = _splits(selected, mapping)
        vectors = fake_vectors(selected)
        with self.assertRaises(R2BEvidenceError):
            _mem2b_policy_candidate({"a": ({"legacy": b"x"*63},)},
                                    {"legacy": b"x"*64})
        with self.assertRaises(R2BEvidenceError):
            _mem2b_policy_candidate({"a": ({"legacy": b"x"*64},)},
                                    {"legacy": b"x"*63})
        with self.assertRaises(R2BEvidenceError):
            evaluate_mem2b_candidates({**vectors, ("other", 9): {}}, groups)
        groups = {**groups, "test_unknown": groups["test_known"]}
        with self.assertRaises(R2BEvidenceError):
            evaluate_mem2b_candidates(vectors, groups)

    def test_metadata_limits_and_redirects_fail_closed(self):
        good = fake_metadata()
        with self.assertRaises(R2BEvidenceError):
            _parse_listings((good,))
        with self.assertRaises(R2BEvidenceError):
            _parse_listings((gzip.compress(b'not json\n'), good))
        with self.assertRaises(R2BEvidenceError):
            _parse_listings((gzip.compress(b'X'*45_100_000), good))
        with self.assertRaisesRegex(R2BEvidenceError, "official predefined"):
            _read_metadata("https://untrusted.example/data")
        def opener(req, timeout=30):
            return _Remote(good, url=req.full_url, redirect=True)
        with self.assertRaisesRegex(R2BEvidenceError, "redirect"):
            _read_metadata(LISTING_BASE.format(0), opener=opener)

    def test_spin_reader_rejects_unreviewed_cohort_size(self):
        with self.assertRaisesRegex(R2BEvidenceError, "invalid preselected"):
            _abo_spin_sample(
                allowed_spin_ids=frozenset({"not-a-spin"}),
                source_count=30)
        with self.assertRaisesRegex(R2BEvidenceError, "invalid preselected"):
            _abo_spin_sample(source_count=70)


if __name__ == "__main__":
    unittest.main()
