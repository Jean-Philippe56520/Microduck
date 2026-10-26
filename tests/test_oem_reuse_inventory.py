"""Offline checks of the *documentary* OEM reuse audit.

These tests validate inventory consistency, not the behaviour of an OEM daemon.
They never reach a network, robot, camera, microphone, or motor bus.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "oem-reuse-inventory-2026-10-26.json"
REPORT = ROOT / "docs" / "oem-reuse-audit-2026-10-26.md"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
ALLOWED_STATES = {
    "oem_coded", "oem_documented_not_ported", "companion_host_fixture_only"
}
ALLOWED_DECISIONS = {
    "reuse_no_duplicate", "reuse_read_only_later",
    "reuse_infrastructure_only", "reuse_signals_not_capture",
    "reuse_not_object_memory", "track_without_copy", "monitor_upstream",
    "retain_as_testbed", "retain_additive", "retain_optional",
}
ALLOWED_OEM_OWNERS = {"robotd", "mediad", "tofd", "pet-detect", "oem_roadmap"}


class OEMReuseInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(INVENTORY.read_text(encoding="utf-8"))

    def test_metadata_and_pinned_oem_sources(self):
        data = self.data
        self.assertEqual(1, data["schema_version"])
        self.assertEqual("2026-10-26", data["audit_date"])
        self.assertEqual("static_source_review_only", data["evidence_level"])
        self.assertFalse(data["physical_robot_tested"])
        self.assertEqual("pollen-robotics/microduck", data["repositories"]["oem"])
        self.assertEqual("pollen-robotics/microduck_rl",
                         data["repositories"]["training"])
        self.assertEqual("Jean-Philippe56520/Microduck",
                         data["repositories"]["companion"])
        # Snapshot is deliberately fixed: a future gitlink bump needs a new
        # audit and revalidation, not a silent inheritance of today's claims.
        self.assertEqual(
            "942e58e3aa6dbb28e7037203fff11866122c7567",
            data["repositories"]["oem_gitlink_sha"])
        self.assertEqual(
            "b02fdea4902c2b93b7d34a83a6f05da4ececb7d3",
            data["repositories"]["training_gitlink_sha"])
        for field in ("oem_gitlink_sha", "training_gitlink_sha"):
            self.assertRegex(data["repositories"][field], HEX40)

    def test_motor_safety_and_no_live_sensor_promotion(self):
        data = self.data
        self.assertEqual("robotd_only", data["motor_authority"])
        self.assertFalse(data["companion_motor_authorized"])
        self.assertFalse(data["companion_oem_sensor_connected"])
        self.assertFalse(data["companion_embedded_brain_enabled"])
        entries = {entry["id"]: entry for entry in data["capabilities"]}
        self.assertEqual("robotd", entries["motor_control_and_safety"]["owner"])
        self.assertEqual("reuse_no_duplicate",
                         entries["motor_control_and_safety"]["decision"])
        self.assertEqual("retain_as_testbed",
                         entries["passive_motivations_and_rhythm"]["decision"])

    def test_ids_states_and_source_paths_are_bounded(self):
        entries = self.data["capabilities"]
        ids = [entry["id"] for entry in entries]
        self.assertGreaterEqual(len(entries), 12)
        self.assertEqual(len(ids), len(set(ids)))
        for item in entries:
            with self.subTest(capability=item["id"]):
                self.assertRegex(item["id"], r"^[a-z][a-z0-9_]*$")
                self.assertIn(item["state"], ALLOWED_STATES)
                self.assertIn(item["decision"], ALLOWED_DECISIONS)
                self.assertIs(type(item["boundary"]), str)
                self.assertGreater(len(item["boundary"]), 12)
                path = item["source_path"]
                self.assertIs(type(path), str)
                self.assertFalse(path.startswith("/"))
                self.assertNotIn("..", Path(path).parts)
                self.assertNotIn("\\", path)
                self.assertIn(item["source_repo"], ("oem", "companion"))
                if item["source_repo"] == "companion":
                    self.assertEqual("companion", item["owner"])
                    self.assertEqual("companion_host_fixture_only",
                                     item["state"])
                    self.assertTrue((ROOT / path).is_file())
                else:
                    self.assertIn(item["owner"], ALLOWED_OEM_OWNERS)
                    self.assertNotEqual("companion_host_fixture_only",
                                        item["state"])
                # OEM paths are documented at pinned gitlinks; this test does
                # not download or inspect upstream source during CI.

    def test_historic_autonomous_brain_is_never_reported_as_shipped(self):
        entries = {entry["id"]: entry for entry in self.data["capabilities"]}
        for name in ("historical_16_state_autonomy", "planned_m9_brain"):
            with self.subTest(capability=name):
                self.assertEqual("oem_documented_not_ported",
                                 entries[name]["state"])
                self.assertEqual("oem_roadmap", entries[name]["owner"])
        self.assertEqual("oem_coded", entries["idle_head_animation"]["state"])
        self.assertEqual("oem_coded", entries["duck_only_visual_detector"]["state"])
        self.assertEqual("oem_coded", entries["petting_sound_detector"]["state"])

    def test_audit_matches_no_motor_and_no_identity_claim(self):
        report = REPORT.read_text(encoding="utf-8")
        self.assertIn("16 états", report)
        self.assertIn("autonomous.rs", report)
        self.assertIn("M9", report)
        self.assertIn("sans deuxième décideur", report)
        self.assertIn("mediad", report)
        self.assertIn("robotd", report)
        self.assertIn("tofd", report)
        self.assertIn("M1-B2", report)
        self.assertIn("Aucun modèle", report) if "Aucun modèle" in report else self.assertIn(
            "pas choisi de modèle embarqué", report)
        self.assertIn("R1 —", report)
        self.assertIn("R2 —", report)
        self.assertIn("R3 —", report)
        self.assertIn("R4 —", report)
        self.assertIn("R5 —", report)


if __name__ == "__main__":
    unittest.main()
