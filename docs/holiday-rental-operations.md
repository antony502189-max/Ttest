# Spain holiday discovery and refresh

The residential province index does not describe vacation supply. Use a separate
`province:<canonical province>:holiday` scope for vacation catalogues. It retains
the existing source identity, canonical upsert, distributed lease, request
budgets and persisted discovery/detail continuation. Residential scopes and
their routes/checkpoints are independent.

Pisos publishes its vacation province destinations through the anonymous search
widget. The adapter reads the audited public vacation seed's `hdnSearchContext`,
then requests the widget's `FilterGeo/GetChildren` endpoint with an empty ancestor.
It takes `DestinationUrl` verbatim from positive-count Spanish province rows.
No province or municipality URL is generated. Zero-count rows without a URL and
foreign territories are excluded. Province names and route names must agree.

Read-only discovery and live route validation:

```bash
python -m app.commands.provision_external_spain --sources Pisos \
  --rental-mode holiday --output var/holiday-routes.json
```

This does not enable or write scopes. Audit details with the existing
`audit_external_sources.audit_source` workflow, recording bedrooms, provider
category, original price, parsed amount/period, rejection reason and photos.
Curate a manifest containing only productive, verified routes. Provision with
`--manifest <file> --apply --enable` only after that detail audit, then import
under the existing shared lease using `external_import.run_source` and bounded
page/detail windows. All provider HTTP requests run outside DB transactions.

Holiday scopes accept only independently validated holiday prices and the
supported individual-room/studio/one-bedroom taxonomy. Monthly recommendations
are rejected without modifying source records belonging to a residential scope.
Unsupported types, ambiguous cadence and missing location/bedroom evidence remain
rejections. Weekly conversion and original source price provenance are unchanged.

Do not replace a residential scope with vacation routes. Do not clear an existing
residential checkpoint to make room for vacation discovery. Existing automatic
scope scheduling resumes the separate vacation checkpoint across restarts;
incomplete windows cannot remove unseen offers. The independent six-hour removal
checks continue with their existing unknown/challenge/mass-removal safeguards.

ThinkSpain stays opt-in. On 2026-10-08 its anonymous VPS holiday request returned
an empty HTTP 202 challenge response. Public search-engine visibility does not
establish an operational import contract. Do not enable it or bypass the challenge
until anonymous discovery, detail extraction and normalization have been verified.
