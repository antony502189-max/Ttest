import { useLayoutEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '@/contexts/app-context'
import { useI18n, type Language } from '@/contexts/i18n-context'
import { filtersToParams } from '@/lib/search'
import type { Filters, RentalMode } from '@/types'

const priceLimit = (mode: RentalMode) => mode === 'holiday' ? 350 : 1200

const sortCopy: Record<string, Record<Language, string>> = {
  Relevancia: { es: 'Relevancia', ru: 'По релевантности', en: 'Relevance' },
  'Más recientes': { es: 'Más recientes', ru: 'Сначала новые', en: 'Newest first' },
  'Más antiguos': { es: 'Más antiguos', ru: 'Сначала старые', en: 'Oldest first' },
  'Precio más bajo': { es: 'Precio más bajo', ru: 'Сначала дешевле', en: 'Lowest price' },
  'Precio más alto': { es: 'Precio más alto', ru: 'Сначала дороже', en: 'Highest price' },
}

const restrictionCopy: Record<string, Record<Language, string>> = {
  'Solo un hombre': { es: 'Solo un hombre', ru: 'Только один мужчина', en: 'One man only' },
  'Solo una mujer': { es: 'Solo una mujer', ru: 'Только одна женщина', en: 'One woman only' },
  'Solo pareja': { es: 'Solo pareja', ru: 'Только пара', en: 'Couples only' },
  'Sin restricción': { es: 'Sin restricción', ru: 'Без ограничений', en: 'No restriction' },
  'Sin niños': { es: 'Sin niños', ru: 'Без детей', en: 'No children' },
  'Sin mascotas': { es: 'Sin mascotas', ru: 'Без животных', en: 'No pets' },
  'Mascotas permitidas': { es: 'Mascotas permitidas', ru: 'Можно с животными', en: 'Pets allowed' },
  'No fumar': { es: 'No fumar', ru: 'Не курить', en: 'No smoking' },
  'Gastos incluidos': { es: 'Gastos incluidos', ru: 'Расходы включены', en: 'Bills included' },
  'Empadronamiento posible': { es: 'Empadronamiento posible', ru: 'Регистрация возможна', en: 'Registration possible' },
  'Sin empadronamiento': { es: 'Sin empadronamiento', ru: 'Без регистрации', en: 'No registration' },
}

const sortAliases = new Map<string, string>()
Object.entries(sortCopy).forEach(([source, variants]) => {
  Object.values(variants).forEach((label) => sortAliases.set(label.trim(), source))
})

const restrictionAliases = new Map<string, string>()
Object.entries(restrictionCopy).forEach(([source, variants]) => {
  Object.values(variants).forEach((label) => restrictionAliases.set(label.trim(), source))
})

function roomCount(language: Language, count: number) {
  if (language === 'es') return `${count} ${count === 1 ? 'habitación' : 'habitaciones'}`
  if (language === 'en') return `${count} ${count === 1 ? 'room' : 'rooms'}`
  const mod10 = count % 10
  const mod100 = count % 100
  const noun = mod10 === 1 && mod100 !== 11
    ? 'комната'
    : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)
      ? 'комнаты'
      : 'комнат'
  return `${count} ${noun}`
}

function resultHeading(language: Language, count: number, place: string) {
  if (language === 'es') return `${roomCount(language, count)} en ${place}`
  if (language === 'en') return `${roomCount(language, count)} in ${place}`
  return `${roomCount(language, count)} в ${place}`
}

function clearFiltersLabel(language: Language, count: number) {
  if (language === 'es') return `Borrar filtros (${count})`
  if (language === 'en') return `Clear filters (${count})`
  return `Сбросить фильтры (${count})`
}

function setText(element: Element | null, value: string) {
  if (element && element.textContent?.trim() !== value) element.textContent = value
}

function setDirectText(element: Element | null, value: string) {
  if (!element) return
  const textNode = [...element.childNodes].find((node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim())
  if (textNode) {
    if (textNode.textContent?.trim() !== value) textNode.textContent = value
    return
  }
  element.append(document.createTextNode(value))
}

function setNativeInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
  input.dispatchEvent(new Event('change', { bubbles: true }))
}

function normalizeFilterNumbers() {
  document.querySelectorAll<HTMLInputElement>('.filter-panel input[type="number"]').forEach((input) => {
    if (!input.value) return
    const minimum = Number(input.min || 0)
    const maximum = Number(input.max || Number.MAX_SAFE_INTEGER)
    const numeric = Number(input.value)
    const normalized = Number.isFinite(numeric)
      ? String(Math.min(maximum, Math.max(minimum, Math.round(numeric))))
      : String(minimum)
    if (input.value !== normalized) setNativeInputValue(input, normalized)
  })
}

