"""P15-B14 Linux host-only Unix peer + OEM identity-file preflight."""
from __future__ import annotations

from contextlib import contextmanager
import json
import multiprocessing
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest

from microduck_companion.b12_local_wire_contract import B12LocalSequenceGate
from microduck_companion.b14_host_identity_gate import (
    B12_REVISION, B14IdentityRefused, read_b14_identity_host_fixture,
)

LINUX_USER = (hasattr(socket, "SO_PEERCRED") and os.name == "posix"
              and os.geteuid() != 0)


def identity(*, pid=None, revision=B12_REVISION, extra=None) -> bytes:
    data = {
        "service": "mediad", "version": "0.17.8", "revision": revision,
        "built_at": None, "exe": "/opt/robot/daemon/current/bin/mediad",
        "pid": os.getpid() if pid is None else pid,
    }
    if extra:
        data.update(extra)
    return (json.dumps(data, separators=(",", ":")) + "\n").encode()


def packet(*, seq=1, age_ns=100_000_000) -> bytes:
    data = {"jsonrpc": "2.0", "method": "media.detections", "params": {
        "width": 720, "height": 1280, "took_ms": 20.,
        "boxes": [{"x0": 10., "y0": 20., "x1": 110., "y1": 220.,
                   "score": 1.38}],
        "captured_at_monotonic_ns": time.monotonic_ns() - age_ns,
        "captured_at_unix_us": int(time.time() * 1_000_000),
        "look_seq": seq,
    }}
    return (json.dumps(data, separators=(",", ":")) + "\n").encode()


@contextmanager
def serve_one(path: Path, message: bytes, *, before_send=None):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(path))
    path.chmod(0o600)
    sock.listen(1)
    sock.settimeout(.1)
    stop = threading.Event()
    calls = []
    def worker():
        while not stop.is_set():
            try:
                conn, _ = sock.accept()
                break
            except socket.timeout:
                continue
            except OSError:
                return
        else:
            return
        try:
            with conn:
                if before_send:
                    before_send()
                conn.sendall(message)
                conn.settimeout(.3)
                try:
                    calls.append(conn.recv(10))
                except OSError:
                    calls.append(b"")
        except OSError:
            pass
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        yield calls
    finally:
        stop.set()
        sock.close()
        thread.join(timeout=2)
        path.unlink(missing_ok=True)
        if thread.is_alive():
            raise RuntimeError("fixture server thread remained alive")


def child_server(path: str, ready):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(path)
    os.chmod(path, 0o600)
    sock.listen(1)
    sock.settimeout(.1)
    ready.set()
    deadline = time.monotonic() + 3
    try:
        while time.monotonic() < deadline:
            try:
                conn, _ = sock.accept()
                with conn:
                    try:
                        conn.sendall(packet())
                    except BrokenPipeError:
                        # Expected: the identity mismatch closes before read.
                        pass
                return
            except socket.timeout:
                continue
    finally:
        sock.close()
        Path(path).unlink(missing_ok=True)


