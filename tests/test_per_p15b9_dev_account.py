"""P15-B9: source-only, negative-test guard for a DEV-only locked identity."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LAYER = ROOT / "yocto/meta-kwipi-p15-account"
CONF = "conf/layer.conf"
APPEND = "recipes-core/images/microduck-image-dev.bbappend"

EXPECTED_CONF = (
    'BBPATH .= ":''\x24{LAYERDIR}"\n'
    'BBFILES += "''\x24{LAYERDIR}/recipes-*/*/*.bbappend"\n'
    'BBFILE_COLLECTIONS += "kwipiaccount"\n'
    'BBFILE_PATTERN_kwipiaccount := "^''\x24{LAYERDIR}/"\n'
    'BBFILE_PRIORITY_kwipiaccount = "24"\n'
    'LAYERVERSION_kwipiaccount = "1"\n'
    'LAYERDEPENDS_kwipiaccount = "core microduck"\n'
    'LAYERSERIES_COMPAT_kwipiaccount = "wrynose"\n'
)
EXPECTED_APPEND = (
    "# P15-B9: isolated, locked service identity for the optional DEV image only.\n"
    "# Preserve OEM microduck operator and the shipping image untouched.\n"
    "# The OEM image already inherits extrausers. No service is enabled here.\n"
    "EXTRA_USERS_PARAMS:append = \" groupadd -r kwipi; "
    "useradd -r -g kwipi -M -s /sbin/nologin -p '!' kwipi;\"\n"
)


def verify(layer: Path, dev_recipe: str, ship_recipe: str) -> None:
    """Reject unreviewed paths and any source recipe change; no BitBake attested."""
    if layer.is_symlink() or not layer.is_dir():
        raise ValueError("layer missing or symlink")
    names = {
        p.relative_to(layer).as_posix()
        for p in layer.rglob("*") if p.is_file() or p.is_symlink()
    }
    if names != {CONF, APPEND}:
        raise ValueError("unexpected source")
    for rel, expected in ((CONF, EXPECTED_CONF), (APPEND, EXPECTED_APPEND)):
        p = layer / rel
        if p.is_symlink() or p.read_text(encoding="utf-8") != expected:
            raise ValueError("source drift")
    if "inherit rockchip-image extrausers" not in ship_recipe:
        raise ValueError("OEM extrausers inheritance absent")
    if 'EXTRA_USERS_PARAMS = "useradd -m -s /bin/bash -G robot' not in ship_recipe:
        raise ValueError("OEM operator account declaration changed")
    if "require recipes-core/images/microduck-image.bb" not in dev_recipe:
        raise ValueError("OEM DEV recipe no longer imports shipping")


class AccountSourceGate(unittest.TestCase):
    def test_exact_dev_only_source(self):
        self.assertEqual((LAYER / CONF).read_text(), EXPECTED_CONF)
        self.assertEqual((LAYER / APPEND).read_text(), EXPECTED_APPEND)
        self.assertEqual({
            p.relative_to(LAYER).as_posix() for p in LAYER.rglob("*") if p.is_file()
        }, {CONF, APPEND})

    def test_nominal_and_negatives(self):
        dev = "require recipes-core/images/microduck-image.bb"
        ship = ('inherit rockchip-image extrausers\n'
                'EXTRA_USERS_PARAMS = "useradd -m -s /bin/bash -G robot,sudo microduck;"')
        verify(LAYER, dev, ship)
        for changed in (
            EXPECTED_APPEND.replace("/sbin/nologin", "/bin/bash"),
            EXPECTED_APPEND.replace("-p '!'", "-p 'password'"),
            EXPECTED_APPEND.replace("-M ", "-m "),
            EXPECTED_APPEND.replace("-g kwipi ", "-G robot -g kwipi "),
            EXPECTED_APPEND.replace(":append", " ="),
        ):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                (root / "conf").mkdir()
                (root / "recipes-core/images").mkdir(parents=True)
                (root / CONF).write_text(EXPECTED_CONF)
                (root / APPEND).write_text(changed)
                with self.assertRaises(ValueError):
                    verify(root, dev, ship)

    def test_wrong_recipe_or_added_shipping_file_refused(self):
        dev = "require recipes-core/images/microduck-image.bb"
        ship = ('inherit rockchip-image extrausers\n'
                'EXTRA_USERS_PARAMS = "useradd -m -s /bin/bash -G robot microduck;"')
        for d, s in (("not-a-dev-image", ship), (dev, "inherit core-image")):
            with self.assertRaises(ValueError):
                verify(LAYER, d, s)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "conf").mkdir()
            (root / "recipes-core/images").mkdir(parents=True)
            (root / CONF).write_text(EXPECTED_CONF)
            (root / APPEND).write_text(EXPECTED_APPEND)
            (root / "recipes-core/images/microduck-image.bbappend").write_text(
                "EXTRA_USERS_PARAMS:append = \" useradd kwipi;\"\n")
            with self.assertRaises(ValueError):
                verify(root, dev, ship)


if __name__ == "__main__":
    unittest.main()
