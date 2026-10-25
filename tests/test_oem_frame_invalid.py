"""Negative cases for media.frame header-shaped fixtures."""
import json
import unittest
from microduck_companion.oem_frame_preflight import parse_mock_frame_header, FrameContractError

NOW=1800000000000000
def frame():
    return {"jsonrpc":"2.0","id":1,"result":{
        "width":2,"height":1,"format":"UYVY","bytes":4,
        "captured_at_unix_us":NOW-1000,"rotate":90}}
def encoded(v):
    return json.dumps(v).encode()

class InvalidFrameTests(unittest.TestCase):
    def test_reject_stale_timestamp(self):
        a=frame()
        a["result"]["captured_at_unix_us"]=NOW-3000000
        with self.assertRaises(FrameContractError):
            parse_mock_frame_header(encoded(a),now_unix_us=NOW)

    def test_reject_wrong_rotation_or_format(self):
        for field,value in (("rotate",45),("format","JPEG"),("bytes",6)):
            a=frame()
            a["result"][field]=value
            with self.assertRaises(FrameContractError):
                parse_mock_frame_header(encoded(a),now_unix_us=NOW)

    def test_reject_unknown_fields(self):
        a=frame()
        a["result"]["extra"]=True
        with self.assertRaises(FrameContractError):
            parse_mock_frame_header(encoded(a),now_unix_us=NOW)

    def test_reject_ambiguous_json(self):
        for raw in (b'{"jsonrpc":"2.0","jsonrpc":"2.0"}',
                    b'{"jsonrpc":NaN}',b"",b"x"*2049):
            with self.assertRaises(FrameContractError):
                parse_mock_frame_header(raw,now_unix_us=NOW)

    def test_reject_nonresponse_methods(self):
        a={"jsonrpc":"2.0","method":"media.detections","params":{}}
        with self.assertRaises(FrameContractError):
            parse_mock_frame_header(encoded(a),now_unix_us=NOW)

if __name__=="__main__":
    unittest.main()
