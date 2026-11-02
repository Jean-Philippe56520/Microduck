"""P15-B17: deterministic source-only package for the B13-B16 read-only OEM reader.

Never alters or selects an image, OEM code, Yocto build, service, detector,
camera, motor group, SQLite, existing B10 rootfs or historical reports.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile

from scripts import per_p14b_yocto_python_layer as p14b
from scripts import per_p15b6_passive_python_addon as b6
from scripts import per_p16_dev_rootfs_audit as p16a
from scripts import per_p16b10_dev_rootfs_audit as b10

LAYER = "meta-kwipi-p15-oem-receiver"
SCHEMA = "kwipi-p15b17-oem-receiver-source-package-v1"
PACKAGE, VERSION = "kwipi-b12-receiver", "0.1.0"
ARCHIVE = f"{PACKAGE}-{VERSION}.tar.gz"
ARCHIVE_PATH = f"recipes-kwipi/{PACKAGE}/files/{ARCHIVE}"
RECIPE_PATH = f"recipes-kwipi/{PACKAGE}/{PACKAGE}_{VERSION}.bb"
REPORT_PATH = "kwipi-oem-receiver-source-provenance.json"
SELECTED = frozenset({
    "microduck_companion/b12_local_wire_contract.py",
    "microduck_companion/b14_host_identity_gate.py",
    "microduck_companion/b15_cross_uid_host_gate.py",
    "microduck_companion/b16_oem_readonly_reader.py",
})
RUNTIME = ("kwipi-companion", "kwipi-passive-fixture", "python3-core",
           "python3-io", "python3-json", "python3-math", "python3-netclient")
DENIED_IMPORT = frozenset({
    "subprocess", "sqlite3", "ctypes", "importlib", "requests",
    "urllib", "http", "shutil", "multiprocessing", "serial",
})
DENIED_CALL = frozenset({
    "send", "sendall", "sendto", "sendmsg", "write", "write_bytes",
    "write_text", "setxattr", "chmod", "chown", "unlink", "mkdir",
    "rename", "replace", "remove", "rmtree", "system", "Popen",
    "setuid", "seteuid", "setgid", "setegid", "setgroups", "kill",
    "execv", "execve", "spawn", "connect_ex",
})


class Refused(ValueError):
    """P15-B17 source or layer violates the allowed passive closure."""


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def audit_new_sources(new: dict[str, bytes], old: set[str]) -> list[str]:
    """Static reuse check, never a runtime proof or sensor certificate."""
    if set(new) != SELECTED or len(new) != 4 or old & SELECTED:
        raise Refused("module selection differs from the 24+4 closure")
    permitted = {Path(x).stem for x in old | SELECTED}
    edges: set[str] = set()
    for path, raw in sorted(new.items()):
        try:
            tree = ast.parse(raw.decode("utf-8"), filename=path)
        except (SyntaxError, UnicodeError) as exc:
            raise Refused("invalid receiver Python") from exc
        for node in ast.walk(tree):
            candidates: list[str] = []
            if isinstance(node, ast.ImportFrom):
                if node.level > 1:
                    raise Refused("parent-relative import")
                module = node.module or ""
                if node.level == 1:
                    candidates = [module.split(".")[0]] if module else [
                        alias.name.split(".")[0] for alias in node.names]
                elif module.startswith("microduck_companion."):
                    candidates = [module.split(".")[1]]
                elif module.split(".")[0] in DENIED_IMPORT:
                    raise Refused("forbidden external import")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in DENIED_IMPORT:
                        raise Refused("forbidden external import")
                    if alias.name.startswith("microduck_companion."):
                        candidates.append(alias.name.split(".")[1])
            for name in candidates:
                if name not in permitted:
                    raise Refused("unreviewed Companion import")
                edges.add(f"{Path(path).stem}->{name}")
            if isinstance(node, ast.Call):
                if (isinstance(node.func, ast.Name)
                        and node.func.id in {"eval", "exec", "__import__", "open"}):
                    raise Refused("dynamic import/exec/write")
                if (isinstance(node.func, ast.Attribute)
                        and node.func.attr in DENIED_CALL):
                    raise Refused("write/motor/process call")
    b16 = new["microduck_companion/b16_oem_readonly_reader.py"]
    for anchor in (
        b'    def __init__(self, *, enabled: bool = False,',
        b'    provenance: str = "none"',
        b'    verified_sensor: bool = False',
        b'    executable_verified: bool = False',
        b'_RUN = Path("/run")',
        b'_MIN_INTERVAL_S = 0.5',
        b'_observer_ids()',
        b'_checked_once(',
    ):
        if anchor not in b16:
            raise Refused("B16 read-only/opt-in invariant removed")
    return sorted(edges)


def selected(root: Path) -> tuple[dict[str, bytes], dict]:
    if root.is_symlink() or not root.is_dir():
        raise Refused("missing/symlinked project root")
    root = root.resolve(strict=True)
    base = p14b.selected_bytes(root)
    prior = {k: v for k, v in base.items() if k.endswith(".py")}
    extra = b6.addon_files(root)
    if (len(prior) != 19 or set(prior) != p14b.p14a.SELECTED
            or len(extra) != 5 or set(extra) != b6.ADDON
            or _sha(p14b._tar_bytes(base)) != p16a.PINNED_P14B_ARCHIVE_SHA256
            or {k: _sha(v) for k, v in extra.items()} != b10.B6_SHA256):
        raise Refused("the historical 19+5 B10 sources changed")
    b6.audit_imports({**prior, **extra})
    old = set(prior) | set(extra)
    if len(old) != 24 or old & SELECTED:
        raise Refused("B17 overlaps B10 installed modules")
    new = {}
    for name in sorted(SELECTED):
        path = root / name
        if (path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to(root)
                or any(x.is_symlink() for x in path.parents
                       if x != root and x.is_relative_to(root))):
            raise Refused("new source missing/linked/escapes checkout")
        new[name] = path.read_bytes()
    edges = audit_new_sources(new, old)
    return new, {
        "source_revision": p14b.repo_sha(root),
        "historical_python_modules": 24,
        "historical_p14b_archive_sha256": p16a.PINNED_P14B_ARCHIVE_SHA256,
        "historical_b6_sha256": dict(sorted(b10.B6_SHA256.items())),
        "companion_import_edges": edges,
    }


def layer_conf() -> bytes:
    return (
        'BBPATH .= ":@{LAYERDIR}"\n'
        'BBFILES += "@{LAYERDIR}/recipes-*/*/*.bb"\n'
        'BBFILE_COLLECTIONS += "kwipib17"\n'
        'BBFILE_PATTERN_kwipib17 := "^@{LAYERDIR}/"\n'
        'BBFILE_PRIORITY_kwipib17 = "26"\n'
        'LAYERVERSION_kwipib17 = "1"\n'
        'LAYERDEPENDS_kwipib17 = "core kwipipy kwipipassive"\n'
        'LAYERSERIES_COMPAT_kwipib17 = "wrynose"\n'
    ).replace("@{", "\x24{").encode("utf-8")


def recipe(digest: str) -> bytes:
    if len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
        raise Refused("unreviewed source archive digest")
    modules = sorted(Path(name).name for name in SELECTED)
    src = (
        'SUMMARY = "Kwipi B12 passive OEM receipt candidate, no service"\n'
        'DESCRIPTION = "Exactly four B13-B16 pure Python modules; no auto-start."\n'
        '# Source redistribution review is pending. PRIVATE DEV only.\n'
        'LICENSE = "CLOSED"\n'
        'inherit allarch python3-dir\n'
        f'SRC_URI = "file://{ARCHIVE};subdir=@{{BP}};name=p15b17"\n'
        f'SRC_URI[p15b17.sha256sum] = "{digest}"\n'
        f'RDEPENDS:@{{PN}} += "{" ".join(RUNTIME)}"\n'
        'do_install() {\n'
        '    install -d "@{D}@{PYTHON_SITEPACKAGES_DIR}/microduck_companion"\n'
        '    for module in ' + " ".join(modules) + '; do\n'
        '        install -m 0644 "@{S}/microduck_companion/$module" '
        '"@{D}@{PYTHON_SITEPACKAGES_DIR}/microduck_companion/$module"\n'
        '    done\n'
        '}\n'
        'FILES:@{PN} += "@{PYTHON_SITEPACKAGES_DIR}/microduck_companion/*.py"\n'
        '# Not selected in DEV/shipping. No unit, model, network or motors.\n'
    )
    return src.replace("@{", "\x24{").encode("utf-8")


def staged_files(root: Path) -> tuple[dict[str, bytes], dict]:
    new, history = selected(root)
    archive = p14b._tar_bytes(new)
    digest = _sha(archive)
    report = {
        "schema": SCHEMA,
        "status": "b17_source_only_b12_receiver_candidate_not_bitbake",
        **history,
        "oem_yocto_sha": p14b.YOCTO_SHA,
        "oem_pin": "942e58e3aa6dbb28e7037203fff11866122c7567",
        "new_modules": 4,
        "new_sha256": {n: _sha(b) for n, b in sorted(new.items())},
        "archive_sha256": digest,
        "runtime_dependencies": list(RUNTIME),
        "license_redistribution_approved": False,
        "bitbake_executed": False,
        "bitbake_parsed": False,
        "dev_image_selected": False,
        "shipping_image_selected": False,
        "rootfs_modified": False,
        "service_installed": False,
        "oem_producer_enabled": False,
        "oem_sensor_verified": False,
        "robot_validated": False,
        "motor_commands_issued": 0,
    }
    return {
        "conf/layer.conf": layer_conf(),
        RECIPE_PATH: recipe(digest),
        ARCHIVE_PATH: archive,
        REPORT_PATH: (json.dumps(report, sort_keys=True, indent=2) + "\n").encode(),
    }, report


def verify(root: Path, layer: Path) -> dict:
    if layer.is_symlink() or not layer.is_dir():
        raise Refused("B17 source layer absent or linked")
    files, report = staged_files(root)
    actual = {f.relative_to(layer).as_posix() for f in layer.rglob("*")
              if f.is_file() or f.is_symlink()}
    if actual != set(files):
        raise Refused("unreviewed/missing B17 file")
    for name, expected in files.items():
        path = layer / name
        if path.is_symlink() or not path.is_file() or path.read_bytes() != expected:
            raise Refused("B17 source, recipe or provenance changed")
    with tarfile.open(layer / ARCHIVE_PATH, "r:gz") as tar:
        members = tar.getmembers()
        if (len(members) != 4 or {m.name for m in members} != SELECTED
                or any(not m.isfile() or m.issym() or m.islnk()
                       or m.mode != 0o644 or m.uid or m.gid or m.mtime
                       for m in members)):
            raise Refused("B17 tar member/name/mode/owner/time mismatch")
        for m in members:
            f = tar.extractfile(m)
            if f is None or _sha(f.read()) != report["new_sha256"][m.name]:
                raise Refused("B17 source tar bytes differ")
    return report


def stage(root: Path, output: Path) -> dict:
    if root.is_symlink() or not root.is_dir():
        raise Refused("project root absent or linked")
    project = root.resolve(strict=True)
    target = output.resolve(strict=False)
    if (not output.is_absolute() or output.exists() or output.is_symlink()
            or target == project or target.is_relative_to(project)
            or project.is_relative_to(target)):
        raise Refused("staging must be outside checkout into an absent directory")
    files, report = staged_files(project)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kwipi-b17-", dir=output.parent) as tmp:
        temp = Path(tmp) / LAYER
        for rel, blob in files.items():
            f = temp / rel
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(blob)
        verify(project, temp)
        temp.rename(output)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    for action in ("stage", "verify"):
        cmd = sub.add_parser(action)
        cmd.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
        cmd.add_argument("--output" if action == "stage" else "--layer",
                         type=Path, required=True)
    args = p.parse_args()
    try:
        r = stage(args.root, args.output) if args.command == "stage" else verify(args.root, args.layer)
    except (Refused, p14b.PackageRefused, b6.Refused,
            ValueError, OSError, KeyError, SyntaxError, tarfile.TarError) as exc:
        p.exit(1, f"P15-B17 STOP: {type(exc).__name__}\n")
    print(json.dumps({k: r[k] for k in (
        "status", "historical_python_modules", "new_modules",
        "dev_image_selected", "shipping_image_selected")}, sort_keys=True))


if __name__ == "__main__":
    main()
