"""B2-E1: UYVY frame <-> MuJoCo pose sidecar (GT replay AFTER robotd stops).

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

SCHEMA = 2
MAX_BYTES = 1_500_000
MAX_RECORDS = 1000
SHA = re.compile(r"[0-9a-f]{64}\Z")
FIELDS = frozenset({
    "schema", "case", "scene_xml", "render_seq", "sim_time_s", "uyvy_sha256",
    "width", "height", "rotation_degrees", "ball_geom_id",
    "qpos", "qvel", "qpos_sha256", "camera_pos_xyz", "camera_mat9", "render_ms",
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
    """Exact typed schema: do not trust sidecar metadata as sensor evidence."""
    if type(r) is not dict or set(r) != FIELDS or case not in ("ball", "empty"):
        raise B2GTError("bad sidecar structure")
    if (type(r["schema"]) is not int or r["schema"] != SCHEMA
            or type(r["case"]) is not str or r["case"] != case
            or r["scene_xml"] != ("scene_ball.xml" if case == "ball" else "scene.xml")
            or type(r["render_seq"]) is not int or r["render_seq"] < 1
            or not _real(r["sim_time_s"], low=0)
            or type(r["uyvy_sha256"]) is not str or not SHA.fullmatch(r["uyvy_sha256"])
            or type(r["width"]) is not int or r["width"] != 640
            or type(r["height"]) is not int or r["height"] != 360
            or type(r["rotation_degrees"]) is not int or r["rotation_degrees"] != 90
            or type(r["qpos_sha256"]) is not str or not SHA.fullmatch(r["qpos_sha256"])
            or not _real(r["render_ms"], low=0, high=1000)
            or type(r["camera_pos_xyz"]) is not list or len(r["camera_pos_xyz"]) != 3
            or not all(_real(x) for x in r["camera_pos_xyz"])
            or type(r["camera_mat9"]) is not list or len(r["camera_mat9"]) != 9
            or not all(_real(x, low=-1.001, high=1.001) for x in r["camera_mat9"])):
        raise B2GTError("bad sidecar fields or pose")
    if (case == "ball" and (type(r["ball_geom_id"]) is not int
                           or r["ball_geom_id"] < 0)
            or case == "empty" and r["ball_geom_id"] is not None):
        raise B2GTError("ball geom not consistent with scene")
    for label in ("qpos", "qvel"):
        values = r[label]
        if type(values) is not list or not 1 <= len(values) <= 128:
            raise B2GTError("bad state vector length")
        if not all(_real(x) for x in values):
            raise B2GTError("nonfinite state vector")


def read_sidecar(path: Path, *, case: str) -> list[dict]:
    if not isinstance(path, Path) or case not in ("ball", "empty"):
        raise B2GTError("invalid sidecar request")
    # Read a bounded prefix from one no-follow fd as the camera appends.
    # This avoids a spurious change while path.read_bytes() races an append.
    import os
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise B2GTError("sidecar missing or unsafe") from exc
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= MAX_BYTES:
            raise B2GTError("sidecar unavailable or oversized")
        raw = os.read(fd, meta.st_size)
    finally:
        os.close(fd)
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
