# External import catalog contract

An external source is useful only when a discovered detail completes normalization and is persisted as a public room listing.

## Repository guarantees

The PostgreSQL integration lifecycle verifies that:

1. the first external `upsert` creates a published external listing and increments the catalog version;
2. an identical payload is idempotent;
3. a richer duplicate from another source updates the same canonical listing rather than creating a second card;
4. the updated primary source is returned by `/api/v1/listings/search` with its source URL and price text;
5. removing one source promotes the remaining active duplicate while keeping the card public;
6. removing the final active source closes the canonical listing, increments the catalog version and removes the card from public search.

The production worker health contract is stricter than process liveness: at least three configured sources must each discover a URL, fetch a detail and accept a valid room during a useful import cycle.

## Post-deploy verification

After deploying a new release, verify on the VPS that:

- the external worker container is healthy and its heartbeat is current;
- the latest worker state reports at least three useful sources;
- recent import-run rows contain accepted rooms rather than empty successful runs;
- active source records reference published canonical listings;
- a sampled imported listing appears through the public search API;
- closing the sampled source in a transaction or dedicated staging drill removes it from public search and advances the catalog version.

Do not infer production database state from CI. CI proves code and isolated integration behavior; the deployed scheduler, worker and production data require server-side verification.
