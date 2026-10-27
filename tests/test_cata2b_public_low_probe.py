"""Cat-A2b public 12cm probe: synthetic only, no external downloads in tests.

A source SHA+geometry check is not a ground-truth annotation, a height
measurement, or a license/consent audit. These are HOST-only unit fixtures.
"""
from __future__ import annotations

from contextlib import redirect_stderr
from hashlib import sha1
from io import BytesIO, StringIO
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from microduck_companion.cata2_bbox_eval import Box
from microduck_companion.cata2b_public_low_probe import (
    EXPECTED_GEOMETRY, PublicPreview, SAMPLES, SOURCE_BASE, SOURCE_COMMIT,
    _load_verified_public_png, main, probe_public_low_angle,
)
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError

HAS_PIL = importlib.util.find_spec("PIL") is not None


def make_png(*, size=EXPECTED_GEOMETRY):
    from PIL import Image
    out = BytesIO()
    Image.new("RGB", size, (31, 151, 223)).save(out, format="PNG")
    return out.getvalue()


def fixture_sample(data):
    digest = sha1(
        b"blob " + str(len(data)).encode("ascii") + b"\x00" + data
    ).hexdigest()
    return PublicPreview("A00001.png", digest)


class FakeResponse(BytesIO):
    status = 200


@unittest.skipUnless(HAS_PIL, "Pillow required for generated PNG fixtures")
class PublicLowProbeTests(unittest.TestCase):
    def test_source_pinned_and_only_three_previews(self):
        self.assertEqual(3, len(SAMPLES))
        self.assertTrue(all(".." not in row.filename for row in SAMPLES))
        self.assertEqual(
            "473d261362901c944a65d630e3892abdeee2353b", SOURCE_COMMIT)
        self.assertIn(SOURCE_COMMIT, SOURCE_BASE)

    def test_one_verified_png_is_transcoded_only_in_ram(self):
        source = make_png()
        sample = fixture_sample(source)
        with patch(
            "microduck_companion.cata2b_public_low_probe.SAMPLES", (sample,)
        ), patch(
            "microduck_companion.cata2b_public_low_probe.urllib.request.urlopen",
            return_value=FakeResponse(source),
        ) as load:
            jpeg, digest = _load_verified_public_png(sample)
        self.assertEqual(1, load.call_count)
        self.assertTrue(jpeg.startswith(b"\xff\xd8"))
        self.assertTrue(jpeg.endswith(b"\xff\xd9"))
        self.assertEqual(64, len(digest))
        from PIL import Image
        with Image.open(BytesIO(jpeg)) as im:
            self.assertEqual(EXPECTED_GEOMETRY, im.size)

    def test_content_sha_changed_rejected_before_decoding(self):
        source = make_png()
        sample = PublicPreview("A00001.png", "0" * 40)
        with patch(
            "microduck_companion.cata2b_public_low_probe.SAMPLES", (sample,)
        ), patch(
            "microduck_companion.cata2b_public_low_probe.urllib.request.urlopen",
            return_value=FakeResponse(source),
        ), self.assertRaisesRegex(PhotoBaselineError, "not source-pinned"):
            _load_verified_public_png(sample)

    def test_wrong_height_and_shape_rejected(self):
        source = make_png(size=(640, 480))
        sample = fixture_sample(source)
        with patch(
            "microduck_companion.cata2b_public_low_probe.SAMPLES", (sample,)
        ), patch(
            "microduck_companion.cata2b_public_low_probe.urllib.request.urlopen",
            return_value=FakeResponse(source),
        ), self.assertRaisesRegex(PhotoBaselineError, "geometry"):
            _load_verified_public_png(sample)

    def test_unexpected_sample_or_url_never_fetched(self):
        sample = PublicPreview("../private.png", "f" * 40)
        with patch(
            "microduck_companion.cata2b_public_low_probe.urllib.request.urlopen"
        ) as fetch, self.assertRaisesRegex(
            PhotoBaselineError, "unsupported public"
        ):
            _load_verified_public_png(sample)
        fetch.assert_not_called()

    def test_oversize_or_nonpng_fails_closed(self):
        sample = SAMPLES[0]
        for payload in (b"x" * 1_250_001, b"x" * 100):
            with self.subTest(length=len(payload)), patch(
                "microduck_companion.cata2b_public_low_probe.urllib.request.urlopen",
                return_value=FakeResponse(payload),
            ), self.assertRaises(PhotoBaselineError):
                _load_verified_public_png(sample)

    def test_explicit_media_gate_and_model_hash_required(self):
        with TemporaryDirectory() as d:
            path = Path(d) / "missing.onnx"
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as err:
                main(["--model-path", str(path)])
            self.assertEqual(2, err.exception.code)
            with self.assertRaises(PhotoBaselineError):
                probe_public_low_angle(model_path=path)

    def test_mock_detector_proposals_are_never_labeled_tp_fp_fn(self):
        fake_session = SimpleNamespace(
            get_inputs=lambda: [SimpleNamespace(
                name="images", shape=[1, 3, 416, 416])],
            get_outputs=lambda: [SimpleNamespace(
                name="output", shape=[1, 3549, 85])],
            run=lambda *args: [object()],
        )
        ort = SimpleNamespace(
            SessionOptions=type("Options", (), {}),
            InferenceSession=lambda *args, **kwargs: fake_session,
        )
        data = tuple(("jpeg", f"{i:064x}") for i in (1, 2, 3))
        predictions = (
            (Box("chair", (2., 4., 40., 90.), 0.9),),
            (),
            (Box("cat", (20., 20., 100., 100.), 0.8),),
        )
        with patch(
            "microduck_companion.cata2b_public_low_probe.validate_model_file"
        ), patch.dict(sys.modules, {"onnxruntime": ort}), patch(
            "microduck_companion.cata2b_public_low_probe._load_verified_public_png",
            side_effect=data,
        ) as load, patch(
            "microduck_companion.cata2b_public_low_probe.prepare_image",
            return_value=object(),
        ), patch(
            "microduck_companion.cata2b_public_low_probe.decode_boxes",
            side_effect=predictions,
        ):
            report = probe_public_low_angle(model_path=Path("mock.onnx"))
        self.assertEqual(len(SAMPLES), load.call_count)
        self.assertEqual(3, report["public_preview_frames"])
        self.assertEqual(1, report["proposed_boxes_by_category_not_ground_truth"]["chair"])
        self.assertEqual(1, report["proposed_boxes_by_category_not_ground_truth"]["cat"])
        self.assertEqual(0, report["ground_truth_annotations_for_five_categories"])
        self.assertIsNone(report["localization_metrics_tp_fp_fn_ap50"])
        self.assertFalse(report["real_robust_low_camera_category_accuracy_known"])
        self.assertFalse(report["individual_frame_camera_height_independently_verified"])
        self.assertFalse(report["independent_source_scenes_verified"])
        self.assertFalse(report["media_published_or_saved"])
        self.assertFalse(report["robot_or_rknn_validated"])
        self.assertEqual(0, report["motor_commands"])
        self.assertEqual(0, report["sqlite_writes"])
        self.assertEqual(0, report["qwen_calls"])
        public = json.dumps(report)
        self.assertNotIn("A00001.png", public)
        self.assertNotIn("A00002.png", public)
        self.assertNotIn("A00019.png", public)


if __name__ == "__main__":
    unittest.main()
