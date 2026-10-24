"""Fake Unix-socket protocol tests; NOT a MuJoCo or robot hardware test."""
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

from microduck_companion.sim_ipc import (
    DepthReading, HealthReading, Notification, ReadOnlyUnixRpc, StateReading,
    TelemetryError, TelemetryTimeout, parse_depth, parse_health, parse_state,
    read_health,
)


def response(request_id, result):
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def notification(method, params):
    return {"jsonrpc": "2.0", "method": method, "params": params}


class FakeUnixDaemon:
    def __init__(self, workdir, *, script, accept_timeout=2.):
        self.path = str(Path(workdir) / "daemon.sock")
        self.script = script
        self.error = None
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.settimeout(accept_timeout)
        self.server.bind(self.path)
        self.server.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        try:
            conn, _ = self.server.accept()
            with conn:
                conn.settimeout(.6)
                self.script(conn)
        except Exception as exc:
            self.error = exc
        finally:
            self.server.close()

    def close(self):
        self.thread.join(timeout=3.)
        if self.thread.is_alive():
            raise RuntimeError("fake daemon did not exit")
        if self.error is not None:
            raise self.error


def recv_request(conn):
    buffer = b""
    while b"\n" not in buffer:
        part = conn.recv(4096)
        if not part:
            raise AssertionError("missing JSON-RPC request")
        buffer += part
    return json.loads(buffer.split(b"\n", 1)[0])


def send(conn, frame):
    conn.sendall((json.dumps(frame) + "\n").encode())


class ReadOnlyRpcTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.daemons = []

    def daemon(self, script):
        daemon = FakeUnixDaemon(self.tmp.name, script=script)
        self.daemons.append(daemon)
        self.addCleanup(daemon.close)
        return daemon.path

    def test_health_uses_only_official_query_and_preserves_unknown_battery(self):
        def serve(conn):
            request = recv_request(conn)
            self.assertEqual("robot.health", request["method"])
            self.assertNotIn("params", request)
            send(conn, response(request["id"], {
                "healthy": True,
                "battery": None,
                "control_loop": {"target_hz": 50., "achieved_hz": None,
                                 "missed": 0, "ticks": 0,
                                 "last_tick_age_ms": 1},
            }))
        got = read_health(self.daemon(serve))
        self.assertIsInstance(got, HealthReading)
        self.assertIsNone(got.battery_pct)
        self.assertIsNone(got.achieved_hz)
        self.assertEqual(50., got.target_hz)
        self.assertEqual(0, got.missed_ticks)
        self.assertGreater(got.received_at, 0)

    def test_battery_and_achieved_rate_are_captured(self):
        got = parse_health({"healthy": True, "battery": {"percent": 71.2},
                            "control_loop": {"target_hz": 50.,
                                             "achieved_hz": 49.8,
                                             "missed": 3}}, 12.)
        self.assertEqual((71.2, 49.8, 3),
                         (got.battery_pct, got.achieved_hz, got.missed_ticks))

    def test_unhealthy_result_never_becomes_healthy(self):
        got = parse_health({"healthy": False}, 12.)
        self.assertFalse(got.healthy)
        self.assertIsNone(got.battery_pct)

    def test_invalid_health_measurements_rejected(self):
        cases = ({"healthy": "yes"}, {"healthy": True,
                 "battery": {"percent": 105}},
                 {"healthy": True, "battery": {"percent": False}},
                 {"healthy": True, "control_loop": {"missed": -2}},
                 {"healthy": True, "control_loop": {"achieved_hz": -4}})
        for case in cases:
            with self.subTest(case=case), self.assertRaises(TelemetryError):
                parse_health(case, 1.)

    def test_reject_motor_request_without_connecting(self):
        for name in ("robot.move", "robot.stop", "robot.head", "robot.enable",
                     "robot.look", "robot.rest"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    ReadOnlyUnixRpc("/tmp/fake").request(name)

    def test_subscription_restricts_rate_and_receives_state(self):
        state = {"safety": {"fallen": False, "limp": False},
                 "loop": {"hz": 49.6, "missed": 1}, "t_ns": 123}
        def serve(conn):
            request = recv_request(conn)
            self.assertEqual("robot.subscribe", request["method"])
            self.assertEqual({"hz": 5}, request["params"])
            send(conn, response(request["id"], {"accepted": True}))
            send(conn, notification("robot.state", state))
        path = self.daemon(serve)
        with ReadOnlyUnixRpc(path) as reader:
            reader.request("robot.subscribe", hz=5)
            got = parse_state(reader.next_notification())
        self.assertIsInstance(got, StateReading)
        self.assertEqual(49.6, got.achieved_hz)
        self.assertEqual(123, got.t_ns)

    def test_tof_frame_keeps_raw_status_not_free_floor(self):
        frame = {"seq": 3, "rows": 8, "cols": 8, "distance_mm": [1200] * 64,
                 "status": [5] * 64, "t_ns": 100}
        def serve(conn):
            request = recv_request(conn)
            self.assertEqual("tof.stream", request["method"])
            send(conn, response(request["id"], {"accepted": True, "rows": 8, "cols": 8}))
            send(conn, notification("tof.frame", frame))
        path = self.daemon(serve)
        with ReadOnlyUnixRpc(path) as reader:
            reader.request("tof.stream")
            got = parse_depth(reader.next_notification())
        self.assertIsInstance(got, DepthReading)
        self.assertEqual(64, len(got.distance_mm))
        self.assertEqual(5, got.status[0])
        self.assertFalse(hasattr(got, "floor_clear"))

    def test_malformed_tof_frame_rejected(self):
        good = {"rows": 8, "cols": 8, "distance_mm": [1000] * 64,
                "status": [5] * 64, "seq": 3}
        variants = (
            dict(good, rows=7), dict(good, distance_mm=[1000] * 63),
            dict(good, status=[False] * 64), dict(good, distance_mm=[40000] * 64),
            dict(good, seq=-1),
        )
        for item in variants:
            with self.subTest(item=item), self.assertRaises(TelemetryError):
                parse_depth(Notification("tof.frame", item, 10.))

    def test_state_rejects_missing_safety(self):
        with self.assertRaises(TelemetryError):
            parse_state(Notification("robot.state", {"loop": {"hz": 50., "missed": 0}}, 0.))

    def test_future_or_missing_t_ns_is_unknown(self):
        got = parse_state(Notification("robot.state", {
            "safety": {"fallen": False, "limp": False},
            "loop": {"hz": 50., "missed": 0}, "t_ns": 0,
        }, 11.))
        self.assertIsNone(got.t_ns)

    def test_mismatched_response_id_rejected(self):
        def serve(conn):
            recv_request(conn)
            send(conn, response(999, {"healthy": True}))
        with ReadOnlyUnixRpc(self.daemon(serve)) as reader:
            with self.assertRaises(TelemetryError):
                reader.request("robot.health")

    def test_daemon_error_rejected(self):
        def serve(conn):
            req = recv_request(conn)
            send(conn, {"jsonrpc": "2.0", "id": req["id"],
                        "error": {"code": -32601, "message": "method not found"}})
        with ReadOnlyUnixRpc(self.daemon(serve)) as reader:
            with self.assertRaises(TelemetryError):
                reader.request("robot.health")

    def test_subscription_refusal_rejected(self):
        def serve(conn):
            req = recv_request(conn)
            send(conn, response(req["id"], {"accepted": False}))
        with ReadOnlyUnixRpc(self.daemon(serve)) as reader:
            with self.assertRaises(TelemetryError):
                reader.request("tof.stream")

    def test_timeout_on_silent_daemon(self):
        def serve(conn):
            recv_request(conn)
            time.sleep(.15)
        with ReadOnlyUnixRpc(self.daemon(serve), timeout_s=.03) as reader:
            with self.assertRaises(TelemetryTimeout):
                reader.request("robot.health")

    def test_disconnected_daemon_rejected(self):
        def serve(conn):
            recv_request(conn)
        with ReadOnlyUnixRpc(self.daemon(serve)) as reader:
            with self.assertRaises(TelemetryError):
                reader.request("robot.health")

    def test_oversize_frame_rejected(self):
        def serve(conn):
            recv_request(conn)
            conn.sendall(b"x" * 65540)
        with ReadOnlyUnixRpc(self.daemon(serve)) as reader:
            with self.assertRaises(TelemetryError):
                reader.request("robot.health")

    def test_bad_json_rejected(self):
        def serve(conn):
            recv_request(conn)
            conn.sendall(b'{"jsonrpc":"2.0","result":NaN}\n')
        with ReadOnlyUnixRpc(self.daemon(serve)) as reader:
            with self.assertRaises(TelemetryError):
                reader.request("robot.health")

    def test_wrong_stream_notification_rejected(self):
        def serve(conn):
            request = recv_request(conn)
            send(conn, response(request["id"], {"accepted": True}))
            send(conn, notification("tof.frame", {"seq": 1}))
        with ReadOnlyUnixRpc(self.daemon(serve)) as reader:
            reader.request("robot.subscribe", hz=5)
            with self.assertRaises(TelemetryError):
                reader.next_notification()

    def test_out_of_order_notification_during_subscription_preserved(self):
        def serve(conn):
            request = recv_request(conn)
            send(conn, notification("robot.state", {"hello": 1}))
            send(conn, response(request["id"], {"accepted": True}))
        with ReadOnlyUnixRpc(self.daemon(serve)) as reader:
            reader.request("robot.subscribe", hz=2)
            got = reader.next_notification()
        self.assertEqual("robot.state", got.method)
        self.assertEqual({"hello": 1}, got.params)

    def test_missing_socket_rejected(self):
        with self.assertRaises(TelemetryError):
            with ReadOnlyUnixRpc(str(Path(self.tmp.name) / "does_not_exist.sock")):
                pass

    def test_invalid_rate_rejected(self):
        with self.assertRaises(ValueError):
            ReadOnlyUnixRpc("/tmp/a").request("robot.subscribe", hz=50)

    def test_invalid_timeout_rejected(self):
        for timeout_s in (0, -1, float("nan"), 31):
            with self.subTest(timeout_s=timeout_s):
                with self.assertRaises(ValueError):
                    ReadOnlyUnixRpc("/tmp/a", timeout_s=timeout_s)


if __name__ == "__main__":
    unittest.main()
