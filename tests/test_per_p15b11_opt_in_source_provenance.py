"""P15-B11: offline source packaging gates; NO robot, camera or BitBake."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from scripts.per_p11_v1_source_release import (
    MANIFEST_NAME, ReleaseRefused, local_detections_profile,
    local_profile_from_source, manifest_for, verify_archive, write_tar,
)
from scripts.per_p12_yocto_layer import BMI_URI, DAEMON_URI, layer_files


REV = "b" * 40
MAIN = (
    "/// P15-B4 opt-in, never started by the stock systemd unit.\n"
    "#[arg(long, default_value_t = false)]\n"
    "kwipi_local_detections: bool,\n"
    "if args.kwipi_local_detections { /* use existing worker */ }\n"
)
LIB = "pub mod local_detections;\n"
LOCAL = (
    'mod acl_policy { include!("local_detections_acl.rs"); }\n'
    "acl_policy::observer_uid()?;\n"
    "acl_policy::hide_private_dir_before_bind(parent, uid)?;\n"
    "acl_policy::grant_socket(path, uid)?;\n"
    "acl_policy::grant_private_dir(parent, uid)?;\n"
)
ACL = 'const NAME: &str = "system.posix_acl_access"; getpwnam_r(...);\n'


def sample() -> dict[str, bytes]:
    return {
        "mediad/src/main.rs": MAIN.encode(),
        "mediad/src/lib.rs": LIB.encode(),
        "mediad/src/local_detections.rs": LOCAL.encode(),
        "mediad/src/local_detections_acl.rs": ACL.encode(),
    }


def stage(root: Path, files: dict[str, bytes]) -> None:
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


class ProfileContractTests(unittest.TestCase):
    def test_01_legacy_source_without_b4b8_remains_default(self):
        self.assertFalse(local_detections_profile({}))
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage(root, {"mediad/src/main.rs": b"fn main() {}",
                         "mediad/src/lib.rs": b"pub mod frame;"})
            m = manifest_for(root, REV)
            self.assertEqual(m["code"], "P10A_P10B_P10C_without_test_harness")
            self.assertIs(m["local_detections_acl_candidate"], False)

    def test_02_opt_in_requires_exact_both_modules_and_default_off(self):
        files = sample()
        self.assertTrue(local_detections_profile(files))
        for name in files:
            with self.subTest(missing=name):
                bad = dict(files)
                del bad[name]
                if name in ("mediad/src/local_detections.rs",
                            "mediad/src/local_detections_acl.rs"):
                    with self.assertRaises(ReleaseRefused):
                        local_detections_profile(bad)
                else:
                    with self.assertRaises(ReleaseRefused):
                        local_detections_profile(bad)
        for name, before, after in (
            ("mediad/src/main.rs", b"default_value_t = false", b"default_value_t = true"),
            ("mediad/src/main.rs", b"if args.kwipi_local_detections", b"if true"),
            ("mediad/src/local_detections.rs", b"acl_policy::grant_socket(path, uid)",
             b"no_acl_but_claim_it()"),
            ("mediad/src/local_detections_acl.rs", b"getpwnam_r(", b"atoi("),
        ):
            with self.subTest(tamper=name + str(before)):
                bad = dict(files)
                bad[name] = bad[name].replace(before, after)
                with self.assertRaises(ReleaseRefused):
                    local_detections_profile(bad)

    def test_03_manifest_and_archive_fail_closed_on_forgery(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "candidate"
            root.mkdir()
            stage(root, sample())
            self.assertTrue(local_profile_from_source(root))
            doc = manifest_for(root, REV)
            self.assertTrue(doc["local_detections_acl_candidate"])
            (root / MANIFEST_NAME).write_text(json.dumps(doc), encoding="utf-8")
            tar_ok = Path(d) / "ok.tar.gz"
            write_tar(root, tar_ok)
            self.assertEqual(verify_archive(tar_ok), doc)
            raw = (root / MANIFEST_NAME).read_text()
            doc["local_detections_acl_candidate"] = False
            (root / MANIFEST_NAME).write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaisesRegex(ReleaseRefused, "profile manifest"):
                verify_archive(_write(root, Path(d) / "forged.tar.gz"))
            (root / MANIFEST_NAME).write_text(raw, encoding="utf-8")
            path = root / "mediad/src/local_detections_acl.rs"
            path.write_text("system.posix_acl_access\n", encoding="utf-8")
            with self.assertRaisesRegex(ReleaseRefused, "content differs"):
                verify_archive(_write(root, Path(d) / "tampered.tar.gz"))

    def test_04_p12_source_candidate_version_and_revision_are_distinct(self):
        common = {"companion_sha": REV}
        legacy = layer_files(common, "c" * 64, [("serde", "1.0", "d" * 64)])
        b8 = layer_files(dict(common, local_detections_acl_candidate=True),
                         "c" * 64, [("serde", "1.0", "d" * 64)])
        name = "recipes-microduck/microduck-daemon/microduck-daemon.bbappend"
        a, b = legacy[name], b8[name]
        self.assertIn("0.17.8+kwipi.p12." + REV[:12] + '"', a)
        self.assertIn("0.17.8+kwipi.p12." + REV[:12] + '.b8"', b)
        self.assertNotIn(".b8", a)
        self.assertIn('export DUCK_REVISION = "' + REV + '"', b)
        self.assertEqual(b.count("file://kwipi-v1-oem-source.tar.gz"), 1)
        self.assertEqual(b.count(BMI_URI), 1)
        self.assertNotIn(DAEMON_URI, b)
        with self.assertRaises(ReleaseRefused):
            layer_files(dict(common, local_detections_acl_candidate="yes"),
                        "c" * 64, [("serde", "1.0", "d" * 64)])

    def test_05_symlinked_opt_in_source_rejected_before_packaging(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            stage(root, sample())
            source = root / "mediad/src/local_detections_acl.rs"
            target = root / "mediad/src/other-file"
            source.rename(target)
            source.symlink_to(target)
            with self.assertRaises(ReleaseRefused):
                local_profile_from_source(root)


def _write(root: Path, output: Path) -> Path:
    write_tar(root, output)
    return output


if __name__ == "__main__":
    unittest.main()
