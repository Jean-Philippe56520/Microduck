"""N5: deterministic, host-only wheel staging and wheel-byte audit.

This tool never imports Companion, installs packages, opens user media/SQLite,
contacts OEM services, or touches motors. The normal pyproject.toml is untouched.
Do NOT publish or install the probe wheel on a robot.
"""
from __future__ import annotations

import argparse
import base64
import csv
from email.parser import Parser
import hashlib
import io
import json
from pathlib import Path
import shutil
import tomllib
import zipfile

from scripts.n1_inventory import PACKAGE, collect
from scripts.n1_public_slice import select_public_closure

DIST_NAME = "microduck-companion-n5-host-probe"
DIST_STEM = "microduck_companion_n5_host_probe"
VERSION = "0.0.0"
SCHEMA = "n5-host-wheel-audit-v1"

# This explicit, reviewed set is NOT an automatic "exclude anything called sim".
# Any changed public API dependency must be re-reviewed, never silently shipped.
APPROVED_FILES = frozenset({
    "microduck_companion/__init__.py",
    "microduck_companion/autonomy.py",
    "microduck_companion/behavior_continuity.py",
    "microduck_companion/behavior_personality.py",
    "microduck_companion/behavioral_memory.py",
    "microduck_companion/episodic_memory.py",
    "microduck_companion/experience_effects.py",
    "microduck_companion/experience_expectations.py",
    "microduck_companion/experience_ledger.py",
    "microduck_companion/mock_cycles.py",
    "microduck_companion/mock_social_cues.py",
    "microduck_companion/oem_expression_hints.py",
    "microduck_companion/passive_intentions.py",
    "microduck_companion/passive_learning.py",
    "microduck_companion/passive_memory.py",
    "microduck_companion/passive_observations.py",
    "microduck_companion/passive_rhythm.py",
    "microduck_companion/passive_sources.py",
    "microduck_companion/perception.py",
})
LAB_EXCEPTIONS = frozenset({
    "microduck_companion/mock_cycles.py",
    "microduck_companion/mock_social_cues.py",
})

PROBE_PYPROJECT = '''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "microduck-companion-n5-host-probe"
version = "0.0.0"
description = "HOST-ONLY N5 dependency probe; not a robot release"
requires-python = ">=3.10"

[tool.setuptools.packages.find]
include = ["microduck_companion"]
'''


def _checked_paths(root: Path, approved: frozenset[str]) -> tuple[dict[str, bytes], dict]:
    manifest = collect(root)
    selected = select_public_closure(manifest)
    paths = {m["path"] for m in selected}
    if paths != approved:
        raise ValueError(
            "Public API closure changed; review allowlist: "
            + "unapproved=" + repr(sorted(paths - approved))
            + " missing=" + repr(sorted(approved - paths))
        )
    if any(m["dynamic_import"] or m["contains_motor_rpc_literal"] for m in selected):
        raise ValueError("Dynamic import or motor RPC literal in candidate")
    if any(p.split("/")[-1].startswith("sim_") for p in paths):
        raise ValueError("Simulator in candidate")
    if any(p.startswith("upstream/") for p in paths):
        raise ValueError("OEM module in candidate")
    expected_exceptions = paths & {p for p in approved if p.endswith(".py") and
                                   p.split("/")[-1].startswith("mock_")}
    if expected_exceptions - LAB_EXCEPTIONS:
        raise ValueError("Unexpected mock module")
    source: dict[str, bytes] = {}
    for rel in sorted(paths):
        p = root / rel
        if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(root.resolve()):
            raise ValueError("Selected source is not a regular in-tree file: " + rel)
        source[rel] = p.read_bytes()
    return source, manifest


def stage_probe(root: Path, stage: Path) -> dict:
    root, stage = root.resolve(), stage.resolve()
    if stage == root or stage.is_relative_to(root) or root.is_relative_to(stage):
        raise ValueError("Staging must be outside checkout/source")
    if stage.exists() and any(stage.iterdir()):
        raise ValueError("Staging must be empty; refuse overwriting files")
    pyproject = root / "pyproject.toml"
    if pyproject.is_symlink():
        raise ValueError("Refuse symlink packaging metadata")
    main_meta = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    if main_meta.get("project", {}).get("name") != "microduck-companion":
        raise ValueError("Unexpected main distribution; cannot stage N5")
    if main_meta.get("build-system", {}).get("build-backend") != "setuptools.build_meta":
        raise ValueError("Unexpected main build backend; review required")
    source, inventory = _checked_paths(root, APPROVED_FILES)
    stage.mkdir(parents=True, exist_ok=True)
    for rel, contents in source.items():
        target = stage / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
    (stage / "pyproject.toml").write_text(PROBE_PYPROJECT, encoding="utf-8")
    return {
        "schema": SCHEMA,
        "scope": "HOST_ONLY_NON_DEPLOYABLE; experimental independent wheel",
        "normal_distribution": main_meta["project"]["name"],
        "normal_version": main_meta["project"]["version"],
        "probe_distribution": DIST_NAME,
        "probe_version": VERSION,
        "normal_source_module_count": inventory["module_count"],
        "selected_module_count": len(source),
        "excluded_from_probe_count": inventory["module_count"] - len(source),
        "approved_paths": sorted(source),
        "source_sha256": {rel: hashlib.sha256(data).hexdigest() for rel, data in source.items()},
        "laboratory_exceptions": sorted(set(source) & LAB_EXCEPTIONS),
        "no_oem_or_motor_package_claim": True,
    }


