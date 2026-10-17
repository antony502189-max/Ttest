# Province search and TOP capacity

Search uses `provincia=28` for Madrid and `provincia=38` for Santa Cruz de Tenerife.
Existing `comunidad` deep links remain compatible. The catalog covers the 50
provinces and two autonomous cities using [INE province codes](https://www.ine.es/daco/daco42/codmun/cod_provincia.htm).

Publication and editing derive a read-only province from the Spanish postcode
returned with the selected address. There is no municipality dropdown. The
municipality remains address metadata populated by Google address selection or
reverse geocoding. Selection supports mainland Spain and the islands. Existing
form, dialog, buttons, colors and layout classes are reused.

Search requests carry `provinceCode`; cards, map searches and province counts use
the same database expression. Public responses expose the province code without
exposing private postcodes or streets.

TOP capacity is three distinct listings per province across both rental modes.
Active and scheduled windows and unconfirmed Stripe checkouts reserve capacity.
A renewal occupies the same listing slot. Checkout, payment fulfillment, admin
promotion and financial restoration all check capacity under the existing
transaction-level advertising lock. Reservations commit before contacting Stripe.
Changing province is blocked while TOP or an unresolved checkout exists, including
updates to several rooms at the same address.

The owner-only `/payments/listings/{id}/top/availability?days=10` endpoint returns
province, capacity, earliest available start and server time. The existing dialog
uses server-relative monotonic time for `HH:MM:SS`, polls every 15 seconds and
rechecks at zero. Zero does not enable payment without server confirmation.
Provider confirmation and legacy permanent TOP can make release time unknown;
the UI explains this instead of inventing a purchase time. Late paid orders that
cannot fit remain available for review/refund without displacing current places.

Before production rollout, audit legacy addresses without valid Spanish postcodes
and provinces with more than three historical TOP listings. Existing paid
entitlements are not silently deleted or shortened. Addresses without valid
postcodes cannot buy TOP and do not appear in provincial search until corrected.
No database schema migration is needed.

Validation: TypeScript, production build, `npm run test:provinces`, and backend
`tests/test_province_top.py` plus payment, search and privacy regressions. Browser
tests cover 320px and 1280px dialogs, countdown, automatic availability refresh,
separate Canary provinces and automatic address selection in Madrid.
PostgreSQL concurrency tests require an isolated test database; Docker was not
running in the implementation environment.
