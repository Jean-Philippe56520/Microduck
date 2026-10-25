"""Tests for mock-only OEM frame headers."""
import json
import unittest
from microduck_companion.oem_frame_preflight import (
    FrameContractError, parse_mock_frame_header, check_mock_frame_tail,
    OEM_REVISION, OEM_LOCAL_SOCKET,
)
from microduck_companion.passive_sources import PINNED_OEM_REVISION, OEM_SOCKET

NOW = 1_800_000_000_000_000

def header(width=2,height=1):
    return json.dumps({"jsonrpc":"2.0","id":1,"result":{
        "width":width,"height":height,"format":"UYVY",
        "bytes":width*height*2,"captured_at_unix_us":NOW-1000,
        "rotate":90,
    }}).encode()

class FrameHeaderTests(unittest.TestCase):
    def test_oem_revision_and_socket(self):
        self.assertEqual(OEM_REVISION, PINNED_OEM_REVISION)
        self.assertEqual(OEM_LOCAL_SOCKET, OEM_SOCKET)

    def test_mock_header_untrusted(self):
        v=parse_mock_frame_header(header(), now_unix_us=NOW)
        self.assertEqual((v.width,v.height,v.expected_bytes),(2,1,4))
        self.assertFalse(v.source_verified)
        self.assertFalse(v.physical_camera_validated)
        self.assertEqual(v.motor_commands_issued,0)

    def test_fixture_tail_exact(self):
        result=check_mock_frame_tail(header(),bytes(4),now_unix_us=NOW)
        self.assertTrue(result.tail_length_checked)
        with self.assertRaises(FrameContractError):
            check_mock_frame_tail(header(),bytes(3),now_unix_us=NOW)

    def test_bounded_geometry(self):
        good=parse_mock_frame_header(header(720,1280),now_unix_us=NOW)
        self.assertEqual(good.expected_bytes,1843200)
        for w,h in ((3,1),(0,1),(2,0),(2048,1025)):
            with self.assertRaises(FrameContractError):
                parse_mock_frame_header(header(w,h),now_unix_us=NOW)

if __name__=="__main__":
    unittest.main()
