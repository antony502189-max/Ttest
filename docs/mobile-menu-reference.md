# Mobile menu and draw-mode visual state

The mobile menu at `/#/menu` follows the customer-approved reference:

- Administrator entry is a blue lead card **only** when `useAdminAccess()` confirms authorization through the existing server-side access contract; a product role string does not grant this.
- The account card is always the first card for non-administrators (including guests). Signed-in users can manage listings and edit their profile; guests see sign-in instead.
- Property management and settings are large, rounded rows with full-width tap targets and readable labels. The default search region is Spain, not Tenerife; an explicitly chosen autonomous community appears next to Spain.
- All copy remains available in Spanish, English and Russian. Unsupported agency/appearance placeholder rows are not added to the new reference layout.
- All menu styling is scoped under `.m2-menu` in `src/mobile-menu-reference.css`. It is imported after the legacy styles to avoid unrelated card changes.

## Drawing control

The existing `.m2-draw-cta` already tracks `aria-pressed={drawing}` in `src/components/mobile-app-v2.tsx`. The active state now has a lime fill, thick green border and double focus-like ring. A short `:active` movement acknowledges the tap. Cancelling removes the persistent selected state. **No map drawing logic, history, search filters or map camera behavior was changed.**

## Regression checks

`tests/mobile-menu-reference-and-drawing.spec.ts` checks:

- 320/390/430px menu layout, pill tap size and no horizontal overflow.
- Guest and tenant account order and absent admin card.
- Admin-only card order, color, and working protected-admin navigation.
- Drawing selected/unselected state including computed background, border and visible ring.

Smoke test after a deployed release: open the mobile menu as guest, tenant and administrator, then select and cancel `Dibujar tu zona` while watching the bottom map control.
