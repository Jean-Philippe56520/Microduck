"""P15-B3: execute real Linux discretionary/ACL gate on temporary fake sockets.

Run in GitHub Actions under sudo (only fake numeric UIDs in a temp directory).
No real robot socket, motors, OEM binary, key, model, or SQLite is accessed.
The result is kernel DAC feasibility ONLY, not a deployed OEM permission.
"""
from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import tempfile
import unittest


# Fixed unused numeric fixture identities, NOT system accounts to create.
UID_TOFD = 31051
UID_MEDIAD = 31052
UID_KWIPI = 31053
UID_ROBOT_CLIENT = 31054
GID_ROBOT = 31061
GID_ISOLATED = 31062
GID_TOFD = 31063


def _probe_as(uid: int, groups: tuple[int, ...], path: Path,
              *, write_identity: bool = False) -> str:
    """One real fork/setgroups/setuid kernel access attempt; no RPC payload.

    The parent retains root; the child drops privileges irreversibly before
    connecting. Only the tiny result is sent back over a private pipe.
    """
    result_r, result_w = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(result_r)
        outcome = "unexpected"
        try:
            os.setgroups(list(groups))
            os.setgid(GID_ISOLATED)
            os.setuid(uid)
            if write_identity:
                with path.open("r+b") as f:
                    f.write(b"fixture overwrite")
            else:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
                    conn.settimeout(0.5)
                    conn.connect(str(path))
            outcome = "allowed"
        except OSError as exc:
            outcome = ("denied" if exc.errno in (errno.EACCES, errno.EPERM)
                       else f"other_errno_{exc.errno}")
        except BaseException:
            outcome = "unexpected_exception"
        try:
            os.write(result_w, outcome.encode("ascii", "replace"))
        finally:
            os.close(result_w)
            os._exit(0)
    os.close(result_w)
    try:
        raw = os.read(result_r, 128)
    finally:
        os.close(result_r)
    _, status = os.waitpid(pid, 0)
    if not os.WIFEXITED(status) or os.WEXITSTATUS(status) != 0:
        raise AssertionError("fixture credential probe child died")
    return raw.decode("ascii", "replace")


