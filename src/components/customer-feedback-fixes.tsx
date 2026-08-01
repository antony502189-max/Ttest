import { useLayoutEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router'
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

type OccupantKey = 'one' | 'two' | 'man' | 'woman' | 'children' | 'pets' | 'unrestricted'
type OccupantLocale = 'es' | 'en' | 'ru'

type OccupantCopy = {
  title: string
  done: string
  prefix: string
  options: Array<{ key: OccupantKey; emoji: string; label: string }>
}

const OCCUPANT_COPY: Record<OccupantLocale, OccupantCopy> = {
  es: {
    title: '¿Quién vivirá?',
    done: 'Listo',
    prefix: 'Para:',
    options: [
      { key: 'one', emoji: '👤', label: '1 persona' },
      { key: 'two', emoji: '👥', label: '2 personas (pareja/amigos)' },
      { key: 'man', emoji: '👱‍♂️', label: 'Solo hombre' },
      { key: 'woman', emoji: '👱‍♀️', label: 'Solo mujer' },
      { key: 'children', emoji: '👪', label: 'Con niños' },
      { key: 'pets', emoji: '🐶', label: 'Con mascotas' },
      { key: 'unrestricted', emoji: '🌍', label: 'Sin restricciones' },
    ],
  },
  en: {
    title: 'Who will live there?',
    done: 'Done',
    prefix: 'For:',
    options: [
      { key: 'one', emoji: '👤', label: '1 person' },
      { key: 'two', emoji: '👥', label: '2 people (couple/friends)' },
      { key: 'man', emoji: '👱‍♂️', label: 'Man only' },
      { key: 'woman', emoji: '👱‍♀️', label: 'Woman only' },
      { key: 'children', emoji: '👪', label: 'With children' },
      { key: 'pets', emoji: '🐶', label: 'With pets' },
      { key: 'unrestricted', emoji: '🌍', label: 'No restrictions' },
    ],
  },
  ru: {
    title: 'Кто будет жить?',
    done: 'Готово',
    prefix: 'Для кого:',
    options: [
      { key: 'one', emoji: '👤', label: '1 человек' },
      { key: 'two', emoji: '👥', label: '2 человека (пара/друзья)' },
      { key: 'man', emoji: '👱‍♂️', label: 'Только мужчина' },
      { key: 'woman', emoji: '👱‍♀️', label: 'Только женщина' },
      { key: 'children', emoji: '👪', label: 'Можно с ребёнком' },
      { key: 'pets', emoji: '🐶', label: 'Можно с животными' },
      { key: 'unrestricted', emoji: '🌍', label: 'Без ограничений' },
    ],
  },
}

const PRIMARY_REQUIREMENTS: Record<Exclude<OccupantKey, 'children' | 'pets' | 'unrestricted'>, {
  tenantRequirement: TenantRequirement
  roomCapacity: '1' | '2'
}> = {
  one: { tenantRequirement: 'single-person', roomCapacity: '1' },
  two: { tenantRequirement: 'couple', roomCapacity: '2' },
  man: { tenantRequirement: 'single-man', roomCapacity: '1' },
  woman: { tenantRequirement: 'single-woman', roomCapacity: '1' },
}

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

function detectOccupantLocale(source?: Element | null): OccupantLocale {
  const text = `${source?.textContent ?? ''} ${document.querySelector('.m2-occupant-trigger')?.textContent ?? ''}`
  if (/кто|человек|мужчин|женщин|ребён|животн|огранич/i.test(text)) return 'ru'
  if (/who|person|people|man|woman|children|pets|restrictions/i.test(text)) return 'en'
  return 'es'
}

function primaryKey(filters: Filters): Exclude<OccupantKey, 'children' | 'pets' | 'unrestricted'> | null {
  const requirement = filters.tenantRequirement !== 'Cualquiera'
    ? filters.tenantRequirement
    : filters.tenantRequirements[0]
  if (requirement === 'single-person') return 'one'
  if (requirement === 'couple') return 'two'
  if (requirement === 'single-man') return 'man'
  if (requirement === 'single-woman') return 'woman'
  if (filters.roomCapacity === '1') return 'one'
  if (filters.roomCapacity === '2') return 'two'
  return null
}

function selectedOccupantKeys(filters: Filters): OccupantKey[] {
  const selected: OccupantKey[] = []
  const primary = primaryKey(filters)
  if (primary) selected.push(primary)
  if (filters.children === 'Sí') selected.push('children')
  if (filters.pets === 'Sí') selected.push('pets')
  return selected.length ? selected : ['unrestricted']
}

function occupantFilters(filters: Filters, key: OccupantKey): Filters {
  if (key === 'unrestricted') {
    return {
      ...filters,
      tenantRequirement: 'Cualquiera',
      tenantRequirements: [],
      roomCapacity: 'Cualquiera',
      children: 'Cualquiera',
      pets: 'Cualquiera',
    }
  }

  if (key === 'children') {
    return { ...filters, children: filters.children === 'Sí' ? 'Cualquiera' : 'Sí' }
  }

  if (key === 'pets') {
    return { ...filters, pets: filters.pets === 'Sí' ? 'Cualquiera' : 'Sí' }
  }

  const active = primaryKey(filters) === key
  if (active) {
    return {
      ...filters,
      tenantRequirement: 'Cualquiera',
      tenantRequirements: [],
      roomCapacity: 'Cualquiera',
    }
  }

  const next = PRIMARY_REQUIREMENTS[key]
  return {
    ...filters,
    tenantRequirement: next.tenantRequirement,
    tenantRequirements: [],
    roomCapacity: next.roomCapacity,
  }
}

function sameOccupantFilters(left: Filters, right: Filters) {
  return left.tenantRequirement === right.tenantRequirement
    && left.tenantRequirements.join('|') === right.tenantRequirements.join('|')
    && left.roomCapacity === right.roomCapacity
    && left.children === right.children
    && left.pets === right.pets
}

function normalizedLegacyOccupants(filters: Filters): Filters {
  if (!filters.tenantRequirements.length && filters.tenantRequirement !== 'any') return filters
  const legacy = filters.tenantRequirement !== 'Cualquiera'
    ? filters.tenantRequirement
    : filters.tenantRequirements.find((value) => value !== 'any') ?? 'any'
  if (legacy === 'any') {
    return {
      ...filters,
      tenantRequirement: 'Cualquiera',
      tenantRequirements: [],
      roomCapacity: 'Cualquiera',
    }
  }
  const nextPrimary = legacy === 'couple' ? 'two' : legacy === 'single-man' ? 'man' : legacy === 'single-woman' ? 'woman' : 'one'
  const next = PRIMARY_REQUIREMENTS[nextPrimary]
  return {
    ...filters,
    tenantRequirement: next.tenantRequirement,
    tenantRequirements: [],
    roomCapacity: next.roomCapacity,
  }
}

function occupantSheetSource() {
  return Array.from(document.querySelectorAll<HTMLElement>('.m2-sheet')).find((sheet) => {
    const title = sheet.querySelector('header strong')?.textContent ?? ''
    return /¿quién vivirá|who will live|кто будет жить/i.test(title)
  })
}

function updatePublishRequirementLabels() {
  const labels: Record<string, string> = {
    'single-man': 'Solo hombre',
    'single-woman': 'Solo mujer',
    'single-person': '1 persona',
    couple: '2 personas (pareja/amigos)',
    any: 'Sin restricciones',
  }
  document.querySelectorAll<HTMLOptionElement>('#publish-tenant-requirement option').forEach((option) => {
    const label = labels[option.value]
    if (label && option.textContent !== label) option.textContent = label
  })
}

function renderOccupantPanel(filters: Filters) {
  const source = occupantSheetSource()
  document.querySelectorAll('.m2-sheet--occupant-source').forEach((element) => {
    if (element !== source) element.classList.remove('m2-sheet--occupant-source')
  })

  const existing = document.querySelector<HTMLElement>('.m2-custom-occupant-sheet')
  const trigger = document.querySelector<HTMLElement>('.m2-occupant-trigger')
  const triggerSummary = trigger?.querySelector<HTMLElement>('strong')
  if (!source) {
    existing?.remove()
    trigger?.removeAttribute('data-occupant-summary')
    triggerSummary?.removeAttribute('data-occupant-summary')
    return
  }

  source.classList.add('m2-sheet--occupant-source')
  const locale = detectOccupantLocale(source)
  const copy = OCCUPANT_COPY[locale]
  const selected = new Set(selectedOccupantKeys(filters))
  const signature = `${locale}:${copy.options.filter((option) => selected.has(option.key)).map((option) => option.key).join('|')}`
  const panel = existing ?? document.createElement('section')
  panel.className = 'm2-custom-occupant-sheet'
  panel.setAttribute('role', 'dialog')
  panel.setAttribute('aria-modal', 'true')
  panel.setAttribute('aria-label', copy.title)
  if (panel.dataset.occupantSignature !== signature) {
    panel.dataset.occupantSignature = signature
    panel.innerHTML = `
      <header>
        <strong>${copy.title}</strong>
        <button type="button" data-m2-occupant-close aria-label="${locale === 'ru' ? 'Закрыть' : locale === 'en' ? 'Close' : 'Cerrar'}">×</button>
      </header>
      <div class="m2-custom-occupant-list" role="group" aria-label="${copy.title}">
        ${copy.options.map((option) => {
          const checked = selected.has(option.key)
          return `<button type="button" role="checkbox" aria-checked="${checked}" data-m2-occupant-key="${option.key}" class="${checked ? 'is-selected' : ''}">
            <span><b aria-hidden="true">${option.emoji}</b>${option.label}</span>
            <i aria-hidden="true">${checked ? '✓' : ''}</i>
          </button>`
        }).join('')}
      </div>
      <button type="button" class="m2-custom-occupant-done" data-m2-occupant-close>${copy.done}</button>
    `
  }
  if (!existing) document.body.appendChild(panel)

  const selectedLabels = copy.options
    .filter((option) => selected.has(option.key) && option.key !== 'unrestricted')
    .map((option) => option.label)
  const summary = selectedLabels.length
    ? `${copy.prefix} ${selectedLabels.join(', ')}`
    : `${copy.prefix} ${copy.options.find((option) => option.key === 'unrestricted')?.label ?? ''}`
  trigger?.setAttribute('data-occupant-summary', summary)
  triggerSummary?.setAttribute('data-occupant-summary', summary)
}

export function CustomerFeedbackFixes() {
  const { rentalMode, setRentalMode, filters, setFilters } = useApp()
  const location = useLocation()
  const navigate = useNavigate()
  const previousMode = useRef(rentalMode)
  const rentalModeRestored = useRef(false)

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
    const normalized = normalizedLegacyOccupants(filters)
    if (!sameOccupantFilters(filters, normalized)) {
      setFilters(normalized)
      return
    }

    let frame = 0
    const synchronize = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(() => {
        renderOccupantPanel(filters)
        updatePublishRequirementLabels()
      })
    }
    const observer = new MutationObserver(synchronize)
    observer.observe(document.body, { childList: true, subtree: true })
    synchronize()

    const closeSource = () => {
      const source = occupantSheetSource()
      source?.querySelector<HTMLButtonElement>('header button')?.click()
    }

    const handleClick = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Element)) return
      if (target.closest('[data-m2-occupant-close]')) {
        event.preventDefault()
        event.stopPropagation()
        closeSource()
        return
      }
      const button = target.closest<HTMLButtonElement>('[data-m2-occupant-key]')
      if (!button) return
      const key = button.dataset.m2OccupantKey as OccupantKey | undefined
      if (!key) return
      event.preventDefault()
      event.stopPropagation()
      const nextFilters = occupantFilters(filters, key)
      setFilters(nextFilters)
      if (location.pathname === '/buscar') {
        const params = filtersToParams(nextFilters, new URLSearchParams(location.search))
        params.delete('pagina')
        const search = params.toString()
        navigate({ pathname: location.pathname, search: search ? `?${search}` : '' }, { replace: true })
      }
    }

    document.addEventListener('click', handleClick, true)
    return () => {
      window.cancelAnimationFrame(frame)
      observer.disconnect()
      document.removeEventListener('click', handleClick, true)
      document.querySelector('.m2-custom-occupant-sheet')?.remove()
      document.querySelectorAll('.m2-sheet--occupant-source').forEach((element) => element.classList.remove('m2-sheet--occupant-source'))
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
