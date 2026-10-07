# PR #287: bounded holiday discovery review (2026-10-07)

Follow-up to reviewed head `1bedfa4ea9b6b9839533c9427e511369ff5d4271`.
This audit used public navigation/index/search evidence and small HTTP samples,
without DB writes, browser challenge interaction or blocked-source retries.
It is route evidence, not a projection of 500 accepted holiday canonicals.

| Source | Holiday catalogue / published route | Province route / validation | Accepted sample | Pagination | Provisioning |
|---|---|---|---|---|---|
| Pisos | [Public Málaga catalogue](https://www.pisos.com/alquiler-vacacional/pisos-malaga/), provider-indexed and self-linked, HTTP 200 | Málaga province; three sampled detail provinces all Málaga; own detail scope checks still reject mismatches | 1/3 accepted: one-bedroom Casares offer, 110 EUR/day, explicit holiday category; 3-bedroom and price-on-request rejected | Published `/2/` followed: two pages, 45 URLs, explicitly partial | Added this exact audited holiday URL to existing Málaga definition alongside the original long URL; live revalidation remains mandatory |
| Fotocasa | Published agency holiday URL found in provider search evidence | Live [agency URL](https://www.fotocasa.es/es/inmobiliaria-actual-servicios-inmobiliarios/alquiler-vacacional/inmuebles/espana/todas-las-zonas/l?clientId=9202752251634) actually served an agency SALES catalogue; homepage had no published holiday links | 0 accepted, sale details deliberately not imported | Holiday pagination not validated | None: neither genuine reachable holiday catalogue nor safe provincial index confirmed |
| Habitaclia | Homepage and current Tenerife catalogue inspected; no separate holiday navigation/index confirmed | Existing catalogue is mixed rental; keyword-only holiday content does not establish a provincial holiday route | No dedicated holiday sample established | Existing ordinary rental pagination retained; holiday pagination unconfirmed | None: no published scalable provincial holiday route established in this bounded audit |

Budget: three provider homepages, one current Habitaclia catalogue, one indexed
Fotocasa agency route, and Pisos first/two-page discovery plus three details.
Three homepages were inadvertently fetched a second time by a research-helper
import side effect; the helper was corrected and no further duplicate research
was performed. No additional provider research was needed after the Pisos
contract was established. Idealista/Milanuncios/ThinkSpain were not retried.
PisoCompartido/ADC/Flatio were not re-researched without clear new evidence.

The Pisos catalogue publishes the province URL, municipality subroutes, unit
filters (including studios) and next-page hrefs. A provincial route is safer
than the previously inspected Catalunya regional page, which leaked geography.
The three-detail sample shows no wrong province, but does not prove every
recommendation on every page is local: structured province admission continues
to enforce the scope on each detail. No regional page is treated as provincial.
Only the exact verified Málaga URL is added; no 52-province holiday slug
expansion or hypothetical provider routes are generated.

The successful sample was the real public detail
[Casares one-bedroom holiday offer](https://www.pisos.com/alquilar/apartamento-casares_costa29690-63355430971_108500/).
Its structured bedroom span is 1, displayed primary price is 110 EUR/day,
and provider breadcrumbs identify holiday/Málaga/Casares. The other two
sampled offers remain rejected without weakening price or bedroom admission.

## Resulting operator contract

`--target-total 2500 --target-holiday-min 500` is the default objective.
`--target` remains the total alias. Satisfied means BOTH thresholds reached.
Operational exhaustion/budget stops explicitly report false holiday satisfaction
and return apply exit code 2. There is no inference that 2600 long / 0 holiday
satisfies the inventory goal. `--target-holiday-min 0` is an explicit operator
opt-out, not a default. Source health remains a separate existing contract.

Only Pisos/PisoCompartido retain automatic scalable province provisioning.
Pisos Málaga now has a verified holiday entry as well as long discovery; no
additional provider gained nationwide holiday provisioning. The 500 holiday
objective remains **unproven**. No monthly or ambiguous temporada offer was
relabeled, no inactive/blocked source enabled, and no production action taken.
