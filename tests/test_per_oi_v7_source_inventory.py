"""PER-OI-V7 source-only contracts; synthetic CSV fixtures, no web or models."""
from __future__ import annotations

import base64
import csv
from pathlib import Path
import tempfile
import unittest

from experiments.per_oi_v7_source_inventory import (
    EXACT_CANDIDATES, OpenImagesSourceStop, source_inventory,
)


def write_rows(path: Path, fieldnames: list[str], data: list[dict]):
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


class OiV7SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.classes = self.root / "classes.csv"
        self.images = self.root / "images.csv"
        self.boxes = self.root / "boxes.csv"
        wanted = list(EXACT_CANDIDATES) + ["Ball"]
        self.label_mid = {
            label: "/m/" + f"{i+1:05x}" for i, label in enumerate(wanted)
        }
        taxonomy = [
            {"LabelName":mid,"DisplayName":name}
            for name,mid in self.label_mid.items()
        ] + [
            {"LabelName":f"/m/{i+101:05x}","DisplayName":f"other-{i}"}
            for i in range(110)
        ]
        write_rows(self.classes,["LabelName","DisplayName"],taxonomy)
        self.image_rows = []
        for n in range(1,1005):
            self.image_rows.append({
                "ImageID":f"{n:016x}", "Subset":"validation",
                "License":"https://creativecommons.org/licenses/by/2.0/",
                "OriginalMD5":base64.b64encode(n.to_bytes(16,"big")).decode("ascii"),
                "Rotation":"0", "OriginalURL":f"https://example.org/{n}.jpg",
            })
        self.image_rows[7]["License"] = "https://creativecommons.org/licenses/by-nc/2.0/"
        self.image_rows[11]["Rotation"] = "90"
        self.write_images()
        self.box_rows = []
        for i,label in enumerate(wanted,1):
            self.box_rows.append(self.make_box(i,label))
        self.box_rows.extend([
            self.make_box(8,"Ball"),
            self.make_box(9,"Person",IsDepiction="1"),
            self.make_box(10,"Cat",IsGroupOf="1"),
            self.make_box(11,"Dog",XMin="0.7",XMax="0.2"),
            self.make_box(12,"Chair"),
        ])
        self.write_boxes()

    def make_box(self,n,label,**changes):
        row = {
            "ImageID":f"{n:016x}","LabelName":self.label_mid[label],
            "Source":"xclick","Confidence":"1",
            "XMin":"0.1","XMax":"0.7","YMin":"0.2","YMax":"0.8",
            "IsGroupOf":"0","IsDepiction":"0","IsInside":"0",
        }
        row.update(changes)
        return row

    def write_images(self):
        write_rows(self.images,[
            "ImageID","Subset","License","OriginalMD5","Rotation","OriginalURL"
        ],self.image_rows)

    def write_boxes(self):
        write_rows(self.boxes,[
            "ImageID","LabelName","Source","Confidence",
            "XMin","XMax","YMin","YMax",
            "IsGroupOf","IsDepiction","IsInside",
        ],self.box_rows)

    def test_positive_public_metadata_only_counts_and_no_physical_promotion(self):
        result = source_inventory(self.classes,self.images,self.boxes)
        self.assertEqual("OI_V7_METADATA_INVENTORY_ONLY_NOT_QUALIFIED",result["status"])
        self.assertEqual(1004,result["validation_image_metadata_rows"])
        self.assertEqual(1002,result["per_image_declared_cc_by_2_valid_md5_zero_rotation"])
        self.assertEqual(2,result["excluded_image_metadata_or_duplicate_md5"])
        self.assertEqual(1,result["per_label"]["Ball"]["bounding_boxes"])
        for label in EXACT_CANDIDATES:
            self.assertEqual(1,result["per_label"][label]["validation_images_with_licensed_declared_gt"])
        self.assertEqual("UNKNOWN_NOT_INFERRED_FROM_BALL",result["sports_ball_coco_mapping"])
        self.assertEqual(1,result["skipped_annotations"]["group_depiction_or_inside"]//2)
        self.assertEqual(1,result["skipped_annotations"]["invalid_rect"])
        self.assertEqual(result["real_pixels_loaded"],0)
        self.assertEqual(result["models_loaded"],0)
        self.assertFalse(result["cohort_selected"])
        self.assertFalse(result["image_rights_independently_verified"])
        self.assertFalse(result["cross_dataset_duplicate_absence_verified"])
        self.assertFalse(result["scores_measured"])
        self.assertEqual(0,result["motor_commands"])
        for name in ("class_descriptions_sha256","validation_images_sha256","validation_bbox_sha256"):
            self.assertEqual(64,len(result["source_sha256"][name]))

    def test_negative_wrong_image_license_does_not_enter_ball_pool(self):
        self.image_rows[6]["License"]="https://creativecommons.org/licenses/by-nc-sa/2.0/"
        self.write_images()
        result=source_inventory(self.classes,self.images,self.boxes)
        self.assertEqual(0,result["per_label"]["Ball"]["bounding_boxes"])

    def test_negative_duplicate_image_identity_refused(self):
        self.image_rows[-1]["ImageID"]=self.image_rows[0]["ImageID"]
        self.write_images()
        with self.assertRaisesRegex(OpenImagesSourceStop,"duplicate image"):
            source_inventory(self.classes,self.images,self.boxes)

    def test_negative_wrong_class_taxonomy_refused(self):
        lines=self.classes.read_text(encoding="utf-8")
        self.classes.write_text(lines.replace(",Book\n",",Fiction title\n"),encoding="utf-8")
        with self.assertRaisesRegex(OpenImagesSourceStop,"mandatory common class"):
            source_inventory(self.classes,self.images,self.boxes)

    def test_negative_traversing_source_symlink_refused(self):
        shadow=self.root/"shadow.csv"
        shadow.symlink_to(self.boxes)
        with self.assertRaisesRegex(OpenImagesSourceStop,"symlinked"):
            source_inventory(self.classes,self.images,shadow)

    def test_negative_corrupt_bbox_with_unparseable_numeric_raises(self):
        self.box_rows[0]["XMin"]="not-a-number"
        self.write_boxes()
        with self.assertRaisesRegex(OpenImagesSourceStop,"malformed bbox"):
            source_inventory(self.classes,self.images,self.boxes)

    def test_negative_duplicate_mid_refused(self):
        duplicate = {"LabelName": self.label_mid["Person"],"DisplayName":"dupe"}
        with self.classes.open("a",encoding="utf-8",newline="") as fp:
            writer=csv.DictWriter(fp,fieldnames=["LabelName","DisplayName"])
            writer.writerow(duplicate)
        with self.assertRaisesRegex(OpenImagesSourceStop,"duplicate class"):
            source_inventory(self.classes,self.images,self.boxes)


if __name__ == "__main__":
    unittest.main()
