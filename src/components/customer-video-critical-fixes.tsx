import { useLayoutEffect, useRef } from 'react'
import { useLocation } from 'react-router'
import { useI18n, type Language } from '@/contexts/i18n-context'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
const DRAFT_KEY = '112233:listing-draft:v3'
const LEGACY_DRAFT_KEY = '112233:listing-draft:v2'
const AUTO_CITY_VALUE = '__112233_auto_municipality__'

type CriticalCopy = {
  emptyTitle: string
  emptyText: string
  filteredEmptyTitle: string
  filteredEmptyText: string
  createListing: string
  autoMunicipality: string
  locationPending: string
  locationPendingHelp: string
  chooseLocation: string
  invalidPostcode: string
}

const COPY: Record<Language, CriticalCopy> = {
  es: {
    emptyTitle: 'Todavía no tienes anuncios',
    emptyText: 'Crea tu primer anuncio cuando quieras.',
    filteredEmptyTitle: 'No hay anuncios con este estado',
    filteredEmptyText: 'Prueba otro estado o crea un anuncio nuevo.',
    createListing: 'Crear anuncio',
    autoMunicipality: 'Se detectará por la dirección o el código postal',
    locationPending: 'Añade una dirección o un código postal',
    locationPendingHelp: 'Detectaremos municipio y zona automáticamente. También puedes elegir el municipio manualmente.',
    chooseLocation: 'Introduce una dirección o un código postal, o selecciona un municipio.',
    invalidPostcode: 'El código postal debe tener exactamente 5 dígitos.',
  },
  en: {
    emptyTitle: 'You do not have any listings yet',
    emptyText: 'Create your first listing whenever you are ready.',
    filteredEmptyTitle: 'No listings have this status',
    filteredEmptyText: 'Try another status or create a new listing.',
    createListing: 'Create listing',
    autoMunicipality: 'Detected from the address or postcode',
    locationPending: 'Add an address or postcode',
    locationPendingHelp: 'We will detect the municipality and area automatically. You can also choose the municipality manually.',
    chooseLocation: 'Enter an address or postcode, or select a municipality.',
    invalidPostcode: 'The postcode must contain exactly 5 digits.',
  },
  ru: {
    emptyTitle: 'У вас пока нет объявлений',
    emptyText: 'Создайте первое объявление, когда будете готовы.',
    filteredEmptyTitle: 'Нет объявлений с таким статусом',
    filteredEmptyText: 'Выберите другой статус или создайте новое объявление.',
    createListing: 'Создать объявление',
    autoMunicipality: 'Определится по адресу или почтовому индексу',
    locationPending: 'Введите адрес или почтовый индекс',
    locationPendingHelp: 'Муниципалитет и район определятся автоматически. При желании муниципалитет можно выбрать вручную.',
    chooseLocation: 'Введите адрес или почтовый индекс либо выберите муниципалитет.',
    invalidPostcode: 'Почтовый индекс должен состоять ровно из 5 цифр.',
  },
}

type DraftRecord = {
  version?: number
  listingId?: string
  data?: {
    publicationKey?: string
    city?: string
    area?: string
    street?: string
    postcode?: string
    locationManuallyMoved?: boolean
  }
}

export function isUntouchedLegacyLocationDefault(value: unknown) {
  if (!value || typeof value !== 'object') return false
  const record = value as DraftRecord
  if (record.listingId) return false
  const draft = record.data
  return Boolean(
    draft
      && draft.city === 'Adeje'
      && draft.area === 'Armeñime'
      && (draft.street ?? '') === ''
      && draft.postcode === '38678'
      && draft.locationManuallyMoved === false,
  )
}

function setNativeInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event('input', { bubbles: true }))
  input.dispatchEvent(new Event('change', { bubbles: true }))
}

function setNativeSelectValue(select: HTMLSelectElement, value: string, addressSync = false) {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')?.set
  if (addressSync) select.dataset.locationAddressSync = 'true'
  try {
    setter?.call(select, value)
    select.dispatchEvent(new Event('input', { bubbles: true }))
    select.dispatchEvent(new Event('change', { bubbles: true }))
  } finally {
    if (addressSync) delete select.dataset.locationAddressSync
  }
}

function readDraftRecord() {
  try {
    return JSON.parse(localStorage.getItem(DRAFT_KEY) ?? 'null') as unknown
  } catch {
    return null
  }
}

function ensureAutoMunicipalityOption(select: HTMLSelectElement, label: string) {
  let option = Array.from(select.options).find((candidate) => candidate.value === AUTO_CITY_VALUE)
  if (!option) {
    option = document.createElement('option')
    option.value = AUTO_CITY_VALUE
    option.disabled = true
    select.prepend(option)
  }
  if (option.textContent !== label) option.textContent = label
}

function setText(element: HTMLElement | null, value: string) {
  if (element && element.textContent !== value) element.textContent = value
}

function locationGuardHost(element: HTMLElement) {
  return element.closest<HTMLElement>('.form-field') ?? element.parentElement
}

function showLocationGuard(element: HTMLElement, message: string) {
  document.querySelector('.customer-video-location-guard')?.remove()
  const host = locationGuardHost(element)
  if (!host) return
  const error = document.createElement('p')
  error.className = 'form-error customer-video-location-guard'
  error.setAttribute('role', 'alert')
  error.textContent = message
  host.append(error)
  element.setAttribute('aria-invalid', 'true')
  element.focus()
}

