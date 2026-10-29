"""One-frame manufacturer camera TCP fixture tests, no renderer or motor."""
from __future__ import annotations

import socket
import struct
import threading
import unittest

from microduck_companion.sim_visual_direct import (
    MAX_CAMERA_BYTES, VisualProbeError, read_official_rendered_frame,
)


class OneFrameServer:
    def __init__(self, chunks: tuple[bytes, ...]):
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.chunks = chunks
        self.completed = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self) -> None:
        try:
            conn, _ = self.listener.accept()
            with conn:
                for chunk in self.chunks:
                    if not chunk:
                        continue
                    try:
                        conn.sendall(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        break
        finally:
            self.listener.close()
            self.completed.set()

    def join(self) -> None:
        self.completed.wait(5.0)
        self.thread.join(5.0)


class OfficialCameraWireTests(unittest.TestCase):
    def test_full_uyvy_frame_over_separate_tcp_chunks(self):
        raw = bytes([128, 100, 129, 101]) * (MAX_CAMERA_BYTES // 4)
        server = OneFrameServer((struct.pack("<I", len(raw)), raw[:5],
                                 raw[5:100_000], raw[100_000:]))
        try:
            self.assertEqual(read_official_rendered_frame(port=server.port),
                             raw)
        finally:
            server.join()

    def test_refuse_wrong_frame_length_before_allocating(self):
        server = OneFrameServer((struct.pack("<I", MAX_CAMERA_BYTES + 1),))
        try:
            with self.assertRaises(VisualProbeError):
                read_official_rendered_frame(port=server.port)
        finally:
            server.join()

    def test_refuse_truncated_frame_payload(self):
        server = OneFrameServer((
            struct.pack("<I", MAX_CAMERA_BYTES),
            bytes(100),
        ))
        try:
            with self.assertRaises(VisualProbeError):
                read_official_rendered_frame(port=server.port)
        finally:
            server.join()

    def test_refuse_truncated_header(self):
        server = OneFrameServer((bytes([0x00, 0x01]),))
        try:
            with self.assertRaises(VisualProbeError):
                read_official_rendered_frame(port=server.port)
        finally:
            server.join()

    def test_refuse_invalid_or_remote_port(self):
        for value in [0, 80, 65536, "17901", True, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                read_official_rendered_frame(port=value)


if __name__ == "__main__":
    unittest.main()
