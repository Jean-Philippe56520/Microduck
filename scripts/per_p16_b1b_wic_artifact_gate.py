from pathlib import Path
import hashlib
import struct
import zlib

EXPECTED = {
    'v_storage': (7168 * 512, 256 * 1024),
    'uboot_env': (8128 * 512, 32 * 1024),
    'uboot': (8 * 1024**2, 4 * 1024**2),
    'boot': (16 * 1024**2, 32 * 1024**2),
    'boot_b': (48 * 1024**2, 32 * 1024**2),
    'rootfs_a': (80 * 1024**2, 2048 * 1024**2),
    'rootfs_b': (2128 * 1024**2, 2048 * 1024**2),
    'data': (4176 * 1024**2, 8192 * 1024**2),
}

class AuditStop(Exception):
    pass

def audit(base: Path, calculate_hash=True):
    roots = sorted(x for x in (base / 'build/tmp/work').glob('*/microduck-image-dev/*/rootfs') if x.is_dir() and not x.is_symlink())
    if len(roots) != 1:
        raise AuditStop(f'Expected one DEV rootfs, found {len(roots)}')
    workdir = roots[0].parent
    stage = workdir / 'deploy-microduck-image-dev-image-complete'
    print('WORKDIR:', workdir)
    print('STAGE_DIR:', stage)
    if not stage.is_dir():
        print('RELATED_DIRS:', [p.name for p in workdir.glob('deploy-*')][:15])
        raise AuditStop('staging directory not found')
    names = sorted(stage.glob('*.wic'))
    print('WIC_MATCHES:', len(names))
    paths = set()
    for p in names:
        try:
            real = p.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise AuditStop(f'broken symlink or path: {p.name}: {exc}') from exc
        print('WIC_ENTRY:', p.name, 'SYMLINK' if p.is_symlink() else 'REGULAR', '=>', real.name)
        if not real.is_file() or real.parent != stage.resolve():
            raise AuditStop(f'WIC entry does not resolve to a regular file in stage: {p}')
        paths.add(real)
    if len(paths) != 1:
        other_dir = base / 'build/tmp/deploy/images'
        if other_dir.is_dir():
            found = list(other_dir.glob('*/microduck-image-dev*.wic'))[:10]
            print('DEPLOY_CANDIDATES:', [str(p) for p in found])
        raise AuditStop(f'expected one unique physical WIC; found {len(paths)}')
    wic = paths.pop()
    if wic.is_symlink() or not wic.name.startswith('microduck-image-dev'):
        raise AuditStop('unexpected physical WIC filename or symlink')
    size = wic.stat().st_size
    limit = max(s + n for s, n in EXPECTED.values())
    if size < limit or size > limit + 128 * 1024**2:
        raise AuditStop(f'unexpected WIC size: {size}, minimum {limit}')
    print('WIC_BYTES:', size)
    with wic.open('rb') as f:
        f.seek(512)
        header = f.read(512)
        if len(header) != 512 or header[:8] != b'EFI PART':
            raise AuditStop('missing GPT primary header')
        header_size = struct.unpack_from('<I', header, 12)[0]
        if not 92 <= header_size <= 512:
            raise AuditStop('invalid GPT header size')
        saved_crc = struct.unpack_from('<I', header, 16)[0]
        tmp = bytearray(header[:header_size]); tmp[16:20] = b'\0' * 4
        if zlib.crc32(tmp) != saved_crc:
            raise AuditStop('GPT header CRC mismatch')
        table_lba, count, entry_size, table_crc = struct.unpack_from('<QIII', header, 72)
        if table_lba < 2 or not 1 <= count <= 1024 or not 128 <= entry_size <= 512:
            raise AuditStop('unexpected GPT entry table dimensions')
        if count * entry_size > 512 * 1024:
            raise AuditStop('oversized GPT entry table')
        f.seek(table_lba * 512)
        table = f.read(count * entry_size)
        if len(table) != count * entry_size or zlib.crc32(table) != table_crc:
            raise AuditStop('GPT partition table CRC mismatch')
    actual = {}
    for i in range(count):
        entry = table[i * entry_size:(i + 1) * entry_size]
        if entry[:16] == b'\0' * 16:
            continue
        first, last = struct.unpack_from('<QQ', entry, 32)
        name = entry[56:min(128, entry_size)].decode('utf-16-le').rstrip('\0')
        if name in actual or last < first:
            raise AuditStop('duplicate or malformed GPT partition')
        actual[name] = (first * 512, (last - first + 1) * 512)
    print('GPT_PARTITIONS:', len(actual))
    for name, expected in EXPECTED.items():
        print('GPT_PART:', name, actual.get(name))
        if actual.get(name) != expected:
            raise AuditStop(f'GPT mismatch in {name}: expected {expected}, got {actual.get(name)}')
    if set(actual) != set(EXPECTED):
        raise AuditStop(f'unexpected GPT labels: {sorted(set(actual) - set(EXPECTED))}')
    print('P16_B1B_STAGE_GPT: PASS')
    if calculate_hash:
        sha = hashlib.sha256()
        with wic.open('rb') as f:
            for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
                sha.update(chunk)
        print('WIC_SHA256:', sha.hexdigest())
        print('P16_B1B_SHA256: PASS')
    return wic

if __name__ == '__main__':
    try:
        audit(Path.cwd())
    except (AuditStop, OSError, UnicodeError) as exc:
        raise SystemExit('P16_B1B_AUDIT_STOP: ' + str(exc))
