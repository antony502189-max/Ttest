# Database and migrations

The production database is PostgreSQL with PostGIS. The Docker image is `postgis/postgis:16-3.4`.

Core tables include `users`, `auth_sessions`, `password_reset_tokens`, `email_verification_tokens`, `mail_outbox`, `media_assets`, `listing_images`, `listings`, `favorites`, `discarded_listings`, `saved_searches`, `search_history`, `message_threads`, `messages`, `reports`, `listing_views`, `listing_status_history` and `audit_logs`.

`listings.location` is the public approximate PostGIS point; `exact_location` is private. The schema has indexes for public listing state, owner, expiry, published time and geospatial queries. Token tables contain SHA-256/HMAC-style hashes from the security layer, not raw tokens.

Apply from an empty database:

```bash
docker compose up -d postgres
docker compose run --rm backend alembic upgrade head
docker compose run --rm backend alembic current
```

The current migration head is `0013_mail_outbox`. Development demo data is idempotent and is prohibited when `APP_ENV=production`:

```bash
docker compose run --rm backend python -m app.commands.seed
```
