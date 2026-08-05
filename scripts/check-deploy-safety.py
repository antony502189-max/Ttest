#!/usr/bin/env python3
"""Static fail-closed assertions for the production release transaction."""

from pathlib import Path


SCRIPT = Path("deploy/deploy-release.sh")
text = SCRIPT.read_text(encoding="utf-8")

required_fragments = {
    "exact main SHA gate": '[[ "$SHA" == "$main_sha" ]]',
    "historical release guidance": "use rollback-release.sh for an older release",
    "writer quiescence": '"${previous_compose[@]}" stop frontend backend mail-worker external-listings-worker',
    "old PostgreSQL backup runtime": 'COMPOSE_FILE="$old_release/docker-compose.production.yml"',
    "audited PostgreSQL backup script": '"$release/deploy/backup-postgres.sh"',
    "audited MinIO backup script": '"$release/deploy/backup-minio.sh"',
    "orphan-volume refusal": "persistent production volumes exist but there is no current release",
    "backup runtime metadata": "backup_runtime_sha=%s",
}
for description, fragment in required_fragments.items():
    if fragment not in text:
        raise SystemExit(f"deploy safety check missing {description}: {fragment}")

orphan_refusal_position = text.index("persistent production volumes exist but there is no current release")
metadata_position = text.index("status=in_progress")
if not orphan_refusal_position < metadata_position:
    raise SystemExit("orphan persistent volumes must fail before deployment metadata enters in_progress")

stop_position = text.index(
    '"${previous_compose[@]}" stop frontend backend mail-worker external-listings-worker'
)
postgres_backup_position = text.index('"$release/deploy/backup-postgres.sh"')
minio_backup_position = text.index('"$release/deploy/backup-minio.sh"')
new_dependencies_position = text.index('"${compose[@]}" up -d postgres redis minio minio-init')
migration_position = text.index('"${compose[@]}" run --rm migrate')

if not stop_position < postgres_backup_position < new_dependencies_position:
    raise SystemExit("PostgreSQL backup must run after writer quiescence and before new dependency images")
if not stop_position < minio_backup_position < new_dependencies_position:
    raise SystemExit("MinIO backup must run after writer quiescence and before new dependency images")
if not new_dependencies_position < migration_position:
    raise SystemExit("new dependencies must become healthy before migrations run")

ancestor_gate = 'merge-base --is-ancestor "$SHA" origin/main'
if ancestor_gate in text:
    raise SystemExit("historical commits must not pass the normal production deploy path")

print("production deploy transaction ordering is fail-closed")


rollback_text = Path("deploy/rollback-release.sh").read_text(encoding="utf-8")
rollback_required = {
    "deployment metadata lookup": 'metadata="$ROOT/releases/$current_sha.deploy-info"',
    "recorded previous SHA": "s/^old_sha=//p",
    "explicit recovery target": "usage: $0 [target-release-sha]",
    "exact target directory": 'previous="$ROOT/releases/$target_sha"',
}
for description, fragment in rollback_required.items():
    if fragment not in rollback_text:
        raise SystemExit(f"rollback safety check missing {description}: {fragment}")
if 'find "$ROOT/releases"' in rollback_text or "sort -nr" in rollback_text:
    raise SystemExit("rollback must not infer the target from directory modification times")

postgres_backup_text = Path("deploy/backup-postgres.sh").read_text(encoding="utf-8")
if "pg_isready" not in postgres_backup_text or "seq 1 60" not in postgres_backup_text:
    raise SystemExit("PostgreSQL backup must wait for database readiness with a bounded retry")
minio_backup_text = Path("deploy/backup-minio.sh").read_text(encoding="utf-8")
if "MinIO did not become ready for backup" not in minio_backup_text or '"$attempt" -lt 60' not in minio_backup_text:
    raise SystemExit("MinIO backup must wait for service readiness with a bounded retry")
