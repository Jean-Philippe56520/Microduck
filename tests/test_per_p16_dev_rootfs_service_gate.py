"""P16-S1 synthetic tests; no actual WSL2/robot claimed."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import per_p16_dev_rootfs_service_gate as gate
from scripts import per_p16b10_dev_rootfs_audit as b10

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

    def _make_b10_report(self) -> Path:
        """Synthetic B10 fixture, independent of the immutable historical file."""
        legacy = json.loads((self.base / "proofs/p16-rootfs-audit.json").read_text())
        # Build the 24-file source closure and B12 ELF fixtures in the same
        # rootfs that P16-S1 will scan. Never change the historical proof.
        pkg = self.root / b10.p16a.PYTHON_PREFIX / "microduck_companion"
        pkg.mkdir(parents=True, exist_ok=True)
        base_hashes = {}
        for i in range(19):
            name = f"fixture_{i:02d}.py"
            data = f"# P14B synthetic module {i}\n".encode()
            (pkg / name).write_bytes(data)
            base_hashes["microduck_companion/" + name] = hashlib.sha256(data).hexdigest()
        addon_hashes = {}
        for rel in b10.B6_SHA256:
            name = rel.removeprefix("microduck_companion/")
            data = ("# B6 synthetic module " + name + "\n").encode()
            (pkg / name).write_bytes(data)
            addon_hashes[rel] = hashlib.sha256(data).hexdigest()
        addon_patch = patch.dict(b10.B6_SHA256, addon_hashes, clear=True)
        addon_patch.start()
        self.addCleanup(addon_patch.stop)
        binaries = {}
        release = self.root / "opt/robot/daemon/releases" / b10.B12_VERSION / "bin"
        release.mkdir(parents=True, exist_ok=True)
        for name in b10.B12_BINARIES:
            data = b"\x7fELF\x02\x01" + b"\x00" * 12 + b"\xb7\x00" + name.encode()
            binary = release / name
            binary.write_bytes(data)
            binary.chmod(0o755)
            binaries[name] = (len(data), hashlib.sha256(data).hexdigest())
        bin_patch = patch.dict(b10.B12_BINARIES, binaries, clear=True)
        bin_patch.start()
        self.addCleanup(bin_patch.stop)
        (self.root / "opt/robot/daemon/current").symlink_to("releases/" + b10.B12_VERSION)
        report = {
            **legacy,
            "schema": "kwipi-p16b10-existing-dev-rootfs-audit-v1",
            "status": b10.STATUS,
            "source_head_verified_against_checkout": b10.SOURCE_HEAD,
            "p14b_archive_sha256": b10.p16a.PINNED_P14B_ARCHIVE_SHA256,
            "packages": {
                "kwipi-companion": "0.2.0a1",
                "kwipi-passive-fixture": "0.1.0",
                "kwipi-readonly-probe": "0.1",
                "microduck-daemon": b10.B12_PKG_VERSION,
                "microduck-data": "1.0",
            },
            "python_modules_verified": 24,
            "p14b_modules_verified": 19,
            "p15b6_modules_verified": 5,
            "python_sha256": {**base_hashes, **addon_hashes},
            "b12_release": b10.B12_VERSION,
            "b12_sha256": {
                name: digest for name, (_, digest) in b10.B12_BINARIES.items()
            },
            "current_points_to_b12": True,
            "kwipi_account_isolated_from_motor": True,
            "oem_operator_preserved": True,
        }
        path = self.base / "proofs/p16b10-private-new-audit.json"
        path.write_text(json.dumps(report, sort_keys=True))
        return path

    def _validate_b10(self, path: Path):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return gate.validate(self.base, report_path=path, report_sha256=digest)

    def test_b10_report_supported_without_boot_claim_and_legacy_preserved(self):
        historical = self.base / "proofs/p16-rootfs-audit.json"
        old_bytes = historical.read_bytes()
        old_digest = hashlib.sha256(old_bytes).hexdigest()
        path = self._make_b10_report()
        proof = self._validate_b10(path)
        self.assertTrue(proof["p16_b10_report_rechecked"])
        self.assertTrue(proof["b10_report_sha256_verified"])
        self.assertEqual(proof["b10_installed_python_rehashed"], 24)
        self.assertEqual(proof["b10_oem_binaries_rehashed"], 2)
        self.assertFalse(proof["p16_a_report_rechecked"])
        self.assertEqual(proof["input_report_kind"], "P16-B10")
        self.assertEqual(proof["probe_autostart_references_found"], 0)
        self.assertFalse(proof["systemd_runtime_or_boot_verified"])
        self.assertEqual(historical.read_bytes(), old_bytes)
        self.assertEqual(hashlib.sha256(historical.read_bytes()).hexdigest(), old_digest)
        self.assertTrue(gate.validate(self.base)["p16_a_report_rechecked"])

    def test_b10_rejects_old_or_drifted_rootfs_despite_authentic_report(self):
        path = self._make_b10_report()
        installed = self.root / b10.p16a.PYTHON_PREFIX / "microduck_companion/fixture_00.py"
        installed.unlink()
        with self.assertRaisesRegex(gate.Stop, "current rootfs differs from pinned B10 proof"):
            self._validate_b10(path)

    def test_b10_rejects_changed_oem_binary_even_with_authentic_report(self):
        path = self._make_b10_report()
        binary = (self.root / "opt/robot/daemon/releases" /
                  b10.B12_VERSION / "bin/mediad")
        binary.write_bytes(binary.read_bytes() + b"drift")
        with self.assertRaisesRegex(gate.Stop, "current rootfs differs from pinned B10 proof"):
            self._validate_b10(path)

    def test_b10_refuses_missing_oem_binary_with_explicit_stop(self):
        path = self._make_b10_report()
        binary = (self.root / "opt/robot/daemon/releases" /
                  b10.B12_VERSION / "bin/robotd")
        binary.unlink()
        with self.assertRaisesRegex(gate.Stop, "current rootfs differs from pinned B10 proof"):
            self._validate_b10(path)

    def test_b10_report_with_wrong_binary_digest_refused(self):
        path = self._make_b10_report()
        report = json.loads(path.read_text())
        report["b12_sha256"]["robotd"] = "0" * 64
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(gate.Stop, "B10 proof incomplete"):
            self._validate_b10(path)

    def test_b10_report_with_wrong_module_count_refused(self):
        path = self._make_b10_report()
        report = json.loads(path.read_text())
        report["python_modules_verified"] = 19
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(gate.Stop, "expected scope"):
            self._validate_b10(path)

    def test_b10_report_missing_digest_refused(self):
        path = self._make_b10_report()
        with self.assertRaisesRegex(gate.Stop, "requires pinned SHA-256"):
            gate.validate(self.base, report_path=path)

    def test_b10_report_wrong_digest_refused(self):
        path = self._make_b10_report()
        with self.assertRaisesRegex(gate.Stop, "SHA-256 mismatch"):
            gate.validate(self.base, report_path=path, report_sha256="0" * 64)

    def test_b10_report_schema_or_version_changed_refused(self):
        path = self._make_b10_report()
        data = json.loads(path.read_text())
        data["schema"] = "unreviewed-schema"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(gate.Stop, "B10 proof incomplete"):
            self._validate_b10(path)
        data["schema"] = "kwipi-p16b10-existing-dev-rootfs-audit-v1"
        data["packages"]["microduck-daemon"] = "wrong"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(gate.Stop, "B10 proof incomplete"):
            self._validate_b10(path)

    def test_b10_report_24_python_hashes_required(self):
        path = self._make_b10_report()
        data = json.loads(path.read_text())
        data["python_sha256"].pop("microduck_companion/passive_resilience.py")
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(gate.Stop, "B10 proof incomplete"):
            self._validate_b10(path)

    def test_b10_report_status_cannot_be_p16a(self):
        path = self._make_b10_report()
        data = json.loads(path.read_text())
        data["status"] = gate.REPORT_STATUS
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(gate.Stop, "explicit report must be P16-B10"):
            self._validate_b10(path)

    def test_b10_report_bad_json_refused(self):
        path = self._make_b10_report()
        path.write_text('{"status":')
        with self.assertRaisesRegex(gate.Stop, "invalid P16-A/B10 JSON"):
            self._validate_b10(path)

    def test_b10_report_symlink_refused(self):
        path = self._make_b10_report()
        alias = self.base / "proofs/symlink-b10.json"
        alias.symlink_to(path)
        with self.assertRaisesRegex(gate.Stop, "B10 report not found or symlinked"):
            gate.validate(self.base, report_path=alias,
                          report_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def test_b10_report_requires_absolute_path(self):
        with self.assertRaisesRegex(gate.Stop, "path must be absolute"):
            gate.validate(self.base, report_path=Path("proofs/b10.json"),
                          report_sha256="a" * 64)

    def test_historical_report_path_cannot_be_explicit_b10(self):
        historical = self.base / "proofs/p16-rootfs-audit.json"
        with self.assertRaisesRegex(gate.Stop, "historical P16-A report cannot serve"):
            gate.validate(self.base, report_path=historical,
                          report_sha256=hashlib.sha256(historical.read_bytes()).hexdigest())

    def test_default_historical_mode_rejects_replacement_with_b10(self):
        historical = self.base / "proofs/p16-rootfs-audit.json"
        path = self._make_b10_report()
        historical.write_bytes(path.read_bytes())
        with self.assertRaisesRegex(gate.Stop, "historical report path requires P16-A"):
            gate.validate(self.base)

    def test_digest_alone_without_report_refused(self):
        with self.assertRaisesRegex(gate.Stop, "without explicit B10"):
            gate.validate(self.base, report_sha256="0" * 64)

    def test_b10_detects_live_systemd_reference(self):
        path = self._make_b10_report()
        service = self.root / "usr/lib/systemd/system/live.service"
        service.write_text("[Unit]\nWants=kwipi-readonly-probe.service\n")
        with self.assertRaisesRegex(gate.Stop, "live probe reference"):
            self._validate_b10(path)

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
