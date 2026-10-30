"""PER-P14B: deterministic opt-in Yocto Python package from the audited P14A slice.

No modification of the OEM repo, its images, P12 layer, motors, user files,
SQLite state, models, systemd units, RAUC configuration or signing keys.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile

from scripts import per_p14a_embedded_wheel as p14a

LAYER = "meta-kwipi-python"
SCHEMA = "kwipi-p14b-yocto-python-source-package-v1"
YOCTO_SHA = "1ee58387810cebb67ae0d634c351d95024483bce"
OE_SHA = "ae5a301091f5b0574ea7444aab40b309b6d9f3f2"
SRC_NAME = "kwipi-companion-p14a-0.2.0a1.tar.gz"
RECIPE = "recipes-kwipi/kwipi-companion/kwipi-companion_0.2.0a1.bb"
RUNTIME = frozenset({
    "python3-core", "python3-io", "python3-json", "python3-math",
    "python3-netclient", "python3-sqlite3", "python3-threading",
})


class PackageRefused(ValueError):
    """Source closure or packaging candidate differs from prior review."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def repo_sha(root: Path) -> str:
    try:
        sha = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        raise PackageRefused("source checkout has no verified HEAD") from e
    if len(sha) != 40 or any(x not in "0123456789abcdef" for x in sha):
        raise PackageRefused("source HEAD is not a stable commit SHA")
    return sha


def selected_bytes(root: Path) -> dict[str, bytes]:
    files = p14a.current_source(root)
    if set(files) != p14a.SELECTED or len(files) != 19:
        raise PackageRefused("N6+readonly P14A allowlist changed")
    meta = p14a.METADATA.encode("utf-8")
    if b"microduck-companion-embedded-candidate" not in meta:
        raise PackageRefused("unexpected P14A distribution identity")
    return {**files, "pyproject.toml": meta}


