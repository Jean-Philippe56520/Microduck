"""F5-B: opt-in Ollama protocol tested with a LOCAL simulated HTTP server.

No external network, no installed Qwen, and no hardware execution.
"""
from __future__ import annotations

from contextlib import contextmanager
import http.server
import json
import math
import socket
import threading
import time
import unittest

from microduck_companion.ollama_local_client import (
    ALLOWED_MODELS, MAX_ENVELOPE_BYTES, OllamaEndpoint,
    OllamaLocalClient, OllamaTransportResult, OptionalOllamaWorker,
    advisory_from_transport,
)
from microduck_companion.pc_hypothesis_contract import (
    OptionalPCAdvisory, PCObservation, PCRequest,
)
from microduck_companion.passive_intentions import PassiveIntent


def make_cycle(now=100.):
    request = PCRequest(
        "a" * 32, (PCObservation("object_label", "unknown", "unknown", .95),),
        now, now + 2.,
    )
    local = PassiveIntent(
        "inspect", "fictional_unresolved_object", "object_label", "unknown",
    )
    return OptionalPCAdvisory(local, request, "pending_transport")


def f5a_reply(req_id, *, kind="object_label", category="unknown",
              confidence=0., ttl_s=1., **extra):
    response = {
        "schema_version": 1,
        "request_id": req_id,
        "source": "pc_qwen_unverified",
        "hypotheses": [{
            "kind": kind, "category": category,
            "confidence": confidence, "ttl_s": ttl_s,
        }],
    }
    response.update(extra)
    return json.dumps(response, allow_nan=False).encode()


def ollama_envelope(req_id, *, model="qwen3.5:4b",
                    content=None, done=True, **extra):
    if content is None:
        content = f5a_reply(req_id).decode()
    envelope = {
        "model": model, "done": done, "done_reason": "stop",
        "message": {"role": "assistant", "content": content},
        "total_duration": 30_000_000,
        "load_duration": 10_000_000,
        "eval_duration": 15_000_000, "eval_count": 20,
    }
    envelope.update(extra)
    return json.dumps(envelope, allow_nan=False).encode()


@contextmanager
def mock_ollama(responder):
    """Run a loopback-only fixture. Never bind an externally reachable port."""
    calls = []
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            data = self.rfile.read(size)
            calls.append((self.path, dict(self.headers.items()), data))
            code, mime, body, pause, headers = responder(data)
            if pause:
                time.sleep(pause)
            try:
                self.send_response(code)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(body)))
                for k, v in headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def good_server(data):
    body = json.loads(data)
    rid = json.loads(body["messages"][1]["content"])["request_id"]
    return 200, "application/json", ollama_envelope(rid), 0, {}


