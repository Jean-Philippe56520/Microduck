from __future__ import annotations
import tempfile
import unittest
from pathlib import Path

from scripts import per_p16_s2_rauc_rootfs_gate as gate


def cert(text):
    import base64
    encoded = base64.b64encode(text.encode()).decode()
    return f'-----BEGIN CERTIFICATE-----\n{encoded}\n-----END CERTIFICATE-----\n'

CONFIG = '''[system]
compatible=microduck-zero3
data-directory=/var/lib/robot/rauc
bootloader=uboot
bundle-formats=-plain
[keyring]
path=/usr/lib/rauc/keyring.pem
[slot.rootfs.0]
device=/dev/disk/by-partlabel/rootfs_a
type=ext4
bootname=A
[slot.rootfs.1]
device=/dev/disk/by-partlabel/rootfs_b
type=ext4
bootname=B
'''

class P16S2FixtureTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / 'build/tmp/work/aarch64/microduck-image-dev/1.0/rootfs'
        self.root.mkdir(parents=True)
        self.prod = cert('prod')
        self.dev = cert('dev')
        self.write('yocto/' + gate.BASE_RAUC + '/ca-prod.cert.pem', self.prod)
        self.write('yocto/' + gate.BASE_RAUC + '/ca-dev.cert.pem', self.dev)
        self.write('build/tmp/work/aarch64/microduck-image-dev/1.0/rootfs/usr/lib/rauc/ca-dev.cert.pem', self.dev)
        self.write('build/tmp/work/aarch64/microduck-image-dev/1.0/rootfs/usr/lib/rauc/keyring.pem', self.prod + self.dev)
        self.write('build/tmp/work/aarch64/microduck-image-dev/1.0/rootfs/usr/lib/rauc/system.conf', CONFIG)
        self.write('build/tmp/work/aarch64/microduck-image-dev/1.0/rootfs/usr/libexec/kwipi/health_probe.py', '# health\n')
        self.write('build/tmp/work/aarch64/microduck-image-dev/1.0/rootfs/usr/lib/systemd/system/kwipi-readonly-probe.service', '[Service]\nType=oneshot\n')
        self.write('build/tmp/work/aarch64/microduck-image-dev/1.0/rootfs/usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset', 'disable kwipi-readonly-probe.service\n')
        self.write('build/tmp/work/aarch64/microduck-image-dev/1.0/rootfs/etc/group', 'root:x:0:\nrobot:x:377:\n')

    def write(self, rel, value):
        p = self.base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value)
        return p

    def check(self):
        return gate.validate(self.base, check_git_pin=False)

    def stop(self, pattern):
        with self.assertRaisesRegex(gate.Stop, pattern):
            self.check()

    def test_positive_scoped(self):
        result = self.check()
        self.assertEqual(result['rootfs_pinned_ca_certificates'], 2)
        self.assertTrue(result['dev_ca_matches_pinned_source'])
        self.assertEqual(result['rauc_config_fields_verified'], 11)
        self.assertFalse(result['postinst_execution_causality_verified'])
        self.assertFalse(result['image_built'])

    def test_dev_source_changed(self):
        self.write('yocto/' + gate.BASE_RAUC + '/ca-dev.cert.pem', cert('fake'))
        self.stop('installed development CA differs')

    def test_installed_dev_ca_changed(self):
        p = self.root / 'usr/lib/rauc/ca-dev.cert.pem'
        p.write_text(cert('tampered'))
        self.stop('installed development CA differs')

    def test_missing_prod_ca_in_keyring(self):
        (self.root / 'usr/lib/rauc/keyring.pem').write_text(self.dev)
        self.stop('two pinned OEM CAs')

    def test_extra_ca_in_keyring(self):
        (self.root / 'usr/lib/rauc/keyring.pem').write_text(self.prod + self.dev + cert('extra'))
        self.stop('two pinned OEM CAs')

    def test_wrong_machine(self):
        p = self.root / 'usr/lib/rauc/system.conf'
        p.write_text(CONFIG.replace('microduck-zero3', 'microduck-beta'))
        self.stop('system.compatible')

    def test_wrong_bootloader(self):
        p = self.root / 'usr/lib/rauc/system.conf'
        p.write_text(CONFIG.replace('bootloader=uboot', 'bootloader=noop'))
        self.stop('system.bootloader')

    def test_wrong_slot(self):
        p = self.root / 'usr/lib/rauc/system.conf'
        p.write_text(CONFIG.replace('rootfs_b', 'rootfs_c'))
        self.stop('slot.rootfs.1.device')

    def test_wrong_bundle_format(self):
        p = self.root / 'usr/lib/rauc/system.conf'
        p.write_text(CONFIG.replace('bundle-formats=-plain', 'bundle-formats=plain'))
        self.stop('system.bundle-formats')

    def test_wrong_keyring_path(self):
        p = self.root / 'usr/lib/rauc/system.conf'
        p.write_text(CONFIG.replace('/usr/lib/rauc/keyring.pem', '/tmp/keyring.pem'))
        self.stop('keyring.path')

    def test_extra_config_section(self):
        p = self.root / 'usr/lib/rauc/system.conf'
        p.write_text(CONFIG + '[foreign]\na=b\n')
        self.stop('unexpected RAUC config section')

    def test_missing_robot_group(self):
        (self.root / 'etc/group').write_text('root:x:0:\n')
        self.stop('expected robot group missing')

    def test_world_writable_probe(self):
        p = self.root / 'usr/libexec/kwipi/health_probe.py'
        p.chmod(0o666)
        self.stop('unsafe permission bits')

    def test_symlink_keyring(self):
        p = self.root / 'usr/lib/rauc/keyring.pem'
        p.unlink()
        p.symlink_to('/etc/passwd')
        self.stop('symlink')

    def test_missing_rootfs(self):
        (self.root / 'usr/lib/rauc/keyring.pem').unlink()
        self.stop('file missing')

    def test_unparseable_pem(self):
        p = self.root / 'usr/lib/rauc/keyring.pem'
        p.write_text('no PEM here')
        self.stop('no PEM')

if __name__ == '__main__':
    unittest.main()
