"""Cat-A2c tests: 25 real-source caption roster, fake bytes and logits only.

Never download JPEGs, create GT bounding boxes or claim camera height in
unit tests. The separate opt-in CI performs transient genuine-media inference.
"""
from __future__ import annotations

from collections import Counter
from contextlib import redirect_stderr
from io import StringIO
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from microduck_companion.cata2_bbox_eval import Box
from microduck_companion.cata2c_public_caption_probe import (
    EXPECTED_GROUPS, EXPECTED_SUBJECT_CLASS, PROBE_ROSTER,
    TARGET_GROUPS, main, run_public_caption_probe,
    summarize_caption_proposals, validate_probe_roster,
)
from microduck_companion.visual_photo_catalog import PHOTO_CATALOG
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError

HAS_PIL = importlib.util.find_spec("PIL") is not None


def empty_rows():
    return tuple((entry.group, ()) for entry in PROBE_ROSTER)


class FakeImage:
    format = "JPEG"
    size = (320, 240)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def getexif(self):
        return {}

    def load(self):
        pass


class PublicCaptionProbeTests(unittest.TestCase):
    def test_frozen_25_public_subjects_from_existing_f3d(self):
        validate_probe_roster()
        self.assertEqual(25, len(PROBE_ROSTER))
        self.assertEqual(EXPECTED_GROUPS, dict(Counter(x.group for x in PROBE_ROSTER)))
        self.assertEqual({"cat", "dog", "chair", "ball"}, set(TARGET_GROUPS))
        self.assertIsNone(EXPECTED_SUBJECT_CLASS["bird"])
        self.assertIsNone(EXPECTED_SUBJECT_CLASS["flower"])
        self.assertEqual(25, len({x.photo.author for x in PROBE_ROSTER}))
        self.assertTrue(all(x.photo.license == "CC0-1.0" for x in PROBE_ROSTER))
        earlier = {x.author.casefold() for x in PHOTO_CATALOG}
        self.assertFalse(earlier & {x.photo.author.casefold() for x in PROBE_ROSTER})

    def test_missing_altered_or_extended_roster_rejected(self):
        for invalid in (PROBE_ROSTER[:-1], PROBE_ROSTER + PROBE_ROSTER[:1],
                        PROBE_ROSTER[::-1], list(PROBE_ROSTER), (), None):
            with self.subTest(invalid=type(invalid)), self.assertRaises(PhotoBaselineError):
                validate_probe_roster(invalid)

    def test_true_five_class_ground_truth_not_inferred_from_captions(self):
        report = summarize_caption_proposals(empty_rows())
        self.assertEqual(25, report["photos"])
        self.assertEqual(22, report["declared_positive_photos"])
        self.assertEqual(3, report["declared_non_target_photos_not_verified_negatives"])
        self.assertEqual(0, report["person_class_caption_positive_photos"])
        self.assertIsNone(report["precision_recall_f1_ap50"])
        self.assertIsNone(report["optical_center_height_per_photo_mm"])
        self.assertEqual(0, report["photos_verified_camera_height_100_to_300mm"])
        self.assertFalse(report["exhaustive_bbox_ground_truth_available"])
        self.assertFalse(report["source_descriptions_independently_verified"])
        for name, item in report["by_public_caption_subject_not_independent_gt"].items():
            self.assertEqual(0, item["images_with_any_proposed_category"])
            self.assertEqual(EXPECTED_GROUPS[name], item["images_without_proposed_category"])
            if name in TARGET_GROUPS:
                self.assertEqual(0, item["images_with_caption_subject_proposed"])
            else:
                self.assertIsNone(item["images_with_caption_subject_proposed"])

    def test_concordant_and_other_class_proposals_not_treated_as_tp_fp(self):
        values = list(empty_rows())
        idx_cat = next(i for i, v in enumerate(values) if v[0] == "cat")
        idx_bird = next(i for i, v in enumerate(values) if v[0] == "bird")
        values[idx_cat] = ("cat", ("cat", "dog", "cat"))
        values[idx_bird] = ("bird", ("person",))
        report = summarize_caption_proposals(tuple(values))
        result = report["by_public_caption_subject_not_independent_gt"]
        self.assertEqual(1, result["cat"]["images_with_caption_subject_proposed"])
        self.assertEqual(1, result["cat"]["other_proposals_not_verified_as_errors"])
        self.assertEqual(1, result["bird"]["images_with_any_proposed_category"])
        self.assertIsNone(result["bird"]["images_with_caption_subject_proposed"])
        self.assertTrue(report["proposed_other_classes_are_not_false_positives"])
        self.assertEqual(2, report["proposed_boxes_by_yolox_category_not_tp"]["cat"])
        self.assertEqual(1, report["proposed_boxes_by_yolox_category_not_tp"]["person"])
        self.assertIsNone(report["precision_recall_f1_ap50"])

    def test_malformed_rows_or_extra_category_rejected(self):
        for bad in (empty_rows()[:-1], empty_rows()[::-1],
                    (("cat", ("human_head",)),) + empty_rows()[1:],
                    (("cat", ("cat",)),) + empty_rows()[1:],
                    (("cat", ["cat"]),) + empty_rows()[1:],
                    list(empty_rows()), None):
            # A properly typed cat entry (fourth case) is valid, so handle
            # it outside this invalid roster list.
            if isinstance(bad, tuple) and bad[0] == ("cat", ("cat",)):
                continue
            with self.subTest(bad=str(type(bad))), self.assertRaises(PhotoBaselineError):
                summarize_caption_proposals(bad)
        okay = (("cat", ("cat",)),) + empty_rows()[1:]
        self.assertEqual(25, summarize_caption_proposals(okay)["photos"])

    def test_media_gate_and_invalid_model_rejected_before_network(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as e:
            main(["--model-path", "/missing/fake.onnx"])
        self.assertEqual(2, e.exception.code)
        with patch(
            "microduck_companion.cata2c_public_caption_probe.fetch_challenge_photo"
        ) as net, self.assertRaises(PhotoBaselineError):
            run_public_caption_probe(model_path=Path("/missing/fake.onnx"))
        net.assert_not_called()

    @unittest.skipUnless(HAS_PIL, "Pillow needed to simulate public JPEG decoding")
    def test_mock_25_inference_is_not_real_ground_truth(self):
        session = SimpleNamespace(
            get_inputs=lambda: [SimpleNamespace(
                name="images", shape=[1, 3, 416, 416])],
            get_outputs=lambda: [SimpleNamespace(
                name="output", shape=[1, 3549, 85])],
            get_providers=lambda: ["CPUExecutionProvider"],
            run=lambda *args: [object()],
        )
        ort = SimpleNamespace(
            SessionOptions=type("Options", (), {}),
            InferenceSession=lambda *args, **kwargs: session,
        )
        with patch(
            "microduck_companion.cata2c_public_caption_probe.validate_model_file"
        ), patch.dict(sys.modules, {"onnxruntime": ort}), patch(
            "microduck_companion.cata2c_public_caption_probe.fetch_challenge_photo",
            side_effect=[bytes([i])*300 for i in range(1, 26)],
        ), patch(
            "PIL.Image.open", return_value=FakeImage(),
        ), patch(
            "microduck_companion.cata2c_public_caption_probe.prepare_image",
            return_value=object(),
        ), patch(
            "microduck_companion.cata2c_public_caption_probe.decode_boxes",
            return_value=(Box("dog", (1., 2., 60., 80.), 0.85),),
        ):
            report = run_public_caption_probe(model_path=Path("fake.onnx"))
        self.assertEqual(25, report["photos"])
        self.assertEqual(25, report["proposed_boxes_by_yolox_category_not_tp"]["dog"])
        self.assertFalse(report["source_descriptions_independently_verified"])
        self.assertIsNone(report["precision_recall_f1_ap50"])
        self.assertEqual(0, report["photos_verified_camera_height_100_to_300mm"])
        self.assertFalse(report["media_published_or_saved"])
        self.assertEqual(0, report["motor_commands"])
        self.assertEqual(0, report["sqlite_writes"])
        self.assertEqual(0, report["qwen_calls"])
        self.assertNotIn("Cat_image.jpg", json.dumps(report))

    @unittest.skipUnless(HAS_PIL, "Pillow needed to simulate public JPEG decoding")
    def test_duplicate_media_fails_closed_without_partial_score(self):
        session = SimpleNamespace(
            get_inputs=lambda: [SimpleNamespace(
                name="images", shape=[1, 3, 416, 416])],
            get_outputs=lambda: [SimpleNamespace(
                name="output", shape=[1, 3549, 85])],
            get_providers=lambda: ["CPUExecutionProvider"],
            run=lambda *args: [object()],
        )
        ort = SimpleNamespace(
            SessionOptions=type("Options", (), {}),
            InferenceSession=lambda *args, **kwargs: session,
        )
        with patch(
            "microduck_companion.cata2c_public_caption_probe.validate_model_file"
        ), patch.dict(sys.modules, {"onnxruntime": ort}), patch(
            "microduck_companion.cata2c_public_caption_probe.fetch_challenge_photo",
            return_value=b"same jpeg" * 40,
        ) as fetch, patch(
            "PIL.Image.open", return_value=FakeImage(),
        ), patch(
            "microduck_companion.cata2c_public_caption_probe.prepare_image",
            return_value=object(),
        ), patch(
            "microduck_companion.cata2c_public_caption_probe.decode_boxes",
            return_value=(),
        ), self.assertRaisesRegex(PhotoBaselineError, "duplicate exact"):
            run_public_caption_probe(model_path=Path("fake.onnx"))
        self.assertEqual(2, fetch.call_count)


if __name__ == "__main__":
    unittest.main()
