import { useLayoutEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { toast } from 'sonner'
import { useApp } from '@/contexts/app-context'
import { useI18n, type Language } from '@/contexts/i18n-context'
import type { Listing, ListingDraft } from '@/types'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
const DRAFT_KEY = '112233:listing-draft:v3'
const LEGACY_DRAFT_KEY = '112233:listing-draft:v2'
const EDIT_DRAFT_PREFIX = '112233:listing-edit-draft:v1:'
const PENDING_EDIT_KEY = '112233:pending-edit-route:v1'
const EDIT_RETRY_PREFIX = '112233:listing-edit-retry:v1:'
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
  saveChanges: string
  savingChanges: string
  imageRetry: string
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
    saveChanges: 'Guardar cambios',
    savingChanges: 'Guardando…',
    imageRetry: 'Los datos se guardaron, pero las fotografías no terminaron de sincronizarse. Hemos recuperado el borrador para que puedas reintentarlo sin perder cambios.',
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
    saveChanges: 'Save changes',
    savingChanges: 'Saving…',
    imageRetry: 'The listing data was saved, but the photos did not finish syncing. We restored the draft so you can retry without losing changes.',
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
    saveChanges: 'Сохранить изменения',
    savingChanges: 'Сохраняем…',
    imageRetry: 'Данные объявления сохранились, но фотографии не успели синхронизироваться. Черновик восстановлен — можно повторить попытку без потери изменений.',
  },
}

type DraftRecord = {
  version?: number
  ownerUserId?: string
  listingId?: string
  data?: Partial<ListingDraft>
}

