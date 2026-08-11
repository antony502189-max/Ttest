# Tenerife room-source research — 2026-08-11

This record is the evidence gate for anonymous automated ingestion.  It is not
permission to work around a source's access controls.  All checks used the
production VPS (`31.97.185.84`), a descriptive `112233.es room-source
suitability audit` user agent, and low request volume.

## Acceptance rule

An adapter is eligible only when it provides public, genuine room rentals in
the target province; its applicable robots policy does not disallow the chosen
HTML/sitemap route; normal anonymous VPS access succeeds without a challenge;
and the route exposes a stable source identity and enough listing data to make
a conservative room import.  Public sales and entire-home catalogues are not
room sources.

## Requested candidates

| Source | Robots / terms | VPS evidence | Catalogue and data | Verdict |
| --- | --- | --- | --- | --- |
| Tenerife Properties (`tenerifeproperties.net`) | Robots allows public property routes, but its legal notice prohibits reproduction, copying, distribution, public communication, transformation and permanent storage/diffusion without authorization. | HTTPS `200`; public WordPress sitemap. | Sales-only property catalogue. | **FAIL** — both incompatible content terms and wrong inventory. |
| FRINA Tenerife Property (`tenerife-property.com`) | Robots allows `/`; advertised compressed sitemap was not available at `/sitemap.xml` (`406`). | HTTPS `200`; robots `200`; sitemap route `406`. | Public material and property PDFs are sales inventory, not rooms. | **FAIL** — no room catalogue. |
| Realty Tenerife (`realtytenerife.com`) | Robots supplies a sitemap; no room-specific policy route found. The linked privacy route redirected outside the expected domain during the audit. | HTTPS `200`; robots `200`; sitemap `200`. | Sitemap contains sales and whole-apartment inventory; no room catalogue. | **FAIL** — wrong inventory and elevated ownership/maintenance risk. |
| Spanish Dream / Property Tenerife (`property-tenerife.es`) | No usable `www` robots or sitemap route (`404`). | `www` home, robots and sitemap all `404`; the public non-`www` listing material is reachable. | Sales/whole-property management catalogue, not room rentals. | **FAIL** — no room inventory or stable catalogue endpoint. |
| Tenerife Properties ES (`tenerifeproperties.es`) | Robots allows public posts, but legal notice restricts reproduction, permanent storage and dissemination of content. | HTTPS `200`; robots `200`; sitemap `200`. | Property catalogue is not room rentals. | **FAIL** — incompatible terms and wrong inventory. |
| Tenerife Property Shop (`tenerifepropertyshop.es`) | Robots has no broad listing disallow, but policy/navigation resolves across `.es` and `.com`. | HTTPS `200`; robots `200`; sitemap `200`. | Sales-led property catalogue; no room route identified. | **FAIL** — wrong inventory and unstable policy ownership boundary. |

## Independently discovered candidates

| Source | Robots / terms | VPS evidence | Catalogue and data | Verdict |
| --- | --- | --- | --- | --- |
| Alquiler Docente Canarias (`alquilerdocentecanarias.com`) | Robots permits the sitemap/detail paths used. Its published “Terms and Conditions” page is a privacy-policy template and contains no automated-extraction prohibition. | HTTPS/robots/sitemap/details all `200`; 1.4–3.3 s for the observed public routes; no challenge, `403` or `429`. | Public `estate_property` sitemap currently exposes 270 Canary properties, including 11 room URLs that explicitly identify the target province or a Santa Cruz municipality. Pages provide a stable property ID, canonical URL, title, price/period, description, city, address, property size, bedrooms/bathrooms, update text and public image. Two independently checked Tenerife room pages were current within a week of the audit. | **PASS / INTEGRATE** — sitemap-scoped, room-only adapter; no public contact data is persisted. |
| Habitaclia (`habitaclia.com`) | Robots does not broadly disallow room pages. | Home/robots `200`, but the project’s documented Tenerife room route returned deterministic `404` twice. | No stable public room route for the required Tenerife scope. | **FAIL** — stale route; retain only as research guardrail. |
| Yaencontre (`yaencontre.com`) | Access policy could not be evaluated because anonymous access was denied. | VPS home, robots and sitemap each returned `403` with CAPTCHA/access-denial markers. | No compliant catalogue access. | **FAIL** — access controlled; no bypass attempted. |
| Promocasa (`promocasa.com`) | Public WordPress robots/sitemap routes. | HTTPS, robots and sitemap `200`; Cloudflare branding only, no challenge. | Long-term whole-home rentals, not room ads. | **FAIL** — wrong inventory. |
| Realax Properties (`realaxproperties.co`) | Shopify robots permits public product pages but forbids transactional paths. | HTTPS, robots and sitemap `200`; no challenge. | Entire-home rental/management offering rather than room adverts. | **FAIL** — wrong inventory. |
| Q-Rort (`q-rort.com`) | Robots and sitemap both `404`. | HTTPS `200`; no public sitemap/robots policy file. | Whole-home sale/long-term rental agency, no room catalogue. | **FAIL** — wrong inventory and weak discovery contract. |
| Taoro Coliving (`taorocoliving.com`) | Robots permits `/rooms` but disallows the booking/API surfaces. | Robots, sitemap and `/rooms` all `200`; five named rooms are public. | Marketing page has fixed room descriptions/prices but no public per-room availability/status feed; booking is a transaction flow. | **DEFER** — useful room product, but static marketing content cannot truthfully be ingested as current availability. |

