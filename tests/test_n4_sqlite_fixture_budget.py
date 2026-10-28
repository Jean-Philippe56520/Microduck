"""N4: synthetic only; no access to operator DB, robot, media or network."""
from __future__ import annotations

import subprocess
import sys
import unittest

from scripts.n4_sqlite_fixture_budget import EXPECTED_KEYS, run_fixture


class N4SqliteFixtureBudgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.result = run_fixture()

    def test_full_closed_vocabulary_and_tombstones_survive_restart(self) -> None:
        r = self.result
        self.assertEqual(EXPECTED_KEYS, 54)
        self.assertEqual((r["before_restart"]["hypothesis_corrected"],
                          r["before_restart"]["hypothesis_active"]), (53, 1))
        self.assertEqual((r["after_restart"]["hypothesis_corrected"],
                          r["after_restart"]["hypothesis_active"]), (53, 1))
        self.assertEqual((r["after_prune"]["hypothesis_corrected"],
                          r["after_prune"]["hypothesis_active"]), (53, 0))

    def test_single_m1b_writer_and_no_unverified_motion_memory(self) -> None:
        r = self.result
        for key in ("before_restart", "after_restart", "after_prune"):
            item = r[key]
            self.assertFalse(item["m1a_legacy_table_present"])
            self.assertEqual((item["m1b_groups"], item["m1b_signatures"],
                              item["m1b_fingerprint_bytes"]), (2, 2, 80))
            self.assertEqual((item["invalid_signature_sizes"],
                              item["legacy_experience_rows"],
                              item["sim_motion_rows"]), (0, 0, 0))
        self.assertFalse(r["raw_media_persisted"])
        self.assertEqual(r["motor_commands"], 0)
        self.assertEqual(r["pc_requests"], 0)

    def test_wal_is_measured_then_checkpointed_only_on_fixture(self) -> None:
        r = self.result
        self.assertGreater(r["after_fixture_writes"]["wal_bytes"], 0)
        self.assertEqual(r["checkpoint_busy"], 0)
        self.assertEqual(r["after_checkpoint"]["wal_bytes"], 0)
        self.assertTrue(r["temporary_database_removed"])
        for label in ("baseline", "after_fixture_writes",
                      "after_restart_prune_sizes", "after_checkpoint"):
            m = r[label]
            self.assertGreaterEqual(m["page_count"], 1)
            self.assertGreaterEqual(m["db_bytes"], 0)
            self.assertGreaterEqual(m["combined_bytes"], m["db_bytes"])
            self.assertEqual(m["combined_bytes"],
                             m["db_bytes"] + m["wal_bytes"] + m["shm_bytes"])

    def test_cli_has_no_database_path_argument(self) -> None:
        # Parser gate: there is no mode to point N4 at a real SQLite file.
        result = subprocess.run(
            [sys.executable, "-m", "scripts.n4_sqlite_fixture_budget",
             "--database", "operator.sqlite3"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unrecognized arguments", result.stderr)


if __name__ == "__main__":
    unittest.main()
