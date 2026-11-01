"""P15-B2: bounded local OEM ToF identity gate, Linux PC fake sockets only.

These tests NEVER reach /run/tofd, motor RPC, camera, Qwen, or the robot.
A fixture passing checks must remain labelled untrusted_local_fixture.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import stat
import tempfile
import threading
import time
import unittest
from unittest import mock

from microduck_companion import oem_tof_readonly
from microduck_companion.sim_ipc import ReadOnlyUnixRpc, TelemetryError
from microduck_companion.oem_tof_readonly import (
    OemTofSample, _read_tof_once, _peer_credentials,
    read_verified_local_tof_once,
)

PIN = "942e58e3aa6dbb28e7037203fff11866122c7567"


@contextmanager
def fake_tofd(
    path: Path, *, sensor: str | None = "VL53L8CX",
    ack_override: dict | None = None, frame_override: dict | None = None,
    time_offset_ns: int = 0, no_frame: bool = False,
):
    """A real local Unix server, never an OEM authentication fixture."""
    requests: list[dict] = []
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.settimeout(.35)
    listener.bind(str(path))
    os.chmod(path, 0o660)
    listener.listen(1)
    errors: list[BaseException] = []

    def serve() -> None:
        try:
            conn, _ = listener.accept()
        except (TimeoutError, OSError):
            return  # expected when an identity gate rejects before connecting
        try:
            with conn:
                conn.settimeout(.6)
                req = b""
                while b"\n" not in req:
                    data = conn.recv(1024)
                    if not data:
                        return
                    req += data
                requests.append(json.loads(req.split(b"\n", 1)[0]))
                ack = {
                    "accepted": True, "sensor": sensor,
                    "rows": 8, "cols": 8, "hz": 15,
                }
                if ack_override is not None:
                    ack.update(ack_override)
                conn.sendall((json.dumps({
                    "jsonrpc": "2.0", "id": 1, "result": ack,
                }) + "\n").encode())
                if no_frame:
                    time.sleep(.18)
                    return
                params = {
                    "seq": 1, "at_us": 12345,
                    "t_ns": time.monotonic_ns() + time_offset_ns,
                    "rows": 8, "cols": 8,
                    "distance_mm": [1200] * 64, "status": [5] * 64,
                }
                if frame_override is not None:
                    params.update(frame_override)
                conn.sendall((json.dumps({
                    "jsonrpc": "2.0", "method": "tof.frame", "params": params,
                }) + "\n").encode())
        except (BrokenPipeError, ConnectionResetError):
            pass
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        yield requests
    finally:
        listener.close()
        thread.join(timeout=2.)
        # Unix listener.close() does not unlink its pathname on Linux.
        # Every subTest must own a fresh fake socket inode.
        path.unlink(missing_ok=True)
        if thread.is_alive():
            raise AssertionError("fake ToF server did not stop")
        if errors:
            raise errors[0]


@unittest.skipUnless(os.name == "posix" and hasattr(socket, "SO_PEERCRED"),
                     "Linux SO_PEERCRED required")
class P15B2TofReadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.socket = self.root / "tof.sock"
        self.identity = self.root / "identity.json"
        self.uid = os.getuid()
        self.gid = os.getgid()
        self.pid = os.getpid()
        self.write_identity()

    def write_identity(self, **changes: object) -> None:
        payload = {
            "service": "tofd", "version": "0.17.8", "revision": PIN,
            "pid": self.pid,
            "exe": "/opt/robot/daemon/releases/0.17.8/bin/tofd",
        }
        payload.update(changes)
        self.identity.write_text(json.dumps(payload))
        os.chmod(self.identity, 0o600)

    def read(self, *, official: bool = False, uid: int | None = None,
             gid: int | None = None, timeout_s: float = .4,
             revision: str = PIN) -> OemTofSample:
        return _read_tof_once(
            self.socket, self.identity,
            uid=self.uid if uid is None else uid,
            gid=self.gid if gid is None else gid,
            revision=revision, timeout_s=timeout_s,
            official=official,
        )

    def assert_no_observation(self, value: OemTofSample) -> None:
        self.assertEqual("unavailable_or_unverified", value.status)
        self.assertIsNone(value.reading)
        self.assertIsNone(value.age_ms)
        self.assertFalse(value.local_peer_checked)
        self.assertFalse(value.physical_sensor_validated)
        self.assertFalse(value.robot_validated)
        self.assertEqual(0, value.motor_commands_issued)
        self.assertEqual(0, value.camera_frames_requested)
        self.assertEqual(0, value.sqlite_writes)

    def test_real_fake_socket_uses_only_tof_stream_once(self) -> None:
        with fake_tofd(self.socket) as requests:
            result = self.read()
        self.assertEqual("fixture_protocol_only", result.status)
        self.assertEqual("untrusted_local_fixture", result.provenance)
        self.assertFalse(result.local_peer_checked)
        self.assertFalse(result.physical_sensor_validated)
        self.assertFalse(result.robot_validated)
        self.assertEqual(1, result.reading.seq)
        self.assertEqual(64, len(result.reading.distance_mm))
        self.assertEqual((1200,) * 64, result.reading.distance_mm)
        self.assertEqual((5,) * 64, result.reading.status)
        self.assertGreaterEqual(result.age_ms, 0.)
        self.assertLess(result.age_ms, 1000.)
        self.assertEqual([{
            "jsonrpc": "2.0", "id": 1, "method": "tof.stream",
        }], requests)
        self.assertEqual(0, result.motor_commands_issued)
        self.assertEqual(0, result.camera_frames_requested)
        self.assertEqual(0, result.sqlite_writes)

    def test_server_process_identity_pid_is_from_kernel(self) -> None:
        with fake_tofd(self.socket):
            with ReadOnlyUnixRpc(self.socket, role="tofd") as rpc:
                pid, uid, gid = _peer_credentials(rpc)
                self.assertEqual((self.pid, self.uid, self.gid), (pid, uid, gid))
                self.assertTrue(rpc.request("tof.stream")["accepted"])

    def test_missing_socket_and_identity_never_produce_data(self) -> None:
        self.assert_no_observation(self.read())
        self.identity.unlink()
        with fake_tofd(self.socket):
            self.assert_no_observation(self.read())

    def test_wrong_revision_or_identity_pid_is_refused(self) -> None:
        for update in ({"revision": "unknown"}, {"revision": None},
                       {"pid": self.pid + 1}, {"pid": True},
                       {"service": "robotd"}):
            with self.subTest(update=update):
                self.write_identity(**update)
                with fake_tofd(self.socket):
                    self.assert_no_observation(self.read())
        self.write_identity()

    def test_wrong_identity_file_type_or_permission_is_refused(self) -> None:
        self.identity.unlink()
        self.identity.symlink_to(self.root / "target.json")
        with fake_tofd(self.socket):
            self.assert_no_observation(self.read())
        self.identity.unlink()
        self.write_identity()
        os.chmod(self.identity, 0o666)
        with fake_tofd(self.socket):
            self.assert_no_observation(self.read())

    def test_duplicate_or_excessive_identity_json_is_refused(self) -> None:
        for value in (
            '{"service":"tofd","service":"tofd","version":"0.17.8","revision":"' + PIN + '","pid":1}',
            '{"service":"tofd","version":NaN,"revision":"' + PIN + '","pid":1}',
            "x" * 2049,
        ):
            with self.subTest(value=value[:15]):
                self.identity.write_text(value)
                os.chmod(self.identity, 0o600)
                with fake_tofd(self.socket):
                    self.assert_no_observation(self.read())

    def test_group_uid_and_socket_mode_are_enforced(self) -> None:
        with fake_tofd(self.socket):
            self.assert_no_observation(self.read(uid=self.uid + 1))
            self.assert_no_observation(self.read(gid=self.gid + 1))
            os.chmod(self.socket, 0o666)
            self.assert_no_observation(self.read())

    def test_unsafe_runtime_directory_or_socket_symlink_rejected(self) -> None:
        with fake_tofd(self.socket):
            os.chmod(self.root, 0o777)
            self.assert_no_observation(self.read())
            os.chmod(self.root, 0o700)
        link = self.root / "link"
        link.symlink_to(self.root, target_is_directory=True)
        result = _read_tof_once(
            link / "tof.sock", link / "identity.json",
            uid=self.uid, gid=self.gid, revision=PIN,
            timeout_s=.4, official=False,
        )
        self.assert_no_observation(result)

    def test_no_sensor_simulated_or_unavailable_cannot_be_claimed_real(self) -> None:
        for sensor in (None, "fake", "sim", "unknown"):
            with self.subTest(sensor=sensor):
                with fake_tofd(self.socket, sensor=sensor):
                    self.assert_no_observation(self.read())
        with fake_tofd(self.socket, ack_override={
            "sensor": "VL53L8CX", "unavailable": "sensor not fitted",
        }):
            self.assert_no_observation(self.read())

    def test_rejects_invalid_stream_geometry_and_rate(self) -> None:
        for field in ({"rows": 7}, {"cols": 9}, {"hz": 0},
                      {"hz": 25}, {"rows": True}, {"hz": 15.0},
                      {"accepted": False}):
            with self.subTest(field=field):
                with fake_tofd(self.socket, ack_override=field):
                    self.assert_no_observation(self.read())

    def test_rejects_stale_future_zero_or_duplicate_sequence(self) -> None:
        for shift in (-2_000_000_000, 2_000_000_000):
            with self.subTest(shift=shift):
                with fake_tofd(self.socket, time_offset_ns=shift):
                    self.assert_no_observation(self.read())
        for invalid in ({"seq": 0}, {"seq": -1}, {"t_ns": 0},
                        {"t_ns": None}, {"distance_mm": [4] * 63},
                        {"status": [5] * 63}):
            with self.subTest(invalid=str(invalid)[:30]):
                with fake_tofd(self.socket, frame_override=invalid):
                    self.assert_no_observation(self.read())

    def test_bounded_timeout_and_refused_malformed_notification(self) -> None:
        with fake_tofd(self.socket, no_frame=True):
            self.assert_no_observation(self.read(timeout_s=.1))
        with fake_tofd(self.socket, frame_override={
            "status": [True] * 64,
        }):
            self.assert_no_observation(self.read())
        for timeout in (0, -1, float("nan"), 2., True):
            with self.subTest(timeout=timeout):
                self.assert_no_observation(self.read(timeout_s=timeout))

    def test_test_fixture_can_never_be_promoted_to_authenticated_oem(self) -> None:
        with fake_tofd(self.socket):
            result = self.read(official=True)
        self.assertEqual("fixture_protocol_only", result.status)
        self.assertFalse(result.local_peer_checked)
        self.assertEqual("untrusted_local_fixture", result.provenance)

    def test_public_entrypoint_is_fixed_oem_socket_no_custom_path(self) -> None:
        with self.assertRaises(TypeError):
            read_verified_local_tof_once(path=self.socket)
        with self.assertRaises(ValueError):
            read_verified_local_tof_once(timeout_s=3)
        with mock.patch("pwd.getpwnam") as uid, mock.patch(
            "grp.getgrnam"
        ) as gid, mock.patch.object(
            oem_tof_readonly, "_read_tof_once",
            return_value=OemTofSample("unavailable_or_unverified", "untrusted"),
        ) as read:
            uid.return_value.pw_uid = 108
            gid.return_value.gr_gid = 999
            out = read_verified_local_tof_once(timeout_s=.4)
        self.assertIsNone(out.reading)
        read.assert_called_once_with(
            Path("/run/tofd/tof.sock"),
            Path("/run/tofd/identity.json"),
            uid=108, gid=999, revision=PIN, timeout_s=.4, official=True,
        )

    def test_read_only_role_rejects_motor_and_camera_before_any_send(self) -> None:
        reader = ReadOnlyUnixRpc(str(self.socket), role="tofd")
        with self.assertRaises(TelemetryError):
            _peer_credentials(reader)
        for method in ("robot.do", "robot.move", "robot.stop",
                       "media.frame", "robot.health"):
            with self.subTest(method=method), self.assertRaises(ValueError):
                reader.request(method)
        self.assertFalse((self.root / "memory.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
