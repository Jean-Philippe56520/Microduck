"""Cat-A protocol and artificial-head tests, no media/model downloads."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import tempfile
import unittest

from microduck_companion.cata_yolox_categories import (
    CATEGORIES, MAX_IMAGE_BYTES, MIN_SCORE, MODEL_LICENSE,
    MODEL_SHA256, MODEL_URL, _metrics, decode_categories,
    prepare_image, validate_model_file,
)
from microduck_companion.visual_photo_mobilenet_demo import PhotoBaselineError


class CategoryFirstContracts(unittest.TestCase):
    def test_predeclared_supported_coco_categories_not_personal_identity(self):
        self.assertEqual(
            {"person":0, "cat":15, "dog":16, "sports_ball":32,"chair":56},
            CATEGORIES)
        for unsupported in ("shoe", "hand", "foot", "head", "Kitty",
                            "Nessquick", "Malo"):
            self.assertNotIn(unsupported, CATEGORIES)
        self.assertEqual(0.25, MIN_SCORE)
        self.assertEqual("Apache-2.0", MODEL_LICENSE)
        self.assertEqual(64, len(MODEL_SHA256))
        self.assertIn("/resolve/", MODEL_URL)

    def test_false_acceptance_and_reject_are_exposed_not_relabelled(self):
        rows = [
            ("cat", "cat"), ("cat", "unknown"),
            ("dog", "cat"), ("unknown", "cat"),
            ("unknown", "unknown"), ("chair", "chair"),
        ]
        result = _metrics(rows)
        self.assertEqual(6, result["samples"])
        self.assertEqual(3, result["correct"])
        self.assertEqual(1, result["per_truth"]["cat"]["rejected_as_unknown"])
        self.assertEqual({"expected":"unknown","predicted":"cat","count":1},
                         next(x for x in result["errors"] if x["expected"]=="unknown"))
        self.assertEqual(.5, result["accuracy_image_level"])

    def test_empty_holdout_refused(self):
        with self.assertRaises(PhotoBaselineError):
            _metrics([])

    def test_model_hash_mismatch_rejected_before_inference(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "model.onnx"
            file.write_bytes(b"x" * 3_500_000)
            with self.assertRaisesRegex(PhotoBaselineError, "SHA256"):
                validate_model_file(file)
            file.unlink()
            with self.assertRaises(PhotoBaselineError):
                validate_model_file(file)

    def test_missing_approval_required_for_public_media(self):
        # CLI uses argparse, must exit before model or network activity.
        from microduck_companion.cata_yolox_categories import main
        with self.assertRaises(SystemExit) as cm:
            main(["--model-path", "/missing/model.onnx"])
        self.assertEqual(2, cm.exception.code)

    @unittest.skipUnless(__import__("importlib").util.find_spec("numpy"),
                         "NumPy optional in global CI")
    def test_decoded_raw_yolox_heads_and_unknown_rejection(self):
        import numpy as np
        arr = np.zeros((1,3549,85),dtype=np.float32)
        # Anchor 0 at grid(0,0), stride 8; center=(.5+.0)*8.
        arr[0,0,:4] = [.5,.5,1.1,1.1]
        arr[0,0,4] = .95
        arr[0,0,5+15] = .9
        label, score, scores = decode_categories(arr)
        self.assertEqual("cat", label)
        self.assertAlmostEqual(.855, score, places=4)
        self.assertLess(scores["dog"], .01)
        arr[0,0,5+15] = .10
        self.assertEqual("unknown", decode_categories(arr)[0])
        arr[0,0,5+15] = float("nan")
        with self.assertRaisesRegex(PhotoBaselineError, "nonfinite"):
            decode_categories(arr)

    @unittest.skipUnless(__import__("importlib").util.find_spec("numpy"),
                         "NumPy optional in global CI")
    def test_invalid_prediction_shape_and_probabilities_rejected(self):
        import numpy as np
        with self.assertRaises(PhotoBaselineError):
            decode_categories(np.zeros((1,100,85),dtype=np.float32))
        arr = np.zeros((1,3549,85),dtype=np.float32)
        arr[..., 4] = 1.2
        with self.assertRaisesRegex(PhotoBaselineError, "probabilities"):
            decode_categories(arr)

    @unittest.skipUnless(__import__("importlib").util.find_spec("numpy") and
                         __import__("importlib").util.find_spec("PIL"),
                         "NumPy and Pillow optional in global CI")
    def test_crop_is_only_synthetic_occlusion_not_real_low_camera(self):
        from PIL import Image
        from io import BytesIO
        from microduck_companion.cata_yolox_categories import SIZE
        image = Image.new("RGB", (80,120), (40,30,80))
        buffer=BytesIO()
        image.save(buffer,format="JPEG")
        orig=prepare_image(buffer.getvalue(), mode="original")
        crop=prepare_image(buffer.getvalue(), mode="bottom_half")
        self.assertEqual((1,3,SIZE,SIZE),orig.shape)
        self.assertEqual((1,3,SIZE,SIZE),crop.shape)
        self.assertFalse((orig==crop).all())
        with self.assertRaisesRegex(PhotoBaselineError, "invalid bounded"):
            prepare_image(buffer.getvalue(), mode="head_only")
        with self.assertRaises(PhotoBaselineError):
            prepare_image(b"<not an image>", mode="original")


if __name__ == "__main__":
    unittest.main()
