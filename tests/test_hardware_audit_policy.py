"""F6-D: static safety review and shell CLI tests, NO physical robot access.

All boolean 'evidence' is synthetic and cannot authorize an action. Tests
never pass both the RK3566 platform gate and physical operator confirmation
to collect data on a real Microduck.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import platform
import re
import shutil
import subprocess
import unittest

from microduck_companion.hardware_audit_policy import (
    AuditClaims, AuditReview, CHECKS, HAZARDS,
    IDLE_REQUIRED, VISION_REQUIRED, review_audit_claims,
)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "resource-audit.sh"


class OfflineChecklistTests(unittest.TestCase):
    def test_unknown_state_blocks_idle_without_claiming_real_hardware(self):
        result = review_audit_claims(AuditClaims())
        self.assertEqual("blocked_missing_manual_preconditions", result.status)
        self.assertEqual(tuple(sorted(IDLE_REQUIRED)), result.missing_declarations)
        self.assertEqual("idle", result.phase)
        self.assertFalse(result.snapshot_collected)
        self.assertFalse(result.physical_robot_validated)
        self.assertFalse(result.movement_authorized)
        self.assertEqual(0, result.oem_sockets_contacted)

    def test_all_claims_even_true_are_not_authorization(self):
        for phase in ("idle", "vision"):
            with self.subTest(phase=phase):
                declared = AuditClaims(phase, frozenset(CHECKS), frozenset())
                result = review_audit_claims(declared)
                self.assertEqual(
                    "declared_snapshot_checklist_only_not_hardware_clearance",
                    result.status,
                )
                self.assertEqual((), result.missing_declarations)
                self.assertFalse(result.physical_robot_validated)
                self.assertFalse(result.movement_authorized)
                self.assertFalse(result.stationary_vision_started)
                self.assertEqual(0, result.motor_commands_issued)

    def test_vision_requires_idle_review_and_independent_telemetry(self):
        evidence = AuditClaims("vision", IDLE_REQUIRED, frozenset())
        result = review_audit_claims(evidence)
        self.assertEqual("blocked_missing_manual_preconditions", result.status)
        for claim in (
            "idle_baseline_reviewed",
            "idle_ram_rss_cpu_reviewed",
            "idle_thermal_frequency_reviewed",
            "data_partition_mount_reviewed",
            "motor_deadline_telemetry_reviewed",
            "stationary_area_supervised",
            "vision_controlled_by_oem",
        ):
            self.assertIn(claim, result.missing_declarations)

    def test_any_hazard_stops_nonessential_activity_before_vision(self):
        for hazard in sorted(HAZARDS):
            with self.subTest(hazard=hazard):
                claim = AuditClaims(
                    "vision", VISION_REQUIRED, frozenset({hazard}),
                )
                result = review_audit_claims(claim)
                self.assertEqual(
                    "stop_nonessential_activity_manual_oem_review",
                    result.status,
                )
                self.assertEqual((hazard,), result.hazards)
                self.assertFalse(result.movement_authorized)
                self.assertFalse(result.stationary_vision_started)

    def test_movement_always_blocked_even_with_claimed_approval(self):
        for check_set, hazard_set in (
            (frozenset(), frozenset()),
            (frozenset(CHECKS), frozenset()),
            (frozenset(CHECKS), frozenset(HAZARDS)),
        ):
            with self.subTest(checks=len(check_set), hazards=len(hazard_set)):
                result = review_audit_claims(
                    AuditClaims("movement", check_set, hazard_set),
                )
                self.assertEqual(
                    "movement_disabled_independent_locomotion_validation_required",
                    result.status,
                )
                self.assertFalse(result.movement_authorized)
                self.assertFalse(result.physical_robot_validated)
                self.assertEqual(0, result.motor_commands_issued)

    def test_bad_phase_claim_flags_and_bad_types_rejected(self):
        for phase in ("", "walk", "MOVE", "movеment", None, False):
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                AuditClaims(phase=phase)
        for value in ("idle_baseline_reviewed", {"idle_baseline_reviewed"},
                      frozenset({"unknown"}), frozenset({1}),
                      frozenset({True}), frozenset({"stationary_area_supervised", 5})):
            with self.subTest(checks=value), self.assertRaises(ValueError):
                AuditClaims(checks=value)
        for value in ("thermal_risk_or_throttling",
                      {"thermal_risk_or_throttling"},
                      frozenset({"unknown"}), frozenset({True})):
            with self.subTest(hazards=value), self.assertRaises(ValueError):
                AuditClaims(hazards=value)

    def test_checklist_never_certifies_external_events(self):
        result = review_audit_claims(
            AuditClaims("idle", IDLE_REQUIRED, frozenset()),
        )
        for unauthorized in (
            {"snapshot_collected": True},
            {"physical_robot_validated": True},
            {"stationary_vision_started": True},
            {"movement_authorized": True},
            {"oem_sockets_contacted": 1},
            {"motor_commands_issued": 1},
            {"recorded_private_data": True},
        ):
            with self.subTest(unauthorized=unauthorized):
                with self.assertRaises(ValueError):
                    replace(result, **unauthorized)

    def test_invalid_review_object_refused(self):
        with self.assertRaises(TypeError):
            review_audit_claims(None)
        with self.assertRaises(TypeError):
            review_audit_claims({"phase": "vision"})


@unittest.skipUnless(shutil.which("sh"), "POSIX shell required for shell guard tests")
class ResourceAuditShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SCRIPT.is_file():
            raise AssertionError("resource-audit.sh is missing")

    def shell(self, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["sh", str(SCRIPT), *arguments],
            capture_output=True, text=True,
            timeout=5.0, check=False,
        )

    def test_shell_has_valid_posix_syntax(self):
        result = subprocess.run(
            ["sh", "-n", str(SCRIPT)],
            capture_output=True, text=True, timeout=5, check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_default_no_arg_never_collects_host_telemetry(self):
        result = self.shell()
        self.assertEqual(2, result.returncode)
        self.assertIn("--plan", result.stderr)
        self.assertNotIn("F6D_SURVEY_ONLY=YES", result.stdout)

    def test_offline_plan_does_not_measure_or_claim_robot(self):
        result = self.shell("--plan")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("NO HARDWARE WAS QUERIED", result.stdout)
        self.assertIn("Movement NOT AUTHORIZED", result.stdout)
        self.assertIn("thermal throttling", result.stdout)
        self.assertNotIn("F6D_SURVEY_ONLY=YES", result.stdout)
        self.assertNotIn("ROBOT_HARDWARE_VALIDATED=YES", result.stdout)
        self.assertNotIn(platform.node(), result.stdout)

    def test_invalid_ambiguous_and_duplicate_flags_fail_closed(self):
        cases = (
            ("--plan", "--phase", "idle"),
            ("--phase", "idle", "--plan"),
            ("--phase", "running", "--operator-confirmed"),
            ("--phase", "idle", "--operator-confirmed",
             "--operator-confirmed"),
            ("--phase", "idle", "--phase", "vision",
             "--operator-confirmed"),
            ("--phase",),
            ("--operator-confirmed",),
            ("--phase", "vision", "--operator-confirmed",
             "--vision-already-enabled", "--vision-already-enabled"),
        )
        for args in cases:
            with self.subTest(args=args):
                result = self.shell(*args)
                self.assertNotEqual(0, result.returncode)
                self.assertNotIn("F6D_SURVEY_ONLY=YES", result.stdout)

    def test_idle_requires_explicit_operator_and_no_vision_claim(self):
        for args in (
            ("--phase", "idle"),
            ("--phase", "idle", "--idle-reviewed", "--operator-confirmed"),
            ("--phase", "idle", "--operator-confirmed",
             "--vision-already-enabled"),
        ):
            with self.subTest(args=args):
                result = self.shell(*args)
                self.assertNotEqual(0, result.returncode)
                self.assertNotIn("F6D_SURVEY_ONLY=YES", result.stdout)

    def test_vision_requires_operator_prior_idle_and_external_enablement(self):
        cases = (
            ("--phase", "vision", "--operator-confirmed"),
            ("--phase", "vision", "--operator-confirmed", "--idle-reviewed"),
            ("--phase", "vision", "--operator-confirmed",
             "--vision-already-enabled"),
            ("--phase", "vision", "--idle-reviewed",
             "--vision-already-enabled"),
        )
        for args in cases:
            with self.subTest(args=args):
                result = self.shell(*args)
                self.assertNotEqual(0, result.returncode)
                self.assertNotIn("F6D_SURVEY_ONLY=YES", result.stdout)

    def test_movement_is_always_blocked_before_platform_probe(self):
        for phase in ("movement", "move", "walking"):
            with self.subTest(phase=phase):
                result = self.shell(
                    "--phase", phase, "--operator-confirmed",
                    "--idle-reviewed", "--vision-already-enabled",
                )
                self.assertEqual(3, result.returncode)
                self.assertIn("never start or audit live movement", result.stderr)
                self.assertNotIn("F6D_SURVEY_ONLY=YES", result.stdout)

    def test_host_x86_cannot_be_mistaken_for_a_robot(self):
        # Skip on future ARM64 CI; never auto-collect on an actual device.
        if platform.machine() in ("aarch64", "arm64"):
            self.skipTest("test must not collect from an ARM64 device")
        for args in (
            ("--phase", "idle", "--operator-confirmed"),
            ("--phase", "vision", "--operator-confirmed",
             "--idle-reviewed", "--vision-already-enabled"),
        ):
            with self.subTest(args=args):
                result = self.shell(*args)
                self.assertEqual(3, result.returncode)
                self.assertIn("ARM64 RK3566 development unit not detected",
                              result.stderr)
                self.assertNotIn("F6D_SURVEY_ONLY=YES", result.stdout)

    def test_script_contains_no_write_record_or_oem_motor_operations(self):
        content = SCRIPT.read_text(encoding="utf-8")
        for dangerous in (
            r"\bsystemctl\s+(?:start|stop|restart|enable|disable)",
            r"\brobotctl\s+(?:move|head|stop)",
            r"\brobot\.move\s*\(",
            r"\bcurl\s+",
            r"\bwget\s+",
            r">\s*/var/lib/robot/",
            r"\bdd\s+",
            r"\bmkfs\.",
            r"(?m)^\s*mount\s+",
            r"(?m)^\s*umount\s+",
        ):
            with self.subTest(expression=dangerous):
                self.assertIsNone(re.search(dangerous, content))
        self.assertIn("MOTOR_50HZ_DEADLINE_MISSES=NOT_MEASURED", content)
        self.assertIn("PERSISTENT_STORAGE_VALIDATED=NO", content)


if __name__ == "__main__":
    unittest.main()
