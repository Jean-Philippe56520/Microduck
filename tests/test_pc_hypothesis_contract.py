"""F5-A: offline-only PC contract, unverified hypotheses and local fallback."""
from __future__ import annotations

import json
import unittest

from microduck_companion.autonomy import AutonomyBrain, Motivations
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot
from microduck_companion.pc_hypothesis_contract import (
    HYPOTHESIS_CATEGORIES, MAX_REPLY_BYTES, MAX_REPLY_HYPOTHESES,
    MAX_WAIT_S, OptionalPCAdvisory, PCContractError, PCObservation, PCRequest,
    PCUnverifiedHypothesis, finish_optional_pc_cycle, parse_pc_reply,
    start_optional_pc_cycle,
)

NOW = 100.0
WALL = 1_780_000_000.0


def fixture(category="unknown", *, seq=1, now=NOW, kind="object_label",
            source="mock", status="ok", channel="mock_fixture_unix",
            environment="mock", confidence=.95, track="track-f5a"):
    ev = PerceptionEvent(
        kind, category, source, now, 1.0, confidence,
        track_id=track if kind == "object_label" else None,
    )
    return PassiveRead(
        status, PerceptionSnapshot(environment, (ev,), now),
        seq, channel,
    )


def response(request, hypotheses=None, **overrides):
    if hypotheses is None:
        hypotheses = [{
            "kind": "object_label", "category": "cat",
            "confidence": 0.74, "ttl_s": 1.0,
        }]
    body = {
        "schema_version": 1, "request_id": request.request_id,
        "source": "pc_qwen_unverified", "hypotheses": hypotheses,
    }
    body.update(overrides)
    return json.dumps(body, separators=(",", ":"), allow_nan=False).encode()


