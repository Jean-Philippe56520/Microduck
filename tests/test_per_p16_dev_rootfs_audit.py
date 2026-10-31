"""P16 offline audit fixtures: never runs BitBake or claims target validation."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from scripts.per_p16_dev_rootfs_audit import PROBE_HASHES, Refused, validate

# This suite uses predeclared immutable fixture bytes, not the actual package
# verified on WSL2. The positive check verifies only the manifest gates; real
# P16 audit must consume the genuine rootfs and package SHA-256.
class P16FixtureTests(unittest.TestCase):
    def test_nonexistent_rootfs_refused(self):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d) / "manifest"
            m.write_text("kwipi-companion all 0.2.0a1\n")
            with self.assertRaises(Refused):
                validate(Path(d)/"not-built", m, builder_exit=0, source_head="a"*40)
    def test_nonzero_build_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r = Path(d)
            m = r/"manifest"; m.write_text("")
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
            r=Path(d);m=r/"manifest";m.write_text("kwipi-companion all 0.2.0a1\n")
            with self.assertRaisesRegex(Refused,"required"):
                validate(r,m,builder_exit=0,source_head="a"*40)
    def test_duplicate_package_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);m=r/"manifest";m.write_text("kwipi-companion all 0.2.0a1\n"*2)
            with self.assertRaisesRegex(Refused,"duplicate"):
                validate(r,m,builder_exit=0,source_head="a"*40)
    def test_unexpected_package_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);m=r/"manifest";m.write_text("".join(
                f"{x} all 1\n" for x in
                ("kwipi-companion","kwipi-readonly-probe","microduck-daemon","microduck-data","kwipi-motor")))
            with self.assertRaisesRegex(Refused,"unexpected"):
                validate(r,m,builder_exit=0,source_head="a"*40)
    def test_missing_actual_rootfs_file_refused(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);m=r/"manifest";m.write_text("".join(
                f"{x} all 1\n" for x in
                ("kwipi-companion","kwipi-readonly-probe","microduck-daemon","microduck-data")))
            with self.assertRaisesRegex(Refused,"missing file"):
                validate(r,m,builder_exit=0,source_head="a"*40)
    def test_no_implied_success(self):
        self.assertEqual(len(PROBE_HASHES),3)
        self.assertNotIn("rootfs_built",PROBE_HASHES)

if __name__ == "__main__":
    unittest.main()
