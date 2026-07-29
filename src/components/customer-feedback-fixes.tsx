import { useLayoutEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '@/contexts/app-context'
import { filtersToParams } from '@/lib/search'
import type { Filters, RentalMode, TenantRequirement } from '@/types'

const priceLimit = (mode: RentalMode) => mode === 'holiday' ? 350 : 1200
const RENTAL_MODE_KEY = '112233:rental-mode:v1'
const REMOVED_MENU_LABELS = [
  'Buscar agencias para vender',
  'Find agencies to sell',
  'Искать агентства для продажи',
  'Acerca de la aplicación',
  'About the app',
  'О приложении',
]
const OCCUPANT_REQUIREMENT_BY_INDEX: Array<TenantRequirement | null> = [
  null,
  'single-man',
  'single-woman',
  'single-person',
  'couple',
  'any',
]

function nativeSetInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
  setter?.call(input, value)
}

function setNativeInputValue(input: HTMLInputElement, value: string) {
  nativeSetInputValue(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
  input.dispatchEvent(new Event('change', { bubbles: true }))
}

function isNumericInput(target: EventTarget | null): target is HTMLInputElement {
  return target instanceof HTMLInputElement && target.type === 'number'
}

function stripLeadingZeroes(value: string) {
  return value.replace(/^(-?)0+(?=\d)/, '$1')
}

function normalizedPriceFilters(filters: Filters, previousMode: RentalMode, nextMode: RentalMode) {
  const previousLimit = priceLimit(previousMode)
  const nextLimit = priceLimit(nextMode)
  const wasFullRange = filters.minPrice === 0 && filters.maxPrice === previousLimit
  const maxPrice = wasFullRange ? nextLimit : Math.min(filters.maxPrice, nextLimit)
  const minPrice = Math.min(filters.minPrice, maxPrice)
  return { ...filters, minPrice, maxPrice }
}

function occupantRows() {
  return Array.from(document.querySelectorAll<HTMLButtonElement>('.m2-check-list > button'))
}

function selectedOccupantRequirements(rows: HTMLButtonElement[]) {
  const selectedIndexes = rows
    .map((row, index) => row.getAttribute('aria-checked') === 'true' ? index : -1)
    .filter((index) => index >= 0)
  if (!selectedIndexes.length || selectedIndexes.includes(0)) return []
  return selectedIndexes
    .map((index) => OCCUPANT_REQUIREMENT_BY_INDEX[index])
    .filter((value): value is TenantRequirement => value !== null)
}

function sameRequirements(left: TenantRequirement[], right: TenantRequirement[]) {
  return [...left].sort().join('|') === [...right].sort().join('|')
}

export function CustomerFeedbackFixes() {
  const { rentalMode, setRentalMode, filters, setFilters } = useApp()
  const location = useLocation()
  const navigate = useNavigate()
  const previousMode = useRef(rentalMode)
  const rentalModeRestored = useRef(false)
  const restoringOccupants = useRef(false)

  useLayoutEffect(() => {
    if (location.pathname === '/contacto') {
      navigate('/', { replace: true })
      return
    }
    if (location.pathname !== '/menu') return

    const hideRemovedRows = () => {
      document.querySelectorAll<HTMLButtonElement>('.m2-menu-row').forEach((row) => {
        const text = row.textContent?.replace(/\s+/g, ' ').trim() ?? ''
        row.hidden = REMOVED_MENU_LABELS.some((label) => text.includes(label))
      })
    }

    hideRemovedRows()
    const observer = new MutationObserver(hideRemovedRows)
    observer.observe(document.body, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [location.pathname, navigate])

  useLayoutEffect(() => {
    const handleFocusIn = (event: FocusEvent) => {
      if (!isNumericInput(event.target) || !/^0+$/.test(event.target.value)) return
      const input = event.target
      window.requestAnimationFrame(() => {
        if (document.activeElement === input) input.select()
      })
    }
    const handleInput = (event: Event) => {
      if (!isNumericInput(event.target)) return
      const input = event.target
      if (input.value === '') {
        event.stopPropagation()
        return
      }
      const normalized = stripLeadingZeroes(input.value)
      if (normalized !== input.value) nativeSetInputValue(input, normalized)
    }
    const handleFocusOut = (event: FocusEvent) => {
      if (!isNumericInput(event.target) || event.target.value !== '') return
      setNativeInputValue(event.target, event.target.min === '' ? '0' : event.target.min)
    }
    document.addEventListener('focusin', handleFocusIn, true)
    document.addEventListener('input', handleInput, true)
    document.addEventListener('focusout', handleFocusOut, true)
    return () => {
      document.removeEventListener('focusin', handleFocusIn, true)
      document.removeEventListener('input', handleInput, true)
      document.removeEventListener('focusout', handleFocusOut, true)
    }
  }, [])

  useLayoutEffect(() => {
    const currentRequirements = filters.tenantRequirement !== 'Cualquiera'
      ? [filters.tenantRequirement]
      : filters.tenantRequirements

    const commitSelection = () => {
      const rows = occupantRows()
      if (!rows.length) return
      const requirements = selectedOccupantRequirements(rows)
      const nextFilters: Filters = requirements.length === 1
        ? { ...filters, tenantRequirement: requirements[0], tenantRequirements: [] }
        : { ...filters, tenantRequirement: 'Cualquiera', tenantRequirements: requirements }
      if (sameRequirements(currentRequirements, requirements)) return
      setFilters(nextFilters)
      if (location.pathname !== '/buscar') return
      const params = filtersToParams(nextFilters, new URLSearchParams(location.search))
      params.delete('pagina')
      navigate({ pathname: location.pathname, search: `?${params.toString()}` }, { replace: true })
    }

    const restoreSelection = () => {
      const rows = occupantRows()
      if (!rows.length || restoringOccupants.current) return
      const desiredIndexes = currentRequirements.length
        ? currentRequirements.map((requirement) => OCCUPANT_REQUIREMENT_BY_INDEX.indexOf(requirement)).filter((index) => index > 0)
        : [0]
      const selectedIndexes = rows
        .map((row, index) => row.getAttribute('aria-checked') === 'true' ? index : -1)
        .filter((index) => index >= 0)
      if (selectedIndexes.join('|') === desiredIndexes.join('|')) return
      restoringOccupants.current = true
      rows[0]?.click()
      if (desiredIndexes[0] !== 0) desiredIndexes.forEach((index) => rows[index]?.click())
      window.requestAnimationFrame(() => { restoringOccupants.current = false })
    }

    const handleOccupantClick = (event: MouseEvent) => {
      if (restoringOccupants.current) return
      const target = event.target
      if (!(target instanceof Element) || !target.closest('.m2-check-list > button')) return
      window.requestAnimationFrame(commitSelection)
    }

    document.addEventListener('click', handleOccupantClick, true)
    const observer = new MutationObserver(restoreSelection)
    observer.observe(document.body, { childList: true, subtree: true })
    restoreSelection()
    return () => {
      document.removeEventListener('click', handleOccupantClick, true)
      observer.disconnect()
    }
  }, [filters, location.pathname, location.search, navigate, setFilters])

  useLayoutEffect(() => {
    if (!rentalModeRestored.current) {
      rentalModeRestored.current = true
      if (location.pathname === '/') {
        try {
          const storedMode = localStorage.getItem(RENTAL_MODE_KEY)
          if ((storedMode === 'long' || storedMode === 'holiday') && storedMode !== rentalMode) {
            setRentalMode(storedMode)
            return
          }
        } catch {
          // Local storage can be unavailable in private browsing.
        }
      }
    }
    try {
      localStorage.setItem(RENTAL_MODE_KEY, rentalMode)
    } catch {
      // Selection still remains in React state when storage is unavailable.
    }
  }, [location.pathname, rentalMode, setRentalMode])

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

  return null
}
