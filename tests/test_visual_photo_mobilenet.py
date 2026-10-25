"""F3-B ONNX baseline: no network/weights/Pillow needed for contract tests."""
from __future__ import annotations

from pathlib import Path
import math
import tempfile
import unittest

from microduck_companion.visual_photo_mobilenet_demo import (
    CAT_INDICES, DOG_INDICES, MODEL_SHA256, MODEL_URL,
    _classification_metrics, check_model_file, classify_score,
    reduce_imagenet_scores, select_validation_threshold,
)
from microduck_companion.visual_photo_baseline import PhotoBaselineError


def logits(at, value=30.):
    values=[-20.]*1000
    values[at]=value
    return tuple(values)


class OnnxBridgeTests(unittest.TestCase):
    def test_model_has_explicit_hf_origin_and_sha256(self):
        self.assertEqual(64,len(MODEL_SHA256))
        self.assertTrue(MODEL_URL.startswith(
            "https://huggingface.co/onnxmodelzoo/mobilenetv2-12/"))
        self.assertEqual(118,len(DOG_INDICES))
        self.assertEqual(5,len(CAT_INDICES))

    def test_breed_mapping_is_exact_and_disjoint(self):
        self.assertEqual(151,min(DOG_INDICES))
        self.assertEqual(268,max(DOG_INDICES))
        self.assertEqual(281,min(CAT_INDICES))
        self.assertEqual(285,max(CAT_INDICES))
        self.assertFalse(set(DOG_INDICES)&set(CAT_INDICES))

    def test_dog_logits_produce_known_dog_mass(self):
        result,mass=reduce_imagenet_scores(logits(151))
        self.assertEqual("dog",result)
        self.assertGreater(mass,.99)

    def test_cat_logits_produce_known_cat_mass(self):
        result,mass=reduce_imagenet_scores(logits(285))
        self.assertEqual("cat",result)
        self.assertGreater(mass,.99)

    def test_wolf_is_not_a_dog_and_wild_cat_is_not_a_domestic_cat(self):
        for index in (269,270,275,286,289,300):
            with self.subTest(index=index):
                _,mass=reduce_imagenet_scores(logits(index))
                self.assertLess(mass,.001)

    def test_probability_input_is_not_softmaxed_a_second_time(self):
        values=[0.]*1000
        values[282]=.7
        values[151]=.3
        label,mass=reduce_imagenet_scores(tuple(values))
        self.assertEqual("cat",label)
        self.assertAlmostEqual(1.,mass)

    def test_nan_inf_wrong_size_and_nonfloat_rejected(self):
        bad_cases=[
            tuple([0.]*999),
            tuple([0.]*1001),
            tuple([0.]*1000)[:-1]+(float("nan"),),
            tuple([0.]*1000)[:-1]+(float("inf"),),
            tuple([0.]*1000)[:-1]+("cat",),
        ]
        for item in bad_cases:
            with self.subTest(len=len(item)), self.assertRaises(PhotoBaselineError):
                reduce_imagenet_scores(item)

    def test_threshold_trained_from_known_unknown_validation_only(self):
        validation=(
            ("cat","cat",.9),
            ("cat","cat",.8),
            ("dog","dog",.95),
            ("dog","cat",.2),
            ("unknown","dog",.15),
            ("unknown","cat",.05),
        )
        threshold=select_validation_threshold(validation)
        self.assertTrue(0.15 < threshold <= .8)
        self.assertEqual("unknown",classify_score("dog",.15,threshold))
        self.assertEqual("cat",classify_score("cat",.9,threshold))

    def test_threshold_missing_validation_unknown_fails(self):
        with self.assertRaises(PhotoBaselineError):
            select_validation_threshold((("cat","cat",.8),))
        with self.assertRaises(PhotoBaselineError):
            select_validation_threshold((("unknown","cat",.1),))

    def test_abstention_never_becomes_a_motor_instruction(self):
        self.assertEqual("unknown",classify_score("dog",.15,.2))
        self.assertEqual("cat",classify_score("cat",.90,.2))
        for bad in (float("nan"),float("inf"),-0.1,1.1,True):
            with self.subTest(value=bad),self.assertRaises(PhotoBaselineError):
                classify_score("dog",bad,.2)

    def test_confusion_reports_out_of_domain_false_known(self):
        scored=_classification_metrics((
            ("cat","cat"),("cat","unknown"),
            ("dog","dog"),("dog","cat"),
            ("unknown","dog"),("unknown","unknown"),
        ))
        self.assertEqual(6,scored["test_or_validation_samples"])
        self.assertEqual(3,scored["correct"])
        self.assertEqual(1,scored["false_known_on_unknown"])
        self.assertEqual(.5,scored["accuracy"])
        self.assertEqual(.5,scored["unknown_recall"])
        self.assertEqual(.5,scored["known_recall"])
        self.assertEqual(2,scored["cat"]["predicted"])

    def test_model_file_missing_or_fake_digest_fails(self):
        with self.assertRaises(PhotoBaselineError):
            check_model_file(Path("/this-file-does-not-exist.onnx"))
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/"fake.onnx"
            file.write_bytes(b"not real model")
            with self.assertRaises(PhotoBaselineError):
                check_model_file(file)


if __name__=="__main__":
    unittest.main()
