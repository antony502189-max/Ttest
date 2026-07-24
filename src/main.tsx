import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './rental-emphasis.css'
import './mobile-app-v2-hardening.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
