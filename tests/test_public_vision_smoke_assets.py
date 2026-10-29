"""Integrity checks for public visual smoke fixtures used by Kwipi."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).parent / "assets" / "public_vision_smoke"
ALLOWED = {"cat", "dog", "sports_ball", "chair", "person", "unknown"}


def _valid_image(data: bytes, name: str) -> bool:
    if name.endswith(".jpg"):
        return data.startswith(b"\xff\xd8\xff") and len(data) > 1024
    if name.endswith(".png"):
        return data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) > 1024
    return False


class PublicVisionSmokeAssetTests(unittest.TestCase):
    def test_public_images_match_pinned_source_git_blobs(self):
        rows = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))["images"]
        self.assertEqual(len(rows), 13)
        names = [row["file"] for row in rows]
        self.assertEqual(len(set(names)), len(names))
        for row in rows:
            name = row["file"]
            with self.subTest(name=name):
                self.assertEqual(name, Path(name).name)
                self.assertIn(row["category"], ALLOWED)
                self.assertTrue(row["source_url"].startswith("https://github.com/"))
                self.assertTrue(row["origin_url"].startswith("https://"))
                payload = (ROOT / name).read_bytes()
                self.assertTrue(_valid_image(payload, name))
                git_header = f"blob {len(payload)}\0".encode()
                self.assertEqual(
                    hashlib.sha1(git_header + payload).hexdigest(),
                    row["source_git_blob_sha"],
                )

    def test_public_image_validator_rejects_corruption(self):
        self.assertFalse(_valid_image(b"not a jpeg", "cat_01.jpg"))
        self.assertFalse(_valid_image(b"not a png", "ball_02.png"))
        self.assertFalse(_valid_image(b"\xff\xd8\xff", "cat_01.jpg"))


if __name__ == "__main__":
    unittest.main()
