"""Synthetic-only local Qwen image path diagnostic (fake HTTP; no real model)."""
import base64
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image
from microduck_companion.ollama_local_client import OllamaEndpoint
from microduck_companion.qwen9b_advisor_v2 import (
    AdvisoryResult, AdvisorError, COLOR_PROBE_CHOICES, ImageQuestion,
    ModelOutputRejected, Qwen9BPCClient, _wire_color_probe,
    parse_color_probe_reply,
)
from microduck_companion.qwen9b_vision_check import make_synthetic_color_question, run_check


class VisionCheck(unittest.TestCase):
    def test_synthetic_images_have_distinct_expected_pixels_and_no_source_file(self):
        images = []
        for color in ('red', 'blue'):
            q = make_synthetic_color_question(color)
            self.assertTrue(q.consent and q.operator_reviewed)
            self.assertEqual('unknown', q.local_category)
            self.assertLess(len(q.image_jpeg), 100000)
            with Image.open(io.BytesIO(q.image_jpeg)) as img:
                self.assertEqual((256, 256), img.size)
                self.assertEqual({}, dict(img.getexif()))
                rgb = img.getpixel((128, 128))
                if color == 'red':
                    self.assertGreater(rgb[0], rgb[2] + 180)
                else:
                    self.assertGreater(rgb[2], rgb[0] + 180)
            images.append(q.image_jpeg)
        self.assertNotEqual(images[0], images[1])
        with self.assertRaises(ValueError):
            make_synthetic_color_question('green')

    def test_probe_wire_reuses_approved_one_image_and_strict_schema(self):
        q = make_synthetic_color_question('red')
        packet = json.loads(_wire_color_probe(q))
        self.assertEqual('qwen3.5:9b', packet['model'])
        self.assertEqual(1, len(packet['messages'][1]['images']))
        self.assertEqual(q.image_jpeg, base64.b64decode(packet['messages'][1]['images'][0]))
        self.assertEqual([q.request_id], packet['format']['properties']['request_id']['enum'])
        self.assertEqual(list(COLOR_PROBE_CHOICES), packet['format']['properties']['color']['enum'])
        self.assertEqual({'color', 'request_id'}, set(packet['format']['required']))
        self.assertFalse(packet['format']['additionalProperties'])
        self.assertFalse(packet['think'])
        self.assertEqual('0', packet['keep_alive'])
        self.assertEqual(4096, packet['options']['num_ctx'])
        self.assertEqual(80, packet['options']['num_predict'])
        self.assertNotIn('motor', json.dumps(packet['format']))
        self.assertNotIn('identity', json.dumps(packet['format']))
        self.assertNotIn('dog_bed', packet['messages'][1]['content'])

    def test_parse_probe_rejects_untrusted_or_wrong_request_and_is_fresh(self):
        q = make_synthetic_color_question('red')
        good = {'request_id': q.request_id, 'color': 'red'}
        self.assertEqual('red', parse_color_probe_reply(q, json.dumps(good).encode(),
                        received_monotonic_s=q.now_monotonic_s + .1))
        self.assertEqual('unknown', parse_color_probe_reply(q, json.dumps({**good, 'color': 'unknown'}).encode(),
                        received_monotonic_s=q.now_monotonic_s + .2))
        for bad, reason in [
            ({**good, 'color': 'green'}, 'enum_invalid'),
            ({**good, 'motor_command': 'kick'}, 'fields_invalid'),
            ({**good, 'request_id': '0'*32}, 'request_id_mismatch'),
            ({**good, 'color': 1}, 'enum_invalid'),
        ]:
            with self.subTest(bad=bad), self.assertRaises(ModelOutputRejected) as err:
                parse_color_probe_reply(q, json.dumps(bad).encode(),
                                        received_monotonic_s=q.now_monotonic_s + .3)
            self.assertEqual(reason, err.exception.reason)
        with self.assertRaises(ModelOutputRejected) as err:
            parse_color_probe_reply(q, ('{"request_id":"'+q.request_id+'","color":"red","color":"blue"}').encode(),
                                    received_monotonic_s=q.now_monotonic_s + .3)
        self.assertEqual('duplicate_key', err.exception.reason)
        with self.assertRaises(AdvisorError):
            parse_color_probe_reply(q, json.dumps(good).encode(),
                                    received_monotonic_s=q.deadline_monotonic_s)
        with self.assertRaises(ValueError):
            AdvisoryResult('rejected', q.request_id, probe_color='red')
        with self.assertRaises(ValueError):
            AdvisoryResult('unverified', q.request_id, probe_color='private free text')

    def test_2_image_loopback_probe_validates_color_from_actual_transmitted_pixels(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path, req))
                blob = base64.b64decode(req['messages'][1]['images'][0])
                with Image.open(io.BytesIO(blob)) as img:
                    rgb = img.getpixel((128, 128))
                observed = 'red' if rgb[0] > rgb[2] else 'blue'
                answer = json.dumps({'request_id':req['format']['properties']['request_id']['enum'][0],
                                     'color':observed})
                response = json.dumps({'model':'qwen3.5:9b','done':True,
                                       'message':{'role':'assistant','content':answer}}).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(response)))
                self.end_headers()
                self.wfile.write(response)
        srv = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        t = threading.Thread(target=srv.serve_forever,daemon=True)
        t.start()
        try:
            result, passed = run_check(port=srv.server_address[1], timeout_s=3)
            self.assertTrue(passed)
            self.assertEqual('two_colors_distinguished', result['result'])
            self.assertEqual(['red','blue'], [x['observed'] for x in result['samples']])
            self.assertEqual(['red','blue'], [x['expected'] for x in result['samples']])
            self.assertEqual(2,len(requests))
            self.assertTrue(all(x[0]=='/api/chat' for x in requests))
            self.assertEqual(0,result['motor_commands_issued'])
            self.assertEqual(0,result['memory_writes'])
            self.assertEqual(0,result['private_images_read'])
        finally:
            srv.shutdown();srv.server_close();t.join(timeout=2)

    def test_invalid_first_model_answer_stops_without_second_request(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_POST(self):
                seen.append(1)
                req=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                response=json.dumps({'model':'qwen3.5:9b','done':True,
                                     'message':{'role':'assistant','content':json.dumps({
                                         'request_id':req['format']['properties']['request_id']['enum'][0],
                                         'color':'red','command':'robot.do'})}}).encode()
                self.send_response(200); self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(response))); self.end_headers()
                self.wfile.write(response)
        srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
        try:
            report, passed = run_check(port=srv.server_address[1], timeout_s=3)
            self.assertFalse(passed)
            self.assertEqual(1,len(seen))
            self.assertEqual('not_demonstrated',report['result'])
            self.assertEqual('rejected',report['samples'][0]['status'])
            self.assertEqual('fields_invalid',report['samples'][0]['diagnostic_reason'])
            self.assertNotIn('robot.do',json.dumps(report))
        finally:
            srv.shutdown();srv.server_close();t.join(timeout=2)

    def test_second_color_is_wrong_then_diagnostic_stays_inconclusive(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                req=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                seen.append(1)
                answer=json.dumps({'request_id':req['format']['properties']['request_id']['enum'][0],
                                   'color':'red'})
                body=json.dumps({'model':'qwen3.5:9b','done':True,
                                 'message':{'role':'assistant','content':answer}}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        t=threading.Thread(target=srv.serve_forever,daemon=True);t.start()
        try:
            result,passed=run_check(port=srv.server_address[1],timeout_s=3)
            self.assertFalse(passed)
            self.assertEqual(2,len(seen))
            self.assertEqual(['red','red'],[x['observed'] for x in result['samples']])
            self.assertEqual('not_demonstrated',result['result'])
        finally:
            srv.shutdown();srv.server_close();t.join(timeout=2)

    def test_windows_batch_uses_existing_launcher_and_no_private_image(self):
        root=Path(__file__).resolve().parents[1]
        cmd=(root/'VERIFIER_VISION_KWIPI.cmd').read_text(encoding='utf-8')
        ps=(root/'scripts'/'kwipi-vision-test.ps1').read_text(encoding='utf-8')
        self.assertIn('-VisionCheck',cmd)
        self.assertIn('kwipi-vision-test.ps1',cmd)
        self.assertIn('} else {',ps)
        self.assertIn('if ($VisionCheck)',ps)
        self.assertIn('qwen9b_vision_check',ps)
        self.assertIn('if ($VisionCheck -and $Image)',ps)
        self.assertNotIn('ollama pull',cmd.lower()+ps.lower())
        self.assertNotIn('api.openai.com',cmd.lower()+ps.lower())
        self.assertLess(ps.index('if ($VisionCheck)'),ps.index('Start-Process -FilePath'))

    def test_no_public_connections_or_python_side_effects_on_import(self):
        import microduck_companion.qwen9b_vision_check as check
        self.assertTrue(callable(check.main))
        with self.assertRaises(ValueError):
            run_check(port=0)
        with self.assertRaises(ValueError):
            run_check(port=65536)


if __name__ == '__main__':
    unittest.main()