@unittest.skipUnless(
    os.name == "posix" and hasattr(os, "fork") and os.geteuid() == 0
    and hasattr(socket, "AF_UNIX"),
    "P15-B3 DAC/ACL kernel test requires Linux root; dedicated CI runs it",
)
class RealLinuxOemSocketDacFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not hasattr(socket, "SO_PEERCRED"):
            raise AssertionError("Linux kernel SO_PEERCRED is required")
        for command in ("setfacl", "getfacl"):
            if shutil.which(command) is None:
                raise AssertionError(f"{command} absent: STOP, no ACL claim")

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="p15b3-dac-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # TemporaryDirectory defaults to 0700; grant traverse to the *fixture*
        # clients. This changes only the temporary test directory, never /run.
        os.chmod(self.root, 0o755)
        self.listeners: dict[str, socket.socket] = {}
        self.paths: dict[str, Path] = {}
        for name, uid in (
            ("tof", UID_TOFD), ("robotd", 0), ("mediad", UID_MEDIAD),
        ):
            path = self.root / (name + ".sock")
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            server.bind(str(path))
            server.listen(64)
            os.chown(path, uid, GID_ROBOT)
            os.chmod(path, 0o660)
            self.listeners[name] = server
            self.paths[name] = path
        self.addCleanup(self._close_listeners)
        self.identity = self.root / "identity.json"
        self.identity.write_text(json.dumps({
            "service": "tofd", "pid": os.getpid(), "revision": "fixture-only",
        }))
        os.chown(self.identity, UID_TOFD, GID_TOFD)
        os.chmod(self.identity, 0o600)

    def _close_listeners(self) -> None:
        for listener in self.listeners.values():
            listener.close()

    def _connect(self, uid: int, name: str, *, robot_group: bool = False) -> str:
        groups = (GID_ROBOT,) if robot_group else ()
        return _probe_as(uid, groups, self.paths[name])

    def _set_acl(self) -> None:
        subprocess.run(
            ["setfacl", "-m", f"u:{UID_KWIPI}:rw", str(self.paths["tof"])],
            check=True, capture_output=True, text=True,
        )

    def test_01_oem_unix_socket_modes_and_owners_match_model(self) -> None:
        for name, owner in (
            ("tof", UID_TOFD), ("robotd", 0), ("mediad", UID_MEDIAD),
        ):
            with self.subTest(name=name):
                st = self.paths[name].stat()
                self.assertTrue(stat.S_ISSOCK(st.st_mode))
                self.assertEqual(0o660, stat.S_IMODE(st.st_mode))
                self.assertEqual(owner, st.st_uid)
                self.assertEqual(GID_ROBOT, st.st_gid)

    def test_02_isolated_companion_denied_all_oem_fixtures_by_default(self) -> None:
        for name in ("tof", "robotd", "mediad"):
            with self.subTest(socket=name):
                self.assertEqual("denied", self._connect(UID_KWIPI, name))

    def test_03_robot_group_exposes_every_oem_fixture_including_motors(self) -> None:
        # This is the threat baseline: membership is NOT a read-only privilege.
        for name in ("tof", "robotd", "mediad"):
            with self.subTest(socket=name):
                self.assertEqual(
                    "allowed",
                    self._connect(UID_ROBOT_CLIENT, name, robot_group=True),
                )
        self.assertEqual("denied", self._connect(UID_ROBOT_CLIENT, "robotd"))

    def test_04_tofd_owner_can_access_tof_without_robot_group(self) -> None:
        self.assertEqual("allowed", self._connect(UID_TOFD, "tof"))
        self.assertEqual("denied", self._connect(UID_TOFD, "robotd"))
        self.assertEqual("denied", self._connect(UID_TOFD, "mediad"))

    def test_05_tof_only_acl_allows_kwipi_without_robotd_permission(self) -> None:
        self._set_acl()
        acl = subprocess.run(
            ["getfacl", "-c", str(self.paths["tof"])],
            check=True, capture_output=True, text=True,
        ).stdout
        self.assertIn(f"user:{UID_KWIPI}:rw-", acl)
        self.assertEqual("allowed", self._connect(UID_KWIPI, "tof"))
        self.assertEqual("denied", self._connect(UID_KWIPI, "robotd"))
        self.assertEqual("denied", self._connect(UID_KWIPI, "mediad"))

    def test_06_acl_revocation_denies_tof_again(self) -> None:
        self._set_acl()
        self.assertEqual("allowed", self._connect(UID_KWIPI, "tof"))
        subprocess.run(
            ["setfacl", "-x", f"u:{UID_KWIPI}", str(self.paths["tof"])],
            check=True, capture_output=True, text=True,
        )
        self.assertEqual("denied", self._connect(UID_KWIPI, "tof"))

    def test_07_shared_tofd_uid_can_modify_tofd_owned_identity(self) -> None:
        self.assertEqual(
            "denied", _probe_as(
                UID_KWIPI, (), self.identity, write_identity=True,
            ),
        )
        # Using the daemon's UID would violate identity separation, despite
        # no access to robotd. This is a NEGATIVE design result.
        self.assertEqual(
            "allowed", _probe_as(
                UID_TOFD, (), self.identity, write_identity=True,
            ),
        )
        self.assertTrue(self.identity.read_bytes().startswith(b"fixture overwrite"))

    def test_08_acl_does_not_survive_unlink_and_rebind(self) -> None:
        self._set_acl()
        self.assertEqual("allowed", self._connect(UID_KWIPI, "tof"))
        old = self.paths["tof"]
        self.listeners["tof"].close()
        old.unlink()
        replacement = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        replacement.bind(str(old))
        replacement.listen(64)
        os.chown(old, UID_TOFD, GID_ROBOT)
        os.chmod(old, 0o660)
        self.listeners["tof"] = replacement
        self.assertEqual(
            "denied", self._connect(UID_KWIPI, "tof"),
            "socket ACL must be restored by the owning service on every bind",
        )
        self.assertEqual("denied", self._connect(UID_KWIPI, "robotd"))


if __name__ == "__main__":
    unittest.main()
