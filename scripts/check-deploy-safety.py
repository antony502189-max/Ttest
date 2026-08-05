#!/usr/bin/env python3
"""Static fail-closed assertions for the production release transaction."""

from pathlib import Path


SCRIPT = Path("deploy/deploy-release.sh")
text = SCRIPT.read_text(encoding="utf-8")

worktree_requirements = (
    "verify_release_worktree()",
    "rev-parse --verify HEAD",
    "rev-parse --git-common-dir",
    "status --porcelain --untracked-files=all",
    "release worktree is not immutable and clean",
)
required_fragments = {
    "restrictive process umask": "umask 077",
    "exact main SHA gate": '[[ "$SHA" == "$main_sha" ]]',
    "historical release guidance": "use rollback-release.sh for an older release",
    "shared release lock": 'LOCK_FILE="$ROOT/shared/release.lock"',
    "non-blocking release serialization": "flock -n 9",
    "inherited release lock": "export RELEASE_LOCK_HELD=1",
    "new worktree verification": 'verify_release_worktree "$release" "$SHA"',
    "current worktree verification": 'verify_release_worktree "$old_release" "$old_sha"',
    "stateful image comparison": 'python3 "$release/deploy/data-service-images.py"',
    "stateful image refusal": "stateful service image changes require a separate controlled data-service migration",
    "writer quiescence": '"${previous_compose[@]}" stop frontend backend mail-worker external-listings-worker',
    "old PostgreSQL backup runtime": 'COMPOSE_FILE="$old_release/docker-compose.production.yml"',
    "audited PostgreSQL backup script": '"$release/deploy/backup-postgres.sh"',
    "audited MinIO backup script": '"$release/deploy/backup-minio.sh"',
    "orphan-volume refusal": "persistent production volumes exist but there is no current release",
    "backup runtime metadata": "backup_runtime_sha=%s",
    "dependency rollback": '"${previous_compose[@]}" up -d postgres redis minio minio-init',
    "bounded automatic rollback readiness": "automatic rollback failed readiness",
}
for fragment in worktree_requirements:
    if fragment not in text:
        raise SystemExit(f"deploy worktree verification requirement missing: {fragment}")
for description, fragment in required_fragments.items():
    if fragment not in text:
        raise SystemExit(f"deploy safety check missing {description}: {fragment}")

lock_position = text.index("flock -n 9")
fetch_position = text.index('git -C "$REPO" fetch')
new_verify_position = text.index('verify_release_worktree "$release" "$SHA"')
new_compose_position = text.index('\ncompose=(docker compose')
if not lock_position < fetch_position:
    raise SystemExit("release lock must be acquired before repository or runtime mutation")
if not new_verify_position < new_compose_position:
    raise SystemExit("new release worktree must be verified before Compose reads it")

orphan_refusal_position = text.index("persistent production volumes exist but there is no current release")
image_gate_position = text.index("stateful service image changes require a separate controlled data-service migration")
metadata_position = text.index("status=in_progress")
if not orphan_refusal_position < metadata_position:
    raise SystemExit("orphan persistent volumes must fail before deployment metadata enters in_progress")
if not image_gate_position < metadata_position:
    raise SystemExit("stateful image changes must fail before deployment metadata or runtime mutation")

stop_position = text.index(
    '"${previous_compose[@]}" stop frontend backend mail-worker external-listings-worker'
)
postgres_backup_position = text.index('"$release/deploy/backup-postgres.sh"')
minio_backup_position = text.index('"$release/deploy/backup-minio.sh"')
new_dependencies_position = text.rindex('"${compose[@]}" up -d postgres redis minio minio-init')
migration_position = text.index('"${compose[@]}" run --rm migrate')

if not image_gate_position < stop_position:
    raise SystemExit("stateful image compatibility must be verified before writers stop")
if not stop_position < postgres_backup_position < new_dependencies_position:
    raise SystemExit("PostgreSQL backup must run after writer quiescence and before new dependency images")
if not stop_position < minio_backup_position < new_dependencies_position:
    raise SystemExit("MinIO backup must run after writer quiescence and before new dependency images")
if not new_dependencies_position < migration_position:
    raise SystemExit("new dependencies must become healthy before migrations run")

ancestor_gate = 'merge-base --is-ancestor "$SHA" origin/main'
if ancestor_gate in text:
    raise SystemExit("historical commits must not pass the normal production deploy path")

image_helper = Path("deploy/data-service-images.py").read_text(encoding="utf-8")
for fragment in ('("postgres", "redis", "minio")', '"@sha256:"', "Compose config is missing"):
    if fragment not in image_helper:
        raise SystemExit(f"stateful image helper requirement missing: {fragment}")

print("production deploy transaction ordering is fail-closed")


