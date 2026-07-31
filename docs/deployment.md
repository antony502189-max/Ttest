# Deployment

Production deployment is self-hosted on the VPS `31.97.185.84`. The React frontend is built into the `frontend` nginx container and is routed by the existing Traefik instance together with FastAPI under `https://112233.es`. It does not use GitHub Pages, Vercel, Netlify, a separate static host, localhost, or a mock backend.

The production compose stack is `docker-compose.production.yml`. It provides PostgreSQL 16/PostGIS, Redis with AOF persistence, private MinIO media storage, FastAPI, a persistent SMTP outbox worker, an external-listings worker, and the frontend. Only Traefik publishes ports 80 and 443; application services are isolated on the Docker network.

Deploy only a tested, merged `main` commit using the controlled scripts in `deploy/`. Full prerequisites, server locations, exact commands, backup/restore, rollback, monitoring, incident response and reboot checks are documented in [Production operations](production-operations.md). Production secrets live solely in `/srv/112233.es/shared/production.env` with mode `600`.

Google Maps remains a browser integration, not a server secret. Restrict its key to the production HTTPS referrers and required APIs before putting it in the VPS env file.
