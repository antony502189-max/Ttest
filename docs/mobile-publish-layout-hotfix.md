# Mobile publish layout hotfix

Regression scope: narrow mobile publish wizard (`/#/publicar`).

- Exit/back control must remain fully inside the header and icon-aligned at 320–430 px.
- Publish wizard content must never increase document horizontal width.
- Municipality/native select and other form controls must remain within the viewport when focused/changed.
- Desktop publish layout is intentionally unchanged.

Automated coverage: `tests/mobile-publish-layout.spec.ts`.
