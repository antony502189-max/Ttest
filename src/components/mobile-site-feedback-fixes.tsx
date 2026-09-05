import { useEffect, useLayoutEffect } from 'react'
import { useApp } from '@/contexts/app-context'
import { useI18n, type Language } from '@/contexts/i18n-context'

const APPEARANCE_KEY = '112233:appearance:v1'
const UNKNOWN_FACT_ES = 'Consultar con el anunciante'
const APPEARANCE_LABELS = new Set(['Apariencia', 'Appearance', 'Внешний вид'])

const feedbackCopy: Record<Language, { unknownFact: string }> = {
  es: { unknownFact: UNKNOWN_FACT_ES },
  en: { unknownFact: 'Ask the advertiser' },
  ru: { unknownFact: 'Уточнить у автора' },
}
const UNKNOWN_FACT_LABELS = new Set(Object.values(feedbackCopy).map((copy) => copy.unknownFact))

function forceLightAppearance() {
  const root = document.documentElement
  root.classList.remove('site-theme-dark')
  root.classList.add('site-theme-light')
  root.dataset.appearance = 'light'
  root.style.colorScheme = 'light'
  try { localStorage.removeItem(APPEARANCE_KEY) } catch { /* private browsing */ }
}

function hideAppearanceRow() {
  document.querySelectorAll<HTMLButtonElement>('.m2-menu-row').forEach((row) => {
    const label = row.querySelector('span')?.textContent?.trim() ?? ''
    if (!APPEARANCE_LABELS.has(label)) return
    row.hidden = true
    row.setAttribute('aria-hidden', 'true')
    row.tabIndex = -1
  })
}

export function MobileSiteFeedbackFixes() {
  const { language } = useI18n()
  const { allListings } = useApp()
  const copy = feedbackCopy[language]

  useLayoutEffect(() => {
    forceLightAppearance()
  }, [])

  useLayoutEffect(() => {
    let frame = 0
    const synchronize = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        forceLightAppearance()
        hideAppearanceRow()

        document.querySelectorAll<HTMLElement>('.m2-result-card__facts, .m2-result-card__badges span, .m2-result-card__availability').forEach((element) => {
          const text = element.textContent ?? ''
          if (![...UNKNOWN_FACT_LABELS].some((label) => text.includes(label))) return
          if (text !== copy.unknownFact) {
            for (const label of UNKNOWN_FACT_LABELS) element.textContent = (element.textContent ?? '').replaceAll(label, copy.unknownFact)
          }
          if (!element.matches('.m2-result-card__badges span')) return

          const card = element.closest<HTMLElement>('.m2-result-card')
          const listingId = card?.dataset.listingId
          const listing = listingId ? allListings.find((item) => item.id === listingId) : undefined
          const sourceUrl = listing?.isExternal ? listing.sourceUrl : undefined
          if (sourceUrl) {
            element.classList.remove('m2-unknown-fact')
            element.classList.add('m2-external-source-cta')
            element.dataset.externalSourceUrl = sourceUrl
            element.setAttribute('role', 'link')
            element.tabIndex = 0
            element.setAttribute('aria-label', `${copy.unknownFact}: ${listing?.primarySource ?? listing?.source ?? 'sitio original'}`)
          } else {
            element.classList.remove('m2-external-source-cta')
            delete element.dataset.externalSourceUrl
            element.removeAttribute('role')
            element.removeAttribute('aria-label')
            element.removeAttribute('tabindex')
            element.classList.add('m2-unknown-fact')
          }
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
  }, [allListings, copy.unknownFact, language])

  useEffect(() => {
    const activate = (target: EventTarget | null) => {
      if (!(target instanceof Element)) return false
      const cta = target.closest<HTMLElement>('.m2-external-source-cta[data-external-source-url]')
      const sourceUrl = cta?.dataset.externalSourceUrl
      if (!sourceUrl) return false
      window.open(sourceUrl, '_blank', 'noopener,noreferrer')
      return true
    }
    const handleClick = (event: MouseEvent) => {
      if (!activate(event.target)) return
      event.preventDefault()
      event.stopPropagation()
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Enter' && event.key !== ' ') return
      if (!activate(event.target)) return
      event.preventDefault()
      event.stopPropagation()
    }
    document.addEventListener('click', handleClick)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('click', handleClick)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  return null
}
