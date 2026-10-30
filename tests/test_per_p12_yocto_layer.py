"""PER-P12: positive/negative gates for a source-only Yocto layer."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.per_p11_v1_source_release import ReleaseRefused
from scripts.per_p12_yocto_layer import (
    BMI_SHA, DAEMON_URI, OEM_FILES, YOCTO_SHA,
    check_yocto, checked_artifact, crates, layer_files, render_crates,
    stage, verify,
)

GOOD_LOCK = ("""version = 3

[[package]]
name = "bmi088"
version = "0.1.2"
source = "git+https://github.com/pollen-robotics/bmi088-rs?tag=v0.1.2#"""
+ BMI_SHA + """"

[[package]]
name = "kwipi-seg-mask-core"
version = "0.1.0"

[[package]]
name = "serde"
version = "1.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = """ + '"' + "a" * 64 + '"' + "\n").encode("utf-8")


class PureSourceContractTests(unittest.TestCase):
    def test_minimal_exact_registry_and_vendor_dependency(self):
        self.assertEqual(crates(GOOD_LOCK), [("serde", "1.0.0", "a" * 64)])

    def test_checksum_missing_is_fatal(self):
        with self.assertRaises(ReleaseRefused):
            crates(GOOD_LOCK.replace(b"a" * 64, b"not-a-hash"))

    def test_duplicate_dependency_is_fatal(self):
        extra = b'\n[[package]]\nname = "serde"\nversion = "1.0.0"\n' + (
            b'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
            b'checksum = "' + b"a" * 64 + b'"\n')
        with self.assertRaises(ReleaseRefused):
            crates(GOOD_LOCK + extra)

    def test_modified_bmi_vendor_revision_is_fatal(self):
        with self.assertRaises(ReleaseRefused):
            crates(GOOD_LOCK.replace(BMI_SHA.encode("ascii"), b"0" * 40))

    def test_additional_git_registry_is_fatal(self):
        with self.assertRaises(ReleaseRefused):
            crates(GOOD_LOCK.replace(b"crates.io-index", b"untrusted-index"))

    def test_generated_crates_source_is_exact_and_has_only_one_registry(self):
        content = render_crates(crates(GOOD_LOCK))
        self.assertEqual(content.count("crate://crates.io/serde/1.0.0"), 1)
        self.assertIn('SRC_URI[serde-1.0.0.sha256sum] = "' + "a" * 64 + '"', content)
        self.assertNotIn("bmi088", content)

    def test_generated_bbappend_selects_only_one_oem_daemon_source(self):
        revision = "c" * 40
        result = layer_files({"companion_sha": revision}, "d" * 64, crates(GOOD_LOCK))
        append = result["recipes-microduck/microduck-daemon/microduck-daemon.bbappend"]
        self.assertNotIn(DAEMON_URI, append)
        self.assertEqual(append.count("file://kwipi-v1-oem-source.tar.gz"), 1)
        self.assertEqual(append.count("name=bmi088"), 1)
        self.assertEqual(append.count('SRC_URI = "'), 1)
        self.assertIn("SRCREV_FORMAT = \"bmi088\"", append)
        self.assertIn("0.17.8+kwipi.p12.cccccccccccc", append)
        self.assertIn("sha256sum", append)
        for file in OEM_FILES:
            self.assertIn("file://" + file, append)
        self.assertIn('BBFILE_PRIORITY_kwipi = "21"', result["conf/layer.conf"])

    def test_unsupported_duplicate_output_does_not_mutate(self):
        with tempfile.TemporaryDirectory() as directory:
            d = Path(directory)
            d.joinpath("layer").mkdir()
            d.joinpath("layer", "keep").write_text("keep", encoding="ascii")
            with self.assertRaises(ReleaseRefused):
                stage(d, d, d / "layer")
            self.assertEqual((d / "layer/keep").read_text(), "keep")


@unittest.skipUnless(
    os.environ.get("KWIPI_P12_YOCTO") and os.environ.get("KWIPI_P12_SOURCE")
    and Path(os.environ["KWIPI_P12_YOCTO"]).is_dir()
    and Path(os.environ["KWIPI_P12_SOURCE"]).is_dir(),
    "requires exact checked-out Yocto + P11 artifact in CI",
)
class RealPinnedSourceTests(unittest.TestCase):
    def setUp(self):
        self.yocto = Path(os.environ["KWIPI_P12_YOCTO"])
        self.artifact = Path(os.environ["KWIPI_P12_SOURCE"])

    def test_real_yocto_recipe_and_crates_change_is_identified(self):
        old_inc = check_yocto(self.yocto)
        archive, manifest, lock, digest = checked_artifact(self.artifact)
        rows = crates(lock)
        self.assertNotIn("P11 weight", old_inc)
        self.assertEqual(len(digest), 64)
        self.assertEqual(manifest["status"], "source_candidate_only_bitbake_licence_and_robot_blocked")
        self.assertGreater(len(rows), 400)

    def test_real_layer_is_deterministic_and_sha_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b = root / "a", root / "b"
            one = stage(self.yocto, self.artifact, a)
            two = stage(self.yocto, self.artifact, b)
            self.assertEqual(one, two)
            self.assertEqual(verify(a), one)
            self.assertFalse(one["bitbake_parsed"])
            self.assertFalse(one["robot_validated"])
            self.assertTrue(one["crates_regenerated"])
            aa = a / "recipes-microduck/microduck-daemon"
            bb = b / "recipes-microduck/microduck-daemon"
            for rel in ("microduck-daemon.bbappend", "microduck-daemon-crates-kwipi.inc"):
                self.assertEqual((aa / rel).read_bytes(), (bb / rel).read_bytes())
            with self.assertRaises(ReleaseRefused):
                stage(self.yocto, self.artifact, a)
            patched = aa / "microduck-daemon.bbappend"
            patched.write_text(patched.read_text() + "\n# unexpected patch\n", encoding="utf-8")
            with self.assertRaises(ReleaseRefused):
                verify(a)

    def test_misleading_provenance_or_modified_binary_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            layer = Path(directory) / "layer"
            stage(self.yocto, self.artifact, layer)
            provenance = layer / "kwipi-layer-provenance.json"
            state = json.loads(provenance.read_text())
            state["bitbake_built"] = True
            provenance.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaises(ReleaseRefused):
                verify(layer)
            state["bitbake_built"] = False
            provenance.write_text(json.dumps(state), encoding="utf-8")
            archive = layer / "recipes-microduck/microduck-daemon/files/kwipi-v1-oem-source.tar.gz"
            with archive.open("ab") as file:
                file.write(b"unauthorized trailing bytes")
            with self.assertRaises(ReleaseRefused):
                verify(layer)


if __name__ == "__main__":
    unittest.main()
