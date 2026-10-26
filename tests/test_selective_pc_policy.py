"""F5-C policy: persistent opt-in, quotas, failure circuit and local fallback.

All requests are fictional F5-A objects; Ollama clients in this file NEVER
open a socket. No media, robotd, actual Qwen or real identities.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path

from microduck_companion.autonomy import AutonomyBrain
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.ollama_local_client import (
    OllamaLocalClient, OllamaTransportResult, OptionalOllamaWorker,
)
from microduck_companion.passive_intentions import PassiveIntent
from microduck_companion.passive_memory import PassiveObservationJournal
from microduck_companion.passive_sources import PassiveRead
from microduck_companion.pc_hypothesis_contract import (
    OptionalPCAdvisory, PCObservation, PCRequest, start_optional_pc_cycle,
)
from microduck_companion.perception import PerceptionEvent, PerceptionSnapshot
from microduck_companion.selective_pc_policy import (
    BACKOFF_S, COOLDOWN_S, DAY_LIMIT, SelectivePCPolicy, SelectivePCBridge,
)

NOW = 100.
WALL = 1_780_000_000.


def cycle(*, now=NOW, status="unknown", request_id=None):
    if request_id is None:
        request_id = uuid.uuid4().hex
    return OptionalPCAdvisory(
        PassiveIntent("inspect","mock_category_uncertain",
                      "object_label","unknown"),
        PCRequest(request_id,(
            PCObservation("object_label","unknown",status,.93),
        ),now,now+2.),
        "pending_transport",
    )


def actual_f5a_cycle(memory, *, now=NOW):
    ev=PerceptionEvent("object_label","unknown","mock",now,1.,.95,
                       track_id="track-fictional-only")
    read=PassiveRead("ok",PerceptionSnapshot("mock",(ev,),now),
                     1,"mock_fixture_unix")
    return start_optional_pc_cycle(
        AutonomyBrain(memory),read,
        journal=PassiveObservationJournal(memory),
        now_monotonic_s=now,now_wall_epoch_s=WALL,
    )


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.memory=ExperienceMemory()
        self.addCleanup(self.memory.close)
        self.policy=SelectivePCPolicy(self.memory)

    def reserve(self, item=None, *, mono=NOW, wall=WALL, opt=True):
        return self.policy.reserve(
            item or cycle(now=mono),
            pc_opt_in=opt,now_monotonic_s=mono,
            now_wall_epoch_s=wall,
        )

    def complete(self,item, *, wall=WALL+.1,
                 status="hypotheses_unverified"):
        return self.policy.complete(item.request.request_id,
                                    now_wall_epoch_s=wall,status=status)

    def test_opt_out_default_is_no_network_and_zero_writes(self):
        item=cycle()
        got=self.policy.reserve(
            item,now_monotonic_s=NOW,now_wall_epoch_s=WALL)
        self.assertFalse(got.allowed)
        self.assertEqual("pc_disabled",got.reason)
        self.assertEqual("inspect",got.local_intention)
        self.assertEqual(0,got.motor_commands_issued)
        self.assertEqual(0,got.network_commands_issued)
        self.assertEqual({},self.policy.counts())

    def test_unknown_and_conflict_are_distinct_triggers_no_identity(self):
        item=cycle()
        accepted=self.reserve(item)
        self.assertTrue(accepted.allowed)
        self.assertEqual("unknown",accepted.reason)
        self.assertTrue(self.complete(item))
        self.assertEqual({"hypotheses_unverified":1},self.policy.counts())
        rows=self.memory.conn.execute(
            "SELECT request_hash,trigger,status FROM f5c_pc_uses").fetchall()
        self.assertEqual("unknown",rows[0]["trigger"])
        self.assertEqual(64,len(rows[0]["request_hash"]))
        self.assertNotIn(item.request.request_id,rows[0]["request_hash"])
        # A conflict after cooldown is eligible, without track identity.
        other=cycle(now=NOW+1,status="conflict")
        decision=self.reserve(other,mono=NOW+1,wall=WALL+61)
        self.assertTrue(decision.allowed)
        self.assertEqual("conflict",decision.reason)

    def test_repeated_request_and_inflight_limit(self):
        item=cycle()
        self.assertTrue(self.reserve(item).allowed)
        self.assertEqual("duplicate_request",self.reserve(
            item,mono=NOW+.1,wall=WALL+.1).reason)
        self.assertEqual("already_pending",self.reserve(
            cycle(),mono=NOW+.1,wall=WALL+.2).reason)
        self.assertTrue(self.complete(item,wall=WALL+.3))
        self.assertFalse(self.complete(item,wall=WALL+.4))
        self.assertEqual("cooldown",self.reserve(
            cycle(),mono=NOW+.1,wall=WALL+1).reason)

    def test_recent_quota_then_expiration(self):
        for i in (0,61):
            it=cycle()
            self.assertTrue(self.reserve(it,wall=WALL+i).allowed)
            self.assertTrue(self.complete(it,wall=WALL+i+.01))
        third=self.reserve(cycle(),wall=WALL+122)
        self.assertEqual("window_quota",third.reason)
        later=cycle()
        result=self.reserve(later,wall=WALL+601)
        self.assertTrue(result.allowed)

    def test_daily_quota_carries_over_within_one_day(self):
        for i in range(DAY_LIMIT):
            when=WALL+i*601
            it=cycle()
            allowed=self.reserve(it,wall=when)
            self.assertTrue(allowed.allowed,(i,allowed.reason))
            self.assertTrue(self.complete(it,wall=when+.01))
        blocked=self.reserve(cycle(),wall=WALL+DAY_LIMIT*601)
        self.assertEqual("daily_quota",blocked.reason)
        allowed=self.reserve(cycle(),wall=WALL+86401)
        self.assertTrue(allowed.allowed)

    def test_two_transport_failures_open_circuit_then_cool_down(self):
        first=cycle()
        self.assertTrue(self.reserve(first).allowed)
        self.assertTrue(self.complete(first,status="pc_unavailable"))
        second=cycle()
        self.assertTrue(self.reserve(second,wall=WALL+61).allowed)
        self.assertTrue(self.complete(second,wall=WALL+61.1,
                                      status="response_rejected"))
        denied=self.reserve(cycle(),wall=WALL+122)
        self.assertEqual("circuit_open",denied.reason)
        resumed=cycle()
        self.assertTrue(self.reserve(resumed,wall=WALL+62+BACKOFF_S).allowed)
        self.assertTrue(self.complete(resumed,wall=WALL+63+BACKOFF_S))
        self.assertEqual("cooldown",self.reserve(
            cycle(),wall=WALL+64+BACKOFF_S).reason)

    def test_crash_pending_recovers_as_failure_with_no_replay(self):
        first=cycle()
        self.assertTrue(self.reserve(first).allowed)
        following=cycle(now=NOW+4.)
        blocked=self.reserve(following,mono=NOW+4.,wall=WALL+4.)
        self.assertEqual("cooldown",blocked.reason)
        self.assertEqual({"pc_unavailable":1},self.policy.counts())
        # An abandoned result can never later overwrite the failure.
        self.assertFalse(self.complete(first,wall=WALL+4.1))
        second=cycle(now=NOW+65.)
        self.assertTrue(self.reserve(second,mono=NOW+65.,
                                     wall=WALL+65.).allowed)
        # A second crash opens the circuit.
        self.assertEqual("circuit_open",self.reserve(
            cycle(now=NOW+69.),mono=NOW+69.,wall=WALL+69.).reason)

    def test_clock_rollback_and_expired_monotonic_fail_closed(self):
        first=cycle()
        self.assertTrue(self.reserve(first).allowed)
        self.assertTrue(self.complete(first))
        got=self.reserve(cycle(),wall=WALL-.1)
        self.assertEqual("wall_clock_rollback",got.reason)
        self.assertEqual("request_expired",self.reserve(
            cycle(),mono=NOW+3,wall=WALL+61).reason)

    def test_wrong_types_and_states_refused(self):
        it=cycle()
        for value in (1,0,None,"yes"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.policy.reserve(it,pc_opt_in=value,
                    now_monotonic_s=NOW,now_wall_epoch_s=WALL)
        for stamp in (float("nan"),float("inf"),-1.,True):
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):
                self.policy.reserve(it,pc_opt_in=True,
                    now_monotonic_s=NOW,now_wall_epoch_s=stamp)
        for status in ("pending","safe_area","robot.move",None):
            with self.subTest(status=status),self.assertRaises(ValueError):
                self.policy.complete(it.request.request_id,
                    status=status,now_wall_epoch_s=WALL)
        for request_id in ("track-animal","",None):
            with self.subTest(request_id=request_id),self.assertRaises(ValueError):
                self.policy.complete(request_id,status="pc_unavailable",
                                     now_wall_epoch_s=WALL)

    def test_f5a_real_fixture_used_with_same_memory(self):
        item=actual_f5a_cycle(self.memory)
        self.assertEqual("inspect",item.local_intent.intention)
        self.assertTrue(self.reserve(item).allowed)
        self.assertEqual(0,self.memory.experience_count())
        self.assertIsNone(self.memory.get("track-fictional-only"))

    def test_local_only_cycle_not_eligible(self):
        it=cycle()
        local=OptionalPCAdvisory(it.local_intent,None,"not_needed")
        answer=self.reserve(local)
        self.assertFalse(answer.allowed)
        self.assertEqual("not_eligible",answer.reason)


class PersistentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"fictional-quota.sqlite3"

    def test_two_independent_sqlite_connections_share_atomic_limits(self):
        a=ExperienceMemory(self.path)
        b=ExperienceMemory(self.path)
        try:
            p=SelectivePCPolicy(a)
            q=SelectivePCPolicy(b)
            item=cycle()
            self.assertTrue(p.reserve(item,now_monotonic_s=NOW,
                         now_wall_epoch_s=WALL,pc_opt_in=True).allowed)
            other=cycle()
            denied=q.reserve(other,pc_opt_in=True,
                             now_monotonic_s=NOW,
                             now_wall_epoch_s=WALL+.1)
            self.assertEqual("already_pending",denied.reason)
            self.assertEqual(1,q.counts()["pending"])
            self.assertTrue(p.complete(item.request.request_id,
                  status="hypotheses_unverified",now_wall_epoch_s=WALL+.2))
        finally:
            a.close()
            b.close()
        reopened=ExperienceMemory(self.path)
        try:
            q=SelectivePCPolicy(reopened)
            again=q.reserve(cycle(),pc_opt_in=True,
                             now_monotonic_s=NOW,now_wall_epoch_s=WALL+10)
            self.assertEqual("cooldown",again.reason)
        finally:
            reopened.close()

    def test_sqlite_busy_fails_closed_without_remote_submission(self):
        a=ExperienceMemory(self.path)
        b=ExperienceMemory(self.path)
        try:
            p=SelectivePCPolicy(a)
            q=SelectivePCPolicy(b)
            a.conn.execute("BEGIN EXCLUSIVE")
            denied=q.reserve(cycle(),pc_opt_in=True,
                now_monotonic_s=NOW,now_wall_epoch_s=WALL)
            self.assertFalse(denied.allowed)
            self.assertEqual("storage_unavailable",denied.reason)
            a.conn.rollback()
            self.assertTrue(q.reserve(cycle(),pc_opt_in=True,
                now_monotonic_s=NOW,now_wall_epoch_s=WALL).allowed)
        finally:
            a.close()
            b.close()

    def test_missing_state_is_storage_unavailable(self):
        mem=ExperienceMemory(self.path)
        try:
            policy=SelectivePCPolicy(mem)
            mem.conn.execute("DELETE FROM f5c_pc_state")
            mem.conn.commit()
            got=policy.reserve(cycle(),now_monotonic_s=NOW,
                               now_wall_epoch_s=WALL,pc_opt_in=True)
            self.assertEqual("storage_unavailable",got.reason)
        finally:
            mem.close()


class FakeClock:
    def __init__(self,now=NOW):
        self.now=now
    def __call__(self):
        return self.now


class NeverNetworkClient(OllamaLocalClient):
    def __init__(self, *, error=False):
        super().__init__()
        self.queries=0
        self.started=threading.Event()
        self.release=threading.Event()
        self.error=error

    def query(self,request,*,timeout_s=2.):
        self.queries+=1
        self.started.set()
        self.release.wait(1.0)
        if self.error:
            return OllamaTransportResult("unavailable",self.model,.01)
        reply={
            "schema_version":1,"request_id":request.request_id,
            "source":"pc_qwen_unverified",
            "hypotheses":[{
                "kind":"object_label","category":"unknown",
                "confidence":0,"ttl_s":1,
            }],
        }
        return OllamaTransportResult("ok",self.model,.01,
                                      wire=json.dumps(reply).encode())


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.mem=ExperienceMemory()
        self.addCleanup(self.mem.close)
        self.policy=SelectivePCPolicy(self.mem)
        self.clock=FakeClock()
        self.client=NeverNetworkClient()
        self.worker=OptionalOllamaWorker(self.client,clock=self.clock)
        self.addCleanup(self.worker.close)
        self.addCleanup(self.client.release.set)
        self.bridge=SelectivePCBridge(self.policy,self.worker)

    def test_default_no_optin_cannot_call_client(self):
        initial=cycle()
        got=self.bridge.submit(initial,now_monotonic_s=NOW,
                  now_wall_epoch_s=WALL)
        self.assertFalse(got.allowed)
        self.assertEqual(0,self.client.queries)
        self.assertIsNone(self.bridge.poll(now_wall_epoch_s=WALL))
        self.assertEqual({},self.policy.counts())

    def test_optin_realizes_only_one_nonblocking_mock_request(self):
        first=cycle()
        decision=self.bridge.submit(first,pc_opt_in=True,
                       now_monotonic_s=NOW,now_wall_epoch_s=WALL)
        self.assertTrue(decision.allowed)
        self.assertTrue(self.client.started.wait(.5))
        start=time.monotonic()
        self.assertIsNone(self.bridge.poll(now_wall_epoch_s=WALL+.01))
        self.assertLess(time.monotonic()-start,.1)
        second=self.bridge.submit(cycle(),pc_opt_in=True,
                    now_monotonic_s=NOW,now_wall_epoch_s=WALL+.02)
        self.assertEqual("bridge_busy",second.reason)
        self.client.release.set()
        answer=None
        for _ in range(50):
            answer=self.bridge.poll(now_wall_epoch_s=WALL+.1)
            if answer is not None:
                break
            time.sleep(.01)
        self.assertIsNotNone(answer)
        self.assertEqual("hypotheses_unverified",answer.status)
        self.assertEqual(first.local_intent,answer.local_intent)
        self.assertEqual(0,answer.motor_commands_issued)
        self.assertEqual(0,answer.speaker_commands_issued)
        self.assertEqual(0,self.mem.experience_count())
        self.assertEqual({"hypotheses_unverified":1},self.policy.counts())
        self.assertEqual(1,self.client.queries)

    def test_async_expiry_discards_result_and_accounts_failure(self):
        first=cycle()
        self.assertTrue(self.bridge.submit(first,pc_opt_in=True,
                now_monotonic_s=NOW,now_wall_epoch_s=WALL).allowed)
        self.assertTrue(self.client.started.wait(.5))
        self.clock.now=NOW+3.
        answer=self.bridge.poll(now_wall_epoch_s=WALL+3.)
        self.assertEqual("pc_unavailable",answer.status)
        self.assertEqual(first.local_intent,answer.local_intent)
        self.assertEqual({"pc_unavailable":1},self.policy.counts())
        self.client.release.set()


if __name__=="__main__":
    unittest.main()
