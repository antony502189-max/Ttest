import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './rental-emphasis.css'
import './admin-moderation.css'
import './moderation.css'
import App from './App.tsx'
import './mobile-app-v2-hardening.css'
import './mobile-home-mode-cards.css'
import './mobile-search-results-overrides.css'
import './mobile-search-results-panels.css'
import './mobile-occupant-filters.css'
import './reference-occupant-icons.css'
import './listing-card-content-order.css'
import './bolder-back-navigation-arrows.css'
import './reference-occupant-icons'
import './mobile-drawn-zone-search-navigation'
import './mobile-home-search-state'
import './white-theme.css'
import './white-theme-audit-fixes.css'
import './client-mobile-alignment-fixes.css'
import './client-listing-requirement-emphasis.css'

const MOBILE_ONBOARDING_KEY = '112233:mobile-onboarding:v1'
const MOBILE_VIEWPORT = '(max-width: 767px), (max-height: 480px) and (max-width: 900px)'

// Customer requirement: a real mobile page refresh starts the short onboarding again.
// Mock-mode E2E keeps the persistence bypass so existing route-focused tests can boot directly.
if (import.meta.env.VITE_ENABLE_MOCK_MODE !== '1' && window.matchMedia(MOBILE_VIEWPORT).matches) {
  try { localStorage.removeItem(MOBILE_ONBOARDING_KEY) } catch { /* Storage can be unavailable in private browsing. */ }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
