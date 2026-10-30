"""P14B regression tests: source bytes, reproducibility and fail-closed packaging."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.per_p14b_yocto_python_layer import (
    LAYER, RECIPE, RUNTIME, SCHEMA, SRC_NAME,
    PackageRefused, _tar_bytes, conf, recipe, selected_bytes, stage, verify,
)

ROOT = Path(__file__).resolve().parents[1]


class RealP14BSourceTests(unittest.TestCase):
    def test_p14a_source_closure_without_models_or_mock(self):
        src = selected_bytes(ROOT)
        self.assertEqual(len(src), 20)
        self.assertEqual(len([x for x in src if x.endswith(".py")]), 19)
        self.assertIn(b'requires = ["setuptools>=68"]', src["pyproject.toml"])
        self.assertIn(b'build-backend = "setuptools.build_meta"', src["pyproject.toml"])
        for name in src:
            self.assertFalse("qwen" in name or "mock_" in name)
        self.assertEqual(len(_tar_bytes(src)), len(_tar_bytes(src)))

    def test_exact_recipe_uses_pinned_OE_PEP517_not_an_invented_installer(self):
        text = recipe("a" * 64)
        self.assertIn("inherit python_pep517\n", text)
        self.assertIn('DEPENDS += "python3-setuptools-native"', text)
        self.assertIn('LICENSE = "CLOSED"\n', text)
        self.assertIn('SRC_URI[kwipipy.sha256sum] = "' + "a" * 64 + '"', text)
        self.assertNotIn("do_install()", text)
        self.assertNotIn("systemd", text)
        self.assertNotIn("IMAGE_INSTALL", text)
        for name in RUNTIME:
            self.assertIn(name, text)
        self.assertNotIn("robot.move", text)

    def test_invalid_digest_cannot_be_declared(self):
        for digest in ("", "g" * 64, "a" * 63):
            with self.subTest(digest=digest), self.assertRaises(PackageRefused):
                recipe(digest)

    def test_no_unreviewed_source_paths_in_tarball(self):
        for name in ("../outside.py", "/absolute.py", "a/../../other.py",
                     "model.rknn"):
            with self.subTest(name=name), self.assertRaises(PackageRefused):
                _tar_bytes({name: b"content"})

    def test_deterministic_layer_and_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a" / LAYER, Path(tmp) / "b" / LAYER
            one, two = stage(ROOT, a), stage(ROOT, b)
            self.assertEqual(one, two)
            self.assertEqual(verify(ROOT, a), one)
            self.assertEqual(verify(ROOT, b), two)
            self.assertEqual(one["selected_python_modules"], 19)
            self.assertEqual(one["schema"], SCHEMA)
            self.assertEqual(one["runtime_deps"], sorted(RUNTIME))
            self.assertFalse(one["source_license_checked"])
            self.assertTrue(one["license_recipe_closed"])
            for k in ("bitbake_compiled", "bitbake_packaged", "rootfs_installed",
                      "robot_validated", "site_packages_yocto_parsed"):
                self.assertIs(one[k], False)
            self.assertEqual(
                {p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()},
                {p.relative_to(b).as_posix(): p.read_bytes() for p in b.rglob("*") if p.is_file()},
            )
            with self.assertRaises(PackageRefused):
                stage(ROOT, a)

    def test_tampered_archive_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            layer = Path(tmp) / LAYER
            stage(ROOT, layer)
            arc = layer / "recipes-kwipi/kwipi-companion/files" / SRC_NAME
            with arc.open("ab") as f:
                f.write(b"unsigned extra bytes")
            with self.assertRaises(PackageRefused):
                verify(ROOT, layer)

    def test_additional_module_or_suspicious_file_is_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            layer = Path(tmp) / LAYER
            stage(ROOT, layer)
            extra = layer / "recipes-kwipi/kwipi-companion/files/model.rknn"
            extra.write_bytes(b"fake model")
            with self.assertRaises(PackageRefused):
                verify(ROOT, layer)

    def test_edited_recipe_and_symlink_are_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            layer = Path(tmp) / LAYER
            stage(ROOT, layer)
            file = layer / RECIPE
            contents = file.read_text()
            file.write_text(contents.replace('LICENSE = "CLOSED"', 'LICENSE = "MIT"'))
            with self.assertRaises(PackageRefused):
                verify(ROOT, layer)
            file.unlink()
            file.symlink_to(layer / "conf/layer.conf")
            with self.assertRaises(PackageRefused):
                verify(ROOT, layer)

    def test_layer_exposes_only_python_recipe_without_boot_policy(self):
        layer = conf()
        self.assertIn('BBFILE_COLLECTIONS += "kwipipy"', layer)
        self.assertIn('LAYERSERIES_COMPAT_kwipipy = "wrynose"', layer)
        self.assertNotIn("bbappend", layer)

    def test_modified_n6_closure_is_not_silently_accepted(self):
        initial = selected_bytes(ROOT)
        fake = {x: v for x, v in initial.items() if x != "pyproject.toml"}
        fake["microduck_companion/new_side_effect.py"] = b"pass"
        with patch("scripts.per_p14b_yocto_python_layer.p14a.current_source",
                   return_value=fake):
            with self.assertRaises(PackageRefused):
                selected_bytes(ROOT)


if __name__ == "__main__":
    unittest.main()
