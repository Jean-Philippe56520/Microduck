"""P16-A/B10 synthetic rootfs gates: no build, OEM process, or robot."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import per_p16b10_dev_rootfs_audit as gate
from scripts import per_p16_dev_rootfs_audit as old
from scripts import per_p15b6_passive_python_addon as b6


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class B10RootfsFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "rootfs"
        self.root.mkdir()
        self.source = Path(self.tmp.name) / "source"
        self.source.mkdir()
        self.manifest = Path(self.tmp.name) / "microduck-image-dev-microduck-zero3.rootfs.manifest"
        self.packages = {
            "kwipi-companion": "0.2.0a1-r0",
            "kwipi-passive-fixture": "0.1.0-r0",
            "kwipi-readonly-probe": "0.1.0-r0",
            "microduck-daemon": gate.B12_VERSION + "-r0",
            "microduck-data": "0.17.8-r0",
        }
        self._write_manifest()
        self._make_identity()
        self.module_root = self.root / old.PYTHON_PREFIX / "microduck_companion"
        self.module_root.mkdir(parents=True)
        self.base_files = {}
        for i in range(19):
            rel = f"microduck_companion/verified_{i:02d}.py"
            data = f"# fixture P14B {i}\n".encode()
            (self.root / old.PYTHON_PREFIX / rel).write_bytes(data)
            self.base_files[rel] = sha(data)
        self.addon_files = {}
        for rel in gate.B6_SHA256:
            data = ("# fixture " + rel + "\n").encode()
            (self.root / old.PYTHON_PREFIX / rel).write_bytes(data)
            self.addon_files[rel] = sha(data)
        self.base_proof = {
            "source_revision": gate.SOURCE_HEAD,
            "selected_python_modules": 19,
            "source_archive_sha256": old.PINNED_P14B_ARCHIVE_SHA256,
            "source_sha256": {**self.base_files, "pyproject.toml": "fixture"},
        }
        self.addon_proof = {
            "source_revision": gate.SOURCE_HEAD,
            "base_modules": 19,
            "addon_modules": 5,
            "base_sha256": self.base_files,
            "addon_sha256": self.addon_files,
        }
        self.patches = [
            patch("scripts.per_p16b10_dev_rootfs_audit.p14b.staged_files",
                  return_value=({}, self.base_proof)),
            patch("scripts.per_p16b10_dev_rootfs_audit.b6.staged_files",
                  return_value=({}, self.addon_proof)),
            patch.dict(gate.B6_SHA256, self.addon_files, clear=True),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        release = self.root / "opt/robot/daemon/releases" / gate.B12_VERSION / "bin"
        release.mkdir(parents=True)
        bins = {}
        for name in gate.B12_BINARIES:
            data = b"\x7fELF\x02\x01" + (b"\x00" * 12) + b"\xb7\x00" + ("fixture:" + name).encode()
            binary = release / name
            binary.write_bytes(data)
            binary.chmod(0o755)
            bins[name] = (len(data), sha(data))
        (self.root / "opt/robot/daemon/current").symlink_to(
            "releases/" + gate.B12_VERSION)
        p = patch.dict(gate.B12_BINARIES, bins, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def _write_manifest(self):
        self.manifest.write_text("".join(
            f"{name} all {version}\n" for name, version in self.packages.items()))

    def _make_identity(self):
        etc = self.root / "etc"
        etc.mkdir()
        (etc / "passwd").write_text(
            "root:x:0:0:root:/root:/bin/sh\n"
            "microduck:x:1000:1000:Microduck:/home/microduck:/bin/sh\n"
            "kwipi:x:1200:1200:Kwipi:/nonexistent:/sbin/nologin\n"
        )
        oem = ("robot", "sudo", "audio", "video", "dialout", "i2c", "plugdev", "input")
        (etc / "group").write_text(
            "root:x:0:\nmicroduck:x:1000:microduck\nkwipi:x:1200:\n" +
            "".join(f"{name}:x:{100+i}:microduck\n" for i, name in enumerate(oem))
        )
        shadow = etc / "shadow"
        shadow.write_text("microduck:!:0:0:99999:7:::\nkwipi:!:0:0:99999:7:::\n")
        shadow.chmod(0o600)
        files = {
            "usr/libexec/kwipi/health_probe.py": b"# passive P15A fixture\n",
            "usr/lib/systemd/system/kwipi-readonly-probe.service":
                b"[Unit]\nDescription=fixture\n[Service]\nType=oneshot\nSupplementaryGroups=robot\n",
            "usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset":
                b"disable kwipi-readonly-probe.service\n",
        }
        proofs = {}
        for rel, data in files.items():
            f = self.root / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
            proofs[rel] = sha(data)
        p = patch.dict(old.PROBE_HASHES, proofs, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def run_gate(self):
        return gate.validate(self.root, self.manifest, builder_exit=0,
                             source_head=gate.SOURCE_HEAD, source_root=self.source)

    def test_positive_24_modules_b12_identity_without_shipping_claim(self):
        proof = self.run_gate()
        self.assertEqual(proof["status"], gate.STATUS)
        self.assertEqual(proof["python_modules_verified"], 24)
        self.assertEqual(proof["p15b6_modules_verified"], 5)
        self.assertEqual(len(proof["b12_sha256"]), 2)
        self.assertTrue(proof["kwipi_account_isolated_from_motor"])
        self.assertFalse(proof["shipping_image_checked"])
        self.assertFalse(proof["manifest_rootfs_association_independently_attested"])
        self.assertFalse(proof["robot_validated"])

    def test_missing_or_extra_modules_refused(self):
        missing = self.module_root / "passive_media_router.py"
        saved = missing.read_bytes()
        missing.unlink()
        with self.assertRaisesRegex(gate.Refused, "24-module"):
            self.run_gate()
        missing.write_bytes(saved)
        extra = self.module_root / "unexpected.py"
        extra.write_text("# unknown code\n")
        with self.assertRaisesRegex(gate.Refused, "24-module"):
            self.run_gate()

    def test_changed_module_bytes_refused(self):
        (self.module_root / "passive_resilience.py").write_bytes(b"changed")
        with self.assertRaisesRegex(gate.Refused, "SHA-256"):
            self.run_gate()

    def test_module_symlink_refused(self):
        f = self.module_root / "passive_media_router.py"
        f.unlink()
        f.symlink_to(self.source)
        with self.assertRaisesRegex(gate.Refused, "unreviewed link"):
            self.run_gate()

    def test_unreviewed_binary_file_in_python_package_refused(self):
        (self.module_root / "extra.so").write_bytes(b"unreviewed")
        with self.assertRaisesRegex(gate.Refused, "unexpected installed"):
            self.run_gate()

    def test_wrong_base_or_addon_provenance_refused(self):
        self.base_proof["source_archive_sha256"] = "0" * 64
        with self.assertRaisesRegex(gate.Refused, "provenance"):
            self.run_gate()
        self.base_proof["source_archive_sha256"] = old.PINNED_P14B_ARCHIVE_SHA256
        self.addon_proof["base_sha256"] = {}
        with self.assertRaisesRegex(gate.Refused, "closure"):
            self.run_gate()

    def test_old_current_release_refused(self):
        current = self.root / "opt/robot/daemon/current"
        current.unlink()
        current.symlink_to("releases/0.17.8+kwipi.p12.3406fee5428c")
        with self.assertRaisesRegex(gate.Refused, "current"):
            self.run_gate()

    def test_tampered_or_non_aarch64_binaries_refused(self):
        f = self.root / "opt/robot/daemon/releases" / gate.B12_VERSION / "bin/robotd"
        original = f.read_bytes()
        f.write_bytes(original[:-1] + b"x")
        with self.assertRaisesRegex(gate.Refused, "SHA-256"):
            self.run_gate()
        f.write_bytes(original[:18] + b"\x3e\x00" + original[20:])
        with self.assertRaisesRegex(gate.Refused, "ELF AArch64"):
            self.run_gate()

    def test_privileged_kwipi_group_refused(self):
        f = self.root / "etc/group"
        f.write_text(f.read_text().replace("robot:x:100:microduck", "robot:x:100:microduck,kwipi"))
        with self.assertRaisesRegex(gate.Refused, "identity"):
            self.run_gate()

    def test_p15a_enablement_refused(self):
        wants = self.root / "etc/systemd/system/multi-user.target.wants"
        wants.mkdir(parents=True)
        (wants / "kwipi-readonly-probe.service").symlink_to(
            self.root / "usr/lib/systemd/system/kwipi-readonly-probe.service")
        with self.assertRaisesRegex(gate.Refused, "identity"):
            self.run_gate()

    def test_manifest_versions_and_shipping_refused(self):
        self.packages["microduck-daemon"] = "0.17.8+kwipi.p12.old-r0"
        self._write_manifest()
        with self.assertRaisesRegex(gate.Refused, "version"):
            self.run_gate()
        self.packages["microduck-daemon"] = gate.B12_VERSION + "-r0"
        self.manifest.rename(self.manifest.with_name("microduck-image-microduck-zero3.rootfs.manifest"))
        with self.assertRaisesRegex(gate.Refused, "manifest"):
            self.run_gate()

    def test_missing_b6_and_unknown_kwipi_package_refused(self):
        del self.packages["kwipi-passive-fixture"]
        self._write_manifest()
        with self.assertRaisesRegex(gate.Refused, "missing"):
            self.run_gate()
        self.packages["kwipi-passive-fixture"] = "0.1.0-r0"
        self.packages["kwipi-motor"] = "1"
        self._write_manifest()
        with self.assertRaisesRegex(gate.Refused, "unexpected"):
            self.run_gate()

    def test_bad_builder_exit_and_source_refused(self):
        with self.assertRaisesRegex(gate.Refused, "exit"):
            gate.validate(self.root, self.manifest, builder_exit=1,
                          source_head=gate.SOURCE_HEAD, source_root=self.source)
        with self.assertRaisesRegex(gate.Refused, "pinned B12"):
            gate.validate(self.root, self.manifest, builder_exit=0,
                          source_head="c" * 40, source_root=self.source)


class SourcePinChecks(unittest.TestCase):
    def test_pinned_b6_five_sha_match_current_source_files(self):
        # Independent of synthetic fixture patches above; no target execution.
        root = Path(__file__).resolve().parents[1]
        _, report = b6.staged_files(root)
        self.assertEqual(report["addon_sha256"], gate.B6_SHA256)
        self.assertEqual(report["base_modules"], 19)
        self.assertEqual(report["addon_modules"], 5)


if __name__ == "__main__":
    unittest.main()
