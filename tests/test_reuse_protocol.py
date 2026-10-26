"""Documentary guardrails for the reuse-first engineering process.

Checking files and imports cannot replace architecture review or physical
testing; this only prevents accidentally dropping the permanent workflow.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReuseFirstProtocolTests(unittest.TestCase):
    def test_protocol_and_agent_instructions_are_committed(self):
        protocol = (ROOT / "docs/development-reuse-protocol.md").read_text(
            encoding="utf-8")
        agent = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for phrase in (
            "Réutiliser avant de créer",
            "Inspecter le dépôt actuel",
            "réutiliser, adapter ou créer",
            "robotd seul",
            "M9",
            "docs/plan-action.md",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.casefold(), protocol.casefold())
        self.assertIn("development-reuse-protocol.md", agent)
        self.assertIn("upstream/microduck", agent)
        self.assertIn("protocole", agent.casefold())

    def test_pull_request_template_requires_a_reuse_justification(self):
        template = (ROOT / ".github/pull_request_template.md").read_text(
            encoding="utf-8")
        for required in (
            "Inventaire réutilisation avant développement",
            "Sources OEM inspectées",
            "Sources Companion inspectées",
            "Composants réutilisés",
            "Nouveau code et nécessité",
            "Risque de doublon",
            "robotd",
            "tests nominaux et d'échec",
        ):
            with self.subTest(required=required):
                self.assertIn(required, template)

    def test_r1_reuses_existing_validators_instead_of_redoing_parsers(self):
        parsed = ast.parse((ROOT / "microduck_companion/oem_passive_fixture.py")
                           .read_text(encoding="utf-8"))
        imported = {
            entry.module: {alias.name for alias in entry.names}
            for entry in parsed.body
            if isinstance(entry, ast.ImportFrom) and entry.level == 1
        }
        expectations = {
            "passive_media_router": {
                "parse_oem_shape_notification", "MockAudioCueRouter",
            },
            "oem_frame_preflight": {"parse_mock_frame_header"},
            "sim_ipc": {"Notification", "parse_depth"},
            "passive_sources": {"PassiveRead"},
            "perception": {"PerceptionSnapshot"},
        }
        for module, names in expectations.items():
            with self.subTest(module=module):
                self.assertTrue(names <= imported.get(module, set()))
        own = (ROOT / "microduck_companion/oem_passive_fixture.py").read_text(
            encoding="utf-8")
        for dangerous in ("socket.connect(", "requests.get(",
                          "robot.move", "media.frame.request"):
            self.assertNotIn(dangerous, own)


if __name__ == "__main__":
    unittest.main()
