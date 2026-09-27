import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './rental-emphasis.css'
import './admin-moderation.css'
import './moderation.css'
import './mobile-app-v2.css'
import './mobile-favorites-selection.css'
import './mobile-map-ideal.css'
import './mobile-search-results.css'
import App from './App.tsx'
import './mobile-app-v2-hardening.css'
import './mobile-home-mode-cards.css'
import './mobile-search-results-overrides.css'
import './mobile-search-results-panels.css'
import './mobile-occupant-filters.css'
import './reference-occupant-icons.css'
import './listing-card-content-order.css'
import './reference-occupant-icons'
import './white-theme.css'
import './white-theme-audit-fixes.css'
import './client-mobile-alignment-fixes.css'
import './client-listing-requirement-emphasis.css'
import './mobile-four-tab-nav.css'
import './customer-card-clickability'
import './mobile-publish-layout-hotfix.css'
import './mobile-site-feedback.css'
import './publish-select-canonical-values'
import './customer-listing-photo-fit.css'
import './bolder-back-navigation-arrows.css'

// Keep the entry URL canonical so returning to Home through browser history
// lands on the same shareable HashRouter URL as internal Home links.
if (!window.location.hash) {
  window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}#/`)
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
