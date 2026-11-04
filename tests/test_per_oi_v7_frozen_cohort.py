"""PER-OI-V7-COHORT-1: GT-only positive/negative fixtures; zero JPEG/model."""
from __future__ import annotations

import base64
import csv
from hashlib import sha256
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.per_oi_v7_source_inventory import (
    OpenImagesSourceStop, source_inventory,
)
from experiments.per_oi_v7_frozen_cohort import (
    EXPECTED_SOURCE_SHA, EXPECTED_TOTAL, PER_TARGET, TARGETS,
    _eligible_images, _taxonomy, _valid_boxes, freeze_cohort,
    select_frozen_roster,
)


def _write(path: Path, fields, records):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def _fixtures(root: Path):
    classes = root / "classes.csv"
    images = root / "images.csv"
    boxes = root / "boxes.csv"
    mids = {name: f"/m/{i+1:05x}" for i, name in enumerate(TARGETS)}
    labels = [{"LabelName": mid, "DisplayName": name}
              for name, mid in mids.items()]
    labels += [{"LabelName": f"/m/{i+100:05x}", "DisplayName": f"other-{i}"}
               for i in range(110)]
    _write(classes, ["LabelName", "DisplayName"], labels)
    image_rows = []
    box_rows = []
    for i in range(1020):
        ident = f"{i+1:016x}"
        image_rows.append({
            "ImageID": ident, "Subset": "validation",
            "License": "https://creativecommons.org/licenses/by/2.0/",
            "OriginalMD5": base64.b64encode((i+1).to_bytes(16, "big")).decode(),
            "Rotation": "0", "OriginalURL": f"https://example.org/{ident}.jpg",
        })
    for label_i, name in enumerate(TARGETS):
        for j in range(10):
            ident = image_rows[label_i*10+j]["ImageID"]
            box_rows.append({
                "ImageID": ident, "LabelName": mids[name],
                "Source": "xclick", "Confidence": "1",
                "XMin": "0.1", "XMax": "0.3", "YMin": "0.1", "YMax": "0.3",
                "IsGroupOf": "0", "IsDepiction": "0", "IsInside": "0",
                "IsOccluded": "0", "IsTruncated": "0",
            })
    class_fields = ["ImageID", "Subset", "License", "OriginalMD5", "Rotation", "OriginalURL"]
    box_fields = ["ImageID", "LabelName", "Source", "Confidence",
                  "XMin", "XMax", "YMin", "YMax",
                  "IsGroupOf", "IsDepiction", "IsInside", "IsOccluded", "IsTruncated"]
    _write(images, class_fields, image_rows)
    _write(boxes, box_fields, box_rows)
    return classes, images, boxes, mids, image_rows, box_rows, class_fields, box_fields


