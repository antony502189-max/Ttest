import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { checkAdminAccess } from '@/api/admin'
import { ApiError } from '@/api/client'
import { getOwnedListings } from '@/api/listings'
import { AppContext, useApp } from '@/contexts/app-context'
import { useI18n, type Language } from '@/contexts/i18n-context'
import type { Listing } from '@/types'

const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
const DRAFT_KEY = '112233:listing-draft:v3'
const AUTO_CITY_VALUE = '__112233_auto_municipality__'

type CriticalCopy = {
  ownedLoading: string
  ownedLoadingHelp: string
  ownedError: string
  ownedErrorHelp: string
  retry: string
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
  adminChecking: string
  adminError: string
  adminErrorHelp: string
}

const COPY: Record<Language, CriticalCopy> = {
  es: {
    ownedLoading: 'Cargando tus anuncios…',
    ownedLoadingHelp: 'Estamos sincronizando la lista actual con el servidor.',
    ownedError: 'No pudimos cargar tus anuncios',
    ownedErrorHelp: 'Tus anuncios no se han borrado. Reintenta la sincronización.',
    retry: 'Reintentar',
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
    adminChecking: 'Comprobando acceso de administración…',
    adminError: 'No pudimos comprobar el acceso de administración',
    adminErrorHelp: 'Tu sesión sigue activa. Reintenta la comprobación; un fallo de red no debe expulsarte del panel.',
  },
  en: {
    ownedLoading: 'Loading your listings…',
    ownedLoadingHelp: 'We are syncing the current list with the server.',
    ownedError: 'We could not load your listings',
    ownedErrorHelp: 'Your listings have not been deleted. Retry the sync.',
    retry: 'Retry',
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
    adminChecking: 'Checking administration access…',
    adminError: 'We could not verify administration access',
    adminErrorHelp: 'Your session is still active. Retry the check; a network failure must not kick you out of the panel.',
  },
  ru: {
    ownedLoading: 'Загружаем ваши объявления…',
    ownedLoadingHelp: 'Синхронизируем актуальный список с сервером.',
    ownedError: 'Не удалось загрузить ваши объявления',
    ownedErrorHelp: 'Объявления не удалены. Повторите синхронизацию.',
    retry: 'Повторить',
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
    adminChecking: 'Проверяем доступ к админ-панели…',
    adminError: 'Не удалось проверить доступ к админ-панели',
    adminErrorHelp: 'Сессия остаётся активной. Повторите проверку — сетевой сбой не должен выбрасывать вас из панели.',
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

export function isExplicitAdminDenial(error: unknown) {
  return error instanceof ApiError && (error.status === 401 || error.status === 403)
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
      const title = empty.querySelector<HTMLElement>('h2')
      const text = empty.querySelector<HTMLElement>('p')
      const action = empty.querySelector<HTMLElement>('a, button')
      if (title) title.textContent = filter === 'Todos' ? copy.emptyTitle : copy.filteredEmptyTitle
      if (text) text.textContent = filter === 'Todos' ? copy.emptyText : copy.filteredEmptyText
      if (action) action.textContent = copy.createListing
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
        ? (raw as DraftRecord).data?.publicationKey ?? 'dom-default'
        : 'dom-default'
      const domLooksLegacy = city.value === 'Adeje' && area.value === 'Armeñime' && !street.value.trim() && postcode.value === '38678'
      if (migratedPublication.current !== publicationKey && (isUntouchedLegacyLocationDefault(raw) || domLooksLegacy)) {
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
          selector.hidden = true
          selector.dataset.customerVideoHidden = 'true'
        } else if (selector.dataset.customerVideoHidden === 'true') {
          selector.hidden = false
          delete selector.dataset.customerVideoHidden
        }
      }
      if (preview && auto) {
        const strong = preview.querySelector<HTMLElement>('strong')
        const help = preview.querySelector<HTMLElement>('span')
        if (strong && strong.textContent !== copy.locationPending) strong.textContent = copy.locationPending
        if (help && help.textContent !== copy.locationPendingHelp) help.textContent = copy.locationPendingHelp
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

type OwnedPhase = 'checking' | 'ready' | 'error'

export function OwnedListingsHydrationGate({ children }: { children: ReactNode }) {
  const app = useApp()
  const { language } = useI18n()
  const copy = COPY[language]
  const userId = app.currentUser?.id ?? null
  const [snapshot, setSnapshot] = useState<Listing[] | null>(null)
  const [phase, setPhase] = useState<OwnedPhase>(() => mockMode || app.ownedListings.length ? 'ready' : 'checking')
  const [attempt, setAttempt] = useState(0)
  const checkedUser = useRef<string | null>(null)

  useEffect(() => {
    if (mockMode || !userId) {
      setSnapshot(null)
      setPhase('ready')
      checkedUser.current = userId
      return
    }

    if (app.ownedListings.length) {
      setSnapshot(null)
      setPhase('ready')
      checkedUser.current = userId
      return
    }

    if (checkedUser.current === userId && (phase === 'ready' || phase === 'error')) return

    const controller = new AbortController()
    checkedUser.current = userId
    setPhase('checking')
    void getOwnedListings(controller.signal).then((items) => {
      if (controller.signal.aborted) return
      setSnapshot(items)
      setPhase('ready')
      if (items.length) window.dispatchEvent(new Event('catalog:updated'))
    }).catch(() => {
      if (!controller.signal.aborted) setPhase('error')
    })
    return () => controller.abort()
  }, [app.ownedListings, attempt, phase, userId])

  const effectiveValue = useMemo(() => {
    if (app.ownedListings.length || snapshot === null) return app
    return { ...app, ownedListings: snapshot }
  }, [app, snapshot])

  if (mockMode) return children
  if (phase === 'checking' && !snapshot?.length) {
    return <div className="route-loading customer-owned-listings-loading" role="status" aria-live="polite"><span /><strong>{copy.ownedLoading}</strong><p>{copy.ownedLoadingHelp}</p></div>
  }
  if (phase === 'error' && !snapshot?.length) {
    return <div className="route-error customer-owned-listings-error" role="alert"><h1>{copy.ownedError}</h1><p>{copy.ownedErrorHelp}</p><button type="button" onClick={() => { checkedUser.current = null; setAttempt((value) => value + 1) }}>{copy.retry}</button></div>
  }
  return <AppContext.Provider value={effectiveValue}>{children}</AppContext.Provider>
}

type AdminPhase = 'checking' | 'allowed' | 'denied' | 'error'

export function AdminAccessRecoveryGate({ children }: { children: ReactNode }) {
  const app = useApp()
  const { language } = useI18n()
  const copy = COPY[language]
  const [phase, setPhase] = useState<AdminPhase>('checking')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    if (!app.currentUser) return
    if (mockMode) {
      setPhase(app.currentUser.role === 'admin' ? 'allowed' : 'denied')
      return
    }

    let cancelled = false
    let retryTimer = 0
    setPhase('checking')

    const verify = async (retry = true) => {
      try {
        await checkAdminAccess()
        if (!cancelled) setPhase('allowed')
      } catch (error) {
        if (cancelled) return
        if (isExplicitAdminDenial(error)) {
          setPhase('denied')
          return
        }
        if (retry) {
          retryTimer = window.setTimeout(() => { void verify(false) }, 450)
          return
        }
        setPhase('error')
      }
    }

    void verify(true)
    return () => {
      cancelled = true
      if (retryTimer) window.clearTimeout(retryTimer)
    }
  }, [app.currentUser, attempt])

  if (!app.currentUser) return <Navigate to="/acceso" replace />
  if (phase === 'allowed') return children
  if (phase === 'denied') return <Navigate to="/" replace />
  if (phase === 'error') {
    return <div className="route-error customer-admin-access-error" role="alert"><h1>{copy.adminError}</h1><p>{copy.adminErrorHelp}</p><button type="button" onClick={() => setAttempt((value) => value + 1)}>{copy.retry}</button></div>
  }
  return <div className="route-loading customer-admin-access-loading" role="status" aria-live="polite"><span /><strong>{copy.adminChecking}</strong></div>
}
