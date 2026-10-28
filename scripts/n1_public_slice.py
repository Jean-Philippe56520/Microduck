"""N1b: preview an isolated *host-only* public-API source slice.

No installation, execution, robot access, modification of runtime packaging, or
claim of embedded readiness. This script only reads source and writes a ZIP
containing the static dependency closure of the current public __init__ API.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

from scripts.n1_inventory import PACKAGE, collect

SOURCE_VERSION = "n1b-public-api-slice-v1"


def select_public_closure(manifest: dict) -> list[dict]:
    modules = {m["module"]: m for m in manifest["modules"]}
    if len(modules) != manifest["module_count"] or PACKAGE not in modules:
        raise ValueError("Invalid manifest: missing or repeated public package")
    selected: set[str] = set()
    pending = [PACKAGE]
    while pending:
        name = pending.pop()
        if name in selected:
            continue
        if name not in modules:
            raise ValueError("Unresolved internal import: " + name)
        m = modules[name]
        if m["internal_imports_missing"]:
            raise ValueError("Unresolved imports in " + name)
        if m["dynamic_import"]:
            raise ValueError("Dynamic import in public closure: " + name)
        if m["contains_motor_rpc_literal"]:
            raise ValueError("Motor RPC marker in public closure: " + name)
        if name.split(".")[-1].startswith("sim_"):
            raise ValueError("Simulator module in public closure: " + name)
        selected.add(name)
        pending.extend(m["internal_imports"])
    return [modules[name] for name in sorted(selected)]


def build_public_slice(root: Path, output: Path) -> dict:
    manifest = collect(root)
    selection = select_public_closure(manifest)
    package_files = [m["path"] for m in selection]
    if len(package_files) != len(set(package_files)):
        raise ValueError("Duplicate source paths")
    # Check all sources before creating any output. Never follow a symlink.
    source = {}
    for rel in package_files:
        p = root / rel
        if p.is_symlink() or not p.is_file():
            raise ValueError("Source must be a regular file: " + rel)
        if not p.resolve().is_relative_to(root.resolve()):
            raise ValueError("Source outside project root")
        source[rel] = p.read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in sorted(source):
            info = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source[rel])
    return {
        "schema": SOURCE_VERSION,
        "scope": "host-only public-API experiment; not a wheel or robot package",
        "total_python_modules": manifest["module_count"],
        "selected_python_modules": len(selection),
        "selected_paths": package_files,
        "lab_candidates_still_required": [
            m["path"] for m in selection if m["category_candidate"] == "lab_candidate"
        ],
        "excluded_python_modules": manifest["module_count"] - len(selection),
        "external_import_roots": sorted(set(
            root for m in selection for root in m["external_import_roots"]
        )),
        "dynamic_imports_in_selection": 0,
        "motor_rpc_literals_in_selection": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = build_public_slice(args.root, args.output)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("host public-API slice:", report["selected_python_modules"],
          "of", report["total_python_modules"], "modules; NO robot deployment")


if __name__ == "__main__":
    main()
