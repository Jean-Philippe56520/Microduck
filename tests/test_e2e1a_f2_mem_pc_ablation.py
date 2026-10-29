"""E2E-1A: executed F2 + MEM-1/EX1 + F5-A boundary, all scenes FAKE.

New scripts are held apart from existing specific test functions, but these
are NEVER independent pictures, camera reads, a Qwen-9B evaluation or real
effects. Here "PC on" is deliberately a locally crafted unverified JSON.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from microduck_companion.autonomy import AutonomyBrain, Motivations
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_ledger import MockExperienceLedger
from microduck_companion.mock_goal_memory import MockGoalMemory
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot
from microduck_companion.pc_hypothesis_contract import (
    finish_optional_pc_cycle, start_optional_pc_cycle,
)

WALL = 1_780_700_000.0
MONO = 120.0
GOAL = "g-0000000000000e21"
SESSION = "s-0000000000000e21"


def frame(*labels: str, source="mock", environment="mock",
          observed=MONO, status="ok", seq=7) -> PassiveRead:
    """Distinct labels in one mock image; track strings are NOT identities."""
    events = tuple(PerceptionEvent(
        "object_label", label, source, observed, 1., .96,
        track_id=f"ephemeral-fixture-{i}",
    ) for i, label in enumerate(labels))
    return PassiveRead(
        status, PerceptionSnapshot(environment, events, observed), seq,
        "mock_fixture_unix",
    )


def mock_reply(request, *, category="cat", confidence=.99, extra=None):
    data = {
        "schema_version": 1, "request_id": request.request_id,
        "source": "pc_qwen_unverified",
        "hypotheses": [{
            "kind": "object_label", "category": category,
            "confidence": confidence, "ttl_s": .5,
        }],
    }
    if extra:
        data.update(extra)
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


class E2E1AIntegratedF2MemF5Tests(unittest.TestCase):
    """Each lane runs real code over its OWN sole fixture-only SQLite."""

    def lane(self, scene, *, memory_on, determination, pc_on):
        with tempfile.TemporaryDirectory() as tmp:
            db = ExperienceMemory(Path(tmp) / "single.sqlite3")
            try:
                journal = PassiveObservationJournal(db)
                goals = None
                if memory_on:
                    ledger = MockExperienceLedger(db)
                    goals = MockGoalMemory(db, ledger)
                    if scene in ("competing", "attempted"):
                        goals.create(
                            goal_id=GOAL, kind="observe_category",
                            category="cat", resume_when="new_view",
                            at_epoch_s=WALL)
                        goals.transition(
                            goal_id=GOAL, expected_revision=1,
                            next_state="active", reason="begin_mock_goal",
                            at_epoch_s=WALL+.1)
                    if scene == "attempted":
                        ledger.record_proposal(
                            PassiveIntent("observe", "fixture-only",
                                          "object_label", "cat"),
                            session=SESSION, sequence=1,
                            proposed_at_epoch_s=WALL+.5)
                        goals.link_attempt(
                            goal_id=GOAL, session=SESSION, sequence=1,
                            strategy="observe_from_distance",
                            context="initial", at_epoch_s=WALL+.75)
                motivations = Motivations(determination=determination)
                if scene == "rest":
                    motivations.energy = .15
                brain = AutonomyBrain(db, motivations)
                if scene == "competing":
                    read = frame("cat", "toy")
                elif scene == "attempted":
                    read = frame("cat")
                elif scene == "uncertain":
                    read = frame("unknown")
                elif scene == "stale":
                    read = frame("toy", observed=MONO-4)
                elif scene == "rest":
                    read = frame("toy")
                else:
                    raise ValueError("unregistered fictional scene")
                before = db.conn.total_changes
                # The request and reply live entirely INSIDE the host test;
                # patching socket proves no real PC/robot/network can be used.
                with patch("socket.socket", side_effect=AssertionError(
                        "network is forbidden in E2E-1A")):
                    cycle = start_optional_pc_cycle(
                        brain, read, journal=journal,
                        now_monotonic_s=MONO+.1, now_wall_epoch_s=WALL+1,
                        goals=goals, guard_attempted_goals=bool(memory_on))
                    wire = None
                    if cycle.request is not None and pc_on:
                        wire = mock_reply(cycle.request)
                    if cycle.request is not None:
                        done = finish_optional_pc_cycle(
                            cycle, wire, received_monotonic_s=MONO+.3)
                    else:
                        done = cycle
                self.assertEqual(before, db.conn.total_changes,
                                 "a decision/PC suggestion may not write SQL")
                self.assertEqual(0, db.experience_count())
                self.assertEqual(0, done.motor_commands_issued)
                self.assertEqual(0, done.speaker_commands_issued)
                self.assertFalse(done.local_intent.executed)
                self.assertFalse(done.local_intent.request_pc_analysis)
                self.assertEqual(cycle.local_intent, done.local_intent)
                self.assertFalse(any(h.verified or h.identity_verified
                                     or h.physical_actions_authorized
                                     for h in done.hypotheses))
                if done.request is not None:
                    sent = done.request.to_wire().decode("utf-8")
                    self.assertNotIn("ephemeral-fixture", sent)
                    self.assertNotIn("g-0000000000000e21", sent)
                    self.assertNotIn("cat", sent)  # no known category leak
                return {
                    "intent": done.local_intent.intention,
                    "target": done.local_intent.target_category,
                    "reason": done.local_intent.reason,
                    "status": done.status,
                    "hypotheses": len(done.hypotheses),
                    "energy": brain.motives.energy,
                    "cycles": brain.passive_rhythm_metrics().cycles,
                    "pc_transports_real": 0,
                    "physical_effects_verified": 0,
                }
            finally:
                db.close()

    def test_full_eight_lanes_competing_categories_mem_det_pc(self):
        outcomes = {}
        for remembered in (False, True):
            for determination in (0., 1.):
                for pc in (False, True):
                    outcomes[(remembered, determination, pc)] = self.lane(
                        "competing", memory_on=remembered,
                        determination=determination, pc_on=pc)
        self.assertEqual(8, len(outcomes))
        for mem in (False, True):
            for det in (0., 1.):
                a, b = outcomes[(mem, det, False)], outcomes[(mem, det, True)]
                self.assertEqual((a["intent"], a["target"], a["reason"]),
                                 (b["intent"], b["target"], b["reason"]))
                self.assertEqual(0, a["hypotheses"] + b["hypotheses"])
                self.assertEqual("not_needed", b["status"])
        self.assertEqual("toy", outcomes[(False, 1., False)]["target"])
        self.assertEqual("toy", outcomes[(True, 0., False)]["target"])
        self.assertEqual(
            ("observe", "cat", "det1_mock_goal_focus"),
            tuple(outcomes[(True, 1., True)][k]
                  for k in ("intent", "target", "reason")))
        self.assertEqual(8, sum(x["cycles"] for x in outcomes.values()))
        self.assertEqual(0, sum(x["pc_transports_real"] for x in outcomes.values()))

    def test_full_eight_lanes_attempted_goal_is_held_only_with_memory(self):
        outcomes = {(m, d, p): self.lane(
            "attempted", memory_on=m, determination=d, pc_on=p)
            for m in (False, True) for d in (0., 1.) for p in (False, True)}
        self.assertEqual(8, len(outcomes))
        for (m, det, pc), row in outcomes.items():
            self.assertEqual("idle" if m else "observe", row["intent"])
            self.assertEqual(None if m else "cat", row["target"])
            self.assertEqual("not_needed", row["status"])
            self.assertEqual(0, row["hypotheses"])
            self.assertEqual(0, row["physical_effects_verified"])
        self.assertEqual(
            [("observe", "idle")]*2,
            [(outcomes[(False, d, pc)]["intent"],
              outcomes[(True, d, pc)]["intent"])
             for d, pc in ((0., False), (1., True))])

    def test_full_eight_lanes_uncertain_pc_reply_is_never_local_fact(self):
        outcomes = {(m, d, p): self.lane(
            "uncertain", memory_on=m, determination=d, pc_on=p)
            for m in (False, True) for d in (0., 1.) for p in (False, True)}
        self.assertEqual(8, len(outcomes))
        for (mem, det, pc), row in outcomes.items():
            self.assertEqual(("inspect", "unknown"),
                             (row["intent"], row["target"]))
            self.assertEqual("hypotheses_unverified" if pc else "pc_unavailable",
                             row["status"])
            self.assertEqual(1 if pc else 0, row["hypotheses"])
            self.assertEqual(0, row["pc_transports_real"])
            self.assertEqual(0, row["physical_effects_verified"])
            self.assertEqual(row["energy"], outcomes[(mem, det, not pc)]["energy"])
        self.assertEqual(4, sum(x["hypotheses"] for x in outcomes.values()))

    def test_forged_or_delayed_pc_claims_cannot_promote_an_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = ExperienceMemory(Path(tmp)/"only.sqlite3")
            try:
                brain=AutonomyBrain(db)
                journal=PassiveObservationJournal(db)
                cycle=start_optional_pc_cycle(
                    brain, frame("unknown"),journal=journal,
                    now_monotonic_s=MONO+.1, now_wall_epoch_s=WALL+1)
                self.assertEqual("pending_transport",cycle.status)
                assert cycle.request is not None
                before=db.conn.total_changes
                fake_wires=(
                    mock_reply(cycle.request, category="person"),
                    mock_reply(cycle.request, extra={"motor_commands": 1}),
                    mock_reply(cycle.request, extra={"source":"sensor"}),
                    mock_reply(cycle.request, extra={"request_id":"0"*32}),
                )
                for wire in fake_wires:
                    with self.subTest(wire=wire):
                        done=finish_optional_pc_cycle(
                            cycle,wire,received_monotonic_s=MONO+.3)
                        self.assertEqual("response_rejected",done.status)
                        self.assertEqual(cycle.local_intent,done.local_intent)
                        self.assertEqual((),done.hypotheses)
                late=finish_optional_pc_cycle(
                    cycle,mock_reply(cycle.request),
                    received_monotonic_s=MONO+5.)
                self.assertEqual("response_rejected",late.status)
                self.assertEqual(before,db.conn.total_changes)
                self.assertEqual(0,db.experience_count())
            finally:
                db.close()

    def test_invalid_and_low_energy_lanes_are_independent_of_pc(self):
        for scene in ("stale","rest"):
            outcomes={(m,d,p): self.lane(
                scene,memory_on=m,determination=d,pc_on=p)
                for m in (False,True) for d in (0.,1.) for p in (False,True)}
            self.assertEqual(8,len(outcomes))
            expected="rest" if scene=="rest" else "idle"
            for row in outcomes.values():
                self.assertEqual(expected,row["intent"])
                self.assertEqual("not_needed",row["status"])
                self.assertEqual(0,row["hypotheses"])
                self.assertEqual(0,row["physical_effects_verified"])
                self.assertEqual(0,row["pc_transports_real"])

    def test_options_forward_fail_closed_on_untrusted_and_foreign_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=ExperienceMemory(Path(tmp)/"one.sqlite3")
            other=ExperienceMemory(Path(tmp)/"other.sqlite3")
            try:
                journal=PassiveObservationJournal(db)
                foreign=MockGoalMemory(other,MockExperienceLedger(other))
                brain=AutonomyBrain(db)
                with self.assertRaises(ValueError):
                    start_optional_pc_cycle(
                        brain,frame("cat"),journal=journal,
                        now_monotonic_s=MONO+.1,now_wall_epoch_s=WALL+1,
                        goals=foreign,guard_attempted_goals=True)
                with self.assertRaises(ValueError):
                    start_optional_pc_cycle(
                        brain,frame("cat"),journal=journal,
                        now_monotonic_s=MONO+.1,now_wall_epoch_s=WALL+1,
                        guard_attempted_goals=True)
                with self.assertRaises(TypeError):
                    start_optional_pc_cycle(
                        brain,frame("cat"),journal=journal,
                        now_monotonic_s=MONO+.1,now_wall_epoch_s=WALL+1,
                        personality_pacing="true")
                # An untrusted sensor label cannot be granted a mock consult.
                valid=start_optional_pc_cycle(
                    brain,frame("unknown",source="sensor"),
                    journal=journal,now_monotonic_s=MONO+.1,
                    now_wall_epoch_s=WALL+1)
                self.assertEqual("idle",valid.local_intent.intention)
                self.assertEqual("not_needed",valid.status)
                self.assertIsNone(valid.request)
            finally:
                db.close()
                other.close()


if __name__ == "__main__":
    unittest.main()
