"""P14A: real source closure and fail-closed embedded wheel candidate."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.per_p14a_embedded_wheel import (
    DIST_NAME, METADATA, PASSIVE_PATH, SCHEMA, SELECTED,
    current_source, inspect, stage, verify_oem_readonly_source,
)

ROOT = Path(__file__).resolve().parents[1]


class P14AEmbeddedCandidateTests(unittest.TestCase):
    def test_pinned_public_N6_plus_only_readonly_transport(self):
        sources = current_source(ROOT)
        self.assertEqual(set(sources), SELECTED)
        self.assertEqual(len(sources), 19)
        self.assertIn(PASSIVE_PATH, sources)
        self.assertFalse(any("/mock_" in x for x in sources))
        self.assertFalse(any("/qwen" in x or "/sim_" in x and x != PASSIVE_PATH
                             for x in sources))
        contract = verify_oem_readonly_source(sources[PASSIVE_PATH])
        self.assertEqual(contract["read_only_rpc"],
                         ["robot.health", "robot.subscribe", "tof.stream"])

    def test_unapproved_move_method_breaks_contract(self):
        original = current_source(ROOT)[PASSIVE_PATH]
        with self.assertRaises(ValueError):
            verify_oem_readonly_source(
                original.replace(b'"robot.health"', b'"robot.move"', 1))

    def test_dynamic_import_or_write_breaks_contract(self):
        original = current_source(ROOT)[PASSIVE_PATH]
        with self.assertRaises(ValueError):
            verify_oem_readonly_source(original + b"\nimport subprocess\n")
        with self.assertRaises(ValueError):
            verify_oem_readonly_source(original + b"\nopen('/tmp/private','w')\n")

    def test_missing_whitelist_breaks_contract(self):
        original = current_source(ROOT)[PASSIVE_PATH]
        wrong = original.replace(b"if method not in _ALLOWED_READS:",
                                 b"if False:", 1)
        self.assertNotEqual(wrong, original)
        with self.assertRaises(ValueError):
            verify_oem_readonly_source(wrong)

    def test_distinct_identity_and_no_boot_service(self):
        self.assertIn(DIST_NAME, METADATA)
        self.assertIn("0.2.0a1", METADATA)
        self.assertNotIn("entry-points", METADATA)
        self.assertNotIn("systemd", METADATA)
        self.assertEqual(len(SELECTED), 19)

    def test_real_staging_preserves_reviewed_source_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "staging"
            out = stage(ROOT, dest)
            self.assertEqual(out["schema"], SCHEMA)
            self.assertEqual(out["python_modules"], 19)
            self.assertEqual(out["motor_commands_issued"], 0)
            self.assertFalse(out["robot_service_installed"])
            self.assertFalse(out["physical_robot_verified"])
            self.assertFalse(out["perception_model_included"])
            self.assertEqual(
                out["source_sha256"][PASSIVE_PATH],
                hashlib.sha256((ROOT / PASSIVE_PATH).read_bytes()).hexdigest(),
            )
            for rel in out["files"]:
                self.assertEqual((dest / rel).read_bytes(), (ROOT / rel).read_bytes())
            self.assertNotIn("microduck_companion/mock_cycles.py", out["files"])
            with self.assertRaises(ValueError):
                stage(ROOT, dest)

    def test_nonwheel_and_foreign_path_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "notawheel.whl"
            fake.write_bytes(b"not-a-wheel")
            with self.assertRaises(ValueError):
                inspect(ROOT, fake)
            with self.assertRaises(ValueError):
                stage(ROOT, ROOT / "should-not-exist-p14a")

    def test_bad_wheel_entries_and_wrong_modules_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / "bad.whl"
            with zipfile.ZipFile(fake, "w") as z:
                z.writestr("microduck_companion/mock_cycles.py", b"motor_fake=True")
            with self.assertRaises(ValueError):
                inspect(ROOT, fake)


if __name__ == "__main__":
    unittest.main()
