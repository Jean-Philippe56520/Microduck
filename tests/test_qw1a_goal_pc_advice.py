"""QW-1A real-code contract tests, NO real 9B requests in GitHub CI."""
from __future__ import annotations

from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from microduck_companion.category_semantics import CategorySemantics
from microduck_companion.episodic_memory import ExperienceMemory
from microduck_companion.experience_ledger import (
    MockExperienceLedger, MockResolution,
)
from microduck_companion.mock_goal_memory import MockGoalMemory
from microduck_companion.ollama_local_client import OllamaEndpoint
from microduck_companion.qwen9b_goal_advice import (
    GoalQuestion, MAX_HUMAN_CHARS, MAX_WIRE_BYTES, MODEL, _pc_fixture,
    build_goal_question, make_wire, parse_advice, query_one, run_ab,
)


def _good_reply(question: GoalQuestion, *, strategy="observe_over_time"):
    return json.dumps({
        "request_id": question.request_id, "status": "unverified",
        "strategy": strategy,
        "reason_for_human": "Une nouvelle observation dans le temps peut etre informative.",
        "testable_observation_for_human": "Constater un changement, sans supposer sa cause.",
    }, separators=(",", ":")).encode()


class FakeSock:
    def settimeout(self, timeout):
        assert timeout > 0


class FakeResponse:
    def __init__(self, data, *, status=200, content_type="application/json",
                 length=None, transfer=None, encoding="identity"):
        self.data=data
        self.position=0
        self.status=status
        self.content_type=content_type
        self.length=length
        self.transfer=transfer
        self.encoding=encoding

    def getheader(self, key, default=None):
        return {
            "Content-Type": self.content_type,
            "Content-Length": str(len(self.data)) if self.length is None else self.length,
            "Transfer-Encoding": self.transfer,
            "Content-Encoding": self.encoding,
        }.get(key,default)

    def read1(self,n):
        part=self.data[self.position:self.position+n]
        self.position+=len(part)
        return part

    def close(self):
        pass


class FakeConn:
    def __init__(self, host, port, timeout, *, responder):
        self.host,self.port=host,port
        self.timeout=timeout
        self.sock=FakeSock()
        self.responder=responder

    def request(self,method,path,body,headers):
        assert (self.host,self.port)==("127.0.0.1",11435)
        assert method=="POST" and path=="/api/chat"
        data=json.loads(body)
        assert data["model"] == MODEL
        assert data["stream"] is False
        assert data["think"] is False
        assert "images" not in str(data["messages"])
        self.response=self.responder(data)

    def getresponse(self):
        return self.response

    def close(self):
        pass


def envelope(request_data, *, strategy="observe_over_time", **changes):
    user=json.loads(request_data["messages"][1]["content"])
    rid=request_data["format"]["properties"]["request_id"]["enum"][0]
    good=json.loads(_good_reply(GoalQuestion(
        rid,user["category_claim"],user["goal_kind"],user["goal_state"],
        "find_strategy",tuple(user["prior_proposals"]),
        user["history_provenance"],user["category_history"],
        user["history_provenance"]!="not_provided",
    ),strategy=strategy))
    e={
        "model": MODEL, "done": True, "done_reason": "stop",
        "message": {"role": "assistant", "content": json.dumps(good)},
        "total_duration": 20_000_000_000, "eval_count": 131,
    }
    e.update(changes)
    return FakeResponse(json.dumps(e).encode())


