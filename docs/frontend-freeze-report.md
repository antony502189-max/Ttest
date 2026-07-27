# Frontend design-freeze report

Backend integration preserves the existing React routes, HashRouter, Google Maps components, dark `UnifiedAuthPage`, mobile/desktop shells, existing visual tokens and page composition.

Frontend files changed for integration are limited to routing, API calls and data ownership:

- `src/api/auth.ts`: password-reset and e-mail-verification API methods.
- `src/contexts/app-context.tsx`: server remains the listing source of truth; mock listing fallback is explicit-only.
- `src/pages/SearchPage.tsx`: sends filters to the server and uses the existing error state when API loading fails.
- `src/pages/AuthPages.tsx` and `src/App.tsx`: add the minimal existing-auth-shell route required to consume an e-mail verification link.

No stylesheet, shared visual component, layout ordering, map provider, typography token or existing screen was redesigned. Browser checks covered the new verification route on desktop and at 390×844.
