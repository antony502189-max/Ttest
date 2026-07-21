# Screenshot-locked parity report

Date: 2026-07-22
Reference baseline: `e38bc3524f0ea05074e0888d50089ce52b0a9e2b`

## Scope reviewed

- Read the four required pack documents and the supporting screen contract/customer analysis.
- Reviewed all 115 selected target frames plus the target contact sheets and 19 comparison boards.
- Kept the implementation frontend-only and Tenerife-only.
- Reused the existing `112233.es` brand, project photography and open-source icons; no Idealista logo, code, trackers, APIs or proprietary image assets were imported.

## Implemented parity deltas

- Added data-derived, maximum-two-line critical restriction overlays to the promoted image, first result image, detail gallery, selected map preview and publication preview.
- Made image, title, price and the main non-control card body valid links while keeping favorite, carousel, contact and overflow controls independent.
- Reordered and compacted the full-screen location flow to match the target action hierarchy; municipality/barrio selection is a secondary state rather than an initial checklist.
- Locked the mobile result, map, filter, menu, owner and publish headers to the compact lime app-bar geometry.
- Added the missing advertiser-comment presentation and honest device-only user comments with create/edit/delete, user scoping and account-deletion cleanup.
- Added compact owner listing rows and an owner edit app bar.
- Added save-search actions to dedicated mobile results/map headers.
- Corrected the listing action order and added a magenta sticky contact action that does not overlap the five-item bottom navigation.
- Kept the publication preview on the same crop and overlay rules as the live cards.

## Evidence

- `before-live/`: 15 unmasked live captures taken before the parity changes.
- `after-live/`: 30 unmasked captures covering responsive home, location states, selected-zone results, filter scroll states, sort, list/map, map drawing and selected listing, detail/comments, menu/messages, owner/profile/edit, publish restrictions/preview and Russian states.
- `comparisons/`: 15 `TARGET | BEFORE-LIVE | AFTER-LIVE` comparison boards.

The original before-live run did not include a dedicated owner-edit or owner-list route. Those two comparison boards explicitly label the closest captured owner-area baseline rather than presenting a reconstructed image as live evidence. Their target and after-live columns are route-specific.

## Verification results

- `npm run build`: pass.
- `npm run typecheck`: pass.
- `npm run lint`: pass.
- Screenshot-locked evidence capture: 1/1 pass, 30 frames, no horizontal overflow assertion failures.
- Reviewed visual baseline suite: 7/7 pass after snapshot refresh.
- Targeted accessibility/behavior gate: 44/44 pass.
- Full Playwright gate: 111/112 pass; the only failure was an obsolete assertion expecting the global bottom navigation inside the screenshot-contracted full-screen publish wizard. The assertion was updated to require no bottom navigation and visible in-viewport wizard actions, then its complete responsive matrix passed 1/1. All 112 distinct current cases therefore have passing evidence.
- Axe checks: 28 route/state checks with 0 serious and 0 critical violations in scope.

Accessibility verification used WCAG 2.2 AA as the review baseline and covered automated axe checks, keyboard focus/return, dialog escape/trapping, named map/gallery controls, no nested interactive controls, touch-size assertions, mobile reflow and sticky-action overlap. This is not a legal certification and did not include a manual screen-reader session.

## Reproducible evidence tests

- `tests/screenshot-locked-contract.spec.ts`
- `tests/screenshot-locked-evidence.spec.ts`
- `playwright.reuse.config.ts`