@unittest.skipUnless(LINUX_USER, "Linux unprivileged UID with SO_PEERCRED required")
class B14IdentityHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="kwipi-b14-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.gate = B12LocalSequenceGate()
        self.uid = os.geteuid()
        self._write(identity())

    def _write(self, content):
        p = self.root / "identity.json"
        p.write_bytes(content)
        p.chmod(0o644)

    def read(self, **kw):
        return read_b14_identity_host_fixture(
            self.root, expected_uid=kw.pop("uid", self.uid),
            sequence_gate=self.gate, **kw)

    def test_one_real_unix_socket_plus_oem_identity_without_rpc(self):
        with serve_one(self.root / "detections.sock", packet()) as received:
            result = self.read()
        self.assertEqual("host_fixture_identity_claim_consistent_not_sensor",
                         result.status)
        self.assertEqual(os.getpid(), result.peer_pid)
        self.assertEqual(self.uid, result.peer_uid)
        self.assertEqual(B12_REVISION, result.identity_revision)
        self.assertEqual(1, result.reported_boxes)
        self.assertEqual("unknown", result.category)
        self.assertFalse(result.verified_sensor)
        self.assertEqual(0, result.media_bytes_stored)
        self.assertEqual(0, result.memory_writes)
        self.assertEqual(0, result.motor_commands_issued)
        self.assertEqual([b""], received)
        self.assertFalse((self.root / "media.sock").exists())

    def test_duplicate_look_and_later_new_sequence(self):
        for seq, accepted in ((5, True), (5, False), (6, True)):
            with serve_one(self.root / "detections.sock", packet(seq=seq)):
                if accepted:
                    self.assertEqual(seq, self.read().look_seq)
                else:
                    with self.assertRaises(B14IdentityRefused):
                        self.read()

    def test_bad_file_identity_revision_service_pid_bool_and_extra(self):
        malformed = (
            identity(revision="942e58e3aa6dbb28e7037203fff11866122c7567"),
            identity(pid=os.getpid() + 101),
            identity(extra={"service": "robotd"}),
            identity(extra={"pid": True}),
            identity(extra={"motor_authorized": True}),
            b'{"service":"mediad","service":"mediad","version":"0.1","revision":"x","pid":1}\n',
        )
        for bad in malformed:
            self._write(bad)
            with serve_one(self.root / "detections.sock", packet()):
                with self.assertRaises(B14IdentityRefused):
                    self.read()
        self._write(identity())

    def test_wrong_file_modes_symlink_and_oversize_rejected(self):
        self._write(identity())
        doc = self.root / "identity.json"
        doc.chmod(0o666)
        with serve_one(self.root / "detections.sock", packet()):
            with self.assertRaises(B14IdentityRefused):
                self.read()
        doc.unlink()
        payload = self.root / "literal.json"
        payload.write_bytes(identity())
        doc.symlink_to(payload)
        with serve_one(self.root / "detections.sock", packet()):
            with self.assertRaises(B14IdentityRefused):
                self.read()
        doc.unlink()
        self._write(b"x" * 2100)
        with serve_one(self.root / "detections.sock", packet()):
            with self.assertRaises(B14IdentityRefused):
                self.read()

    def test_missing_identity_and_socket_rejected(self):
        with self.assertRaises(B14IdentityRefused):
            self.read()
        (self.root / "identity.json").unlink()
        with serve_one(self.root / "detections.sock", packet()):
            with self.assertRaises(B14IdentityRefused):
                self.read()

    def test_world_writable_socket_and_fixture_root_rejected(self):
        with serve_one(self.root / "detections.sock", packet()):
            (self.root / "detections.sock").chmod(0o666)
            with self.assertRaises(B14IdentityRefused):
                self.read()
        self.root.chmod(0o777)
        with self.assertRaises(B14IdentityRefused):
            self.read()
        self.root.chmod(0o700)

    def test_stale_and_future_capture_refused(self):
        for age in (3_000_000_000, -3_000_000_000):
            with serve_one(self.root / "detections.sock", packet(age_ns=age)):
                with self.assertRaises(B14IdentityRefused):
                    self.read()

    def test_real_oem_and_symlink_roots_never_consulted(self):
        for p in ("/run/mediad", "/run/mediad/kwipi", "/var/run/mediad"):
            with self.assertRaises(B14IdentityRefused):
                read_b14_identity_host_fixture(
                    p, expected_uid=self.uid, sequence_gate=self.gate)
        alias = self.root.parent / (self.root.name + "-alias")
        alias.symlink_to(self.root)
        self.addCleanup(lambda: alias.unlink(missing_ok=True))
        with self.assertRaises(B14IdentityRefused):
            read_b14_identity_host_fixture(
                alias, expected_uid=self.uid, sequence_gate=self.gate)

    def test_wrong_uid_timeout_and_missing_gate_refused(self):
        for uid in (0, self.uid + 1, True):
            with self.assertRaises(B14IdentityRefused):
                self.read(uid=uid)
        for timeout in (0, True, float("nan"), 3):
            with self.assertRaises(B14IdentityRefused):
                self.read(timeout_s=timeout)
        with self.assertRaises(B14IdentityRefused):
            read_b14_identity_host_fixture(
                self.root, expected_uid=self.uid, sequence_gate=None)

    def test_pid_peer_credentials_from_second_real_process_refused(self):
        if "spawn" not in multiprocessing.get_all_start_methods():
            self.skipTest("spawn unavailable")
        ctx = multiprocessing.get_context("spawn")
        ready = ctx.Event()
        child = ctx.Process(target=child_server, args=(str(self.root / "detections.sock"), ready))
        child.start()
        try:
            self.assertTrue(ready.wait(timeout=2))
            with self.assertRaises(B14IdentityRefused):
                self.read()  # identity file claims parent PID, kernel peer is child PID
        finally:
            child.join(timeout=2)
            if child.is_alive():
                child.terminate()
                child.join(timeout=2)

    def test_identity_mutation_while_socket_open_refused(self):
        # Metadata changed by the host's owner after the initial read but before
        # delivery cannot be treated as stable provenance.
        def mutate():
            time.sleep(.03)
            self._write(identity(extra={"version": "0.17.9"}))
        with serve_one(self.root / "detections.sock", packet(), before_send=mutate):
            with self.assertRaises(B14IdentityRefused):
                self.read()


if __name__ == "__main__":
    unittest.main()
