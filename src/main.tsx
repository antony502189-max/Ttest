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
import './mobile-four-tab-nav.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
