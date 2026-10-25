"""F3-D regression tests: no real photos or model weights required."""
from __future__ import annotations
from collections import Counter
from dataclasses import replace
from urllib.error import URLError
import platform
import unittest

from microduck_companion.visual_photo_catalog import PHOTO_CATALOG, PublicPhoto
from microduck_companion.visual_photo_f3d_catalog import (
    CHALLENGE_CATALOG, EXPECTED_GROUPS, validate_challenge_catalog,
)
from microduck_companion.visual_photo_f3d_benchmark import (
    FROZEN_F3B_THRESHOLD, FROZEN_THRESHOLD_EVIDENCE, FETCH_TIMEOUT_S,
    _latency_summary, fetch_challenge_photo, host_rss_kib,
    host_peak_rss_kib, summarize_challenge, wilson_interval,
)
from microduck_companion.visual_photo_baseline import PhotoBaselineError
from microduck_companion.visual_photo_mobilenet_demo import classify_score


class FakeImage:
    def __init__(self,*,host="https://thumb.wikimedia.org/file.jpg",
                 mime="image/jpeg",data=None):
        self.url=host
        self.headers={"Content-Type":mime}
        self.data=data if data is not None else b"\xff\xd8"+bytes(256)+b"\xff\xd9"
    def geturl(self):return self.url
    def read(self,n):return self.data[:n]
    def __enter__(self):return self
    def __exit__(self,*args):return False


class ChallengeCatalogTests(unittest.TestCase):
    def test_source_count_groups_and_license(self):
        validate_challenge_catalog()
        self.assertEqual(28,len(CHALLENGE_CATALOG))
        self.assertEqual(EXPECTED_GROUPS,dict(Counter(x.group for x in CHALLENGE_CATALOG)))
        self.assertTrue(all(x.photo.license=="CC0-1.0" for x in CHALLENGE_CATALOG))
        self.assertTrue(all(x.photo.split=="test" for x in CHALLENGE_CATALOG))

    def test_no_author_or_filename_overlaps_prior_split(self):
        old_names={p.filename.casefold() for p in PHOTO_CATALOG}
        old_authors={p.author.casefold() for p in PHOTO_CATALOG}
        new_names={x.photo.filename.casefold() for x in CHALLENGE_CATALOG}
        new_authors={x.photo.author.casefold() for x in CHALLENGE_CATALOG}
        self.assertEqual((28,28),(len(new_names),len(new_authors)))
        self.assertFalse(old_names & new_names)
        self.assertFalse(old_authors & new_authors)

    def test_sources_use_public_commons_pages(self):
        for x in CHALLENGE_CATALOG:
            self.assertTrue(x.photo.file_page.startswith(
                "https://commons.wikimedia.org/wiki/File:"))
            self.assertTrue(x.photo.thumbnail_url.startswith(
                "https://commons.wikimedia.org/wiki/Special:FilePath/"))
            self.assertTrue(x.photo.thumbnail_url.endswith("?width=320"))

    def test_cross_split_author_or_image_duplicate_rejected(self):
        for field in ("author","filename"):
            first=CHALLENGE_CATALOG[0]
            bad=replace(first,photo=replace(
                first.photo, **{field:getattr(PHOTO_CATALOG[0],field)}))
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_challenge_catalog((bad,)+CHALLENGE_CATALOG[1:])

    def test_duplicate_within_challenge_rejected(self):
        for field in ("author","filename"):
            old=CHALLENGE_CATALOG[0].photo
            nextone=CHALLENGE_CATALOG[1]
            change=replace(nextone,photo=replace(
                nextone.photo,**{field:getattr(old,field)}))
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_challenge_catalog(CHALLENGE_CATALOG[:1]+(
                    change,)+CHALLENGE_CATALOG[2:])

    def test_non_cc0_wrong_label_split_and_path_rejected(self):
        original=CHALLENGE_CATALOG[0]
        for field,value in (
            ("license","CC-BY-SA"),("split","train"),
            ("category","person"),("filename","../outside.jpg")
        ):
            bad=replace(original,photo=replace(original.photo,**{field:value}))
            with self.subTest(field=field),self.assertRaises(ValueError):
                validate_challenge_catalog((bad,)+CHALLENGE_CATALOG[1:])

    def test_wrong_group_or_missing_sample_rejected(self):
        with self.assertRaises(ValueError):
            validate_challenge_catalog(CHALLENGE_CATALOG[:-1])
        bad=replace(CHALLENGE_CATALOG[-1],group="chair")
        with self.assertRaises(ValueError):
            validate_challenge_catalog(CHALLENGE_CATALOG[:-1]+(bad,))

    def test_fetch_rejects_non_catalog_source(self):
        arbitrary=PublicPhoto("arbitrary.jpg","unknown-author","cat","test")
        with self.assertRaises(PhotoBaselineError):
            fetch_challenge_photo(arbitrary,opener=lambda *_a,**_kw:None)


class ChallengeFetchTests(unittest.TestCase):
    def test_valid_jpeg_and_deadline(self):
        calls=[]
        def fake(request,*,timeout):
            calls.append((request.full_url,timeout,request.get_header("User-agent")))
            return FakeImage()
        data=fetch_challenge_photo(CHALLENGE_CATALOG[0].photo,opener=fake)
        self.assertTrue(data.startswith(b"\xff\xd8"))
        self.assertEqual(FETCH_TIMEOUT_S,calls[0][1])
        self.assertIn("MicroduckCompanion",calls[0][2])

    def test_bad_domain_mime_or_jpeg_rejected(self):
        for fake in (
            FakeImage(host="https://wrong.example/a.jpg"),
            FakeImage(host="http://thumb.wikimedia.org/a.jpg"),
            FakeImage(mime="text/html"),
            FakeImage(data=b"not image"*30),
            FakeImage(data=b"\xff\xd8"+bytes(1_200_001)+b"\xff\xd9"),
        ):
            with self.subTest(fake=fake),self.assertRaises(PhotoBaselineError):
                fetch_challenge_photo(CHALLENGE_CATALOG[0].photo,
                                      opener=lambda req,timeout:fake)

    def test_two_network_retries_then_fail_closed(self):
        calls=[]
        delays=[]
        def fail(req,*,timeout):
            calls.append(timeout)
            raise URLError("unavailable")
        with self.assertRaisesRegex(PhotoBaselineError,"no partial metric"):
            fetch_challenge_photo(CHALLENGE_CATALOG[0].photo,
                                  opener=fail,sleeper=delays.append)
        self.assertEqual([FETCH_TIMEOUT_S]*2,calls)
        self.assertEqual([1.],delays)

    def test_bad_mime_does_not_retry(self):
        calls=[]
        def fail(req,*,timeout):
            calls.append(timeout)
            return FakeImage(mime="text/html")
        with self.assertRaises(PhotoBaselineError):
            fetch_challenge_photo(CHALLENGE_CATALOG[0].photo,opener=fail)
        self.assertEqual(1,len(calls))


if __name__=="__main__":
    unittest.main()
