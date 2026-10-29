"""Public image smoke assets: keep the source bytes and labels intact."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent / "assets" / "public_vision_smoke"
ALLOWED = {"cat", "dog", "sports_ball", "chair", "person", "unknown"}


def _valid_image(data: bytes, name: str) -> bool:
    if name.endswith(".jpg"):
        return data.startswith(b"\xff\xd8\xff") and len(data) > 1024
    if name.endswith(".png"):
        return data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) > 1024
    return False


def test_public_images_match_pinned_source_git_blobs():
    rows = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["images"]
    assert len(rows) == 13
    names = [row["file"] for row in rows]
    assert len(set(names)) == len(names)
    for row in rows:
        name = row["file"]
        assert name == Path(name).name and row["category"] in ALLOWED
        assert row["source_url"].startswith("https://github.com/")
        assert row["origin_url"].startswith("https://")
        content = (ROOT / name).read_bytes()
        assert _valid_image(content, name)
        header = f"blob {len(content)}\0".encode()
        assert hashlib.sha1(header + content).hexdigest() == row["source_git_blob_sha"]


def test_public_image_validator_rejects_corruption():
    assert not _valid_image(b"not a jpeg", "cat_01.jpg")
    assert not _valid_image(b"not a png", "ball_02.png")
    assert not _valid_image(b"\xff\xd8\xff", "cat_01.jpg")