class PCContractTests(unittest.TestCase):
    def setUp(self):
        self.mem = ExperienceMemory()
        self.addCleanup(self.mem.close)
        self.journal = PassiveObservationJournal(self.mem)
        self.brain = AutonomyBrain(self.mem)

    def start(self, read=None, *, now=NOW):
        return start_optional_pc_cycle(
            self.brain, fixture() if read is None else read,
            journal=self.journal, now_monotonic_s=now,
            now_wall_epoch_s=WALL,
        )

    def test_unknown_object_offers_pc_without_waiting_or_motor(self):
        cycle = self.start()
        self.assertEqual("inspect", cycle.local_intent.intention)
        self.assertEqual("pending_transport", cycle.status)
        self.assertIsNotNone(cycle.request)
        self.assertEqual(0, cycle.motor_commands_issued)
        self.assertEqual(0, cycle.speaker_commands_issued)
        self.assertFalse(cycle.local_intent.executed)
        self.assertEqual(0, self.mem.experience_count())

    def test_offline_pc_does_not_change_local_intent(self):
        cycle = self.start()
        done = finish_optional_pc_cycle(
            cycle, None, received_monotonic_s=NOW+.2,
        )
        self.assertEqual("pc_unavailable", done.status)
        self.assertEqual(cycle.local_intent, done.local_intent)
        self.assertEqual((), done.hypotheses)
        self.assertEqual(0, self.mem.experience_count())

    def test_fake_valid_pc_reply_is_unverified_and_never_used_as_fact(self):
        cycle = self.start()
        done = finish_optional_pc_cycle(
            cycle, response(cycle.request),
            received_monotonic_s=NOW+.25,
        )
        self.assertEqual("hypotheses_unverified", done.status)
        self.assertEqual(cycle.local_intent, done.local_intent)
        self.assertEqual(1, len(done.hypotheses))
        hypothesis = done.hypotheses[0]
        self.assertEqual(("cat", .74), (
            hypothesis.category, hypothesis.claimed_confidence))
        self.assertFalse(hypothesis.verified)
        self.assertFalse(hypothesis.identity_verified)
        self.assertFalse(hypothesis.physical_actions_authorized)
        self.assertEqual(0, hypothesis.motor_commands_issued)
        self.assertEqual(0, hypothesis.speaker_commands_issued)
        self.assertEqual("pc_qwen_unverified", hypothesis.source)
        self.assertIsNone(self.mem.get("track-f5a"))
        self.assertEqual(0, self.mem.experience_count())

    def test_request_contains_only_generic_categories_no_track(self):
        cycle = self.start(fixture(track="track-private-123"))
        raw = cycle.request.to_wire().decode("utf-8")
        obj = json.loads(raw)
        self.assertEqual({
            "schema_version", "request_id", "source", "task",
            "observations", "hypotheses_are_unverified",
        }, set(obj))
        self.assertEqual("mock_fixture_unix", obj["source"])
        self.assertEqual([{
            "kind": "object_label", "category": "unknown",
            "status": "unknown", "claimed_confidence": .95,
        }], obj["observations"])
        self.assertTrue(obj["hypotheses_are_unverified"])
        self.assertNotIn("track-private", raw)
        self.assertNotIn("motor", raw)
        self.assertNotIn("sensor", raw)

    def test_conflicting_observations_are_unknown_not_two_facts(self):
        events = (
            PerceptionEvent("object_label", "dog", "mock",
                            NOW, 1., .96, track_id="track-one"),
            PerceptionEvent("object_label", "cat", "mock",
                            NOW, 1., .93, track_id="track-one"),
        )
        read = PassiveRead("ok", PerceptionSnapshot("mock", events, NOW),
                           1, "mock_fixture_unix")
        cycle = self.start(read)
        self.assertEqual("inspect", cycle.local_intent.intention)
        self.assertEqual([("unknown", "conflict")], [
            (e.category, e.status) for e in cycle.request.observations
        ])

    def test_mock_identity_and_person_category_never_sent(self):
        events = (
            PerceptionEvent("object_label", "unknown", "mock",
                            NOW, 1., .97, track_id="track-one"),
            PerceptionEvent("object_label", "person", "mock",
                            NOW, 1., .99, track_id="track-two"),
        )
        cycle = self.start(PassiveRead(
            "ok", PerceptionSnapshot("mock", events, NOW),
            1, "mock_fixture_unix"))
        self.assertEqual("inspect", cycle.local_intent.intention)
        self.assertIsNone(cycle.request)
        self.assertEqual("not_needed", cycle.status)

    def test_sensitive_sounds_prevent_PC_request(self):
        for category in ("speech", "keyword_stop",
                         "keyword_microduck", "keyword_viens"):
            with self.subTest(category=category):
                mem = ExperienceMemory()
                try:
                    brain = AutonomyBrain(mem)
                    journal = PassiveObservationJournal(mem)
                    events = (
                        PerceptionEvent("object_label", "unknown", "mock",
                                        NOW, 1., .96, track_id="track-one"),
                        PerceptionEvent("sound_label", category, "mock",
                                        NOW, 1., .96),
                    )
                    result = start_optional_pc_cycle(
                        brain, PassiveRead("ok",
                            PerceptionSnapshot("mock", events, NOW),
                            1, "mock_fixture_unix"),
                        journal=journal, now_monotonic_s=NOW,
                        now_wall_epoch_s=WALL,
                    )
                    self.assertIsNone(result.request)
                finally:
                    mem.close()

    def test_low_confidence_sensitive_raw_event_is_also_private(self):
        for kind, category in (("object_label","person"),
                               ("sound_label","speech")):
            with self.subTest(kind=kind):
                mem=ExperienceMemory()
                try:
                    journal=PassiveObservationJournal(mem)
                    events=(
                        PerceptionEvent("object_label","unknown","mock",
                                        NOW,1.,.96,track_id="track-unresolved"),
                        PerceptionEvent(kind,category,"mock",NOW,1.,.1,
                                        track_id="track-private"
                                        if kind=="object_label" else None),
                    )
                    result=start_optional_pc_cycle(
                        AutonomyBrain(mem),
                        PassiveRead("ok",
                            PerceptionSnapshot("mock",events,NOW),
                            1,"mock_fixture_unix"),
                        journal=journal,
                        now_monotonic_s=NOW,now_wall_epoch_s=WALL,
                    )
                    self.assertIsNone(result.request)
                finally:
                    mem.close()

    def test_observed_known_object_uses_local_choice_no_pc(self):
        cycle = self.start(fixture("ball"))
        self.assertEqual("observe", cycle.local_intent.intention)
        self.assertEqual("not_needed", cycle.status)
        self.assertIsNone(cycle.request)

    def test_no_pc_on_invalid_or_untrusted_source(self):
        for status, channel, source in (
            ("unavailable_or_invalid", "mock_fixture_unix", "mock"),
            ("rate_limited", "mock_fixture_unix", "mock"),
            ("ok", "wrong_channel", "mock"),
            ("ok", "mock_fixture_unix", "sensor"),
        ):
            with self.subTest(status=status, channel=channel, source=source):
                mem=ExperienceMemory()
                try:
                    r=start_optional_pc_cycle(
                        AutonomyBrain(mem),
                        fixture(status=status, channel=channel, source=source),
                        journal=PassiveObservationJournal(mem),
                        now_monotonic_s=NOW, now_wall_epoch_s=WALL,
                    )
                    self.assertIsNone(r.request)
                    self.assertEqual("not_needed", r.status)
                finally:
                    mem.close()

    def test_no_pc_if_event_stale(self):
        cycle=self.start(fixture(now=NOW-2))
        self.assertIsNone(cycle.request)
        self.assertEqual("idle",cycle.local_intent.intention)

    def test_too_many_unresolved_categories_prevents_PC_payload(self):
        events=tuple(
            PerceptionEvent("object_label", "unknown", "mock",
                            NOW, 1., .94, track_id="track-%02d" % i)
            for i in range(5))
        cycle=self.start(PassiveRead(
            "ok",PerceptionSnapshot("mock",events,NOW),1,"mock_fixture_unix"))
        self.assertEqual("inspect",cycle.local_intent.intention)
        self.assertIsNone(cycle.request)

    def test_response_forged_sensor_source_rejected(self):
        cycle=self.start()
        done=finish_optional_pc_cycle(cycle,response(
            cycle.request,source="sensor"),received_monotonic_s=NOW+.1)
        self.assertEqual("response_rejected",done.status)
        self.assertEqual((),done.hypotheses)

    def test_mismatched_correlation_rejected(self):
        cycle=self.start()
        done=finish_optional_pc_cycle(cycle,response(
            cycle.request,request_id="a"*32),received_monotonic_s=NOW+.1)
        self.assertEqual("response_rejected",done.status)

    def test_schema_version_rejected(self):
        cycle=self.start()
        for version in (2,True,None,"1"):
            with self.subTest(version=version):
                self.assertEqual("response_rejected",
                    finish_optional_pc_cycle(cycle,response(
                        cycle.request,schema_version=version),
                        received_monotonic_s=NOW+.1).status)

    def test_unexpected_action_motor_safety_fields_rejected(self):
        cycle=self.start()
        for name,value in (
            ("command","robot.move"),
            ("motor",True),
            ("safe_area",True),
            ("floor_clear",True),
            ("identity_verified",True),
            ("observations",[{"source":"sensor"}]),
            ("speaker","say hello"),
        ):
            with self.subTest(name=name):
                kw={name:value}
                self.assertEqual("response_rejected",
                    finish_optional_pc_cycle(
                        cycle,response(cycle.request,**kw),
                        received_monotonic_s=NOW+.1).status)

    def test_invalid_hypothesis_values_rejected(self):
        cycle=self.start()
        for hypo in (
            {"kind":"floor_clear","category":"cat","confidence":1.,"ttl_s":1.},
            {"kind":"object_label","category":"person","confidence":1.,"ttl_s":1.},
            {"kind":"object_label","category":"Nessquick","confidence":1.,"ttl_s":1.},
            {"kind":"object_label","category":"cat","confidence":True,"ttl_s":1.},
            {"kind":"object_label","category":"cat","confidence":-1.,"ttl_s":1.},
            {"kind":"object_label","category":"cat","confidence":1.01,"ttl_s":1.},
            {"kind":"object_label","category":"cat","confidence":1.,"ttl_s":0},
            {"kind":"object_label","category":"cat","confidence":1.,"ttl_s":6.},
            {"kind":"object_label","category":"cat","confidence":1.,"ttl_s":True},
            {"kind":"object_label","category":"cat","confidence":1.,"ttl_s":1.,"action":"move"},
        ):
            with self.subTest(hypo=hypo):
                self.assertEqual("response_rejected",
                    finish_optional_pc_cycle(cycle,response(
                        cycle.request,[hypo]),received_monotonic_s=NOW+.1).status)

    def test_nonfinite_hypothesis_is_rejected(self):
        cycle=self.start()
        raw=response(cycle.request,[])
        raw=raw.replace(b'"hypotheses":[]',
            b'"hypotheses":[{"kind":"object_label","category":"cat","confidence":NaN,"ttl_s":1}]')
        self.assertEqual("response_rejected",
            finish_optional_pc_cycle(cycle,raw,received_monotonic_s=NOW+.1).status)

    def test_too_many_hypotheses_and_duplicate_categories_refused(self):
        cycle=self.start()
        one={"kind":"object_label","category":"cat","confidence":.9,"ttl_s":1.}
        self.assertEqual("response_rejected",
            finish_optional_pc_cycle(
                cycle,response(cycle.request,[one]*(MAX_REPLY_HYPOTHESES+1)),
                received_monotonic_s=NOW+.1).status)
        self.assertEqual("response_rejected",
            finish_optional_pc_cycle(
                cycle,response(cycle.request,[one,one]),
                received_monotonic_s=NOW+.1).status)

    def test_empty_unverified_hypotheses_allowed_without_identity(self):
        cycle=self.start()
        done=finish_optional_pc_cycle(
            cycle,response(cycle.request,[]),received_monotonic_s=NOW+.1)
        self.assertEqual("hypotheses_unverified",done.status)
        self.assertEqual((),done.hypotheses)

    def test_truncated_invalid_and_duplicate_json_fields_rejected(self):
        cycle=self.start()
        examples=(
            b"",b"{",b"[]",b'{"schema_version":1,"schema_version":1}',
            response(cycle.request) + b"extra", b"\xff",
            b" "*(MAX_REPLY_BYTES+1),
        )
        for raw in examples:
            with self.subTest(raw=raw[:40]):
                self.assertEqual("response_rejected",
                    finish_optional_pc_cycle(
                        cycle,raw,received_monotonic_s=NOW+.1).status)

    def test_payload_wrong_python_type_rejected_not_interpreted(self):
        cycle=self.start()
        for raw in ('{"role":"system"}', {"role":"system"}, 1, True):
            with self.subTest(raw=raw):
                self.assertEqual("response_rejected",
                    finish_optional_pc_cycle(
                        cycle,raw,received_monotonic_s=NOW+.1).status)

    def test_late_response_rejected_with_local_fallback(self):
        cycle=self.start()
        late=finish_optional_pc_cycle(
            cycle,response(cycle.request),
            received_monotonic_s=NOW+MAX_WAIT_S+.01)
        self.assertEqual("response_rejected",late.status)
        self.assertEqual(cycle.local_intent,late.local_intent)

    def test_reply_at_exact_deadline_is_rejected_not_materialized(self):
        cycle=self.start()
        done=finish_optional_pc_cycle(
            cycle,response(cycle.request),
            received_monotonic_s=cycle.request.expires_monotonic_s)
        self.assertEqual("response_rejected",done.status)
        self.assertEqual((),done.hypotheses)

    def test_conflicting_pc_hypotheses_remain_separate_and_untrusted(self):
        cycle=self.start()
        data=[
            {"kind":"object_label","category":"dog","confidence":.95,"ttl_s":1.},
            {"kind":"object_label","category":"cat","confidence":.94,"ttl_s":1.},
        ]
        done=finish_optional_pc_cycle(
            cycle,response(cycle.request,data),
            received_monotonic_s=NOW+.1)
        self.assertEqual("hypotheses_unverified",done.status)
        self.assertEqual(2,len(done.hypotheses))
        self.assertTrue(all(not h.verified for h in done.hypotheses))
        self.assertEqual("inspect",done.local_intent.intention)
        self.assertIsNone(self.mem.get("track-f5a"))

    def test_invalid_receipt_clock_rejected(self):
        cycle=self.start()
        for stamp in (NOW-.1,True,float("nan"),float("inf"),-1.):
            with self.subTest(stamp=stamp):
                self.assertEqual("response_rejected",
                    finish_optional_pc_cycle(
                        cycle,response(cycle.request),
                        received_monotonic_s=stamp).status)

    def test_hypothesis_expires_at_local_request_deadline(self):
        cycle=self.start()
        done=finish_optional_pc_cycle(
            cycle,response(cycle.request,[{
                "kind":"object_label","category":"toy",
                "confidence":.8,"ttl_s":5.,
            }]),received_monotonic_s=NOW+.5)
        self.assertLessEqual(
            done.hypotheses[0].expires_monotonic_s,
            cycle.request.expires_monotonic_s)
        self.assertFalse(done.hypotheses[0].verified)

    def test_cannot_complete_local_only_or_completed_request(self):
        local=self.start(fixture("ball"))
        with self.assertRaises(ValueError):
            finish_optional_pc_cycle(local,None,received_monotonic_s=NOW)
        pending=PCRequest("a"*32,(PCObservation(
            "object_label","unknown","unknown",.8),),NOW,NOW+1.)
        done=finish_optional_pc_cycle(
            OptionalPCAdvisory(local.local_intent,pending,"pending_transport"),
            None,received_monotonic_s=NOW)
        with self.assertRaises(ValueError):
            finish_optional_pc_cycle(done,None,received_monotonic_s=NOW)

    def test_forged_verified_hypothesis_is_invalid(self):
        args=dict(kind="object_label",category="dog",
                  claimed_confidence=1.,received_monotonic_s=NOW,
                  expires_monotonic_s=NOW+1.)
        for key in ("verified","identity_verified","physical_actions_authorized"):
            with self.subTest(key=key),self.assertRaises(ValueError):
                PCUnverifiedHypothesis(**{**args,key:True})
        for key in ("motor_commands_issued","speaker_commands_issued"):
            with self.subTest(key=key),self.assertRaises(ValueError):
                PCUnverifiedHypothesis(**{**args,key:1})
        with self.assertRaises(ValueError):
            PCUnverifiedHypothesis(**{**args,"source":"sensor"})

    def test_bad_advisory_cannot_claim_actions_or_pc_truth(self):
        cycle=self.start()
        with self.assertRaises(ValueError):
            OptionalPCAdvisory(cycle.local_intent,cycle.request,
                               "pending_transport",motor_commands_issued=1)
        with self.assertRaises(ValueError):
            OptionalPCAdvisory(cycle.local_intent,cycle.request,
                               "pc_unavailable",hypotheses=(
                PCUnverifiedHypothesis(
                    "object_label","cat",.5,NOW,NOW+1),))

    def test_malformed_request_cannot_include_person_or_commands(self):
        for obs in (
            PCObservation("object_label","unknown","unknown",.8),
        ):
            self.assertEqual("unknown",obs.category)
        for params in (
            ("safe_area","unknown","unknown",.8),
            ("object_label","person","unknown",.8),
            ("object_label","unknown","identified",.8),
            ("object_label","unknown","unknown",float("nan")),
            ("object_label","unknown","unknown",True),
        ):
            with self.subTest(params=params),self.assertRaises(ValueError):
                PCObservation(*params)

    def test_schema_request_binding_and_size_strict(self):
        obs=(PCObservation("object_label","unknown","unknown",.9),)
        for key,kwargs in (
            ("id",{"request_id":"private-name"}),
            ("expiry",{"expires_monotonic_s":NOW+3}),
            ("version",{"schema_version":2}),
            ("source",{"source":"sensor"}),
            ("shape",{"observations":[*obs]}),
        ):
            with self.subTest(key=key),self.assertRaises(ValueError):
                PCRequest(**{
                    "request_id":"a"*32,"observations":obs,
                    "created_monotonic_s":NOW,
                    "expires_monotonic_s":NOW+2,**kwargs,
                })

    def test_no_mutation_to_robot_safety_decision(self):
        cycle=self.start()
        done=finish_optional_pc_cycle(
            cycle,response(cycle.request),received_monotonic_s=NOW+.1)
        self.assertFalse(done.hypotheses[0].physical_actions_authorized)
        self.assertEqual(0,self.mem.experience_count())
        # No trusted floor, zone, ToF or actual battery source is present.
        self.assertEqual("halt",self.brain.choose_from_snapshot(
            fixture().snapshot,now=NOW+.1).intention)

    def test_public_mock_demo_does_not_use_real_pc(self):
        from microduck_companion.f5a_contract_demo import run_demo
        out=run_demo()
        self.assertEqual("inspect",out["offline_local_intention"])
        self.assertEqual("pc_unavailable",out["offline_pc_status"])
        self.assertEqual("hypotheses_unverified",out["mock_reply_status"])
        self.assertEqual(0,out["actual_pc_queries"])
        self.assertEqual(0,out["motor_commands_issued"])
        self.assertEqual(0,out["speaker_commands_issued"])


if __name__ == "__main__":
    unittest.main()
