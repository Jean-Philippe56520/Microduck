"""P16-S1 synthetic tests; no actual WSL2/robot claimed."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import per_p16_dev_rootfs_service_gate as gate

UNIT = """# PER-P15A: deliberately no [Install] / WantedBy; manual DEV probe only.
[Unit]
Description=Kwipi passive read-only OEM health check
After=robotd.service
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 -I -B /usr/libexec/kwipi/health_probe.py
DynamicUser=yes
SupplementaryGroups=robot
NoNewPrivileges=yes
"""


class ServiceGateFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / "build/tmp/work/microduck-zero3/microduck-image-dev/1.0/rootfs"
        self.root.mkdir(parents=True)
        content = {
            gate.UNIT_REL: UNIT,
            gate.PRESET_REL: "disable kwipi-readonly-probe.service\n",
            gate.PROBE_REL: "print('safe')\n",
        }
        sha = {}
        for rel, data in content.items():
            p = self.root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(data)
            sha[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        self.hashes = sha
        r = self.base / "proofs/p16-rootfs-audit.json"
        r.parent.mkdir(parents=True)
        r.write_text(json.dumps({
            "status": gate.REPORT_STATUS,
            "python_modules_verified": 19,
            "probe_sha256": sha,
            "probe_systemd_symlink_found": False,
        }))
        self.mock = patch.dict(gate.EXPECTED_SHA256, sha, clear=True)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def test_success_scoped_only(self):
        report = gate.validate(self.base)
        self.assertEqual(report["probe_autostart_references_found"], 0)
        self.assertFalse(report["postinst_package_scriptlets_audited"])
        self.assertTrue(report["robot_socket_group_full_rpc_access_risk_open"])
        self.assertFalse(report["image_built"])

    def test_unit_comment_not_a_real_install_section(self):
        self.assertTrue(gate.validate(self.base)["p16_a_report_rechecked"])

    def test_wrong_checksum_refused(self):
        (self.root / gate.PROBE_REL).write_text("changed")
        with self.assertRaisesRegex(gate.Stop, "rootfs installed bytes changed"):
            gate.validate(self.base)

    def test_real_install_header_refused_even_with_review_hash_updated(self):
        p = self.root / gate.UNIT_REL
        p.write_text(UNIT + "[Install]\nWantedBy=multi-user.target\n")
        self._replace_review_hash(gate.UNIT_REL)
        with self.assertRaisesRegex(gate.Stop, r"real \[Install\]"):
            gate.validate(self.base)

    def _replace_review_hash(self, rel):
        digest = hashlib.sha256((self.root / rel).read_bytes()).hexdigest()
        gate.EXPECTED_SHA256[rel] = digest
        r = self.base / "proofs/p16-rootfs-audit.json"
        j = json.loads(r.read_text())
        j["probe_sha256"][rel] = digest
        r.write_text(json.dumps(j))

    def test_wants_reference_in_other_service_refused(self):
        p = self.root / "usr/lib/systemd/system/evil.service"
        p.write_text("[Unit]\nWants=kwipi-readonly-probe.service\n")
        with self.assertRaisesRegex(gate.Stop, "live probe reference"):
            gate.validate(self.base)

    def test_comment_reference_in_other_service_allowed(self):
        p = self.root / "usr/lib/systemd/system/info.service"
        p.write_text("[Unit]\n# Wants=kwipi-readonly-probe.service\n")
        self.assertEqual(gate.validate(self.base)["other_systemd_files_examined"], 1)

    def test_auto_enable_symlink_refused(self):
        folder = self.root / "etc/systemd/system/multi-user.target.wants"
        folder.mkdir(parents=True)
        (folder / gate.UNIT_NAME).symlink_to(self.root / gate.UNIT_REL)
        with self.assertRaisesRegex(gate.Stop, "systemd symlink"):
            gate.validate(self.base)

    def test_unexpected_preset_refused(self):
        folder = self.root / "etc/systemd/system-preset"
        folder.mkdir(parents=True)
        (folder / "50-overrides.preset").write_text("enable kwipi-readonly-probe.service\n")
        with self.assertRaisesRegex(gate.Stop, "unreviewed systemd preset"):
            gate.validate(self.base)

    def test_deferred_postinst_refused(self):
        folder = self.root / "etc/opkg-postinsts"
        folder.mkdir(parents=True)
        (folder / "kwipi-readonly-probe").write_text("#!/bin/sh\n")
        with self.assertRaisesRegex(gate.Stop, "deferred postinst"):
            gate.validate(self.base)

    def test_service_override_refused(self):
        folder = self.root / "etc/systemd/system"
        folder.mkdir(parents=True)
        (folder / gate.UNIT_NAME).write_text(UNIT)
        with self.assertRaisesRegex(gate.Stop, "override"):
            gate.validate(self.base)

    def test_report_missing_refused(self):
        (self.base / "proofs/p16-rootfs-audit.json").unlink()
        with self.assertRaisesRegex(gate.Stop, "P16-A report"):
            gate.validate(self.base)

    def test_dropin_override_refused(self):
        folder = self.root / "etc/systemd/system/kwipi-readonly-probe.service.d"
        folder.mkdir(parents=True)
        (folder / "override.conf").write_text("[Service]\nRestart=always\n")
        with self.assertRaisesRegex(gate.Stop, "drop-in override"):
            gate.validate(self.base)

    def test_absolute_lib_alias_rooted_in_image(self):
        (self.root / "lib").symlink_to("/usr/lib")
        self.assertEqual(gate.validate(self.base)["probe_autostart_references_found"], 0)

    def test_wrong_preset_refused(self):
        p = self.root / gate.PRESET_REL
        p.write_text("enable kwipi-readonly-probe.service\n")
        self._replace_review_hash(gate.PRESET_REL)
        with self.assertRaisesRegex(gate.Stop, "not exactly disable"):
            gate.validate(self.base)


if __name__ == "__main__":
    unittest.main()
