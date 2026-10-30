"""PER-P14A: produce a bounded, pure-Python embedded *candidate* wheel.

Reuse the N6 exact public closure, add the unchanged audited OEM read-only
telemetry client, and never pretend this is an installed Yocto/robot service.
"""
from __future__ import annotations

import argparse
import ast
import base64
import csv
from email.parser import Parser
import hashlib
import io
import json
from pathlib import Path
import tomllib
import zipfile

from scripts import n5_host_wheel as n5, n6_no_mock_wheel as n6

SCHEMA = "kwipi-p14a-embedded-candidate-wheel-v1"
DIST_NAME = "microduck-companion-embedded-candidate"
DIST_STEM = "microduck_companion_embedded_candidate"
VERSION = "0.2.0a1"
PASSIVE_PATH = "microduck_companion/sim_ipc.py"
SELECTED = n5.APPROVED_FILES - n6.OMITTED | {PASSIVE_PATH}
METADATA = n6.PROBE_PYPROJECT.replace(
    n6.DIST_NAME, DIST_NAME
).replace('version = "0.0.0"', 'version = "' + VERSION + '"').replace(
    "N6 mock-free dependency probe", "P14A readonly embedded candidate; NOT FOR ROBOT",
)


def verify_oem_readonly_source(source: bytes) -> dict:
    tree = ast.parse(source.decode("utf-8"), filename=PASSIVE_PATH)
    imported = set()
    denied = {"subprocess", "ctypes", "multiprocessing", "importlib", "requests",
              "http", "urllib", "serial", "sqlite3"}
    allowed = {"__future__", "collections", "dataclasses", "json", "math", "os",
               "socket", "time", "typing"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(x.name.split(".")[0] for x in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                raise ValueError("P14A telemetry may not import another Companion module")
            imported.add((node.module or "").split(".")[0])
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in {"eval", "exec", "__import__", "open"}:
                raise ValueError("new dynamic import/eval/write path in telemetry")
            if isinstance(fn, ast.Attribute) and fn.attr in {
                "import_module", "Popen", "system", "write_text", "write_bytes",
                "unlink", "replace", "remove", "mkdir", "connect_ex",
            }:
                raise ValueError("unreviewed telemetry side-effect")
    if imported - allowed or imported & denied:
        raise ValueError("unknown telemetry import: " + repr(imported - allowed))
    allowed_rpc = None
    has_method_guard = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_ALLOWED_READS" for t in node.targets):
            if not (isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "frozenset"
                    and len(node.value.args) == 1):
                raise ValueError("read-only request set is no longer a static frozenset")
            allowed_rpc = ast.literal_eval(node.value.args[0])
        if (isinstance(node, ast.Compare)
                and isinstance(node.left, ast.Name) and node.left.id == "method"
                and any(isinstance(op, ast.NotIn) for op in node.ops)
                and any(isinstance(x, ast.Name) and x.id == "_ALLOWED_READS"
                        for x in node.comparators)):
            has_method_guard = True
    if set(allowed_rpc or ()) != {"robot.health", "robot.subscribe", "tof.stream"}:
        raise ValueError("OEM read-only whitelist changed")
    if not has_method_guard:
        raise ValueError("OEM request method guard absent")
    classes = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
    if "ReadOnlyUnixRpc" not in classes or "TelemetryError" not in classes:
        raise ValueError("reviewed OEM read-only transport was replaced")
    return {"read_only_rpc": sorted(allowed_rpc), "imports": sorted(imported)}


def current_source(root: Path) -> dict[str, bytes]:
    root = root.resolve(strict=True)
    full, _ = n5._checked_paths(root, n5.APPROVED_FILES)
    n6.verify_optional_boundary(full)
    source = {p: b for p, b in full.items() if p not in n6.OMITTED}
    file = root / PASSIVE_PATH
    if (file.is_symlink() or not file.is_file()
            or not file.resolve().is_relative_to(root)):
        raise ValueError("P14A read-only OEM telemetry source missing/unsafe")
    data = file.read_bytes()
    verify_oem_readonly_source(data)
    source[PASSIVE_PATH] = data
    if set(source) != SELECTED or len(source) != 19:
        raise ValueError("P14A closure changed without explicit review")
    return source


def stage(root: Path, target: Path) -> dict:
    root = root.resolve(strict=True)
    target = target.resolve()
    if (target == root or root.is_relative_to(target) or target.is_relative_to(root)
            or (target.exists() and any(target.iterdir()))):
        raise ValueError("P14A staging must be empty and outside checkout")
    selected = current_source(root)
    report = n6.stage_probe(root, target)
    targetpath = target / PASSIVE_PATH
    targetpath.write_bytes(selected[PASSIVE_PATH])
    (target / "pyproject.toml").write_text(METADATA, encoding="utf-8")
    return {
        "schema": SCHEMA,
        "status": "pure_python_host_candidate_not_yocto",
        "files": sorted(selected),
        "python_modules": len(selected),
        "source_sha256": {p: hashlib.sha256(b).hexdigest() for p, b in sorted(selected.items())},
        "read_only_transport": verify_oem_readonly_source(selected[PASSIVE_PATH]),
        "n6_selected_modules": report["probe_python_modules"],
        "mock_engines_included": False,
        "compiled_for_rk3566": False,
        "robot_service_installed": False,
        "perception_model_included": False,
        "physical_robot_verified": False,
        "motor_commands_issued": 0,
    }


def inspect(root: Path, wheel: Path) -> dict:
    sources = current_source(root)
    if not wheel.is_file() or wheel.is_symlink() or not zipfile.is_zipfile(wheel):
        raise ValueError("P14A wheel missing/not a real wheel")
    with zipfile.ZipFile(wheel, "r") as z:
        if z.testzip() is not None:
            raise ValueError("corrupt P14A wheel")
        members = z.namelist()
        if len(members) != len(set(members)):
            raise ValueError("duplicate wheel members")
        for n in members:
            if (n.startswith("/") or ".." in Path(n).parts
                    or n.endswith((".pth", ".so", ".pyd", ".pyc"))
                    or ".data/" in n or n.endswith("/entry_points.txt")):
                raise ValueError("unsafe wheel member")
        got = {p for p in members if p.startswith("microduck_companion/") and p.endswith(".py")}
        if got != set(sources):
            raise ValueError("P14A wheel includes wrong module set")
        for p, b in sources.items():
            if z.read(p) != b:
                raise ValueError("wheel source bytes differ from audited repository")
        meta = DIST_STEM + "-" + VERSION + ".dist-info/"
        expected = {meta + k for k in ("METADATA", "RECORD", "WHEEL")}
        if set(members) != got | expected:
            raise ValueError("wheel includes unreviewed resources/metadata")
        m = Parser().parsestr(z.read(meta + "METADATA").decode("utf-8"))
        if m.get("Name", "").lower() != DIST_NAME or m.get("Version") != VERSION or m.get_all("Requires-Dist"):
            raise ValueError("wheel identity or unreviewed external dependency")
        if "Tag: py3-none-any" not in z.read(meta + "WHEEL").decode("utf-8"):
            raise ValueError("wheel is not pure Python")
        rows = list(csv.reader(io.StringIO(z.read(meta + "RECORD").decode("utf-8"))))
        if len(rows) != len(members) or {row[0] for row in rows} != set(members):
            raise ValueError("RECORD listing mismatch")
        for name, digest, size in rows:
            if name == meta + "RECORD":
                if digest or size:
                    raise ValueError("RECORD self hash must be empty")
                continue
            b = z.read(name)
            sha = base64.urlsafe_b64encode(hashlib.sha256(b).digest()).rstrip(b"=").decode("ascii")
            if digest != "sha256=" + sha or size != str(len(b)):
                raise ValueError("invalid wheel RECORD integrity: " + name)
    return {
        "schema": SCHEMA,
        "status": "pure_python_host_candidate_not_yocto",
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "wheel_bytes": wheel.stat().st_size,
        "python_modules": len(sources),
        "mock_engines_included": False,
        "read_only_transport": verify_oem_readonly_source(sources[PASSIVE_PATH]),
        "compiled_for_rk3566": False,
        "robot_service_installed": False,
        "physical_robot_verified": False,
        "motor_commands_issued": 0,
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    subs = cli.add_subparsers(dest="command", required=True)
    for name in ("stage", "inspect"):
        p = subs.add_parser(name)
        p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
        if name == "stage":
            p.add_argument("--stage-dir", type=Path, required=True)
        else:
            p.add_argument("--wheel", type=Path, required=True)
        p.add_argument("--report", type=Path, required=True)
    args = cli.parse_args()
    try:
        result = (stage(args.root, args.stage_dir) if args.command == "stage"
                  else inspect(args.root, args.wheel))
        if args.report.exists():
            raise ValueError("refuse to overwrite an existing P14A report")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"status": result["status"], "python_modules": result["python_modules"]}))
    except (ValueError, OSError, SyntaxError, KeyError, tomllib.TOMLDecodeError,
            zipfile.BadZipFile) as error:
        cli.exit(1, f"PER-P14A STOP: {error}\n")


if __name__ == "__main__":
    main()
