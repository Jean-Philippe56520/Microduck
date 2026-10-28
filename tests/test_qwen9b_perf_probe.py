"""QW-PERF-1: fake Ollama only, never trigger a real model or motor."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

from microduck_companion.ollama_local_client import OllamaEndpoint
from microduck_companion.qwen9b_perf_probe import (
    KEEP_ALIVE, MODEL, PROFILES, _read_one, classify_envelope,
    main, make_probe_request, make_synthetic_jpeg, run_probe,
)


class QwenPerfProbeTests(unittest.TestCase):
    def test_dry_run_never_touches_image_or_ollama(self):
        output = io.StringIO()
        with patch("microduck_companion.qwen9b_perf_probe.make_synthetic_jpeg",
                   side_effect=AssertionError("no image in dry run")):
            with patch("microduck_companion.qwen9b_perf_probe.http.client.HTTPConnection",
                       side_effect=AssertionError("no HTTP in dry run")):
                with redirect_stdout(output):
                    self.assertEqual(0, main([]))
        record = json.loads(output.getvalue())
        self.assertEqual("dry_run_no_network", record["mode"])
        self.assertFalse(record["qwen_pc_model_measured"])
        self.assertEqual(list(PROFILES), record["profiles"])

    def test_run_requires_explicit_approval_before_network(self):
        with self.assertRaises(SystemExit):
            main(["--run"])
        for args in (["--run", "--ollama-port", "0"],
                     ["--run", "--timeout", "nan"],
                     ["--run", "--timeout", "181"]):
            with self.subTest(args=args), self.assertRaises(SystemExit):
                main(args)
        with self.assertRaises(ValueError):
            run_probe(consent=False)
        with self.assertRaises(ValueError):
            run_probe(consent=True, profiles=("compact_json",) * 6)
        with self.assertRaises(ValueError):
            run_probe(consent=True, profiles=("compact_json", "compact_json"))
        with self.assertRaises(ValueError):
            run_probe(consent=True, endpoint=OllamaEndpoint(
                "http://192.168.1.40:11435", unsafe_private_lan_lab=True))

    def test_synthetic_image_is_bounded_stripped_and_consistent(self):
        from microduck_companion.qwen9b_advisor_v2 import _jpeg_dimensions
        jpeg = make_synthetic_jpeg()
        self.assertLessEqual(len(jpeg), 100_000)
        self.assertEqual((256, 256), _jpeg_dimensions(jpeg))
        self.assertEqual(jpeg, make_synthetic_jpeg())

    def test_five_profiles_share_image_model_and_disable_thinking(self):
        jpeg = make_synthetic_jpeg()
        rid = "b" * 32
        packages = [json.loads(make_probe_request(name, jpeg, rid))
                    for name in PROFILES]
        self.assertEqual({MODEL}, {p["model"] for p in packages})
        self.assertEqual({KEEP_ALIVE}, {p["keep_alive"] for p in packages})
        self.assertEqual({False}, {p["think"] for p in packages})
        self.assertEqual({False}, {p["stream"] for p in packages})
        images = [p["messages"][1]["images"][0] for p in packages]
        self.assertEqual(1, len(set(images)))
        self.assertEqual(packages[0], packages[1])
        self.assertNotIn("format", packages[2])
        self.assertEqual(packages[3]["format"], packages[4]["format"])
        self.assertLess(len(packages[3]["messages"][1]["content"]),
                        len(packages[4]["messages"][1]["content"]))
        self.assertEqual(96, packages[3]["options"]["num_predict"])
        self.assertEqual(320, packages[0]["options"]["num_predict"])
        self.assertNotIn("The image depicts a red circle", json.dumps(packages[3]))

    def test_invalid_profiles_and_ids_refused(self):
        jpeg = make_synthetic_jpeg()
        for p in ("", "unknown", "compact_json_private"):
            with self.assertRaises(ValueError):
                make_probe_request(p, jpeg, "f" * 32)
        for rid in ("abc", "g" * 32, "f" * 32 + "x", "A" * 32):
            with self.assertRaises(ValueError):
                make_probe_request("compact_json", jpeg, rid)

    def test_valid_structured_reply_is_unverified_not_memory_fact(self):
        rid = "a" * 32
        contents = json.dumps({"request_id": rid, "shape": "circle",
                               "color": "red"})
        envelope = {"model": MODEL, "done": True, "done_reason": "stop",
                    "message": {"role": "assistant", "content": contents}}
        outcome = classify_envelope(envelope, profile="compact_json", request_id=rid)
        self.assertEqual("unverified", outcome["status"])
        self.assertIs(True, outcome["fixture_shape_color_match"])
        other = {**envelope, "message": {"role": "assistant", "content":
                 json.dumps({"request_id": rid, "shape": "square", "color": "blue"})}}
        self.assertIs(False, classify_envelope(
            other, profile="compact_json", request_id=rid)["fixture_shape_color_match"])
        self.assertIsNone(classify_envelope(
            envelope, profile="role_v2_first", request_id=rid)["fixture_shape_color_match"])

    def test_injected_motor_and_invalid_json_are_never_exported(self):
        rid = "a" * 32
        samples = [
            ('{"request_id":"'+rid+'","shape":"circle","color":"red","motor":"kick"}',
             "schema_invalid"),
            ('{"request_id":"'+rid+'","shape":"circle","shape":"square","color":"red"}',
             "json_invalid"),
            ("PRIVATE_PERSON_NAME", "json_invalid"),
            ('{"request_id":"'+("b" * 32)+'","shape":"circle","color":"red"}',
             "schema_invalid"),
        ]
        for reply, diagnostic in samples:
            envelope = {"model": MODEL, "done": True, "done_reason": "stop",
                        "message": {"role": "assistant", "content": reply}}
            result = classify_envelope(envelope, profile="compact_json", request_id=rid)
            self.assertEqual("rejected", result["status"])
            self.assertEqual(diagnostic, result["diagnostic"])
            self.assertNotIn("PRIVATE_PERSON_NAME", json.dumps(result))
            self.assertNotIn("kick", json.dumps(result))
        for modified in (
            {"done_reason": "length"},
            {"message": {"role": "assistant", "content": "{}",
                         "tool_calls": [{"function": {"name": "write_sql"}}]}},
            {"message": {"role": "assistant", "content": "{}",
                         "thinking": "private reasoning"}},
        ):
            envelope = {"model": MODEL, "done": True,
                        "message": {"role": "assistant", "content": "{}"},
                        **modified}
            result = classify_envelope(envelope, profile="role_v2_first",
                                       request_id=rid)
            self.assertEqual("rejected", result["status"])

    def test_result_is_numeric_only_with_five_fake_samples(self):
        reported = []
        def fake_one(_target, body, profile, request_id, timeout):
            payload = json.loads(body)
            reported.append((profile, payload["model"], payload["keep_alive"]))
            return {"status": "unverified", "diagnostic": "none",
                    "wall_s": 1.2, "load_s": 0, "eval_s": 0.3,
                    "eval_count": 7, "fixture_shape_color_match": None}
        with patch("microduck_companion.qwen9b_perf_probe._read_one",
                   side_effect=fake_one):
            report = run_probe(consent=True, profiles=PROFILES)
        self.assertEqual(5, len(reported))
        self.assertEqual(list(PROFILES), [x["profile"] for x in report["profiles"]])
        self.assertTrue(report["same_synthetic_pixels"])
        self.assertFalse(report["model_identity_independently_verified"])
        self.assertFalse(report["response_content_recorded"])
        self.assertFalse(report["memory_used"])
        self.assertEqual(0, report["private_images_read"])
        self.assertEqual(0, report["motor_commands_issued"])
        self.assertEqual(0, report["memory_writes"])
        self.assertNotIn("advisor_text", json.dumps(report))
        self.assertNotIn("image_jpeg", json.dumps(report))

    def test_transport_rejects_untrusted_envelope_and_does_not_log_text(self):
        rid = "c" * 32
        response_data = {
            "model": MODEL, "done": True, "done_reason": "stop",
            "message": {"role": "assistant", "content": json.dumps({
                "request_id": rid, "shape": "circle", "color": "red"})},
            "load_duration": 2500000000,
            "prompt_eval_duration": 1000000000,
            "eval_duration": 3000000000,
            "eval_count": 20,
            "prompt_eval_count": 100,
        }
        encoded = json.dumps(response_data).encode("utf-8")

        class FakeReply:
            status = 200
            def __init__(self, payload):
                self.payload = payload
            def getheader(self, name, default=None):
                return {"Content-Type": "application/json",
                        "Content-Length": str(len(self.payload))}.get(name, default)
            def read1(self, n):
                value, self.payload = self.payload[:n], self.payload[n:]
                return value
            def close(self):
                pass

        class FakeSocket:
            def settimeout(self, seconds):
                assert seconds > 0

        class FakeConnection:
            sock = FakeSocket()
            def __init__(self, *args, **kwargs):
                self.reply = FakeReply(encoded)
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                return self.reply
            def close(self):
                pass

        with patch("microduck_companion.qwen9b_perf_probe.http.client.HTTPConnection",
                   FakeConnection):
            outcome = _read_one(OllamaEndpoint("http://127.0.0.1:11435"),
                                b"synthetic body", "compact_json", rid, 2)
        self.assertEqual("unverified", outcome["status"])
        self.assertIs(True, outcome["fixture_shape_color_match"])
        self.assertEqual(2.5, outcome["load_s"])
        self.assertEqual(20, outcome["eval_count"])
        self.assertNotIn("message", outcome)
        self.assertNotIn("content", outcome)


if __name__ == "__main__":
    unittest.main()