class GoalMemoryContextTests(unittest.TestCase):
    def setUp(self):
        self.memory,self.semantics,self.goals,self.goal_id,self.now=_pc_fixture()
        self.addCleanup(self.memory.close)

    def questions(self):
        no=build_goal_question(
            self.memory,self.semantics,self.goals,goal_id=self.goal_id,
            now_wall_epoch_s=self.now,memory_enabled=False)
        yes=build_goal_question(
            self.memory,self.semantics,self.goals,goal_id=self.goal_id,
            now_wall_epoch_s=self.now,memory_enabled=True)
        return no,yes

    def test_real_sqlite_readonly_memo_with_without_context(self):
        before=self.memory.conn.total_changes
        no,yes=self.questions()
        self.assertEqual(before,self.memory.conn.total_changes)
        self.assertEqual((no.category,no.goal_kind,no.state,no.need),
                         ("ball","observe_category","suspended","find_strategy"))
        self.assertEqual((no.category,no.goal_kind,no.state,no.need),
                         (yes.category,yes.goal_kind,yes.state,yes.need))
        self.assertEqual((),no.prior_proposals)
        self.assertEqual(("observe_from_distance",),yes.prior_proposals)
        self.assertEqual("not_provided",no.source)
        self.assertEqual("mock_fixture_only",yes.source)
        self.assertEqual("unknown",yes.category_history)
        self.assertFalse(yes.memory_enabled is False)
        self.assertNotEqual(no.request_id,yes.request_id)
        for question in (no,yes):
            self.assertTrue(
                len(make_wire(question)) < MAX_WIRE_BYTES)
            self.assertFalse(question.memory_enabled is None)

    def test_only_public_enums_leave_no_raw_identifiers_or_media(self):
        no,yes=self.questions()
        for q in (no,yes):
            data=json.loads(make_wire(q))
            sent=json.loads(data["messages"][1]["content"])
            self.assertEqual({"task","need","category_claim","goal_kind",
                              "goal_state","history_provenance",
                              "category_history","prior_proposals",
                              "physical_executions_verified",
                              "effects_verified","robot_safety_state",
                              "input_is_fixture_only"},set(sent))
            self.assertEqual(0,sent["physical_executions_verified"])
            self.assertEqual(0,sent["effects_verified"])
            self.assertEqual("unavailable",sent["robot_safety_state"])
            self.assertNotIn(self.goal_id,make_wire(q).decode())
            self.assertNotIn("s-0000000000000a91",make_wire(q).decode())
            for forbidden in ("SELECT ", "sqlite3", "face", "track",
                              "robot.do", "motor_commands", "KICK CAT"):
                self.assertNotIn(forbidden, json.dumps(sent))
            self.assertNotIn("images",data["messages"][1])
            self.assertEqual(["unverified"],
                             data["format"]["properties"]["status"]["enum"])
            self.assertEqual([q.request_id],
                             data["format"]["properties"]["request_id"]["enum"])

    def test_goal_withdrawal_age_future_and_wrong_memory_fail_closed(self):
        with self.assertRaises(ValueError):
            build_goal_question(
                self.memory,self.semantics,self.goals,goal_id=self.goal_id,
                now_wall_epoch_s=self.now-50,memory_enabled=True)
        with self.assertRaises(ValueError):
            build_goal_question(
                self.memory,self.semantics,self.goals,goal_id=self.goal_id,
                now_wall_epoch_s=self.now+15*86400,memory_enabled=True)
        with self.assertRaises(ValueError):
            build_goal_question(
                self.memory,self.semantics,self.goals,goal_id=self.goal_id,
                now_wall_epoch_s=self.now,memory_enabled=1)
        with self.assertRaises(ValueError):
            build_goal_question(
                self.memory,self.semantics,self.goals,goal_id=self.goal_id,
                now_wall_epoch_s=float("nan"),memory_enabled=True)
        other=ExperienceMemory(":memory:")
        try:
            with self.assertRaises(ValueError):
                build_goal_question(
                    other,self.semantics,self.goals,goal_id=self.goal_id,
                    now_wall_epoch_s=self.now,memory_enabled=True)
        finally:
            other.close()
        self.goals.retract(goal_id=self.goal_id,reason="source_retracted")
        with self.assertRaises(ValueError):
            self.questions()

    def test_corrupt_attempt_reference_fails_closed_without_export(self):
        self.memory.conn.execute(
            "UPDATE mem1_mock_goal_links SET strategy=?",
            ("invalid_synthetic_strategy",))
        self.memory.conn.commit()
        with self.assertRaises(ValueError):
            self.questions()

    def test_mock_executed_is_still_not_physical_proof(self):
        # EX1's fictional status is not serialised to the advisor as success.
        ledger=MockExperienceLedger(self.memory)
        ledger.resolve(MockResolution(
            "s-0000000000000a91",1,"mock_executed",self.now-1.7))
        _,q=self.questions()
        wire=make_wire(q).decode()
        self.assertNotIn("mock_executed",wire)
        self.assertIn("physical_executions_verified",wire)
        self.assertEqual(("observe_from_distance",),q.prior_proposals)


