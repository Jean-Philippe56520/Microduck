"""P15-B7: real Linux POSIX ACL on FAKE mediad metadata socket only.

Reuses the P15-B3 fork/setuid probe. All paths are in a temporary test
directory: no actual /run, OEM service, robot, camera, or motor RPC. No
permissions are ever changed outside the disposable fixture.
"""
from __future__ import annotations

import errno
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import tempfile
import unittest

import test_per_p15b3_oem_unix_dac as b3


GID_MEDIAD = 31064


def _list_as_kwipi(path: Path) -> str:
    """Prove a traversal-only ACL cannot enumerate a private directory."""
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        status = "unexpected"
        try:
            os.setgroups([])
            os.setgid(b3.GID_ISOLATED)
            os.setuid(b3.UID_KWIPI)
            os.listdir(path)
            status = "allowed"
        except OSError as exc:
            status = ("denied" if exc.errno in (errno.EACCES, errno.EPERM)
                      else "unexpected_errno_" + str(exc.errno))
        try:
            os.write(write_fd, status.encode("ascii"))
        finally:
            os.close(write_fd)
            os._exit(0)
    os.close(write_fd)
    try:
        answer = os.read(read_fd, 128)
    finally:
        os.close(read_fd)
    _, state = os.waitpid(pid, 0)
    if not os.WIFEXITED(state) or os.WEXITSTATUS(state):
        raise AssertionError("forked directory probe did not exit cleanly")
    return answer.decode("ascii")


