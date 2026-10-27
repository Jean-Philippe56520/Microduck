"""F5 v2: strict PC-only multimodal hypotheses, without an actual Qwen/robot."""
import base64
import io
import json
import math
import threading
import time
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from microduck_companion.qwen9b_advisor_v2 import (
    AdvisorError, ImageQuestion, Qwen9BPCClient, MAX_IMAGE_BYTES,
    MAX_SOURCE_BYTES, MODEL, _wire, parse_reply, prepare_jpeg,
)
from microduck_companion.ollama_local_client import OllamaEndpoint


def sample():
    from PIL import Image
    img = Image.new('RGB', (300, 300), (120, 30, 10))
    output = io.BytesIO()
    img.save(output, format='PNG', pnginfo=None)
    return prepare_jpeg(output.getvalue())


def question(*, now=None, consent=True, reviewed=True, image=None):
    now = time.monotonic() if now is None else now
    return ImageQuestion(uuid.uuid4().hex, sample() if image is None else image,
                         'unknown', consent, reviewed, now, now + 10.0)


def good_reply(q):
    return {'schema_version': 2, 'request_id': q.request_id,
            'source': 'pc_qwen_unverified', 'hypotheses': [{
                'category': 'ball', 'confidence': 0.45, 'properties': ['round'],
                'uses': ['play_possible'], 'relations': ['unknown'],
                'possible_outcomes': ['may_roll'],
                'suggested_observations': ['observe_from_distance'],
                'risks': ['unknown_manipulation'],
                'unknowns': ['manipulation_feasibility'],
            }]}


class ImageAndSchema(unittest.TestCase):
    def test_image_recompression_dimensions_and_no_exif(self):
        from PIL import Image
        img = Image.new('RGB', (1300, 700), (0, 140, 90))
        image = io.BytesIO()
        img.save(image, format='JPEG', exif=b'private EXIF data')
        out = prepare_jpeg(image.getvalue())
        self.assertLessEqual(len(out), MAX_IMAGE_BYTES)
        self.assertNotIn(b'EXIF', out)
        self.assertNotIn(b'private EXIF data', out)
        with Image.open(io.BytesIO(out)) as opened:
            self.assertLessEqual(max(opened.size), 512)
            self.assertFalse(opened.getexif())

    def test_requires_two_explicit_operator_approvals(self):
        for consent, reviewed in [(False, True), (True, False), (0, True), (True, 1)]:
            with self.subTest(consent=consent, reviewed=reviewed):
                with self.assertRaises(AdvisorError):
                    question(consent=consent, reviewed=reviewed)

    def test_bad_input_image_and_oversize_rejected(self):
        with self.assertRaises(AdvisorError):
            prepare_jpeg(b'not a picture')
        with self.assertRaises(AdvisorError):
            prepare_jpeg(b'x' * (MAX_SOURCE_BYTES + 1))
        with self.assertRaises(AdvisorError):
            question(image=b'\xff\xd8fake\xff\xd9')
        with self.assertRaises(AdvisorError):
            question(image=sample().replace(b'JFIF', b'EXIF'))

    def test_wired_request_has_exactly_one_image_and_no_motor_authority(self):
        q = question()
        body = json.loads(_wire(q))
        self.assertEqual(MODEL, body['model'])
        self.assertEqual(4096, body['options']['num_ctx'])
        self.assertEqual('0', body['keep_alive'])
        self.assertFalse(body['stream'])
        self.assertEqual(1, len(body['messages'][1]['images']))
        self.assertEqual(q.image_jpeg, base64.b64decode(body['messages'][1]['images'][0]))
        user = json.loads(body['messages'][1]['content'])
        self.assertNotIn('motor', body['format']['properties'])
        self.assertNotIn('execute', body['format']['properties'])
        self.assertEqual('unknown', user['local_category'])
        self.assertNotIn('memory', user)
        self.assertNotIn('track_id', user)
        self.assertNotIn('speaker', body['format']['properties'])

    def test_bounded_parsed_advice_is_always_unverified(self):
        q = question(now=100)
        hypotheses = parse_reply(q, json.dumps(good_reply(q)).encode(), received_monotonic_s=101)
        self.assertEqual('ball', hypotheses[0].category)
        self.assertFalse(hypotheses[0].verified)
        self.assertFalse(hypotheses[0].physical_actions_authorized)
        self.assertEqual('pc_qwen_unverified', hypotheses[0].source)

    def test_abstention_is_valid(self):
        q = question(now=100)
        result = good_reply(q)
        result['hypotheses'] = []
        self.assertEqual((), parse_reply(q, json.dumps(result).encode(), received_monotonic_s=100.1))

    def test_reply_rejects_actions_identities_duplicates_wrong_id_and_stale(self):
        q = question(now=100)
        basic = good_reply(q)
        def parse(x):
            return parse_reply(q, json.dumps(x).encode(), received_monotonic_s=100.2)
        for key, value in [('motor_command', 'ground_pick'), ('reward', 1),
                           ('identity', 'Nessquick'), ('safe_to_approach', True),
                           ('command', 'kick_left')]:
            bad = json.loads(json.dumps(basic))
            bad['hypotheses'][0][key] = value
            with self.subTest(key=key), self.assertRaises(AdvisorError):
                parse(bad)
        bad = json.loads(json.dumps(basic))
        bad['hypotheses'][0]['risks'] = ['kick_dog']
        with self.assertRaises(AdvisorError):
            parse(bad)
        bad = json.loads(json.dumps(basic))
        bad['request_id'] = uuid.uuid4().hex
        with self.assertRaises(AdvisorError):
            parse(bad)
        with self.assertRaises(AdvisorError):
            parse_reply(q, json.dumps(basic).encode(), received_monotonic_s=110)
        raw = json.dumps(basic).replace('"schema_version": 2', '"schema_version": 2, "schema_version": 2')
        with self.assertRaises(AdvisorError):
            parse_reply(q, raw.encode(), received_monotonic_s=100.2)

    def test_nonfinite_and_explicit_unknown_not_allowed_as_fact(self):
        q = question(now=100)
        raw = good_reply(q)
        raw['hypotheses'][0]['confidence'] = math.nan
        with self.assertRaises(AdvisorError):
            parse_reply(q, json.dumps(raw).encode(), received_monotonic_s=100.1)


