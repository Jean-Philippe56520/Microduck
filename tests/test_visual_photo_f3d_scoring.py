"""F3-D scoring and resource contract tests, no real images loaded."""
from __future__ import annotations
import platform
import unittest
from microduck_companion.visual_photo_f3d_benchmark import (
    FROZEN_F3B_THRESHOLD, FROZEN_THRESHOLD_EVIDENCE, _latency_summary,
    host_rss_kib, host_peak_rss_kib, summarize_challenge, wilson_interval,
)
from microduck_companion.visual_photo_baseline import PhotoBaselineError
from microduck_companion.visual_photo_mobilenet_demo import classify_score

class FrozenHoldoutTests(unittest.TestCase):
    def test_threshold_from_prior_validation_not_challenge(self):
        self.assertEqual(.7059010988271212,FROZEN_F3B_THRESHOLD)
        self.assertIn("40243269608",FROZEN_THRESHOLD_EVIDENCE)
        self.assertEqual("unknown",classify_score(
            "dog",float(FROZEN_F3B_THRESHOLD-.001),FROZEN_F3B_THRESHOLD))

    def test_fictional_metric_computation(self):
        rows=(
            (("cat","cat","cat"),)*7 + (("cat","unknown","cat"),)
            + (("dog","dog","dog"),)*6
            + (("dog","cat","dog"),("dog","unknown","dog"))
            + (("unknown","unknown","chair"),)*3
            + (("unknown","dog","chair"),)
            + (("unknown","unknown","flower"),)*4
            + (("unknown","unknown","bird"),)*2
            + (("unknown","cat","ball"),)
            + (("unknown","unknown","ball"),)
        )
        report=summarize_challenge(rows)
        self.assertEqual(28,report["test_or_validation_samples"])
        self.assertEqual(23,report["correct"])
        self.assertEqual(2,report["false_known_on_unknown"])
        self.assertEqual(16,report["known_support"])
        self.assertEqual(12,report["unknown_support"])
        self.assertEqual(9,report["cat"]["predicted"])
        self.assertEqual(7,report["dog"]["predicted"])
        self.assertFalse(report["independent_label_audit_completed"])
        self.assertFalse(report["overlap_with_imagenet_pretraining_audited"])

    def test_invalid_group_or_output_cannot_be_scored(self):
        for case in ((("cat","dog","bird"),),
                     (("dog","person","dog"),),
                     (("unknown","cat","cat"),),()):
            with self.subTest(case=case),self.assertRaises(PhotoBaselineError):
                summarize_challenge(case)

    def test_false_known_is_separate_from_recognized_animal_recall(self):
        report=summarize_challenge((("cat","cat","cat"),
                                    ("dog","dog","dog"),
                                    ("unknown","dog","chair")))
        self.assertEqual(1,report["false_known_on_unknown"])
        self.assertEqual(1.,report["unknown_false_known_rate"])
        self.assertEqual(1.,report["known_recall"])

    def test_wilson_interval_with_tiny_denominator(self):
        self.assertIsNone(wilson_interval(0,0))
        self.assertEqual(0.,wilson_interval(0,6)[0])
        self.assertEqual(1.,wilson_interval(6,6)[1])
        self.assertLess(wilson_interval(5,6)[0],5/6)
        for args in ((-1,5),(6,5),(1,-2),(1.2,5),(True,1)):
            with self.assertRaises(ValueError):
                wilson_interval(*args)

    def test_latency_percentiles_and_invalid_inputs(self):
        values=[float(x) for x in range(1,21)]
        s=_latency_summary(values)
        self.assertEqual((20,10.5,19.),(s["n"],s["median_ms"],
                                        s["p95_nearest_rank_ms"]))
        for bad in ([],[-1.],[float("nan")],[float("inf")],[1,2]):
            with self.assertRaises(PhotoBaselineError):
                _latency_summary(bad)

    def test_linux_host_process_memory(self):
        if platform.system()!="Linux":
            self.skipTest("Linux host only")
        self.assertGreater(host_rss_kib(),0)
        self.assertGreaterEqual(host_peak_rss_kib(),host_rss_kib())

if __name__=="__main__":
    unittest.main()
