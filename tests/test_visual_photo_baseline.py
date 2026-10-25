"""F3-B: network-free tests for REAL-photo path; no fixture accuracy claims."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
import unittest
from urllib.error import URLError

from microduck_companion.visual_dataset import parse_visual_manifest
from microduck_companion.visual_photo_catalog import PHOTO_CATALOG, PublicPhoto
from microduck_companion.visual_photo_baseline import (
    DecisionThreshold, ImageFeature, PhotoBaselineError, Prediction,
    TinyRGBKNN, _check_jpeg_bytes, choose_threshold, classify,
    evaluate_holdout, fetch_thumbnail, rgb_features, sample_features,
    validate_catalog, validate_samples,
)
from microduck_companion.visual_photo_baseline_demo import _metadata_manifest


def pixels(r,g,b):
    return bytes([r,g,b]) * 256


def feature(c):
    if c=="cat":
        return rgb_features(pixels(8,20,225))
    if c=="dog":
        return rgb_features(pixels(220,20,5))
    if c=="unknown":
        return rgb_features(pixels(6,230,15))
    raise ValueError(c)


def synthetic_records():
    # Pure handcrafted feature fixtures; never a claim of tested photographs.
    return tuple(ImageFeature(
        p.category,p.split,p.author,
        hashlib.sha256(("fixture-"+p.filename).encode()).hexdigest(),
        feature(p.category))
        for p in PHOTO_CATALOG)


class FakeResponse:
    def __init__(self, *, url="https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/a.jpg",
                 content_type="image/jpeg", data=None):
        self.url = url
        self.headers = {"Content-Type":content_type}
        self.data = data if data is not None else b"\xff\xd8"+bytes(256)+b"\xff\xd9"
    def geturl(self): return self.url
    def read(self, size): return self.data[:size]
    def __enter__(self): return self
    def __exit__(self, *args): return False


class PublicCatalogTests(unittest.TestCase):
    def test_hand_curated_sources_have_distinct_authors_splits_and_cc0(self):
        validate_catalog()
        self.assertEqual(20,len(PHOTO_CATALOG))
        self.assertEqual(20,len({p.filename for p in PHOTO_CATALOG}))
        self.assertEqual(20,len({p.author for p in PHOTO_CATALOG}))
        self.assertEqual(8,sum(p.split=="train" for p in PHOTO_CATALOG))
        self.assertEqual(6,sum(p.split=="validation" for p in PHOTO_CATALOG))
        self.assertEqual(6,sum(p.split=="test" for p in PHOTO_CATALOG))
        self.assertTrue(all(p.license=="CC0-1.0" for p in PHOTO_CATALOG))
        self.assertTrue(all(p.file_page.startswith(
            "https://commons.wikimedia.org/wiki/File:")
            for p in PHOTO_CATALOG))
        self.assertEqual(0, sum(p.category=="unknown" and p.split=="train"
                                for p in PHOTO_CATALOG))
        self.assertEqual(2, sum(p.category=="unknown" and p.split=="test"
                                for p in PHOTO_CATALOG))

    def test_allowlisted_filepaths_are_not_arbitrary_network_urls(self):
        photo = PHOTO_CATALOG[0]
        self.assertEqual("Picture_of_cat.jpg",photo.filename)
        self.assertEqual(
            "https://commons.wikimedia.org/wiki/Special:FilePath/Picture_of_cat.jpg?width=320",
            photo.thumbnail_url)
        self.assertNotIn("?", photo.file_page)
        self.assertNotIn("upload.wikimedia.org", photo.file_page)

    def test_catalog_rejects_cross_split_author_even_when_photo_unique(self):
        changed=PHOTO_CATALOG[:-1]+(
            replace(PHOTO_CATALOG[-1],author=PHOTO_CATALOG[0].author),)
        with self.assertRaisesRegex(PhotoBaselineError,"leaks"):
            validate_catalog(changed)

    def test_catalog_rejects_non_cc0_and_relabelled_unknown_training(self):
        for bad in (
            replace(PHOTO_CATALOG[0],license="unknown"),
            replace(PHOTO_CATALOG[0],category="person"),
            replace(PHOTO_CATALOG[0],category="unknown"),
            replace(PHOTO_CATALOG[0],filename="../escape.jpg"),
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(PhotoBaselineError):
                    validate_catalog((bad,)+PHOTO_CATALOG[1:])

    def test_source_not_curated_cannot_be_downloaded(self):
        arbitrary=PublicPhoto("secret.jpg","someone","cat","train")
        with self.assertRaises(PhotoBaselineError):
            fetch_thumbnail(arbitrary,opener=lambda *_args,**_kwargs:None)

    def test_network_redirect_and_mime_type_are_fail_closed(self):
        for bad in (
            FakeResponse(url="https://malicious.example.com/a.jpg"),
            FakeResponse(url="http://upload.wikimedia.org/a.jpg"),
            FakeResponse(content_type="text/html"),
            FakeResponse(data=b"not an actual jpg"*10),
            FakeResponse(data=b"\xff\xd8"+bytes(1_200_001)+b"\xff\xd9"),
            FakeResponse(data=b"\xff\xd8"+bytes(2)+b"\xff\xd9"),
        ):
            with self.subTest(bad=bad), self.assertRaises(PhotoBaselineError):
                _check_jpeg_bytes(bad)

    def test_valid_jpeg_envelope_and_http_request_fields(self):
        received=[]
        def opener(request,*,timeout):
            received.append((request.full_url,timeout,
                             request.get_header("User-agent")))
            return FakeResponse()
        data=fetch_thumbnail(PHOTO_CATALOG[0],opener=opener)
        self.assertEqual(b"\xff\xd8",data[:2])
        self.assertEqual(1,len(received))
        self.assertEqual(10,received[0][1])
        self.assertIn("Microduck",received[0][2])

    def test_failed_download_retries_three_times_then_raises_no_score(self):
        calls=[]
        delays=[]
        def failure(req,*,timeout):
            calls.append(timeout)
            raise URLError("fixture failure")
        with self.assertRaisesRegex(PhotoBaselineError,"unavailable"):
            fetch_thumbnail(PHOTO_CATALOG[0],opener=failure,
                            sleeper=delays.append)
        self.assertEqual([10,10,10],calls)
        self.assertEqual([1.,2.],delays)

    def test_invalid_mime_does_not_retry(self):
        calls=[]
        def invalid(req,*,timeout):
            calls.append(1)
            return FakeResponse(content_type="text/html")
        with self.assertRaises(PhotoBaselineError):
            fetch_thumbnail(PHOTO_CATALOG[0],opener=invalid)
        self.assertEqual([1],calls)


class TinyModelTests(unittest.TestCase):
    def setUp(self):
        self.records=synthetic_records()
        self.train=tuple(s for s in self.records if s.split=="train")
        self.val=tuple(s for s in self.records if s.split=="validation")
        self.test=tuple(s for s in self.records if s.split=="test")
        self.model=TinyRGBKNN(self.train)

    def test_16x16_rgb_feature_shape_and_stability(self):
        for c in ("cat","dog","unknown"):
            v=feature(c)
            self.assertEqual(34,len(v))
            self.assertTrue(all(0 <= x <= 1 for x in v))
            self.assertEqual(v,feature(c))
        self.assertNotEqual(feature("cat"),feature("dog"))

    def test_bad_rgb_bytes_rejected(self):
        for invalid in (b"",bytes(767),bytes(769),bytearray(768)):
            with self.subTest(invalid=type(invalid)), self.assertRaises(PhotoBaselineError):
                rgb_features(invalid)

    def test_raw_features_different_classes_and_unknown_distance(self):
        cat=self.model.predict(feature("cat"))
        dog=self.model.predict(feature("dog"))
        strange=self.model.predict(feature("unknown"))
        self.assertEqual(("cat","dog"),(cat.category,dog.category))
        self.assertAlmostEqual(0.,cat.distance)
        self.assertAlmostEqual(0.,dog.distance)
        self.assertGreater(strange.distance,cat.distance)
        self.assertGreater(strange.distance,dog.distance)

    def test_threshold_freezes_using_validation_not_test(self):
        t=choose_threshold(self.model,self.val)
        self.assertGreaterEqual(t.vote_fraction,.5)
        self.assertGreater(t.maximum_distance,0.)
        scored=evaluate_holdout(self.model,self.test,t)
        self.assertEqual(6,scored.samples)
        self.assertEqual(2,scored.unknown_support)
        self.assertEqual(4,scored.known_support)
        self.assertEqual(0,scored.false_known_on_unknown)
        self.assertEqual(0,scored.samples-sum(n for _,_,n in scored.confusion))
        self.assertEqual(0,scored.samples-sum(s[1] for s in scored.per_class)-2)

    def test_holdout_refuses_validation_data(self):
        with self.assertRaisesRegex(PhotoBaselineError,"TEST"):
            evaluate_holdout(self.model,self.val,DecisionThreshold(.5,1.))

    def test_threshold_refuses_test_data(self):
        with self.assertRaises(PhotoBaselineError):
            choose_threshold(self.model,self.test)

    def test_strict_rejection_is_unknown_not_a_false_cat_label(self):
        self.assertEqual("unknown",classify(
            Prediction("cat",.45,.1),DecisionThreshold(.5,1.)))
        self.assertEqual("unknown",classify(
            Prediction("dog",.95,.7),DecisionThreshold(.5,.2)))
        self.assertEqual("dog",classify(
            Prediction("dog",.95,.1),DecisionThreshold(.5,.2)))

    def test_nonfinite_features_are_rejected(self):
        bad=list(feature("dog"))
        bad[0]=float("nan")
        with self.assertRaises(PhotoBaselineError):
            self.model.predict(tuple(bad))

    def test_invalid_training_category_rejected(self):
        with self.assertRaises(PhotoBaselineError):
            TinyRGBKNN(self.test)
        with self.assertRaises(PhotoBaselineError):
            TinyRGBKNN(())

    def test_sample_features_stores_only_digest_not_raw_bytes(self):
        payload=b"fictional-image-token"
        result=sample_features(
            PHOTO_CATALOG[0],payload,extractor=lambda _:feature("cat"))
        self.assertEqual(hashlib.sha256(payload).hexdigest(),
                         result.content_sha256)
        self.assertEqual(34,len(result.values))
        self.assertEqual("cat",result.category)
        self.assertNotIn("fictional-image-token",str(result))

    def test_sample_features_refuses_nonfinite_or_nonfloat_values(self):
        for value in ((1,),(float("nan"),),(float("inf"),)):
            with self.subTest(value=value),self.assertRaises(PhotoBaselineError):
                sample_features(PHOTO_CATALOG[0],b"x",
                                extractor=lambda _data:value)

    def test_f3a_manifest_accepts_external_only_with_explicit_opt_in(self):
        manifest=_metadata_manifest(self.records)
        with self.assertRaises(Exception):
            parse_visual_manifest(manifest)
        dataset=parse_visual_manifest(manifest,allow_external=True)
        self.assertFalse(dataset.synthetic_only)
        self.assertEqual(20,len(dataset.samples))
        self.assertEqual(6,len(dataset.partition("test")))
        self.assertEqual(20,len({s.group_id for s in dataset.samples}))
        self.assertNotIn("Malo",manifest)
        self.assertNotIn("Nessquick",manifest)
        self.assertNotIn("Kitty",manifest)
        self.assertNotIn("image_path",manifest)
        self.assertNotIn("image_bytes",manifest)

    def test_incomplete_or_duplicate_real_features_rejected(self):
        with self.assertRaisesRegex(PhotoBaselineError,"incomplete"):
            validate_samples(self.records[:-1])
        duplicate=replace(self.records[-1],
                          content_sha256=self.records[0].content_sha256)
        with self.assertRaises(PhotoBaselineError):
            validate_samples(self.records[:-1]+(duplicate,))
        validate_samples(self.records)

    def test_bogus_split_label_or_malformed_feature_rejected(self):
        bad=replace(self.records[-1],split="train")
        with self.assertRaises(PhotoBaselineError):
            validate_samples(self.records[:-1]+(bad,))
        short=replace(self.records[-1],values=self.records[-1].values[:10])
        with self.assertRaises(PhotoBaselineError):
            validate_samples(self.records[:-1]+(short,))

    def test_metrics_report_real_scoring_math_on_fixture_values_only(self):
        limits=DecisionThreshold(.5,1.)
        output=evaluate_holdout(self.model,self.test,limits)
        self.assertEqual(6,output.samples)
        self.assertEqual(2,output.unknown_support)
        self.assertEqual(0.,output.unknown_recall)
        self.assertGreaterEqual(output.accuracy,0.)
        self.assertLessEqual(output.accuracy,1.)
        self.assertEqual({"cat","dog"},{x[0] for x in output.per_class})
        self.assertEqual(2,output.false_known_on_unknown)

    def test_f3a_manifest_traces_exact_content_digest(self):
        manifest=json.loads(_metadata_manifest(self.records))
        self.assertEqual({r.content_sha256 for r in self.records},
                         {x["fingerprint_sha256"] for x in manifest["samples"]})
        self.assertEqual("licensed_external",
                         manifest["samples"][0]["source_kind"])


if __name__=="__main__":
    unittest.main()