class HTTPPilot(unittest.TestCase):
    def test_cli_can_target_dedicated_loopback_port(self):
        import tempfile
        import sys
        from pathlib import Path
        from PIL import Image
        from microduck_companion.qwen9b_advisor_v2 import main, AdvisoryResult
        image_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        try:
            Image.new('RGB', (20, 20), (30, 40, 50)).save(image_file, format='PNG')
            image_file.close()
            with patch.object(sys, 'argv', [
                'qwen9b_advisor_v2', '--image', image_file.name,
                '--authorize-image', '--reviewed-no-private-subjects',
                '--ollama-port', '11435',
            ]), patch('microduck_companion.qwen9b_advisor_v2.Qwen9BPCClient') as client:
                client.return_value.query.side_effect = lambda q, **kw: AdvisoryResult(
                    'unverified', q.request_id, ())
                with patch('builtins.print'):
                    self.assertEqual(0, main())
                self.assertEqual(('127.0.0.1', 11435), client.call_args[0][0].host_port)
                self.assertLessEqual(client.return_value.query.call_args[1]['timeout_s'], 180)
        finally:
            image_file.close()
            Path(image_file.name).unlink(missing_ok=True)

    def test_cli_rejects_invalid_port(self):
        import sys
        from microduck_companion.qwen9b_advisor_v2 import main
        with patch.object(sys, 'argv', ['qwen9b_advisor_v2', '--image', 'placeholder',
                                        '--ollama-port', '0']), self.assertRaises(SystemExit):
            main()

    def test_only_existing_f5b_loopback_endpoint_allowed_for_images(self):
        with self.assertRaises(ValueError):
            OllamaEndpoint('http://example.com:11434')
        with self.assertRaises(AdvisorError):
            Qwen9BPCClient(OllamaEndpoint('http://192.168.1.2:11434', unsafe_private_lan_lab=True))

    def test_http_loopback_image_and_strict_answer(self):
        q = question()
        captured = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_POST(self):
                n = int(self.headers['Content-Length'])
                raw = self.rfile.read(n)
                captured.append((self.path, json.loads(raw)))
                response = {'model': MODEL, 'done': True,
                            'message': {'role': 'assistant', 'content': json.dumps(good_reply(q))}}
                wire = json.dumps(response).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(wire)))
                self.end_headers()
                self.wfile.write(wire)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint = OllamaEndpoint(f'http://127.0.0.1:{server.server_address[1]}')
            result = Qwen9BPCClient(endpoint).query(q, timeout_s=2)
            self.assertEqual('unverified', result.status)
            self.assertEqual('ball', result.hypotheses[0].category)
            self.assertEqual(0, result.motor_commands_issued)
            self.assertEqual(0, result.memory_writes)
            self.assertEqual('/api/chat', captured[0][0])
            self.assertEqual(MODEL, captured[0][1]['model'])
            self.assertEqual(1, len(captured[0][1]['messages'][1]['images']))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_diagnostic_stages_never_expose_model_text_or_run_actions(self):
        from microduck_companion.qwen9b_advisor_v2 import AdvisoryResult
        q = question()
        unsafe = good_reply(q)
        unsafe['hypotheses'][0]['motor_command'] = 'kick_left'
        invalid_model = json.dumps(unsafe)
        cases = [
            ('invalid_output', {'model': MODEL, 'done': True,
                                'message': {'role': 'assistant',
                                            'content': invalid_model}}, 'model_output'),
            ('generation_limit', {'model': MODEL, 'done': True,
                                  'done_reason': 'length',
                                  'message': {'role': 'assistant',
                                              'content': '{'}}, 'generation_limit'),
            ('invalid_envelope', {'model': 'other-model', 'done': True,
                                  'message': {'role': 'assistant',
                                              'content': invalid_model}}, 'ollama_envelope'),
        ]
        for name, payload, stage in cases:
            with self.subTest(name=name):
                class Handler(BaseHTTPRequestHandler):
                    def log_message(self, *_args):
                        pass
                    def do_POST(self):
                        self.rfile.read(int(self.headers['Content-Length']))
                        wire = json.dumps(payload).encode()
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Content-Length', str(len(wire)))
                        self.end_headers()
                        self.wfile.write(wire)
                server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    endpoint = OllamaEndpoint(f'http://127.0.0.1:{server.server_address[1]}')
                    result = Qwen9BPCClient(endpoint).query(q, timeout_s=2)
                    self.assertEqual('rejected', result.status)
                    self.assertEqual(stage, result.diagnostic_stage)
                    self.assertEqual((), result.hypotheses)
                    self.assertEqual(0, result.memory_writes)
                    self.assertEqual(0, result.motor_commands_issued)
                    self.assertNotIn('kick_left', result.diagnostic_stage)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2)
        with self.assertRaises(ValueError):
            AdvisoryResult('rejected', q.request_id, diagnostic_stage='raw private text')

    def test_cli_missing_image_is_clean_error(self):
        import sys
        from microduck_companion.qwen9b_advisor_v2 import main
        with patch.object(sys, 'argv', [
            'qwen9b_advisor_v2', '--image', 'not_a_real_photo.jpg',
            '--authorize-image', '--reviewed-no-private-subjects',
        ]), self.assertRaises(SystemExit) as err:
            main()
        self.assertEqual(2, err.exception.code)

    def test_no_server_is_unavailable_without_side_effects(self):
        # Request timeouts are controlled even for connection refusal.
        q = question()
        endpoint = OllamaEndpoint('http://127.0.0.1:9')
        result = Qwen9BPCClient(endpoint).query(q, timeout_s=.5)
        self.assertEqual('unavailable', result.status)
        self.assertEqual(0, result.motor_commands_issued)
        self.assertEqual(0, result.memory_writes)