class StrictSchemaTests(unittest.TestCase):
    def setUp(self):
        self.mem,self.sem,self.goals,self.key,self.now=_pc_fixture()
        self.addCleanup(self.mem.close)
        self.q=build_goal_question(
            self.mem,self.sem,self.goals,goal_id=self.key,
            now_wall_epoch_s=self.now,memory_enabled=True)

    def test_accepts_passive_observation_and_abstention_only(self):
        for strategy in ("observe_from_distance","observe_over_time",
                         "inspect_other_view","compare_memory","abstain"):
            with self.subTest(strategy=strategy):
                a=parse_advice(self.q,_good_reply(self.q,strategy=strategy))
                self.assertEqual(strategy,a.strategy)
                self.assertEqual("blocked",a.machine_use)
                self.assertFalse(a.physical_effect_verified)
                self.assertEqual(0,a.memory_writes)
                self.assertEqual(0,a.motor_commands_issued)

    def test_refuses_motor_tool_source_extra_fields_and_wrong_request(self):
        for change in ({"strategy":"kick_left"},
                       {"strategy":"ground_pick"},
                       {"strategy":"walk"},
                       {"status":"verified"},
                       {"request_id":"0"*32},
                       {"source":"sensor"},
                       {"motor_commands":1},
                       {"category":"person"}):
            with self.subTest(change=change):
                d=json.loads(_good_reply(self.q))
                d.update(change)
                with self.assertRaises(ValueError):
                    parse_advice(self.q,json.dumps(d).encode())

    def test_refuses_duplicate_json_keys_nonfinite_oversize_and_empty(self):
        good=_good_reply(self.q)
        cases=(
            good[:-1]+b',"strategy":"abstain"}',
            good.replace(b'"status":"unverified"',b'"status":NaN'),
            good+b" ",
            b"{}",
            b"\xff",
            b"x"*4000,
        )
        for c in cases:
            with self.subTest(payload=c[:30]),self.assertRaises(ValueError):
                parse_advice(self.q,c)
        d=json.loads(good)
        d["reason_for_human"]="x"*(MAX_HUMAN_CHARS+1)
        with self.assertRaises(ValueError):
            parse_advice(self.q,json.dumps(d).encode())
        d["reason_for_human"]=""
        with self.assertRaises(ValueError):
            parse_advice(self.q,json.dumps(d).encode())

    def test_no_model_request_by_default_or_without_operator_permission(self):
        with patch("http.client.HTTPConnection",
                   side_effect=AssertionError("never connect")):
            dry=run_ab(consent=False)
        self.assertEqual("not_run",dry["status"])
        self.assertEqual(0,dry["qwen_real_calls_attempted"])
        self.assertEqual(0,dry["motor_commands_issued"])
        self.assertEqual((),tuple(dry["memory_disabled"]["prior_proposals"]))
        self.assertEqual(["observe_from_distance"],
                         dry["memory_enabled"]["prior_proposals"])

    def test_rejects_nonloopback_and_malformed_options(self):
        with self.assertRaises(ValueError):
            query_one(self.q,endpoint=OllamaEndpoint(
                "http://192.168.1.5:11435",unsafe_private_lan_lab=True))
        with self.assertRaises(ValueError):
            query_one(self.q,endpoint=OllamaEndpoint(),timeout_s=121)
        with self.assertRaises(ValueError):
            query_one(self.q,endpoint=OllamaEndpoint(),timeout_s=float("nan"))
        with self.assertRaises(ValueError):
            run_ab(consent="yes")
        with self.assertRaises(ValueError):
            run_ab(consent=False,port=0)


