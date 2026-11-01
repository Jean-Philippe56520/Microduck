"""P15-B9-R independent rootfs contents: synthetic, no BitBake or robot."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.per_p15b6_cached_package_runner import Refused
from scripts.per_p15b9_rootfs_identity_gate import verify_rootfs, STATUS


class InstalledIdentityFixtures(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory(prefix="p15b9r-fixture-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "rootfs"
        (self.root / "etc").mkdir(parents=True)
        (self.root / "usr/lib/systemd/system").mkdir(parents=True)
        (self.root / "usr/lib/systemd/system-preset").mkdir(parents=True)
        self.passwd = self.root / "etc/passwd"
        self.group = self.root / "etc/group"
        self.shadow = self.root / "etc/shadow"
        self.passwd.write_text(
            "root:x:0:0:root:/root:/bin/sh\n"
            "microduck:x:1000:100:OEM:/home/microduck:/bin/bash\n"
            "kwipi:x:981:981::/home/kwipi:/sbin/nologin\n"
        )
        self.group.write_text(
            "root:x:0:\nusers:x:100:\nkwipi:x:981:\n"
            + "".join(f"{g}:x:{1001+i}:microduck\n" for i, g in enumerate(
                ("robot", "sudo", "audio", "video", "dialout", "i2c",
                 "plugdev", "input")))
        )
        self.shadow.write_text(
            "root:!:19000:0:99999:7:::\n"
            "microduck:!synthetic-oem:19000:0:99999:7:::\n"
            "kwipi:!:19000:0:99999:7:::\n"
        )
        self.shadow.chmod(0o600)
        self.unit = self.root / "usr/lib/systemd/system/kwipi-readonly-probe.service"
        self.unit.write_text(
            "[Unit]\nDescription=read-only probe\n[Service]\n"
            "Type=oneshot\nExecStart=/usr/libexec/kwipi/health_probe.py\n"
        )
        self.preset = (self.root /
                       "usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset")
        self.preset.write_text("disable kwipi-readonly-probe.service\n")

    def test_positive_is_identity_files_only_not_robot(self):
        result = verify_rootfs(self.root)
        self.assertEqual(STATUS, result["status"])
        self.assertTrue(result["kwipi_uid_isolated_nonroot"])
        self.assertFalse(result["robot_validated"])
        self.assertFalse(result["runtime_service_state_verified"])
        self.assertNotIn("synthetic-oem", str(result))

    def test_negative_uid_root_or_shared(self):
        original = self.passwd.read_text()
        for wrong in (0, 1000):
            with self.subTest(wrong=wrong):
                self.passwd.write_text(original.replace("kwipi:x:981:", f"kwipi:x:{wrong}:"))
                with self.assertRaises(Refused):
                    verify_rootfs(self.root)
        self.passwd.write_text(original)

    def test_negative_wrong_primary_gid(self):
        original = self.passwd.read_text()
        self.passwd.write_text(original.replace(":981:981::", ":981:1001::"))
        with self.assertRaises(Refused):
            verify_rootfs(self.root)

    def test_negative_interactive_shell(self):
        self.passwd.write_text(self.passwd.read_text().replace(
            "/home/kwipi:/sbin/nologin", "/home/kwipi:/bin/bash"))
        with self.assertRaises(Refused):
            verify_rootfs(self.root)

    def test_negative_shadow_unlocked_or_world_readable(self):
        original = self.shadow.read_text()
        self.shadow.write_text(original.replace(
            "kwipi:!:19000", "kwipi:password:19000"))
        with self.assertRaises(Refused):
            verify_rootfs(self.root)
        self.shadow.write_text(original)
        self.shadow.chmod(0o644)
        with self.assertRaises(Refused):
            verify_rootfs(self.root)

    def test_negative_motor_group(self):
        self.group.write_text(self.group.read_text().replace(
            "robot:x:1001:microduck", "robot:x:1001:microduck,kwipi"))
        with self.assertRaises(Refused):
            verify_rootfs(self.root)

    def test_negative_oem_operator_group_drift(self):
        self.group.write_text(self.group.read_text().replace(
            "robot:x:1001:microduck", "robot:x:1001:"))
        with self.assertRaises(Refused):
            verify_rootfs(self.root)

    def test_negative_unexpected_home_created(self):
        (self.root / "home/kwipi").mkdir(parents=True)
        with self.assertRaises(Refused):
            verify_rootfs(self.root)

    def test_negative_unit_enabled_or_missing(self):
        self.preset.write_text("enable kwipi-readonly-probe.service\n")
        with self.assertRaises(Refused):
            verify_rootfs(self.root)
        self.preset.write_text("disable kwipi-readonly-probe.service\n")
        self.unit.write_text(self.unit.read_text() + "[Install]\nWantedBy=multi-user.target\n")
        with self.assertRaises(Refused):
            verify_rootfs(self.root)

    def test_negative_systemd_wants_link(self):
        wants = self.root / "etc/systemd/system/multi-user.target.wants"
        wants.mkdir(parents=True)
        (wants / "kwipi-readonly-probe.service").symlink_to(self.unit)
        with self.assertRaises(Refused):
            verify_rootfs(self.root)

    def test_negative_linked_passwd_or_group(self):
        group_content = self.group.read_text()
        self.group.unlink()
        target = self.root / "etc/group-actual"
        target.write_text(group_content)
        self.group.symlink_to(target)
        with self.assertRaises(Refused):
            verify_rootfs(self.root)

    def test_negative_duplicate_or_missing_account(self):
        text = self.passwd.read_text()
        self.passwd.write_text(text + text.splitlines()[-1] + "\n")
        with self.assertRaises(Refused):
            verify_rootfs(self.root)
        self.passwd.write_text(text.replace("kwipi:x:981:981::/home/kwipi:/sbin/nologin\n", ""))
        with self.assertRaises(Refused):
            verify_rootfs(self.root)


if __name__ == "__main__":
    unittest.main()
