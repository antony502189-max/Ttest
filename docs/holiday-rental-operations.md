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

Holiday discovery also follows published `/alquilar/atico-` detail links. A
penthouse becomes an apartment candidate only when its own `gaCusVar` field
explicitly declares `tipoInmueble:'aticos'` and no conflicting structured type
exists. The existing bedroom and price rules still decide admission. This was
verified against one-bedroom public details in Roquetas de Mar and Torrox;
two-bedroom, monthly, missing-price and unknown-type examples remain excluded.
Residential discovery and the product taxonomy are unchanged.

Pisos's photo counter can count a repeated cover as a second primary-gallery
entry. Completeness therefore also accepts all advertised, trusted primary
entries when they yield fewer unique photos. The stored gallery stays unique;
a genuinely missing entry still defers replacement of existing media.

### Existing residential offer seen in a holiday catalogue

The provider may advertise the same URL in residential and holiday search results.
`SourceRecord` identity is global to the provider URL/external ID, not scoped
to a route. If the incoming rental mode conflicts with the existing canonical,
or a holiday scope attempts to take ownership of a residential source (or vice
versa), the importer now records a `scope_conflict`, leaves the existing source
and canonical unchanged, and treats that source run as partial. Such overlaps
require explicit operator review; do not force an in-place conversion of a
published monthly listing into a nightly listing. Ordinary monthly price
refreshes in the original residential scope remain permitted.

A changed aggregate long-term inventory checksum is a **stop-and-diagnose**
signal, not proof of corruption. Compare changed listing IDs and individual
fields against the pre-import snapshot, the normal two-hour worker's run log,
and audit timestamps. Separate expected background updates (prices, photos,
availability) from any holiday-triggered mode/scope changes. Do not resume
further holiday bootstrap tranches until unexpected cross-mode writes are
ruled out, and do not roll back legitimate unrelated residential updates.

Do not replace a residential scope with vacation routes. Do not clear an existing
residential checkpoint to make room for vacation discovery. Existing automatic
scope scheduling resumes the separate vacation checkpoint across restarts;
incomplete windows cannot remove unseen offers. The independent six-hour removal
checks continue with their existing unknown/challenge/mass-removal safeguards.

ThinkSpain stays opt-in. On 2026-10-08 its anonymous VPS holiday request returned
an empty HTTP 202 challenge response. Public search-engine visibility does not
establish an operational import contract. Do not enable it or bypass the challenge
until anonymous discovery, detail extraction and normalization have been verified.
