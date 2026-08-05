#!/usr/bin/env python3
"""Reject schema-destructive Alembic upgrades that break code rollback.

Production deploys may temporarily restore the previous application release after
an unsuccessful rollout. Every upgrade therefore has to follow an expand-first
policy: adding tables/columns/indexes/constraints and relaxing nullability is
allowed, while removal, rename, truncation and type replacement must be split
into a later release after the old code is no longer a rollback target.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


MIGRATIONS = Path("backend/alembic/versions")
PROHIBITED_SQL = (
    (re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE), "DROP TABLE"),
    (re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE), "DROP COLUMN"),
    (re.compile(r"\bRENAME\s+(?:TABLE|COLUMN)\b", re.IGNORECASE), "schema rename"),
    (re.compile(r"\bALTER\s+TABLE\b[\s\S]*?\bRENAME\b", re.IGNORECASE), "ALTER TABLE RENAME"),
    (
        re.compile(
            r"\bALTER\s+(?:TABLE\b[\s\S]*?\bCOLUMN\b|COLUMN\b)[\s\S]*?\bTYPE\b",
            re.IGNORECASE,
        ),
        "column type replacement",
    ),
    (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), "TRUNCATE"),
)
PROHIBITED_OP_METHODS = {"drop_table", "drop_column", "rename_table"}


def string_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    changed = True
    while changed:
        changed = False
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value_node = node.value
            if value_node is None:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = constant_text(value_node, constants)
            if value is None:
                continue
            for target in targets:
                if isinstance(target, ast.Name) and constants.get(target.id) != value:
                    constants[target.id] = value
                    changed = True
    return constants


def constant_text(node: ast.AST, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = constant_text(node.left, constants)
        right = constant_text(node.right, constants)
        if left is not None and right is not None:
            return left + right
        return None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                resolved = constant_text(value.value, constants)
                parts.append(resolved if resolved is not None else "__EXPRESSION__")
            else:
                return None
        return "".join(parts)
    return None


def reachable_upgrade_functions(tree: ast.Module, path: Path) -> list[ast.FunctionDef]:
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    upgrade = functions.get("upgrade")
    if upgrade is None:
        raise SystemExit(f"{path}: missing upgrade() function")

    reachable: list[ast.FunctionDef] = []
    pending = [upgrade]
    visited: set[str] = set()
    while pending:
        function = pending.pop()
        if function.name in visited:
            continue
        visited.add(function.name)
        reachable.append(function)
        for node in ast.walk(function):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                helper = functions.get(node.func.id)
                if helper is not None and helper.name not in visited:
                    pending.append(helper)
    return reachable


violations: list[str] = []
for path in sorted(MIGRATIONS.glob("*.py")):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    constants = string_constants(tree)

    for function in reachable_upgrade_functions(tree, path):
        for node in ast.walk(function):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue

            method = node.func.attr
            if method in PROHIBITED_OP_METHODS:
                violations.append(f"{path}:{node.lineno}: {method} is not rollback-compatible")
            if method == "alter_column":
                keyword_names = {keyword.arg for keyword in node.keywords if keyword.arg is not None}
                if "new_column_name" in keyword_names or "type_" in keyword_names:
                    violations.append(
                        f"{path}:{node.lineno}: alter_column rename/type change is not rollback-compatible"
                    )

            if method == "execute" and node.args:
                sql = constant_text(node.args[0], constants)
                if sql is None:
                    violations.append(
                        f"{path}:{node.lineno}: execute() SQL is not statically inspectable; use a literal or module string constant"
                    )
                    continue
                for pattern, description in PROHIBITED_SQL:
                    if pattern.search(sql):
                        violations.append(f"{path}:{node.lineno}: {description} is forbidden in upgrade()")

if violations:
    raise SystemExit("\n".join(violations))

print("Alembic upgrades preserve previous-release schema compatibility")
