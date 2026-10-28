"""N1: read-only import/packaging inventory. Never imports Companion runtime code.

Reports imports that AST can prove; dynamic imports and runtime side effects require review.
A wheel is inspected as bytes, never imported/installed by this command.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import zipfile

PACKAGE = "microduck_companion"


def category(name: str) -> str:
    if name.startswith("sim_") or name.endswith("_demo") or name.endswith("_demo.py"):
        return "lab_candidate"
    if name.endswith("_demo.py") or "benchmark" in name or name.startswith("mock_"):
        return "lab_candidate"
    return "review_required"


def inspect_source(path: Path, root: Path) -> dict:
    rel = path.relative_to(root).as_posix()
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=rel)
    imports: set[str] = set()
    external: set[str] = set()
    dynamic = False
    main_guard = False
    motor_literal = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                if node.module:
                    imports.add(PACKAGE + "." + node.module.split(".")[0])
                else:
                    for alias in node.names:
                        imports.add(PACKAGE + "." + alias.name.split(".")[0])
            elif node.module:
                external.add(node.module.split(".")[0])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(PACKAGE + "."):
                    imports.add(PACKAGE + "." + alias.name.split(".")[1])
                else:
                    external.add(alias.name.split(".")[0])
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id == "__import__":
                dynamic = True
            elif isinstance(fn, ast.Attribute) and fn.attr == "import_module":
                dynamic = True
        elif isinstance(node, ast.If):
            # Detect conventional CLI entrypoints but not assert actual execution.
            if isinstance(node.test, ast.Compare) and isinstance(node.test.left, ast.Name):
                if node.test.left.id == "__name__":
                    main_guard = True
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "robot.move" in node.value or "robot.do" in node.value:
                motor_literal = True
    return {
        "path": rel,
        "module": PACKAGE + ("." + path.stem if path.stem != "__init__" else ""),
        "category_candidate": category(path.name),
        "internal_imports": sorted(imports),
        "external_import_roots": sorted(external),
        "dynamic_import": dynamic,
        "main_guard": main_guard,
        "contains_motor_rpc_literal": motor_literal,
    }


def collect(root: Path) -> dict:
    package = root / PACKAGE
    if not package.is_dir():
        raise ValueError("package directory missing")
    modules = [inspect_source(p, root) for p in sorted(package.rglob("*.py"))]
    names = {m["module"] for m in modules}
    for m in modules:
        m["internal_imports_missing"] = sorted(x for x in m["internal_imports"] if x not in names)
    return {"schema": "n1-import-inventory-v1", "modules": modules,
            "module_count": len(modules),
            "dynamic_import_count": sum(m["dynamic_import"] for m in modules),
            "lab_candidates": sum(m["category_candidate"] == "lab_candidate" for m in modules)}


def inspect_wheel(wheel: Path, manifest: dict) -> dict:
    with zipfile.ZipFile(wheel) as z:
        entries = set(z.namelist())
    python = sorted(x for x in entries if x.startswith(PACKAGE + "/") and x.endswith(".py"))
    expected = {m["path"] for m in manifest["modules"]}
    absent = sorted(expected - set(python))
    extra = sorted(set(python) - expected)
    return {"wheel": wheel.name, "python_file_count": len(python),
            "absent_source_modules": absent, "extra_modules": extra,
            "lab_candidates_included": sorted(m["path"] for m in manifest["modules"]
                if m["category_candidate"] == "lab_candidate" and m["path"] in python)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = collect(args.root)
    if args.wheel:
        report["wheel_inspection"] = inspect_wheel(args.wheel, report)
        if report["wheel_inspection"]["absent_source_modules"] or report["wheel_inspection"]["extra_modules"]:
            raise SystemExit("Wheel/source mismatch: inspect build configuration")
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized)


if __name__ == "__main__":
    main()