class FakeRealTransportTests(unittest.TestCase):
    def setUp(self):
        mem,sem,goals,gid,now=_pc_fixture()
        self.addCleanup(mem.close)
        self.q=build_goal_question(
            mem,sem,goals,goal_id=gid,now_wall_epoch_s=now,
            memory_enabled=True)
        self.endpoint=OllamaEndpoint("http://127.0.0.1:11435")

    def fake(self,responder):
        return patch(
            "microduck_companion.qwen9b_goal_advice.http.client.HTTPConnection",
            side_effect=lambda host,port,timeout: FakeConn(
                host,port,timeout,responder=responder))

    def test_single_real_http_protocol_contract_accepts_valid_json(self):
        with self.fake(lambda d:envelope(d)):
            result=query_one(self.q,endpoint=self.endpoint)
        self.assertEqual("unverified",result["status"])
        self.assertEqual("observe_over_time",result["strategy"])
        self.assertFalse(result["repeats_prior_proposal"])
        self.assertEqual(20.0,result["ollama_total_s"])
        self.assertEqual(131,result["tokens_generated"])
        self.assertEqual(0,result["motor_commands_issued"])
        self.assertEqual(0,result["memory_writes"])
        self.assertTrue(result["real_pc_call_attempted"])
        self.assertIn("_human_only",result)

    def test_malicious_envelopes_and_generation_limits_fail_closed(self):
        cases=[
            lambda d: envelope(d,model="other_model"),
            lambda d: envelope(d,done_reason="length"),
            lambda d: envelope(d,message={"role":"assistant","content":"{}",
                                          "tool_calls":[{"tool":"motor"}]}),
            lambda d: envelope(d,status=500),
            lambda d: FakeResponse(b"{}",length="9999999"),
            lambda d: FakeResponse(b"{}",content_type="text/html"),
            lambda d: envelope(d,message={"role":"assistant","content":
                    json.dumps({"status":"verified","motor_commands":1})}),
            lambda d: FakeResponse(b"not-json"),
        ]
        for i,responder in enumerate(cases):
            with self.subTest(case=i),self.fake(responder):
                r=query_one(self.q,endpoint=self.endpoint)
            self.assertNotEqual("unverified",r["status"])
            self.assertIsNone(r["strategy"])
            self.assertEqual(0,r["motor_commands_issued"])
            self.assertEqual(0,r["memory_writes"])
            self.assertNotIn("_human_only",r)

    def test_first_failed_request_prevents_second_and_model_echo(self):
        with self.fake(lambda d:envelope(d,done_reason="length")):
            r=run_ab(consent=True)
        self.assertEqual("stopped_after_first_failure",r["status"])
        self.assertEqual(1,r["qwen_real_calls_attempted"])
        self.assertEqual("not_sent",r["with_memory_result"])
        self.assertEqual(0,r["memory_writes_during_consultation"])

    def test_paired_real_transport_mock_returns_only_limited_strategy(self):
        requests=[]
        def responder(d):
            payload=json.loads(d["messages"][1]["content"])
            requests.append(payload)
            strategy=("observe_over_time" if payload["prior_proposals"]
                      else "observe_from_distance")
            return envelope(d,strategy=strategy)
        with self.fake(responder):
            report=run_ab(consent=True,show_human_text=False)
        self.assertEqual(2,report["qwen_real_calls_attempted"])
        self.assertEqual("technical_gate_passed_unverified",report["status"])
        self.assertTrue(report["predeclared_technical_gate_passed"])
        self.assertEqual(0,report["memory_writes_during_consultation"])
        self.assertFalse(report["semantic_gain_verified"])
        self.assertNotIn("untrusted_human_review_only",report)
        self.assertEqual((),tuple(requests[0]["prior_proposals"]))
        self.assertEqual(["observe_from_distance"],requests[1]["prior_proposals"])
        self.assertEqual("blocked",report["machine_use"])

    def test_both_lanes_have_same_goal_without_real_model_or_secret_access(self):
        requests=[]
        def responder(d):
            requests.append(json.loads(d["messages"][1]["content"]))
            return envelope(d,strategy="abstain")
        with self.fake(responder):
            report=run_ab(consent=True,show_human_text=True)
        self.assertEqual("technical_gate_passed_unverified",report["status"])
        a,b=requests
        for key in ("task","need","category_claim","goal_kind",
                    "goal_state","physical_executions_verified",
                    "effects_verified","robot_safety_state"):
            self.assertEqual(a[key],b[key])
        self.assertIn("untrusted_human_review_only",report)
        self.assertEqual(0,report["motor_commands_issued"])

    def test_unavailable_endpoint_is_single_failure_no_second_request(self):
        with patch("microduck_companion.qwen9b_goal_advice.http.client.HTTPConnection",
                   side_effect=ConnectionRefusedError("no local model")):
            report=run_ab(consent=True)
        self.assertEqual(1,report["qwen_real_calls_attempted"])
        self.assertEqual("stopped_after_first_failure",report["status"])
        self.assertEqual("transport",report["without_memory_result"]["diagnostic"])


if __name__ == "__main__":
    unittest.main()
