import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { ChevronLeft } from 'lucide-react'
import '@/mobile-publication-gate.css'

type GateLanguage = 'es' | 'en' | 'ru'

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

function currentLanguage(): GateLanguage {
  const language = document.documentElement.lang
  return language === 'en' || language === 'ru' ? language : 'es'
}

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

function isPublicationTrigger(target: Element) {
  if (target.closest('.m2-home .m2-outline')) return true

  const menuRow = target.closest<HTMLElement>('.m2-menu .m2-menu-row')
  if (!menuRow || !menuRow.parentElement) return false

  const rows = Array.from(menuRow.parentElement.querySelectorAll<HTMLElement>(':scope > .m2-menu-row'))
  return rows.indexOf(menuRow) === 1
}

function openExistingAuthentication() {
  const openMenuLogin = () => {
    const loginButton = document.querySelector<HTMLButtonElement>('.m2-menu > .m2-primary')
    loginButton?.click()
  }

  const menuScreen = document.querySelector('.m2-menu')
  if (menuScreen) {
    requestAnimationFrame(openMenuLogin)
    return
  }

  const menuTab = document.querySelector<HTMLButtonElement>('.m2-bottom-nav button:last-child')
  menuTab?.click()
  requestAnimationFrame(() => requestAnimationFrame(openMenuLogin))
}

export function MobilePublicationGate() {
  const [open, setOpen] = useState(false)
  const [language, setLanguage] = useState<GateLanguage>('es')

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Element) || !isPublicationTrigger(target)) return

      event.preventDefault()
      event.stopPropagation()
      setLanguage(currentLanguage())
      setOpen(true)
    }

    document.addEventListener('click', handleClick, true)
    return () => document.removeEventListener('click', handleClick, true)
  }, [])

  useEffect(() => {
    if (!open) return

    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [open])

  if (!open) return null

  const t = gateCopy[language]

  const login = () => {
    setOpen(false)
    requestAnimationFrame(() => requestAnimationFrame(openExistingAuthentication))
  }

  return createPortal(
    <section className="m2-publication-gate notranslate" translate="no" data-testid="publication-gate">
      <header className="m2-publication-gate__header">
        <button type="button" onClick={() => setOpen(false)} aria-label={t.back}><ChevronLeft /></button>
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
