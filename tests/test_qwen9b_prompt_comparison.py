"""Tests for prompt A/B with synthetic local input and a fake Ollama endpoint."""
import base64
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from PIL import Image

from microduck_companion.ollama_local_client import OllamaEndpoint
from microduck_companion.qwen9b_advisor_v2 import (
    MODEL, Qwen9BPCClient, _wire_balanced, _wire_simple,
)
from microduck_companion.qwen9b_prompt_comparison import compare_approved_image, main


def synthetic_image():
    image = Image.new("RGB", (200, 170), (10, 100, 50))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


class SameImagePromptComparison(unittest.TestCase):
    def test_balanced_prompt_changes_only_instructions(self):
        from microduck_companion.qwen9b_vision_check import make_synthetic_color_question
        question = make_synthetic_color_question("red")
        a = json.loads(_wire_simple(question))
        b = json.loads(_wire_balanced(question))
        self.assertEqual(a["model"], b["model"])
        self.assertEqual("qwen3.5:9b", a["model"])
        self.assertEqual(a["format"], b["format"])
        self.assertEqual(a["options"], b["options"])
        self.assertFalse(a["think"])
        self.assertEqual("0", a["keep_alive"])
        self.assertEqual(a["messages"][1], b["messages"][1])
        self.assertNotEqual(a["messages"][0]["content"], b["messages"][0]["content"])
        for packet in (a,b):
            self.assertEqual(1, len(packet["messages"][1]["images"]))
            self.assertEqual(question.image_jpeg,base64.b64decode(packet["messages"][1]["images"][0]))
            self.assertEqual([question.request_id],packet["format"]["properties"]["request_id"]["enum"])
            self.assertNotIn("motor_command", json.dumps(packet["format"]))
        self.assertNotIn('dog_bed', b['messages'][0]['content'])

    def test_two_calls_share_same_jpeg_but_fresh_request_ids(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args): pass
            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seen.append(req)
                rid = req['format']['properties']['request_id']['enum'][0]
                balanced = 'rather than automatically' in req['messages'][0]['content']
                obj = {'request_id':rid,'category':'toy' if balanced else 'unknown',
                       'depiction':'photograph','visibility':'clear'}
                response=json.dumps({'model':MODEL,'done':True,
                          'message':{'role':'assistant','content':json.dumps(obj)}}).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(response)))
                self.end_headers();self.wfile.write(response)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        t=threading.Thread(target=server.serve_forever,daemon=True)
        t.start()
        try:
            client=Qwen9BPCClient(OllamaEndpoint(f'http://127.0.0.1:{server.server_address[1]}'))
            result,completed=compare_approved_image(synthetic_image(),consent=True,
                operator_reviewed=True,port=server.server_address[1],timeout_s=3,client=client)
            self.assertTrue(completed)
            self.assertEqual('comparison_completed',result['result'])
            self.assertEqual(['simple','balanced'],[s['mode'] for s in result['samples']])
            self.assertEqual(['unknown','toy'],[s['visual_observation']['category'] for s in result['samples']])
            self.assertEqual(['unverified']*2,[s['status'] for s in result['samples']])
            self.assertEqual(2,len(seen))
            self.assertNotEqual(seen[0]['format']['properties']['request_id']['enum'],
                                seen[1]['format']['properties']['request_id']['enum'])
            self.assertEqual(seen[0]['messages'][1]['images'][0],seen[1]['messages'][1]['images'][0])
            for req in seen:
                request_metadata = json.loads(req['messages'][1]['content'])
                self.assertNotIn('local_category', request_metadata)
                self.assertNotIn('dog_bed',req['messages'][0]['content'])
            self.assertFalse(result['verified_recognition'])
            self.assertEqual(0,result['motor_commands_issued'])
            self.assertEqual(0,result['memory_writes'])
            self.assertEqual(0,result['photos_saved_by_companion'])
        finally:
            server.shutdown(); server.server_close(); t.join(timeout=2)

    def test_rejected_first_does_not_issue_second_request(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args): pass
            def do_POST(self):
                request=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                seen.append(1)
                wrong={'request_id':request['format']['properties']['request_id']['enum'][0],
                       'category':'dog_bed', 'depiction':'photograph',
                       'visibility':'clear','motor_command':'kick'}
                payload=json.dumps({'model':MODEL,'done':True,
                                    'message':{'role':'assistant','content':json.dumps(wrong)}}).encode()
                self.send_response(200)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(payload)))
                self.end_headers();self.wfile.write(payload)
        srv=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=srv.serve_forever,daemon=True)
        thread.start()
        try:
            c=Qwen9BPCClient(OllamaEndpoint(f'http://127.0.0.1:{srv.server_address[1]}'))
            report,completed=compare_approved_image(synthetic_image(),consent=True,
                    operator_reviewed=True,port=srv.server_address[1],timeout_s=3,client=c)
            self.assertFalse(completed)
            self.assertEqual('comparison_incomplete',report['result'])
            self.assertEqual(1,len(seen))
            self.assertEqual('rejected',report['samples'][0]['status'])
            self.assertIsNone(report['samples'][0]['visual_observation'])
            self.assertNotIn('kick',json.dumps(report))
        finally:
            srv.shutdown();srv.server_close();thread.join(timeout=2)

    def test_consent_bad_input_and_loopback_guards(self):
        sample=synthetic_image()
        for consent,review in ((False,True),(True,False),(1,True),(True,1)):
            with self.subTest(consent=consent,review=review),self.assertRaises(ValueError):
                compare_approved_image(sample,consent=consent,operator_reviewed=review)
        with self.assertRaises(ValueError):
            compare_approved_image(sample,consent=True,operator_reviewed=True,port=0)
        with self.assertRaises(ValueError):
            compare_approved_image(sample,consent=True,operator_reviewed=True,timeout_s=181)
        with self.assertRaises(ValueError):
            compare_approved_image(b'x'*2_000_001,consent=True,operator_reviewed=True)

    def test_cli_refuses_missing_image_before_network_and_without_traceback(self):
        import sys
        with patch.object(sys,'argv',['qwen9b_prompt_comparison','--image','nonexistent.png',
            '--authorize-image','--reviewed-no-private-subjects']),self.assertRaises(SystemExit) as exc:
            main()
        self.assertEqual(2,exc.exception.code)

    def test_one_click_launcher_is_explicit_two_calls_and_no_cloud(self):
        root=Path(__file__).resolve().parents[1]
        cmd=(root/'COMPARER_VISION_KWIPI.cmd').read_text(encoding='utf-8')
        ps=(root/'scripts'/'kwipi-vision-test.ps1').read_text(encoding='utf-8')
        self.assertIn('-ComparePrompts',cmd)
        self.assertIn('kwipi-vision-test.ps1',cmd)
        self.assertIn('qwen9b_prompt_comparison',ps)
        self.assertIn('Read-Host',ps)
        self.assertIn('Votre approbation couvre EXACTEMENT deux appels',ps)
        self.assertLess(ps.index('Read-Host "Image autorisee'),ps.index('Start-Process -FilePath'))
        self.assertLess(ps.index('Start-Process -FilePath'),ps.index('qwen9b_prompt_comparison'))
        self.assertNotIn('api.openai.com',ps+cmd)
        self.assertNotIn('ollama pull',ps.lower()+cmd.lower())
        self.assertNotIn('github.com',ps.lower()+cmd.lower())
        self.assertNotIn('Invoke-WebRequest',ps)


if __name__ == '__main__':
    unittest.main()