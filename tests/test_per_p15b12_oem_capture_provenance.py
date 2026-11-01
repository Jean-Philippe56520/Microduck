"""P15-B12: atomic source-only overlay gates; no camera, NPU or robot."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from scripts.per_p10a_apply_oem_rknn_overlay import PIN, SENTINEL
from scripts.per_p10b_apply_oem_tail_overlay import OverlayRefused
from scripts.per_p15b12_apply_oem_capture_provenance import PATCHES, apply


class CaptureProvenanceOverlayTests(unittest.TestCase):
    def _scratch(self, root: Path) -> dict[Path, str]:
        (root / SENTINEL).write_text(PIN + "\n", encoding="utf-8")
        original = {}
        for rel, changes in PATCHES.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            # Synthetically represent each exact pre-overlay source anchor once.
            contents = "\n// independent fixture anchor\n".join(old for old, _ in changes)
            path.write_text(contents, encoding="utf-8")
            original[path] = contents
        return original

    def test_positive_all_required_sources_and_replay_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            old = self._scratch(root)
            apply(root, root)
            for path, prior in old.items():
                self.assertNotEqual(path.read_text(), prior)
            pipeline = (root / "mediad/src/pipeline.rs").read_text()
            detect = (root / "mediad/src/detect.rs").read_text()
            local = (root / "mediad/src/local_detections.rs").read_text()
            self.assertIn("proto::clock::monotonic_ns()", pipeline)
            self.assertIn("sighting.captured_at_monotonic_ns = Some(capture_monotonic_ns)", detect)
            self.assertIn("sighting.captured_at_unix_us = capture_unix_us", detect)
            self.assertIn("sighting.look_seq = Some(look_seq)", detect)
            self.assertIn("MAX_CAPTURE_AGE_NS: u64 = 2_000_000_000", local)
            self.assertIn("if seq <= last_seq", local)
            self.assertIn("fn notification_at(", local)
            self.assertIn('serde_json::to_string(&value)', local)
            # No second camera frame request or new motor interface.
            self.assertNotIn("media.frame", local.split("#[cfg(test)]", 1)[0])
            self.assertNotIn("robot.do", local.split("#[cfg(test)]", 1)[0])
            with self.assertRaises(OverlayRefused):
                apply(root, root)

    def test_missing_pin_or_source_fail_before_any_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            old = self._scratch(root)
            (root / SENTINEL).write_text("not-pinned\n", encoding="utf-8")
            with self.assertRaises(OverlayRefused):
                apply(root, root)
            self.assertTrue(all(path.read_text() == value for path, value in old.items()))
            (root / SENTINEL).write_text(PIN + "\n", encoding="utf-8")
            broken = root / "mediad/src/local_detections.rs"
            broken.write_text(broken.read_text().replace("fn notification(sighting:", "fn broken("))
            before = {path: path.read_text() for path in old}
            with self.assertRaises(OverlayRefused):
                apply(root, root)
            self.assertTrue(all(path.read_text() == value for path, value in before.items()))

    def test_duplicate_and_symlink_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            old = self._scratch(root)
            target = root / "mediad/src/pipeline.rs"
            target.write_text(target.read_text() + "\n" + PATCHES["mediad/src/pipeline.rs"][0][0])
            before = {path: path.read_text() for path in old}
            with self.assertRaises(OverlayRefused):
                apply(root, root)
            self.assertTrue(all(path.read_text() == value for path, value in before.items()))
            target.unlink()
            target.symlink_to(root / "mediad/src/detect.rs")
            with self.assertRaises(OverlayRefused):
                apply(root, root)


if __name__ == "__main__":
    unittest.main()