def _wheel_modules(path: Path) -> tuple[set[str], int]:
    if not path.is_file() or not zipfile.is_zipfile(path):
        raise ValueError("Not a readable wheel file")
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError("Bad wheel CRC")
        return (
            {n for n in z.namelist() if n.startswith(PACKAGE + "/") and n.endswith(".py")},
            path.stat().st_size,
        )


def inspect_probe(root: Path, wheel: Path, normal_wheel: Path) -> dict:
    source, manifest = _checked_paths(root.resolve(), APPROVED_FILES)
    probe_modules, probe_bytes = _wheel_modules(wheel)
    normal_modules, normal_bytes = _wheel_modules(normal_wheel)
    if probe_modules != set(source):
        raise ValueError("Candidate wheel file list disagrees with strict allowlist")
    if normal_modules != {m["path"] for m in manifest["modules"]}:
        raise ValueError("Baseline normal wheel differs from source checkout")
    if len(probe_modules) >= len(normal_modules):
        raise ValueError("No packaging isolation measured")
    with zipfile.ZipFile(wheel) as z:
        members = z.namelist()
        if len(members) != len(set(members)):
            raise ValueError("Duplicate ZIP entries in wheel")
        if any(n.startswith("/") or ".." in Path(n).parts or
               n.endswith((".pyc", ".so", ".pyd", ".pth")) or
               ".data/" in n or n.endswith("/entry_points.txt")
               for n in members):
            raise ValueError("Executable/external data or unsafe wheel entry")
        for name, contents in source.items():
            if z.read(name) != contents:
                raise ValueError("Candidate wheel changes source bytes: " + name)
        distinfo = DIST_STEM + "-" + VERSION + ".dist-info/"
        if not (distinfo + "METADATA" in members and
                distinfo + "WHEEL" in members and
                distinfo + "RECORD" in members):
            raise ValueError("Wheel metadata missing or wrong distribution")
        metadata = Parser().parsestr(z.read(distinfo + "METADATA").decode("utf-8"))
        if (metadata.get("Name", "").lower() != DIST_NAME or
                metadata.get("Version") != VERSION or
                metadata.get_all("Requires-Dist")):
            raise ValueError("Invalid/disallowed candidate wheel metadata")
        wheel_metadata = z.read(distinfo + "WHEEL").decode("utf-8")
        if "Tag: py3-none-any" not in wheel_metadata:
            raise ValueError("Candidate is not a pure-Python wheel")
        rows = list(csv.reader(io.StringIO(z.read(distinfo + "RECORD").decode("utf-8"))))
        if len(rows) != len(members) or {r[0] for r in rows} != set(members):
            raise ValueError("Wheel RECORD entries differ from ZIP files")
        for filename, digest, size in rows:
            if filename == distinfo + "RECORD":
                if digest or size:
                    raise ValueError("RECORD must not self-hash")
                continue
            data = z.read(filename)
            calculated = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            if digest != "sha256=" + calculated or size != str(len(data)):
                raise ValueError("Wheel RECORD hash or size mismatch: " + filename)
    return {
        "schema": SCHEMA,
        "scope": "HOST_ONLY_NON_DEPLOYABLE; pip-install smoke in temporary CI target only",
        "normal_source_python_modules": len(normal_modules),
        "probe_python_modules": len(probe_modules),
        "excluded_python_modules": len(normal_modules) - len(probe_modules),
        "normal_wheel_bytes": normal_bytes,
        "probe_wheel_bytes": probe_bytes,
        "probe_wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "lab_exceptions": sorted(probe_modules & LAB_EXCEPTIONS),
        "selected_files": sorted(probe_modules),
        "standard_wheel_unchanged": True,
        "robot_hardware_validated": False,
        "motors_or_sensors_tested": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="cmd", required=True)
    stage = commands.add_parser("stage")
    stage.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    stage.add_argument("--stage-dir", type=Path, required=True)
    stage.add_argument("--report", type=Path, required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    inspect.add_argument("--wheel", type=Path, required=True)
    inspect.add_argument("--normal-wheel", type=Path, required=True)
    inspect.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    report = (stage_probe(args.root, args.stage_dir)
              if args.cmd == "stage" else
              inspect_probe(args.root, args.wheel, args.normal_wheel))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("N5 HOST ONLY:", report.get("selected_module_count", report.get("probe_python_modules")),
          "modules; never install on Microduck")


if __name__ == "__main__":
    main()