class FixedModelOutputReasonTests(unittest.TestCase):
    """No model text, images, names, IDs or freeform exceptions in diagnostics."""

    def test_schema_pins_dynamic_request_id_but_parser_remains_authoritative(self):
        q = question()
        body = json.loads(_wire(q))
        self.assertEqual([q.request_id], body['format']['properties']['request_id']['enum'])
        self.assertEqual('string', body['format']['properties']['request_id']['type'])
        self.assertEqual(4096, body['options']['num_ctx'])
        self.assertEqual(1, len(body['messages'][1]['images']))

    def test_invalid_outputs_are_classified_without_untrusted_values(self):
        from microduck_companion.qwen9b_advisor_v2 import (
            ModelOutputRejected, MODEL_OUTPUT_REASONS,
        )
        q = question(now=100)
        base = good_reply(q)
        cases = []
        cases.append((b'not-json-private-text', 'json_invalid'))
        cases.append((json.dumps(base).replace('"schema_version": 2',
                          '"schema_version": 2, "schema_version": 2').encode(),
                      'duplicate_key'))
        cases.append((b'a' * 9000, 'response_size'))
        other = json.loads(json.dumps(base))
        other['request_id'] = 'a' * 32
        cases.append((json.dumps(other).encode(), 'request_id_mismatch'))
        other = json.loads(json.dumps(base))
        other['source'] = 'attacker_payload'
        cases.append((json.dumps(other).encode(), 'schema_invalid'))
        other = json.loads(json.dumps(base))
        other['hypotheses'] = [{}] * 4
        cases.append((json.dumps(other).encode(), 'hypotheses_invalid'))
        other = json.loads(json.dumps(base))
        other['hypotheses'][0]['motor_command'] = 'kick_left'
        cases.append((json.dumps(other).encode(), 'fields_invalid'))
        other = json.loads(json.dumps(base))
        other['hypotheses'][0]['category'] = 'child_identity_private'
        cases.append((json.dumps(other).encode(), 'category_invalid'))
        other = json.loads(json.dumps(base))
        other['hypotheses'][0]['confidence'] = -0.1
        cases.append((json.dumps(other).encode(), 'confidence_invalid'))
        other = json.loads(json.dumps(base))
        other['hypotheses'][0]['risks'] = ['kick_dog']
        cases.append((json.dumps(other).encode(), 'enum_invalid'))
        other = json.loads(json.dumps(base))
        other['hypotheses'][0]['risks'] = ['unknown', 'unknown']
        cases.append((json.dumps(other).encode(), 'enum_invalid'))
        for wire, reason in cases:
            with self.subTest(reason=reason), self.assertRaises(ModelOutputRejected) as raised:
                parse_reply(q, wire, received_monotonic_s=100.1)
            self.assertEqual(reason, raised.exception.reason)
            self.assertIn(reason, MODEL_OUTPUT_REASONS)
            self.assertNotIn('kick_left', raised.exception.reason)
            self.assertNotIn('private', raised.exception.reason)

    def test_http_does_not_echo_model_text_or_correlation_id_in_reason(self):
        from microduck_companion.qwen9b_advisor_v2 import AdvisoryResult
        q = question()
        fake = good_reply(q)
        fake['request_id'] = '0' * 32
        fake['hypotheses'][0]['unknown_private_identifier'] = 'private payload'
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                reply = json.dumps({'model': MODEL, 'done': True,
                                    'message': {'role': 'assistant',
                                                'content': json.dumps(fake)}}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(reply)))
                self.end_headers()
                self.wfile.write(reply)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            endpoint = OllamaEndpoint(f'http://127.0.0.1:{server.server_address[1]}')
            result = Qwen9BPCClient(endpoint).query(q, timeout_s=2)
            self.assertEqual('rejected', result.status)
            self.assertEqual('model_output', result.diagnostic_stage)
            self.assertEqual('request_id_mismatch', result.diagnostic_reason)
            self.assertEqual((), result.hypotheses)
            self.assertEqual(0, result.motor_commands_issued)
            self.assertEqual(0, result.memory_writes)
            self.assertNotIn(q.request_id, result.diagnostic_reason)
            self.assertNotIn('private payload', result.diagnostic_reason)
        finally:
            server.shutdown()
            server.server_close()
            t.join(timeout=2)
        with self.assertRaises(ValueError):
            AdvisoryResult('rejected', q.request_id, diagnostic_stage='model_output',
                           diagnostic_reason='unsafe data leak')
        with self.assertRaises(ValueError):
            AdvisoryResult('rejected', q.request_id, diagnostic_stage='transport',
                           diagnostic_reason='schema_invalid')
        self.assertEqual('none', AdvisoryResult('unverified', q.request_id).diagnostic_reason)


if __name__ == '__main__':
    unittest.main()