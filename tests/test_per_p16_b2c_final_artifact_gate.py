import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from scripts.per_p16_b2c_final_artifact_gate import audit, AuditStop, IMAGE_STEM, ALIAS_STEM, SUFFIXES

class FinalArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.stage = self.base / 'build/tmp/work/microduck_zero3-poky-linux/microduck-image-dev/1.0/deploy-microduck-image-dev-image-complete'
        self.final = self.base / 'build/tmp/deploy/images/microduck-zero3'
        (self.stage.parent / 'rootfs').mkdir(parents=True)
        self.stage.mkdir()
        self.final.mkdir(parents=True)
        self.raw = bytes(4096 * 3)
        self.zst = b'test-zstd-stream'
        self.hash = hashlib.sha256(self.raw).hexdigest()
        zst_hash = hashlib.sha256(self.zst).hexdigest()
        self.content = {
            '.wic': self.raw,
            '.wic.zst': self.zst,
            '.wic.zst.sha256sum': (zst_hash + '  ' + IMAGE_STEM + '.wic.zst\n').encode(),
            '.wic.bmap': b'<bmap version="2.0"><ImageSize>12288</ImageSize><BlockSize>4096</BlockSize><BlocksCount>3</BlocksCount><MappedBlocksCount>2</MappedBlocksCount><BlockMap><Range>0</Range><Range>2</Range></BlockMap></bmap>',
        }
        for d in (self.stage, self.final):
            for suffix, contents in self.content.items():
                (d / (IMAGE_STEM + suffix)).write_bytes(contents)
                (d / (ALIAS_STEM + suffix)).symlink_to(IMAGE_STEM + suffix)

    def check(self):
        return audit(self.base, expected_bytes=len(self.raw), expected_sha256=self.hash)

    def test_positive(self):
        report = self.check()
        self.assertEqual(report['physical_files'], 4)
        self.assertTrue(report['stage_final_zst_sha256_equal'])
        self.assertEqual(report['bmap']['mapped_blocks'], 2)
        self.assertFalse(report['robot_boot_verified'])

    def test_missing_final(self):
        (self.final / (IMAGE_STEM + '.wic.zst')).unlink()
        with self.assertRaisesRegex(AuditStop, 'not a regular|unexpected release entries'):
            self.check()

    def test_final_alias_wrong(self):
        p = self.final / (ALIAS_STEM + '.wic')
        p.unlink(); p.symlink_to(IMAGE_STEM + '.wic.zst')
        with self.assertRaisesRegex(AuditStop, 'wrong symlink target'):
            self.check()

    def test_extra_release_file(self):
        (self.final / 'microduck-image-dev-microduck-zero3.rootfs-older.wic').write_bytes(b'other')
        with self.assertRaisesRegex(AuditStop, 'unexpected release entries'):
            self.check()

    def test_bad_zst_checksum(self):
        (self.final / (IMAGE_STEM + '.wic.zst')).write_bytes(b'B' * len(self.zst))
        with self.assertRaisesRegex(AuditStop, 'ZST SHA-256 mismatch'):
            self.check()

    def test_bad_checksum_filename(self):
        p = self.final / (IMAGE_STEM + '.wic.zst.sha256sum')
        p.write_text('a' * 64 + '  evil.wic.zst\n')
        (self.stage / p.name).write_text('a' * 64 + '  evil.wic.zst\n')
        with self.assertRaisesRegex(AuditStop, 'checksum filename'):
            self.check()

    def test_stage_final_mismatch(self):
        (self.stage / (IMAGE_STEM + '.wic.zst')).write_bytes(b'another-zstd-test')
        with self.assertRaisesRegex(AuditStop, 'size differs'):
            self.check()

    def test_bad_bmap_size(self):
        for d in (self.stage, self.final):
            p=d / (IMAGE_STEM+'.wic.bmap')
            p.write_bytes(self.content['.wic.bmap'].replace(b'12288',b'99999'))
        with self.assertRaisesRegex(AuditStop, 'bmap image size'):
            self.check()

    def test_bad_bmap_range(self):
        for d in (self.stage, self.final):
            p=d / (IMAGE_STEM+'.wic.bmap')
            p.write_bytes(self.content['.wic.bmap'].replace(b'<Range>2</Range>',b'<Range>3</Range>'))
        with self.assertRaisesRegex(AuditStop, 'bmap overlapping or out-of-range'):
            self.check()

    def test_bad_raw_sha(self):
        (self.final / (IMAGE_STEM+'.wic')).write_bytes(b'1'*len(self.raw))
        with self.assertRaisesRegex(AuditStop, 'raw WIC differs'):
            self.check()

    def test_missing_robot_rootfs(self):
        (self.stage.parent / 'rootfs').rmdir()
        with self.assertRaisesRegex(AuditStop, 'one existing DEV rootfs'):
            self.check()

    def test_compressed_stage_bytes_different(self):
        self.zst = b'C' * len(self.zst)
        (self.stage / (IMAGE_STEM + '.wic.zst')).write_bytes(self.zst)
        with self.assertRaisesRegex(AuditStop, 'staged ZST SHA-256 mismatch'):
            self.check()

if __name__ == '__main__':
    unittest.main()
