import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './rental-emphasis.css'
import App from './App.tsx'
import './mobile-app-v2-hardening.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
