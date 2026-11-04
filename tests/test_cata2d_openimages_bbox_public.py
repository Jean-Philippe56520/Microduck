"""Cat-A2d public Open Images bbox/depiction gate: offline synthetic fixtures."""
from __future__ import annotations

import csv
from io import StringIO
import unittest

from experiments.cata2d_openimages_bbox_public import (
    CATEGORIES, PublicBox, _matched_boxes, select_public_cases,
)
from microduck_companion.cata2_bbox_eval import Box
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError


def csv_bytes(header, rows):
    out = StringIO()
    writer = csv.writer(out, lineterminator="\n")
    if header is not None:
        writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue().encode()


class PublicOpenImagesBoxTests(unittest.TestCase):
    def setUp(self):
        self.classes = [("/m/demo"+str(i), name)
                        for i, name in enumerate(("Person", "Cat", "Dog", "Chair"))]
        self.classes.append(("/m/ball", "Ball"))
        self.meta = []
        self.votes = []
        self.boxes = []
        for i, cat in enumerate(CATEGORIES):
            for present in (True, False):
                ident = f"{i*2+int(not present)+1:016x}"
                self.meta.append((
                    ident, "validation", "https://creativecommons.org/licenses/by/2.0/",
                    "48000", "0",
                ))
                self.votes.append((
                    ident, "verification", f"/m/demo{i}", str(int(present)),
                ))
                if present:
                    self.boxes.append((
                        ident, "xclick", f"/m/demo{i}", "1",
                        ".1", ".5", ".2", ".8",
                        "0", "0", "0", str(int(i == 1)), "0",
                    ))

    def blobs(self):
        return (
            csv_bytes(None, self.classes),
            csv_bytes(
                ["ImageID", "Subset", "License", "OriginalSize", "Rotation"],
                self.meta,
            ),
            csv_bytes(
                ["ImageID", "Source", "LabelName", "Confidence"],
                self.votes,
            ),
            csv_bytes([
                "ImageID", "Source", "LabelName", "Confidence",
                "XMin", "XMax", "YMin", "YMax", "IsOccluded",
                "IsTruncated", "IsGroupOf", "IsDepiction", "IsInside",
            ], self.boxes),
        )

    def select(self, **kwargs):
        return select_public_cases(
            *self.blobs(), excluded_ids=frozenset(), per_label=1, **kwargs,
        )

    def test_four_classes_with_true_positive_and_explicit_negative(self):
        cases = self.select()
        self.assertEqual(8, len(cases))
        self.assertEqual(8, len({x.image_id for x in cases}))
        self.assertEqual(
            {(c, label) for c in CATEGORIES for label in (True, False)},
            {(x.category, x.present) for x in cases},
        )
        self.assertTrue(any(x.boxes[0].depiction == "1"
                            for x in cases if x.boxes))
        self.assertFalse(any(c.category == "sports_ball" for c in cases))
        self.assertTrue(all(c.boxes for c in cases if c.present))
        self.assertTrue(all(not c.boxes for c in cases if not c.present))

    def test_order_is_stable_under_csv_permutation(self):
        a = self.select()
        self.classes.reverse()
        self.meta.reverse()
        self.votes.reverse()
        self.boxes.reverse()
        self.assertEqual(a, self.select())

    def test_excluding_an_old_image_without_replacement_stops(self):
        original = self.select()
        old = original[0].image_id
        with self.assertRaises(PhotoBaselineError):
            select_public_cases(
                *self.blobs(), excluded_ids=frozenset({old}), per_label=1,
            )

    def test_machine_vote_is_not_silently_treated_as_negative(self):
        row = list(self.votes[1])
        row[1] = "machine"
        self.votes[1] = tuple(row)
        with self.assertRaises(PhotoBaselineError):
            self.select()

    def test_omitted_vote_is_not_a_negative(self):
        self.votes.pop()
        with self.assertRaises(PhotoBaselineError):
            self.select()

    def test_conflicting_votes_do_not_create_false_truth(self):
        first = self.votes[0]
        self.votes.append((first[0], "crowdsource-verification",
                           first[2], "0"))
        with self.assertRaises(PhotoBaselineError):
            self.select()

    def test_grouped_box_is_not_single_target_instance(self):
        row = list(self.boxes[0])
        row[10] = "1"  # IsGroupOf
        self.boxes[0] = tuple(row)
        with self.assertRaises(PhotoBaselineError):
            self.select()

    def test_box_without_human_vote_is_not_positive(self):
        self.votes[0] = (self.votes[0][0], "verification", "/m/ball", "1")
        with self.assertRaises(PhotoBaselineError):
            self.select()

    def test_invalid_geometry_and_depiction_attribute_stop(self):
        saved = self.boxes[0]
        for idx, value in ((4, "nan"), (4, ".7"), (5, "1.2"), (11, "2")):
            with self.subTest(idx=idx, value=value):
                row = list(saved)
                row[idx] = value
                self.boxes[0] = tuple(row)
                with self.assertRaises(PhotoBaselineError):
                    self.select()
        self.boxes[0] = saved
        self.assertEqual(8, len(self.select()))

    def test_duplicate_metadata_and_unknown_rights_stop(self):
        self.meta.append(self.meta[0])
        with self.assertRaises(PhotoBaselineError):
            self.select()
        self.meta.pop()
        original = self.meta[0]
        self.meta[0] = (original[0], original[1],
                        "https://creativecommons.org/licenses/by-nc/2.0/",
                        original[3], original[4])
        with self.assertRaises(PhotoBaselineError):
            self.select()

    def test_matcher_requires_box_overlap_and_exact_category(self):
        refs = (PublicBox((.1, .2, .5, .8), "1"),)
        correct = (Box("cat", (10., 20., 50., 80.), .7),)
        wrong_label = (Box("dog", (10., 20., 50., 80.), .9),)
        wrong_place = (Box("cat", (60., 20., 80., 80.), .9),)
        self.assertEqual((1, 1), _matched_boxes(
            "cat", refs, correct, 100, 100,
        ))
        self.assertEqual((0, 0), _matched_boxes(
            "cat", refs, wrong_label, 100, 100,
        ))
        self.assertEqual((0, 0), _matched_boxes(
            "cat", refs, wrong_place, 100, 100,
        ))

    def test_repeated_proposals_do_not_duplicate_ground_truth(self):
        refs = (PublicBox((.1, .2, .5, .8), "0"),)
        pred = (Box("chair", (10., 20., 50., 80.), .9),
                Box("chair", (12., 21., 49., 80.), .8))
        self.assertEqual((1, 0), _matched_boxes(
            "chair", refs, pred, 100, 100,
        ))


if __name__ == "__main__":
    unittest.main()
