# Database and migrations

The production database is PostgreSQL with PostGIS. The Docker image is `postgis/postgis:16-3.4`.

Core tables include `users`, `auth_sessions`, `password_reset_tokens`, `email_verification_tokens`, `mail_outbox`, `media_assets`, `listing_images`, `listings`, `favorites`, `discarded_listings`, `saved_searches`, `search_history`, `message_threads`, `messages`, `reports`, `listing_views`, `listing_status_history` and `audit_logs`.

`listings.location` is the public approximate PostGIS point; `exact_location` is private. The schema has GIST and composite/partial indexes for public listing search, owner dashboards, expiry, publication time and room counts. PostgreSQL check constraints enforce nonnegative prices/deposits, positive area, bedroom count 1–99, room capacity 1–2, ordered availability dates and the required primary price for each rental mode. Token tables contain hashes, never raw tokens.

Apply from an empty database:

```bash
docker compose up -d postgres
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend alembic current
```

The current migration head is `0015_integrity_constraints`. Development demo data is idempotent and is prohibited when `APP_ENV=production`:

```bash
docker compose --profile tools run --rm seed
```

Create a local database backup:

```bash
docker compose --profile tools run --rm db-backup
```

Production must use encrypted scheduled backups and periodically test restoration into an isolated database.
