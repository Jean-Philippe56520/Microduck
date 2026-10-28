"""N6: host-only true wheel omitting mock engines, preserving their source/tests.

Reuses N5 staging, source-byte and RECORD verification. This is NOT a robot
package, a consent check, an OEM service, or an action scheduler.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

from scripts import n5_host_wheel as n5

SCHEMA = "n6-no-mock-host-wheel-v1"
DIST_NAME = "microduck-companion-n6-no-mock-host-probe"
OMITTED = n5.LAB_EXCEPTIONS
# Audited, narrowly optional imports: both TYPE_CHECKING and the guarded
# historical lab method. A new call site fails closed, not quietly omitted.
ALLOWED_SITES = frozenset({
    ("behavioral_memory.py", "TYPE_CHECKING", "mock_cycles", "MockCycleRunner"),
    ("behavioral_memory.py", "record", "mock_cycles", "MockCycleRunner"),
    ("behavior_personality.py", "TYPE_CHECKING", "mock_social_cues", "MockSocialPlan"),
    ("behavior_personality.py", "_interpret", "mock_social_cues", "MockSocialPlan"),
})
PROBE_PYPROJECT = n5.PROBE_PYPROJECT.replace(
    n5.DIST_NAME, DIST_NAME
).replace("N5 dependency probe", "N6 mock-free dependency probe")


class OptionalImportVisitor(ast.NodeVisitor):
    def __init__(self, source_file: str) -> None:
        self.source_file = source_file
        self.scope = ["module"]
        self.sites: set[tuple[str, str, str, str]] = set()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node: ast.If) -> None:
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            self.scope.append("TYPE_CHECKING")
            for stmt in node.body:
                self.visit(stmt)
            self.scope.pop()
            for stmt in node.orelse:
                self.visit(stmt)
        else:
            self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if not node.level:
            if node.module in {"microduck_companion.mock_cycles", "microduck_companion.mock_social_cues"}:
                raise ValueError("Absolute mock-engine import must not be retained")
            return
        if node.module in ("mock_cycles", "mock_social_cues"):
            for alias in node.names:
                if alias.asname is not None:
                    raise ValueError("Unexpected optional import alias")
                self.sites.add((
                    self.source_file, self.scope[-1], node.module, alias.name
                ))
        if node.module is None and any(
                alias.name in ("mock_cycles", "mock_social_cues")
                for alias in node.names):
            raise ValueError("Indirect optional mock import denied")

    def visit_Import(self, node: ast.Import) -> None:
        if any(alias.name in {
                "microduck_companion.mock_cycles",
                "microduck_companion.mock_social_cues",
                "mock_cycles", "mock_social_cues",
            } for alias in node.names):
            raise ValueError("Unexpected absolute mock-engine import")


def verify_optional_boundary(source: dict[str, bytes]) -> list[tuple[str, str, str, str]]:
    required = {p for p in n5.APPROVED_FILES if p not in OMITTED}
    if set(source) != n5.APPROVED_FILES:
        raise ValueError("Full N5 reviewed-source closure required before removal")
    if len(required) != 18 or len(OMITTED) != 2:
        raise ValueError("N6 allowlist changed without review")
    all_sites: set[tuple[str, str, str, str]] = set()
    for rel in sorted(required):
        path = rel.rsplit("/", 1)[-1]
        tree = ast.parse(source[rel].decode("utf-8"), filename=rel)
        v = OptionalImportVisitor(path)
        v.visit(tree)
        all_sites.update(v.sites)
    if all_sites != ALLOWED_SITES:
        raise ValueError("Optional mock-engine import sites changed; review first: " +
                         repr(sorted(all_sites ^ ALLOWED_SITES)))
    return sorted(all_sites)


def stage_probe(root: Path, stage: Path) -> dict:
    source, _inventory = n5._checked_paths(root.resolve(), n5.APPROVED_FILES)
    sites = verify_optional_boundary(source)
    report = n5.stage_probe(root, stage)
    for rel in sorted(OMITTED):
        target = stage / rel
        if not target.is_file() or target.is_symlink():
            raise ValueError("Expected historical source missing in staging")
        target.unlink()
    (stage / "pyproject.toml").write_text(PROBE_PYPROJECT, encoding="utf-8")
    included = n5.APPROVED_FILES - OMITTED
    return {
        "schema": SCHEMA,
        "scope": "HOST_ONLY; non-deployable wheel with fixture APIs unavailable",
        "normal_source_python_modules": report["normal_source_module_count"],
        "n5_reviewed_closure": len(n5.APPROVED_FILES),
        "probe_python_modules": len(included),
        "omitted_mock_engines": sorted(OMITTED),
        "allowed_optional_import_sites": sites,
        "selected_paths": sorted(included),
        "mock_engine_source_retained_in_repository": True,
        "robot_hardware_validated": False,
    }


def inspect_probe(root: Path, wheel: Path, normal_wheel: Path) -> dict:
    source, _ = n5._checked_paths(root.resolve(), n5.APPROVED_FILES)
    verify_optional_boundary(source)
    report = n5.inspect_probe(root, wheel, normal_wheel, variant="n6")
    if report["probe_python_modules"] != 18 or report["lab_exceptions"]:
        raise ValueError("N6 wheel contains unexpected modules")
    return {**report, "schema": SCHEMA,
            "omitted_mock_engines": sorted(OMITTED),
            "no_mock_modules_in_candidate": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    stage = subs.add_parser("stage")
    stage.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    stage.add_argument("--stage-dir", type=Path, required=True)
    stage.add_argument("--report", type=Path, required=True)
    audit = subs.add_parser("inspect")
    audit.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    audit.add_argument("--wheel", type=Path, required=True)
    audit.add_argument("--normal-wheel", type=Path, required=True)
    audit.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = (stage_probe(args.root, args.stage_dir) if args.command == "stage"
              else inspect_probe(args.root, args.wheel, args.normal_wheel))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print("N6 HOST-ONLY:", result["probe_python_modules"], "modules; NOT a robot release")


if __name__ == "__main__":
    main()
