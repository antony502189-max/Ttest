# Property province search and owner municipality TOP

Search uses `provincia=28` for Madrid and `provincia=38` for Santa Cruz de Tenerife.
Municipality selection adds its five-digit INE code, for example
`q=Adeje&provincia=38&municipio=38001` or `q=Arafo&provincia=38&municipio=38004`.
Suggestions cover all 8,132 municipalities, appear from the first letter, and
narrow by name/word prefix without requiring accents. Official trailing articles
and bilingual names are accepted. Exact names rank first, then recent selections
and matching places in the last selected province. This is local deterministic
ranking; it does not train an ML model or request GPS permission.

The server validates municipality/province consistency and applies both the
province and exact normalized city aliases to cards, map requests and counts.
Legacy listings without a province remain searchable only when their city alias
identifies one municipality in the national catalogue; ambiguous names never
match another province through this fallback.
Municipality suggestions do not display province-wide listing counts. Saved
searches keep the municipality code in existing filter metadata and preserve it
in restored links and notifications. No database migration is required.
`scripts/build-municipality-catalog.py` updates both frontend/backend catalogues.
Existing `comunidad` deep links remain compatible. The catalogue covers 50 provinces
and two autonomous cities using INE province codes. Saved searches persist the
explicit province; legacy city searches keep their city interpretation.

Property geography and TOP capacity are different scopes. The product owner
confirmed that TOP means three distinct listings per **municipality of the owner**,
using the owner's address. Geocoder verification is sufficient; proof of residence
is not required. The bundled official INE catalogue contains 8,132 municipal codes,
which are not postcodes.

## Addresses and catalogue

Publication/address edits are checked by the backend against CartoCiudad IGN/CNIG:
country, street, building number, postcode, municipality and map point must agree.
Unavailable verification returns503; inconsistent input returns422. Client
coordinates may be within250m of the resolved portal. Native, smart and fallback
address selection cover Spain, including the islands, Ceuta and Melilla.
City remains resolved address metadata, without a manual city dropdown.

`Listing.province_code` is the canonical search source. Imports receive it from
consistent structured source evidence without inventing a postcode. Cards, map,
counts and alerts use the same geography. A legacy postcode read fallback remains
until old local addresses are explicitly verified. Public responses expose the
province code, without private streets/postcodes or the owner's private address.

## TOP lifecycle

The owner verifies their private address in the profile using `PUT /users/me/address`;
`GET /users/me/address` is owner-only. The server resolves the INE municipality and
freezes it on the payment order and promotion. The owner's municipality cannot move
while any owned listing has active TOP or an unsettled purchase. Initial verification
of unassociated legacy accounts is allowed, but never silently reassigns their service.

Three distinct listings may reserve a municipality across both rental modes.
Active/scheduled windows and unresolved Stripe checkouts count; renewal counts the
same listing once. Checkout, fulfillment, admin promotion and financial restoration
use the existing transaction advertising lock. Reservations commit before Stripe IO.
Every financial expansion/revival checks the complete interval, even when an order
was already labelled fulfilled.

Legacy admin PUT/DELETE cannot overwrite a live paid/pending entitlement. Restore
checks the real projection and retains its original paid period. Hourly and legacy daily/monthly
fulfillment repeat full eligibility. Moderation/withdrawal or a published listing
returning to pending sends active paid TOP to review and keeps its reserved
interval/history; refund/restoration uses audited payment resolution.

`/payments/listings/{id}/top/availability?durationHours=12` returns `municipalityCode`,
`municipality`, capacity, earliest start and server time. The existing dialog uses
monotonic server-relative `HH:MM:SS`, polls every15s and rechecks at zero. Zero,
unknown release time and provider errors cannot authorize payment.

## Migration and rollout

Apply `alembic upgrade head` through `0065_verified_geography`, following the existing
`0064_hourly_promotion_orders` migration in a single linear chain. TOP purchases
use server-owned tariffs: 12 hours for €0.99, 24 hours for €1.70, and 72 hours for €4.50.
Legacy day/month orders retain their purchased periods. Start with:

```text
python -m app.commands.backfill_geography --expected-database DATABASE_NAME
```

This is a rollback-only dry-run. Review unknown addresses and overlapping TOP windows;
owners verify their own address, never infer it from a property. Explicit operator
`--apply` fills validated imported provinces. `--apply --bind-top` also binds reviewed
legacy TOP to verified owners and refuses unknown/overbooked pools. No service period
is deleted/shortened by backfill. Active unknown legacy TOP associations conservatively
block new purchases until reconciled.

The remediation did not migrate production or perform real payments. See
[the remediation report](../FULL_PROJECT_REMEDIATION_REPORT.md) for exact gates,
T01–T30/A–J evidence, source references and remaining operational limits.

The mobile province list opens when its search box receives focus; initial entry
keeps all three map alternatives visible. Province suggestions use the existing
light palette. Desktop legacy zone selection still applies directly to the URL.
Older explicitly chosen municipality metadata remains covered as restored draft
state; the current publication UI never offers a municipality dropdown.
