import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronLeft } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'
import '@/mobile-publication-gate.css'

const gateCopy = {
  es: {
    title: 'Publica tu anuncio',
    heading: 'Inicia sesión para publicar un anuncio',
    text: 'Publica tu anuncio para que lo vean millones de personas que buscan una nueva vivienda.',
    login: 'Iniciar sesión',
    back: 'Volver',
    illustration: 'Formulario para publicar un anuncio',
  },
  en: {
    title: 'Publish an ad',
    heading: 'Sign in to publish an ad',
    text: 'Publish your ad so it can be seen by millions of people looking for a new home.',
    login: 'Sign in',
    back: 'Back',
    illustration: 'Form for publishing an ad',
  },
  ru: {
    title: 'Разместите объявление',
    heading: 'Для публикации объявления войдите в аккаунт',
    text: 'Опубликуйте объявление, чтобы его увидели миллионы людей, ищущих новое жильё.',
    login: 'Войти в аккаунт',
    back: 'Назад',
    illustration: 'Форма публикации объявления',
  },
} as const

function PublicationIllustration({ label }: { label: string }) {
  return <svg className="m2-publication-gate__illustration" viewBox="0 0 280 230" role="img" aria-label={label}>
    <rect x="39" y="20" width="191" height="181" fill="#4a4a4a" stroke="#383838" strokeWidth="3" />
    <rect x="51" y="34" width="82" height="13" fill="#6c6c6c" />
    <rect x="51" y="59" width="157" height="25" fill="#656565" stroke="#252525" strokeWidth="2" />
    <rect x="51" y="96" width="82" height="13" fill="#6c6c6c" />
    <circle cx="63" cy="126" r="9" fill="none" stroke="#222" strokeWidth="3" />
    <rect x="79" y="119" width="82" height="13" fill="#6c6c6c" />
    <circle cx="63" cy="150" r="9" fill="none" stroke="#222" strokeWidth="3" />
    <rect x="79" y="143" width="82" height="13" fill="#6c6c6c" />
    <rect x="60" y="170" width="150" height="23" rx="1" fill="#728f00" stroke="#242424" strokeWidth="2" />
    <path d="M190 184c10-11 21-7 25 4l9 28-25 8-12-34c-1-3 0-5 3-6Z" fill="#818181" stroke="#2d2d2d" strokeWidth="2" />
    <path d="M190 184c4-8 12-9 17-2l5 8c-7 3-13 5-20 3Z" fill="#929292" stroke="#2d2d2d" strokeWidth="2" />
    <path d="M202 204l16-5" stroke="#5d5d5d" strokeWidth="2" />
  </svg>
}

export function MobilePublicationGate() {
  const { currentUser } = useApp()
  const { language } = useI18n()
  const location = useLocation()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const requested = new URLSearchParams(location.search).get('gate') === 'publicar'
    if (!requested) { setOpen(false); return }
    if (currentUser) { navigate('/publicar', { replace: true }); return }
    setOpen(true)
  }, [currentUser, location.search, navigate])

  useEffect(() => {
    if (!open) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') navigate(location.pathname, { replace: true })
    }

    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [location.pathname, navigate, open])

  if (!open) return null

  const t = gateCopy[language]

  const close = () => navigate(location.pathname, { replace: true })
  const login = () => navigate('/acceso')

  return createPortal(
    <section className="m2-publication-gate notranslate" translate="no" data-testid="publication-gate">
      <header className="m2-publication-gate__header">
        <button type="button" onClick={close} aria-label={t.back}><ChevronLeft /></button>
        <strong>{t.title}</strong>
      </header>

      <div className="m2-publication-gate__content">
        <PublicationIllustration label={t.illustration} />
        <h1>{t.heading}</h1>
        <p>{t.text}</p>
      </div>

      <div className="m2-publication-gate__footer">
        <button type="button" onClick={login}>{t.login}</button>
      </div>
    </section>,
    document.body,
  )
}