## Alquiler Docente Canarias production test samples

Two public Tenerife room detail pages were checked from the VPS on 2026-08-11,
two seconds apart.  Both returned `200` HTML, a canonical final URL and an
individual WordPress property ID.  The first showed a monthly room price, a
La Laguna locality and a recent update date; the second showed a different
monthly room price, included-bills text, property size and the same locality.
Their public page structure is server-rendered and contained JSON-LD plus an
Open Graph image.  Contact information present in the public pages is
deliberately discarded by the adapter.

The public property sitemap exposes the full Canary catalogue.  The adapter
does **not** crawl that general catalogue: it accepts only sitemap URLs whose
path explicitly says `habitacion` and whose path identifies a Santa Cruz de
Tenerife location.  It rejects Las Palmas paths before any detail request.

## Monitor interpretation

The current monitor is intentionally stricter than the worker's critical
minimum.  It declares a source useful only when its latest completed run is
`success`, discovery is complete, and discovered/fetched/accepted room
counters are all positive.  It returns `1` below
`EXTERNAL_IMPORT_MIN_HEALTHY_SOURCES` (currently `3`), and returns `2` when
the minimum is met but useful sources are fewer than all configured sources.
Thus the observed `3/6` is a degraded warning (`rc=2`), not a critical
three-source failure.  This branch does not change that logic or its
thresholds.

## Future-crawl transition and historical preservation

`Fotocasa`, `PisoCompartido` and `Pisos` remain enabled because their latest
production runs satisfy the useful-source contract.  `Idealista` and
`Milanuncios` are removed from the versioned default future-crawl set because
they deny compliant anonymous access; `ThinkSpain` is removed because its
room-strict importer remains partial with no accepted room.  Their adapter
classes and all existing `ExternalListingSource`/listing rows are retained.
The first subsequent full cycle retires their active source records: it
promotes an active duplicate when one exists, otherwise closes the canonical
listing with `source_retired`. No source identifier is reused and no historical
data is deleted.

The approved default is therefore
`fotocasa,pisocompartido,pisos,alquilerdocentecanarias`.  It is a
source-quality decision, not a monitor workaround: all four must still produce
a complete successful import with positive discovery, detail and room counters
for the monitor to return `rc=0`.

## Scoring

| Candidate | Compliance | VPS availability | Data quality | Maintenance risk | Incremental value | Score / decision |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Alquiler Docente Canarias | 8 | 9 | 8 | 5 | 5 | **35/50 — integrate** |
| Taoro Coliving | 6 | 9 | 4 | 7 | 2 | **28/50 — defer** |
| Habitaclia | 5 | 3 | 0 | 7 | 8 | **23/50 — reject** |
| Promocasa | 7 | 8 | 2 | 4 | 0 | **21/50 — reject** |
| Realax Properties | 7 | 8 | 2 | 6 | 0 | **23/50 — reject** |
| Yaencontre | 0 | 0 | 0 | 8 | 8 | **16/50 — reject** |

The remaining named agencies score below these candidates because their
catalogues are sales-only, their terms forbid the required content use, or
their policy/discovery boundaries are unreliable.  They are not implemented
solely to inflate monitor counts.
