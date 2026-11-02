"""P15-B15: real Linux UID separation with exact P15-B8 ACL on fake sockets.

Run as root ONLY in a disposable test environment. Both forked principals
irreversibly drop all groups and privilege. No actual /run, daemon, cameras,
network, hardware, robot RPC, accounts, or database are touched.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import socket
import stat
import tempfile
import time
import unittest

from microduck_companion.b12_local_wire_contract import B12LocalSequenceGate
from microduck_companion.b14_host_identity_gate import B12_REVISION
from microduck_companion.b15_cross_uid_host_gate import (
    B15HostRefused, _expected_acl, read_b15_cross_uid_host_fixture,
)

UID_MEDIAD = 31052
GID_MEDIAD = 31064
UID_KWIPI = 31053
GID_KWIPI = 31062
GID_ROBOT = 31061


def _drop(uid: int, gid: int) -> None:
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)


def _packet(seq=1, *, age_ns=100_000_000) -> bytes:
    obj = {"jsonrpc":"2.0", "method":"media.detections", "params":{
        "width":720, "height":1280, "took_ms":20.0,
        "boxes":[{"x0":10,"y0":20,"x1":110,"y1":220,"score":1.38}],
        "look_seq":seq,
        "captured_at_monotonic_ns":time.monotonic_ns()-age_ns,
        "captured_at_unix_us":int(time.time()*1_000_000),
    }}
    return (json.dumps(obj,separators=(",",":"))+"\n").encode()


def _publish_identity(runtime: Path, pid: int, revision=B12_REVISION):
    identity = {"service":"mediad", "version":"0.17.8", "revision":revision,
                "pid":pid,"built_at":None,
                "exe":"/opt/robot/daemon/current/bin/mediad"}
    p=runtime/"identity.json"
    p.write_text(json.dumps(identity,separators=(",",":"))+"\n")
    p.chmod(0o644)


@unittest.skipUnless(
    os.name=="posix" and os.geteuid()==0 and hasattr(socket,"SO_PEERCRED")
    and hasattr(os,"fork") and hasattr(os,"setxattr"),
    "Linux root fixture ACL and two dropped UIDs required; dedicated CI runs",
)
class B15CrossUidHostTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="kwipi-b15-",dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.root.chmod(0o755)
        self.runtime=self.root/"mediad"
        self.runtime.mkdir(mode=0o755)
        os.chown(self.runtime,UID_MEDIAD,GID_MEDIAD)
        self.runtime.chmod(0o755)
        self.private=self.runtime/"kwipi"
        self.private.mkdir(mode=0o700)
        os.chown(self.private,UID_MEDIAD,GID_MEDIAD)
        self.private.chmod(0o700)
        self.sock=self.private/"detections.sock"
        self.daemon_pid=None
        self.root_listeners=[]
        self.addCleanup(self._stop_daemon)

    def _stop_daemon(self):
        for sock in self.root_listeners:
            sock.close()
        if self.daemon_pid is not None:
            try:
                os.kill(self.daemon_pid,signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(self.daemon_pid,0)
            except ChildProcessError:
                pass
            self.daemon_pid=None
        # TemporaryDirectory cleanup follows, after the daemon has exited.

    def _launch_daemon(self, *, n=1, grant_dir=True, grant_sock=True,
                       seqs=None, ages=None):
        self.assertIsNone(self.daemon_pid)
        rd,wr=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(rd)
            try:
                _drop(UID_MEDIAD,GID_MEDIAD)
                listener=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                listener.bind(str(self.sock))
                self.sock.chmod(0o600)
                listener.listen(4)
                listener.settimeout(.15)
                _publish_identity(self.runtime,os.getpid())
                if grant_sock:
                    os.setxattr(self.sock,"system.posix_acl_access",
                                _expected_acl(UID_KWIPI,directory=False))
                if grant_dir:
                    os.setxattr(self.private,"system.posix_acl_access",
                                _expected_acl(UID_KWIPI,directory=True))
                os.write(wr,b"R")
                until=time.monotonic()+2.3
                index=0
                while time.monotonic()<until and index<n:
                    try:
                        conn,_=listener.accept()
                    except socket.timeout:
                        continue
                    with conn:
                        age=100_000_000 if ages is None else ages[index]
                        seq=index+1 if seqs is None else seqs[index]
                        try:
                            conn.sendall(_packet(seq=seq,age_ns=age))
                        except OSError:
                            pass
                    index+=1
                listener.close()
            except BaseException as exc:
                try:
                    os.write(wr,("E"+str(exc)[:240]).encode())
                except OSError:
                    pass
            finally:
                os.close(wr)
                os._exit(0)
        os.close(wr)
        try:
            ready=os.read(rd,255)
        finally:
            os.close(rd)
        self.daemon_pid=pid
        self.assertEqual(b"R",ready,"mediad fixture failed: "+repr(ready))
        self.assertEqual(UID_MEDIAD,self.sock.stat().st_uid)
        self.assertEqual(UID_MEDIAD,(self.runtime/"identity.json").stat().st_uid)

    def _client(self, *, n=1) -> list[dict]:
        rd,wr=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(rd)
            answers=[]
            try:
                _drop(UID_KWIPI,GID_KWIPI)
                gate=B12LocalSequenceGate()
                for _ in range(n):
                    try:
                        x=read_b15_cross_uid_host_fixture(
                            self.root,mediad_uid=UID_MEDIAD,
                            mediad_gid=GID_MEDIAD,kwipi_uid=UID_KWIPI,
                            robot_gid=GID_ROBOT,sequence_gate=gate,
                            timeout_s=.5)
                        answers.append({"ok":True,"status":x.status,
                            "pid":x.peer_pid,"uid":x.peer_uid,
                            "seq":x.look_seq,"category":x.category,
                            "sensor":x.verified_sensor,"media":x.media_bytes_stored,
                            "memory":x.memory_writes,"motors":x.motor_commands_issued})
                    except B15HostRefused:
                        answers.append({"ok":False})
                answers.append({"groups":os.getgroups(),"uid":os.geteuid()})
            except BaseException as exc:
                answers=[{"error":repr(exc)}]
            os.write(wr,json.dumps(answers).encode())
            os.close(wr)
            os._exit(0)
        os.close(wr)
        try:
            result=os.read(rd,4096)
        finally:
            os.close(rd)
        _,status=os.waitpid(pid,0)
        self.assertTrue(os.WIFEXITED(status))
        self.assertEqual(0,os.WEXITSTATUS(status))
        parsed=json.loads(result)
        self.assertNotIn("error",parsed[0],parsed)
        self.assertEqual([],parsed[-1]["groups"])
        self.assertEqual(UID_KWIPI,parsed[-1]["uid"])
        return parsed[:-1]

    def _fake_protected(self):
        paths=[]
        for name,owner in (("media.sock",UID_MEDIAD),("robotd.sock",0)):
            target=self.runtime/name if name=="media.sock" else self.root/name
            server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            server.bind(str(target))
            server.listen(3)
            os.chown(target,owner,GID_ROBOT)
            target.chmod(0o660)
            self.root_listeners.append(server)
            paths.append(target)
        return paths

    def test_one_cross_uid_peer_identity_and_b12_is_passive(self):
        self._launch_daemon()
        values=self._client()
        self.assertEqual(1,len(values))
        self.assertTrue(values[0]["ok"],values)
        self.assertEqual(UID_MEDIAD,values[0]["uid"])
        self.assertEqual(self.daemon_pid,values[0]["pid"])
        self.assertEqual("host_two_uid_claim_consistent_not_sensor",values[0]["status"])
        self.assertEqual("unknown",values[0]["category"])
        self.assertFalse(values[0]["sensor"])
        self.assertEqual((0,0,0),(values[0]["media"],values[0]["memory"],values[0]["motors"]))

    def test_both_approved_acl_entries_required(self):
        for which in ("no_directory","no_socket"):
            with self.subTest(which=which):
                if self.daemon_pid is not None:
                    self._stop_daemon()
                    self.sock.unlink(missing_ok=True)
                    (self.runtime/"identity.json").unlink(missing_ok=True)
                    try:os.removexattr(self.private,"system.posix_acl_access")
                    except OSError:pass
                    self.private.chmod(0o700)
                self._launch_daemon(grant_dir=which!="no_directory",
                                    grant_sock=which!="no_socket")
                self.assertEqual([{"ok":False}],self._client())

    def test_identity_must_be_readable_as_separate_kwipi(self):
        self._launch_daemon()
        (self.runtime/"identity.json").chmod(0o600)
        self.assertEqual([{"ok":False}],self._client())

    def test_wrong_revision_and_pid_claims_refused(self):
        self._launch_daemon(n=2)
        _publish_identity(self.runtime,self.daemon_pid,revision="942e58e3")
        self.assertEqual([{"ok":False}],self._client())
        _publish_identity(self.runtime,self.daemon_pid+1)
        # The server remains able to accept if denied before connecting; its
        # listening socket is unchanged, but the client refuses self-claim.
        self.assertEqual([{"ok":False}],self._client())

    def test_unexpected_acl_or_excessive_permissions_refused(self):
        self._launch_daemon(n=2)
        self.private.chmod(0o711)  # Opens traversal more widely: reject.
        self.assertEqual([{"ok":False}],self._client())
        self.private.chmod(0o710)
        # An ACL for the wrong named observer is refused, even if its mode
        # bits still look identical to the approved 0660 socket.
        os.setxattr(self.sock,"system.posix_acl_access",
                    _expected_acl(UID_KWIPI+1,directory=False))
        self.assertEqual([{"ok":False}],self._client())

    def test_rebound_socket_without_named_acl_is_denied(self):
        self._launch_daemon()
        os.removexattr(self.sock,"system.posix_acl_access")
        self.sock.chmod(0o600)
        self.assertEqual([{"ok":False}],self._client())

    def test_dedicated_kwipi_cannot_open_motor_or_raw_frame_sockets(self):
        self._launch_daemon()
        fake=self._fake_protected()
        rd,wr=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(rd)
            _drop(UID_KWIPI,GID_KWIPI)
            denied=[]
            for p in fake:
                try:
                    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
                        conn.settimeout(.15)
                        conn.connect(str(p))
                    denied.append(False)
                except PermissionError:
                    denied.append(True)
                except OSError:
                    denied.append(False)
            os.write(wr,json.dumps(denied).encode())
            os._exit(0)
        os.close(wr)
        try:raw=os.read(rd,200)
        finally:os.close(rd)
        os.waitpid(pid,0)
        self.assertEqual([True,True],json.loads(raw))
        self.assertTrue(self._client()[0]["ok"])

    def test_stale_detection_and_false_timestamp_do_not_promote(self):
        self._launch_daemon(n=2,ages=[3_000_000_000,-3_000_000_000])
        self.assertEqual([{"ok":False},{"ok":False}],self._client(n=2))

    def test_duplicate_sequence_refused_on_second_read(self):
        self._launch_daemon(n=2,seqs=[9,9])
        response=self._client(n=2)
        self.assertTrue(response[0]["ok"],response)
        self.assertFalse(response[1]["ok"],response)


if __name__=="__main__":unittest.main()
