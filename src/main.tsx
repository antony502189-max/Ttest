import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './rental-emphasis.css'
import App from './App.tsx'
import './mobile-app-v2-hardening.css'
import './mobile-search-results-overrides.css'
import './mobile-search-results-panels.css'

function restoreMobileLocationStep(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof Element)) return
  if (!document.documentElement.classList.contains('mobile-v2-active')) return
  if (!target.closest('[data-testid="open-location"]')) return

  event.preventDefault()
  event.stopImmediatePropagation()
  window.location.hash = '/?panel=ubicacion'
}

document.addEventListener('click', restoreMobileLocationStep, true)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