type TemporaryListingRestore = {
  target: Listing
  snapshot: Listing
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

function parseDraft(raw: string | null): DraftRecord | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as DraftRecord
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

function readDraftRecord() {
  return parseDraft(localStorage.getItem(DRAFT_KEY))
}

function editDraftKey(listingId: string) {
  return `${EDIT_DRAFT_PREFIX}${listingId}`
}

function editRetryKey(listingId: string) {
  return `${EDIT_RETRY_PREFIX}${listingId}`
}

function editRouteId(pathname: string) {
  const match = pathname.match(/^\/mis-anuncios\/([^/]+)\/editar$/)
  return match ? decodeURIComponent(match[1]) : null
}

function isDraftForListing(record: DraftRecord | null, listingId: string, ownerUserId?: string | null) {
  if (!record || record.version !== 3 || record.listingId !== listingId || !record.data) return false
  return !record.ownerUserId || !ownerUserId || record.ownerUserId === ownerUserId
}

function cloneListing(listing: Listing): Listing {
  return {
    ...listing,
    owner: { ...listing.owner },
    coordinates: { ...listing.coordinates },
    ...(listing.exactCoordinates ? { exactCoordinates: { ...listing.exactCoordinates } } : {}),
    restrictions: [...listing.restrictions],
    amenities: [...listing.amenities],
    images: [...listing.images],
    acceptedTenantTypes: listing.acceptedTenantTypes ? [...listing.acceptedTenantTypes] : listing.acceptedTenantTypes,
  }
}

function overlayDraftOnListing(listing: Listing, draft: Partial<ListingDraft>) {
  const directKeys = [
    'rentalMode', 'city', 'area', 'street', 'postcode', 'roomType', 'roomSizeM2', 'homeSizeM2', 'bedroomCount',
    'bathroomCount', 'currentResidents', 'roomCapacity', 'rentalUnit', 'bedType', 'bedCount', 'currentRoomResidents',
    'bathroom', 'toilet', 'shower', 'kitchen', 'heatingType', 'accessible', 'floor', 'furnished', 'monthlyPrice',
    'nightlyPrice', 'weeklyPrice', 'depositAmount', 'billsIncluded', 'availableFrom', 'availableUntil', 'minimumStayMonths',
    'minimumNights', 'expiresAt', 'tenantRequirement', 'householdGender', 'householdHasChildren', 'couplesAllowed',
    'smokingAllowed', 'petsAllowed', 'childrenAllowed', 'empadronamientoAllowed', 'title', 'description', 'contactPhone',
    'contactWhatsapp', 'contactEmail', 'showPhone', 'showWhatsApp', 'status',
  ] as const
  const target = listing as unknown as Record<string, unknown>
  const source = draft as unknown as Record<string, unknown>
  for (const key of directKeys) {
    if (source[key] !== undefined) target[key] = source[key]
  }
  if (draft.coordinates) listing.exactCoordinates = { ...draft.coordinates }
  if (draft.amenities) listing.amenities = [...draft.amenities]
  if (draft.images) listing.images = [...draft.images]
  if (draft.acceptedTenantTypes) listing.acceptedTenantTypes = [...draft.acceptedTenantTypes]
  if (draft.rules !== undefined) listing.homeDescription = draft.rules
  if (draft.contactName !== undefined) listing.owner = { ...listing.owner, name: draft.contactName }
  if (draft.billsIncluded !== undefined || draft.billsNote !== undefined) {
    listing.bills = draft.billsIncluded
      ? 'Gastos incluidos en el precio'
      : draft.billsNote
        ? `Gastos aparte: aprox. ${draft.billsNote} €/mes`
        : 'Gastos aparte'
  }
  const mode = draft.rentalMode ?? listing.rentalMode
  const primaryPrice = mode === 'holiday' ? draft.nightlyPrice ?? listing.nightlyPrice ?? listing.price : draft.monthlyPrice ?? listing.monthlyPrice ?? listing.price
  listing.price = primaryPrice
  listing.cadence = mode === 'holiday' ? 'noche' : 'mes'
  if (draft.roomCapacity !== undefined && draft.currentRoomResidents !== undefined) {
    listing.availableSpots = Math.max(0, draft.roomCapacity - draft.currentRoomResidents)
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

function requestDetails(input: RequestInfo | URL, init?: RequestInit) {
  const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
  const method = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase()
  return { url, method }
}

export function CustomerVideoCriticalFixes() {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { language } = useI18n()
  const { ownedListings, currentUser } = useApp()
  const copy = COPY[language]
  const migratedPublication = useRef<string | null>(null)
  const restoredEditDraft = useRef<string | null>(null)
  const temporaryListingRestore = useRef<TemporaryListingRestore | null>(null)
  const editImageSyncFailed = useRef(false)
  const editId = editRouteId(pathname)
  const existingEditListing = editId ? ownedListings.find((listing) => listing.id === editId) : undefined

  // This component is rendered before the route element. Scope an unfinished
  // edit draft before PublishPage's create-mode state initializer can consume
  // it as a new listing draft.
  if (!mockMode && pathname === '/publicar') {
    const globalDraft = readDraftRecord()
    if (globalDraft?.listingId) {
      try {
        localStorage.setItem(editDraftKey(globalDraft.listingId), JSON.stringify(globalDraft))
        localStorage.removeItem(DRAFT_KEY)
      } catch { /* The editor still has its server snapshot if storage is unavailable. */ }
    }
  }

  // PublishPage intentionally prefers the authoritative server listing in edit
  // mode. Overlay a matching autosaved edit draft for the single render in
  // which PublishPage initializes its local state, then restore AppContext's
  // listing object in the layout phase so unsaved changes never leak elsewhere.
  if (editId && existingEditListing) {
    const globalDraft = readDraftRecord()
    if (isDraftForListing(globalDraft, editId, currentUser?.id)) {
      try { localStorage.setItem(editDraftKey(editId), JSON.stringify(globalDraft)) } catch { /* best effort */ }
    }
    const scopedRaw = localStorage.getItem(editDraftKey(editId))
    const scopedDraft = parseDraft(scopedRaw)
    if (isDraftForListing(scopedDraft, editId, currentUser?.id) && scopedDraft?.data) {
      const token = `${editId}:${scopedRaw}`
      if (restoredEditDraft.current !== token) {
        restoredEditDraft.current = token
        temporaryListingRestore.current = { target: existingEditListing, snapshot: cloneListing(existingEditListing) }
        overlayDraftOnListing(existingEditListing, scopedDraft.data)
      }
    }
  }

  if (editId && !existingEditListing) {
    try { sessionStorage.setItem(PENDING_EDIT_KEY, editId) } catch { /* navigation recovery remains best effort */ }
  }

  useLayoutEffect(() => {
    const temporary = temporaryListingRestore.current
    if (temporary) {
      const { target, snapshot } = temporary
      Object.assign(target, snapshot)
      target.owner = { ...snapshot.owner }
      target.coordinates = { ...snapshot.coordinates }
      target.exactCoordinates = snapshot.exactCoordinates ? { ...snapshot.exactCoordinates } : undefined
      target.restrictions = [...snapshot.restrictions]
      target.amenities = [...snapshot.amenities]
      target.images = [...snapshot.images]
      target.acceptedTenantTypes = snapshot.acceptedTenantTypes ? [...snapshot.acceptedTenantTypes] : snapshot.acceptedTenantTypes
      temporaryListingRestore.current = null
    }

    let disposed = false
    let reloadingAfterImageFailure = false

    const localizeOwnedEmptyState = () => {
      if (pathname !== '/mis-anuncios') return
      const empty = document.querySelector<HTMLElement>('.account-empty')
      if (!empty) return
      const filter = document.querySelector<HTMLSelectElement>('#my-listings-status')?.value ?? 'Todos'
      setText(empty.querySelector<HTMLElement>('h2'), filter === 'Todos' ? copy.emptyTitle : copy.filteredEmptyTitle)
      setText(empty.querySelector<HTMLElement>('p'), filter === 'Todos' ? copy.emptyText : copy.filteredEmptyText)
      setText(empty.querySelector<HTMLElement>('a, button'), copy.createListing)
    }

    const localizeEditSubmit = () => {
      if (!editId) return
      document.querySelectorAll<HTMLButtonElement>('.wizard-actions button').forEach((button) => {
        const label = button.textContent?.trim().toLocaleLowerCase() ?? ''
        if (/publicar anuncio|publish listing|опубликовать объявление/.test(label)) setText(button, copy.saveChanges)
        else if (/publicando|publishing|публикуем/.test(label)) setText(button, copy.savingChanges)
      })
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
      const publicationKey = raw?.data?.publicationKey ?? (raw ? 'persisted-default' : 'brand-new-unpersisted')
      const hasLegacyDraft = localStorage.getItem(LEGACY_DRAFT_KEY) !== null
      const domStillUntouchedLegacyDefault = city.value === 'Adeje'
        && area.value === 'Armeñime'
        && !street.value.trim()
        && postcode.value === '38678'
      const brandNewUnpersistedDefault = raw === null
        && !hasLegacyDraft
        && domStillUntouchedLegacyDefault
      const shouldMigrateLegacyDefault = (isUntouchedLegacyLocationDefault(raw) || brandNewUnpersistedDefault)
        && domStillUntouchedLegacyDefault

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
      if (preview) {
        if (auto) {
          if (!preview.hidden) preview.hidden = true
          preview.dataset.customerVideoHidden = 'true'
        } else if (preview.dataset.customerVideoHidden === 'true') {
          preview.hidden = false
          delete preview.dataset.customerVideoHidden
        }
      }
    }

    const recoverPendingEditRoute = () => {
      let pending: string | null = null
      try { pending = sessionStorage.getItem(PENDING_EDIT_KEY) } catch { /* ignore */ }
      if (!pending) return
      if (editId === pending && ownedListings.some((listing) => listing.id === pending)) {
        try { sessionStorage.removeItem(PENDING_EDIT_KEY) } catch { /* ignore */ }
        return
      }
      if (pathname === '/mis-anuncios' && ownedListings.some((listing) => listing.id === pending)) {
        try { sessionStorage.removeItem(PENDING_EDIT_KEY) } catch { /* ignore */ }
        navigate(`/mis-anuncios/${encodeURIComponent(pending)}/editar`, { replace: true })
      }
    }

    const setup = () => {
      if (disposed) return
      localizeOwnedEmptyState()
      localizeEditSubmit()
      setupPublicationLocation()
      recoverPendingEditRoute()
    }

    if (editId && !existingEditListing) window.dispatchEvent(new Event('catalog:updated'))

    const onContinue = (event: MouseEvent) => {
      const target = event.target
      if (!(target instanceof Element)) return
      const button = target.closest<HTMLButtonElement>('button')
      if (!button) return

      if (editId) {
        const label = button.textContent?.trim().toLocaleLowerCase() ?? ''
        if ([copy.saveChanges, 'publicar anuncio', 'publish listing', 'опубликовать объявление'].some((value) => label === value.toLocaleLowerCase())) {
          editImageSyncFailed.current = false
          const currentDraft = localStorage.getItem(DRAFT_KEY) ?? localStorage.getItem(editDraftKey(editId))
          if (currentDraft) {
            try {
              sessionStorage.setItem(editRetryKey(editId), currentDraft)
              localStorage.setItem(editDraftKey(editId), currentDraft)
            } catch { /* best effort */ }
          }
        }
      }

      if (pathname !== '/publicar') return
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

    const originalFetch = window.fetch.bind(window)
    if (editId) {
      window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        const details = requestDetails(input, init)
        const imageRequest = details.method === 'PUT' && /\/listings\/[^/?#]+\/images(?:[?#]|$)/.test(details.url)
        try {
          const response = await originalFetch(input, init)
          if (imageRequest && !response.ok) editImageSyncFailed.current = true
          return response
        } catch (error) {
          if (imageRequest) editImageSyncFailed.current = true
          throw error
        }
      }
    }

    const mirrorEditDraft = () => {
      if (!editId) return
      const raw = localStorage.getItem(DRAFT_KEY)
      const record = parseDraft(raw)
      if (!raw || !isDraftForListing(record, editId, currentUser?.id)) return
      try { localStorage.setItem(editDraftKey(editId), raw) } catch { /* best effort */ }
    }

    const handleMutation = (mutations: MutationRecord[]) => {
      if (editId) {
        for (const mutation of mutations) {
          for (const node of Array.from(mutation.addedNodes)) {
            const text = node.textContent ?? ''
            if (/No se pudieron actualizar las imágenes del anuncio|No se encontró una de las imágenes locales|Una de las imágenes ya no está disponible/i.test(text)) {
              editImageSyncFailed.current = true
            }
          }
        }
        const success = document.querySelector<HTMLElement>('.publish-success')
        if (success && editImageSyncFailed.current && !reloadingAfterImageFailure) {
          reloadingAfterImageFailure = true
          let retryDraft: string | null = null
          try { retryDraft = sessionStorage.getItem(editRetryKey(editId)) } catch { /* ignore */ }
          if (retryDraft) {
            try {
              localStorage.setItem(DRAFT_KEY, retryDraft)
              localStorage.setItem(editDraftKey(editId), retryDraft)
            } catch { /* ignore */ }
          }
          toast.error(copy.imageRetry, { id: 'listing-edit-image-retry' })
          window.setTimeout(() => window.location.reload(), 0)
          return
        }
        if (success && !editImageSyncFailed.current) {
          try {
            localStorage.removeItem(editDraftKey(editId))
            sessionStorage.removeItem(editRetryKey(editId))
            sessionStorage.removeItem(PENDING_EDIT_KEY)
          } catch { /* successful edit is authoritative even if cleanup storage fails */ }
        }
      }
      setup()
    }

    document.addEventListener('click', onContinue, true)
    document.addEventListener('input', onLocationInput, true)
    document.addEventListener('change', onLocationInput, true)
    window.addEventListener('112233:map-address-resolved', setup)
    const observer = new MutationObserver(handleMutation)
    observer.observe(document.body, { childList: true, subtree: true })
    const draftMirror = editId ? window.setInterval(mirrorEditDraft, 250) : 0
    mirrorEditDraft()
    setup()
    return () => {
      disposed = true
      observer.disconnect()
      document.removeEventListener('click', onContinue, true)
      document.removeEventListener('input', onLocationInput, true)
      document.removeEventListener('change', onLocationInput, true)
      window.removeEventListener('112233:map-address-resolved', setup)
      if (draftMirror) window.clearInterval(draftMirror)
      mirrorEditDraft()
      if (editId) window.fetch = originalFetch
      clearLocationGuard()
    }
  }, [copy, currentUser?.id, editId, existingEditListing, navigate, ownedListings, pathname])

  return null
}
