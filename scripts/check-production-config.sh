#!/usr/bin/env bash
set -euo pipefail

# Static CI gate: use deliberately fake values and never start application containers.
export APP_DOMAIN=example.test
export POSTGRES_PASSWORD=ci-placeholder-password
export DATABASE_URL=postgresql+asyncpg://ttest:ci-placeholder-password@postgres:5432/ttest
export JWT_SECRET=ci-placeholder-secret-with-at-least-32-characters
export EMAIL_VERIFICATION_HMAC_SECRET=ci-independent-verification-secret-32-plus
export GOOGLE_CLIENT_ID=ci-google-client-id.apps.googleusercontent.com
export VITE_GOOGLE_CLIENT_ID=ci-google-client-id.apps.googleusercontent.com
export REDIS_URL=redis://redis:6379/0
export MINIO_ROOT_USER=ci-minio
export MINIO_ROOT_PASSWORD=ci-placeholder-password
export S3_BUCKET=ttest-media
export S3_ENDPOINT_URL=http://minio:9000
export S3_ACCESS_KEY=ci-minio
export S3_SECRET_KEY=ci-placeholder-password
export SMTP_HOST=smtp.example.test
export SMTP_FROM=noreply@example.test
export TRAEFIK_NETWORK=traefik-public
export TRAEFIK_ENTRYPOINT=websecure
export TRAEFIK_CERT_RESOLVER=letsencrypt
export BACKUP_ENCRYPTION_KEY=ci-encryption-secret-with-at-least-32-characters
export BACKUP_AUTHENTICATION_KEY=ci-authentication-secret-with-at-least-32-characters

