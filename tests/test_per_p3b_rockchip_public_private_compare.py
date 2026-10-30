"""PER-P3B: positive and negative data provenance/contract tests, no model."""
from __future__ import annotations

from io import BytesIO
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from experiments.per_p3b_rockchip_public_private_compare import (
    EXPECTED_PUBLIC, PRIVATE_STUDY, StudyStop,
    assess_image, prepare_rgb_and_jpeg, run, summarize_targets, verify_inputs,
)


def _jpeg() -> bytes:
    from PIL import Image
    b = BytesIO()
    # Deterministic test-only pattern, no operator photo.
    img = Image.frombytes(
        "RGB", (96, 96),
        bytes((i * 73 + i // 97) % 256 for i in range(96 * 96 * 3)))
    img.save(b, format="JPEG", quality=94)
    return b.getvalue()


def _private(root: Path) -> dict:
    data = _jpeg()
    (root / "images").mkdir()
    photos = []
    for idx, v in enumerate(("view_lateral", "view_front")):
        name = f"images/{v}.jpg"
        (root / name).write_bytes(data)
        photos.append({
            "id": v, "file": name,
            "session_group": "test_one_scene",
            "sha256_sanitized": hashlib.sha256(data).hexdigest(),
            "width": 96, "height": 96,
        })
    manifest = {
        "study": PRIVATE_STUDY,
        "not_two_independent_scenes": True,
        "image_exif_removed": True,
        "gt_boxes": "not_available",
        "camera_height_mm": None,
        "scene_group": "test_one_scene",
        "photos": photos,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8")
    return manifest


# Synthetic JPEG fixtures must test the real data gates.
# The production CI guard remains enabled outside fixture-only tests.
@patch.dict(os.environ, {"GITHUB_ACTIONS": "false"})
class TestPerP3BProvenance(unittest.TestCase):
    def test_two_sanitized_private_images_only_preflight(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            _private(root)
            report = run(root, source="private", preflight_only=True,
                         yolox_model=None, ppyoloe_model=None, vendor_root=None)
            self.assertEqual(report["scenes"], 2)
            self.assertEqual(report["status"], "preflight_only_NO_model_scores")
            self.assertNotIn("observations", report)
            self.assertFalse(report["inference_attempted"])
            self.assertTrue(report["single_private_scene_multiple_angles"])

    def test_private_source_forbidden_in_ci(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            _private(root)
            with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}):
                with self.assertRaises(StudyStop):
                    verify_inputs(root, source="private")

    def test_refuse_modified_private_sha_scene_and_one_image(self):
        for corrupt in ("sha", "scene", "missing", "height"):
            with self.subTest(corrupt=corrupt), TemporaryDirectory() as d:
                root = Path(d)
                manifest = _private(root)
                if corrupt == "sha":
                    manifest["photos"][1]["sha256_sanitized"] = "0"*64
                elif corrupt == "scene":
                    manifest["photos"][1]["session_group"] = "different_place"
                elif corrupt == "missing":
                    manifest["photos"].pop()
                else:
                    manifest["camera_height_mm"] = 200  # Was not measured.
                (root / "manifest.json").write_text(json.dumps(manifest))
                with self.assertRaises(StudyStop):
                    verify_inputs(root, source="private")

    def test_manifest_traversal_or_symlink_refused(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            manifest = _private(root)
            manifest["photos"][0]["file"] = "images/../view_lateral.jpg"
            (root / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(StudyStop):
                verify_inputs(root, source="private")
            manifest["photos"][0]["file"] = "images/view_lateral.jpg"
            (root / "manifest.json").write_text(json.dumps(manifest))
            (root / "images/view_lateral.jpg").unlink()
            (root / "images/view_lateral.jpg").symlink_to(
                root / "images/view_front.jpg")
            with self.assertRaises(StudyStop):
                verify_inputs(root, source="private")

    def test_refuse_corrupt_image_even_with_matching_sha(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            manifest = _private(root)
            data = b"x" * 2000
            (root / "images/view_front.jpg").write_bytes(data)
            manifest["photos"][1]["sha256_sanitized"] = hashlib.sha256(data).hexdigest()
            (root / "manifest.json").write_text(json.dumps(manifest))
            rows = verify_inputs(root, source="private")
            with self.assertRaises(StudyStop):
                prepare_rgb_and_jpeg(rows[1])

    def test_bounded_public_manifest_provenance(self):
        with TemporaryDirectory() as d:
            root = Path(d) / "public_vision_smoke"
            root.mkdir()
            data = _jpeg()
            names = []
            for cat, count in EXPECTED_PUBLIC.items():
                for i in range(count):
                    names.append({"file": f"{cat}_{i}.jpg", "category": cat,
                                  "source_git_blob_sha": hashlib.sha1(
                                      f"blob {len(data)}".encode()+bytes([0])+data
                                  ).hexdigest()})
                    (root / names[-1]["file"]).write_bytes(data)
            (root / "manifest.json").write_text(json.dumps({
                "version": 1, "images": names,
            }))
            rows = verify_inputs(root, source="public")
            self.assertEqual(len(rows), 13)
            tampered = list(names)
            tampered[-1] = dict(tampered[-1], source_git_blob_sha="a"*40)
            (root / "manifest.json").write_text(json.dumps({
                "version": 1, "images": tampered,
            }))
            with self.assertRaises(StudyStop):
                verify_inputs(root, source="public")


class TestPerP3BProposals(unittest.TestCase):
    def test_target_proposals_and_mismatched_category(self):
        found = summarize_targets([(15, .75), (15, .35), (0, .45), (2, .99)])
        self.assertEqual(found["cat"], {"count": 2, "best_score": .75})
        self.assertEqual(found["person"]["count"], 1)
        self.assertNotIn("dog", found)
        result = assess_image("public", "cat", {
            "yolox": [(15, .75)], "ppyoloe": [(16, .8)],
        })
        self.assertTrue(result["results"]["yolox"]["expected_category_proposed"])
        self.assertFalse(result["results"]["ppyoloe"]["expected_category_proposed"])

    def test_no_target_proposal_not_unknown_object_detection(self):
        row = assess_image("public", "unknown", {
            "yolox": [], "ppyoloe": [(2, .9)],
        })
        self.assertTrue(row["results"]["yolox"]["no_target_category_proposed"])
        self.assertTrue(row["results"]["ppyoloe"]["no_target_category_proposed"])
        row2 = assess_image("public", "unknown", {
            "yolox": [(32, .3)], "ppyoloe": [],
        })
        self.assertFalse(row2["results"]["yolox"]["no_target_category_proposed"])

    def test_private_no_accuracy_or_expected_label(self):
        row = assess_image("private", None, {
            "yolox": [(56, .8)], "ppyoloe": [(15, .7)],
        })
        self.assertIsNone(row["expected_image_label"])
        self.assertNotIn("expected_category_proposed", row["results"]["yolox"])

    def test_reject_forged_untrusted_scores_and_incomplete_pair(self):
        for bad in ([(-1, .6)], [(80, .6)], [(15, float("nan"))],
                    [(15, -0.1)], [(15, 1.1)], [(15, "high")]):
            with self.subTest(bad=bad):
                with self.assertRaises(StudyStop):
                    summarize_targets(bad)
        with self.assertRaises(StudyStop):
            assess_image("public", "cat", {"yolox": [(15, .8)]})


if __name__ == "__main__":
    unittest.main()
