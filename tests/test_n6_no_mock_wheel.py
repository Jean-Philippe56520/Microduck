"""N6 nonmotor regression fixtures, including historical F4-C compatibility."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts import n5_host_wheel as n5
from scripts import n6_no_mock_wheel as n6

ROOT = Path(__file__).resolve().parents[1]


class N6NoMockWheelTests(unittest.TestCase):
    def test_historical_context_import_identity_and_strict_flags(self):
        from microduck_companion.mock_social_cues import (
            MockSocialContext as HistoricalContext,
        )
        from microduck_companion.social_context import (
            MockSocialContext as SharedContext,
        )
        from microduck_companion.oem_expression_hints import (
            MockSocialContext as OemContext,
        )
        self.assertIs(HistoricalContext, SharedContext)
        self.assertIs(OemContext, SharedContext)
        self.assertEqual(SharedContext(), HistoricalContext())
        with self.assertRaisesRegex(ValueError, "booleans"):
            SharedContext(operator_opt_in=1)
        with self.assertRaisesRegex(ValueError, "booleans"):
            SharedContext(privacy_reviewed="yes")

    def test_strict_optional_import_sites_are_reviewed(self):
        source, inventory = n5._checked_paths(ROOT, n5.APPROVED_FILES)
        self.assertEqual(inventory["module_count"], 122)
        self.assertEqual(len(n5.APPROVED_FILES), 20)
        sites = n6.verify_optional_boundary(source)
        self.assertEqual(set(sites), n6.ALLOWED_SITES)

    def test_unreviewed_fixture_import_is_rejected(self):
        source, _ = n5._checked_paths(ROOT, n5.APPROVED_FILES)
        source = dict(source)
        filename = "microduck_companion/social_context.py"
        source[filename] += b"\nfrom .mock_cycles import MockCycleRunner\n"
        with self.assertRaisesRegex(ValueError, "import sites changed"):
            n6.verify_optional_boundary(source)

    def test_optional_site_removal_requires_review(self):
        source, _ = n5._checked_paths(ROOT, n5.APPROVED_FILES)
        source = dict(source)
        filename = "microduck_companion/behavioral_memory.py"
        source[filename] = source[filename].replace(
            b"from .mock_cycles import MockCycleRunner",
            b"from typing import Any as MockCycleRunner", 1,
        )
        with self.assertRaisesRegex(ValueError, "import sites changed"):
            n6.verify_optional_boundary(source)

    def test_new_absolute_import_is_rejected(self):
        source, _ = n5._checked_paths(ROOT, n5.APPROVED_FILES)
        source = dict(source)
        filename = "microduck_companion/social_context.py"
        source[filename] += b"\nimport microduck_companion.mock_social_cues\n"
        with self.assertRaisesRegex(ValueError, "Absolute"):
            n6.verify_optional_boundary(source)

    def test_n6_stage_is_exclusively_in_temporary_directory(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "stage"
            report = n6.stage_probe(ROOT, output)
            self.assertEqual(report["normal_source_python_modules"], 122)
            self.assertEqual(report["n5_reviewed_closure"], 20)
            self.assertEqual(report["probe_python_modules"], 18)
            self.assertEqual(report["omitted_mock_engines"], sorted(n5.LAB_EXCEPTIONS))
            self.assertTrue((output / "microduck_companion/social_context.py").is_file())
            for path in n5.LAB_EXCEPTIONS:
                self.assertFalse((output / path).exists())
            staged = {p.relative_to(output).as_posix() for p in output.rglob("*.py")}
            self.assertEqual(staged, n5.APPROVED_FILES - n5.LAB_EXCEPTIONS)
            self.assertIn(n6.DIST_NAME, (output / "pyproject.toml").read_text())

    def test_staging_in_checkout_remains_forbidden(self):
        with self.assertRaisesRegex(ValueError, "outside"):
            n6.stage_probe(ROOT, ROOT / "n6-dangerous-incheckout")

    def test_legacy_P2a_record_and_social_description_still_work_on_full_repo(self):
        from microduck_companion.autonomy import AutonomyBrain
        from microduck_companion.behavioral_memory import BehavioralMemory
        from microduck_companion.episodic_memory import ExperienceMemory
        from microduck_companion.mock_cycles import MockCycleRunner
        from microduck_companion.mock_social_cues import MockSocialPlan
        from microduck_companion.passive_memory import PassiveObservationJournal
        mem = ExperienceMemory(":memory:")
        try:
            brain = AutonomyBrain(mem)
            journal = PassiveObservationJournal(mem)
            hist = BehavioralMemory(mem)
            runner = MockCycleRunner(mem, session="n6-historical")
            self.assertFalse(hist.record(runner=runner, sequence=1, now_wall_epoch_s=100.0))
            portrait = brain.describe_behavior(
                MockSocialPlan("silence", "fixture"),
                journal=journal, now_wall_epoch_s=100.0)
            self.assertEqual(portrait.state, "Chill")
            self.assertFalse(portrait.executed)
            self.assertEqual(portrait.motor_commands_issued, 0)
        finally:
            mem.close()


if __name__ == "__main__":
    unittest.main()
