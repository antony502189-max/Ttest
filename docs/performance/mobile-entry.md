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
bytes compete with visible search results and the first listing photo. The
latency cost was not isolated, so this change does not claim a millisecond
improvement.

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
