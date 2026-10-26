"""R2-B+1: bounded read-only HTTP Range sampling of licensed DCASE2020 ZIPs.

Never downloads an entire archive or commits/publishes audio. Uses the
existing ToyADMOS local adapter and R2-B evaluator, in a temporary directory.
A successful pilot on these start-to-stop recordings is NOT evidence of
different recording days/rooms/microphones or a reliable home sound recognizer.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import io
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.parse
import urllib.request
import wave
import zipfile

from .r2b1_toyadmos_local import (
    DATASET_DOI, FAMILIES, MAX_INPUT_BYTES, ORIGINAL_RE, prepare,
)
from .r2b_independent_capture_eval import R2BEvidenceError, run_audio_manifest

# Zenodo: https://zenodo.org/records/3678171; archive MD5 published there.
OFFICIAL_ARCHIVES = {
    "ToyCar": ("dev_data_ToyCar.zip", "4dec75ca8d9f666aa9e4c1894a740501"),
    "ToyConveyor": ("dev_data_ToyConveyor.zip", "03b6aa1bfd09a39d53af0ba39f71fa91"),
}
RECORD_URL = "https://zenodo.org/records/3678171/files/{file}?download=1"
CHUNK = 256 * 1024
MAX_READ = 5 * 1024 * 1024
MAX_TRANSFER = 16 * 1024 * 1024  # per archive, including ZIP directory
MAX_ARCHIVE = 2_200_000_000
MAX_REQUESTS = 180
RANGE_HEADER = re.compile(r"bytes (\d+)-(\d+)/(\d+)\Z", re.ASCII)


class BoundedRangeReader:
    """Seekable read-only byte-range stream for ZipFile; fail on HTTP 200."""

    def __init__(self, url: str, *, opener=None):
        parsed = urllib.parse.urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != "zenodo.org"
                or not parsed.path.startswith("/records/3678171/files/")
                or not parsed.path.endswith(".zip")
                or parsed.username or parsed.password):
            raise R2BEvidenceError("official Zenodo HTTPS source required")
        self.url = url
        self._open = opener or urllib.request.urlopen
        self.size = None
        self.position = 0
        self.transferred = 0
        self.requests = 0
        self._cache_no = -1
        self._cache = b""
        self._fetch(0, 0)
        if not self.size or not 1 <= self.size <= MAX_ARCHIVE:
            raise R2BEvidenceError("invalid or unbounded official archive size")

    def _fetch(self, start: int, end: int) -> bytes:
        if (type(start) is not int or type(end) is not int
                or start < 0 or end < start or self.requests >= MAX_REQUESTS
                or self.transferred + end - start + 1 > MAX_TRANSFER):
            raise R2BEvidenceError("out-of-bounds HTTP Range budget")
        req = urllib.request.Request(
            self.url,
            headers={"Range": f"bytes={start}-{end}",
                     "User-Agent": "Microduck-Companion-R2B1/1"},
        )
        self.requests += 1
        try:
            with self._open(req, timeout=25) as response:
                hdr = response.headers.get("Content-Range", "")
                match = RANGE_HEADER.fullmatch(hdr)
                if response.status != 206 or match is None:
                    raise R2BEvidenceError("server refused strict HTTP 206 range")
                received_start, received_end, total = map(int, match.groups())
                if (received_start != start or received_end != end
                        or not 1 <= total <= MAX_ARCHIVE
                        or (self.size is not None and total != self.size)):
                    raise R2BEvidenceError("inconsistent or unsafe remote range")
                final_url = urllib.parse.urlsplit(response.url)
                if final_url.scheme != "https" or final_url.hostname != "zenodo.org":
                    raise R2BEvidenceError("unexpected archive redirect")
                raw = response.read(end - start + 2)
        except (OSError, TimeoutError) as exc:
            raise R2BEvidenceError("archive range download failed") from exc
        if len(raw) != end - start + 1:
            raise R2BEvidenceError("short or excessive remote byte range")
        self.size = total
        self.transferred += len(raw)
        return raw

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = 0) -> int:
        if type(offset) is not int or whence not in (0, 1, 2):
            raise R2BEvidenceError("invalid ZIP stream seek")
        position = ((offset if whence == 0 else self.position + offset)
                    if whence != 2 else self.size + offset)
        if not 0 <= position <= self.size:
            raise R2BEvidenceError("ZIP seek outside bounded archive")
        self.position = position
        return position

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = self.size - self.position
        if type(size) is not int or size > MAX_READ:
            raise R2BEvidenceError("unbounded ZIP stream read forbidden")
        result = bytearray()
        while size and self.position < self.size:
            block = self.position // CHUNK
            if block != self._cache_no:
                start = block * CHUNK
                end = min(start + CHUNK, self.size) - 1
                self._cache = self._fetch(start, end)
                self._cache_no = block
            offset = self.position % CHUNK
            n = min(size, len(self._cache) - offset)
            if n <= 0:
                raise R2BEvidenceError("invalid range block")
            result.extend(self._cache[offset:offset+n])
            self.position += n
            size -= n
        return bytes(result)


def _selected_wavs(zf: zipfile.ZipFile, family: str) -> dict[str, bytes]:
    candidates = {}
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        parts = name.split("/")
        if len(parts) == 4 and parts[0] == "dev_data":
            parts = parts[1:]
        if (len(parts) != 3 or parts[0] != family
                or parts[1] not in ("train", "test")):
            continue
        match = ORIGINAL_RE.fullmatch(parts[2])
        if match is None:
            continue
        if (info.is_dir() or info.flag_bits & 1
                or info.file_size > MAX_INPUT_BYTES
                or info.compress_size > MAX_INPUT_BYTES
                or not 1 <= info.file_size):
            raise R2BEvidenceError("unsafe or oversized selected ZIP member")
        key = (parts[1], match[1])
        candidates.setdefault(key, []).append(info)
    ids = sorted({mid for split, mid in candidates if split == "train"}
                 & {mid for split, mid in candidates if split == "test"})
    if len(ids) < 3:
        raise R2BEvidenceError("official ZIP lacks 3 individual train/test IDs")
    selected = {}
    for index, mid in enumerate(ids[:3]):
        splits = ("train", "test") if index < 2 else ("test",)
        for split in splits:
            choices = sorted(candidates[(split, mid)], key=lambda x: x.filename)
            info = choices[0]  # Deterministic first clip; never select on scores.
            with zf.open(info) as input_file:
                raw = input_file.read(MAX_INPUT_BYTES + 1)
            if len(raw) != info.file_size or len(raw) > MAX_INPUT_BYTES:
                raise R2BEvidenceError("ZIP member rejected by bounded size")
            selected[f"{family}/{split}/{info.filename.rsplit('/', 1)[-1]}"] = raw
    return selected


def run_remote_pilot(*, license_reviewed: bool,
                     independent_operations_reviewed: bool,
                     opener=None) -> dict:
    if license_reviewed is not True or independent_operations_reviewed is not True:
        raise R2BEvidenceError("manual noncommercial license and operation review required")
    with tempfile.TemporaryDirectory(prefix="r2b1-dcase-") as folder:
        root = Path(folder)
        dataset_root = root / "dataset"
        derived_root = root / "derived"
        manifest = root / "ledger.json"
        selected_counts = {}
        range_metrics = {}
        for family, _, _ in FAMILIES:
            basename, published_md5 = OFFICIAL_ARCHIVES[family]
            source = BoundedRangeReader(
                RECORD_URL.format(file=basename), opener=opener)
            with zipfile.ZipFile(source) as zf:
                subset = _selected_wavs(zf, family)
            selected_counts[family] = len(subset)
            range_metrics[family] = {
                "http_range_bytes": source.transferred,
                "http_range_calls": source.requests,
                "archive_size_bytes": source.size,
                "official_full_archive_md5_not_reverified": published_md5,
                "zip_member_crc_checked": True,
            }
            for name, data in subset.items():
                dest = dataset_root / "dev_data" / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                with dest.open("xb") as output:
                    output.write(data)
        prepared = prepare(
            dataset_root, derived_root, manifest,
            reviewed_noncommercial_rights=True,
            reviewed_individual_operations=True,
        )
        benchmark = run_audio_manifest(manifest, derived_root)
        return {
            "study": "R2-B+1 DCASE2020 ToyADMOS IND pilot",
            "reference": DATASET_DOI,
            "licensed_research_noncommercial": True,
            "individual_machine_ids_separated": True,
            "independent_operation_files": True,
            "distinct_recording_dates_or_microphones_verified": False,
            "reference_clip_picking": "first_normal_clip_by_sorted_zip_path",
            "cropping": "center_one_second_no_model_tuning",
            "source_count": 6,
            "selected_original_file_count": sum(selected_counts.values()),
            "per_family_original_files": selected_counts,
            "remote_range_probe": range_metrics,
            "private_output_not_persisted": True,
            "hardware_validation": False,
            "preparation": prepared,
            "benchmark": benchmark,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-cc-by-nc-sa-noncommercial",
                        action="store_true")
    parser.add_argument("--reviewed-original-operation-provenance",
                        action="store_true")
    args = parser.parse_args(argv)
    result = run_remote_pilot(
        license_reviewed=args.reviewed_cc_by_nc_sa_noncommercial,
        independent_operations_reviewed=args.reviewed_original_operation_provenance,
    )
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
