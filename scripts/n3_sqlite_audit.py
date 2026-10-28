"""N3: static, read-only inventory of Companion SQLite schemas and writers.

This never imports Companion runtime modules or opens a SQLite database.
It intentionally reports, rather than guesses about, dynamically built SQL.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re

PACKAGE = "microduck_companion"
SQL_METHODS = {"execute", "executemany", "executescript"}
STATEMENTS = {
    "create": re.compile(r"\bCREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"\[]?([A-Za-z_]\w*)", re.I),
    "insert": re.compile(r"\bINSERT\s+(?:OR\s+\w+\s+)?INTO\s+[\"\[]?([A-Za-z_]\w*)", re.I),
    "replace": re.compile(r"\bREPLACE\s+INTO\s+[\"\[]?([A-Za-z_]\w*)", re.I),
    "update": re.compile(r"\bUPDATE\s+[\"\[]?([A-Za-z_]\w*)\s+SET\b", re.I),
    "delete": re.compile(r"\bDELETE\s+FROM\s+[\"\[]?([A-Za-z_]\w*)", re.I),
}
DESTRUCTIVE = re.compile(r"\b(?:DROP\s+TABLE|ATTACH\s+DATABASE|DETACH\s+DATABASE)\b", re.I)


def _literal_sql(expr: ast.AST) -> str | None:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        left = _literal_sql(expr.left)
        right = _literal_sql(expr.right)
        return left + right if left is not None and right is not None else None
    return None


def _is_read_only(connect_call: ast.Call) -> bool:
    uri = any(k.arg == "uri" and isinstance(k.value, ast.Constant)
              and k.value.value is True for k in connect_call.keywords)
    if not uri or not connect_call.args:
        return False
    return any(isinstance(n, ast.Constant) and isinstance(n.value, str)
               and "?mode=ro" in n.value for n in ast.walk(connect_call.args[0]))


class SourceScanner(ast.NodeVisitor):
    def __init__(self, module: str) -> None:
        self.module = module
        self.sqlite_names = {"sqlite3"}
        self.connect_names: set[str] = set()
        self.sql_sites: list[dict] = []
        self.connection_sites: list[dict] = []
        self.dynamic_sql_sites: list[dict] = []
        self.destructive_sites: list[dict] = []

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            if item.name == "sqlite3":
                self.sqlite_names.add(item.asname or item.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "sqlite3":
            for item in node.names:
                if item.name == "connect":
                    self.connect_names.add(item.asname or item.name)

    def visit_Call(self, node: ast.Call) -> None:
        f = node.func
        is_connect = (
            isinstance(f, ast.Attribute) and f.attr == "connect"
            and isinstance(f.value, ast.Name) and f.value.id in self.sqlite_names
        ) or (isinstance(f, ast.Name) and f.id in self.connect_names)
        if is_connect:
            self.connection_sites.append({
                "module": self.module, "line": node.lineno,
                "mode": "read_only_uri" if _is_read_only(node) else "write_capable_or_unknown",
            })
        if isinstance(f, ast.Attribute) and f.attr in SQL_METHODS:
            sql = _literal_sql(node.args[0]) if node.args else None
            if sql is None:
                self.dynamic_sql_sites.append({
                    "module": self.module, "line": node.lineno, "method": f.attr,
                })
            else:
                for operation, expression in STATEMENTS.items():
                    for match in expression.finditer(sql):
                        self.sql_sites.append({
                            "module": self.module, "line": node.lineno,
                            "operation": operation, "table": match.group(1).lower(),
                        })
                if DESTRUCTIVE.search(sql):
                    self.destructive_sites.append({"module": self.module, "line": node.lineno})
                for match in STATEMENTS["delete"].finditer(sql):
                    if match.group(1).lower() == "f4a_property_hypotheses":
                        remainder = sql[match.end():].split(";", 1)[0]
                        if not re.search(r"\bWHERE\s+active\s*=\s*1\b", remainder, re.I):
                            self.destructive_sites.append({
                                "module": self.module, "line": node.lineno,
                                "reason": "unbounded correction tombstone deletion",
                            })


def scan_source(source: str, module: str) -> dict:
    tree = ast.parse(source, filename=module)
    scanner = SourceScanner(module)
    # Resolve import aliases first; never execute any imported module.
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            scanner.visit_Import(node)
        elif isinstance(node, ast.ImportFrom):
            scanner.visit_ImportFrom(node)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            scanner.visit_Call(node)
    return {
        "sql_sites": scanner.sql_sites,
        "connection_sites": scanner.connection_sites,
        "dynamic_sql_sites": scanner.dynamic_sql_sites,
        "destructive_sites": scanner.destructive_sites,
    }


def scan_tree(root: Path) -> dict:
    base = root / PACKAGE
    if not base.is_dir():
        raise ValueError("Companion package not found")
    report: dict = {
        "schema": "n3-sqlite-source-inventory-v1",
        "scope": "static source, never connects to DB",
        "modules_scanned": 0,
        "tables": [], "connection_sites": [],
        "dynamic_sql_sites": [], "destructive_sites": [],
        "cross_module_writes": [],
    }
    sql_sites: list[dict] = []
    for path in sorted(base.rglob("*.py")):
        if path.is_symlink():
            raise ValueError("Refuse symlink source: " + str(path))
        part = scan_source(path.read_text(encoding="utf-8"), path.relative_to(base).as_posix())
        report["modules_scanned"] += 1
        for key in ("connection_sites", "dynamic_sql_sites", "destructive_sites"):
            report[key].extend(part[key])
        sql_sites.extend(part["sql_sites"])
    tables: dict[str, dict] = {}
    for site in sql_sites:
        table = site["table"]
        item = tables.setdefault(table, {
            "table": table, "schema_modules": set(), "writers": set(),
            "write_operations": set(), "write_sites": [],
        })
        if site["operation"] == "create":
            item["schema_modules"].add(site["module"])
        else:
            item["writers"].add(site["module"])
            item["write_operations"].add(site["operation"])
            item["write_sites"].append(site)
    for table, obj in sorted(tables.items()):
        item = {
            "table": table,
            "schema_modules": sorted(obj["schema_modules"]),
            "writers": sorted(obj["writers"]),
            "write_operations": sorted(obj["write_operations"]),
            "write_sites": sorted(obj["write_sites"],
                                  key=lambda s: (s["module"], s["line"], s["operation"])),
        }
        report["tables"].append(item)
        for writer in item["writers"]:
            if item["schema_modules"] and writer not in item["schema_modules"]:
                report["cross_module_writes"].append({
                    "table": table, "module": writer, "owners": item["schema_modules"],
                })
    report["sql_literal_sites"] = len(sql_sites)
    report["table_count"] = len(report["tables"])
    return report


def enforce_non_destructive_boundaries(report: dict) -> None:
    """N3 source-level regressions only, NOT a comprehensive security proof."""
    connections = report["connection_sites"]
    owners = [x for x in connections if x["mode"] != "read_only_uri"]
    if len(owners) != 1 or owners[0]["module"] != "episodic_memory.py":
        raise ValueError("Unexpected second writable/unknown SQLite connection; review required")
    unexpected_ro = sorted({x["module"] for x in connections
                            if x["mode"] == "read_only_uri"
                            and x["module"] != "kwipi_journal.py"})
    if unexpected_ro:
        raise ValueError("Unexpected read-only SQLite connection location; review required: "
                         + ", ".join(unexpected_ro))
    if report["destructive_sites"]:
        raise ValueError("Destructive SQL or deletion of durable corrections; review required")
    table_map = {x["table"]: x for x in report["tables"]}
    for table, owner in {
        "f4a_property_hypotheses": "category_semantics.py",
        "m1a_compact_patterns": "compact_multimodal_memory.py",
        "m1b_groups": "multiview_pattern_memory.py",
        "m1b_signatures": "multiview_pattern_memory.py",
    }.items():
        found = table_map.get(table)
        if found is None or found["schema_modules"] != [owner]:
            raise ValueError("Critical historical table missing or multiply owned: " + table)
    for item in report["tables"]:
        if len(item["schema_modules"]) > 1:
            raise ValueError("Multiple DDL owners for " + item["table"])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    report = scan_tree(args.root)
    # Preserve a source-only diagnostic even when a conservative gate fails.
    # Never include paths to user databases, SQL arguments or their values.
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized)
    enforce_non_destructive_boundaries(report)
    print("N3 read-only: modules=%d tables=%d read-only-connections=%d cross-writer-sites=%d" % (
        report["modules_scanned"], report["table_count"],
        sum(x["mode"] == "read_only_uri" for x in report["connection_sites"]),
        len(report["cross_module_writes"])))


if __name__ == "__main__":
    main()
