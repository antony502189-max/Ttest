import { createContext, useContext, useEffect, useMemo, type ReactNode } from 'react'

export type Language = 'es'

type I18nState = {
  language: Language
  locale: string
  languageName: string
  setLanguage: (language: Language) => void
  t: (source: string) => string
}

const I18nContext = createContext<I18nState | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  useEffect(() => {
    document.documentElement.lang = 'es'
    document.title = '112233.es — habitaciones en Tenerife'
  }, [])
  const value = useMemo<I18nState>(() => ({ language: 'es', locale: 'es-ES', languageName: 'Español', setLanguage: () => undefined, t: (source) => source }), [])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) throw new Error('useI18n debe usarse dentro de I18nProvider')
  return context
}
