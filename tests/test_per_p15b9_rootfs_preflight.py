"""P15-B9-R read-only gate fixtures: no KAS, BitBake, WIC or rootfs."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from scripts import per_p15b9_rootfs_preflight as gate
from scripts import per_p15b6_cached_package_runner as cached


class RootfsPreflightFixture(TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.project = root / "project"
        self.project.mkdir()
        for rel in gate.ROOT_LAYERS:
            (self.project / rel).mkdir(parents=True)
        account = self.project / gate.ACCOUNT
        (account / gate.CONF).parent.mkdir(parents=True)
        (account / gate.CONF).write_text(gate.EXPECTED_CONF)
        (account / gate.APPEND).parent.mkdir(parents=True)
        (account / gate.APPEND).write_text(gate.EXPECTED_APPEND)
        self.cfg = cached.Config(self.project, root / "yocto",
                                 root / "work", root / "build",
                                 root / "scratch", "a" * 40)

    def _proof(self):
        return {"source_revision": "a" * 40, "oem_sha": cached.OEM,
                "yocto_sha": cached.YOCTO,
                "pinned_kas_repositories": 6, "existing_bitbake_cache": True}

    def test_readonly_preflight_no_scratch(self):
        with patch.object(gate.cached, "preflight", return_value=self._proof()), \
             patch.object(gate, "verify_p15a", return_value={"reviewed_source_unchanged": True}):
            result = gate.check(self.cfg)
        self.assertFalse(self.cfg.scratch.exists())
        self.assertFalse(result["rootfs_built"])
        self.assertFalse(result["bitbake_executed"])
        self.assertTrue(result["account_layer_exact"])

    def test_reject_account_mutations(self):
        with patch.object(gate.cached, "preflight", return_value=self._proof()), \
             patch.object(gate, "verify_p15a", return_value={"reviewed_source_unchanged": True}):
            file = self.project / gate.ACCOUNT / gate.APPEND
            file.write_text(gate.EXPECTED_APPEND.replace("/sbin/nologin", "/bin/bash"))
            with self.assertRaises(cached.Refused):
                gate.check(self.cfg)

    def test_reject_unreviewed_account_file(self):
        with patch.object(gate.cached, "preflight", return_value=self._proof()):
            (self.project / gate.ACCOUNT / "extra.bbappend").write_text("bad")
            with self.assertRaises(cached.Refused):
                gate.check(self.cfg)

    def test_reject_missing_layer(self):
        with patch.object(gate.cached, "preflight", return_value=self._proof()):
            (self.project / gate.ROOT_LAYERS[1]).rmdir()
            with self.assertRaises(cached.Refused):
                gate.check(self.cfg)

    def test_inherited_cache_rejection(self):
        with patch.object(gate.cached, "preflight", side_effect=cached.Refused("cache")):
            with self.assertRaises(cached.Refused):
                gate.check(self.cfg)
