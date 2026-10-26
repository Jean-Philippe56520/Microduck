"""M1-B2 offline contract tests: no download, model weights, or OEM access."""
from __future__ import annotations
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.m1b2_host_embeddings import (
    YAMNET_SHA256, YAMNET_URL, _audio_variants, _latency, _pairs,
    check_audio_model, conservative_threshold, main, similarity,
)


class M1B2OfflineTests(unittest.TestCase):
    def test_live_study_is_opt_in_and_requires_both_paths(self):
        with patch("microduck_companion.m1b2_host_embeddings.run_public_study") as run:
            for args in ([], ["--public-cc0"],
                         ["--image-model", "i", "--audio-model", "a"]):
                with self.subTest(args=args), self.assertRaises(SystemExit) as caught:
                    main(args)
                self.assertEqual(2, caught.exception.code)
            run.assert_not_called()

    def test_audio_weights_pinned_and_bad_file_rejected(self):
        self.assertEqual(64, len(YAMNET_SHA256))
        self.assertIn("/audiomagic/yamnet-onnx/", YAMNET_URL)
        with self.assertRaises(ValueError):
            check_audio_model(Path("/nonexistent/yamnet.onnx"))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "yamnet.onnx"
            path.write_bytes(b"no model")
            with self.assertRaises(ValueError):
                check_audio_model(path)

    def test_no_validation_pairs_fails_closed(self):
        for neg in ((), (float("nan"),), (float("inf"),), (1.1,), (-1.1,),
                    (True,), ("bad",)):
            with self.subTest(neg=neg), self.assertRaises(ValueError):
                conservative_threshold(neg)

    def test_validation_negatives_freeze_strict_cutoff(self):
        self.assertEqual(.8, conservative_threshold((.1, .8, .4)))
        self.assertEqual(1., conservative_threshold((1.,)))

    def test_cosine_only_accepts_finite_matching_vectors(self):
        self.assertAlmostEqual(1., similarity((1., 0.), (2., 0.)))
        self.assertAlmostEqual(0., similarity((1., 0.), (0., 1.)))
        for bad in (((), ()), ((0.,), (0.,)), ((1.,), (1., 2.)),
                    ((1.,), (float("nan"),)), ((True,), (1.,))):
            with self.subTest(pair=bad), self.assertRaises(ValueError):
                similarity(*bad)

    def test_cross_file_merges_are_not_called_verified_false_identities(self):
        # An identical learned signature across different files is a problem.
        records = {
            "a": {"original": {"legacy": bytes([2]*64),
                               "learned": (1., 0.)},
                  "rotation": {"legacy": bytes([2]*64),
                               "learned": (1., 0.)}},
            "b": {"original": {"legacy": bytes([2]*64),
                               "learned": (1., 0.)},
                  "rotation": {"legacy": bytes([3]*64),
                               "learned": (1., 0.)}},
        }
        result = _pairs(records, ("a", "b"), ("rotation",), kind="learned",
                        threshold=.95)
        self.assertEqual(2, result["same_file_hits"]["rotation"])
        self.assertEqual(1, result["cross_file_merges_proxy"])
        self.assertEqual(1, result["cross_file_pairs_proxy"])
        # An exact maximum-negative threshold must abstain on ties.
        safer = _pairs(records, ("a", "b"), ("rotation",), kind="learned",
                       threshold=conservative_threshold((1.,)))
        self.assertEqual(0, safer["cross_file_merges_proxy"])
        self.assertEqual(0, safer["same_file_hits"]["rotation"])

    def test_audio_gain_and_shift_keep_one_second_and_no_io(self):
        raw = tuple((i % 101) * 100 for i in range(16000))
        result = _audio_variants(raw)
        self.assertEqual(set(result),
                         {"original", "gain_80pct", "shift_16ms",
                          "synthetic_noise_26dB"})
        self.assertEqual(result["synthetic_noise_26dB"],
                         _audio_variants(raw)["synthetic_noise_26dB"])
        self.assertNotEqual(raw, result["synthetic_noise_26dB"])
        self.assertEqual((0,) * 256, result["shift_16ms"][:256])
        self.assertEqual(raw[:-256], result["shift_16ms"][256:])
        self.assertEqual(round(raw[123] * .8), result["gain_80pct"][123])
        with self.assertRaises(ValueError):
            _audio_variants(tuple([0] * 1024))

    def test_latency_report_counts_real_samples_only(self):
        self.assertEqual(4, _latency([4., 3., 1., 2.])["calls"])
        self.assertEqual(4., _latency([4., 3., 1., 2.])["p95_ms"])
        with self.assertRaises(ValueError):
            _latency([])


if __name__ == "__main__":
    unittest.main()
