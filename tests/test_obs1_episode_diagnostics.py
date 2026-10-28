"""OBS-1 diagnostic projection of existing mock EX1/EX2 evidence only."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_ledger import MockExperienceLedger, MockResolution
from microduck_companion.experience_effects import MockCue, MockEffectPair, MockEffectJournal
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.kwipi_journal import (
    read_journal, render_episode_diagnostics, MAX_ROWS, FIELDS,
)

NOW = 1_770_000_000.0
SESSION = "s-00000000000000b1"


class OBS1EpisodeDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "kwipi.sqlite3"
        self.mem = ExperienceMemory(self.path)
        self.addCleanup(self.mem.close)
        self.ledger = MockExperienceLedger(self.mem)

    def proposal(self, sequence=1, *, status="mock_executed", at=NOW):
        self.ledger.record_proposal(
            PassiveIntent("inspect", "fixture private text MUST NOT EXPORT",
                          "object_label", "ball"),
            session=SESSION, sequence=sequence, proposed_at_epoch_s=at,
        )
        if status is not None:
            self.ledger.resolve(MockResolution(
                SESSION, sequence, status, at + 1,
            ))

    def rows(self, **kwargs):
        return read_journal(
            self.path, now_wall_epoch_s=NOW + 9,
            include_withdrawn=True, **kwargs,
        )

    def test_mock_resolution_never_claims_oem_execution_or_effect(self):
        self.proposal()
        before = self.path.read_bytes()
        (record,) = [json.loads(s) for s in
                     render_episode_diagnostics(self.rows()).splitlines()]
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(1, record["schema_version"])
        self.assertEqual(SESSION + ":1", record["episode_id"])
        self.assertEqual("mock_executed", record["fixture_resolution"])
        self.assertEqual("not_recorded", record["mock_effect"])
        self.assertEqual("not_attested", record["oem_execution"])
        self.assertEqual("not_attested", record["physical_effect"])
        self.assertEqual("unproven", record["causality"])
        self.assertFalse(record["verified_on_robot"])
        self.assertEqual(0, record["motor_commands_issued"])
        self.assertEqual("not_recorded", record["qwen_context"])
        self.assertNotIn("private", json.dumps(record))

    def test_temporal_change_remains_fictional_and_not_causal(self):
        self.proposal()
        effects = MockEffectJournal(self.ledger)
        effects.record(MockEffectPair(
            SESSION, 1, MockCue("motion", "still", NOW - .5, .9),
            MockCue("motion", "moving", NOW + 1.2, .9), True, False,
        ))
        (event,) = [json.loads(s) for s in
                    render_episode_diagnostics(self.rows()).splitlines()]
        self.assertEqual("changed", event["mock_effect"])
        self.assertEqual("temporal_only", event["mock_association"])
        self.assertEqual("not_attested", event["oem_execution"])
        self.assertEqual("unproven", event["causality"])

    def test_withdrawn_and_refused_are_not_physical_failures(self):
        self.proposal(1)
        self.ledger.retract(
            session=SESSION, sequence=1, reason="source_retracted")
        self.proposal(2, status="refused", at=NOW + 2)
        rows = self.rows()
        output = render_episode_diagnostics(rows)
        a, b = [json.loads(s) for s in output.splitlines()]
        self.assertEqual("refused", a["fixture_resolution"])
        self.assertEqual("not_recorded", a["mock_effect"])
        self.assertEqual("withdrawn", b["fixture_resolution"])
        self.assertTrue(b["corrected"])
        self.assertEqual("unproven", b["causality"])

    def test_rejects_forgery_private_fields_duplicates_and_wrong_types(self):
        self.proposal()
        (original,) = self.rows()
        for field, value in (
            ("source", "sensor"),
            ("verified_on_robot", True),
            ("causality_established", True),
            ("motor_commands_issued", 1),
            ("motor_commands_issued", True),
            ("status", "real_executed"),
            ("reason_code", "person-secret@example.org"),
            ("intention", "kick_left"),
            ("time_epoch_s", float("nan")),
            ("sequence", 0),
            ("corrected", "False"),
            ("effect_status", "changed"),
            ("category", "somebody@example.org"),
        ):
            with self.subTest(field=field, value=value):
                row = dict(original, **{field: value})
                with self.assertRaises(ValueError):
                    render_episode_diagnostics((row,))
        with self.assertRaises(ValueError):
            render_episode_diagnostics((dict(original, secret="private"),))
        with self.assertRaises(ValueError):
            render_episode_diagnostics((original, original))
        with self.assertRaises(ValueError):
            render_episode_diagnostics(tuple(original for _ in range(MAX_ROWS + 1)))
        with self.assertRaises(ValueError):
            render_episode_diagnostics([original])
        self.assertEqual("", render_episode_diagnostics(()))
        self.assertEqual(set(FIELDS), set(original))

    def test_cli_reads_only_and_refuses_incompatible_modes(self):
        self.proposal()
        before = self.path.read_bytes()
        root = Path(__file__).resolve().parents[1]
        base = [sys.executable, "-m", "microduck_companion.kwipi_journal",
                str(self.path), "--at", str(NOW + 9), "--diagnostic"]
        run = subprocess.run(base, cwd=root, capture_output=True,
                             text=True, timeout=15)
        self.assertEqual(0, run.returncode, run.stderr)
        self.assertEqual(1, len(run.stdout.splitlines()))
        self.assertEqual("mock_fixture_only",
                         json.loads(run.stdout)["source"])
        self.assertEqual(before, self.path.read_bytes())
        for suffix in (["--format", "csv"], ["--trend", "observe",
                                            "--category", "ball"]):
            with self.subTest(suffix=suffix):
                refused = subprocess.run(base + suffix, cwd=root,
                                         capture_output=True, text=True,
                                         timeout=15)
                self.assertEqual(2, refused.returncode)
                self.assertEqual("", refused.stdout)
        self.assertEqual(before, self.path.read_bytes())


if __name__ == "__main__":
    unittest.main()