@unittest.skipUnless(
    os.name == "posix" and hasattr(os, "fork")
    and os.geteuid() == 0 and hasattr(socket, "SO_PEERCRED"),
    "P15-B7 kernel DAC needs Linux root; GitHub dedicated CI runs it",
)
class MediadPrivateMetadataDacFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        for cmd in ("setfacl", "getfacl"):
            if shutil.which(cmd) is None:
                raise AssertionError(cmd + " unavailable; STOP (no ACL claim)")

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="p15b7-fake-mediad-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        os.chmod(self.root, 0o755)
        self.runtime = self.root / "mediad"
        self.runtime.mkdir(mode=0o755)
        os.chown(self.runtime, b3.UID_MEDIAD, GID_MEDIAD)
        os.chmod(self.runtime, 0o755)
        self.private = self.runtime / "kwipi"
        self.private.mkdir(mode=0o700)
        os.chown(self.private, b3.UID_MEDIAD, GID_MEDIAD)
        os.chmod(self.private, 0o700)
        self.metadata = self.private / "detections.sock"
        self.frame = self.runtime / "media.sock"
        self.motor = self.root / "robotd.sock"
        self.listeners: dict[str, socket.socket] = {}
        for name, path, owner, group, mode in (
            ("metadata", self.metadata, b3.UID_MEDIAD, GID_MEDIAD, 0o600),
            ("frame", self.frame, b3.UID_MEDIAD, b3.GID_ROBOT, 0o660),
            ("motor", self.motor, 0, b3.GID_ROBOT, 0o660),
        ):
            listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            listener.bind(str(path))
            listener.listen(64)
            os.chown(path, owner, group)
            os.chmod(path, mode)
            self.listeners[name] = listener
        self.addCleanup(self._close_listeners)
        self.identity = self.private / "identity.json"
        self.identity.write_text('{"service":"mediad","revision":"fixture"}\n')
        os.chown(self.identity, b3.UID_MEDIAD, GID_MEDIAD)
        os.chmod(self.identity, 0o600)

    def _close_listeners(self) -> None:
        for listener in self.listeners.values():
            listener.close()

    def _connect(self, path: Path) -> str:
        return b3._probe_as(b3.UID_KWIPI, (), path)

    def _setfacl(self, path: Path, spec: str, *, remove: bool = False) -> None:
        command = ["setfacl", "-x" if remove else "-m", spec, str(path)]
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=10)

    def _grant_dir(self) -> None:
        self._setfacl(self.private, f"u:{b3.UID_KWIPI}:--x")

    def _grant_socket(self) -> None:
        self._setfacl(self.metadata, f"u:{b3.UID_KWIPI}:rw-")

    def _grant_both(self) -> None:
        self._grant_dir()
        self._grant_socket()

    def _getfacl(self, path: Path) -> str:
        return subprocess.run(
            ["getfacl", "-c", str(path)], check=True,
            capture_output=True, text=True, timeout=10,
        ).stdout

    def test_01_actual_modes_and_fictive_ownership(self) -> None:
        self.assertEqual(0o700, stat.S_IMODE(self.private.stat().st_mode))
        self.assertEqual(b3.UID_MEDIAD, self.private.stat().st_uid)
        for path, uid, gid, mode in (
            (self.metadata, b3.UID_MEDIAD, GID_MEDIAD, 0o600),
            (self.frame, b3.UID_MEDIAD, b3.GID_ROBOT, 0o660),
            (self.motor, 0, b3.GID_ROBOT, 0o660),
        ):
            with self.subTest(path=path.name):
                info = path.stat()
                self.assertTrue(stat.S_ISSOCK(info.st_mode))
                self.assertEqual((uid, gid, mode), (
                    info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode),
                ))

    def test_02_kwipi_without_acl_cannot_open_any_socket(self) -> None:
        for path in (self.metadata, self.frame, self.motor):
            with self.subTest(path=path.name):
                self.assertEqual("denied", self._connect(path))
        self.assertEqual("denied", _list_as_kwipi(self.private))

    def test_03_socket_acl_alone_cannot_traverse_private_directory(self) -> None:
        self._grant_socket()
        self.assertEqual("denied", self._connect(self.metadata))
        self.assertEqual("denied", self._connect(self.frame))
        self.assertEqual("denied", self._connect(self.motor))

    def test_04_directory_traverse_acl_alone_cannot_open_socket(self) -> None:
        self._grant_dir()
        self.assertEqual("denied", self._connect(self.metadata))
        self.assertEqual("denied", self._connect(self.frame))
        self.assertEqual("denied", self._connect(self.motor))

    def test_05_two_named_acls_allow_only_metadata_without_group_robot(self) -> None:
        self._grant_both()
        self.assertIn(f"user:{b3.UID_KWIPI}:--x", self._getfacl(self.private))
        self.assertIn(f"user:{b3.UID_KWIPI}:rw-", self._getfacl(self.metadata))
        # An ACL mask may change stat's mode "group" bits, but named
        # group::--- / other::--- remain closed to all unnamed peers.
        self.assertIn("group::---", self._getfacl(self.private))
        self.assertIn("group::---", self._getfacl(self.metadata))
        self.assertIn("other::---", self._getfacl(self.private))
        self.assertIn("other::---", self._getfacl(self.metadata))
        self.assertEqual("allowed", self._connect(self.metadata))
        self.assertEqual("denied", self._connect(self.frame))
        self.assertEqual("denied", self._connect(self.motor))
        self.assertEqual("denied", _list_as_kwipi(self.private))
        self.assertEqual(
            "denied", b3._probe_as(
                b3.UID_KWIPI, (), self.identity, write_identity=True,
            ),
        )

    def test_06_revocation_of_either_acl_denies_access(self) -> None:
        self._grant_both()
        self.assertEqual("allowed", self._connect(self.metadata))
        self._setfacl(self.metadata, f"u:{b3.UID_KWIPI}", remove=True)
        self.assertEqual("denied", self._connect(self.metadata))
        self._grant_socket()
        self.assertEqual("allowed", self._connect(self.metadata))
        self._setfacl(self.private, f"u:{b3.UID_KWIPI}", remove=True)
        self.assertEqual("denied", self._connect(self.metadata))
        self.assertEqual("denied", self._connect(self.motor))

    def test_07_unlink_rebind_invalidates_old_socket_acl(self) -> None:
        self._grant_both()
        self.assertEqual("allowed", self._connect(self.metadata))
        old_inode = self.metadata.stat().st_ino
        self.listeners["metadata"].close()
        self.metadata.unlink()
        replacement = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        replacement.bind(str(self.metadata))
        replacement.listen(64)
        os.chown(self.metadata, b3.UID_MEDIAD, GID_MEDIAD)
        os.chmod(self.metadata, 0o600)
        self.listeners["metadata"] = replacement
        self.assertNotEqual(old_inode, self.metadata.stat().st_ino)
        self.assertEqual("denied", self._connect(self.metadata))
        self.assertEqual("denied", self._connect(self.motor))
        # Regranting on the newly bound inode is a separate OEM responsibility.
        self._grant_socket()
        self.assertEqual("allowed", self._connect(self.metadata))
        self.assertEqual("denied", self._connect(self.motor))

    def test_08_posix_acl_mask_conflicts_with_exact_0700_oem_binder(self) -> None:
        # P15-B4's *unmodified* Rust safe_dir() requires exactly 0700.
        oem_candidate = (
            Path(__file__).resolve().parents[1] /
            "scripts/per_p15b4_local_detections.rs"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "private && (info.permissions().mode() & 0o777) != 0o700",
            oem_candidate,
        )
        self.assertEqual(0o700, stat.S_IMODE(self.private.stat().st_mode))
        self._grant_dir()
        after = stat.S_IMODE(self.private.stat().st_mode)
        self.assertNotEqual(
            0o700, after,
            "POSIX ACL mask must be assessed against OEM exact-mode check",
        )
        self.assertIn(f"user:{b3.UID_KWIPI}:--x", self._getfacl(self.private))
        # This is a NEGATIVE integration outcome: a restarted mediad using
        # the current source guard rejects an ACL-bearing private directory.
        self.assertEqual("denied", self._connect(self.metadata))


if __name__ == "__main__":
    unittest.main()
