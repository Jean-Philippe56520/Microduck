"""Kwipi is the chosen project name; wake phrase remains only planned."""
from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DOCS = (
    "AGENTS.md",
    "README.md",
    "docs/plan-action.md",
    "docs/roadmap.md",
    "docs/r2c-category-first-active-perception-2026-10-26.md",
)


class KwipiNamingContract(unittest.TestCase):
    def test_canonical_documents_use_kwipi_not_the_old_name(self):
        for path in CANONICAL_DOCS:
            with self.subTest(path=path):
                content = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("Kwipi", content)
                self.assertNotIn("Kwirou", content)

    def test_wake_phrase_is_not_claimed_implemented(self):
        for path in ("README.md", "AGENTS.md", "docs/plan-action.md"):
            with self.subTest(path=path):
                content = (ROOT / path).read_text(encoding="utf-8")
                self.assertIn("Hé Kwipi !", content)
                self.assertRegex(content.lower(), r"non (?:codée?|implémentée?|validée?|réalisée?)")


if __name__ == "__main__":
    unittest.main()
