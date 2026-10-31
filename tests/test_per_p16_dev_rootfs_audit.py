"""P16 offline audit fixtures: never runs BitBake or claims target validation."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from scripts.per_p16_dev_rootfs_audit import (PROBE_HASHES, PINNED_P14B_ARCHIVE_SHA256,
    PYTHON_PREFIX, Refused, validate, _verify_python_slice)

# This suite uses predeclared immutable fixture bytes, not the actual package
# verified on WSL2. The positive check verifies only the manifest gates; real
# P16 audit must consume the genuine rootfs and package SHA-256.
class P16FixtureTests(unittest.TestCase):
    def test_positive_synthetic_rootfs_only(self):
        import hashlib
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            manifest = r / "microduck-image-dev-microduck-zero3.rootfs.manifest"
            manifest.write_text("".join(
                f"{x} all 1\n" for x in
                ("kwipi-companion", "kwipi-readonly-probe",
                 "microduck-daemon", "microduck-data")))
            synthetic = {}
            for rel in PROBE_HASHES:
                file = r / rel
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_bytes(("fixture:" + rel).encode())
                synthetic[rel] = hashlib.sha256(file.read_bytes()).hexdigest()
            with patch.dict(PROBE_HASHES, synthetic), patch(
                    "scripts.per_p16_dev_rootfs_audit._verify_python_slice",
                    return_value={"synthetic_module_%02d.py" % i: "synthetic"
                                  for i in range(19)},
                ):
                result = validate(r, manifest, builder_exit=0,
                                  source_head="a" * 40, source_root=r)
            self.assertEqual(result["status"],
                "existing_dev_rootfs_probe_and_package_manifest_checked_only")
            self.assertFalse(result["rauc_signed_or_verified"])
            self.assertFalse(result["robot_validated"])
            self.assertFalse(result["license_redistribution_approved"])
            self.assertEqual(result["python_modules_verified"], 19)
            self.assertTrue(result["do_rootfs_exit_zero_operator_declared_not_independently_attested"])


    def test_p14b_19_installed_modules_positive_negative(self):
        import hashlib
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "rootfs"
            source = Path(d) / "source"
            source.mkdir()
            entries = {"pyproject.toml": "metadata"}
            for i in range(19):
                name = "verified_%02d.py" % i
                rel = "microduck_companion/" + name
                p = root / PYTHON_PREFIX / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(("P14B fixture " + name).encode("ascii"))
                entries[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
            proof = {
                "source_revision": "b" * 40,
                "source_archive_sha256": PINNED_P14B_ARCHIVE_SHA256,
                "source_sha256": entries,
            }
            with patch("scripts.per_p16_dev_rootfs_audit.staged_files",
                       return_value=({}, proof)):
                result = _verify_python_slice(root, source, "b" * 40)
                self.assertEqual(len(result), 19)
                with self.assertRaisesRegex(Refused, "source head"):
                    _verify_python_slice(root, source, "c" * 40)
                p = root / PYTHON_PREFIX / "microduck_companion/verified_00.py"
                p.write_bytes(b"tampered")
                with self.assertRaisesRegex(Refused, "module bytes"):
                    _verify_python_slice(root, source, "b" * 40)
                p.write_bytes(b"P14B fixture verified_00.py")
                p.unlink()
                with self.assertRaises(Refused):
                    _verify_python_slice(root, source, "b" * 40)
                p.symlink_to(source)
                with self.assertRaises(Refused):
                    _verify_python_slice(root, source, "b" * 40)


    def test_shipping_or_renamed_manifest_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "microduck-image-microduck-zero3.rootfs.manifest"
            manifest.write_text("microduck-daemon aarch64 0.17.8\n")
            with self.assertRaisesRegex(Refused, "expected OEM DEV"):
                validate(root, manifest, builder_exit=0, source_head="a"*40)

    def test_nonexistent_rootfs_refused(self):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d) / "microduck-image-dev-microduck-zero3.rootfs.manifest"
            m.write_text("kwipi-companion all 0.2.0a1\n")
            with self.assertRaises(Refused):
                validate(Path(d)/"not-built", m, builder_exit=0, source_head="a"*40)
    def test_nonzero_build_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            m = r/"microduck-image-dev-microduck-zero3.rootfs.manifest"; m.write_text("")
            with self.assertRaisesRegex(Refused,"exit"):
                validate(r,m,builder_exit=1,source_head="a"*40)
    def test_missing_manifest_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Refused):
                validate(Path(d),Path(d)/"absent",builder_exit=0,source_head="a"*40)
    def test_source_head_required(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(Refused):
                validate(Path(d),Path(d)/"absent",builder_exit=0,source_head="unknown")
    def test_incomplete_package_list_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);m=r/"microduck-image-dev-microduck-zero3.rootfs.manifest";m.write_text("kwipi-companion all 0.2.0a1\n")
            with self.assertRaisesRegex(Refused,"required"):
                validate(r,m,builder_exit=0,source_head="a"*40)
    def test_duplicate_package_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);m=r/"microduck-image-dev-microduck-zero3.rootfs.manifest";m.write_text("kwipi-companion all 0.2.0a1\n"*2)
            with self.assertRaisesRegex(Refused,"duplicate"):
                validate(r,m,builder_exit=0,source_head="a"*40)
    def test_unexpected_package_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);m=r/"microduck-image-dev-microduck-zero3.rootfs.manifest";m.write_text("".join(
                f"{x} all 1\n" for x in
                ("kwipi-companion","kwipi-readonly-probe","microduck-daemon","microduck-data","kwipi-motor")))
            with self.assertRaisesRegex(Refused,"unexpected"):
                validate(r,m,builder_exit=0,source_head="a"*40)
    def test_missing_actual_rootfs_file_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);m=r/"microduck-image-dev-microduck-zero3.rootfs.manifest";m.write_text("".join(
                f"{x} all 1\n" for x in
                ("kwipi-companion","kwipi-readonly-probe","microduck-daemon","microduck-data")))
            with self.assertRaisesRegex(Refused,"missing file"):
                validate(r,m,builder_exit=0,source_head="a"*40)

    def test_python_provenance_not_skipped_with_no_source_checkout(self):
        import hashlib
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)
            manifest=r/"microduck-image-dev-microduck-zero3.rootfs.manifest"
            manifest.write_text("".join(f"{n} all 1\n" for n in
                ("kwipi-companion", "kwipi-readonly-probe", "microduck-daemon", "microduck-data")))
            sample={}
            for rel in PROBE_HASHES:
                p=r/rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(rel.encode())
                sample[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
            with patch.dict(PROBE_HASHES, sample), self.assertRaisesRegex(Refused, "source checkout"):
                validate(r,manifest,builder_exit=0,source_head="a"*40)

    def test_no_implied_success(self):
        self.assertEqual(len(PROBE_HASHES),3)
        self.assertNotIn("rootfs_built",PROBE_HASHES)

if __name__ == "__main__":
    unittest.main()
