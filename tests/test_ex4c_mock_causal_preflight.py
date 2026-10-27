"""EX4-C: mock causal cross-check. No physical execution or reward is possible."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_ledger import MockExperienceLedger, MockResolution
from microduck_companion.experience_effects import MockCue, MockEffectJournal, MockEffectPair
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.ex4_evidence_audit import ExecutionEvidenceAudit
from microduck_companion.ex4b_oem_wire_audit import OemWireFrame, OemWireProposal
from microduck_companion.ex4c_mock_causal_preflight import (
    ScriptedStage, MockCausalPreflight, MAX_EVENTS, MAX_BATCH,
)

WALL = 1_780_000_000.
SESSION = "s-0000000000000001"
SESSION2 = "s-0000000000000002"


def wire(*, session=SESSION, sequence=1, rpc_id=11, method="robot.do"):
    params = {
        "robot.do": {"skill": "kick_left"},
        "robot.stop": {},
        "robot.look": {"x": .25, "y": 0., "z": .15},
        "robot.move": {"vx": .1, "vy": 0., "vyaw": 0.},
        "robot.head": {
            "neck_pitch": 0., "head_pitch": .1,
            "head_yaw": .2, "head_roll": 0.,
        },
    }[method]
    p = {"jsonrpc": "2.0", "method": method, "params": params}
    if rpc_id is not None:
        p["id"] = rpc_id
    return OemWireProposal(session=session, sequence=sequence,
                           sent_monotonic_s=10., packet=p)


def reply(*, rpc_id=11, accepted=True):
    return OemWireFrame(12., {
        "jsonrpc": "2.0", "id": rpc_id,
        "result": {"accepted": accepted, **(
            {} if accepted else {"reason": "disabled"}
        )},
    })


def state(*, limited=False, fallen=False, t=8., ns=8_000_000_000, at=13.):
    return OemWireFrame(at, {
        "jsonrpc": "2.0", "method": "robot.state", "params": {
            "t": t, "t_ns": ns,
            "move": {
                "requested": [.1, 0., 0.],
                "applied": [0. if limited else .1, 0., 0.],
                "limited_by": ["deadman"] if limited else [],
            },
            "policy": "walk",
            "safety": {"fallen": fallen, "limp": False},
            "loop": {"hz": 50., "missed": 0},
        },
    })


def stages(*, session=SESSION, sequence=1, rpc_id=11,
           start=WALL + .25, end=WALL + 1.5, last="completed"):
    return (
        ScriptedStage(session, sequence, rpc_id, 1, "started", start),
        ScriptedStage(session, sequence, rpc_id, 2, last, end),
    )


class Ex4cMockCausalPreflightTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = Path(temp.name) / "episodes.db"
        self.memory = ExperienceMemory(self.db)
        self.addCleanup(self.memory.close)
        self.audit = ExecutionEvidenceAudit(self.memory)
        self.preflight = MockCausalPreflight(self.audit)
        self.ledger = MockExperienceLedger(self.memory)
        self.effects = None

    def seed(self, *, session=SESSION, sequence=1, status="mock_executed",
             after="moving", competing=False, same_scene=True,
             confidence=.9, before_at=WALL-.5, after_at=WALL+2.5):
        self.assertTrue(self.ledger.record_proposal(
            PassiveIntent("observe", "synthetic only", "object_label", "ball"),
            session=session, sequence=sequence, proposed_at_epoch_s=WALL,
        ))
        if status != "proposed":
            self.assertTrue(self.ledger.resolve(MockResolution(
                session, sequence, status, WALL+2,
            )))
        if status == "mock_executed" and after is not None:
            if self.effects is None:
                self.effects = MockEffectJournal(self.ledger)
            self.assertTrue(self.effects.record(MockEffectPair(
                session, sequence,
                MockCue("motion", "still", before_at, confidence),
                MockCue("motion", after, after_at, confidence),
                same_scene, competing,
            )))

    def review(self, *, p=None, r="default", fr=(), ev=None, now=WALL+3):
        if r == "default":
            r = reply()
        if ev is None:
            ev = stages()
        return self.preflight.review(
            p if p is not None else wire(),
            reply=r, states=fr, stages=ev,
            now_monotonic_s=15., now_epoch_s=now,
        )

    def assert_no_robot(self, v):
        self.assertEqual("not_attested", v.authorized)
        self.assertEqual("not_attested", v.executed)
        self.assertFalse(v.observations_authenticated)
        self.assertFalse(v.physical_execution_verified)
        self.assertFalse(v.causality_established)
        self.assertFalse(v.physical_learning_allowed)
        self.assertEqual(0, v.motor_commands_issued)
        self.assertNotIn("reward", asdict(v))
        self.assertEqual("mock_fixture_crosscheck_only", v.source)

    def test_synthetic_chain_consistent_but_not_causal(self):
        self.seed()
        v = self.review()
        self.assertEqual(("mock_completed_only", "temporal_only", "mock_temporal_only"),
                         (v.stage_status, v.effect_status, v.status))
        self.assert_no_robot(v)

    def test_original_oem_ack_stays_only_queued(self):
        self.seed()
        v = self.review()
        self.assertEqual("queued_only", v.wire_status)
        self.assert_no_robot(v)

    def test_confounded_change_not_a_reward(self):
        self.seed(competing=True)
        v = self.review()
        self.assertEqual("mock_confounded", v.status)
        self.assertEqual("confounded", v.effect_status)
        self.assert_no_robot(v)

    def test_identical_cue_not_a_consequence(self):
        self.seed(after="still")
        v = self.review()
        self.assertEqual("mock_unchanged", v.status)
        self.assertEqual("no_change", v.effect_status)
        self.assert_no_robot(v)

    def test_different_scene_is_indeterminate(self):
        self.seed(same_scene=False)
        v = self.review()
        self.assertEqual("mock_indeterminate", v.status)
        self.assert_no_robot(v)

    def test_unknown_cue_is_indeterminate(self):
        self.seed(after="unknown")
        v = self.review()
        self.assertEqual("mock_indeterminate", v.status)
        self.assert_no_robot(v)

    def test_low_confidence_is_indeterminate(self):
        self.seed(confidence=.5)
        v = self.review()
        self.assertEqual("mock_indeterminate", v.status)
        self.assert_no_robot(v)

    def test_no_effect_table_remains_missing(self):
        self.seed(after=None)
        v = self.review()
        self.assertEqual("mock_no_effect", v.status)
        self.assertEqual("not_observed", v.effect_status)
        self.assert_no_robot(v)

    def test_queued_without_scripted_stages(self):
        self.seed()
        v = self.review(ev=())
        self.assertEqual("no_scripted_stages", v.status)
        self.assert_no_robot(v)

    def test_started_without_completed_is_incomplete(self):
        self.seed()
        v = self.review(ev=stages()[:1])
        self.assertEqual("mock_incomplete", v.status)
        self.assert_no_robot(v)

    def test_started_then_interrupted_is_not_learned(self):
        self.seed()
        v = self.review(ev=stages(last="interrupted"))
        self.assertEqual("mock_interrupted", v.status)
        self.assert_no_robot(v)

    def test_unresolved_ex1_not_promoted(self):
        self.seed(status="proposed", after=None)
        v = self.review(ev=())
        self.assertEqual("unresolved_mock_proposal", v.status)
        self.assert_no_robot(v)
        with self.assertRaises(ValueError):
            self.review()

    def test_missing_ex1_not_promoted(self):
        v = self.review(ev=())
        self.assertEqual("missing_mock_history", v.status)
        self.assert_no_robot(v)
        with self.assertRaises(ValueError):
            self.review()

    def test_explicitly_refused_ex1(self):
        self.seed(status="refused", after=None)
        event = (ScriptedStage(SESSION, 1, 11, 1, "refused", WALL+1),)
        v = self.review(r=reply(accepted=False), ev=event)
        self.assertEqual("refused", v.status)
        self.assert_no_robot(v)

    def test_explicitly_interrupted_ex1(self):
        self.seed(status="interrupted", after=None)
        event = (ScriptedStage(SESSION, 1, 11, 1, "interrupted", WALL+1),)
        v = self.review(ev=event)
        self.assertEqual("interrupted", v.status)
        self.assert_no_robot(v)

    def test_refused_ex1_with_claimed_execution_is_rejected(self):
        self.seed(status="refused", after=None)
        with self.assertRaises(ValueError):
            self.review()

    def test_refusal_outside_ex1_times_rejected(self):
        self.seed(status="refused", after=None)
        e = (ScriptedStage(SESSION, 1, 11, 1, "refused", WALL+5),)
        with self.assertRaises(ValueError):
            self.review(ev=e, now=WALL+6)

    def test_oem_refusal_overrides_mock_claim(self):
        self.seed()
        v = self.review(r=reply(accepted=False), ev=())
        self.assertEqual("oem_refused", v.status)
        self.assert_no_robot(v)
        with self.assertRaises(ValueError):
            self.review(r=reply(accepted=False))

    def test_no_reply_cannot_be_upgraded_by_script(self):
        self.seed()
        v = self.review(r=None, ev=())
        self.assertEqual("unanswered_or_error", v.status)
        self.assert_no_robot(v)
        with self.assertRaises(ValueError):
            self.review(r=None)

    def test_no_id_notification_cannot_be_upgraded(self):
        self.seed()
        v = self.review(p=wire(rpc_id=None), r=None, ev=())
        self.assertEqual("unanswered_or_error", v.status)
        self.assert_no_robot(v)
        with self.assertRaises(ValueError):
            self.review(p=wire(rpc_id=None), r=None)

    def test_robot_look_is_not_action_completion(self):
        self.seed()
        v = self.review(p=wire(method="robot.look"), r=None, ev=())
        self.assertEqual("no_skill_lifecycle", v.status)
        self.assert_no_robot(v)
        with self.assertRaises(ValueError):
            self.review(p=wire(method="robot.look"), r=None)

    def test_robot_move_is_not_action_completion(self):
        self.seed()
        v = self.review(p=wire(method="robot.move",rpc_id=None), r=None, ev=())
        self.assertEqual("no_skill_lifecycle", v.status)
        self.assert_no_robot(v)
        with self.assertRaises(ValueError):
            self.review(p=wire(method="robot.move",rpc_id=None), r=None)

    def test_mismatched_stage_session_rejected(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.review(ev=stages(session=SESSION2))

    def test_mismatched_stage_sequence_rejected(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.review(ev=stages(sequence=2))

    def test_mismatched_rpc_id_rejected(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.review(ev=stages(rpc_id=12))

    def test_noncontiguous_event_numbers_rejected(self):
        self.seed()
        ev = (
            ScriptedStage(SESSION,1,11,1,"started",WALL+.25),
            ScriptedStage(SESSION,1,11,3,"completed",WALL+1.5),
        )
        with self.assertRaises(ValueError):
            self.review(ev=ev)

    def test_reversed_event_times_rejected(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.review(ev=stages(start=WALL+1.9,end=WALL+1))

    def test_future_stage_rejected(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.review(ev=stages(start=WALL+.2,end=WALL+10))

    def test_started_before_ex1_rejected(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.review(ev=stages(start=WALL-10,end=WALL+1))

    def test_partial_stage_before_ex1_rejected(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.review(ev=stages(start=WALL-10)[:1])

    def test_completed_after_ex1_resolution_rejected(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.review(ev=stages(end=WALL+2.4))

    def test_unsupported_scripted_state_machine_rejected(self):
        self.seed()
        event = (ScriptedStage(SESSION,1,11,1,"completed",WALL+1),)
        with self.assertRaises(ValueError):
            self.review(ev=event)

    def test_duplicate_stage_name_rejected(self):
        self.seed()
        event = (
            ScriptedStage(SESSION,1,11,1,"started",WALL+.2),
            ScriptedStage(SESSION,1,11,2,"started",WALL+.3),
        )
        with self.assertRaises(ValueError):
            self.review(ev=event)

    def test_stage_fake_source_is_refused(self):
        with self.assertRaises(ValueError):
            ScriptedStage(SESSION,1,11,1,"started",WALL+.2,source="robotd")

    def test_stage_boolean_rpc_and_event_number_rejected(self):
        for kwargs in (
            {"rpc_id": True}, {"event_number": True}, {"sequence": True},
            {"stage": "executed"}, {"at_epoch_s": float("nan")},
        ):
            values = {
                "session": SESSION, "sequence": 1, "rpc_id": 11,
                "event_number": 1, "stage": "started",
                "at_epoch_s": WALL+.2,
            }
            values.update(kwargs)
            with self.subTest(**kwargs), self.assertRaises(ValueError):
                ScriptedStage(**values)

    def test_simulated_unsafe_state_cannot_promote(self):
        self.seed()
        v = self.review(fr=(state(fallen=True),))
        self.assertEqual("unsafe_or_limited_wire", v.status)
        self.assert_no_robot(v)

    def test_simulated_limited_state_cannot_promote(self):
        self.seed()
        v = self.review(fr=(state(limited=True),))
        self.assertEqual("unsafe_or_limited_wire", v.status)
        self.assert_no_robot(v)

    def test_coherent_state_is_still_not_physical_proof(self):
        self.seed()
        v = self.review(fr=(state(),))
        self.assertEqual("mock_temporal_only", v.status)
        self.assert_no_robot(v)

    def test_corrupt_ex2_annotation_refused(self):
        self.seed()
        with self.memory.conn:
            self.memory.conn.execute(
                "UPDATE ex2_mock_effects SET after_value='still'"
            )
        v = self.review()
        self.assertEqual("invalid_mock_history", v.status)
        self.assert_no_robot(v)

    def test_retracted_ex1_no_longer_used(self):
        self.seed()
        self.assertTrue(self.ledger.retract(
            session=SESSION,sequence=1,reason="source_retracted"
        ))
        v = self.review()
        self.assertEqual("withdrawn",v.status)
        self.assert_no_robot(v)

    def test_withdrawn_history_still_rejects_unmatched_mock_rpc(self):
        self.seed()
        self.ledger.retract(
            session=SESSION, sequence=1, reason="source_retracted",
        )
        with self.assertRaises(ValueError):
            self.review(ev=stages(rpc_id=999))

    def test_retracted_ex2_no_longer_used(self):
        self.seed()
        self.assertTrue(self.effects.retract(
            session=SESSION,sequence=1,reason="fixture_annotation_error"
        ))
        v = self.review()
        self.assertEqual("withdrawn_effect",v.status)
        self.assert_no_robot(v)

    def test_persists_retractions_across_database_reopen(self):
        self.seed()
        self.effects.retract(
            session=SESSION,sequence=1,reason="source_retracted",
        )
        self.memory.close()
        self.memory = ExperienceMemory(self.db)
        self.addCleanup(self.memory.close)
        self.audit = ExecutionEvidenceAudit(self.memory)
        self.preflight = MockCausalPreflight(self.audit)
        v = self.review()
        self.assertEqual("withdrawn_effect",v.status)
        self.assert_no_robot(v)

    def test_one_sqlite_and_no_write_or_schema_growth(self):
        self.seed()
        tables = tuple(self.memory.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall())
        changes = self.memory.conn.total_changes
        for _ in range(5):
            self.assert_no_robot(self.review())
        self.assertEqual(changes,self.memory.conn.total_changes)
        self.assertEqual(tables,tuple(self.memory.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()))
        self.assertIs(self.preflight._audit._memory,self.memory)

    def test_no_experience_or_physical_preference_changes(self):
        self.seed()
        before = self.memory.experience_count()
        prior_pref = self.memory.intent_preference("robot","explore")
        self.assert_no_robot(self.review())
        self.assertEqual(before,self.memory.experience_count())
        self.assertEqual(prior_pref,self.memory.intent_preference("robot","explore"))

    def test_batch_independent_cycles(self):
        self.seed(session=SESSION,sequence=1)
        self.seed(session=SESSION2,sequence=2)
        inputs = (
            (wire(session=SESSION,sequence=1,rpc_id=11),reply(rpc_id=11),
             (),stages(session=SESSION,sequence=1,rpc_id=11)),
            (wire(session=SESSION2,sequence=2,rpc_id=12),reply(rpc_id=12),
             (),stages(session=SESSION2,sequence=2,rpc_id=12)),
        )
        results=self.preflight.review_batch(
            inputs,now_monotonic_s=15.,now_epoch_s=WALL+3
        )
        self.assertEqual(2,len(results))
        for v in results:
            self.assertEqual("mock_temporal_only",v.status)
            self.assert_no_robot(v)

    def test_batch_duplicate_cycle_rejected(self):
        self.seed()
        item=(wire(),reply(),(),stages())
        with self.assertRaises(ValueError):
            self.preflight.review_batch(
                (item,item),now_monotonic_s=15.,now_epoch_s=WALL+3
            )

    def test_batch_duplicate_rpc_in_same_session_rejected(self):
        self.seed(sequence=1)
        self.seed(sequence=2)
        inputs=(
            (wire(sequence=1,rpc_id=11),reply(),(),stages(sequence=1)),
            (wire(sequence=2,rpc_id=11),reply(),(),stages(sequence=2)),
        )
        with self.assertRaises(ValueError):
            self.preflight.review_batch(
                inputs,now_monotonic_s=15.,now_epoch_s=WALL+3
            )

    def test_batch_rejects_unbounded_inputs(self):
        self.assertEqual(32,MAX_BATCH)
        self.assertEqual(3,MAX_EVENTS)
        with self.assertRaises(ValueError):
            self.preflight.review_batch(
                tuple(() for _ in range(MAX_BATCH+1)),
                now_monotonic_s=15.,now_epoch_s=WALL+3,
            )

    def test_invalid_stage_sequence_type_rejected(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.review(ev=[*stages()])

    def test_constructor_demands_original_existing_audit(self):
        with self.assertRaises(TypeError):
            MockCausalPreflight(object())


if __name__ == "__main__":
    unittest.main()
