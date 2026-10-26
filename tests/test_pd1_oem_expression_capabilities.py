"""PD1: audit of sixteen *historical* OEM names; no physical expression.

All inputs are local, invented fixtures. No state in this test grants motor,
speaker, camera, wake-word, PC/Qwen, or SQLite write permissions.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.behavior_personality import (
    BehaviorExpressionCapability, BehaviorPortrait, DESCRIPTIVE_ONLY,
    HISTORICAL_OEM_STATES, behavior_catalog, expression_capability_catalog,
    expression_capability_for, inspect_expression_capability,
)
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.mock_social_cues import MockSocialContext
from microduck_companion.oem_expression_hints import (
    MockOemConditions, MockOemCue, describe_oem_expression,
)
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_memory import PassiveObservationJournal

WALL = 1_780_000_000.0
NOW = 100.0


def consent(**changes):
    flags = dict(
        operator_opt_in=True, supervised=True, privacy_reviewed=True,
        quiet_mode=False, brief_audio_opt_in=True,
    )
    flags.update(changes)
    return MockSocialContext(**flags)


class PD1CapabilityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "existing-memory.sqlite3"
        self.memory = ExperienceMemory(self.path)
        self.addCleanup(self.memory.close)
        self.journal = PassiveObservationJournal(self.memory)
        self.brain = AutonomyBrain(self.memory)
        self.portrait = self.brain.describe_behavior(
            PassiveIntent("idle", "no_current_observation"),
            journal=self.journal, now_wall_epoch_s=WALL,
        )

    def event(self, kind="petting_start", *, consent_flags=None,
              conditions=None, now=NOW, at=NOW-.1):
        return describe_oem_expression(
            self.portrait,
            cue=MockOemCue(kind, at),
            context=consent() if consent_flags is None else consent_flags,
            conditions=MockOemConditions() if conditions is None else conditions,
            now_monotonic_s=now,
        )

    def test_all_sixteen_in_same_order_as_existing_pa_catalogue(self):
        entries = expression_capability_catalog()
        self.assertEqual(16, len(entries))
        self.assertEqual(HISTORICAL_OEM_STATES, tuple(e.state for e in entries))
        self.assertEqual(
            tuple((x.state, x.companion_status) for x in entries),
            behavior_catalog(),
        )
        self.assertEqual(16, len(set(e.state for e in entries)))

    def test_four_partial_evidence_entries_not_four_dispatchable_skills(self):
        evidence = {
            c.state: c.oem_expression_evidence
            for c in expression_capability_catalog()
            if c.oem_expression_evidence != "none"
        }
        self.assertEqual({
            "Chill": "background_idle_glance",
            "LookAround": "background_idle_glance",
            "Nap": "background_idle_yawn",
            "Petted": "conditional_oem_petting_coo",
        }, evidence)
        for c in expression_capability_catalog():
            self.assertFalse(c.named_state_command_available)
            self.assertFalse(c.expression_executed)
            self.assertFalse(c.hardware_verified)
            self.assertFalse(c.physical_execution_authorized)
            self.assertEqual(0, c.motor_commands_issued)
            self.assertEqual(0, c.speaker_commands_issued)
            self.assertEqual(0, c.pc_requests_issued)
            self.assertEqual(0, c.memories_written)

    def test_twelve_states_without_partial_expressions_stay_unported(self):
        pending = {
            c.state for c in expression_capability_catalog()
            if c.oem_expression_evidence == "none"
        }
        self.assertEqual(12, len(pending))
        self.assertEqual(pending, set(HISTORICAL_OEM_STATES) - {
            "Chill", "LookAround", "Nap", "Petted",
        })
        self.assertIn("Held", pending)
        self.assertIn("GroundPick", pending)
        self.assertIn("BallPlay", pending)
        self.assertIn("Startle", pending)

    def test_descriptive_only_does_not_claim_oem_action(self):
        for name in DESCRIPTIVE_ONLY:
            with self.subTest(name=name):
                cap = expression_capability_for(name)
                self.assertEqual("mock_description_only", cap.companion_status)
                self.assertFalse(cap.named_state_command_available)
        self.assertEqual(
            "requires_oem_m9_or_sensor_review",
            expression_capability_for("Petted").companion_status,
        )

    def test_evidence_paths_reference_pinned_oem_only(self):
        for c in expression_capability_catalog():
            self.assertEqual("pinned_oem_942e58e3_static_review", c.source)
            if c.oem_expression_evidence == "none":
                self.assertIsNone(c.oem_evidence_path)
            else:
                self.assertIn(
                    c.oem_evidence_path,
                    {"robotd/src/idle_head.rs", "robotd/src/main.rs"},
                )

    def test_idle_portrait_selection_is_description_only(self):
        before = self.memory.conn.total_changes
        old = vars(self.brain.motives).copy()
        cap = inspect_expression_capability(self.portrait)
        self.assertEqual("Chill", cap.state)
        self.assertEqual("mock_behavior_portrait", cap.selected_from)
        self.assertEqual("background_idle_glance", cap.oem_expression_evidence)
        self.assertFalse(cap.expression_executed)
        self.assertEqual(before, self.memory.conn.total_changes)
        self.assertEqual(old, vars(self.brain.motives))

    def test_rest_portrait_is_not_a_named_nap_command(self):
        rest = self.brain.describe_behavior(
            PassiveIntent("rest", "low_simulated_motivational_energy"),
            journal=self.journal, now_wall_epoch_s=WALL,
        )
        cap = inspect_expression_capability(rest)
        self.assertEqual(("Nap", "background_idle_yawn"),
                         (cap.state, cap.oem_expression_evidence))
        self.assertFalse(cap.named_state_command_available)
        self.assertFalse(cap.hardware_verified)

    def test_existing_petting_coo_owned_by_oem_never_replayed(self):
        hint = self.event()
        self.assertEqual("oem_owned", hint.status)
        cap = inspect_expression_capability(self.portrait, hint=hint)
        self.assertEqual("Petted", cap.state)
        self.assertEqual("conditional_oem_petting_coo",
                         cap.oem_expression_evidence)
        self.assertEqual("mock_oem_expression_hint", cap.selected_from)
        self.assertEqual(0, cap.speaker_commands_issued)
        self.assertEqual(0, cap.motor_commands_issued)
        self.assertFalse(cap.expression_executed)
        self.assertFalse(cap.hardware_verified)

    def test_unexpected_noise_startle_has_no_oem_expression_proof(self):
        hint = self.event("ambient_noise")
        self.assertEqual("hypothesis", hint.status)
        cap = inspect_expression_capability(self.portrait, hint=hint)
        self.assertEqual("Startle", cap.state)
        self.assertEqual("none", cap.oem_expression_evidence)
        self.assertFalse(cap.named_state_command_available)
        self.assertFalse(cap.expression_executed)

    def test_voice_notice_is_not_speech_or_qwen(self):
        hint = self.event("ambient_voice")
        self.assertEqual("notice_only", hint.status)
        cap = inspect_expression_capability(self.portrait, hint=hint)
        self.assertEqual("Chill", cap.state)
        self.assertEqual(0, cap.pc_requests_issued)
        self.assertEqual(0, cap.speaker_commands_issued)
        self.assertFalse(cap.expression_executed)

    def test_stop_busy_and_no_opt_in_cues_do_not_select_new_state(self):
        for ctx, flags in (
            (consent(), MockOemConditions(stop_requested=True)),
            (consent(), MockOemConditions(busy=True)),
            (consent(), MockOemConditions(fallen=True)),
            (consent(operator_opt_in=False), MockOemConditions()),
            (consent(quiet_mode=True), MockOemConditions()),
        ):
            with self.subTest(ctx=ctx, flags=flags):
                hint = self.event(consent_flags=ctx, conditions=flags)
                self.assertEqual("silent", hint.status)
                cap = inspect_expression_capability(self.portrait, hint=hint)
                self.assertEqual(self.portrait.state, cap.state)
                self.assertEqual(0, cap.motor_commands_issued)

    def test_stale_or_future_cue_cannot_select_petted(self):
        for at in (NOW-100, NOW+.001):
            with self.subTest(at=at):
                hint = self.event(at=at)
                self.assertEqual("silent", hint.status)
                self.assertEqual(
                    "Chill",
                    inspect_expression_capability(self.portrait, hint=hint).state,
                )

    def test_cross_portrait_hint_mismatch_is_rejected(self):
        hint = self.event()
        other = self.brain.describe_behavior(
            PassiveIntent("rest", "low_simulated_motivational_energy"),
            journal=self.journal, now_wall_epoch_s=WALL,
        )
        with self.assertRaises(ValueError):
            inspect_expression_capability(other, hint=hint)

    def test_unexpected_types_and_unknown_state_are_rejected(self):
        for name in ("Unknown", "Kwirou", "kick", "Pet", "", None, 1, True):
            with self.subTest(name=name), self.assertRaises(ValueError):
                expression_capability_for(name)
        with self.assertRaises(TypeError):
            inspect_expression_capability("Chill")
        with self.assertRaises(TypeError):
            inspect_expression_capability(self.portrait, hint="Petted")
        with self.assertRaises(ValueError):
            expression_capability_for("Chill", selected_from="robotd_confirmed")

    def test_forged_commands_and_false_oem_status_are_rejected(self):
        cap = expression_capability_for("Petted")
        for forged in (
            {"named_state_command_available": True},
            {"expression_executed": True},
            {"hardware_verified": True},
            {"physical_execution_authorized": True},
            {"motor_commands_issued": 1},
            {"speaker_commands_issued": 1},
            {"pc_requests_issued": 1},
            {"memories_written": 1},
            {"source": "robotd_real"},
            {"oem_expression_evidence": "state_machine_installed"},
            {"oem_evidence_path": None},
            {"companion_status": "mock_description_only"},
            {"selected_from": "sensor"},
            {"motor_commands_issued": False},
        ):
            with self.subTest(forged=forged), self.assertRaises(ValueError):
                replace(cap, **forged)

    def test_inventory_is_pure_and_does_not_change_sqlite_schema(self):
        self.assertEqual(0, self.memory.conn.total_changes)
        tables_before = self.memory.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        for _ in range(20):
            items = expression_capability_catalog()
            self.assertEqual(16, len(items))
            inspect_expression_capability(self.portrait)
            hint = self.event()
            inspect_expression_capability(self.portrait, hint=hint)
        tables_after = self.memory.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        self.assertEqual(tables_before, tables_after)
        self.assertEqual(0, self.memory.conn.total_changes)
        self.assertEqual(0, self.memory.experience_count())

    def test_read_only_static_catalog_stable_after_restart(self):
        first = expression_capability_catalog()
        self.memory.close()
        other = ExperienceMemory(self.path)
        try:
            self.assertEqual(first, expression_capability_catalog())
            self.assertEqual(0, other.experience_count())
        finally:
            other.close()


if __name__ == "__main__":
    unittest.main()
