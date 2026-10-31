"""P16-S2: inspect DEV rootfs RAUC trust and P15A file modes, without installing."""
from __future__ import annotations
import configparser
import hashlib
import json
import re
import ssl
import stat
import subprocess
from pathlib import Path

YOCTO_PIN = '1ee58387810cebb67ae0d634c351d95024483bce'
PEM_RE = re.compile(rb'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', re.S)
BASE_RAUC = 'meta-microduck/recipes-core/rauc/files'

class Stop(ValueError):
    pass

def fail(reason: str):
    raise Stop(reason)

def safe_file(root: Path, rel: str) -> Path:
    cur = root
    for comp in Path(rel).parts:
        cur = cur / comp
        if cur.is_symlink():
            fail('symlink in audited path: ' + rel)
    if not cur.is_file():
        fail('file missing: ' + rel)
    if not cur.resolve().is_relative_to(root.resolve()):
        fail('path escapes root: ' + rel)
    return cur

def cert_fingerprints(path: Path) -> list[str]:
    content = path.read_bytes()
    blocks = PEM_RE.findall(content)
    if not blocks:
        fail('no PEM certificates in: ' + path.name)
    try:
        der = [ssl.PEM_cert_to_DER_cert(x.decode('ascii')) for x in blocks]
    except (ValueError, UnicodeError) as exc:
        raise Stop('invalid PEM: ' + path.name) from exc
    return [hashlib.sha256(x).hexdigest() for x in der]

def validate(base: Path, *, check_git_pin: bool = True) -> dict:
    base = base.resolve(strict=True)
    yocto = base / 'yocto'
    if check_git_pin:
        try:
            rev = subprocess.check_output(['git', '-C', str(yocto), 'rev-parse', 'HEAD'], text=True).strip()
        except (OSError, subprocess.CalledProcessError) as exc:
            raise Stop('cannot read pinned Yocto revision') from exc
        if rev != YOCTO_PIN:
            fail('Yocto pin changed')
    work = base / 'build/tmp/work'
    roots = [p for p in work.glob('*/microduck-image-dev/*/rootfs')
             if p.is_dir() and not p.is_symlink()]
    if len(roots) != 1:
        fail('expected one existing DEV rootfs')
    root = roots[0].resolve()
    source_prod = safe_file(yocto, BASE_RAUC + '/ca-prod.cert.pem')
    source_dev = safe_file(yocto, BASE_RAUC + '/ca-dev.cert.pem')
    installed_dev = safe_file(root, 'usr/lib/rauc/ca-dev.cert.pem')
    keyring = safe_file(root, 'usr/lib/rauc/keyring.pem')
    prod = cert_fingerprints(source_prod)
    dev = cert_fingerprints(source_dev)
    installed = cert_fingerprints(installed_dev)
    bundle = cert_fingerprints(keyring)
    if len(prod) != 1 or len(dev) != 1 or prod == dev:
        fail('OEM CA source set unexpected')
    if installed != dev:
        fail('installed development CA differs from pinned OEM source')
    if len(bundle) != 2 or set(bundle) != set(prod + dev):
        fail('DEV keyring does not contain exactly the two pinned OEM CAs')
    cfg_file = safe_file(root, 'usr/lib/rauc/system.conf')
    cfg = configparser.ConfigParser(interpolation=None)
    try:
        cfg.read_string(cfg_file.read_text(encoding='utf-8'))
    except (configparser.Error, UnicodeError) as exc:
        raise Stop('RAUC system.conf unparseable') from exc
    expected = {
        ('system', 'compatible'): 'microduck-zero3',
        ('system', 'data-directory'): '/var/lib/robot/rauc',
        ('system', 'bootloader'): 'uboot',
        ('system', 'bundle-formats'): '-plain',
        ('keyring', 'path'): '/usr/lib/rauc/keyring.pem',
        ('slot.rootfs.0', 'device'): '/dev/disk/by-partlabel/rootfs_a',
        ('slot.rootfs.0', 'type'): 'ext4',
        ('slot.rootfs.0', 'bootname'): 'A',
        ('slot.rootfs.1', 'device'): '/dev/disk/by-partlabel/rootfs_b',
        ('slot.rootfs.1', 'type'): 'ext4',
        ('slot.rootfs.1', 'bootname'): 'B',
    }
    for (section, key), want in expected.items():
        if cfg.get(section, key, fallback=None) != want:
            fail('RAUC system.conf mismatched: ' + section + '.' + key)
    if set(cfg.sections()) != {'system', 'keyring', 'slot.rootfs.0', 'slot.rootfs.1'}:
        fail('unexpected RAUC config section')
    checked = ['usr/libexec/kwipi/health_probe.py',
               'usr/lib/systemd/system/kwipi-readonly-probe.service',
               'usr/lib/systemd/system-preset/98-kwipi-readonly-probe.preset',
               'usr/lib/rauc/system.conf', 'usr/lib/rauc/keyring.pem']
    for rel in checked:
        p = safe_file(root, rel)
        mode = stat.S_IMODE(p.stat().st_mode)
        if mode & (stat.S_IWGRP | stat.S_IWOTH | stat.S_ISUID | stat.S_ISGID):
            fail('unsafe permission bits in: ' + rel)
    group = safe_file(root, 'etc/group').read_text(encoding='utf-8')
    groups = [line.split(':') for line in group.splitlines() if line and not line.startswith('#')]
    if not any(len(fields) >= 4 and fields[0] == 'robot' and fields[2].isdigit() for fields in groups):
        fail('expected robot group missing in installed rootfs')
    return {
        'status': 'p16_s2_rauc_pinned_ca_and_rootfs_mode_gate_pass',
        'rootfs_pinned_ca_certificates': 2,
        'dev_ca_matches_pinned_source': True,
        'rauc_config_fields_verified': len(expected),
        'rootfs_files_checked_for_unsafe_modes': len(checked),
        'robot_group_present_in_rootfs': True,
        'target_uid_gid_verified': False,
        'postinst_execution_causality_verified': False,
        'all_package_scriptlets_audited': False,
        'robot_socket_readonly_acl_verified': False,
        'license_redistribution_approved': False,
        'image_built': False,
        'rauc_bundle_signed_verified': False,
        'robot_validated': False,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    a = parser.parse_args()
    try:
        result = validate(a.base)
    except (Stop, OSError, ValueError) as exc:
        parser.exit(1, 'P16_S2_STOP: ' + str(exc) + '\n')
    print(json.dumps(result, sort_keys=True, separators=(',', ':')))

if __name__ == '__main__':
    main()
