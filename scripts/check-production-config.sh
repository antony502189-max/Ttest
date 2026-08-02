#!/usr/bin/env bash
set -euo pipefail

# Static CI gate: use deliberately fake values and never start a container.
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

docker compose --profile ops -f docker-compose.production.yml config --quiet
for script in deploy/*.sh; do
  bash -n "$script"
done
grep -Fq 'location /api/' deploy/nginx.conf
grep -Fq 'proxy_pass http://backend:8000;' deploy/nginx.conf
grep -Fq 'Cross-Origin-Opener-Policy "same-origin-allow-popups"' deploy/nginx.conf
grep -Fq 'location = /privacidad' deploy/nginx.conf
grep -Fq 'location = /terminos' deploy/nginx.conf
grep -Fq 'https://$domain/api/health/live' deploy/smoke-production.sh
grep -Fq 'https://$domain/api/health/ready' deploy/smoke-production.sh
grep -Fq 'https://$domain/api/v1/listings' deploy/smoke-production.sh
grep -Fq 'expected $path to return 404' deploy/smoke-production.sh
grep -Fq 'for _ in $(seq 1 30); do' deploy/smoke-production.sh
test -s public/privacidad/index.html
test -s public/terminos/index.html
grep -Fq 'Política de privacidad' public/privacidad/index.html
grep -Fq 'Términos de uso' public/terminos/index.html
# A backup manifest must be generated outside the mirrored tree to avoid
# including itself and making every restore verification fail.
grep -Fq '> /tmp/backup-manifest' deploy/backup-minio.sh
grep -Fq 'cp /tmp/backup-manifest .backup-manifest' deploy/backup-minio.sh

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
if services["frontend"].get("depends_on", {}).get("backend", {}).get("condition") != "service_healthy":
    raise SystemExit("frontend must wait for a ready backend")
if config["networks"].get("application", {}).get("internal") is not True:
    raise SystemExit("application network must be internal")
if config["networks"].get("egress", {}).get("internal") is True:
    raise SystemExit("egress network must allow outbound connectivity")
if not config["networks"].get("traefik", {}).get("external"):
    raise SystemExit("Traefik network must be an existing external network")
for name in {"postgres", "redis", "minio", "minio-init", "migrate"}:
    if set(services[name].get("networks", [])) != {"application"}:
        raise SystemExit(f"{name} must only join the application network")
for name in {"backend", "mail-worker", "external-listings-worker"}:
    if set(services[name].get("networks", [])) != {"application", "egress"}:
        raise SystemExit(f"{name} must join application and egress networks")
if set(services["frontend"].get("networks", [])) != {"application", "traefik"}:
    raise SystemExit("frontend must join both application and Traefik networks")
'
