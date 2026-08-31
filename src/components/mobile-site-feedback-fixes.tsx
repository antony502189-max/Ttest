import { useLayoutEffect } from 'react'
import { useI18n, type Language } from '@/contexts/i18n-context'

const APPEARANCE_KEY = '112233:appearance:v1'
const UNKNOWN_FACT_ES = 'Consultar con el anunciante'

const feedbackCopy: Record<Language, { unknownFact: string }> = {
  es: { unknownFact: UNKNOWN_FACT_ES },
  en: { unknownFact: 'Ask the advertiser' },
  ru: { unknownFact: 'Уточнить у автора' },
}

function forceLightAppearance() {
  const root = document.documentElement
  root.classList.remove('site-theme-dark')
  root.classList.add('site-theme-light')
  root.dataset.appearance = 'light'
  root.style.colorScheme = 'light'
  try { localStorage.removeItem(APPEARANCE_KEY) } catch { /* private browsing */ }
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

  useLayoutEffect(() => {
    forceLightAppearance()
  }, [])

  useLayoutEffect(() => {
    let frame = 0
    const synchronize = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        forceLightAppearance()

        const appearanceRow = findAppearanceRow()
        if (appearanceRow) {
          appearanceRow.hidden = true
          appearanceRow.setAttribute('aria-hidden', 'true')
          appearanceRow.removeAttribute('data-mobile-appearance-trigger')
          appearanceRow.removeAttribute('data-testid')
          appearanceRow.removeAttribute('aria-haspopup')
          appearanceRow.tabIndex = -1
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
  }, [copy.unknownFact, language])

  return null
}
