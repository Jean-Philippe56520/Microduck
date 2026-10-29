"""SIM-VIS-A1 positive/negative IPC and scene tests; no real camera or motor."""
from __future__ import annotations

import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

from microduck_companion.sim_visual_a1 import (
    FRAME_HEIGHT, FRAME_WIDTH, VisualProbeError, read_frame,
    scene_ball_inventory,
)


def make_frame(*, rotation=90, age_us=0, truncate=False, stale=False):
    now_us = time.time_ns() // 1000
    pixels = bytes((128, 90, 128, 110)) * (FRAME_WIDTH * FRAME_HEIGHT // 2)
    header = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "result": {
            "width": FRAME_WIDTH, "height": FRAME_HEIGHT,
            "format": "UYVY", "bytes": len(pixels),
            "captured_at_unix_us": now_us - (3_000_000 if stale else age_us),
            "rotate": rotation,
        },
    }).encode() + b"\n"
    return header + (pixels[:-200] if truncate else pixels)


class OneShotUnixServer:
    def __init__(self, root: Path, payload: bytes):
        self.socket_path = root / "duck-a-frame.sock"
        self.listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.listener.bind(str(self.socket_path))
        self.listener.listen(1)
        self.payload = payload
        self.done = threading.Event()
        self.worker = threading.Thread(target=self.serve, daemon=True)
        self.worker.start()

    def serve(self):
        try:
            conn, _ = self.listener.accept()
            with conn:
                conn.settimeout(2.0)
                conn.recv(512)
                try:
                    conn.sendall(self.payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        finally:
            self.listener.close()
            self.done.set()

    def finish(self):
        self.done.wait(3.0)
        self.worker.join(3.0)


class SimVisualA1Tests(unittest.TestCase):
    def test_oem_frame_exact_header_and_payload(self):
        with tempfile.TemporaryDirectory() as dirname:
            server = OneShotUnixServer(Path(dirname), make_frame())
            try:
                shape, pixels = read_frame(server.socket_path)
                self.assertTrue(shape.tail_length_checked)
                self.assertEqual((shape.width, shape.height, shape.rotation),
                                 (640, 360, 90))
                self.assertEqual(len(pixels), 640 * 360 * 2)
                self.assertLessEqual(shape.age_us, 2_000_000)
            finally:
                server.finish()

    def test_missing_socket_fails_closed(self):
        with tempfile.TemporaryDirectory() as dirname:
            with self.assertRaises(VisualProbeError):
                read_frame(Path(dirname) / "duck-a-frame.sock")

    def test_truncated_frame_is_not_success(self):
        with tempfile.TemporaryDirectory() as dirname:
            server = OneShotUnixServer(Path(dirname), make_frame(truncate=True))
            try:
                with self.assertRaises(VisualProbeError):
                    read_frame(server.socket_path)
            finally:
                server.finish()

    def test_stale_frame_is_not_success(self):
        with tempfile.TemporaryDirectory() as dirname:
            server = OneShotUnixServer(Path(dirname), make_frame(stale=True))
            try:
                with self.assertRaises(VisualProbeError):
                    read_frame(server.socket_path)
            finally:
                server.finish()

    def test_wrong_camera_rotation_is_not_success(self):
        with tempfile.TemporaryDirectory() as dirname:
            server = OneShotUnixServer(Path(dirname), make_frame(rotation=0))
            try:
                with self.assertRaises(VisualProbeError):
                    read_frame(server.socket_path)
            finally:
                server.finish()

    def test_world_inventory_is_not_visible_ground_truth(self):
        template = """<mujoco><worldbody>{bodies}</worldbody></mujoco>"""
        sphere = """<body name="ball_{i}"><freejoint/>
          <geom name="ball_{i}_geom" type="sphere" size="0.04"/></body>"""
        with tempfile.TemporaryDirectory() as dirname:
            scene = Path(dirname) / "scene.xml"
            scene.write_text(template.format(
                bodies="".join(sphere.format(i=i) for i in range(3))
            ), encoding="utf-8")
            self.assertEqual(scene_ball_inventory(scene), 3)
            scene.write_text(template.format(
                bodies="".join(sphere.format(i=i) for i in range(2))
            ), encoding="utf-8")
            with self.assertRaises(VisualProbeError):
                scene_ball_inventory(scene)

    def test_static_ball_is_not_dynamic_ball(self):
        with tempfile.TemporaryDirectory() as dirname:
            scene = Path(dirname) / "scene.xml"
            scene.write_text(
                '<mujoco><worldbody><body name="ball_0">'
                '<geom name="ball_0_geom" type="sphere"/></body></worldbody></mujoco>',
                encoding="utf-8",
            )
            with self.assertRaises(VisualProbeError):
                scene_ball_inventory(scene)


if __name__ == "__main__":
    unittest.main()
