"""Category-first active attention is hypothetical and MOCK-only.

These checks run on fixtures, not photos, hardware, real cameras, actions
or Qwen. Every suggestion stays outside the safety/motor/SQLite write path.
"""
from __future__ import annotations

import math
import unittest

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.category_inspection import (
    MAX_FOLLOWUPS, CategoryInspectionHint, PartialVisualCue,
    suggest_category_inspection,
)
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot


NOW = 101.0
WALL = 1_770_000_000.0


def inspect_intent() -> PassiveIntent:
    return PassiveIntent(
        "inspect", "unresolved_fictional_object_category",
        "object_label", "unknown",
    )


def part(name: str, *, at: float = 100.7, conf: float = .93):
    return PartialVisualCue(name, conf, at)


def suggest(*cues, intent=None, **options):
    return suggest_category_inspection(
        inspect_intent() if intent is None else intent,
        tuple(cues), now_monotonic_s=NOW, **options,
    )


class CategoryInspectionFixtureTests(unittest.TestCase):
    def test_small_robot_hand_or_foot_does_not_verify_a_person(self):
        for clue, next_part in (("hand", "forearm"), ("foot", "leg")):
            with self.subTest(clue=clue):
                plan = suggest(part(clue))
                self.assertEqual("inspect_more", plan.status)
                self.assertEqual(("person",), plan.candidates_unverified)
                self.assertEqual(next_part, plan.look_for)
                self.assertFalse(plan.verified_category)
                self.assertEqual(0, plan.motor_commands_issued)
                self.assertEqual(0, plan.sensor_reads)

    def test_shoe_without_connected_body_is_not_evidence_person_present(self):
        plan = suggest(part("shoe"))
        self.assertEqual(("shoe",), plan.candidates_unverified)
        self.assertNotIn("person", plan.candidates_unverified)
        self.assertEqual("sole", plan.look_for)

    def test_clues_for_chair_ball_and_cat_dog_stay_unverified(self):
        scenarios = (
            ("furniture_leg", ("chair",), "seat"),
            ("round_edge", ("ball",), "round_outline"),
            ("fur", ("cat", "dog"), "head_outline"),
            ("paw", ("cat", "dog"), "head_outline"),
        )
        for clue, expected, next_part in scenarios:
            with self.subTest(clue=clue):
                plan = suggest(part(clue))
                self.assertEqual(expected, plan.candidates_unverified)
                self.assertEqual(next_part, plan.look_for)
                self.assertEqual("inspect_more", plan.status)
                self.assertFalse(plan.physical_source_verified)

    def test_continuity_is_required_to_narrow_several_cues(self):
        fur, whiskers = part("fur"), part("whiskers")
        separate = suggest(fur, whiskers, visual_continuity_supported=False)
        linked = suggest(fur, whiskers, visual_continuity_supported=True)
        self.assertEqual(("cat", "dog"), separate.candidates_unverified)
        self.assertEqual(("cat",), linked.candidates_unverified)
        self.assertFalse(linked.verified_category)
        self.assertEqual("head_outline", linked.look_for)

    def test_contradictory_connected_parts_never_form_new_identity(self):
        linked = suggest(
            part("hand"), part("furniture_leg"),
            visual_continuity_supported=True,
        )
        self.assertEqual("keep_unknown", linked.status)
        self.assertEqual((), linked.candidates_unverified)
        self.assertEqual("contradictory_connected_parts", linked.reason)
        separate = suggest(
            part("hand"), part("furniture_leg"),
            visual_continuity_supported=False,
        )
        self.assertEqual(("chair", "person"),
                         separate.candidates_unverified)
        self.assertFalse(separate.verified_category)

    def test_no_selected_f2_inspect_means_no_active_proposal(self):
        for intent in (
            PassiveIntent("idle", "not_interested"),
            PassiveIntent("rest", "low_simulated_motivational_energy"),
            PassiveIntent(
                "observe", "a_category_is_already_known", "object_label", "cat",
            ),
        ):
            with self.subTest(intention=intent.intention):
                plan = suggest(part("hand"), intent=intent)
                self.assertEqual("keep_unknown", plan.status)
                self.assertIsNone(plan.look_for)

    def test_current_cue_requirements_fail_closed(self):
        self.assertEqual("keep_unknown", suggest().status)
        for cue in (
            part("hand", at=98.0),
            part("hand", at=102.0),
            part("hand", conf=.40),
        ):
            self.assertEqual(
                "keep_unknown", suggest(cue).status)
            self.assertIsNone(suggest(cue).look_for)

    def test_no_automatic_qwen_even_after_two_attempts(self):
        candidate = suggest(
            part("round_edge"), followups_used=MAX_FOLLOWUPS,
            optional_pc_consent=True)
        self.assertEqual("pc_review_candidate", candidate.status)
        self.assertEqual("optional_f5_permission_and_quota_still_required",
                         candidate.reason)
        self.assertEqual(0, candidate.pc_requests_issued)
        self.assertIsNone(candidate.look_for)
        denied = suggest(
            part("round_edge"), followups_used=MAX_FOLLOWUPS,
            optional_pc_consent=False)
        self.assertEqual("keep_unknown", denied.status)
        self.assertEqual(0, denied.pc_requests_issued)

    def test_person_parts_never_trigger_pc_review_from_this_module(self):
        candidate = suggest(
            part("hand"), followups_used=MAX_FOLLOWUPS,
            optional_pc_consent=True)
        self.assertEqual("keep_unknown", candidate.status)
        self.assertEqual("person_clues_cannot_trigger_pc_review",
                         candidate.reason)
        self.assertEqual(0, candidate.pc_requests_issued)

    def test_reject_unbounded_identifiers_real_sensor_and_nonfinite_cues(self):
        for args in (
            ("Nessquick", .95, 100.7),
            ("head_of_Malo", .98, 100.7),
            ("hand", math.nan, 100.7),
            ("hand", .9, math.inf),
            ("hand", 1.1, 100.7),
            ("hand", -.01, 100.7),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                PartialVisualCue(*args)
        for src in ("sensor", "llm_suggestion", "robotd", "simulator"):
            with self.subTest(src=src), self.assertRaises(ValueError):
                PartialVisualCue("paw", .99, 100.7, src)

    def test_validate_budget_types_and_proposal_fields(self):
        for budget in (-1, 3, 1.1, True):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                suggest(part("fur"), followups_used=budget)
        for now in (math.nan, math.inf, -1, True):
            with self.subTest(now=now), self.assertRaises(ValueError):
                suggest_category_inspection(
                    inspect_intent(), (part("fur"),),
                    now_monotonic_s=now)
        with self.assertRaises(ValueError):
            suggest(part("fur"), optional_pc_consent=1)
        with self.assertRaises(ValueError):
            suggest(part("fur"), visual_continuity_supported=1)
        with self.assertRaises(ValueError):
            suggest(*([part("fur")] * 5))
        with self.assertRaises(ValueError):
            CategoryInspectionHint(
                "inspect_more", ("dog",), "head_outline", "illicit",
                motor_commands_issued=1,
            )

    def test_actual_existing_f2_inspection_remains_mock_and_readonly(self):
        # Real F2 method on a mock PerceptionSnapshot, no second decision loop.
        memory = ExperienceMemory()
        self.addCleanup(memory.close)
        journal = PassiveObservationJournal(memory)
        brain = AutonomyBrain(memory)
        event = PerceptionEvent(
            "object_label", "unknown", "mock", 100.0, 2.0, .95,
            track_id="ephemeral-fixture",
        )
        receipt = PassiveRead(
            "ok", PerceptionSnapshot("mock", (event,), 100.0), 1,
            "mock_fixture_unix",
        )
        intent = brain.propose_passive(
            receipt, journal=journal, now_monotonic_s=100.5,
            now_wall_epoch_s=WALL,
        )
        self.assertEqual("inspect", intent.intention)
        plan = suggest_category_inspection(
            intent, (PartialVisualCue("hand", .92, 100.5),),
            now_monotonic_s=100.7,
        )
        self.assertEqual("inspect_more", plan.status)
        self.assertEqual("forearm", plan.look_for)
        for table in ("objects", "experiences", "passive_observation_log"):
            row = memory.conn.execute(
                f"SELECT count(*) FROM {table}").fetchone()
            self.assertEqual(0, row[0])
        self.assertFalse(plan.verified_category)
        self.assertEqual((0, 0, 0),
                         (plan.motor_commands_issued,
                          plan.pc_requests_issued, plan.memories_written))


if __name__ == "__main__":
    unittest.main()