rollback_text = Path("deploy/rollback-release.sh").read_text(encoding="utf-8")
rollback_required = {
    "restrictive process umask": "umask 077",
    "deployment metadata lookup": 'metadata="$ROOT/releases/$current_sha.deploy-info"',
    "recorded previous SHA": "s/^old_sha=//p",
    "explicit recovery target": "usage: $0 [target-release-sha]",
    "exact target directory": 'previous="$RELEASES/$target_sha"',
    "shared release lock": 'LOCK_FILE="$ROOT/shared/release.lock"',
    "non-blocking release serialization": "flock -n 9",
    "current worktree verification": 'verify_release_worktree "$current" "$current_sha"',
    "target worktree verification": 'verify_release_worktree "$previous" "$target_sha"',
    "rollback image comparison": 'python3 "$SCRIPT_DIR/data-service-images.py"',
    "rollback image refusal": "rollback across stateful service image changes requires a separate controlled data-service recovery",
    "target dependency activation": '"${compose[@]}" up -d postgres redis minio minio-init',
    "current dependency recovery": '"${current_compose[@]}" up -d postgres redis minio minio-init',
    "current release recovery": "restore_current_after_failure",
    "bounded target readiness": "for _ in $(seq 1 30); do",
    "manual incident escalation": "manual incident response is required",
}
for fragment in worktree_requirements:
    if fragment not in rollback_text:
        raise SystemExit(f"rollback worktree verification requirement missing: {fragment}")
for description, fragment in rollback_required.items():
    if fragment not in rollback_text:
        raise SystemExit(f"rollback safety check missing {description}: {fragment}")
if 'find "$ROOT/releases"' in rollback_text or "sort -nr" in rollback_text:
    raise SystemExit("rollback must not infer the target from directory modification times")
if rollback_text.index("flock -n 9") > rollback_text.index('current="$(readlink -f "$CURRENT")"'):
    raise SystemExit("rollback lock must be acquired before release state is read")
if rollback_text.index('verify_release_worktree "$current" "$current_sha"') > rollback_text.index('current_compose=(docker compose'):
    raise SystemExit("current release worktree must be verified before Compose reads it")
if rollback_text.index('verify_release_worktree "$previous" "$target_sha"') > rollback_text.index('\ncompose=(docker compose'):
    raise SystemExit("rollback target worktree must be verified before Compose reads it")
if rollback_text.index("rollback across stateful service image changes") > rollback_text.index("trap restore_current_after_failure ERR"):
    raise SystemExit("rollback image compatibility must fail before target runtime mutation")
if rollback_text.index("trap restore_current_after_failure ERR") > rollback_text.index('"${compose[@]}" up -d postgres redis minio minio-init'):
    raise SystemExit("rollback recovery trap must be armed before target dependencies are changed")

backup_production_text = Path("deploy/backup-production.sh").read_text(encoding="utf-8")
for fragment in ("umask 077", 'LOCK_FILE="$ROOT/shared/release.lock"', "flock -n 9", "export RELEASE_LOCK_HELD=1"):
    if fragment not in backup_production_text:
        raise SystemExit(f"production backup must share release serialization: {fragment}")
if backup_production_text.index("flock -n 9") > backup_production_text.index('"$release_dir/deploy/backup-postgres.sh"'):
    raise SystemExit("production backup must acquire the shared lock before child backups")

for backup_path, readiness_fragments in (
    (Path("deploy/backup-postgres.sh"), ("pg_isready", "seq 1 60")),
    (Path("deploy/backup-minio.sh"), ("MinIO did not become ready for backup", '"$attempt" -lt 60')),
):
    backup_text = backup_path.read_text(encoding="utf-8")
    required = (
        '${RELEASE_LOCK_HELD:-0}',
        'readlink -f "/proc/$$/fd/9"',
        'readlink -f "$LOCK_FILE"',
        "RELEASE_LOCK_HELD is set without the inherited production release lock",
        "flock -n 9",
        *readiness_fragments,
    )
    for fragment in required:
        if fragment not in backup_text:
            raise SystemExit(f"{backup_path} safety requirement missing: {fragment}")

backup_crypto_text = Path("deploy/backup-crypto.sh").read_text(encoding="utf-8")
if 'stat -c %a "$env_file"' not in backup_crypto_text or "must have mode 600" not in backup_crypto_text:
    raise SystemExit("shared backup key loader must reject non-private production env files")

for restore_path in (Path("deploy/restore-verify.sh"), Path("deploy/restore-minio-verify.sh")):
    restore_text = restore_path.read_text(encoding="utf-8")
    for fragment in ("umask 077", '"$ROOT/shared/release.lock"', "flock -n 9"):
        if fragment not in restore_text:
            raise SystemExit(f"{restore_path} must serialize restore drills: {fragment}")
