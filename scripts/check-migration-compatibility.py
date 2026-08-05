#!/usr/bin/env python3
"""Enforce immutable deployed history and expand-only future Alembic upgrades."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MIGRATIONS = Path("backend/alembic/versions")
BASELINE_FILE = Path("backend/alembic/rollback-compatibility-baseline.json")
PROHIBITED_SQL = (
    (re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE), "DROP TABLE"),
    (re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE), "DROP COLUMN"),
    (re.compile(r"\bDROP\s+CONSTRAINT\b", re.IGNORECASE), "DROP CONSTRAINT"),
    (re.compile(r"\bRENAME\s+(?:TABLE|COLUMN)\b", re.IGNORECASE), "schema rename"),
    (re.compile(r"\bALTER\s+TABLE\b[\s\S]*?\bRENAME\b", re.IGNORECASE), "ALTER TABLE RENAME"),
    (re.compile(r"\bALTER\s+TABLE\b[\s\S]*?\bALTER\s+COLUMN\b[\s\S]*?\bTYPE\b", re.IGNORECASE), "column type replacement"),
    (re.compile(r"\bALTER\s+TABLE\b[\s\S]*?\bALTER\s+COLUMN\b[\s\S]*?\bSET\s+NOT\s+NULL\b", re.IGNORECASE), "NOT NULL tightening"),
    (re.compile(r"\bALTER\s+TABLE\b[\s\S]*?\bALTER\s+COLUMN\b[\s\S]*?\bDROP\s+DEFAULT\b", re.IGNORECASE), "default removal"),
    (re.compile(r"\bALTER\s+TABLE\b[\s\S]*?\bADD\s+CONSTRAINT\b", re.IGNORECASE), "constraint addition"),
    (re.compile(r"\bADD\s+COLUMN\b[\s\S]*?\bNOT\s+NULL\b", re.IGNORECASE), "non-null column addition"),
    (re.compile(r"\bCREATE\s+UNIQUE\s+INDEX\b", re.IGNORECASE), "unique index addition"),
    (re.compile(r"\bTRUNCATE\b", re.IGNORECASE), "TRUNCATE"),
    (re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE), "irreversible row deletion"),
)
PROHIBITED_OP_METHODS = {
    "drop_table",
    "drop_column",
    "rename_table",
    "drop_constraint",
    "create_check_constraint",
    "create_foreign_key",
    "create_primary_key",
    "create_unique_constraint",
}
SQL_METHODS = {"execute", "exec_driver_sql"}


@dataclass(frozen=True)
class Migration:
    path: Path
    tree: ast.Module
    revision: str
    parents: tuple[str, ...]


def assigned_literal(tree: ast.Module, name: str) -> Any:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = node.targets
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        else:
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            try:
                return ast.literal_eval(value)
            except (TypeError, ValueError):
                raise SystemExit(f"{name} must be a literal in an Alembic migration") from None
    raise SystemExit(f"missing {name} in an Alembic migration")


def normalize_parents(value: Any, path: Path) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (tuple, list)) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise SystemExit(f"{path}: unsupported down_revision {value!r}")


def load_migrations() -> dict[str, Migration]:
    migrations: dict[str, Migration] = {}
    for path in sorted(MIGRATIONS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        revision = assigned_literal(tree, "revision")
        if not isinstance(revision, str):
            raise SystemExit(f"{path}: revision must be a string")
        if revision in migrations:
            raise SystemExit(f"duplicate Alembic revision: {revision}")
        migrations[revision] = Migration(
            path=path,
            tree=tree,
            revision=revision,
            parents=normalize_parents(assigned_literal(tree, "down_revision"), path),
        )
    for migration in migrations.values():
        for parent in migration.parents:
            if parent not in migrations:
                raise SystemExit(f"{migration.path}: missing parent revision {parent}")
    return migrations


def historical_revisions(migrations: dict[str, Migration], baseline: str) -> set[str]:
    if baseline not in migrations:
        raise SystemExit(f"rollback compatibility baseline revision is missing: {baseline}")
    historical: set[str] = set()
    pending = [baseline]
    while pending:
        revision = pending.pop()
        if revision in historical:
            continue
        historical.add(revision)
        pending.extend(migrations[revision].parents)
    return historical


def verify_historical_hashes(migrations: dict[str, Migration], historical: set[str], manifest: dict[str, Any]) -> None:
    hashes = manifest.get("files")
    if not isinstance(hashes, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in hashes.items()):
        raise SystemExit("rollback compatibility baseline has an invalid files map")
    expected_names = {migrations[revision].path.name for revision in historical}
    if set(hashes) != expected_names:
        missing = sorted(expected_names - set(hashes))
        extra = sorted(set(hashes) - expected_names)
        raise SystemExit(f"rollback baseline file set mismatch: missing={missing}, extra={extra}")
    for revision in sorted(historical):
        path = migrations[revision].path
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != hashes[path.name]:
            raise SystemExit(f"deployed migration history is immutable: {path}")


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
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "text" and node.args:
        return constant_text(node.args[0], constants)
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                resolved = constant_text(value.value, constants)
                if resolved is None:
                    return None
                parts.append(resolved)
            else:
                return None
        return "".join(parts)
    return None


def reachable_upgrade_functions(tree: ast.Module, path: Path) -> list[ast.FunctionDef]:
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
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


def keyword_value(call: ast.Call, name: str) -> ast.AST | None:
    return next((keyword.value for keyword in call.keywords if keyword.arg == name), None)


def literal_false(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


def literal_none(node: ast.AST | None) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


def inspect_future_migration(migration: Migration) -> list[str]:
    constants = string_constants(migration.tree)
    violations: list[str] = []
    for function in reachable_upgrade_functions(migration.tree, migration.path):
        for node in ast.walk(function):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            method = node.func.attr
            if method in PROHIBITED_OP_METHODS:
                violations.append(f"{migration.path}:{node.lineno}: {method} is not expand-compatible")
            if method == "alter_column":
                if keyword_value(node, "new_column_name") is not None or keyword_value(node, "type_") is not None:
                    violations.append(f"{migration.path}:{node.lineno}: alter_column rename/type change is forbidden")
                if literal_false(keyword_value(node, "nullable")):
                    violations.append(f"{migration.path}:{node.lineno}: nullable=False tightening is forbidden")
                if literal_none(keyword_value(node, "server_default")):
                    violations.append(f"{migration.path}:{node.lineno}: removing a server default is forbidden")
            if method == "add_column" and len(node.args) >= 2 and isinstance(node.args[1], ast.Call):
                column = node.args[1]
                if literal_false(keyword_value(column, "nullable")) and keyword_value(column, "server_default") is None:
                    violations.append(f"{migration.path}:{node.lineno}: a non-null column requires a server default")
            if method in SQL_METHODS and node.args:
                sql = constant_text(node.args[0], constants)
                if sql is None:
                    violations.append(f"{migration.path}:{node.lineno}: SQL is not statically inspectable")
                    continue
                for pattern, description in PROHIBITED_SQL:
                    if pattern.search(sql):
                        violations.append(f"{migration.path}:{node.lineno}: {description} is forbidden in upgrade()")
    return violations


manifest = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
baseline = manifest.get("baseline_revision")
if not isinstance(baseline, str):
    raise SystemExit("rollback compatibility baseline_revision must be a string")
migrations = load_migrations()
historical = historical_revisions(migrations, baseline)
verify_historical_hashes(migrations, historical, manifest)
violations: list[str] = []
for revision, migration in sorted(migrations.items()):
    if revision not in historical:
        violations.extend(inspect_future_migration(migration))
if violations:
    raise SystemExit("\n".join(violations))
print(f"deployed migration history is immutable; future upgrades after {baseline} are expand-compatible")
