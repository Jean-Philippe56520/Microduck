"""New candidate role: hypotheses and possible safe consequences, never motor authority."""
from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from PIL import Image

from microduck_companion.qwen9b_production_role import ROLE_VERSION as V1, SYSTEM_PROMPT as V1_PROMPT
from microduck_companion.qwen9b_production_role_v2 import (
    ROLE_VERSION as V2,
    SYSTEM_PROMPT as V2_PROMPT,
    SCENARIO_USER_PROMPT as V2_SCENARIO,
)
from microduck_companion.qwen9b_role_preview import make_request, evaluate_local_image


def img():
    b = io.BytesIO()
    Image.new("RGB", (125, 85), "green").save(b, format="JPEG")
    return b.getvalue()


class V2RoleTests(unittest.TestCase):
    def test_v1_remains_unchanged_and_is_still_default(self):
        wire = json.loads(make_request(img()))
        self.assertEqual(wire["messages"][0]["content"], V1_PROMPT)
        self.assertEqual(V1, "kwipi-qwen9b-role-v1-candidate")
        self.assertNotEqual(V1, V2)

    def test_v2_teaches_meaning_actions_outcomes_and_personality(self):
        for token in (
            "explorer", "experimenter", "interagir", "consequences", "jeu",
            "curiosite", "sociabilite", "prudence", "energie", "recompense",
            "inaction", "vivant", "non-vivant", "incertitude", "robotd",
            "OEM", "SQLite", "apprentissage", "corrigeable", "observer",
        ):
            self.assertIn(token.casefold(), V2_PROMPT.casefold(), token)
        self.assertIn("aucune action", V2_SCENARIO)
        self.assertIn("MOTIVATIONS ET PERSONNALITE", V2_PROMPT)

    def test_oem_skills_named_as_unverified_candidates_not_commands(self):
        for label in (
            "robotctl policy list", "walk", "sit_toggle", "sitstand",
            "kick_left", "kick_right", "ground_pick", "roulade", "bec",
            "salto", "repertorie", "disponible", "non verifiee",
        ):
            self.assertIn(label.casefold(), V2_PROMPT.casefold())
        self.assertIn("une `roulade` n'est pas", V2_PROMPT.casefold())
        self.assertIn("ne cree jamais de primitive", V2_PROMPT.casefold())
        self.assertIn("ni liste actuelle `robotctl policy list`", V2_SCENARIO)
        self.assertIn("le robot n'est pas connecte", V2_SCENARIO)
        self.assertIn("seul", V2_PROMPT.casefold())

    def test_catalog_is_not_claimed_to_be_robot_live_state(self):
        self.assertIn("catalogue N'EST PAS la liste actuelle", V2_PROMPT)
        self.assertIn("HYPOTHESE DE COMPATIBILITE", V2_PROMPT)
        self.assertIn("conditionnelles", V2_PROMPT.casefold())
        self.assertIn("ne rien faire", V2_PROMPT)
        self.assertIn("aucun contact", V2_PROMPT.casefold())

    def test_v2_is_single_image_without_forced_schema_or_motor(self):
        request = json.loads(make_request(img(), role_version=V2))
        self.assertEqual(request["messages"][0]["content"], V2_PROMPT)
        self.assertIn("consequences", request["messages"][1]["content"])
        self.assertEqual(len(request["messages"][1]["images"]), 1)
        self.assertEqual(request["model"], "qwen3.5:9b")
        self.assertFalse(request["think"])
        self.assertNotIn("format", request)
        self.assertEqual(request["options"]["num_ctx"], 4096)
        self.assertEqual(request["options"]["num_predict"], 180)
        self.assertEqual(request["keep_alive"], "0")

    def test_unknown_role_rejected_before_network(self):
        with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection") as network:
            with self.assertRaises(ValueError):
                evaluate_local_image(img(), consent=True, reviewed=True, role_version="unknown")
            with self.assertRaises(ValueError):
                evaluate_local_image(img(), consent=True, reviewed=True, role_version=None)
            with self.assertRaises(ValueError):
                make_request(img(), role_version="unknown")
            network.assert_not_called()

    def test_reject_before_consent(self):
        with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection") as network:
            for consent, reviewed in ((False, True), (True, False)):
                with self.assertRaises(ValueError):
                    evaluate_local_image(img(), consent=consent, reviewed=reviewed, role_version=V2)
            network.assert_not_called()

    def test_v2_advice_only_with_fake_ollama(self):
        envelope = {
            "model": "qwen3.5:9b", "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": "Observation : balle. Possibilite : pourrait rouler; observer l'effet."},
            "total_duration": 10_000_000_000, "load_duration": 2_000_000_000,
            "prompt_eval_duration": 3_000_000_000, "eval_duration": 5_000_000_000,
            "eval_count": 55,
        }
        class Resp:
            status = 200
            def getheader(self, name, default=None):
                return "application/json" if name == "Content-Type" else default
            def read(self, n):
                return json.dumps(envelope).encode()[:n]
        class FakeConn:
            def __init__(self, host, port, timeout):
                self.calls = []
            def request(self, method, route, body, headers):
                self.calls.append(json.loads(body))
            def getresponse(self):
                return Resp()
            def close(self):
                pass
        with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection", FakeConn):
            report = evaluate_local_image(img(), consent=True, reviewed=True, role_version=V2)
        self.assertEqual(report["role_version"], V2)
        self.assertEqual(report["status"], "unverified")
        self.assertEqual(report["motor_commands_issued"], 0)
        self.assertEqual(report["memory_writes"], 0)
        self.assertEqual(report["photos_saved_by_companion"], 0)
        self.assertIn("pourrait rouler", report["advisor_text"])
        self.assertEqual(report["generation_s"], 5.0)

    def test_v2_has_no_robot_dependency(self):
        import ast
        from pathlib import Path
        role_file = Path(__file__).resolve().parent.parent / "microduck_companion" / "qwen9b_production_role_v2.py"
        module = ast.parse(role_file.read_text(encoding="utf-8"))
        imported = [n.module for n in module.body if isinstance(n, ast.ImportFrom)]
        self.assertEqual(imported, ["__future__"])
        self.assertNotIn("import subprocess", role_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()