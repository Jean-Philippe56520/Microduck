"""P15-B6: deterministic add-on to the 19-module P14A/P14B package.

HOST-only mock-fixture lifecycle, NOT an OEM daemon or an activated service.
No model, motor, camera, ACL, SQLite state or Yocto image is changed.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile

from scripts import n6_no_mock_wheel as n6
from scripts import per_p14a_embedded_wheel as p14a
from scripts import per_p14b_yocto_python_layer as p14b

LAYER = "meta-kwipi-passive-fixture"
SCHEMA = "p15b6-passive-closure-v1"
PN, PV = "kwipi-passive-fixture", "0.1.0"
SRC_NAME = f"{PN}-{PV}.tar.gz"
RECIPE = f"recipes-kwipi/{PN}/{PN}_{PV}.bb"
ARCHIVE = f"recipes-kwipi/{PN}/files/{SRC_NAME}"
PROVENANCE = "kwipi-passive-source-provenance.json"
ADDON = frozenset({
    "microduck_companion/offline_resource_budget.py",
    "microduck_companion/passive_resilience.py",
    "microduck_companion/passive_media_router.py",
    "microduck_companion/passive_media_fixture_reader.py",
    "microduck_companion/passive_fixture_runtime.py",
})
OPTIONAL = frozenset({
    "microduck_companion/mock_cycles.py",
    "microduck_companion/mock_social_cues.py",
})


class Refused(ValueError):
    """Fail closed on unreviewed dependencies or changed source bytes."""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def addon_files(root: Path) -> dict[str, bytes]:
    if len(ADDON) != 5 or ADDON & p14a.SELECTED or n6.OMITTED != OPTIONAL:
        raise Refused("only five additional files, no duplicate/mock engine")
    found = {}
    for name in sorted(ADDON):
        path = root / name
        if (path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to(root)
                or any(parent.is_symlink() for parent in path.parents
                       if parent != root and parent.is_relative_to(root))):
            raise Refused("missing/symlinked source: " + name)
        raw = path.read_bytes()
        try:
            ast.parse(raw.decode("utf-8"), filename=name)
        except (UnicodeError, SyntaxError) as exc:
            raise Refused("invalid Python source") from exc
        found[name] = raw
    return found


def audit_imports(src: dict[str, bytes]) -> tuple[str, ...]:
    """Static check of package imports, including imports inside functions.

    The two historical optional mock sites were separately audited by N6.
    This is NOT a substitute for running a process from isolated staging.
    """
    selected = p14a.SELECTED | ADDON
    if set(src) != selected or len(src) != 24:
        raise Refused("closure is not exactly 19+5 modules")
    names = {Path(s).stem for s in selected}
    optional = {Path(s).stem for s in OPTIONAL}
    edges: set[str] = set()
    for path, content in src.items():
        tree = ast.parse(content.decode("utf-8"), filename=path)
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.ImportFrom):
                if node.level > 1:
                    raise Refused("parent-relative source import")
                if node.level == 1:
                    targets = ([node.module.split(".")[0]] if node.module
                               else [x.name.split(".")[0] for x in node.names])
                elif node.module and node.module.startswith("microduck_companion."):
                    targets = [node.module.split(".")[1]]
            elif isinstance(node, ast.Import):
                targets = [x.name.split(".")[1] for x in node.names
                           if x.name.startswith("microduck_companion.")]
            for name in targets:
                if name not in names | optional:
                    raise Refused("unreviewed dependency: " + name)
                edges.add(f"{Path(path).stem}->{name}")
    return tuple(sorted(edges))


def select(root: Path) -> tuple[dict[str, bytes], dict[str, bytes], tuple[str, ...]]:
    root = root.resolve(strict=True)
    base = p14a.current_source(root)  # P14A verifies 19 files and N6 optional imports
    if len(base) != 19 or set(base) != p14a.SELECTED:
        raise Refused("baseline P14B changed")
    extra = addon_files(root)
    return base, extra, audit_imports({**base, **extra})


def layer_conf() -> bytes:
    return (
        'BBPATH .= ":${LAYERDIR}"\n'
        'BBFILES += "${LAYERDIR}/recipes-*/*/*.bb"\n'
        'BBFILE_COLLECTIONS += "kwipipassive"\n'
        'BBFILE_PATTERN_kwipipassive := "^${LAYERDIR}/"\n'
        'BBFILE_PRIORITY_kwipipassive = "24"\n'
        'LAYERVERSION_kwipipassive = "1"\n'
        'LAYERDEPENDS_kwipipassive = "core kwipipy"\n'
        'LAYERSERIES_COMPAT_kwipipassive = "wrynose"\n'
    ).encode()


def recipe(digest: str) -> bytes:
    if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise Refused("invalid digest")
    modules = sorted(Path(f).name for f in ADDON)
    return (
        'SUMMARY = "Kwipi passive MOCK fixture add-on, NOT an OEM agent"\n'
        'DESCRIPTION = "Five source modules without service or privileged access."\n'
        'LICENSE = "CLOSED"\n'
        'inherit allarch python3-dir\n'
        'SRC_URI = "file://' + SRC_NAME + ';subdir=${BP};name=p15b6"\n'
        'SRC_URI[p15b6.sha256sum] = "' + digest + '"\n'
        '# Depends on P14B, does not replace its 19 modules.\n'
        'RDEPENDS:${PN} += "kwipi-companion"\n'
        'do_install() {\n'
        '    install -d "${D}${PYTHON_SITEPACKAGES_DIR}/microduck_companion"\n'
        '    for module in ' + " ".join(modules) + '; do\n'
        '        install -m 0644 "${S}/microduck_companion/$module" '
        '"${D}${PYTHON_SITEPACKAGES_DIR}/microduck_companion/$module"\n'
        '    done\n'
        '}\n'
        'FILES:${PN} += "${PYTHON_SITEPACKAGES_DIR}/microduck_companion/*.py"\n'
        '# No image bbappend, boot service, motors, ACL or hardware.\n'
    ).encode()


def staged_files(root: Path) -> tuple[dict[str, bytes], dict]:
    base, extra, edges = select(root)
    archive = p14b._tar_bytes(extra)  # deterministic reviewed P14B tar helper
    digest = sha(archive)
    report = {
        "schema": SCHEMA,
        "status": "host_addon_source_candidate_not_bitbake",
        "source_revision": p14b.repo_sha(root),
        "oem_yocto_sha": p14b.YOCTO_SHA,
        "base_modules": 19,
        "base_version": p14a.VERSION,
        "base_sha256": {p: sha(b) for p, b in sorted(base.items())},
        "addon_modules": 5,
        "addon_sha256": {p: sha(b) for p, b in sorted(extra.items())},
        "archive_sha256": digest,
        "static_import_edges": list(edges),
        "redistribution_license_reviewed": False,
        "bitbake_parsed": False,
        "target_python_tested": False,
        "dev_image_selected": False,
        "shipping_image_selected": False,
        "systemd_installed": False,
        "oem_sensor_validated": False,
        "robot_validated": False,
        "motor_commands_issued": 0,
    }
    files = {
        "conf/layer.conf": layer_conf(),
        RECIPE: recipe(digest),
        ARCHIVE: archive,
        PROVENANCE: (json.dumps(report, sort_keys=True, indent=2) + "\n").encode(),
    }
    return files, report


def verify(root: Path, layer: Path) -> dict:
    if layer.is_symlink() or not layer.is_dir():
        raise Refused("add-on layer unavailable/linked")
    files, report = staged_files(root.resolve(strict=True))
    listed = {p.relative_to(layer).as_posix() for p in layer.rglob("*")
              if p.is_file() or p.is_symlink()}
    if listed != set(files):
        raise Refused("missing or unreviewed add-on file")
    for name, expected in files.items():
        path = layer / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
            raise Refused("changed add-on recipe/source/provenance")
    with tarfile.open(layer / ARCHIVE, mode="r:gz") as tar:
        members = tar.getmembers()
        if (len(members) != 5 or {x.name for x in members} != ADDON
                or any(not m.isfile() or m.issym() or m.islnk()
                       or m.mode != 0o644 or m.uid != 0 or m.gid != 0
                       or m.mtime != 0 for m in members)):
            raise Refused("unsafe/extra source tar member")
        for m in members:
            if sha(tar.extractfile(m).read()) != report["addon_sha256"][m.name]:
                raise Refused("changed source tar member")
    return report


def stage(root: Path, output: Path) -> dict:
    root = root.resolve(strict=True)
    dest = output.resolve(strict=False)
    if (dest == root or dest.is_relative_to(root) or root.is_relative_to(dest)
            or output.exists() or output.is_symlink()):
        raise Refused("stage only outside checkout to an absent destination")
    dest.parent.mkdir(parents=True, exist_ok=True)
    files, report = staged_files(root)
    with tempfile.TemporaryDirectory(prefix="kwipi-b6-", dir=dest.parent) as tmp:
        work = Path(tmp) / LAYER
        for name, data in files.items():
            file = work / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        verify(root, work)
        work.rename(dest)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    c = p.add_subparsers(dest="command", required=True)
    for action in ("stage", "verify"):
        cmd = c.add_parser(action)
        cmd.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
        cmd.add_argument("--output" if action == "stage" else "--layer",
                         type=Path, required=True)
    a = p.parse_args()
    try:
        result = (stage(a.root, a.output) if a.command == "stage"
                  else verify(a.root, a.layer))
    except (Refused, p14b.PackageRefused, OSError, ValueError, tarfile.TarError) as e:
        p.exit(1, "P15-B6 STOP: " + type(e).__name__ + "\n")
    print(json.dumps({
        "status": result["status"], "base": result["base_modules"],
        "addon": result["addon_modules"],
        "bitbake_parsed": result["bitbake_parsed"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
