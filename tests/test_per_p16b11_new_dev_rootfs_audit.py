"""P16-B11 offline rootfs adversarial fixtures; no new image or BitBake run."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p16b11_new_dev_rootfs_audit as b11
from scripts import per_p16b10_dev_rootfs_audit as b10
from scripts import per_p16_dev_rootfs_audit as p16
from scripts import per_p15b18_dev_receiver_env_gate as b18
from scripts import per_p15b17_oem_receiver_package as b17

ROOT = Path(__file__).resolve().parents[1]


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class P16B11OfflineRootfsFixtures(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="kwipi-p16b11-fixture-")
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.rootfs = self.work / "candidate-build/rootfs"
        self.rootfs.mkdir(parents=True)
        self.historical = self.work / "b10-historical-rootfs"
        self.historical.mkdir()
        (self.historical / "B10-KEEP-UNMODIFIED").write_bytes(b"immutable historical")
        self.manifest = self.work / "microduck-image-dev-microduck-zero3.rootfs-20261102151000.manifest"
        self.packages = {
            "microduck-daemon": b10.B12_PKG_VERSION,
            "microduck-data": "0.17.8-r0",
            "kwipi-companion": "0.2.0a1-r0",
            "kwipi-passive-fixture": "0.1.0-r0",
            "kwipi-readonly-probe": "0.1-r0",
            "kwipi-b12-receiver": "0.1.0-r0",
        }
        self._write_manifest()
        self._identity()
        self.new = {}
        self.mods = self.rootfs / p16.PYTHON_PREFIX / "microduck_companion"
        self.mods.mkdir(parents=True)
        for i in range(19):
            name = f"microduck_companion/fixture_{i:02}.py"
            self.new[name] = f"# P14B fixture {i}\n".encode()
        for name in b10.B6_SHA256:
            self.new[name] = ("# B6 fixture " + name + "\n").encode()
        for name in b17.SELECTED:
            self.new[name] = ("# B13-B16 fixture " + name + "\n").encode()
        for name, data in self.new.items():
            target = self.mods / Path(name).name
            target.write_bytes(data)
            target.chmod(0o644)
        self.hashes = {name: sha(raw) for name, raw in self.new.items()}
        self.source_head = "a" * 40
        self.source = self.work / "checkout"
        self.source.mkdir()
        self.archive = {
            "source_revision": self.source_head,
            "oem_yocto_sha": p14b.YOCTO_SHA,
            "archive_sha256": b11.B19_ARCHIVE_SHA256,
        }
        self.metadata = {
            "schema": b18.SCHEMA, "status": b18.STATUS,
            "dev_receiver_count": 1, "shipping_receiver_count": 0,
            "base_modules": 19, "passive_modules": 5, "receiver_modules": 4,
            "receiver_recipe_license": "CLOSED",
            "receiver_recipe_version": b17.VERSION,
            "receiver_rdepends_checked": True,
            "oem_packages_preserved": True,
            "kwipi_account_isolated_by_effective_metadata": True,
            "source_receiver_sha256": b11.B19_ARCHIVE_SHA256,
            "oem_producer_activated": False,
            "systemd_service_activated": False,
            "robot_validated": False,
            "shipping_image_changed": False,
        }
        self._fake_executables()
        p = patch.object(b11, "_source_closure", return_value=(
            self.hashes, self.archive))
        p.start()
        self.addCleanup(p.stop)

    def _write_manifest(self):
        self.manifest.write_text("".join(
            f"{name} all {version}\n" for name, version in self.packages.items()))

    def _identity(self):
        etc = self.rootfs / "etc"
        etc.mkdir()
        (etc / "passwd").write_text(
            "root:x:0:0:root:/root:/bin/sh\n"
            "microduck:x:1000:1000:Microduck:/home/microduck:/bin/sh\n"
            "kwipi:x:1200:1200:Kwipi:/nonexistent:/sbin/nologin\n")
        (etc / "group").write_text(
            "root:x:0:\nmicroduck:x:1000:microduck\nkwipi:x:1200:\n"
            + "".join(f"{g}:x:{200+i}:microduck\n" for i, g in enumerate(
                ("robot", "sudo", "audio", "video", "dialout", "i2c", "plugdev", "input"))))
        shadow = etc / "shadow"
        shadow.write_text("microduck:!:0:0:99999:7:::\nkwipi:!:0:0:99999:7:::\n")
        shadow.chmod(0o600)
        originals = {
            "usr/libexec/kwipi/health_probe.py": b"# audited fixture health probe\n",
            "usr/lib/systemd/system/kwipi-readonly-probe.service":
                b"[Unit]\nDescription=fixture\n[Service]\nType=oneshot\n",
            "usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset":
                b"disable kwipi-readonly-probe.service\n",
        }
        for name, data in originals.items():
            target = self.rootfs / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        p = patch.dict(p16.PROBE_HASHES,
                       {name: sha(data) for name, data in originals.items()},
                       clear=True)
        p.start()
        self.addCleanup(p.stop)

    def _fake_executables(self):
        release = self.rootfs / "opt/robot/daemon/releases" / b10.B12_VERSION / "bin"
        release.mkdir(parents=True)
        expected = {}
        for name in ("robotd", "mediad"):
            blob = (b"\x7fELF\x02\x01" + b"\x00" * 12 + b"\xb7\x00"
                    + ("fixture-" + name).encode())
            binary = release / name
            binary.write_bytes(blob)
            binary.chmod(0o755)
            expected[name] = (len(blob), sha(blob))
        (self.rootfs / "opt/robot/daemon/current").symlink_to(
            "releases/" + b10.B12_VERSION)
        p = patch.dict(b10.B12_BINARIES, expected, clear=True)
        p.start()
        self.addCleanup(p.stop)

    def check(self, *, metadata=None, rootfs=None, manifest=None,
              historical=None, exit_code=0):
        return b11.validate(
            self.rootfs if rootfs is None else rootfs,
            self.historical if historical is None else historical,
            self.manifest if manifest is None else manifest,
            self.source, self.source_head, builder_exit=exit_code,
            metadata=self.metadata if metadata is None else metadata,
        )

    def test_positive_28_modules_and_no_new_runtime_claim(self):
        result = self.check()
        self.assertEqual(result["status"], b11.STATUS)
        self.assertEqual(result["python_modules_verified"], 28)
        self.assertEqual((result["p14b_modules_verified"],
                          result["p15b6_modules_verified"],
                          result["b13_b16_modules_verified"]), (19, 5, 4))
        self.assertEqual(len(result["python_sha256"]), 28)
        self.assertEqual(len(result["b12_sha256"]), 2)
        self.assertTrue(result["kwipi_account_isolated_from_motor"])
        self.assertTrue(result["historical_b10_rootfs_distinct_and_unmodified_by_gate"])
        for k in ("manifest_rootfs_association_independently_attested",
                  "bitbake_executed_by_this_gate", "shipping_rootfs_checked",
                  "device_runtime_import_verified", "oem_detector_activated",
                  "real_socket_acl_verified", "camera_or_npu_verified",
                  "rauc_signed_or_verified", "robot_validated"):
            self.assertFalse(result[k], k)
        self.assertEqual((self.historical / "B10-KEEP-UNMODIFIED").read_bytes(),
                         b"immutable historical")

    def test_module_missing_extra_and_bytecode_refused(self):
        target = self.mods / "b16_oem_readonly_reader.py"
        original = target.read_bytes()
        target.unlink()
        with self.assertRaises(b11.Refused):
            self.check()
        target.write_bytes(original)
        target.chmod(0o644)
        for name in ("unexpected.py", "__init__.pyc", ".hidden", "mediad.rknn"):
            item = self.mods / name
            item.write_bytes(b"unreviewed")
            with self.subTest(name=name), self.assertRaises(b11.Refused):
                self.check()
            item.unlink()

    def test_source_sha_and_mode_symlink_refused(self):
        name = self.mods / "b15_cross_uid_host_gate.py"
        original = name.read_bytes()
        name.write_bytes(original + b"# changed")
        with self.assertRaises(b11.Refused):
            self.check()
        name.write_bytes(original)
        for mode in (0o600, 0o755, 0o444):
            name.chmod(mode)
            with self.subTest(mode=mode), self.assertRaises(b11.Refused):
                self.check()
        name.chmod(0o644)
        name.unlink()
        name.symlink_to(self.historical / "B10-KEEP-UNMODIFIED")
        with self.assertRaises(b11.Refused):
            self.check()

    def test_unexpected_subdirectory_refused(self):
        (self.mods / "__pycache__").mkdir()
        with self.assertRaises(b11.Refused):
            self.check()

    def test_same_nested_or_symlinked_old_rootfs_refused(self):
        with self.assertRaises(b11.Refused):
            self.check(historical=self.rootfs)
        with self.assertRaises(b11.Refused):
            self.check(historical=self.rootfs.parent)
        link = self.work / "linked-history"
        link.symlink_to(self.historical, target_is_directory=True)
        with self.assertRaises(b11.Refused):
            self.check(historical=link)

    def test_manifest_missing_duplicate_shipping_or_wrong_version(self):
        for edits in (
            {"kwipi-b12-receiver": "0.2.0"},
            {"kwipi-b12-receiver": None},
            {"microduck-daemon": "unreviewed"},
        ):
            old = dict(self.packages)
            self.packages = {k: v for k, v in old.items() if edits.get(k, "ok") is not None}
            self.packages.update({k: v for k, v in edits.items() if v is not None})
            self._write_manifest()
            with self.subTest(edits=edits), self.assertRaises(b11.Refused):
                self.check()
            self.packages = old
        self._write_manifest()
        self.manifest.write_text(
            self.manifest.read_text() + "kwipi-b12-receiver all 0.1.0-r0\n")
        with self.assertRaises((b11.Refused, p16.Refused)):
            self.check()
        self._write_manifest()
        old = self.manifest
        self.manifest = self.manifest.rename(
            self.work / "microduck-image-microduck-zero3.rootfs.manifest")
        with self.assertRaises(b11.Refused):
            self.check()
        self.manifest = self.manifest.rename(old)

    def test_manifest_symlink_and_nonzero_builder_exit_refused(self):
        link = self.work / "fake-manifest"
        link.symlink_to(self.manifest)
        with self.assertRaises(b11.Refused):
            self.check(manifest=link)
        for bad in (1, -1, True):
            with self.assertRaises(b11.Refused):
                self.check(exit_code=bad)

    def test_kwipi_group_and_password_regression_refused(self):
        g = self.rootfs / "etc/group"
        original = g.read_text()
        g.write_text(original.replace("robot:x:200:microduck",
                                      "robot:x:200:microduck,kwipi"))
        with self.assertRaises(b11.Refused):
            self.check()
        g.write_text(original)
        s = self.rootfs / "etc/shadow"
        original = s.read_text()
        s.write_text(original.replace("kwipi:!", "kwipi:$6$"))
        with self.assertRaises(b11.Refused):
            self.check()
        s.write_text(original)

    def test_service_activation_and_probe_change_refused(self):
        svc = self.rootfs / "etc/systemd/system/multi-user.target.wants"
        svc.mkdir(parents=True)
        (svc / "kwipi-readonly-probe.service").symlink_to(
            self.rootfs / "usr/lib/systemd/system/kwipi-readonly-probe.service")
        with self.assertRaises(b11.Refused):
            self.check()
        (svc / "kwipi-readonly-probe.service").unlink()
        file = self.rootfs / "usr/libexec/kwipi/health_probe.py"
        file.write_bytes(b"# replacement\n")
        with self.assertRaises(b11.Refused):
            self.check()

    def test_oem_executable_sha_and_mode_refused(self):
        f = self.rootfs / "opt/robot/daemon/releases" / b10.B12_VERSION / "bin/mediad"
        data = f.read_bytes()
        f.write_bytes(data + b"x")
        with self.assertRaises(b11.Refused):
            self.check()
        f.write_bytes(data)
        f.chmod(0o644)
        with self.assertRaises(b11.Refused):
            self.check()

    def test_supplied_b18_metadata_must_not_claim_activation(self):
        for key, value in (
            ("schema", "unreviewed"),
            ("source_receiver_sha256", "0" * 64),
            ("shipping_receiver_count", 1),
            ("dev_receiver_count", 0),
            ("oem_producer_activated", True),
            ("systemd_service_activated", True),
            ("robot_validated", True),
            ("receiver_recipe_version", "0.2.0"),
        ):
            with self.subTest(key=key), self.assertRaises(b11.Refused):
                self.check(metadata={**self.metadata, key: value})

    def test_load_proof_refuses_symlink_or_non_dictionary(self):
        path = self.work / "proof.json"
        path.write_text(json.dumps(self.metadata))
        self.assertEqual(b11._load_proof(path), self.metadata)
        link = self.work / "proof-link"
        link.symlink_to(path)
        with self.assertRaises(b11.Refused):
            b11._load_proof(link)
        path.write_text("[]")
        with self.assertRaises(b11.Refused):
            b11._load_proof(path)


class ActualB19SourceCompatibility(unittest.TestCase):
    def test_source_archive_still_matches_real_b19_sha(self):
        # This is real repository data, not the synthetic rootfs above.
        source_head = p14b.repo_sha(ROOT)
        hashes, proof = b11._source_closure(ROOT, source_head)
        self.assertEqual(len(hashes), 28)
        self.assertEqual(proof["archive_sha256"], b11.B19_ARCHIVE_SHA256)
        self.assertEqual({k for k in hashes if k in b17.SELECTED}, b17.SELECTED)


if __name__ == "__main__":
    unittest.main()
