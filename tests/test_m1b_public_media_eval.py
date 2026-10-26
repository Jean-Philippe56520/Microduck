"""M1-B public-media benchmark safety tests. NO download is made by tests."""
from __future__ import annotations
from unittest.mock import patch
import unittest

from microduck_companion.m1b_public_media_eval import (
    PHOTO_NAMES,PUBLIC_SOUNDS,commons_audio_url,
    decoded_loudest_pcm,load_cc0_ogg,main,
)
from microduck_companion.visual_photo_catalog import PHOTO_CATALOG


class FakeResponse:
    def __init__(self,*,url,body=b"OggS"+b"A"*1000,content_type="audio/ogg"):
        self.url,self.body,self.headers=url,body,{"Content-Type":content_type}
    def geturl(self):return self.url
    def read(self,length):return self.body[:length]
    def __enter__(self):return self
    def __exit__(self,*args):return False


class CuratedPublicStudyTests(unittest.TestCase):
    def test_no_network_without_explicit_flag(self):
        with self.assertRaises(SystemExit) as cm:
            main([])
        self.assertEqual(2,cm.exception.code)

    def test_public_images_are_only_existing_cc0_validation_photos(self):
        manifest={p.filename:p for p in PHOTO_CATALOG}
        self.assertEqual(6,len(PHOTO_NAMES))
        self.assertEqual(6,len(set(PHOTO_NAMES)))
        for filename in PHOTO_NAMES:
            with self.subTest(filename=filename):
                self.assertEqual("CC0-1.0",manifest[filename].license)
                self.assertEqual("validation",manifest[filename].split)
                self.assertIn(manifest[filename].category,
                              ("cat","dog","unknown"))

    def test_public_audio_sources_are_curated_non_voice_commons_pages(self):
        self.assertEqual(2,len(PUBLIC_SOUNDS))
        self.assertEqual({"knock","ambient"},
                         {label for _,label,_ in PUBLIC_SOUNDS})
        for filename,kind,url in PUBLIC_SOUNDS:
            self.assertIn("commons.wikimedia.org/wiki/File:",url)
            result=commons_audio_url(filename)
            self.assertTrue(result.startswith(
                "https://upload.wikimedia.org/wikipedia/commons/"))
            self.assertTrue(result.endswith(".ogg"))
        with self.assertRaises(ValueError):
            commons_audio_url("private_meeting.ogg")
        with self.assertRaises(ValueError):
            commons_audio_url("../Door_knocker_audio.ogg")

    def test_bounded_audio_fetch_denies_redirects_non_ogg_or_oversize(self):
        valid=PUBLIC_SOUNDS[0][0]
        url=commons_audio_url(valid)
        with patch("microduck_companion.m1b_public_media_eval.urlopen"):
            pass
        for sample in (
            FakeResponse(url="https://evil.example/sound.ogg"),
            FakeResponse(url="http://upload.wikimedia.org/1.ogg"),
            FakeResponse(url=url,content_type="text/html"),
            FakeResponse(url=url,body=b"ID3"+b"A"*1000),
            FakeResponse(url=url,body=b"OggS"+b"A"*250000),
            FakeResponse(url=url,body=b"OggS"+b"A"*10),
        ):
            with self.subTest(sample=(sample.url,len(sample.body))):
                with self.assertRaises(ValueError):
                    load_cc0_ogg(valid,opener=lambda request,timeout:sample)
        accepted=load_cc0_ogg(valid,opener=lambda request,timeout:
                              FakeResponse(url=url))
        self.assertEqual(1004,len(accepted))

    def test_bounded_decoder_refuses_invalid_payload(self):
        for sample in (b"",b"RIFF"+b"\x00"*60,b"OggS"+b"A"*200001):
            with self.subTest(size=len(sample)),self.assertRaises(ValueError):
                decoded_loudest_pcm(sample)


if __name__=="__main__":
    unittest.main()