def _tar_bytes(entries: dict[str, bytes]) -> bytes:
    blob = io.BytesIO()
    with gzip.GzipFile(fileobj=blob, filename="", mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
            for rel in sorted(entries):
                if (rel.startswith("/") or ".." in Path(rel).parts
                        or Path(rel).as_posix() != rel or not rel.endswith((".py", ".toml"))):
                    raise PackageRefused("unsafe Python package source member")
                data = entries[rel]
                member = tarfile.TarInfo(name=rel)
                member.uid = member.gid = member.mtime = 0
                member.mode = 0o644
                member.size = len(data)
                tar.addfile(member, io.BytesIO(data))
    return blob.getvalue()


def conf() -> str:
    return (
        'BBPATH .= ":${LAYERDIR}"\n'
        'BBFILES += "${LAYERDIR}/recipes-*/*/*.bb"\n'
        'BBFILE_COLLECTIONS += "kwipipy"\n'
        'BBFILE_PATTERN_kwipipy := "^${LAYERDIR}/"\n'
        'BBFILE_PRIORITY_kwipipy = "22"\n'
        'LAYERVERSION_kwipipy = "1"\n'
        'LAYERDEPENDS_kwipipy = "core"\n'
        'LAYERSERIES_COMPAT_kwipipy = "wrynose"\n'
    )


def recipe(archive_sha: str) -> str:
    if len(archive_sha) != 64 or any(x not in "0123456789abcdef" for x in archive_sha):
        raise PackageRefused("invalid Python source archive checksum")
    modules = sorted(Path(p).name for p in p14a.SELECTED)
    if (len(modules) != 19 or len(set(modules)) != 19
            or any(p != "microduck_companion/" + Path(p).name
                   or not p.endswith(".py") for p in p14a.SELECTED)):
        raise PackageRefused("P14A source paths are no longer flat/strict Python modules")
    return (
        'SUMMARY = "Kwipi Companion read-only Python cognitive candidate"\n'
        'DESCRIPTION = "Only 19 audited P14A Python modules, no motors or model."\n'
        'HOMEPAGE = "https://github.com/Jean-Philippe56520/Microduck"\n'
        '# No explicit source redistribution license: private development only.\n'
        'LICENSE = "CLOSED"\n'
        '# The wheel was built/checked in P14A. Install the identical pure-Python '
        'sources here without rebuilding native setuptools/Python toolchains.\n'
        'inherit allarch python3-dir\n'
        'SRC_URI = "file://' + SRC_NAME + ';subdir=${BP};name=kwipipy"\n'
        'SRC_URI[kwipipy.sha256sum] = "' + archive_sha + '"\n'
        '# Default pinned OE S is ${UNPACKDIR}/${BP}; never use WORKDIR in S.\n'
        'RDEPENDS:${PN} += "' + " ".join(sorted(RUNTIME)) + '"\n'
        'do_install() {\n'
        '    install -d "${D}${PYTHON_SITEPACKAGES_DIR}/microduck_companion"\n'
        '    for module in ' + " ".join(modules) + '; do\n'
        '        install -m 0644 "${S}/microduck_companion/$module" '
        '"${D}${PYTHON_SITEPACKAGES_DIR}/microduck_companion/$module"\n'
        '    done\n'
        '}\n'
        'FILES:${PN} += "${PYTHON_SITEPACKAGES_DIR}/microduck_companion"\n'
        '# NOT added to any image. No service, entry point, DB, model or auto-start.\n'
    )


def staged_files(root: Path) -> tuple[dict[str, bytes], dict]:
    src = selected_bytes(root)
    tar = _tar_bytes(src)
    sha = _sha(tar)
    files = {
        "conf/layer.conf": conf().encode("utf-8"),
        RECIPE: recipe(sha).encode("utf-8"),
        "recipes-kwipi/kwipi-companion/files/" + SRC_NAME: tar,
    }
    metadata = {
        "schema": SCHEMA,
        "status": "yocto_python_layer_source_candidate_not_bitbake",
        "source_revision": repo_sha(root),
        "oem_yocto_sha": YOCTO_SHA,
        "oecore_sha": OE_SHA,
        "source_archive_sha256": sha,
        "source_sha256": {p: _sha(src[p]) for p in sorted(src)},
        "selected_python_modules": 19,
        "distribution": p14a.DIST_NAME,
        "distribution_version": p14a.VERSION,
        "runtime_deps": sorted(RUNTIME),
        "source_license_checked": False,
        "license_recipe_closed": True,
        "site_packages_yocto_parsed": False,
        "bitbake_compiled": False,
        "bitbake_packaged": False,
        "rootfs_installed": False,
        "robot_validated": False,
        "motor_commands_issued": 0,
    }
    files["kwipi-python-layer-provenance.json"] = (
        json.dumps(metadata, sort_keys=True, indent=2) + "\n").encode("utf-8")
    return files, metadata


def stage(root: Path, out: Path) -> dict:
    if out.exists() or out.is_symlink():
        raise PackageRefused("output layer exists")
    root = root.resolve(strict=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    files, expected = staged_files(root)
    with tempfile.TemporaryDirectory(prefix="kwipi-p14b-", dir=out.parent) as d:
        work = Path(d) / LAYER
        for name, data in files.items():
            file = work / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        verify(root, work)
        work.rename(out)
    return expected


def verify(root: Path, layer: Path) -> dict:
    if layer.is_symlink() or not layer.is_dir():
        raise PackageRefused("layer absent or symlinked")
    expected_files, expected = staged_files(root.resolve(strict=True))
    actual_names = {
        p.relative_to(layer).as_posix()
        for p in layer.rglob("*") if p.is_file() or p.is_symlink()
    }
    if actual_names != set(expected_files):
        raise PackageRefused("layer has missing/unreviewed files")
    for rel, value in expected_files.items():
        p = layer / rel
        if p.is_symlink() or not p.is_file() or p.read_bytes() != value:
            raise PackageRefused("source/recipe/provenance mismatch: " + rel)
    with tarfile.open(layer / "recipes-kwipi/kwipi-companion/files" / SRC_NAME, "r:gz") as t:
        members = t.getmembers()
        if ({m.name for m in members} != set(expected["source_sha256"])
                or len(members) != len(expected["source_sha256"])
                or any(not m.isfile() or m.issym() or m.islnk() for m in members)):
            raise PackageRefused("unexpected Python source tar contents")
    return expected


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("stage")
    a.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    a.add_argument("--output", type=Path, required=True)
    b = sub.add_parser("verify")
    b.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    b.add_argument("--layer", type=Path, required=True)
    args = p.parse_args()
    try:
        result = (stage(args.root, args.output) if args.command == "stage"
                  else verify(args.root, args.layer))
    except (PackageRefused, ValueError, OSError, KeyError,
            tarfile.TarError) as e:
        p.exit(1, f"PER-P14B STOP: {e}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
