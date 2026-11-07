"""B2: host-only exact UYVY frame <-> MuJoCo geom-ID sidecar, never F2 input.

This evaluates an explicitly instrumented simulator; the OEM on-robot frame
protocol does not expose camera pose, step or truth. Sidecars contain NO pixels.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import stat

SCHEMA = 1
MAX_BYTES = 1_500_000
MAX_RECORDS = 1000
SHA = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = frozenset({
    "schema", "case", "render_seq", "sim_time_s", "uyvy_sha256",
    "width", "height", "rotation_degrees", "ball_geom_id",
    "ball_visible_pixels", "ball_bbox_upright_xyxy",
    "qpos_sha256", "camera_pos_xyz", "camera_mat9", "render_ms",
})


class B2GTError(ValueError):
    """Fail closed; never promote an unpaired image or pixel GT."""


def _json_pairs(pairs):
    record = {}
    for k, v in pairs:
        if k in record:
            raise B2GTError("duplicate JSON key")
        record[k] = v
    return record


def _bad_number(text):
    raise B2GTError("non-finite JSON number")


def _real(v, *, low=-1e9, high=1e9):
    return type(v) in (int, float) and math.isfinite(v) and low <= v <= high


def validate_record(r: dict, case: str) -> None:
    if (type(r) is not dict or set(r) != FIELDS or r["schema"] != SCHEMA
            or r["case"] != case or type(r["render_seq"]) is not int
            or r["render_seq"] < 1 or not _real(r["sim_time_s"], low=0)
            or type(r["uyvy_sha256"]) is not str or not SHA.fullmatch(r["uyvy_sha256"])
            or r["width"] != 640 or r["height"] != 360
            or r["rotation_degrees"] != 90
            or type(r["qpos_sha256"]) is not str or not SHA.fullmatch(r["qpos_sha256"])
            or not _real(r["render_ms"], low=0, high=1000)
            or type(r["camera_pos_xyz"]) is not list or len(r["camera_pos_xyz"]) != 3
            or not all(_real(x) for x in r["camera_pos_xyz"])
            or type(r["camera_mat9"]) is not list or len(r["camera_mat9"]) != 9
            or not all(_real(x, low=-1.001, high=1.001) for x in r["camera_mat9"])):
        raise B2GTError("bad sidecar schema, provenance or pose")
    if type(r["ball_visible_pixels"]) is not int or not 0 <= r["ball_visible_pixels"] <= 640 * 360:
        raise B2GTError("bad geom pixels")
    bounds = r["ball_bbox_upright_xyxy"]
    if case == "ball":
        if type(r["ball_geom_id"]) is not int or r["ball_geom_id"] < 0:
            raise B2GTError("no ball geom ID")
        if r["ball_visible_pixels"] == 0 and bounds is not None:
            raise B2GTError("inconsistent absent mask")
        if r["ball_visible_pixels"] > 0:
            if (type(bounds) is not list or len(bounds) != 4
                    or any(type(x) is not int for x in bounds)
                    or not (0 <= bounds[0] < bounds[2] <= 360
                            and 0 <= bounds[1] < bounds[3] <= 640)
                    or r["ball_visible_pixels"] > (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])):
                raise B2GTError("invalid segmentation bbox")
    elif case == "empty":
        if (r["ball_geom_id"] is not None or r["ball_visible_pixels"] != 0
                or bounds is not None):
            raise B2GTError("empty scene contains a ball mask")
    else:
        raise B2GTError("unknown case")


def read_sidecar(path: Path, *, case: str) -> list[dict]:
    if type(path) is not Path or case not in ("ball", "empty"):
        raise B2GTError("invalid sidecar request")
    meta = path.lstat()
    if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= MAX_BYTES:
        raise B2GTError("sidecar unavailable or oversized")
    raw = path.read_bytes()
    if len(raw) != meta.st_size or not raw.endswith(b"\n"):
        raise B2GTError("torn or changed sidecar")
    lines = raw.splitlines()
    if not 0 < len(lines) <= MAX_RECORDS:
        raise B2GTError("bad sidecar length")
    rows = []
    seen_hashes = set()
    previous_seq, previous_time = 0, -1.0
    for line in lines:
        try:
            r = json.loads(line.decode("ascii"), object_pairs_hook=_json_pairs,
                           parse_constant=_bad_number)
        except (UnicodeError, json.JSONDecodeError) as e:
            raise B2GTError("bad sidecar JSON") from e
        validate_record(r, case)
        if (r["uyvy_sha256"] in seen_hashes
                or r["render_seq"] <= previous_seq
                or r["sim_time_s"] <= previous_time):
            raise B2GTError("ambiguous hash or non-monotonic render sequence")
        seen_hashes.add(r["uyvy_sha256"])
        previous_seq, previous_time = r["render_seq"], r["sim_time_s"]
        rows.append(r)
    return rows


def match_frame(rows: list[dict], pixels_uyvy: bytes, *, case: str) -> dict:
    """Require one exact byte match; NEVER send the answer to production F2."""
    if (type(rows) is not list or not rows or type(pixels_uyvy) is not bytes
            or len(pixels_uyvy) != 640 * 360 * 2):
        raise B2GTError("invalid UYVY evidence")
    target = hashlib.sha256(pixels_uyvy).hexdigest()
    matched = [r for r in rows if r.get("uyvy_sha256") == target]
    if len(matched) != 1:
        raise B2GTError("frame missing or ambiguously matched")
    record = matched[0]
    validate_record(record, case)
    return record
