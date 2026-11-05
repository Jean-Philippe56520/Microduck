"""SIM-1A: independent fake Unix server tests for read-only mediad protocol."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

from microduck_companion.sim_media_frame import (
    MediaFrameError, acquire_simulated_oem_frame,
)

UNIX = hasattr(socket, "AF_UNIX")


def response(*, stamp=None, width=4, height=2, data=b"0123456789abcdef",
             updates=None):
    header = {
        "width": width, "height": height, "format": "UYVY",
        "bytes": width * height * 2,
        "captured_at_unix_us": stamp or int(time.time() * 1_000_000),
        "rotate": 90,
    }
    if updates:
        header.update(updates)
    return (json.dumps({"jsonrpc": "2.0", "id": 1, "result": header})
            + "\n").encode() + data


@unittest.skipUnless(UNIX, "Linux Unix sockets")
class MediaFrameTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "duck-a-frame.sock"

    def serve(self, wire: bytes, *, delay: float = 0):
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(self.path))
        listener.listen(1)
        received = []
        failures = []

        def run():
            try:
                with listener:
                    conn, _ = listener.accept()
                    with conn:
                        conn.settimeout(2)
                        received.append(conn.recv(4096))
                        if delay:
                            time.sleep(delay)
                        conn.sendall(wire)
            except OSError as exc:
                failures.append(str(exc))
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        self.addCleanup(lambda: thread.join(timeout=3))
        return received

    def test_valid_frame_ephemeral_not_authorized(self):
        got = self.serve(response(data=b"0123456789abcdef"))
        frame = acquire_simulated_oem_frame(self.path)
        self.assertEqual(got, [
            b'{"jsonrpc":"2.0","id":1,"method":"media.frame"}\n'
        ])
        self.assertEqual(frame.pixels_uyvy, b"0123456789abcdef")
        self.assertFalse(frame.evidence["semantic_category_verified"])
        self.assertFalse(frame.evidence["floor_certified"])
        self.assertEqual(frame.evidence["motor_commands_issued"], 0)
        self.assertFalse(frame.evidence["image_persisted"])

    def test_truncated_payload_rejected(self):
        self.serve(response(data=b"1234"))
        with self.assertRaises(MediaFrameError):
            acquire_simulated_oem_frame(self.path)

    def test_geometry_mismatch_rejected(self):
        self.serve(response(updates={"bytes": 100}))
        with self.assertRaises(MediaFrameError):
            acquire_simulated_oem_frame(self.path)

    def test_future_capture_rejected(self):
        self.serve(response(stamp=int((time.time() + 60) * 1_000_000)))
        with self.assertRaises(MediaFrameError):
            acquire_simulated_oem_frame(self.path)

    def test_stale_capture_rejected(self):
        self.serve(response(stamp=int((time.time() - 60) * 1_000_000)))
        with self.assertRaises(MediaFrameError):
            acquire_simulated_oem_frame(self.path)

    def test_non_uyvy_rejected(self):
        self.serve(response(updates={"format": "RGB"}))
        with self.assertRaises(MediaFrameError):
            acquire_simulated_oem_frame(self.path)

    def test_rpc_error_cannot_supply_frame(self):
        self.serve(b'{"jsonrpc":"2.0","id":1,"error":{"code":-32603}}\n')
        with self.assertRaises(MediaFrameError):
            acquire_simulated_oem_frame(self.path)

    def test_wrong_response_id_rejected(self):
        self.serve(response().replace(b'"id": 1', b'"id": 2'))
        with self.assertRaises(MediaFrameError):
            acquire_simulated_oem_frame(self.path)

    def test_overlong_header_rejected(self):
        self.serve(b"x" * 2048 + b"\n")
        with self.assertRaises(MediaFrameError):
            acquire_simulated_oem_frame(self.path)

    def test_timeout_rejected(self):
        self.serve(response(), delay=0.3)
        with self.assertRaises(MediaFrameError):
            acquire_simulated_oem_frame(self.path, timeout_s=0.05)

    def test_no_socket_rejected(self):
        with self.assertRaises(MediaFrameError):
            acquire_simulated_oem_frame(self.path, timeout_s=0.05)


if __name__ == "__main__":
    unittest.main()