class EndpointTests(unittest.TestCase):
    def test_loopback_default_ipv4_ipv6(self):
        self.assertEqual(
            ("127.0.0.1", 11434), OllamaEndpoint().host_port,
        )
        self.assertEqual(
            ("::1", 11434), OllamaEndpoint("http://[::1]:11434").host_port,
        )

    def test_no_dns_cloud_public_redirect_or_url_credentials(self):
        for url in (
            "https://127.0.0.1:11434", "http://localhost:11434",
            "http://example.com:11434", "http://8.8.8.8:11434",
            "http://0.0.0.0:11434", "http://127.0.0.1:11434/api",
            "http://127.0.0.1:11434?x=y", "http://127.0.0.1:11434/#x",
            "http://u:p@127.0.0.1:11434", "http://127.0.0.1",
            "http://127.0.0.1:notaport", "http://127.0.0.1:99999",
            "http://127.0.0.1:11434 ",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                OllamaEndpoint(url)

    def test_direct_private_lan_requires_explicit_lab_only_opt_in(self):
        for ip in ("192.168.1.25", "172.17.0.2", "10.0.0.8"):
            with self.subTest(ip=ip):
                url = f"http://{ip}:11434"
                with self.assertRaises(ValueError):
                    OllamaEndpoint(url)
                configured = OllamaEndpoint(url, unsafe_private_lan_lab=True)
                self.assertEqual(ip, configured.host_port[0])
        for ip in ("169.254.3.3", "100.64.2.10", "8.8.8.8", "224.0.0.1"):
            with self.subTest(ip=ip), self.assertRaises(ValueError):
                OllamaEndpoint(f"http://{ip}:11434", unsafe_private_lan_lab=True)

    def test_invalid_lab_flag_fails_closed(self):
        with self.assertRaises(ValueError):
            OllamaEndpoint("http://192.168.1.4:11434",
                           unsafe_private_lan_lab=1)


class OllamaHTTPTests(unittest.TestCase):
    def test_only_known_model_tags_and_keep_alive(self):
        self.assertEqual({"qwen3.5:4b", "qwen3.5:9b"}, ALLOWED_MODELS)
        for value in ("", "llama", "qwen3.5:27b", "qwen3.5:9b;rm -rf", 4):
            with self.subTest(value=value), self.assertRaises(ValueError):
                OllamaLocalClient(model=value)
        for value in (True, "always", "1h", None):
            with self.subTest(keep_alive=value), self.assertRaises(ValueError):
                OllamaLocalClient(keep_alive=value)

    def test_request_is_bounded_no_person_data_or_motor(self):
        client = OllamaLocalClient()
        content = json.loads(client._request_body(make_cycle().request))
        self.assertEqual("qwen3.5:4b", content["model"])
        self.assertFalse(content["stream"])
        self.assertFalse(content["think"])
        self.assertEqual("0", content["keep_alive"])
        self.assertEqual(0, content["options"]["temperature"])
        self.assertEqual("hypothesize_object_category",
                         json.loads(content["messages"][1]["content"])["task"])
        self.assertNotIn("track", content["messages"][1]["content"])
        self.assertNotIn("person", content["messages"][1]["content"])
        self.assertNotIn("robot.move", content["messages"][1]["content"])
        self.assertEqual(1, content["format"]["properties"][
            "hypotheses"]["maxItems"])

    def test_real_loopback_http_and_f5a_parser_integration(self):
        with mock_ollama(good_server) as (url, calls):
            client = OllamaLocalClient(OllamaEndpoint(url))
            cycle = make_cycle()
            transport = client.query(cycle.request, timeout_s=1)
            self.assertEqual("ok", transport.status)
            self.assertEqual(20, transport.eval_tokens)
            self.assertEqual(30_000_000, transport.server_total_ns)
            result = advisory_from_transport(cycle, transport,
                                             now_monotonic_s=100.3)
            self.assertEqual("hypotheses_unverified", result.status)
            self.assertEqual("unknown", result.hypotheses[0].category)
            self.assertFalse(result.hypotheses[0].verified)
            self.assertEqual(cycle.local_intent, result.local_intent)
            self.assertEqual(0, result.motor_commands_issued)
            self.assertEqual(0, result.speaker_commands_issued)
            self.assertEqual(1, len(calls))
            self.assertEqual("/api/chat", calls[0][0])
            self.assertEqual("close", calls[0][1]["Connection"].lower())

    def test_no_pc_is_local_fallback(self):
        # Reserve a port then close it. If another server races and starts
        # on that port, the parser still keeps F5-A's decision unchanged.
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        cycle = make_cycle()
        outcome = OllamaLocalClient(
            OllamaEndpoint(f"http://127.0.0.1:{port}")
        ).query(cycle.request, timeout_s=.1)
        self.assertIn(outcome.status, ("unavailable", "protocol_rejected"))
        final = advisory_from_transport(
            cycle, outcome, now_monotonic_s=100.1)
        self.assertEqual(cycle.local_intent, final.local_intent)
        self.assertEqual((), final.hypotheses)

    def test_fail_closed_for_http_redirect_error_and_wrong_mime(self):
        for status, mime in (
            (302, "application/json"), (401, "application/json"),
            (500, "application/json"), (200, "text/html"),
        ):
            with self.subTest(status=status, mime=mime):
                def responder(_):
                    return status, mime, b"{}", 0, {"Location": "https://evil.test"}
                with mock_ollama(responder) as (url, calls):
                    result = OllamaLocalClient(
                        OllamaEndpoint(url)).query(make_cycle().request,timeout_s=1)
                    self.assertNotEqual("ok", result.status)
                    self.assertIsNone(result.wire)
                    self.assertEqual(1, len(calls))

    def test_oversize_content_and_malformed_ollama_envelope(self):
        cycle = make_cycle()
        rid = cycle.request.request_id
        bad = (
            b"\xff", b"{", b"[]", b'{"done":true,"done":true}',
            b"{" + b"x" * MAX_ENVELOPE_BYTES + b"}",
            ollama_envelope(rid, model="other"),
            ollama_envelope(rid, done=False),
            ollama_envelope(rid, done_reason="length"),
            ollama_envelope(rid, message={"role": "tool", "content":"{}"}),
            ollama_envelope(rid, message={
                "role": "assistant", "content": "{}", "tool_calls": [{"function": {}}]}),
            ollama_envelope(rid, eval_count=-2),
            ollama_envelope(rid, eval_count=True),
            ollama_envelope(rid, content="x" * 4100),
        )
        for raw in bad:
            with self.subTest(raw=raw[:40]):
                def responder(_):
                    return 200, "application/json", raw, 0, {}
                with mock_ollama(responder) as (url, _calls):
                    answer = OllamaLocalClient(OllamaEndpoint(url)).query(
                        cycle.request, timeout_s=1)
                    self.assertEqual("protocol_rejected", answer.status)
                    self.assertIsNone(answer.wire)

    def test_response_hypothesis_command_or_wrong_id_is_never_promoted(self):
        cycle = make_cycle()
        for reply in (
            f5a_reply(cycle.request.request_id, command="robot.move"),
            f5a_reply("b" * 32),
            f5a_reply(cycle.request.request_id, category="person"),
            f5a_reply(cycle.request.request_id, category="dog",confidence=.9),
            f5a_reply(cycle.request.request_id, category="unknown",ttl_s=10),
        ):
            with self.subTest(reply=reply[:90]):
                def responder(_):
                    return 200, "application/json", ollama_envelope(
                        cycle.request.request_id, content=reply.decode()), 0, {}
                with mock_ollama(responder) as (url, _calls):
                    response = OllamaLocalClient(
                        OllamaEndpoint(url)).query(cycle.request,timeout_s=1)
                    done=advisory_from_transport(
                        cycle, response, now_monotonic_s=100.1)
                    self.assertEqual(cycle.local_intent, done.local_intent)
                    # With no image or object features, dog/cat guesses
                    # cannot be carried into cognitive advice in F5-B.
                    self.assertEqual("response_rejected", done.status)
                    self.assertEqual((), done.hypotheses)
                    self.assertEqual(0, done.motor_commands_issued)

    def test_unknown_with_fabricated_confidence_is_rejected(self):
        cycle = make_cycle()
        trans = OllamaTransportResult(
            "ok", "qwen3.5:4b", .05,
            wire=f5a_reply(cycle.request.request_id,
                          category="unknown", confidence=.95),
        )
        done = advisory_from_transport(cycle, trans, now_monotonic_s=100.1)
        self.assertEqual("response_rejected", done.status)
        self.assertEqual(cycle.local_intent, done.local_intent)

    def test_timeout_of_stalled_local_http_server_returns_unavailable(self):
        def responder(data):
            return 200, "application/json", ollama_envelope(
                json.loads(json.loads(data)["messages"][1]["content"])["request_id"]
            ), .25, {}
        with mock_ollama(responder) as (url, _calls):
            answer = OllamaLocalClient(OllamaEndpoint(url)).query(
                make_cycle().request,timeout_s=.05)
            self.assertEqual("unavailable",answer.status)

    def test_strict_timeout_and_result_shapes(self):
        client=OllamaLocalClient()
        for timeout in (0.,-1,121.,float("nan"),True,"2"):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                client.query(make_cycle().request,timeout_s=timeout)
        for wrong in (
            {"status":"ok","wire":None},
            {"status":"unavailable","wire":b"x"},
            {"status":"invented","wire":None},
            {"status":"ok","wire":b"x"*5000},
        ):
            with self.subTest(wrong=wrong),self.assertRaises(ValueError):
                OllamaTransportResult(
                    model="qwen3.5:4b",elapsed_s=0.,**wrong)

    def test_response_received_at_deadline_is_discarded(self):
        cycle=make_cycle()
        trans=OllamaTransportResult(
            "ok","qwen3.5:4b",.5,
            wire=f5a_reply(cycle.request.request_id),
        )
        done=advisory_from_transport(
            cycle,trans,now_monotonic_s=cycle.request.expires_monotonic_s)
        self.assertEqual("response_rejected", done.status)
        self.assertEqual(cycle.local_intent,done.local_intent)


class FakeClock:
    def __init__(self, now=100.):
        self.now=now
    def __call__(self):
        return self.now


class MockSlowClient(OllamaLocalClient):
    def __init__(self):
        super().__init__()
        self.started=threading.Event()
        self.release=threading.Event()

    def query(self, request, *,timeout_s=2):
        self.started.set()
        self.release.wait(1.5)
        return OllamaTransportResult(
            "ok",self.model,.1,
            wire=f5a_reply(request.request_id),
        )


class WorkerTests(unittest.TestCase):
    def test_poll_does_not_block_brain_and_enforces_one_inflight(self):
        client=MockSlowClient()
        clk=FakeClock()
        worker=OptionalOllamaWorker(client,clock=clk)
        try:
            cycle=make_cycle()
            self.assertTrue(worker.submit(cycle))
            self.assertTrue(client.started.wait(.5))
            t=time.monotonic()
            self.assertIsNone(worker.poll())
            self.assertLess(time.monotonic()-t,.1)
            self.assertFalse(worker.submit(make_cycle()))
            clk.now=102.
            timed=worker.poll()
            self.assertEqual("pc_unavailable",timed.status)
            self.assertEqual(cycle.local_intent,timed.local_intent)
            self.assertFalse(worker.submit(make_cycle(now=102.)))
        finally:
            client.release.set()
            worker.close()

    def test_eventual_completion_is_only_an_unverified_annotation(self):
        client=MockSlowClient()
        clk=FakeClock()
        with OptionalOllamaWorker(client,clock=clk) as worker:
            cycle=make_cycle()
            self.assertTrue(worker.submit(cycle))
            self.assertTrue(client.started.wait(.5))
            client.release.set()
            final=None
            for _ in range(30):
                final=worker.poll()
                if final is not None:
                    break
                time.sleep(.01)
            self.assertIsNotNone(final)
            self.assertEqual("hypotheses_unverified",final.status)
            self.assertEqual("unknown",final.hypotheses[0].category)
            self.assertEqual(cycle.local_intent,final.local_intent)

    def test_close_refuses_new_jobs(self):
        client=OllamaLocalClient()
        worker=OptionalOllamaWorker(client)
        worker.close()
        with self.assertRaises(RuntimeError):
            worker.submit(make_cycle())

    def test_no_pending_or_future_cycle_submitted(self):
        clk=FakeClock()
        with OptionalOllamaWorker(OllamaLocalClient(),clock=clk) as worker:
            cycle=make_cycle(now=105.)
            self.assertFalse(worker.submit(cycle))
            clk.now=107.
            self.assertFalse(worker.submit(cycle))
            self.assertIsNone(worker.poll())


if __name__=="__main__":
    unittest.main()
