"""COG-A1 reference data gate. No motor, image, model, network or SQLite."""
from __future__ import annotations

import json
import unittest
from importlib import resources

from microduck_companion.initial_knowledge import (
    MAX_REFERENCE_BYTES, parse_reference_bytes, read_bundled_references,
)


class CogA1ReferenceTests(unittest.TestCase):
    @staticmethod
    def raw_data():
        return json.loads(resources.files("microduck_companion").joinpath(
            "initial_knowledge_v1.json").read_text(encoding="utf-8"))

    @staticmethod
    def parse(data):
        return parse_reference_bytes(json.dumps(data, ensure_ascii=False).encode())

    def test_bundled_candidate_is_bounded_and_non_motor(self):
        catalog = read_bundled_references()
        self.assertLessEqual(len(catalog.rules), 32)
        self.assertGreaterEqual(len(catalog.rules), 6)
        self.assertEqual(2, len(catalog.sources))
        for rule in catalog.rules:
            self.assertEqual("candidate_not_operator_approved", rule.source_status)
            self.assertFalse(rule.physical_observation_verified)
            self.assertFalse(rule.skill_loaded_verified)
            self.assertFalse(rule.motor_action_authorized)
            self.assertFalse(rule.causality_established)

    def test_general_reference_adds_explanation_not_observation(self):
        catalog = read_bundled_references()
        names = [rule.id for rule in catalog.for_f1_label("ball")]
        self.assertIn("ball.possible_rolling", names)
        self.assertIn("ball.possible_kick_game", names)
        kick = next(r for r in catalog.for_concept("ball") if r.oem_skill_reference)
        self.assertEqual("kick_left", kick.oem_skill_reference)
        self.assertFalse(kick.skill_loaded_verified)
        self.assertFalse(kick.motor_action_authorized)

    def test_f1_unknown_and_future_concepts_never_map_to_live_objects(self):
        catalog = read_bundled_references()
        self.assertTrue(catalog.for_concept("chair"))
        self.assertTrue(catalog.for_concept("cloth"))
        for label in ("chair", "cloth", "unknown", "other_object", "", "Ball", "person:alice"):
            self.assertEqual((), catalog.for_f1_label(label))
        self.assertTrue(catalog.for_f1_label("person"))

    def test_new_reference_for_existing_category_needs_only_data(self):
        data = self.raw_data()
        row = dict(data["rules"][0])
        row.update({"id": "ball.new_property", "statement": "Observation supplementaire utile si la surface change."})
        data["rules"].append(row)
        augmented = self.parse(data)
        self.assertEqual(len(read_bundled_references().for_concept("ball")) + 1,
                         len(augmented.for_concept("ball")))

    def test_reject_duplicate_key_and_rule_id(self):
        with self.assertRaises(ValueError):
            parse_reference_bytes(b'{"schema_version":1,"schema_version":1}')
        data = self.raw_data()
        data["rules"].append(dict(data["rules"][0]))
        with self.assertRaises(ValueError):
            self.parse(data)

    def test_reject_missing_source_and_laundered_oem_name(self):
        data = self.raw_data()
        data["rules"][0]["source_ids"] = ["unprovided_source"]
        with self.assertRaises(ValueError):
            self.parse(data)
        data = self.raw_data()
        skill = next(r for r in data["rules"] if r["oem_skill_reference"])
        skill["source_ids"] = ["cog-a1-editorial-draft"]
        with self.assertRaises(ValueError):
            self.parse(data)

    def test_reject_invented_oem_skill_or_bogus_pin_prefix(self):
        data = self.raw_data()
        entry = next(r for r in data["rules"] if r["oem_skill_reference"])
        entry["oem_skill_reference"] = "unreviewed_skill"
        with self.assertRaises(ValueError):
            self.parse(data)
        data = self.raw_data()
        data["sources"][1]["citation"] = (
            "https://github.com/pollen-robotics/microduck/blob/"
            "942e58e3NOT_THE_PIN/docs/robot/cheatsheet.md"
        )
        with self.assertRaises(ValueError):
            self.parse(data)

    def test_reject_correct_commit_with_unreviewed_document(self):
        # Correct pinned commit alone is insufficient: exact reviewed path
        # is required before a source may legitimate any OEM skill name.
        valid = self.raw_data()["sources"][1]["citation"]
        self.assertTrue(valid.endswith("/docs/robot/cheatsheet.md"))
        for citation in (
            valid.rsplit("/", 1)[0] + "/not-reviewed.md",
            valid + ".backup",
            valid + "?raw=1",
            valid + "#uncertified",
            valid.replace("/docs/robot/cheatsheet.md", "/robotd/src/control.rs"),
            valid.replace("942e58e3aa6dbb28e7037203fff11866122c7567",
                          "d13be2c1a2f4b1e0b0e499b08b92f870518b1384"),
        ):
            data = self.raw_data()
            data["sources"][1]["citation"] = citation
            with self.subTest(citation=citation), self.assertRaises(ValueError):
                self.parse(data)

    def test_reject_unreviewed_fact_or_motor_boolean(self):
        for field, value in (("verified", True), ("executed", True),
                             ("physical_observation_verified", True),
                             ("can_authorize_actions", True)):
            data = self.raw_data()
            data["rules"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.parse(data)

    def test_reject_bad_counts_versions_and_nonfinite_json(self):
        with self.assertRaises(ValueError):
            parse_reference_bytes(b' ' * (MAX_REFERENCE_BYTES + 1))
        with self.assertRaises(ValueError):
            parse_reference_bytes(b'{"schema_version":NaN}')
        for key, value in (("schema_version", 2), ("schema_version", True),
                           ("status", "approved")):
            data = self.raw_data()
            data[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.parse(data)
        data = self.raw_data()
        data["rules"] = data["rules"] * 5
        with self.assertRaises(ValueError):
            self.parse(data)

    def test_reject_unauthenticated_oem_documentation_source(self):
        data = self.raw_data()
        data["sources"][1]["citation"] = "https://example.com/not-pinned"
        with self.assertRaises(ValueError):
            self.parse(data)

    def test_no_second_database_or_actuator_dependencies(self):
        import inspect
        import microduck_companion.initial_knowledge as module
        source = inspect.getsource(module)
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("robot.do", source)
        self.assertNotIn("Ollama", source)


if __name__ == "__main__":
    unittest.main()
