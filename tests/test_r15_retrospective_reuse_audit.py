"""R1.5 retrospective architecture evidence guards, NOT hardware/behavior tests.

These assertions only prevent the audit from silently misrepresenting the
existing source. They do NOT prove that duplicated functionality cannot
appear later or that any companion capability works on the real robot.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/r15-retrospective-reuse-audit-2026-10-26.md"
M1A = ROOT / "microduck_companion/compact_multimodal_memory.py"
M1B = ROOT / "microduck_companion/multiview_pattern_memory.py"
CORE = ROOT / "microduck_companion/episodic_memory.py"


class RetrospectiveReuseAuditTests(unittest.TestCase):
    def test_report_is_documented_without_pretending_hardware_validation(self):
        report = REPORT.read_text(encoding="utf-8")
        for required in (
            "a6142919e763b3c1f762c5d14494d54de4e1be2e",
            "942e58e3aa6dbb28e7037203fff11866122c7567",
            "réutiliser avant de créer", "M1-A", "M1-B",
            "m1a_compact_patterns", "m1b_groups", "m1b_signatures",
            "M9", "unknown", "R2", "avant portage",
            "robotd", "pas un audit ligne par ligne",
        ):
            with self.subTest(required=required):
                self.assertIn(required.casefold(), report.casefold())
        self.assertIn("**P0 — avant tout R2", report)
        self.assertIn("**CONSERVER LAB", report)
        self.assertIn("non mise en code", report)

    def test_m1b_reuses_m1a_features_and_the_same_sqlite_connection_type(self):
        m1a = M1A.read_text(encoding="utf-8")
        m1b = M1B.read_text(encoding="utf-8")
        core = CORE.read_text(encoding="utf-8")
        imported = [
            node for node in ast.parse(m1b).body
            if isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module == "compact_multimodal_memory"
        ]
        names = {a.name for node in imported for a in node.names}
        self.assertIn("image_fingerprint", names)
        self.assertIn("audio_fingerprint", names)
        self.assertIn("m1a_compact_patterns", m1a)
        self.assertIn("m1b_groups", m1b)
        self.assertIn("m1b_signatures", m1b)
        for content in (m1a, m1b):
            self.assertIn("from .episodic_memory import ExperienceMemory", content)
            self.assertIn("memory.conn", content)
            self.assertNotIn("sqlite3.connect(", content)
        self.assertIn("sqlite3.connect(", core)
        # This confirms that the code contains two schema variants, not
        # whether they are both in use or if their physical size is bounded.

    def test_legacy_motor_diagnostics_remain_only_simulator_examples(self):
        trial = (ROOT / "microduck_companion/sim_walk_trial.py").read_text(
            encoding="utf-8")
        command = (ROOT / "microduck_companion/sim_motion.py").read_text(
            encoding="utf-8")
        self.assertIn("Never import/use this on an actual Microduck", trial)
        self.assertIn("simulator-only", command)
        self.assertIn("robot.move", command)
        self.assertIn("robot.stop", command)
        # Existence of these commands is a reason to exclude the diagnostic
        # package from any future embedded runtime, NOT proof of deployment.

    def test_single_source_of_truth_for_next_r2_gate(self):
        plan = (ROOT / "docs/plan-action.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for target in (plan, readme):
            self.assertIn(REPORT.name, target)
        self.assertIn("R1.5", plan)
        self.assertIn("sans double écriture", plan)
        protocol = (ROOT / "docs/development-reuse-protocol.md").read_text(
            encoding="utf-8")
        self.assertIn("réutiliser, adapter ou créer", protocol.casefold())


if __name__ == "__main__":
    unittest.main()
