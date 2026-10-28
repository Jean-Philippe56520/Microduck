"""F5 v3 role-preview checks: fake transport, never a real camera or Ollama."""
from __future__ import annotations

import base64
import io
import json
from unittest import TestCase
from unittest.mock import patch

from PIL import Image

from microduck_companion.qwen9b_production_role import (
    ROLE_VERSION, SCENARIO_USER_PROMPT, SYSTEM_PROMPT,
)
from microduck_companion.qwen9b_role_preview import (
    MODEL, evaluate_local_image, make_request,
)
from microduck_companion.ollama_local_client import OllamaEndpoint


def _photo():
    out = io.BytesIO()
    Image.new("RGB", (140, 90), "blue").save(out, format="JPEG")
    return out.getvalue()


class Reply:
    def __init__(self, response, code=200, content_type="application/json"):
        self.content = response
        self.status = code
        self.content_type = content_type

    def getheader(self, name, default=None):
        return self.content_type if name.lower() == "content-type" else default

    def read(self, n):
        return self.content[:n]


class FakeHTTP:
    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.url = None
        self.body = None
        self.closed = False
        self.response = Reply(json.dumps({
            "model": MODEL, "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": "Perception : une chaise grise.\nHypothèse : siège.\nIncertitude : poids inconnu.\nÀ vérifier : autre vue."},
            "total_duration": 18_000_000_000, "load_duration": 2_000_000_000,
            "eval_duration": 8_000_000_000, "prompt_eval_duration": 4_000_000_000,
            "eval_count": 55,
        }).encode("utf-8"))

    def request(self, method, url, body, headers):
        assert method == "POST" and url == "/api/chat"
        self.url = url
        self.body = body
        self.headers = headers

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class RolePreviewTests(TestCase):
    def test_role_version_and_boundaries(self):
        self.assertIn("candidate", ROLE_VERSION)
        for keyword in ("robotd", "motrice", "identit", "Incertitude", "À vérifier", "corrigibles", "facultatif"):
            self.assertIn(keyword.casefold(), SYSTEM_PROMPT.casefold())
        self.assertIn("robot réel non connecté", SCENARIO_USER_PROMPT)

    def test_one_image_native_short_text_not_forced_json(self):
        request = json.loads(make_request(_photo()))
        self.assertEqual(request["model"], MODEL)
        self.assertEqual([x["role"] for x in request["messages"]], ["system", "user"])
        self.assertEqual(request["messages"][0]["content"], SYSTEM_PROMPT)
        self.assertNotIn("format", request)
        self.assertEqual(request["options"]["num_predict"], 180)
        self.assertEqual(request["options"]["num_ctx"], 4096)
        self.assertFalse(request["think"])
        self.assertEqual(request["keep_alive"], "0")
        self.assertEqual(len(request["messages"][1]["images"]), 1)
        self.assertTrue(base64.b64decode(request["messages"][1]["images"][0]).startswith(b"\xff\xd8"))

    def test_cannot_call_before_operator_consent(self):
        with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection") as conn:
            for consent, reviewed in ((False, True), (True, False)):
                with self.assertRaises(ValueError):
                    evaluate_local_image(_photo(), consent=consent, reviewed=reviewed)
            conn.assert_not_called()

    def test_approved_request_is_human_only(self):
        created = []
        def factory(*args, **kwargs):
            instance = FakeHTTP(*args, **kwargs)
            created.append(instance)
            return instance
        with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection", side_effect=factory):
            report = evaluate_local_image(_photo(), consent=True, reviewed=True)
        self.assertEqual(report["status"], "unverified")
        self.assertTrue(report["unverified"])
        self.assertEqual(report["memory_writes"], 0)
        self.assertEqual(report["motor_commands_issued"], 0)
        self.assertEqual(report["photos_saved_by_companion"], 0)
        self.assertIn("chaise", report["advisor_text"])
        self.assertEqual(report["load_s"], 2.0)
        self.assertEqual(report["image_prompt_s"], 4.0)
        self.assertEqual(report["generation_s"], 8.0)
        self.assertEqual(report["generated_tokens"], 55)
        self.assertEqual(len(created), 1)
        self.assertTrue(created[0].closed)
        self.assertIn('"images"', created[0].body.decode())
        self.assertEqual(created[0].host, "127.0.0.1")
        self.assertEqual(created[0].port, 11435)

    def test_reject_remote_even_opted_in_lab_endpoint(self):
        remote = OllamaEndpoint("http://192.168.10.3:12345", unsafe_private_lan_lab=True)
        with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection") as conn:
            with self.assertRaises(ValueError):
                evaluate_local_image(_photo(), consent=True, reviewed=True, endpoint=remote)
            conn.assert_not_called()

    def test_reject_invalid_timeout_port_size(self):
        with self.assertRaises(ValueError):
            evaluate_local_image(_photo(), consent=True, reviewed=True, timeout_s=float("nan"))
        with self.assertRaises(ValueError):
            evaluate_local_image(_photo(), consent=True, reviewed=True, timeout_s=181)
        with self.assertRaises(ValueError):
            evaluate_local_image(_photo(), consent=True, reviewed=True, port=65536)
        with self.assertRaises(ValueError):
            evaluate_local_image(b"", consent=True, reviewed=True)
        with self.assertRaises(ValueError):
            make_request(b"x" * 100001)

    def test_invalid_envelope_is_refused(self):
        for obj in (
            {"model": MODEL, "done": False, "message": {"role": "assistant", "content": "texte"}},
            {"model": "wrong:9b", "done": True, "message": {"role": "assistant", "content": "texte"}},
            {"model": MODEL, "done": True, "done_reason": "length", "message": {"role": "assistant", "content": "texte"}},
            {"model": MODEL, "done": True, "message": {"role": "assistant", "content": "texte", "tool_calls": [{"function": {}}]}},
        ):
            with self.subTest(obj=obj):
                with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection") as create:
                    conn = create.return_value
                    conn.getresponse.return_value = Reply(json.dumps(obj).encode())
                    report = evaluate_local_image(_photo(), consent=True, reviewed=True)
                self.assertEqual(report["status"], "rejected")
                self.assertNotIn("advisor_text", report)

    def test_envelope_diagnostics_are_bounded_and_do_not_leak_content(self):
        cases = (
            ("length", "generation_truncated"),
            ("not_a_stop", "stop_reason_invalid"),
        )
        for reason, expected in cases:
            envelope = {"model": MODEL, "done": True, "done_reason": reason,
                        "message": {"role": "assistant", "content": "private test content"},
                        "eval_count": 180, "total_duration": 12_000_000_000}
            with self.subTest(reason=reason):
                with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection") as create:
                    create.return_value.getresponse.return_value = Reply(json.dumps(envelope).encode())
                    result = evaluate_local_image(_photo(), consent=True, reviewed=True)
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(result["diagnostic"], expected)
                self.assertNotIn("advisor_text", result)
                self.assertNotIn("private test content", json.dumps(result))
                self.assertEqual(result["memory_writes"], 0)
                self.assertEqual(result["motor_commands_issued"], 0)
                if reason == "length":
                    self.assertEqual(result["generated_tokens"], 180)

    def test_v2_truncated_reply_is_rejected_with_only_numeric_telemetry(self):
        from microduck_companion.qwen9b_production_role_v2 import ROLE_VERSION as V2
        answer = {"model": MODEL, "done": True, "done_reason": "length",
                  "message": {"role": "assistant", "content": "private partial answer"},
                  "eval_count": 320, "total_duration": 36_000_000_000}
        with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection") as create:
            create.return_value.getresponse.return_value = Reply(json.dumps(answer).encode())
            report = evaluate_local_image(_photo(), consent=True, reviewed=True, role_version=V2)
        sent = json.loads(create.return_value.request.call_args.kwargs["body"])
        self.assertEqual(sent["options"]["num_predict"], 320)
        self.assertEqual(report["status"], "rejected")
        self.assertEqual(report["diagnostic"], "generation_truncated")
        self.assertEqual(report["generated_tokens"], 320)
        self.assertNotIn("private partial answer", json.dumps(report))
        self.assertEqual(create.return_value.request.call_count, 1)
        self.assertEqual(report["motor_commands_issued"], 0)
        self.assertEqual(report["memory_writes"], 0)

    def test_wrong_model_diagnostic_remains_non_disclosing(self):
        data = {"model": "different:model", "done": True,
                "message": {"role": "assistant", "content": "sensitive"}}
        with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection") as create:
            create.return_value.getresponse.return_value = Reply(json.dumps(data).encode())
            result = evaluate_local_image(_photo(), consent=True, reviewed=True)
        self.assertEqual(result["diagnostic"], "model_mismatch")
        self.assertNotIn("sensitive", json.dumps(result))

    def test_overlong_text_refused_and_no_injection_into_actions(self):
        data = {"model": MODEL, "done": True, "done_reason": "stop",
                "message": {"role": "assistant", "content": "x" * 1201}}
        with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection") as create:
            create.return_value.getresponse.return_value = Reply(json.dumps(data).encode())
            report = evaluate_local_image(_photo(), consent=True, reviewed=True)
        self.assertEqual(report["status"], "rejected")
        self.assertNotIn("advisor_text", report)

    def test_bad_http_type_rejected(self):
        with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection") as create:
            create.return_value.getresponse.return_value = Reply(b"err", 503, "text/plain")
            report = evaluate_local_image(_photo(), consent=True, reviewed=True)
        self.assertEqual(report["diagnostic"], "http_protocol")

    def test_transport_failure_is_quiet(self):
        with patch("microduck_companion.qwen9b_role_preview.http.client.HTTPConnection", side_effect=OSError("secret path")):
            report = evaluate_local_image(_photo(), consent=True, reviewed=True)
        self.assertEqual(report["status"], "unavailable")
        self.assertNotIn("secret", str(report))


if __name__ == "__main__":
    import unittest
    unittest.main()