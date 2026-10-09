# Mobile search hidden-home work

## Finding

On a mobile `/buscar` route, `AppLayout` mounts both `MobileAppV2` and the
full-screen `MobileSearchResults` portal. `tabFromPath('/buscar')` resolves to
`home`, so `HomeScreen` remains mounted behind the results surface. Its effects
fetch the homepage hero and commercial-advertisement list, while its hero
background and optional promoted image can load even though search covers the
home content.

The production audit reproduced this on direct mobile search: the mobile hero
background was about 112 KB and the homepage hero/ad media about 35.7 KB. Those
bytes compete with visible search results and the first listing photo. A
matched local measurement below estimates app behavior with controlled
fixtures; it is not a production latency result.

## Change and behavior preservation

`HomeScreen` now mounts only when the current mobile route is not `/buscar`.
The search route continues to mount the results portal and retains the mobile
tab and query state. Returning to `/` mounts HomeScreen again, so the homepage
hero and ads load when the user can see the home page.

No CSS, text, layout, routes, search state, gallery state, or API contracts
changed. A mobile browser test covers direct search, verifies that the
homepage-only API and image requests are absent, then returns to home and
confirms that home content and its resources load there.

## Verification

The new browser test reproduced both homepage API requests and the hero image
on the original `main`; it passes on the candidate with zero homepage API or
hero image requests during search. A 390×844 direct-search screenshot is
pixel-identical before and after (0 of 329,160 pixels changed). The screenshot
captures are retained in the task's audit workspace rather than replacing
repository visual baselines.

The ~148 KB figure is the earlier production resource sample; it is not a
matched production before/after result. The PR is not deployed, and no
production data or configuration was changed.

## Matched local mobile search measurement

Baseline main `63ca366ca97f51558b3db4e1778ef24938d474ad` and this PR
`eea4b2204cd4e6194d5291f29968ce2c04b86851` were built with the same production
Vite settings (`VITE_ENABLE_MOCK_MODE=0`) and served from local Vite preview.
Each target had three cold-context runs at 390×844, 300 ms RTT, 400 kbps down,
200 kbps up, and CPU ×4. Both received the same one-listing search response and
the same local SVG media fixture.

| Metric | Main median | PR #300 median | Change |
| --- | ---: | ---: | ---: |
| First result card | 4,837 ms | 4,694 ms | −143 ms |
| First photo load | 4,990 ms | 4,855 ms | −136 ms |
| FCP | 2,664 ms | 2,696 ms | +32 ms |
| LCP | 4,260 ms | 2,696 ms | −1,564 ms |
| Cumulative long tasks | 1,822 ms | 1,586 ms | −236 ms |
| JavaScript transfer | 331,428 B | 328,737 B | −2,691 B |
| CSS transfer | 66,987 B | 65,600 B | −1,387 B |
| Total resource transfer | 513,188 B | 396,358 B | −116,830 B |
| Resource requests | 41 | 35 | −6 |

The first-card and first-photo medians improved in all three paired runs. The
FCP ranges overlap, so this result does not establish an FCP improvement. LCP
was not attributed to a specific element; do not treat its median change as an
acceptance claim. The media fixture is a small SVG, so first-photo time measures
app scheduling and rendering, not production image transport or decode. Vite
preview does not apply production Nginx compression, TLS, or CDN behavior.