function clearLocationGuard() {
  document.querySelector('.customer-video-location-guard')?.remove()
  document.querySelectorAll<HTMLElement>('[data-customer-video-invalid="true"]').forEach((element) => {
    element.removeAttribute('data-customer-video-invalid')
    element.removeAttribute('aria-invalid')
  })
}

export function CustomerVideoCriticalFixes() {
  const { pathname } = useLocation()
  const { language } = useI18n()
  const copy = COPY[language]
  const migratedPublication = useRef<string | null>(null)

  useLayoutEffect(() => {
    let disposed = false

    const localizeOwnedEmptyState = () => {
      if (pathname !== '/mis-anuncios') return
      const empty = document.querySelector<HTMLElement>('.account-empty')
      if (!empty) return
      const filter = document.querySelector<HTMLSelectElement>('#my-listings-status')?.value ?? 'Todos'
      setText(empty.querySelector<HTMLElement>('h2'), filter === 'Todos' ? copy.emptyTitle : copy.filteredEmptyTitle)
      setText(empty.querySelector<HTMLElement>('p'), filter === 'Todos' ? copy.emptyText : copy.filteredEmptyText)
      setText(empty.querySelector<HTMLElement>('a, button'), copy.createListing)
    }

    const setupPublicationLocation = () => {
      if (mockMode || pathname !== '/publicar') return
      const city = document.querySelector<HTMLSelectElement>('#publish-city')
      const area = document.querySelector<HTMLInputElement>('#publish-area')
      const street = document.querySelector<HTMLInputElement>('#publish-street')
      const postcode = document.querySelector<HTMLInputElement>('#publish-postcode')
      if (!city || !area || !street || !postcode) return

      ensureAutoMunicipalityOption(city, copy.autoMunicipality)
      const raw = readDraftRecord()
      const publicationKey = raw && typeof raw === 'object'
        ? (raw as DraftRecord).data?.publicationKey ?? 'persisted-default'
        : 'brand-new-unpersisted'
      const hasLegacyDraft = localStorage.getItem(LEGACY_DRAFT_KEY) !== null
      const brandNewUnpersistedDefault = raw === null
        && !hasLegacyDraft
        && city.value === 'Adeje'
        && area.value === 'Armeñime'
        && !street.value.trim()
        && postcode.value === '38678'
      const shouldMigrateLegacyDefault = isUntouchedLegacyLocationDefault(raw) || brandNewUnpersistedDefault

      if (migratedPublication.current !== publicationKey && shouldMigrateLegacyDefault) {
        migratedPublication.current = publicationKey
        setNativeSelectValue(city, AUTO_CITY_VALUE, true)
        setNativeInputValue(area, '')
        setNativeInputValue(postcode, '')
      }

      const auto = city.value === AUTO_CITY_VALUE
      const selector = document.querySelector<HTMLElement>('.approximate-location-selector')
      const preview = document.querySelector<HTMLElement>('.location-preview')
      if (selector) {
        if (auto) {
          if (!selector.hidden) selector.hidden = true
          selector.dataset.customerVideoHidden = 'true'
        } else if (selector.dataset.customerVideoHidden === 'true') {
          selector.hidden = false
          delete selector.dataset.customerVideoHidden
        }
      }
      if (preview && auto) {
        setText(preview.querySelector<HTMLElement>('strong'), copy.locationPending)
        setText(preview.querySelector<HTMLElement>('span'), copy.locationPendingHelp)
      }
    }

    const setup = () => {
      if (disposed) return
      localizeOwnedEmptyState()
      setupPublicationLocation()
    }

    const onContinue = (event: MouseEvent) => {
      if (pathname !== '/publicar') return
      const target = event.target
      if (!(target instanceof Element)) return
      const button = target.closest<HTMLButtonElement>('button')
      if (!button) return
      const label = button.textContent?.trim().toLocaleLowerCase() ?? ''
      if (!['continuar', 'continue', 'продолжить'].includes(label)) return
      const city = document.querySelector<HTMLSelectElement>('#publish-city')
      const postcode = document.querySelector<HTMLInputElement>('#publish-postcode')
      if (!city || !postcode) return
      if (city.value === AUTO_CITY_VALUE) {
        event.preventDefault()
        event.stopImmediatePropagation()
        city.dataset.customerVideoInvalid = 'true'
        showLocationGuard(city, copy.chooseLocation)
        return
      }
      if (postcode.value.trim() && !/^\d{5}$/.test(postcode.value.trim())) {
        event.preventDefault()
        event.stopImmediatePropagation()
        postcode.dataset.customerVideoInvalid = 'true'
        showLocationGuard(postcode, copy.invalidPostcode)
      }
    }

    const onLocationInput = (event: Event) => {
      const target = event.target
      if (!(target instanceof HTMLElement)) return
      if (!['publish-city', 'publish-area', 'publish-street', 'publish-postcode'].includes(target.id)) return
      clearLocationGuard()
      queueMicrotask(setup)
    }

    document.addEventListener('click', onContinue, true)
    document.addEventListener('input', onLocationInput, true)
    document.addEventListener('change', onLocationInput, true)
    window.addEventListener('112233:map-address-resolved', setup)
    const observer = new MutationObserver(setup)
    observer.observe(document.body, { childList: true, subtree: true })
    setup()
    return () => {
      disposed = true
      observer.disconnect()
      document.removeEventListener('click', onContinue, true)
      document.removeEventListener('input', onLocationInput, true)
      document.removeEventListener('change', onLocationInput, true)
      window.removeEventListener('112233:map-address-resolved', setup)
      clearLocationGuard()
    }
  }, [copy, pathname])

  return null
}
