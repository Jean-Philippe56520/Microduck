"""Probe integration against two fake Unix daemons, not a real simulator."""
import contextlib
import io
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest

from microduck_companion.sim_probe import collect, main


def send(conn, frame):
    conn.sendall((json.dumps(frame) + "\n").encode())


def recv(conn):
    data = b""
    while b"\n" not in data:
        data += conn.recv(4096)
    return json.loads(data.split(b"\n", 1)[0])


class FakeService:
    def __init__(self, path, serve):
        self.path = path
        self.error = None
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(2.)
        self.socket.bind(str(path))
        self.socket.listen(1)
        def runner():
            try:
                conn, _ = self.socket.accept()
                with conn:
                    conn.settimeout(1.)
                    serve(conn)
            except Exception as exc:
                self.error = exc
            finally:
                self.socket.close()
        self.thread = threading.Thread(target=runner, daemon=True)
        self.thread.start()

    def join(self):
        self.thread.join(timeout=2.)
        if self.thread.is_alive():
            raise AssertionError("fake service stuck")
        if self.error:
            raise self.error


class SimProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.services = []

    def start_services(self, *, healthy=True):
        def robot(conn):
            req = recv(conn)
            self.assertEqual("robot.health", req["method"])
            send(conn, {"jsonrpc": "2.0", "id": req["id"], "result": {
                "healthy": healthy,
                "battery": {"percent": 78.},
                "control_loop": {"target_hz": 50., "achieved_hz": 49.9,
                                 "missed": 0},
            }})
            req = recv(conn)
            self.assertEqual("robot.subscribe", req["method"])
            self.assertEqual({"hz": 2}, req["params"])
            send(conn, {"jsonrpc": "2.0", "id": req["id"], "result": {"accepted": True}})
            for i in range(2):
                send(conn, {"jsonrpc": "2.0", "method": "robot.state", "params": {
                    "safety": {"fallen": False, "limp": False},
                    "loop": {"hz": 49.9, "missed": 0}, "t_ns": (i + 1) * 1000,
                }})
        def tof(conn):
            req = recv(conn)
            self.assertEqual("tof.stream", req["method"])
            send(conn, {"jsonrpc": "2.0", "id": req["id"], "result": {
                "accepted": True, "sensor": "simulated-tof", "rows": 8, "cols": 8,
            }})
            for i in range(2):
                send(conn, {"jsonrpc": "2.0", "method": "tof.frame", "params": {
                    "seq": i, "rows": 8, "cols": 8, "distance_mm": [1200] * 64,
                    "status": [5] * 64, "t_ns": (i + 1) * 1000,
                }})
        self.services = [
            FakeService(self.root / "duck-a.sock", robot),
            FakeService(self.root / "duck-a-tof.sock", tof),
        ]
        self.addCleanup(lambda: [s.join() for s in self.services])

    def test_probe_only_reads_and_never_certifies_floor(self):
        self.start_services()
        reading = collect(self.root)
        self.assertTrue(reading["robot_healthy"])
        self.assertEqual([64, 64], reading["tof_frame_cells"])
        self.assertFalse(reading["floor_certified"])
        self.assertEqual([], reading["commands_sent"])
        self.assertEqual([0, 1], reading["tof_sequences"])

    def test_cli_exits_nonzero_when_robot_unhealthy(self):
        self.start_services(healthy=False)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = main(["--state-dir", str(self.root)])
        self.assertEqual(2, result)
        self.assertIs(json.loads(output.getvalue())["robot_healthy"], False)

    def test_cli_missing_sockets_reports_error(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            result = main(["--state-dir", str(self.root)])
        self.assertEqual(1, result)
        self.assertIn("failed", error.getvalue())


if __name__ == "__main__":
    unittest.main()
