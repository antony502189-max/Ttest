import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter, Navigate, Route, Routes } from 'react-router'
import { I18nProvider } from '@/contexts/i18n-context'
import { HomePage } from './site-pilot-home'
import '../index.css'
import '../home-ai-search.css'

createRoot(document.getElementById('root')!).render(<StrictMode><HashRouter><I18nProvider>
  <Routes><Route path="/" element={<HomePage />} /><Route path="*" element={<Navigate to="/" replace />} /></Routes>
</I18nProvider></HashRouter></StrictMode>)
