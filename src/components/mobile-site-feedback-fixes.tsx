import { useEffect, useLayoutEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { useI18n, type Language } from '@/contexts/i18n-context'
import { cn } from '@/lib/utils'

type AppearanceMode = 'light' | 'dark' | 'system'

const APPEARANCE_KEY = '112233:appearance:v1'
const UNKNOWN_FACT_ES = 'Consultar con el anunciante'

const feedbackCopy: Record<Language, {
  appearance: string
  appearanceTitle: string
  light: string
  dark: string
  system: string
  close: string
  unknownFact: string
}> = {
  es: {
    appearance: 'Apariencia', appearanceTitle: 'Apariencia', light: 'Clara', dark: 'Oscura', system: 'Predeterminada — como el sistema', close: 'Cerrar',
    unknownFact: UNKNOWN_FACT_ES,
  },
  en: {
    appearance: 'Appearance', appearanceTitle: 'Appearance', light: 'Light', dark: 'Dark', system: 'Default — follow system', close: 'Close',
    unknownFact: 'Ask the advertiser',
  },
  ru: {
    appearance: 'Внешний вид', appearanceTitle: 'Внешний вид', light: 'Светлая', dark: 'Темная', system: 'По умолчанию — как в системе', close: 'Закрыть',
    unknownFact: 'Уточнить у автора',
  },
}

function readAppearance(): AppearanceMode {
  try {
    const stored = localStorage.getItem(APPEARANCE_KEY)
    return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system'
  } catch {
    return 'system'
  }
}

function applyAppearance(mode: AppearanceMode) {
  const systemDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const resolved = mode === 'system' ? (systemDark ? 'dark' : 'light') : mode
  const root = document.documentElement
  root.classList.toggle('site-theme-dark', resolved === 'dark')
  root.classList.toggle('site-theme-light', resolved === 'light')
  root.dataset.appearance = mode
  root.style.colorScheme = resolved
}

function appearanceLabel(language: Language, mode: AppearanceMode) {
  const copy = feedbackCopy[language]
  return mode === 'light' ? copy.light : mode === 'dark' ? copy.dark : copy.system
}

function findAppearanceRow() {
  return Array.from(document.querySelectorAll<HTMLButtonElement>('.m2-menu-row')).find((row) => {
    const label = row.querySelector('span')?.textContent?.trim() ?? ''
    return ['Apariencia', 'Appearance', 'Внешний вид'].includes(label)
  }) ?? null
}

export function MobileSiteFeedbackFixes() {
  const { language } = useI18n()
  const copy = feedbackCopy[language]
  const [appearance, setAppearance] = useState<AppearanceMode>(readAppearance)
  const [appearanceOpen, setAppearanceOpen] = useState(false)
  const appearanceOptions = useMemo(() => [
    { value: 'light' as const, label: copy.light },
    { value: 'dark' as const, label: copy.dark },
    { value: 'system' as const, label: copy.system },
  ], [copy.dark, copy.light, copy.system])

  useLayoutEffect(() => {
    applyAppearance(appearance)
    try { localStorage.setItem(APPEARANCE_KEY, appearance) } catch { /* private browsing */ }
    if (appearance !== 'system') return
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const update = () => applyAppearance('system')
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [appearance])

  useLayoutEffect(() => {
    let frame = 0
    const synchronize = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const row = findAppearanceRow()
        if (row) {
          row.dataset.mobileAppearanceTrigger = 'true'
          row.setAttribute('aria-haspopup', 'dialog')
          row.setAttribute('data-testid', 'mobile-appearance-trigger')
          const value = row.querySelector('b')
          const label = appearanceLabel(language, appearance)
          if (value && value.textContent !== label) value.textContent = label
        }

        document.querySelectorAll<HTMLElement>('.m2-result-card__facts, .m2-result-card__badges span, .m2-result-card__availability').forEach((element) => {
          const text = element.textContent ?? ''
          if (!text.includes(UNKNOWN_FACT_ES)) return
          if (language !== 'es') element.textContent = text.replaceAll(UNKNOWN_FACT_ES, copy.unknownFact)
          if (element.matches('.m2-result-card__badges span')) element.classList.add('m2-unknown-fact')
        })
      })
    }
    const observer = new MutationObserver(synchronize)
    observer.observe(document.body, { childList: true, subtree: true })
    synchronize()
    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
    }
  }, [appearance, copy.unknownFact, language])

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Element)) return
      if (!target.closest('[data-mobile-appearance-trigger]')) return
      event.preventDefault()
      event.stopPropagation()
      setAppearanceOpen(true)
    }
    document.addEventListener('click', handleClick, true)
    return () => document.removeEventListener('click', handleClick, true)
  }, [])

  useEffect(() => {
    if (!appearanceOpen) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const close = (event: KeyboardEvent) => { if (event.key === 'Escape') setAppearanceOpen(false) }
    document.addEventListener('keydown', close)
    return () => {
      document.body.style.overflow = previousOverflow
      document.removeEventListener('keydown', close)
    }
  }, [appearanceOpen])

  return <>
    {appearanceOpen ? createPortal(<div className="m2-appearance-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setAppearanceOpen(false) }}>
      <section className="m2-appearance-dialog" role="dialog" aria-modal="true" aria-labelledby="m2-appearance-title">
        <header><strong id="m2-appearance-title">{copy.appearanceTitle}</strong><button type="button" onClick={() => setAppearanceOpen(false)} aria-label={copy.close}><X /></button></header>
        <div role="radiogroup" aria-label={copy.appearanceTitle}>{appearanceOptions.map((option) => <button key={option.value} type="button" role="radio" aria-checked={appearance === option.value} className={cn(appearance === option.value && 'is-selected')} onClick={() => { setAppearance(option.value); setAppearanceOpen(false) }}><span>{option.label}</span><i aria-hidden="true">{appearance === option.value ? '●' : ''}</i></button>)}</div>
      </section>
    </div>, document.body) : null}
  </>
}
