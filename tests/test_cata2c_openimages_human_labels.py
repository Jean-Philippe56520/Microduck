"""Cat-A2c public human-label selection tests, with NO Internet/model/photos."""
from __future__ import annotations

import csv
from io import StringIO
from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.cata2c_openimages_human_labels import (
    CLASS_MAPPING, VerifiedCase, binary_metrics, select_human_verified_cases,
    benchmark, main,
)
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError


def encode_csv(headers, records):
    out = StringIO()
    writer = csv.writer(out, lineterminator="\n")
    if headers is not None:
        writer.writerow(headers)
    writer.writerows(records)
    return out.getvalue().encode("utf-8")


class OpenImagesHumanLabelTests(unittest.TestCase):
    def setUp(self):
        self.names = [
            (f"/m/mock{i}", name)
            for i, name in enumerate(CLASS_MAPPING.values())
        ] + [("/m/mock4", "Ball")]
        self.metadata = []
        self.verified = []
        idx = 1
        for i, category in enumerate(CLASS_MAPPING):
            for present in (True, False):
                image_id = f"{idx:016x}"
                idx += 1
                self.metadata.append((
                    image_id, "validation",
                    "https://creativecommons.org/licenses/by/2.0/",
                    "49000", "0",
                ))
                self.verified.append((
                    image_id, "verification",
                    f"/m/mock{i}", str(int(present)),
                ))

    def blobs(self):
        return (
            encode_csv(None, self.names),
            encode_csv(
                ["ImageID", "Subset", "License", "OriginalSize", "Rotation"],
                self.metadata,
            ),
            encode_csv(
                ["ImageID", "Source", "LabelName", "Confidence"],
                self.verified,
            ),
        )

    def select(self, **kwargs):
        return select_human_verified_cases(*self.blobs(), per_label=1, **kwargs)

    def test_human_binary_cohort_has_distinct_images_and_expected_labels(self):
        cases = self.select()
        self.assertEqual(8, len(cases))
        self.assertEqual(8, len({c.image_id for c in cases}))
        self.assertEqual(
            {(category, positive) for category in CLASS_MAPPING for positive
             in (True, False)},
            {(c.category, c.present) for c in cases},
        )
        self.assertFalse(any(c.category == "sports_ball" for c in cases))

    def test_official_v7_class_names_with_header(self):
        classes, meta, labels = self.blobs()
        headed = b"LabelName,DisplayName\n" + classes
        samples = select_human_verified_cases(
            headed, meta, labels, per_label=1,
        )
        self.assertEqual(8, len(samples))

    def test_selection_order_not_depends_on_csv_row_order(self):
        a = self.select()
        self.names.reverse()
        self.metadata.reverse()
        self.verified.reverse()
        self.assertEqual(a, self.select())

    def test_alternate_http_cc_by_2_0_metadata_allowed_only(self):
        first = list(self.metadata[0])
        first[2] = "http://creativecommons.org/licenses/by/2.0/"
        self.metadata[0] = tuple(first)
        self.assertEqual(8, len(self.select()))
        first[2] = "https://creativecommons.org/licenses/by-nc/2.0/"
        self.metadata[0] = tuple(first)
        with self.assertRaises(PhotoBaselineError):
            self.select()

    def test_rotated_or_unlicensed_images_not_silently_used(self):
        for field, value in ((4, "90"), (1, "train"), (3, "0"),
                             (2, "https://unknown.invalid/")):
            with self.subTest(field=field):
                old = self.metadata[0]
                row = list(old)
                row[field] = value
                self.metadata[0] = tuple(row)
                with self.assertRaises(PhotoBaselineError):
                    self.select()
                self.metadata[0] = old

    def test_machine_label_and_absence_of_annotation_are_not_negatives(self):
        row = self.verified[1]
        self.verified[1] = (row[0], "machine", row[2], row[3])
        with self.assertRaises(PhotoBaselineError):
            self.select()
        self.verified[1] = row
        self.verified.pop()
        with self.assertRaises(PhotoBaselineError):
            self.select()

    def test_conflicting_human_votes_refused_by_exclusion(self):
        first = self.verified[0]
        self.verified.append((first[0], "crowdsource-verification",
                              first[2], "0"))
        with self.assertRaises(PhotoBaselineError):
            self.select()

    def test_duplicate_image_metadata_is_not_silent(self):
        self.metadata.append(self.metadata[0])
        with self.assertRaisesRegex(PhotoBaselineError, "duplicate"):
            self.select()

    def test_nonbinary_human_confidence_rejected(self):
        first = self.verified[0]
        self.verified[0] = (first[0], first[1], first[2], "0.85")
        with self.assertRaisesRegex(PhotoBaselineError, "nonbinary"):
            self.select()

    def test_class_mapping_requires_single_exact_mid(self):
        self.names.append(("/m/duplicate", "Cat"))
        with self.assertRaisesRegex(PhotoBaselineError, "ambiguous"):
            self.select()
        self.names.pop()
        self.names = [v for v in self.names if v[1] != "Chair"]
        with self.assertRaisesRegex(PhotoBaselineError, "ambiguous"):
            self.select()

    def test_undocumented_classes_and_invalid_csv_rejected(self):
        self.names[0] = ("person", "Person")
        with self.assertRaises(PhotoBaselineError):
            self.select()
        self.names[0] = ("/m/mock0", "Person")
        self.metadata.append(("000000000000000g", "validation",
                              "https://creativecommons.org/licenses/by/2.0/",
                              "49000", "0"))
        with self.assertRaises(PhotoBaselineError):
            self.select()

    def test_image_level_binary_metrics_do_not_claim_object_map(self):
        cases = self.select()
        # Positive: detected; negative: no prediction, except one FP chair.
        found = tuple(c.present or c.category == "chair" for c in cases)
        r = binary_metrics(cases, found)
        self.assertEqual(1, r["cat"]["tp"])
        self.assertEqual(1, r["cat"]["tn"])
        self.assertEqual(0, r["cat"]["fp"])
        self.assertEqual(1, r["chair"]["fp"])
        self.assertEqual(0, r["chair"]["tn"])
        self.assertEqual(0.0, r["chair"]["specificity"])
        self.assertNotIn("map", r["chair"])
        with self.assertRaises(PhotoBaselineError):
            binary_metrics(cases, tuple([True] * 7))
        with self.assertRaises(PhotoBaselineError):
            binary_metrics(cases, tuple([True] * 7 + [1]))

    def test_changed_source_metadata_rejected_before_runtime_or_download(self):
        classes, metadata, labels = self.blobs()
        with tempfile.TemporaryDirectory() as dirname:
            base = Path(dirname)
            paths = [base / f"{i}.csv" for i in range(3)]
            for path, blob in zip(paths, (classes, metadata, labels)):
                path.write_bytes(blob)
            with patch(
                "microduck_companion.cata2c_openimages_human_labels.validate_model_file"
            ), patch("urllib.request.urlopen", side_effect=AssertionError("no network")):
                with self.assertRaisesRegex(PhotoBaselineError, "metadata changed"):
                    benchmark(
                        model_path=base / "nonexistent.onnx",
                        class_path=paths[0], metadata_path=paths[1],
                        labels_path=paths[2],
                    )

    def test_network_requires_explicit_approval(self):
        with patch("sys.stderr"), patch(
            "urllib.request.urlopen", side_effect=AssertionError("no internet")
        ):
            with self.assertRaises(SystemExit) as x:
                main([
                    "--model-path", "model.onnx", "--classes-path", "class.csv",
                    "--metadata-path", "metadata.csv", "--labels-path", "labels.csv",
                ])
        self.assertEqual(2, x.exception.code)


if __name__ == "__main__":
    unittest.main()