class OiV7FrozenCohortTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.classes, self.images, self.boxes, self.mids,
         self.image_rows, self.box_rows, self.image_fields, self.box_fields) = (
            _fixtures(self.root))

    def _freeze_fixture(self):
        source = source_inventory(self.classes, self.images, self.boxes)
        with patch.dict(EXPECTED_SOURCE_SHA, source["source_sha256"]):
            return freeze_cohort(self.classes, self.images, self.boxes)

    def test_positive_42_disjoint_gt_only_and_hash_stable(self):
        first = self._freeze_fixture()
        again = self._freeze_fixture()
        self.assertEqual(first, again)
        self.assertEqual(EXPECTED_TOTAL, first["cohort_images"])
        self.assertEqual({n: PER_TARGET for n in TARGETS}, first["assigned_per_label"])
        self.assertEqual(42, first["selected_target_boxes"])
        self.assertEqual(64, len(first["roster_sha256"]))
        self.assertEqual("POSSIBLE_COCO_SPORTS_BALL_SUBTYPE_UNVERIFIED",
                         first["candidate_semantic_mapping"]["Tennis ball"])
        self.assertTrue(first["gt_independent_of_model_predictions"])
        self.assertFalse(first["cross_dataset_image_duplicate_absence_verified"])
        self.assertFalse(first["commercial_image_rights_individually_verified"])
        self.assertEqual((0, 0, 0), (
            first["images_fetched"], first["model_inferences"],
            first["motor_commands"]))

    def test_negative_unpinned_source_sha_refused_before_selection(self):
        with self.assertRaisesRegex(OpenImagesSourceStop, "SHA drift"):
            freeze_cohort(self.classes, self.images, self.boxes)

    def test_negative_missing_target_label_rejected(self):
        row = next(r for r in self.box_rows
                   if r["LabelName"] == self.mids["Tennis ball"])
        self.box_rows = [r for r in self.box_rows
                         if r["LabelName"] != self.mids["Tennis ball"]]
        _write(self.boxes, self.box_fields, self.box_rows)
        with patch.dict(EXPECTED_SOURCE_SHA,
                        source_inventory(self.classes, self.images,
                                         self.boxes)["source_sha256"]):
            with self.assertRaisesRegex(OpenImagesSourceStop, "Tennis ball"):
                freeze_cohort(self.classes, self.images, self.boxes)

    def test_negative_unauthorized_license_excludes_enough_ball_gt(self):
        for i in range(5):
            self.image_rows[i]["License"] = (
                "https://creativecommons.org/licenses/by-nc/2.0/")
        _write(self.images, self.image_fields, self.image_rows)
        with patch.dict(EXPECTED_SOURCE_SHA,
                        source_inventory(self.classes, self.images,
                                         self.boxes)["source_sha256"]):
            with self.assertRaisesRegex(OpenImagesSourceStop,
                                        "Tennis ball.*required=6"):
                freeze_cohort(self.classes, self.images, self.boxes)

    def test_negative_duplicate_md5_removes_both_candidates(self):
        self.image_rows[1]["OriginalMD5"] = self.image_rows[0]["OriginalMD5"]
        _write(self.images, self.image_fields, self.image_rows)
        eligible = _eligible_images(self.images)
        self.assertNotIn(self.image_rows[0]["ImageID"], eligible)
        self.assertNotIn(self.image_rows[1]["ImageID"], eligible)

    def test_negative_duplicate_image_id_rejected(self):
        self.image_rows[2]["ImageID"] = self.image_rows[0]["ImageID"]
        _write(self.images, self.image_fields, self.image_rows)
        with self.assertRaisesRegex(OpenImagesSourceStop, "duplicate image ID"):
            _eligible_images(self.images)

    def test_negative_duplicate_mid_rejected(self):
        with self.classes.open("a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([self.mids["Tennis ball"], "other"])
        with self.assertRaisesRegex(OpenImagesSourceStop, "repeated MID"):
            _taxonomy(self.classes)

    def test_negative_crowd_depiction_and_inside_do_not_add_truth(self):
        for i in (0, 1, 2):
            self.box_rows[i][("IsGroupOf", "IsDepiction", "IsInside")[i]] = "1"
        _write(self.boxes, self.box_fields, self.box_rows)
        mids = _taxonomy(self.classes)
        eligible = _eligible_images(self.images)
        boxes = _valid_boxes(self.boxes, mids, eligible)
        self.assertEqual(7, sum(1 for (ident,label) in boxes if label == "Tennis ball"))

    def test_negative_bogus_flag_rejected(self):
        self.box_rows[0]["IsTruncated"] = "maybe"
        _write(self.boxes, self.box_fields, self.box_rows)
        with self.assertRaisesRegex(OpenImagesSourceStop, "nonbinary"):
            _valid_boxes(self.boxes, _taxonomy(self.classes),
                         _eligible_images(self.images))

    def test_negative_nonfinite_bbox_rejected(self):
        self.box_rows[0]["XMin"] = "nan"
        _write(self.boxes, self.box_fields, self.box_rows)
        with self.assertRaisesRegex(OpenImagesSourceStop, "invalid target box"):
            _valid_boxes(self.boxes, _taxonomy(self.classes),
                         _eligible_images(self.images))

    def test_negative_wrong_source_annotations_rejected(self):
        self.box_rows[0]["Source"] = "automated"
        _write(self.boxes, self.box_fields, self.box_rows)
        with self.assertRaisesRegex(OpenImagesSourceStop, "unapproved"):
            _valid_boxes(self.boxes, _taxonomy(self.classes),
                         _eligible_images(self.images))

    def test_negative_duplicate_image_across_two_labels_is_not_counted_twice(self):
        mids = _taxonomy(self.classes)
        eligible = _eligible_images(self.images)
        boxes = dict(_valid_boxes(self.boxes, mids, eligible))
        shared_id = self.image_rows[0]["ImageID"]
        boxes[(shared_id, "Cat")] = boxes[(shared_id, "Tennis ball")]
        chosen, _ = select_frozen_roster(mids, eligible, boxes)
        self.assertEqual(42, len(chosen))
        self.assertEqual(42, len({image_id for image_id, _ in chosen}))

    def test_negative_missing_gt_quota_stops_without_resampling(self):
        mids = _taxonomy(self.classes)
        eligible = _eligible_images(self.images)
        boxes = {k:v for k,v in _valid_boxes(self.boxes,mids,eligible).items()
                 if k[1] != "Tennis ball" or k[0] in
                 {r["ImageID"] for r in self.image_rows[:5]}}
        with self.assertRaisesRegex(OpenImagesSourceStop,
                                    "Tennis ball.*required=6"):
            select_frozen_roster(mids, eligible, boxes)


if __name__ == "__main__":
    unittest.main()
