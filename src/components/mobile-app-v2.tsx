import { useEffect, useMemo, useRef, useState, type MutableRefObject, type ReactNode } from 'react'
import { importLibrary, setOptions } from '@googlemaps/js-api-loader'
import {
  Bell,
  BriefcaseBusiness,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Crosshair,
  Heart,
  Home,
  Layers3,
  Mail,
  Map,
  MapPin,
  Menu,
  MessageCircle,
  PenTool,
  Plus,
  Search,
  SlidersHorizontal,
  UserRound,
  Users,
  X,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import '@/mobile-app-v2.css'

type OnboardingStep = 'language' | 'country' | 'privacy' | 'auth' | 'done'
type OnboardingOrigin = 'startup' | 'language-settings' | 'region-settings' | 'region-location' | 'account'
type MobileTab = 'home' | 'searches' | 'favorites' | 'messages' | 'menu'
type AppLanguage = 'es' | 'en' | 'ru'
type SearchMode = 'vivienda' | 'turismo' | null
type AppPage = 'tabs' | 'location' | 'map'
type MapMode = 'draw' | 'search'
type OccupantOption = 'anyone' | 'man' | 'woman' | 'person' | 'couple' | 'unrestricted'
type MapStatus = 'loading' | 'ready' | 'error'
type LocationStatus = 'idle' | 'loading' | 'success' | 'error'

const LANGUAGE_KEY = '112233:mobile-language:v2'
const TENERIFE_CENTER = { lat: 28.2916, lng: -16.6291 }
const GENERAL_OCCUPANTS = new Set<OccupantOption>(['anyone', 'unrestricted'])

const languages: Array<{ value: AppLanguage; label: string }> = [
  { value: 'es', label: 'Español' },
  { value: 'en', label: 'English' },
  { value: 'ru', label: 'Русский' },
]

const copy = {
  es: {
    languageTitle: 'Selecciona el idioma de la aplicación', continue: 'Continuar', regionTitle: 'Selecciona la región en la que buscas o tienes una vivienda',
    privacyTitle: 'Gracias por instalar nuestra aplicación', privacyText: 'Necesitamos tu permiso para personalizar las funciones disponibles según el uso que hagas del sitio web y de la aplicación.',
    skip: 'Ahora no', authTitle: 'Inicia sesión o regístrate', googleContinue: 'Continuar con Google', emailLogin: 'Iniciar sesión con email',
    legalIntro: 'Consulta la siguiente información:', privacyPolicy: 'Política de privacidad', terms: 'Términos y condiciones',
    housingMode: 'Vivienda', tourismMode: 'Turismo', occupantQuestion: '¿Quién vivirá?', occupantPrefix: 'Para quién:', occupantAnyone: 'cualquiera',
    occupantMan: 'solo un hombre', occupantWoman: 'solo una mujer', occupantPerson: 'una persona', occupantCouple: 'solo pareja', occupantUnrestricted: 'sin restricción', done: 'Listo',
    searchTenerife: 'Buscar en Tenerife', search: 'Buscar', publishAd: 'Publicar anuncio', searchesTitle: 'Tus búsquedas', searchesHeading: 'Todas tus búsquedas en un solo lugar',
    searchesText: 'Guarda aquí tus búsquedas habituales para acceder a ellas más fácilmente. También te avisaremos cuando aparezcan nuevos anuncios que coincidan con tus criterios.',
    favoritesTitle: 'Favoritos y listas', favoritesHeading: 'No tienes viviendas en favoritos', favoritesText: 'Guarda los anuncios que te gusten en tu cuenta para consultarlos desde el teléfono, la tableta o el ordenador.',
    chatTitle: 'Chat', chatHeading: 'Inicia sesión para ver tus chats', chatText: 'Habla con propietarios y anunciantes y responde a los mensajes nuevos. Todas tus conversaciones estarán disponibles en 112233.es.',
    login: 'Iniciar sesión', menu: 'Menú', loginDescription: 'Sincroniza tus favoritos y búsquedas en el ordenador, la tableta y el teléfono móvil.',
    yourProperties: 'Tus propiedades', findAgencies: 'Buscar agencias para vender', publishYourAd: 'Publica tu anuncio', settings: 'Ajustes', searchRegion: 'Región de búsqueda',
    language: 'Idioma', appearance: 'Apariencia', appearanceDefault: 'Predeterminada (oscura)', about: 'Acerca de la aplicación', version: 'Versión 14.5.0',
    home: 'Inicio', searches: 'Búsquedas', favorites: 'Favoritos', chat: 'Chat', mainNavigation: 'Navegación principal', heroAlt: 'Interior de una vivienda',
    locationTitle: '¿Dónde buscas?', regionSearch: 'Búsqueda en Tenerife', change: 'Cambiar', locationPlaceholder: 'Municipio, zona o dirección', alsoYouCan: 'También puedes',
    drawZone: 'Dibujar tu zona', searchOnMap: 'Buscar en el mapa', mapDrawTitle: 'Tu propia zona', visibleArea: 'Zona visible', filters: 'Filtros', list: 'Listado',
    save: 'Guardar', saved: 'Guardado', layers: 'Cambiar capas', locate: 'Mi ubicación', mapLoading: 'Cargando mapa…', mapError: 'No se pudo cargar Google Maps',
    locating: 'Buscando tu ubicación…', locationFound: 'Ubicación encontrada', locationDenied: 'No se pudo obtener tu ubicación', back: 'Volver', close: 'Cerrar', clear: 'Borrar búsqueda',
  },
  en: {
    languageTitle: 'Select the app language', continue: 'Continue', regionTitle: 'Select the region where you are looking for or own a property',
    privacyTitle: 'Thank you for installing our app', privacyText: 'We need your permission to personalize the available features based on how you use the website and the app.',
    skip: 'Not now', authTitle: 'Sign in or create an account', googleContinue: 'Continue with Google', emailLogin: 'Sign in with email', legalIntro: 'Review the following information:',
    privacyPolicy: 'Privacy policy', terms: 'Terms and conditions', housingMode: 'Housing', tourismMode: 'Tourism', occupantQuestion: 'Who will live there?', occupantPrefix: 'For:',
    occupantAnyone: 'anyone', occupantMan: 'men only', occupantWoman: 'women only', occupantPerson: 'one person', occupantCouple: 'couples only', occupantUnrestricted: 'no restriction', done: 'Done',
    searchTenerife: 'Search in Tenerife', search: 'Search', publishAd: 'Publish an ad', searchesTitle: 'Your searches', searchesHeading: 'All your searches in one place',
    searchesText: 'Save your frequent searches here for easier access. We will also notify you when new ads match your criteria.', favoritesTitle: 'Favorites and lists',
    favoritesHeading: 'You have no favorite properties', favoritesText: 'Save the ads you like to your account and view them on your phone, tablet, or computer.',
    chatTitle: 'Chat', chatHeading: 'Sign in to view your chats', chatText: 'Talk to property owners and advertisers and reply to new messages. All your conversations will be available on 112233.es.',
    login: 'Sign in', menu: 'Menu', loginDescription: 'Sync your favorites and searches across your computer, tablet, and mobile phone.', yourProperties: 'Your properties',
    findAgencies: 'Find agencies to sell', publishYourAd: 'Publish your ad', settings: 'Settings', searchRegion: 'Search region', language: 'Language', appearance: 'Appearance',
    appearanceDefault: 'Default (dark)', about: 'About the app', version: 'Version 14.5.0', home: 'Home', searches: 'Searches', favorites: 'Favorites', chat: 'Chat',
    mainNavigation: 'Main navigation', heroAlt: 'Home interior', locationTitle: 'Where are you looking?', regionSearch: 'Searching in Tenerife', change: 'Change',
    locationPlaceholder: 'Town, area or address', alsoYouCan: 'You can also', drawZone: 'Draw your own area', searchOnMap: 'Search on the map', mapDrawTitle: 'Your own area',
    visibleArea: 'Visible area', filters: 'Filters', list: 'List', save: 'Save', saved: 'Saved', layers: 'Change map layers', locate: 'My location', mapLoading: 'Loading map…',
    mapError: 'Google Maps could not be loaded', locating: 'Finding your location…', locationFound: 'Location found', locationDenied: 'Your location could not be obtained',
    back: 'Back', close: 'Close', clear: 'Clear search',
  },
  ru: {
    languageTitle: 'Выберите язык приложения', continue: 'Продолжить', regionTitle: 'Выберите регион, в котором вы ищете или имеете жильё',
    privacyTitle: 'Спасибо, что установили наше приложение', privacyText: 'Нам нужно ваше разрешение на персонализацию доступных функций в зависимости от использования сайта и приложения.',
    skip: 'Сейчас нет', authTitle: 'Войти в аккаунт или зарегистрироваться', googleContinue: 'Продолжить с Google', emailLogin: 'Войти с помощью email',
    legalIntro: 'Ознакомьтесь со следующей информацией:', privacyPolicy: 'Политика конфиденциальности', terms: 'Общие положения и условия', housingMode: 'Жильё', tourismMode: 'Туризм',
    occupantQuestion: 'Кто будет жить?', occupantPrefix: 'Для кого:', occupantAnyone: 'для любого', occupantMan: 'только мужчина', occupantWoman: 'только женщина',
    occupantPerson: 'один человек', occupantCouple: 'только пара', occupantUnrestricted: 'без ограничений', done: 'Готово', searchTenerife: 'Искать на Тенерифе',
    search: 'Найти', publishAd: 'Разместить объявление', searchesTitle: 'Ваши поиски', searchesHeading: 'Все ваши поиски в одном месте',
    searchesText: 'Сохраняйте здесь частые настройки поиска для большего удобства. Также мы уведомим вас о появлении новых объявлений, совпадающих с вашими критериями.',
    favoritesTitle: 'Избранное и списки', favoritesHeading: 'У вас нет объектов в избранном', favoritesText: 'Сохраните понравившиеся объявления в аккаунте, чтобы просматривать их на телефоне, планшете или компьютере.',
    chatTitle: 'Чат', chatHeading: 'Войдите в аккаунт, чтобы увидеть свои чаты', chatText: 'Общайтесь с владельцами объектов и рекламодателями и отвечайте на новые сообщения. Все разговоры будут доступны на 112233.es.',
    login: 'Войти в аккаунт', menu: 'Меню', loginDescription: 'Синхронизируйте избранное и поиски на компьютере, планшете и мобильном телефоне.',
    yourProperties: 'Ваши объекты', findAgencies: 'Искать агентства для продажи', publishYourAd: 'Опубликовать своё объявление', settings: 'Настройки', searchRegion: 'Регион поиска',
    language: 'Язык', appearance: 'Внешний вид', appearanceDefault: 'По умолчанию (тёмный)', about: 'О приложении', version: 'Версия 14.5.0', home: 'Главная',
    searches: 'Поиски', favorites: 'Избранное', chat: 'Чат', mainNavigation: 'Основная навигация', heroAlt: 'Интерьер жилого помещения', locationTitle: 'Где вы ищете?',
    regionSearch: 'Поиск на Тенерифе', change: 'Изменить', locationPlaceholder: 'Город, район или адрес', alsoYouCan: 'Также вы можете', drawZone: 'Нарисовать свою зону',
    searchOnMap: 'Искать на карте', mapDrawTitle: 'Ваша собственная зона', visibleArea: 'Видимая зона', filters: 'Фильтры', list: 'Перечень', save: 'Сохранить',
    saved: 'Сохранено', layers: 'Сменить слой карты', locate: 'Моё местоположение', mapLoading: 'Загрузка карты…', mapError: 'Не удалось загрузить Google Maps',
    locating: 'Определяем местоположение…', locationFound: 'Местоположение найдено', locationDenied: 'Не удалось определить местоположение', back: 'Назад', close: 'Закрыть', clear: 'Очистить поиск',
  },
} as const

type MobileCopy = Record<keyof typeof copy.es, string>

const darkMapStyles: google.maps.MapTypeStyle[] = [
  { elementType: 'geometry', stylers: [{ color: '#1e2938' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#1e2938' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#9ba7b6' }] },
  { featureType: 'administrative.locality', elementType: 'labels.text.fill', stylers: [{ color: '#d0a36f' }] },
  { featureType: 'poi', elementType: 'labels.text.fill', stylers: [{ color: '#87a078' }] },
  { featureType: 'poi.park', elementType: 'geometry', stylers: [{ color: '#203b36' }] },
  { featureType: 'road', elementType: 'geometry', stylers: [{ color: '#4f5560' }] },
  { featureType: 'road', elementType: 'geometry.stroke', stylers: [{ color: '#2f3440' }] },
  { featureType: 'road', elementType: 'labels.text.fill', stylers: [{ color: '#b8a48d' }] },
  { featureType: 'transit', elementType: 'geometry', stylers: [{ color: '#2a3442' }] },
  { featureType: 'water', elementType: 'geometry', stylers: [{ color: '#142536' }] },
  { featureType: 'water', elementType: 'labels.text.fill', stylers: [{ color: '#70879a' }] },
]

let mapsConfigured = false

function configureMaps(language: AppLanguage) {
  if (mapsConfigured) return
  const key = import.meta.env.VITE_GOOGLE_MAPS_API_KEY
  if (!key) throw new Error('VITE_GOOGLE_MAPS_API_KEY is missing')
  const mapId = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID
  setOptions({ key, v: 'weekly', language, region: 'ES', ...(mapId ? { mapIds: [mapId] } : {}) })
  mapsConfigured = true
}

function Brand({ compact = false }: { compact?: boolean }) {
  return <div className={cn('m2-brand', compact && 'm2-brand--compact')} aria-label="www.112233.es">www.112233.es</div>
}

function PrimaryButton({ children, onClick, testId }: { children: ReactNode; onClick?: () => void; testId?: string }) {
  return <button type="button" className="m2-primary" onClick={onClick} data-testid={testId}>{children}</button>
}

function BackHeader({ title, onBack, backLabel }: { title: string; onBack: () => void; backLabel: string }) {
  return <header className="m2-back-header">
    <button type="button" className="m2-icon-button" onClick={onBack} aria-label={backLabel}><ChevronLeft /></button>
    <strong>{title}</strong><div className="m2-back-header__right" />
  </header>
}

function AuthPanel({ onContinue, t }: { onContinue: () => void; t: MobileCopy }) {
  return <div className="m2-auth-panel">
    <Brand /><span>España (Tenerife)</span><h1>{t.authTitle}</h1>
    <button type="button" onClick={onContinue}><b>G</b>{t.googleContinue}</button>
    <button type="button" onClick={onContinue}><Mail />{t.emailLogin}</button>
    <p>{t.legalIntro}</p><a href="#privacy">{t.privacyPolicy}</a><a href="#terms">{t.terms}</a>
  </div>
}

function Onboarding({ step, origin, language, setLanguage, onStep, onCountryContinue, onLanguageContinue, onAuthBack, onDone }: {
  step: OnboardingStep; origin: OnboardingOrigin; language: AppLanguage; setLanguage: (language: AppLanguage) => void; onStep: (step: OnboardingStep) => void
  onCountryContinue: () => void; onLanguageContinue: () => void; onAuthBack: () => void; onDone: () => void
}) {
  const t: MobileCopy = copy[language]
  if (step === 'auth') return <section className="m2-onboarding m2-onboarding--auth">
    <button type="button" className="m2-auth-back" onClick={onAuthBack} aria-label={t.back}>‹</button>
    <button type="button" className="m2-auth-skip" onClick={onDone}>{t.skip}</button><AuthPanel onContinue={onDone} t={t} />
  </section>

  return <section className="m2-onboarding">
    <Brand />
    {step === 'language' ? <><div className="m2-onboarding__content"><h1>{t.languageTitle}</h1><div className="m2-language-list">
      {languages.map(({ value, label }) => <button key={value} type="button" className={cn(value === language && 'is-selected')} aria-pressed={value === language} onClick={() => setLanguage(value)}>
        <span lang={value}>{label}</span>{value === language ? <Check /> : null}
      </button>)}
    </div></div><PrimaryButton onClick={onLanguageContinue}>{t.continue}</PrimaryButton></> : null}
    {step === 'country' ? <><div className="m2-onboarding__content"><h1>{t.regionTitle}</h1><button type="button" className="m2-country is-selected" aria-pressed="true">
      <span>ES</span><strong>España (Tenerife)</strong><Check />
    </button></div><PrimaryButton onClick={onCountryContinue}>{t.continue}</PrimaryButton></> : null}
    {step === 'privacy' ? <><div className="m2-onboarding__content m2-privacy"><h1>{t.privacyTitle}</h1><p>{t.privacyText}</p></div>
      <PrimaryButton onClick={() => onStep('auth')}>{t.continue}</PrimaryButton></> : null}
    <span className="m2-sr-only">{origin}</span>
  </section>
}

function getOccupantOptions(t: MobileCopy): Array<{ value: OccupantOption; label: string }> {
  return [
    { value: 'anyone', label: t.occupantAnyone }, { value: 'man', label: t.occupantMan }, { value: 'woman', label: t.occupantWoman },
    { value: 'person', label: t.occupantPerson }, { value: 'couple', label: t.occupantCouple }, { value: 'unrestricted', label: t.occupantUnrestricted },
  ]
}

function OccupantSelector({ t }: { t: MobileCopy }) {
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState<OccupantOption[]>(['anyone'])
  const options = getOccupantOptions(t)
  const summary = useMemo(() => `${t.occupantPrefix} ${options.filter((option) => selected.includes(option.value)).map((option) => option.label).join(', ')}`, [options, selected, t.occupantPrefix])

  useEffect(() => {
    if (!open) return
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', closeOnEscape)
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener('keydown', closeOnEscape) }
  }, [open])

  const toggle = (value: OccupantOption) => {
    if (GENERAL_OCCUPANTS.has(value)) { setSelected([value]); return }
    setSelected((current) => {
      const specific = current.filter((item) => !GENERAL_OCCUPANTS.has(item))
      const next = specific.includes(value) ? specific.filter((item) => item !== value) : [...specific, value]
      return next.length ? next : ['anyone']
    })
  }

  return <>
    <button type="button" className="m2-occupant-trigger" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-expanded={open} aria-label={`${t.occupantQuestion} ${summary}`}>
      <Users /><span><small>{t.occupantQuestion}</small><strong>{summary}</strong></span><ChevronDown />
    </button>
    {open ? <div className="m2-sheet-backdrop" onClick={() => setOpen(false)}><section className="m2-sheet" role="dialog" aria-modal="true" aria-label={t.occupantQuestion} onClick={(event) => event.stopPropagation()}>
      <header><strong>{t.occupantQuestion}</strong><button type="button" onClick={() => setOpen(false)} aria-label={t.close}><X /></button></header>
      <div className="m2-check-list" role="group" aria-label={t.occupantQuestion}>{options.map((option) => {
        const checked = selected.includes(option.value)
        return <button key={option.value} type="button" role="checkbox" aria-checked={checked} className={cn(checked && 'is-selected')} onClick={() => toggle(option.value)}>
          <span>{t.occupantPrefix} {option.label}</span><i>{checked ? <Check /> : null}</i>
        </button>
      })}</div><PrimaryButton onClick={() => setOpen(false)}>{t.done}</PrimaryButton>
    </section></div> : null}
  </>
}

function HomeScreen({ t, onLocation }: { t: MobileCopy; onLocation: () => void }) {
  const [mode, setMode] = useState<SearchMode>(null)
  return <section className="m2-screen m2-home"><header className="m2-topbar"><Brand compact /></header><div className="m2-hero" role="img" aria-label={t.heroAlt} />
    <div className="m2-search-card"><div className="m2-mode-switch" role="group" aria-label={`${t.housingMode} / ${t.tourismMode}`}>
      <button type="button" className={cn(mode === 'vivienda' && 'is-active')} onClick={() => setMode('vivienda')} aria-pressed={mode === 'vivienda'}><span className="m2-mode-icon m2-mode-icon--home"><Home /></span><span>{t.housingMode}</span></button>
      <button type="button" className={cn(mode === 'turismo' && 'is-active')} onClick={() => setMode('turismo')} aria-pressed={mode === 'turismo'}><span className="m2-mode-icon m2-mode-icon--tourism"><BriefcaseBusiness /></span><span>{t.tourismMode}</span></button>
    </div><OccupantSelector t={t} />
      <button type="button" className="m2-select-row" onClick={onLocation}><span>{t.searchTenerife}</span><MapPin /></button>
      <PrimaryButton onClick={onLocation} testId="open-location"><Search />{t.search}</PrimaryButton><button type="button" className="m2-outline">{t.publishAd}</button>
    </div>
  </section>
}

function LocationScreen({ t, onBack, onChangeRegion, onMap }: { t: MobileCopy; onBack: () => void; onChangeRegion: () => void; onMap: (mode: MapMode, query?: string) => void }) {
  const [query, setQuery] = useState('')
  const submit = (event: React.FormEvent) => { event.preventDefault(); onMap('search', query.trim()) }
  return <section className="m2-screen m2-location" data-testid="location-screen"><BackHeader title={t.locationTitle} onBack={onBack} backLabel={t.back} />
    <div className="m2-location__body"><div className="m2-location-region"><strong>{t.regionSearch}</strong><button type="button" onClick={onChangeRegion}>{t.change}</button></div>
      <form className="m2-location-search" onSubmit={submit}><Search /><input value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder={t.locationPlaceholder} aria-label={t.locationPlaceholder} />
        {query ? <button type="button" className="m2-location-clear" onClick={() => setQuery('')} aria-label={t.clear}><X /></button> : null}
      </form><h2>{t.alsoYouCan}</h2>
      <button type="button" className="m2-location-action" onClick={() => onMap('draw')} data-testid="draw-zone"><span><PenTool /></span><strong>{t.drawZone}</strong><ChevronRight /></button>
      <button type="button" className="m2-location-action" onClick={() => onMap('search')} data-testid="search-map"><span><Map /></span><strong>{t.searchOnMap}</strong><ChevronRight /></button>
    </div>
  </section>
}

function GoogleMapCanvas({ language, t, mapRef, query, onStatus }: { language: AppLanguage; t: MobileCopy; mapRef: MutableRefObject<google.maps.Map | null>; query: string; onStatus: (status: MapStatus) => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<MapStatus>('loading')
  useEffect(() => {
    let cancelled = false
    const initialize = async () => {
      try {
        configureMaps(language)
        const { Map: GoogleMap } = await importLibrary('maps') as google.maps.MapsLibrary
        if (cancelled || !containerRef.current) return
        const mapId = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID
        const map = new GoogleMap(containerRef.current, {
          center: TENERIFE_CENTER, zoom: query ? 12 : 10, mapId: mapId || undefined, styles: mapId ? undefined : darkMapStyles, disableDefaultUI: true,
          gestureHandling: 'greedy', clickableIcons: false, backgroundColor: '#142536', minZoom: 8, maxZoom: 19,
          restriction: { latLngBounds: { north: 29.2, south: 27.1, east: -15.3, west: -18.2 }, strictBounds: false },
        })
        mapRef.current = map
        if (!cancelled) { setStatus('ready'); onStatus('ready') }
      } catch (error) {
        console.error('Google Maps initialization failed', error)
        if (!cancelled) { setStatus('error'); onStatus('error') }
      }
    }
    setStatus('loading'); onStatus('loading'); void initialize()
    return () => { cancelled = true; mapRef.current = null }
  }, [language, mapRef, onStatus, query])
  return <div className="m2-map-canvas-wrap"><div ref={containerRef} className="m2-map-canvas" data-testid="google-map" />
    {status === 'loading' ? <div className="m2-map-status" role="status">{t.mapLoading}</div> : null}
    {status === 'error' ? <div className="m2-map-status m2-map-status--error" role="alert">{t.mapError}</div> : null}
  </div>
}

function MapScreen({ mode, language, t, query, onBack }: { mode: MapMode; language: AppLanguage; t: MobileCopy; query: string; onBack: () => void }) {
  const mapRef = useRef<google.maps.Map | null>(null)
  const [mapType, setMapType] = useState<'roadmap' | 'hybrid'>('roadmap')
  const [saved, setSaved] = useState(false)
  const [mapStatus, setMapStatus] = useState<MapStatus>('loading')
  const [locationStatus, setLocationStatus] = useState<LocationStatus>('idle')
  const toggleLayers = () => { const next = mapType === 'roadmap' ? 'hybrid' : 'roadmap'; setMapType(next); mapRef.current?.setMapTypeId(next) }
  const locate = () => {
    if (!navigator.geolocation) { setLocationStatus('error'); return }
    setLocationStatus('loading')
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      mapRef.current?.panTo({ lat: coords.latitude, lng: coords.longitude }); mapRef.current?.setZoom(14); setLocationStatus('success')
    }, () => setLocationStatus('error'), { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 })
  }
  const locationMessage = locationStatus === 'loading' ? t.locating : locationStatus === 'success' ? t.locationFound : locationStatus === 'error' ? t.locationDenied : ''
  return <section className="m2-map-screen" data-testid={`map-${mode}`}>
    {mode === 'draw' ? <BackHeader title={t.mapDrawTitle} onBack={onBack} backLabel={t.back} /> : <><header className="m2-map-results-header">
      <button type="button" className="m2-icon-button" onClick={onBack} aria-label={t.back}><ChevronLeft /></button><div><strong>Tenerife</strong><small>{query || t.visibleArea}</small></div>
      <button type="button" className={cn('m2-save', saved && 'is-saved')} onClick={() => setSaved((value) => !value)} aria-pressed={saved}>{saved ? <Check /> : <Bell />}{saved ? t.saved : t.save}</button>
    </header><div className="m2-map-toolbar"><button type="button"><SlidersHorizontal />{t.filters}</button><button type="button"><Menu />{t.list}</button></div></>}
    <GoogleMapCanvas language={language} t={t} mapRef={mapRef} query={query} onStatus={setMapStatus} />
    <div className="m2-map-controls"><button type="button" onClick={toggleLayers} aria-label={t.layers} aria-pressed={mapType === 'hybrid'} disabled={mapStatus !== 'ready'}><Layers3 /></button>
      <button type="button" onClick={locate} aria-label={t.locate} disabled={mapStatus !== 'ready' || locationStatus === 'loading'}><Crosshair /></button></div>
    {locationMessage ? <div className={cn('m2-location-toast', locationStatus === 'error' && 'is-error')} role="status">{locationMessage}</div> : null}
    <button type="button" className="m2-draw-cta"><PenTool />{t.drawZone}</button>
  </section>
}

function EmptyScreen({ kind, onLogin, t }: { kind: 'searches' | 'favorites' | 'messages'; onLogin: () => void; t: MobileCopy }) {
  const data = { searches: { title: t.searchesTitle, heading: t.searchesHeading, text: t.searchesText, icon: <Bell /> }, favorites: { title: t.favoritesTitle, heading: t.favoritesHeading, text: t.favoritesText, icon: <Heart /> }, messages: { title: t.chatTitle, heading: t.chatHeading, text: t.chatText, icon: <MessageCircle /> } }[kind]
  return <section className="m2-screen m2-empty"><header>{data.title}</header><div className="m2-empty__icon">{data.icon}</div><h1>{data.heading}</h1><p>{data.text}</p><PrimaryButton onClick={onLogin}>{t.login}</PrimaryButton></section>
}

function MenuScreen({ onLogin, onLanguage, onRegion, language, t }: { onLogin: () => void; onLanguage: () => void; onRegion: () => void; language: AppLanguage; t: MobileCopy }) {
  const languageLabel = languages.find((item) => item.value === language)?.label ?? 'Español'
  return <section className="m2-screen m2-menu"><header>{t.menu}</header><div className="m2-menu-login"><UserRound /><div><h2>{t.login}</h2><p>{t.loginDescription}</p></div></div><PrimaryButton onClick={onLogin}>{t.login}</PrimaryButton>
    <h3>{t.yourProperties}</h3><button type="button" className="m2-menu-row"><span><Search />{t.findAgencies}</span><ChevronRight /></button><button type="button" className="m2-menu-row"><span><Plus />{t.publishYourAd}</span><ChevronRight /></button>
    <h3>{t.settings}</h3><button type="button" className="m2-menu-row" onClick={onRegion}><span>{t.searchRegion}</span><b>España (Tenerife)</b></button>
    <button type="button" className="m2-menu-row" onClick={onLanguage}><span>{t.language}</span><b>{languageLabel}</b></button><button type="button" className="m2-menu-row"><span>{t.appearance}</span><b>{t.appearanceDefault}</b></button>
    <button type="button" className="m2-menu-row"><span>{t.about}</span><b>{t.version}</b></button>
  </section>
}

function getNavItems(t: MobileCopy): Array<{ tab: MobileTab; label: string; icon: typeof Home }> {
  return [{ tab: 'home', label: t.home, icon: Home }, { tab: 'searches', label: t.searches, icon: Bell }, { tab: 'favorites', label: t.favorites, icon: Heart }, { tab: 'messages', label: t.chat, icon: MessageCircle }, { tab: 'menu', label: t.menu, icon: Menu }]
}

export function MobileAppV2() {
  const [step, setStep] = useState<OnboardingStep>('language')
  const [origin, setOrigin] = useState<OnboardingOrigin>('startup')
  const [page, setPage] = useState<AppPage>('tabs')
  const [mapMode, setMapMode] = useState<MapMode>('search')
  const [mapQuery, setMapQuery] = useState('')
  const [tab, setTab] = useState<MobileTab>('home')
  const [language, setLanguageState] = useState<AppLanguage>(() => { try { const saved = localStorage.getItem(LANGUAGE_KEY); return saved === 'es' || saved === 'en' || saved === 'ru' ? saved : 'es' } catch { return 'es' } })
  const t: MobileCopy = copy[language]
  const navItems = getNavItems(t)
  const setLanguage = (next: AppLanguage) => { setLanguageState(next); try { localStorage.setItem(LANGUAGE_KEY, next) } catch { /* private mode */ } }

  useEffect(() => { document.documentElement.classList.add('mobile-v2-active'); document.documentElement.lang = language; return () => document.documentElement.classList.remove('mobile-v2-active') }, [language])

  const returnToApp = () => { setStep('done'); setPage('tabs') }
  const finishAuth = () => { if (origin === 'startup') { setTab('home'); setPage('tabs') }; setStep('done') }
  const openAccount = () => { setOrigin('account'); setStep('auth') }
  const openLanguageSettings = () => { setOrigin('language-settings'); setStep('language') }
  const openRegionSettings = (from: 'menu' | 'location') => { setOrigin(from === 'menu' ? 'region-settings' : 'region-location'); setStep('country') }
  const handleLanguageContinue = () => { if (origin === 'language-settings') { setStep('done'); setPage('tabs'); setTab('menu') } else setStep('country') }
  const handleCountryContinue = () => {
    if (origin === 'region-location') { setStep('done'); setPage('location'); return }
    if (origin === 'region-settings') { setStep('done'); setPage('tabs'); setTab('menu'); return }
    setStep('privacy')
  }
  const authBack = () => { if (origin === 'startup') setStep('privacy'); else returnToApp() }
  const openMap = (mode: MapMode, query = '') => { setMapMode(mode); setMapQuery(query); setPage('map') }

  if (step !== 'done') return <div className="m2-app notranslate" translate="no"><Onboarding step={step} origin={origin} language={language} setLanguage={setLanguage} onStep={setStep} onCountryContinue={handleCountryContinue} onLanguageContinue={handleLanguageContinue} onAuthBack={authBack} onDone={finishAuth} /></div>
  if (page === 'location') return <div className="m2-app notranslate" translate="no"><LocationScreen t={t} onBack={() => setPage('tabs')} onChangeRegion={() => openRegionSettings('location')} onMap={openMap} /></div>
  if (page === 'map') return <div className="m2-app notranslate" translate="no"><MapScreen mode={mapMode} language={language} t={t} query={mapQuery} onBack={() => setPage('location')} /></div>

  return <div className="m2-app notranslate" translate="no"><main className="m2-main">
    {tab === 'home' ? <HomeScreen t={t} onLocation={() => setPage('location')} /> : null}
    {tab === 'searches' ? <EmptyScreen kind="searches" onLogin={openAccount} t={t} /> : null}
    {tab === 'favorites' ? <EmptyScreen kind="favorites" onLogin={openAccount} t={t} /> : null}
    {tab === 'messages' ? <EmptyScreen kind="messages" onLogin={openAccount} t={t} /> : null}
    {tab === 'menu' ? <MenuScreen onLogin={openAccount} onLanguage={openLanguageSettings} onRegion={() => openRegionSettings('menu')} language={language} t={t} /> : null}
  </main><nav className="m2-bottom-nav" aria-label={t.mainNavigation}>{navItems.map(({ tab: itemTab, label, icon: Icon }) => <button key={itemTab} type="button" className={cn(tab === itemTab && 'is-active')} aria-current={tab === itemTab ? 'page' : undefined} onClick={() => setTab(itemTab)}><Icon /><span>{label}</span></button>)}</nav></div>
}
