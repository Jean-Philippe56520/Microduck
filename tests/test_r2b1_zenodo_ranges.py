"""No Internet or original audio in these tests: artificial ZIP range fixtures."""
from __future__ import annotations

import hashlib
import io
import math
import re
import struct
import unittest
import urllib.request
import wave
import zipfile

from microduck_companion.r2b1_zenodo_ranges import (
    BoundedRangeReader, FAMILIES, OFFICIAL_ARCHIVES,
    RECORD_URL, _selected_wavs, run_remote_pilot,
)
from microduck_companion.r2b_independent_capture_eval import R2BEvidenceError


def _tone(value):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(16_000)
        freq = 180 + value
        samples = (round(2600 * math.sin(2 * math.pi * freq * i / 16_000))
                   for i in range(16_000))
        block = struct.pack("<16000h", *samples)
        file.writeframes(block * 10)
    return buffer.getvalue()


def _zip_fixture(family, *, unsafe=False):
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for m in range(1, 4):
            for split in ("train", "test"):
                name = f"dev_data/{family}/{split}/normal_id_{m:02d}_00000000.wav"
                zf.writestr(name, _tone(m*53+(split=="test")*5+
                                       (family=="ToyConveyor")*200))
        if unsafe:
            zf.writestr(f"dev_data/{family}/train/normal_id_04_00000000.wav",
                        b"\0"*1_100_000)
    return memory.getvalue()


class _Response(io.BytesIO):
    def __init__(self, content, url, start, end, status=206):
        super().__init__(content[start:end+1])
        self.status = status
        self.url = url
        self.headers = {
            "Content-Range": f"bytes {start}-{end}/{len(content)}",
            "Content-Length": str(end-start+1),
        }


class FakeZenodo:
    def __init__(self):
        self.archives = {
            family: _zip_fixture(family) for family, _, _ in FAMILIES
        }
        self.calls = 0

    def __call__(self, request, timeout=25):
        self.calls += 1
        url = request.full_url
        family = next((family for family, (name, _) in OFFICIAL_ARCHIVES.items()
                       if name in url), None)
        if family is None:
            raise AssertionError("unapproved URL")
        match = re.fullmatch(r"bytes=(\d+)-(\d+)",
                             request.get_header("Range"))
        if match is None:
            raise AssertionError("unbounded request")
        start, end = int(match[1]), int(match[2])
        blob = self.archives[family]
        if not 0 <= start <= end < len(blob):
            raise AssertionError("out-of-bounds request")
        return _Response(blob, url, start, end)


class R2B1RemoteZipFixtureTests(unittest.TestCase):
    def test_selective_zip_reads_and_existing_audio_runner(self):
        client = FakeZenodo()
        result = run_remote_pilot(
            license_reviewed=True,
            independent_operations_reviewed=True, opener=client,
        )
        self.assertEqual(6, result["source_count"])
        self.assertEqual(12, result["selected_original_file_count"])
        self.assertEqual(10, result["clips_evaluated"])
        self.assertEqual(10, result["benchmark"]["manifest_entries"])
        self.assertEqual("declared_not_authenticated",
                         result["benchmark"]["rights_and_source_independence"])
        self.assertEqual(2, result["benchmark"]["candidates"]["legacy"]["test"]["known_queries"])
        self.assertEqual(1, result["benchmark"]["candidates"]["legacy"]["test"]["unknown_queries"])
        self.assertFalse(result["hardware_validation"])
        self.assertFalse(result["distinct_recording_dates_or_microphones_verified"])
        self.assertGreater(client.calls, 2)
        for metric in result["remote_range_probe"].values():
            self.assertLess(metric["http_range_bytes"], 16_000_000)
            self.assertTrue(metric["zip_member_crc_checked"])

    def test_fail_closed_on_missing_rights_or_unknown_url(self):
        client = FakeZenodo()
        with self.assertRaisesRegex(R2BEvidenceError, "license"):
            run_remote_pilot(
                license_reviewed=False,
                independent_operations_reviewed=True,
                opener=client,
            )
        self.assertEqual(0, client.calls)
        with self.assertRaisesRegex(R2BEvidenceError, "official Zenodo"):
            BoundedRangeReader("https://attacker.example.org/big.zip", opener=client)

    def test_reject_http_200_even_if_bytes_are_small(self):
        client = FakeZenodo()
        def bogus(req, timeout=25):
            r = client(req, timeout)
            r.status = 200
            return r
        with self.assertRaisesRegex(R2BEvidenceError, "strict HTTP 206"):
            BoundedRangeReader(
                RECORD_URL.format(file="dev_data_ToyCar.zip"), opener=bogus)

    def test_seek_outside_archive_and_unbounded_read(self):
        client = FakeZenodo()
        stream = BoundedRangeReader(
            RECORD_URL.format(file="dev_data_ToyCar.zip"), opener=client)
        with self.assertRaisesRegex(R2BEvidenceError, "seek"):
            stream.seek(stream.size + 1)
        with self.assertRaisesRegex(R2BEvidenceError, "unbounded"):
            stream.read(6 * 1024 * 1024)

    def test_missing_individual_id_fails_corpus_gate(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zf:
            for mid in ("01", "02"):
                for split in ("train", "test"):
                    zf.writestr(
                        f"ToyCar/{split}/normal_id_{mid}_00000000.wav",
                        _tone(200+int(mid)))
        with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as zf:
            with self.assertRaisesRegex(R2BEvidenceError, "3 individual"):
                _selected_wavs(zf, "ToyCar")


if __name__ == "__main__":
    unittest.main()
