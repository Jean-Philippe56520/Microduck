import unittest
import tempfile
import zlib
import struct
from pathlib import Path
from scripts.per_p16_b1b_wic_artifact_gate import audit, EXPECTED, AuditStop

class TestP16WIC(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.base=Path(td.name)
        self.work=self.base/'build/tmp/work/microduck-zero3/microduck-image-dev/1.0'
        (self.work/'rootfs').mkdir(parents=True)
        self.stage=self.work/'deploy-microduck-image-dev-image-complete'
        self.stage.mkdir()
        self.file=self.stage/'microduck-image-dev-microduck-zero3-20261031.wic'
        self.create_wic()
    def create_wic(self, bad_partition=False):
        end=max(a+b for a,b in EXPECTED.values())
        with self.file.open('wb') as f:
            f.truncate(end+4096)
            table=bytearray(128*128)
            for i,(name,(start,length)) in enumerate(EXPECTED.items()):
                off=i*128
                table[off:off+16]=b'\x01'*16
                struct.pack_into('<QQ',table,off+32,start//512+(1 if bad_partition and i==0 else 0),(start+length)//512-1)
                encoded=name.encode('utf-16-le')
                table[off+56:off+56+len(encoded)]=encoded
            h=bytearray(512)
            h[0:8]=b'EFI PART'
            struct.pack_into('<I',h,8,0x10000)
            struct.pack_into('<I',h,12,92)
            struct.pack_into('<Q',h,24,1)
            struct.pack_into('<Q',h,32,(end+4096)//512-1)
            struct.pack_into('<Q',h,72,2)
            struct.pack_into('<I',h,80,128)
            struct.pack_into('<I',h,84,128)
            struct.pack_into('<I',h,88,zlib.crc32(table))
            struct.pack_into('<I',h,16,zlib.crc32(h[:92]))
            f.seek(512);f.write(h)
            f.seek(1024);f.write(table)
    def test_ok_one_file(self):
        self.assertEqual(audit(self.base,False),self.file)
    def test_ok_one_file_and_link(self):
        (self.stage/'microduck-image-dev-microduck-zero3.wic').symlink_to(self.file.name)
        self.assertEqual(audit(self.base,False),self.file)
    def test_missing_stage(self):
        self.file.unlink();self.stage.rmdir()
        with self.assertRaisesRegex(AuditStop,'staging directory'):
            audit(self.base,False)
    def test_two_real_files(self):
        (self.stage/'microduck-image-dev-other.wic').touch()
        with self.assertRaisesRegex(AuditStop,'two|found 2'):
            audit(self.base,False)
    def test_broken_link(self):
        (self.stage/'microduck-image-dev-alias.wic').symlink_to('nonexistent.wic')
        with self.assertRaisesRegex(AuditStop,'broken symlink'):
            audit(self.base,False)
    def test_bad_partition(self):
        self.create_wic(bad_partition=True)
        with self.assertRaisesRegex(AuditStop,'GPT mismatch'):
            audit(self.base,False)
    def test_corrupt_crc(self):
        with self.file.open('r+b') as f:
            f.seek(512+16);f.write(b'\0\0\0\0')
        with self.assertRaisesRegex(AuditStop,'header CRC'):
            audit(self.base,False)
    def test_missing_wic(self):
        self.file.unlink()
        with self.assertRaisesRegex(AuditStop,'found 0'):
            audit(self.base,False)
    def test_incorrect_size(self):
        with self.file.open('r+b') as f:f.truncate(1024)
        with self.assertRaisesRegex(AuditStop,'size'):
            audit(self.base,False)
if __name__=='__main__': unittest.main()