docker compose --profile ops -f docker-compose.production.yml config --quiet
for script in deploy/*.sh; do
  bash -n "$script"
done
python3 scripts/check-deploy-safety.py
python3 scripts/check-migration-compatibility.py

grep -Fq 'location /api/' deploy/nginx.conf
grep -Fq 'proxy_pass http://backend:8000;' deploy/nginx.conf
grep -Fq 'proxy_set_header X-Real-IP $trusted_client_ip;' deploy/nginx.conf
grep -Fq 'proxy_set_header X-Forwarded-For $trusted_client_ip;' deploy/nginx.conf
grep -Fq 'limit_req zone=api_per_ip' deploy/nginx.conf
grep -Fq 'limit_req zone=api_writes_per_ip' deploy/nginx.conf
grep -Fq 'limit_conn connections_per_ip' deploy/nginx.conf
if grep -Eq '^[[:space:]]*proxy_cache(_path|[[:space:]])' deploy/nginx.conf; then
  echo 'shared proxy caching is forbidden for mutable-visibility media' >&2
  exit 1
fi
grep -Fq 'Cross-Origin-Opener-Policy "same-origin-allow-popups"' deploy/nginx.conf
grep -Fq 'Strict-Transport-Security "max-age=31536000"' deploy/nginx.conf
grep -Fq 'location = /privacidad' deploy/nginx.conf
grep -Fq 'location = /terminos' deploy/nginx.conf
grep -Fq 'location = /favicon.svg' deploy/nginx.conf
grep -Fq 'try_files /favicon.svg =404;' deploy/nginx.conf
grep -Fq 'https://$domain/api/health/live' deploy/smoke-production.sh
grep -Fq 'https://$domain/api/health/ready' deploy/smoke-production.sh
grep -Fq 'https://$domain/api/v1/listings' deploy/smoke-production.sh
grep -Fq 'expected $path to return 404' deploy/smoke-production.sh
grep -Fq 'for _ in $(seq 1 30); do' deploy/smoke-production.sh
test -s public/privacidad/index.html
test -s public/terminos/index.html
grep -Fq 'Política de privacidad' public/privacidad/index.html
grep -Fq 'Términos de uso' public/terminos/index.html
grep -Fq 'BACKUP_AUTHENTICATION_KEY=' deploy/production.env.example
grep -Fq 'MAX_MEDIA_ASSETS_PER_USER=100' deploy/production.env.example
grep -Fq 'MAX_MEDIA_BYTES_PER_USER=268435456' deploy/production.env.example
grep -Fq 'MAX_LISTING_COLLECTION_ITEMS_PER_USER=500' deploy/production.env.example
grep -Fq 'EXTERNAL_IMPORT_MIN_HEALTHY_SOURCES=3' deploy/production.env.example
# A backup manifest must be generated outside the mirrored tree to avoid
# including itself and making every restore verification fail.
grep -Fq '> /tmp/backup-manifest' deploy/backup-minio.sh
grep -Fq 'cp /tmp/backup-manifest .backup-manifest' deploy/backup-minio.sh
grep -Fq 'verify_backup_authentication' deploy/restore-verify.sh
grep -Fq 'verify_backup_authentication' deploy/restore-minio-verify.sh

# Exercise the exact HMAC implementation used on the VPS. A modified encrypted
# file must fail authentication even when an attacker can replace plain hashes.
backup_test_dir="$(mktemp -d)"
cleanup_backup_test() { rm -rf "$backup_test_dir"; }
trap cleanup_backup_test EXIT
# shellcheck source=deploy/backup-crypto.sh
source deploy/backup-crypto.sh
printf 'encrypted-backup-placeholder' > "$backup_test_dir/backup.enc"
write_backup_hmac "$backup_test_dir/backup.enc"
verify_backup_authentication "$backup_test_dir/backup.enc"
printf 'tampered' >> "$backup_test_dir/backup.enc"
if verify_backup_authentication "$backup_test_dir/backup.enc" 2>/dev/null; then
  echo 'tampered backup unexpectedly passed authentication' >&2
  exit 1
fi
cleanup_backup_test
trap - EXIT

# Parse the exact production nginx file in the pinned runtime image. The fake
# backend host avoids DNS failure during nginx -t without starting the stack.
docker run --rm \
  --add-host backend:127.0.0.1 \
  --mount type=bind,src="$PWD/deploy/nginx.conf",dst=/etc/nginx/conf.d/default.conf,readonly \
  nginxinc/nginx-unprivileged:1.27-alpine@sha256:65e3e85dbaed8ba248841d9d58a899b6197106c23cb0ff1a132b7bfe0547e4c0 nginx -t

docker compose --profile ops -f docker-compose.production.yml config --format json | python3 -c '
import json
import sys

config = json.load(sys.stdin)
services = config["services"]
required = {"postgres", "redis", "minio", "minio-init", "migrate", "backend", "mail-worker", "external-listings-worker", "frontend"}
missing = required - services.keys()
if missing:
    raise SystemExit(f"missing production services: {sorted(missing)}")
public_ports = {name: service["ports"] for name, service in services.items() if service.get("ports")}
if public_ports:
    raise SystemExit(f"application services must not publish host ports: {sorted(public_ports)}")
for name in {"postgres", "redis", "minio", "backend", "mail-worker", "external-listings-worker", "frontend"}:
    if services[name].get("restart") != "unless-stopped":
        raise SystemExit(f"{name} must use restart: unless-stopped")
if "healthcheck" not in services["external-listings-worker"]:
    raise SystemExit("external-listings-worker must have a healthcheck")
if "healthcheck" not in services["mail-worker"]:
    raise SystemExit("mail-worker must have a healthcheck")
if services["frontend"].get("labels", {}).get("traefik.enable") != "true":
    raise SystemExit("frontend must be exposed only through Traefik")
router_rule = services["frontend"].get("labels", {}).get("traefik.http.routers.ttest.rule", "")
if "www." in router_rule or router_rule.count("Host(") != 1:
    raise SystemExit("frontend must expose exactly one application host")
backend_env = services["backend"].get("environment", {})
if backend_env.get("FRONTEND_ORIGINS") != "https://example.test":
    raise SystemExit("backend CORS must allow only the application host")
if backend_env.get("EMAIL_VERIFICATION_HMAC_SECRET") != "ci-independent-verification-secret-32-plus":
    raise SystemExit("backend must receive the dedicated verification HMAC secret")
if backend_env.get("PASSWORD_WORK_CONCURRENCY") != "2":
    raise SystemExit("backend must receive the bounded password-work setting")
if backend_env.get("MAX_MEDIA_ASSETS_PER_USER") != "100":
    raise SystemExit("backend must receive the per-user media asset quota")
if backend_env.get("MAX_MEDIA_BYTES_PER_USER") != "268435456":
    raise SystemExit("backend must receive the per-user media byte quota")
if backend_env.get("MAX_LISTING_COLLECTION_ITEMS_PER_USER") != "500":
    raise SystemExit("backend must receive the per-user listing collection quota")
if backend_env.get("EXTERNAL_IMPORT_MIN_HEALTHY_SOURCES") != "3":
    raise SystemExit("external worker must require three healthy production sources")
if services["frontend"].get("depends_on", {}).get("backend", {}).get("condition") != "service_healthy":
    raise SystemExit("frontend must wait for a ready backend")
if config["networks"].get("data", {}).get("internal") is not True:
    raise SystemExit("data network must be internal")
if config["networks"].get("application", {}).get("internal") is not True:
    raise SystemExit("application network must be internal")
if config["networks"].get("egress", {}).get("internal") is True:
    raise SystemExit("egress network must allow outbound connectivity")
if not config["networks"].get("traefik", {}).get("external"):
    raise SystemExit("Traefik network must be an existing external network")
for name in {"postgres", "redis", "minio", "minio-init", "migrate"}:
    if set(services[name].get("networks", [])) != {"data"}:
        raise SystemExit(f"{name} must only join the data network")
if set(services["backend"].get("networks", [])) != {"application", "data", "egress"}:
    raise SystemExit("backend must join application, data, and egress networks")
for name in {"mail-worker", "external-listings-worker"}:
    if set(services[name].get("networks", [])) != {"data", "egress"}:
        raise SystemExit(f"{name} must join data and egress networks")
if set(services["frontend"].get("networks", [])) != {"application", "traefik"}:
    raise SystemExit("frontend must join only application and Traefik networks")
frontend_networks = set(services["frontend"].get("networks", []))
for name in {"postgres", "redis", "minio"}:
    if frontend_networks & set(services[name].get("networks", [])):
        raise SystemExit(f"frontend must not share a network with {name}")
'
