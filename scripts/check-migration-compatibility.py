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
    (re.compile(r"\bALTER\s+(?:TABLE\b[\s\S]*?\bCOLUMN\b|COLUMN\b)[\s\S]*?\bTYPE\b", re.IGNORECASE), "column type replacement"),
    (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), "TRUNCATE"),
)
PROHIBITED_OP_METHODS = {"drop_table", "drop_column", "rename_table"}


def upgrade_node(tree: ast.Module, path: Path) -> ast.FunctionDef:
    matches = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade"]
    if len(matches) != 1:
        raise SystemExit(f"{path}: expected exactly one upgrade() function")
    return matches[0]


def constant_text(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            else:
                parts.append("__EXPRESSION__")
        return "".join(parts)
    return None


violations: list[str] = []
for path in sorted(MIGRATIONS.glob("*.py")):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    upgrade = upgrade_node(tree, path)

    for node in ast.walk(upgrade):
        if not isinstance(node, ast.Call):
            continue

        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in PROHIBITED_OP_METHODS:
                violations.append(f"{path}:{node.lineno}: op.{method} is not rollback-compatible")
            if method == "alter_column":
                keyword_names = {keyword.arg for keyword in node.keywords if keyword.arg is not None}
                if "new_column_name" in keyword_names or "type_" in keyword_names:
                    violations.append(
                        f"{path}:{node.lineno}: alter_column rename/type change is not rollback-compatible"
                    )

            if method == "execute" and node.args:
                sql = constant_text(node.args[0])
                if sql is not None:
                    for pattern, description in PROHIBITED_SQL:
                        if pattern.search(sql):
                            violations.append(f"{path}:{node.lineno}: {description} is forbidden in upgrade()")

if violations:
    raise SystemExit("\n".join(violations))

print("Alembic upgrades preserve previous-release schema compatibility")