function normalizedPriceFilters(filters: Filters, previousMode: RentalMode, nextMode: RentalMode) {
  const previousLimit = priceLimit(previousMode)
  const nextLimit = priceLimit(nextMode)
  const wasFullRange = filters.minPrice === 0 && filters.maxPrice === previousLimit
  const maxPrice = wasFullRange ? nextLimit : Math.min(filters.maxPrice, nextLimit)
  const minPrice = Math.min(filters.minPrice, maxPrice)
  return { ...filters, minPrice, maxPrice }
}

export function CustomerFeedbackFixes() {
  const { rentalMode, filters, setFilters, activeFilterCount } = useApp()
  const { language } = useI18n()
  const location = useLocation()
  const navigate = useNavigate()
  const previousMode = useRef(rentalMode)

  useLayoutEffect(() => {
    const previous = previousMode.current
    if (previous === rentalMode) return
    previousMode.current = rentalMode

    const nextFilters = normalizedPriceFilters(filters, previous, rentalMode)
    if (nextFilters.minPrice === filters.minPrice && nextFilters.maxPrice === filters.maxPrice) return

    setFilters(nextFilters)
    if (location.pathname !== '/buscar') return

    const params = filtersToParams(nextFilters, new URLSearchParams(location.search))
    params.set('alquiler', rentalMode)
    const search = params.toString()
    navigate({ pathname: location.pathname, search: search ? `?${search}` : '' }, { replace: true })
  }, [filters, location.pathname, location.search, navigate, rentalMode, setFilters])

  useLayoutEffect(() => {
    if (location.pathname !== '/buscar') return
    const params = new URLSearchParams(location.search)
    if (params.get('vista') === 'mapa') return

    let animationFrame = 0
    const apply = () => {
      animationFrame = 0
      normalizeFilterNumbers()

      const title = document.querySelector<HTMLElement>('#results-title')
      if (title) {
        const count = Number(title.textContent?.match(/\d+/)?.[0] ?? 0)
        const place = params.get('q')?.trim() || 'Tenerife'
        setText(title, resultHeading(language, count, place))
      }

      setText(document.querySelector('.applied-filters__clear'), clearFiltersLabel(language, activeFilterCount))
      setDirectText(
        document.querySelector('.mobile-sort-control'),
        language === 'ru' ? 'Сортировка' : language === 'en' ? 'Sort' : 'Ordenar',
      )
      setText(
        document.querySelector('.sort-drawer [data-slot="drawer-title"], .sort-drawer h2'),
        language === 'ru' ? 'Сортировка результатов' : language === 'en' ? 'Sort results' : 'Ordenar resultados',
      )
      setText(
        document.querySelector('.sort-drawer [data-slot="drawer-description"], .sort-drawer p'),
        language === 'ru' ? 'Выберите порядок показа комнат.' : language === 'en' ? 'Choose how to order the rooms.' : 'Elige cómo quieres ver las habitaciones.',
      )

      document.querySelectorAll<HTMLElement>('.sort-options label').forEach((label) => {
        const source = sortAliases.get(label.textContent?.trim() ?? '')
        if (source) setText(label, sortCopy[source][language])
      })
      document.querySelectorAll<HTMLOptionElement>('.desktop-sort-control option').forEach((option) => {
        const source = sortCopy[option.value] ? option.value : sortAliases.get(option.textContent?.trim() ?? '')
        if (source) option.textContent = sortCopy[source][language]
      })
      const desktopSort = document.querySelector<HTMLElement>('.desktop-sort-control > span')
      setText(desktopSort, language === 'ru' ? 'Сортировка:' : language === 'en' ? 'Sort:' : 'Ordenar:')
      const desktopSelect = document.querySelector<HTMLSelectElement>('.desktop-sort-control select')
      if (desktopSelect) desktopSelect.setAttribute('aria-label', language === 'ru' ? 'Сортировка результатов' : language === 'en' ? 'Sort results' : 'Ordenar resultados')

      const sortApply = document.querySelector<HTMLElement>('.sort-drawer [data-slot="drawer-footer"] button, .sort-drawer footer button')
      setDirectText(sortApply, language === 'ru' ? 'Применить' : language === 'en' ? 'Apply sort' : 'Aplicar orden')

      document.querySelectorAll<HTMLElement>('.property-badge').forEach((badge) => {
        const source = restrictionAliases.get(badge.textContent?.trim() ?? '')
        if (source) setText(badge, restrictionCopy[source][language])
      })
    }

    const schedule = () => {
      if (animationFrame) return
      animationFrame = window.requestAnimationFrame(apply)
    }

    apply()
    const observer = new MutationObserver(schedule)
    observer.observe(document.body, { subtree: true, childList: true, characterData: true })
    document.addEventListener('input', schedule, true)
    document.addEventListener('change', schedule, true)
    document.addEventListener('click', schedule, true)

    return () => {
      observer.disconnect()
      document.removeEventListener('input', schedule, true)
      document.removeEventListener('change', schedule, true)
      document.removeEventListener('click', schedule, true)
      if (animationFrame) window.cancelAnimationFrame(animationFrame)
    }
  }, [activeFilterCount, language, location.pathname, location.search])

  return null
}
