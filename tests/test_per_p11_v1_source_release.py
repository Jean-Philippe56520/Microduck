"""P11 source artifact: deterministic positive and fail-closed negative cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from scripts.per_p11_v1_source_release import (
    ARCHIVE_NAME, MANIFEST_NAME, OEM_ONNX_PATHS, PIN, RL_PIN,
    ReleaseRefused, drop_test_harness, manifest_for,
    no_models_or_harness, safe_member, verify_archive, write_tar,
)


class P11V1SourceTests(unittest.TestCase):
    def _minimum(self, root: Path) -> None:
        for name, content in {
            "Cargo.toml": '[workspace]\nmembers = ["mediad", "xtask"]\n',
            "Cargo.lock": '[[package]]\nname = "kwipi-seg-mask-core"\nversion = "0.1.0"\n'
                           '[[package]]\nname = "duck-detect"\ndependencies = [\n "kwipi-seg-mask-core",\n]\n',
            "LICENSE": "Apache-2.0 fixture",
            "mediad/src/detect.rs": 'frames.next_frame(); name("duck-detect"); pub(crate) mod seg;',
            "mediad/src/detect/seg.rs": "fixture",
            "duck-detect/src/rknn/segments.rs": "fixture",
            "duck-detect/src/seg_tail.rs": "fixture",
            "kwipi-seg-mask-core/src/lib.rs": "fixture",
            "robotd-params/src/lib.rs": "enabled: false",
            "duck-control/models/pickup_detector.onnx": "pinned OEM model fixture",
        }.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def test_reproducible_tar_and_verified_oem_onnx_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "src"
            root.mkdir()
            self._minimum(root)
            (root / "spaces/shared").mkdir(parents=True)
            (root / "spaces/shared/control.py").write_text("pass", encoding="utf-8")
            (root / "spaces/vision-demo").mkdir()
            os.symlink("../shared/control.py", root / "spaces/vision-demo/control.py")
            no_models_or_harness(root)
            manifest = manifest_for(root, "a" * 40)
            self.assertEqual(manifest["oem_sha"], PIN)
            self.assertEqual(manifest["mujoco_sha"], RL_PIN)
            self.assertFalse(manifest["kwipi_seg_weights_included"])
            (root / MANIFEST_NAME).write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
            first, second = Path(temp) / "1.tar.gz", Path(temp) / "2.tar.gz"
            write_tar(root, first)
            write_tar(root, second)
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(),
                             hashlib.sha256(second.read_bytes()).digest())
            self.assertEqual(verify_archive(first), manifest)

    def test_changed_content_after_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "src"
            root.mkdir()
            self._minimum(root)
            manifest = manifest_for(root, "b" * 40)
            (root / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
            (root / "mediad/src/detect/seg.rs").write_text("tampered", encoding="utf-8")
            artifact = Path(temp) / "tampered.tar.gz"
            write_tar(root, artifact)
            with self.assertRaisesRegex(ReleaseRefused, "content differs"):
                verify_archive(artifact)

    def test_new_weights_model_and_harness_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self._minimum(root)
            no_models_or_harness(root)
            (root / "kwipi_seg.rknn").write_bytes(b"unlicensed")
            with self.assertRaises(ReleaseRefused):
                no_models_or_harness(root)
            (root / "kwipi_seg.rknn").unlink()
            (root / "other.onnx").write_bytes(b"new model")
            with self.assertRaises(ReleaseRefused):
                no_models_or_harness(root)
            (root / "other.onnx").unlink()
            (root / "p10c-harness").mkdir()
            with self.assertRaises(ReleaseRefused):
                no_models_or_harness(root)
            self.assertIn("pet-detect/models/pet_detect.onnx", OEM_ONNX_PATHS)

    def test_archive_paths_and_escaping_links_refused(self):
        for name in ("../escape", "/tmp/file", "./test", "bad\\name", "dir/../../escape"):
            with self.subTest(name=name), self.assertRaises(ReleaseRefused):
                safe_member(name)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            os.symlink("../outside", root / "escape")
            with self.assertRaises(ReleaseRefused):
                manifest_for(root, "c" * 40)

    def test_harness_exact_removal_and_wrong_fixture_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "src"
            project = Path(temp) / "project"
            (project / "scripts").mkdir(parents=True)
            (project / "scripts/per_p10c_harness.toml").write_text("fixture-toml")
            (project / "scripts/per_p10c_harness.rs").write_text("fixture-rs")
            (root / "p10c-harness/src").mkdir(parents=True)
            (root / "p10c-harness/Cargo.toml").write_text("wrong")
            (root / "p10c-harness/src/lib.rs").write_text("fixture-rs")
            (root / "Cargo.toml").write_text('"uyvy", "xtask", "p10c-harness"]\n\n# Everything except')
            (root / ".per-p10a-throwaway-pin").write_text(PIN + "\n")
            with self.assertRaises(ReleaseRefused):
                drop_test_harness(root, project)
            self.assertTrue((root / "p10c-harness").is_dir())
            (root / "p10c-harness/Cargo.toml").write_text("fixture-toml")
            drop_test_harness(root, project)
            self.assertFalse((root / "p10c-harness").exists())
            self.assertFalse((root / ".per-p10a-throwaway-pin").exists())
            self.assertNotIn("p10c-harness", (root / "Cargo.toml").read_text())


if __name__ == "__main__":
    unittest.main()