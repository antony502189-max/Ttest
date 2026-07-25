import { useEffect, useMemo, useRef, useState, type MutableRefObject, type ReactNode } from 'react'
import { importLibrary, setOptions } from '@googlemaps/js-api-loader'
import { useLocation, useNavigate } from 'react-router-dom'
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
  Trash2,
  UserRound,
  Users,
  X,
} from 'lucide-react'
import { MobileMapListingsLayer } from '@/components/mobile-map-listings-layer'
import { cn } from '@/lib/utils'
import { useApp } from '@/contexts/app-context'
import { useI18n, type Language } from '@/contexts/i18n-context'
import { persistListingAccessProfile, readListingAccessProfile, type HomeOccupantChoice } from '@/lib/listing-access'
import '@/mobile-app-v2.css'

type OnboardingStep = 'language' | 'country' | 'privacy' | 'auth' | 'done'
type OnboardingOrigin = 'startup' | 'language-settings' | 'region-settings' | 'region-location' | 'account'
type MobileTab = 'home' | 'searches' | 'favorites' | 'messages' | 'menu'
type AppLanguage = Language
type SearchMode = 'vivienda' | 'turismo' | null
type AppPage = 'tabs' | 'location' | 'map' | 'phone'
type MapMode = 'draw' | 'search'
type OccupantOption = 'anyone' | 'man' | 'woman' | 'person' | 'couple' | 'unrestricted'
type MapStatus = 'loading' | 'ready' | 'error'
type LocationStatus = 'idle' | 'loading' | 'success' | 'error'
type MapPoint = { lat: number; lng: number }
type DrawingStroke = { pointerId: number; lastX: number; lastY: number; points: MapPoint[] }
type MapInteractionState = {
  gestureHandling: google.maps.MapOptions['gestureHandling']
  draggable: google.maps.MapOptions['draggable']
  scrollwheel: google.maps.MapOptions['scrollwheel']
  disableDoubleClickZoom: google.maps.MapOptions['disableDoubleClickZoom']
  keyboardShortcuts: google.maps.MapOptions['keyboardShortcuts']
}

const ONBOARDING_KEY = '112233:mobile-onboarding:v1'
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
    searchesEmpty: 'Aún no tienes búsquedas guardadas', searchesEmptyText: 'Aplica tus condiciones y guárdalas desde los resultados.',
    favoritesTitle: 'Favoritos y listas', favoritesHeading: 'No tienes viviendas en favoritos', favoritesText: 'Guarda los anuncios que te gusten en tu cuenta para consultarlos desde el teléfono, la tableta o el ordenador.',
    chatTitle: 'Chat', chatHeading: 'Inicia sesión para ver tus chats', chatText: 'Habla con propietarios y anunciantes y responde a los mensajes nuevos. Todas tus conversaciones estarán disponibles en 112233.es.',
    chatEmpty: 'Todavía no hay mensajes', chatEmptyText: 'Cuando contactes con un anunciante, podrás volver a la conversación desde aquí.',
    login: 'Iniciar sesión', menu: 'Menú', loginDescription: 'Sincroniza tus favoritos y búsquedas en el ordenador, la tableta y el teléfono móvil.',
    yourProperties: 'Tus propiedades', findAgencies: 'Buscar agencias para vender', publishYourAd: 'Publica tu anuncio', settings: 'Ajustes', searchRegion: 'Región de búsqueda',
    language: 'Idioma', appearance: 'Apariencia', appearanceDefault: 'Predeterminada (oscura)', about: 'Acerca de la aplicación', version: 'Versión 14.5.0',
    home: 'Inicio', searches: 'Búsquedas', favorites: 'Favoritos', chat: 'Chat', mainNavigation: 'Navegación principal', heroAlt: 'Interior de una vivienda',
    locationTitle: '¿Dónde buscas?', regionSearch: 'Búsqueda en Tenerife', change: 'Cambiar', locationPlaceholder: 'Municipio, zona o dirección', alsoYouCan: 'También puedes',
    drawZone: 'Dibujar tu zona', redrawZone: 'Volver a dibujar', cancelDrawing: 'Cancelar dibujo', clearZone: 'Eliminar zona', drawInstruction: 'Mantén pulsado y dibuja el contorno',
    drawingInstruction: 'Rodea la zona y suelta el dedo', drawTooShort: 'Dibuja una zona más grande con un solo movimiento', areaReady: 'Zona seleccionada',
    searchOnMap: 'Buscar en el mapa', searchNearby: 'Buscar alrededor de ti', searchByPhone: 'Buscar por teléfono', mapDrawTitle: 'Tu propia zona', visibleArea: 'Zona visible', filters: 'Filtros', list: 'Listado',
    phoneIntro: '¿Has visto un cartel de "se vende" o "se alquila"? Introduce los datos para buscarlo', phone: 'Teléfono', operation: 'Operación',
    buy: 'Comprar', rent: 'Alquilar', type: 'Tipo', homes: 'Viviendas', invalidPhone: 'Introduce un teléfono válido', phoneNotFound: 'No hemos encontrado ningún anuncio con ese teléfono.',
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
    searchesEmpty: 'You have no saved searches yet', searchesEmptyText: 'Set your conditions and save them from the results.',
    favoritesHeading: 'You have no favorite properties', favoritesText: 'Save the ads you like to your account and view them on your phone, tablet, or computer.',
    chatTitle: 'Chat', chatHeading: 'Sign in to view your chats', chatText: 'Talk to property owners and advertisers and reply to new messages. All your conversations will be available on 112233.es.',
    chatEmpty: 'No messages yet', chatEmptyText: 'After contacting an advertiser, you can return to the conversation here.',
    login: 'Sign in', menu: 'Menu', loginDescription: 'Sync your favorites and searches across your computer, tablet, and mobile phone.', yourProperties: 'Your properties',
    findAgencies: 'Find agencies to sell', publishYourAd: 'Publish your ad', settings: 'Settings', searchRegion: 'Search region', language: 'Language', appearance: 'Appearance',
    appearanceDefault: 'Default (dark)', about: 'About the app', version: 'Version 14.5.0', home: 'Home', searches: 'Searches', favorites: 'Favorites', chat: 'Chat',
    mainNavigation: 'Main navigation', heroAlt: 'Home interior', locationTitle: 'Where are you looking?', regionSearch: 'Searching in Tenerife', change: 'Change',
    locationPlaceholder: 'Town, area or address', alsoYouCan: 'You can also', drawZone: 'Draw your own area', redrawZone: 'Draw again', cancelDrawing: 'Cancel drawing',
    clearZone: 'Delete area', drawInstruction: 'Press and draw the area outline', drawingInstruction: 'Draw around the area and release',
    drawTooShort: 'Draw a larger area in one continuous movement', areaReady: 'Area selected', searchOnMap: 'Search on the map', searchNearby: 'Search around you', searchByPhone: 'Search by phone', mapDrawTitle: 'Your own area',
    phoneIntro: 'Have you seen a "for sale" or "for rent" sign? Enter the details to find it', phone: 'Phone', operation: 'Operation',
    buy: 'Buy', rent: 'Rent', type: 'Type', homes: 'Homes', invalidPhone: 'Enter a valid phone number', phoneNotFound: 'We could not find a listing with that phone number.',
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
    searchesEmpty: 'У вас пока нет сохранённых поисков', searchesEmptyText: 'Выберите условия и сохраните их из результатов.',
    favoritesTitle: 'Избранное и списки', favoritesHeading: 'У вас нет объектов в избранном', favoritesText: 'Сохраните понравившиеся объявления в аккаунте, чтобы просматривать их на телефоне, планшете или компьютере.',
    chatTitle: 'Чат', chatHeading: 'Войдите в аккаунт, чтобы увидеть свои чаты', chatText: 'Общайтесь с владельцами объектов и рекламодателями и отвечайте на новые сообщения. Все разговоры будут доступны на 112233.es.',
    chatEmpty: 'Сообщений пока нет', chatEmptyText: 'После обращения к владельцу вы сможете вернуться к разговору отсюда.',
    login: 'Войти в аккаунт', menu: 'Меню', loginDescription: 'Синхронизируйте избранное и поиски на компьютере, планшете и мобильном телефоне.',
    yourProperties: 'Ваши объекты', findAgencies: 'Искать агентства для продажи', publishYourAd: 'Опубликовать своё объявление', settings: 'Настройки', searchRegion: 'Регион поиска',
    language: 'Язык', appearance: 'Внешний вид', appearanceDefault: 'По умолчанию (тёмный)', about: 'О приложении', version: 'Версия 14.5.0', home: 'Главная',
    searches: 'Поиски', favorites: 'Избранное', chat: 'Чат', mainNavigation: 'Основная навигация', heroAlt: 'Интерьер жилого помещения', locationTitle: 'Где вы ищете?',
    regionSearch: 'Поиск на Тенерифе', change: 'Изменить', locationPlaceholder: 'Город, район или адрес', alsoYouCan: 'Также вы можете', drawZone: 'Нарисовать свою зону',
    redrawZone: 'Нарисовать заново', cancelDrawing: 'Отменить рисование', clearZone: 'Удалить зону', drawInstruction: 'Зажмите и нарисуйте контур зоны',
    drawingInstruction: 'Обведите нужную территорию и отпустите', drawTooShort: 'Нарисуйте область побольше одним непрерывным движением', areaReady: 'Зона выбрана',
    searchOnMap: 'Искать на карте', searchNearby: 'Искать рядом с вами', searchByPhone: 'Искать по телефону', mapDrawTitle: 'Ваша собственная зона', visibleArea: 'Видимая зона', filters: 'Фильтры', list: 'Перечень', save: 'Сохранить',
    phoneIntro: 'Вы видели объявление «продаётся» или «сдаётся»? Введите данные, чтобы найти его', phone: 'Телефон', operation: 'Операция',
    buy: 'Купить', rent: 'Снять', type: 'Тип', homes: 'Жильё', invalidPhone: 'Введите корректный номер телефона', phoneNotFound: 'Объявление с таким номером телефона не найдено.',
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

function PrimaryButton({ children, onClick, testId, type = 'button' }: { children: ReactNode; onClick?: () => void; testId?: string; type?: 'button' | 'submit' }) {
  return <button type={type} className="m2-primary" onClick={onClick} data-testid={testId}>{children}</button>
}

function BackHeader({ title, onBack, backLabel }: { title: string; onBack: () => void; backLabel: string }) {
  return <header className="m2-back-header"><button type="button" className="m2-icon-button" onClick={onBack} aria-label={backLabel}><ChevronLeft /></button><strong>{title}</strong><div className="m2-back-header__right" /></header>
}

function AuthPanel({ onContinue, t }: { onContinue: () => void; t: MobileCopy }) {
  return <div className="m2-auth-panel"><Brand /><span>España (Tenerife)</span><h1>{t.authTitle}</h1><button type="button" onClick={onContinue}><b>G</b>{t.googleContinue}</button><button type="button" onClick={onContinue}><Mail />{t.emailLogin}</button><p>{t.legalIntro}</p><a href="#privacy">{t.privacyPolicy}</a><a href="#terms">{t.terms}</a></div>
}

function Onboarding({ step, origin, language, setLanguage, onStep, onCountryContinue, onLanguageContinue, onAuthBack, onDone }: {
  step: OnboardingStep; origin: OnboardingOrigin; language: AppLanguage; setLanguage: (language: AppLanguage) => void; onStep: (step: OnboardingStep) => void
  onCountryContinue: () => void; onLanguageContinue: () => void; onAuthBack: () => void; onDone: () => void
}) {
  const t: MobileCopy = copy[language]
  if (step === 'auth') return <section className="m2-onboarding m2-onboarding--auth"><button type="button" className="m2-auth-back" onClick={onAuthBack} aria-label={t.back}>‹</button><button type="button" className="m2-auth-skip" onClick={onDone}>{t.skip}</button><AuthPanel onContinue={onDone} t={t} /></section>
  return <section className="m2-onboarding"><Brand />
    {step === 'language' ? <><div className="m2-onboarding__content"><h1>{t.languageTitle}</h1><div className="m2-language-list">{languages.map(({ value, label }) => <button key={value} type="button" className={cn(value === language && 'is-selected')} aria-pressed={value === language} onClick={() => setLanguage(value)}><span lang={value}>{label}</span>{value === language ? <Check /> : null}</button>)}</div></div><PrimaryButton onClick={onLanguageContinue}>{t.continue}</PrimaryButton></> : null}
    {step === 'country' ? <><div className="m2-onboarding__content"><h1>{t.regionTitle}</h1><button type="button" className="m2-country is-selected" aria-pressed="true"><span>ES</span><strong>España (Tenerife)</strong><Check /></button></div><PrimaryButton onClick={onCountryContinue}>{t.continue}</PrimaryButton></> : null}
    {step === 'privacy' ? <><div className="m2-onboarding__content m2-privacy"><h1>{t.privacyTitle}</h1><p>{t.privacyText}</p></div><PrimaryButton onClick={() => onStep('auth')}>{t.continue}</PrimaryButton></> : null}
    <span className="m2-sr-only">{origin}</span>
  </section>
}

function getOccupantOptions(t: MobileCopy): Array<{ value: OccupantOption; label: string }> {
  return [{ value: 'anyone', label: t.occupantAnyone }, { value: 'man', label: t.occupantMan }, { value: 'woman', label: t.occupantWoman }, { value: 'person', label: t.occupantPerson }, { value: 'couple', label: t.occupantCouple }, { value: 'unrestricted', label: t.occupantUnrestricted }]
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
  useEffect(() => {
    const specific = selected.filter((value) => !GENERAL_OCCUPANTS.has(value))
    const occupantMap: Partial<Record<OccupantOption, HomeOccupantChoice>> = {
      man: 'single-man',
      woman: 'single-woman',
      person: 'single-person',
      couple: 'couple',
    }
    const occupant = specific.length === 1 ? occupantMap[specific[0]] ?? 'any' : 'any'
    persistListingAccessProfile({ ...readListingAccessProfile(), occupant })
  }, [selected])
  const toggle = (value: OccupantOption) => {
    if (GENERAL_OCCUPANTS.has(value)) { setSelected([value]); return }
    setSelected((current) => {
      const specific = current.filter((item) => !GENERAL_OCCUPANTS.has(item))
      const next = specific.includes(value) ? specific.filter((item) => item !== value) : [...specific, value]
      return next.length ? next : ['anyone']
    })
  }
  return <><button type="button" className="m2-occupant-trigger" onClick={() => setOpen(true)} aria-haspopup="dialog" aria-expanded={open} aria-label={`${t.occupantQuestion} ${summary}`}><Users /><span><small>{t.occupantQuestion}</small><strong>{summary}</strong></span><ChevronDown /></button>
    {open ? <div className="m2-sheet-backdrop" onClick={() => setOpen(false)}><section className="m2-sheet" role="dialog" aria-modal="true" aria-label={t.occupantQuestion} onClick={(event) => event.stopPropagation()}><header><strong>{t.occupantQuestion}</strong><button type="button" onClick={() => setOpen(false)} aria-label={t.close}><X /></button></header><div className="m2-check-list" role="group" aria-label={t.occupantQuestion}>{options.map((option) => { const checked = selected.includes(option.value); return <button key={option.value} type="button" role="checkbox" aria-checked={checked} className={cn(checked && 'is-selected')} onClick={() => toggle(option.value)}><span>{t.occupantPrefix} {option.label}</span><i>{checked ? <Check /> : null}</i></button> })}</div><PrimaryButton onClick={() => setOpen(false)}>{t.done}</PrimaryButton></section></div> : null}
  </>
}

function HomeScreen({ t, onLocation, onSearch, onPublish }: { t: MobileCopy; onLocation: () => void; onSearch: (mode: SearchMode) => void; onPublish: () => void }) {
  const [mode, setMode] = useState<SearchMode>(null)
  return <section className="m2-screen m2-home"><header className="m2-topbar"><Brand compact /></header><div className="m2-hero" role="img" aria-label={t.heroAlt} /><div className="m2-search-card"><div className="m2-mode-switch" role="group" aria-label={`${t.housingMode} / ${t.tourismMode}`}><button type="button" className={cn(mode === 'vivienda' && 'is-active')} onClick={() => setMode('vivienda')} aria-pressed={mode === 'vivienda'}><span className="m2-mode-icon m2-mode-icon--home"><Home /></span><span>{t.housingMode}</span></button><button type="button" className={cn(mode === 'turismo' && 'is-active')} onClick={() => setMode('turismo')} aria-pressed={mode === 'turismo'}><span className="m2-mode-icon m2-mode-icon--tourism"><BriefcaseBusiness /></span><span>{t.tourismMode}</span></button></div><OccupantSelector t={t} /><button type="button" className="m2-select-row" onClick={onLocation}><span>{t.searchTenerife}</span><MapPin /></button><PrimaryButton onClick={() => onSearch(mode)} testId="open-location"><Search />{t.search}</PrimaryButton><button type="button" className="m2-outline" onClick={onPublish}>{t.publishAd}</button></div></section>
}

function LocationScreen({ t, onBack, onChangeRegion, onMap }: {
  t: MobileCopy
  onBack: () => void
  onChangeRegion: () => void
  onMap: (mode: MapMode, query?: string) => void
}) {
  const [query, setQuery] = useState('')
  const submit = (event: React.FormEvent) => { event.preventDefault(); onMap('search', query.trim()) }
  return <section className="m2-screen m2-location" data-testid="location-screen"><BackHeader title={t.locationTitle} onBack={onBack} backLabel={t.back} /><div className="m2-location__body"><div className="m2-location-region"><strong>{t.regionSearch}</strong><button type="button" onClick={onChangeRegion}>{t.change}</button></div><form className="m2-location-search" onSubmit={submit}><Search /><input value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder={t.locationPlaceholder} aria-label={t.locationPlaceholder} />{query ? <button type="button" className="m2-location-clear" onClick={() => setQuery('')} aria-label={t.clear}><X /></button> : null}</form><h2>{t.alsoYouCan}</h2><button type="button" className="m2-location-action" onClick={() => onMap('draw')} data-testid="draw-zone"><span><PenTool /></span><strong>{t.drawZone}</strong><ChevronRight /></button><button type="button" className="m2-location-action" onClick={() => onMap('search')} data-testid="search-map"><span><Map /></span><strong>{t.searchOnMap}</strong><ChevronRight /></button></div></section>
}

function normalizePhone(value: string) {
  return value.replace(/\D/g, '')
}

function PhoneSearchScreen({ t, listings, onBack, onFound }: {
  t: MobileCopy
  listings: ReturnType<typeof useApp>['allListings']
  onBack: () => void
  onFound: (listingId: string) => void
}) {
  const [phone, setPhone] = useState('')
  const [operation, setOperation] = useState<'buy' | 'rent'>('buy')
  const [error, setError] = useState('')
  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    const normalized = normalizePhone(phone)
    if (normalized.length < 7) {
      setError(t.invalidPhone)
      return
    }
    const match = listings.find((listing) => [listing.contactPhone, listing.contactWhatsapp].some((value) => value && normalizePhone(value).endsWith(normalized)))
    if (!match) {
      setError(t.phoneNotFound)
      return
    }
    onFound(match.id)
  }
  return <section className="m2-phone-search" data-testid="phone-search-screen">
    <BackHeader title={t.searchByPhone} onBack={onBack} backLabel={t.back} />
    <form onSubmit={submit}>
      <p>{t.phoneIntro}</p>
      <label htmlFor="m2-phone-input">{t.phone}</label>
      <input id="m2-phone-input" value={phone} onChange={(event) => { setPhone(event.target.value); setError('') }} type="tel" inputMode="tel" autoComplete="tel" />
      <fieldset>
        <legend>{t.operation}</legend>
        <div className="m2-phone-toggle">
          <button type="button" className={cn(operation === 'buy' && 'is-active')} aria-pressed={operation === 'buy'} onClick={() => setOperation('buy')}>{t.buy}</button>
          <button type="button" className={cn(operation === 'rent' && 'is-active')} aria-pressed={operation === 'rent'} onClick={() => setOperation('rent')}>{t.rent}</button>
        </div>
      </fieldset>
      <label htmlFor="m2-phone-type">{t.type}</label>
      <select id="m2-phone-type" defaultValue="homes"><option value="homes">{t.homes}</option></select>
      {error ? <p className="m2-phone-error" role="alert">{error}</p> : null}
      <PrimaryButton type="submit" testId="submit-phone-search"><Search />{t.search}</PrimaryButton>
    </form>
  </section>
}

function GoogleMapCanvas({ language, t, mapRef, query, initialCenter, onStatus }: { language: AppLanguage; t: MobileCopy; mapRef: MutableRefObject<google.maps.Map | null>; query: string; initialCenter?: MapPoint; onStatus: (status: MapStatus) => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<MapStatus>('loading')
  const initialLat = initialCenter?.lat
  const initialLng = initialCenter?.lng
  useEffect(() => {
    let cancelled = false
    const initialize = async () => {
      try {
        configureMaps(language)
        const { Map: GoogleMap } = await importLibrary('maps') as google.maps.MapsLibrary
        if (cancelled || !containerRef.current) return
        const mapId = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID
        const hasInitialCenter = initialLat !== undefined && initialLng !== undefined
        const map = new GoogleMap(containerRef.current, { center: hasInitialCenter ? { lat: initialLat, lng: initialLng } : TENERIFE_CENTER, zoom: hasInitialCenter ? 14 : query ? 12 : 10, mapId: mapId || undefined, styles: mapId ? undefined : darkMapStyles, disableDefaultUI: true, gestureHandling: 'greedy', clickableIcons: false, backgroundColor: '#142536', minZoom: 8, maxZoom: 19, restriction: { latLngBounds: { north: 29.2, south: 27.1, east: -15.3, west: -18.2 }, strictBounds: false } })
        mapRef.current = map
        google.maps.event.addListenerOnce(map, 'idle', () => { if (!cancelled) { setStatus('ready'); onStatus('ready') } })
      } catch (error) {
        console.error('Google Maps initialization failed', error)
        if (!cancelled) { setStatus('error'); onStatus('error') }
      }
    }
    setStatus('loading'); onStatus('loading'); void initialize()
    return () => { cancelled = true; mapRef.current = null }
  }, [initialLat, initialLng, language, mapRef, onStatus, query])
  return <div className="m2-map-canvas-wrap"><div ref={containerRef} className="m2-map-canvas" data-testid="google-map" />{status === 'loading' ? <div className="m2-map-status" role="status">{t.mapLoading}</div> : null}{status === 'error' ? <div className="m2-map-status m2-map-status--error" role="alert">{t.mapError}</div> : null}</div>
}

function captureMapInteractions(map: google.maps.Map): MapInteractionState {
  return {
    gestureHandling: map.get('gestureHandling') as MapInteractionState['gestureHandling'],
    draggable: map.get('draggable') as MapInteractionState['draggable'],
    scrollwheel: map.get('scrollwheel') as MapInteractionState['scrollwheel'],
    disableDoubleClickZoom: map.get('disableDoubleClickZoom') as MapInteractionState['disableDoubleClickZoom'],
    keyboardShortcuts: map.get('keyboardShortcuts') as MapInteractionState['keyboardShortcuts'],
  }
}

function mapPointFromPointer(map: google.maps.Map, clientX: number, clientY: number): MapPoint | null {
  const projection = map.getProjection()
  const center = map.getCenter()
  const zoom = map.getZoom()
  if (!projection || !center || zoom === undefined) return null
  const centerPoint = projection.fromLatLngToPoint(center)
  if (!centerPoint) return null
  const bounds = map.getDiv().getBoundingClientRect()
  const scale = 2 ** zoom
  const worldPoint = new google.maps.Point(centerPoint.x + (clientX - bounds.left - bounds.width / 2) / scale, centerPoint.y + (clientY - bounds.top - bounds.height / 2) / scale)
  const latLng = projection.fromPointToLatLng(worldPoint, true)
  return latLng ? { lat: latLng.lat(), lng: latLng.lng() } : null
}

function pointLineDistance(point: MapPoint, start: MapPoint, end: MapPoint) {
  const dx = end.lng - start.lng
  const dy = end.lat - start.lat
  if (dx === 0 && dy === 0) return Math.hypot(point.lng - start.lng, point.lat - start.lat)
  const ratio = Math.max(0, Math.min(1, ((point.lng - start.lng) * dx + (point.lat - start.lat) * dy) / (dx * dx + dy * dy)))
  return Math.hypot(point.lng - (start.lng + ratio * dx), point.lat - (start.lat + ratio * dy))
}

function simplifyMapPath(points: MapPoint[], tolerance = 0.00018): MapPoint[] {
  if (points.length <= 3) return points
  let maxDistance = 0
  let splitIndex = 0
  for (let index = 1; index < points.length - 1; index += 1) {
    const distance = pointLineDistance(points[index], points[0], points[points.length - 1])
    if (distance > maxDistance) { maxDistance = distance; splitIndex = index }
  }
  if (maxDistance <= tolerance) return [points[0], points[points.length - 1]]
  const left = simplifyMapPath(points.slice(0, splitIndex + 1), tolerance)
  const right = simplifyMapPath(points.slice(splitIndex), tolerance)
  return [...left.slice(0, -1), ...right]
}

function FreehandAreaLayer({ mapRef, mapReady, active, setActive, polygon, onPolygonChange, t }: {
  mapRef: MutableRefObject<google.maps.Map | null>; mapReady: boolean; active: boolean; setActive: (active: boolean) => void
  polygon: MapPoint[]; onPolygonChange: (polygon: MapPoint[]) => void; t: MobileCopy
}) {
  const layerRef = useRef<google.maps.Polygon | google.maps.Polyline | null>(null)
  const interactionRef = useRef<MapInteractionState | null>(null)
  const strokeRef = useRef<DrawingStroke | null>(null)
  const [draft, setDraft] = useState<MapPoint[]>([])
  const [hint, setHint] = useState(t.drawInstruction)

  useEffect(() => { setHint(t.drawInstruction) }, [t.drawInstruction])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady) return
    layerRef.current?.setMap(null)
    const points = draft.length >= 2 ? draft : polygon
    if (points.length >= 3) {
      layerRef.current = new google.maps.Polygon({ map, paths: points, clickable: false, strokeColor: '#d2ff3f', strokeOpacity: 1, strokeWeight: 3, fillColor: '#d2ff3f', fillOpacity: .22, zIndex: 20 })
    } else if (points.length === 2) {
      layerRef.current = new google.maps.Polyline({ map, path: points, clickable: false, strokeColor: '#d2ff3f', strokeOpacity: 1, strokeWeight: 3, zIndex: 20 })
    }
    return () => { layerRef.current?.setMap(null); layerRef.current = null }
  }, [draft, mapReady, mapRef, polygon])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !mapReady || !active) return
    interactionRef.current = captureMapInteractions(map)
    map.setOptions({ gestureHandling: 'none', draggable: false, scrollwheel: false, disableDoubleClickZoom: true, keyboardShortcuts: false })
    setDraft([])
    setHint(t.drawInstruction)
    return () => {
      if (interactionRef.current) map.setOptions(interactionRef.current)
      interactionRef.current = null
      strokeRef.current = null
    }
  }, [active, mapReady, mapRef, t.drawInstruction])

  const appendPointerPoint = (stroke: DrawingStroke, clientX: number, clientY: number) => {
    const map = mapRef.current
    if (!map) return false
    const point = mapPointFromPointer(map, clientX, clientY)
    if (!point) return false
    stroke.lastX = clientX
    stroke.lastY = clientY
    stroke.points.push(point)
    setDraft([...stroke.points])
    return true
  }

  const pointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!event.isPrimary || (event.pointerType === 'mouse' && event.button !== 0)) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    setHint(t.drawingInstruction)
    const stroke: DrawingStroke = { pointerId: event.pointerId, lastX: event.clientX, lastY: event.clientY, points: [] }
    strokeRef.current = stroke
    appendPointerPoint(stroke, event.clientX, event.clientY)
  }

  const pointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const stroke = strokeRef.current
    if (!stroke || event.pointerId !== stroke.pointerId) return
    event.preventDefault()
    event.stopPropagation()
    const samples = event.nativeEvent.getCoalescedEvents?.() ?? [event.nativeEvent]
    const minimumDistance = event.pointerType === 'touch' ? 7 : 5
    samples.forEach((sample) => {
      const distance = Math.hypot(sample.clientX - stroke.lastX, sample.clientY - stroke.lastY)
      if (distance >= minimumDistance) appendPointerPoint(stroke, sample.clientX, sample.clientY)
    })
  }

  const finishStroke = (event: React.PointerEvent<HTMLDivElement>) => {
    const stroke = strokeRef.current
    if (!stroke || event.pointerId !== stroke.pointerId) return
    event.preventDefault()
    event.stopPropagation()
    const distance = Math.hypot(event.clientX - stroke.lastX, event.clientY - stroke.lastY)
    if (distance >= 3) appendPointerPoint(stroke, event.clientX, event.clientY)
    try { event.currentTarget.releasePointerCapture(event.pointerId) } catch { /* capture may already be released */ }
    strokeRef.current = null
    const simplified = simplifyMapPath(stroke.points)
    if (simplified.length < 3) {
      setDraft([])
      setHint(t.drawTooShort)
      return
    }
    const limited = simplified.length > 80 ? simplified.filter((_, index) => index % Math.ceil(simplified.length / 80) === 0) : simplified
    setDraft([])
    onPolygonChange(limited)
    setHint(t.areaReady)
    setActive(false)
  }

  const cancelStroke = (event: React.PointerEvent<HTMLDivElement>) => {
    if (strokeRef.current?.pointerId !== event.pointerId) return
    strokeRef.current = null
    setDraft([])
    setHint(t.drawInstruction)
  }

  if (!active) return null
  return <div className="m2-freehand-overlay" data-testid="freehand-overlay" role="application" aria-label={t.drawInstruction} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={finishStroke} onPointerCancel={cancelStroke} onContextMenu={(event) => event.preventDefault()}><span>{hint}</span></div>
}

function MapScreen({ mode, language, t, query, initialCenter, polygon, onPolygonChange, onBack, onSave, onList, onFilters }: {
  mode: MapMode; language: AppLanguage; t: MobileCopy; query: string; initialCenter?: MapPoint; polygon: MapPoint[]; onPolygonChange: (polygon: MapPoint[]) => void; onBack: () => void; onSave?: () => void; onList?: () => void; onFilters?: () => void
}) {
  const mapRef = useRef<google.maps.Map | null>(null)
  const [mapType, setMapType] = useState<'roadmap' | 'hybrid'>('roadmap')
  const [saved, setSaved] = useState(false)
  const [mapStatus, setMapStatus] = useState<MapStatus>('loading')
  const [locationStatus, setLocationStatus] = useState<LocationStatus>('idle')
  const [drawing, setDrawing] = useState(false)
  const toggleLayers = () => { const next = mapType === 'roadmap' ? 'hybrid' : 'roadmap'; setMapType(next); mapRef.current?.setMapTypeId(next) }
  const locate = () => {
    if (!navigator.geolocation) { setLocationStatus('error'); return }
    setLocationStatus('loading')
    navigator.geolocation.getCurrentPosition(({ coords }) => { mapRef.current?.panTo({ lat: coords.latitude, lng: coords.longitude }); mapRef.current?.setZoom(14); setLocationStatus('success') }, () => setLocationStatus('error'), { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 })
  }
  const locationMessage = locationStatus === 'loading' ? t.locating : locationStatus === 'success' ? t.locationFound : locationStatus === 'error' ? t.locationDenied : ''
  const mainDrawLabel = drawing ? t.cancelDrawing : polygon.length >= 3 ? t.redrawZone : t.drawZone
  const toggleDrawing = () => setDrawing((current) => !current)
  return <section className={cn('m2-map-screen', drawing && 'is-freehand-drawing', polygon.length >= 3 && 'has-drawn-zone')} data-testid={`map-${mode}`}>
    {mode === 'draw' ? <BackHeader title={t.mapDrawTitle} onBack={onBack} backLabel={t.back} /> : <><header className="m2-map-results-header"><button type="button" className="m2-icon-button" onClick={onBack} aria-label={t.back}><ChevronLeft /></button><div><strong>Tenerife</strong><small>{query || t.visibleArea}</small></div><button type="button" className={cn('m2-save', saved && 'is-saved')} onClick={() => { if (!saved) onSave?.(); setSaved((value) => !value) }} aria-pressed={saved}>{saved ? <Check /> : <Bell />}{saved ? t.saved : t.save}</button></header><div className="m2-map-toolbar"><button type="button" onClick={onFilters}><SlidersHorizontal />{t.filters}</button><button type="button" onClick={onList}><Menu />{t.list}</button></div></>}
    <GoogleMapCanvas language={language} t={t} mapRef={mapRef} query={query} initialCenter={initialCenter} onStatus={setMapStatus} />
    <MobileMapListingsLayer mapRef={mapRef} mapReady={mapStatus === 'ready'} language={language} drawing={drawing} />
    <FreehandAreaLayer mapRef={mapRef} mapReady={mapStatus === 'ready'} active={drawing} setActive={setDrawing} polygon={polygon} onPolygonChange={onPolygonChange} t={t} />
    <div className="m2-map-controls"><button type="button" onClick={toggleLayers} aria-label={t.layers} aria-pressed={mapType === 'hybrid'} disabled={mapStatus !== 'ready' || drawing}><Layers3 /></button><button type="button" onClick={locate} aria-label={t.locate} disabled={mapStatus !== 'ready' || locationStatus === 'loading' || drawing}><Crosshair /></button></div>
    {locationMessage ? <div className={cn('m2-location-toast', locationStatus === 'error' && 'is-error')} role="status">{locationMessage}</div> : null}
    <div className="m2-draw-actions">{polygon.length >= 3 && !drawing ? <button type="button" className="m2-clear-zone" onClick={() => onPolygonChange([])} aria-label={t.clearZone}><Trash2 /></button> : null}<button type="button" className="m2-draw-cta" onClick={toggleDrawing} disabled={mapStatus !== 'ready'} aria-pressed={drawing}><PenTool />{mainDrawLabel}</button></div>
  </section>
}

type MobileCollectionItem = { id: string; title: string; meta: string; onOpen: () => void }

function EmptyScreen({ kind, onLogin, onExplore, authenticated, t, items = [] }: { kind: 'searches' | 'favorites' | 'messages'; onLogin: () => void; onExplore: () => void; authenticated: boolean; t: MobileCopy; items?: MobileCollectionItem[] }) {
  const data = { searches: { title: t.searchesTitle, heading: t.searchesHeading, text: t.searchesText, icon: <Bell /> }, favorites: { title: t.favoritesTitle, heading: t.favoritesHeading, text: t.favoritesText, icon: <Heart /> }, messages: { title: t.chatTitle, heading: t.chatHeading, text: t.chatText, icon: <MessageCircle /> } }[kind]
  if (items.length) return <section className="m2-screen m2-empty m2-collection"><header>{data.title}</header><div className="m2-collection__list">{items.map((item) => <button type="button" key={item.id} onClick={item.onOpen}><span><strong>{item.title}</strong><small>{item.meta}</small></span><ChevronRight /></button>)}</div></section>
  const heading = authenticated && kind === 'searches' ? t.searchesEmpty : authenticated && kind === 'messages' ? t.chatEmpty : data.heading
  const text = authenticated && kind === 'searches' ? t.searchesEmptyText : authenticated && kind === 'messages' ? t.chatEmptyText : data.text
  return <section className="m2-screen m2-empty"><header>{data.title}</header><div className="m2-empty__icon">{data.icon}</div><h1>{heading}</h1><p>{text}</p><PrimaryButton onClick={authenticated ? onExplore : onLogin}>{authenticated ? t.search : t.login}</PrimaryButton></section>
}

function MenuScreen({ onLogin, onLanguage, onRegion, onAgencies, onPublish, language, t, currentUserName }: { onLogin: () => void; onLanguage: () => void; onRegion: () => void; onAgencies: () => void; onPublish: () => void; language: AppLanguage; t: MobileCopy; currentUserName?: string }) {
  const languageLabel = languages.find((item) => item.value === language)?.label ?? 'Español'
  return <section className="m2-screen m2-menu"><header>{t.menu}</header><div className="m2-menu-login"><UserRound /><div><h2>{currentUserName ?? t.login}</h2><p>{t.loginDescription}</p></div></div><PrimaryButton onClick={onLogin}>{currentUserName ? t.yourProperties : t.login}</PrimaryButton><h3>{t.yourProperties}</h3><button type="button" className="m2-menu-row" onClick={onAgencies}><span><Search />{t.findAgencies}</span><ChevronRight /></button><button type="button" className="m2-menu-row" onClick={onPublish}><span><Plus />{t.publishYourAd}</span><ChevronRight /></button><h3>{t.settings}</h3><button type="button" className="m2-menu-row" onClick={onRegion}><span>{t.searchRegion}</span><b>España (Tenerife)</b></button><button type="button" className="m2-menu-row" onClick={onLanguage}><span>{t.language}</span><b>{languageLabel}</b></button><button type="button" className="m2-menu-row"><span>{t.appearance}</span><b>{t.appearanceDefault}</b></button><button type="button" className="m2-menu-row"><span>{t.about}</span><b>{t.version}</b></button></section>
}

function getNavItems(t: MobileCopy): Array<{ tab: MobileTab; label: string; icon: typeof Home }> {
  return [{ tab: 'home', label: t.home, icon: Home }, { tab: 'searches', label: t.searches, icon: Bell }, { tab: 'favorites', label: t.favorites, icon: Heart }, { tab: 'messages', label: t.chat, icon: MessageCircle }, { tab: 'menu', label: t.menu, icon: Menu }]
}

const tabRoutes: Record<MobileTab, string> = {
  home: '/',
  searches: '/busquedas-guardadas',
  favorites: '/favoritos',
  messages: '/mensajes',
  menu: '/menu',
}

function tabFromPath(pathname: string): MobileTab {
  if (pathname === '/busquedas-guardadas') return 'searches'
  if (pathname === '/favoritos') return 'favorites'
  if (pathname === '/mensajes') return 'messages'
  if (pathname === '/menu') return 'menu'
  return 'home'
}

export function MobileAppV2() {
  const location = useLocation()
  const navigate = useNavigate()
  const { language, setLanguage } = useI18n()
  const { allListings, favorites, savedSearches, localThreads, mapPolygon, setMapPolygon, saveCurrentSearch, restoreSavedSearch, setQuery, currentUser } = useApp()
  const [step, setStep] = useState<OnboardingStep>(() => {
    try { return localStorage.getItem(ONBOARDING_KEY) === 'done' ? 'done' : 'language' } catch { return 'language' }
  })
  const [origin, setOrigin] = useState<OnboardingOrigin>('startup')
  const [page, setPage] = useState<AppPage>('tabs')
  const [mapMode, setMapMode] = useState<MapMode>('search')
  const [mapQuery, setMapQuery] = useState('')
  const [mapCenter, setMapCenter] = useState<MapPoint | undefined>()
  const [tab, setTab] = useState<MobileTab>(() => tabFromPath(location.pathname))
  const shellActive = ['/', '/buscar', '/favoritos', '/busquedas-guardadas', '/mensajes', '/menu'].includes(location.pathname)
  const t: MobileCopy = copy[language]
  const navItems = getNavItems(t)
  const favoriteItems = useMemo<MobileCollectionItem[]>(() => allListings.filter((listing) => favorites.has(listing.id)).map((listing) => ({ id: listing.id, title: listing.title, meta: `${listing.area}, ${listing.city} · ${listing.price} €`, onOpen: () => navigate(`/habitacion/${listing.id}`) })), [allListings, favorites, navigate])
  const savedSearchItems = useMemo<MobileCollectionItem[]>(() => savedSearches.map((search) => ({ id: search.id, title: search.query, meta: search.rentalMode === 'holiday' ? t.tourismMode : t.housingMode, onOpen: () => { restoreSavedSearch(search.id); navigate(`/buscar?q=${encodeURIComponent(search.query)}&alquiler=${search.rentalMode}`) } })), [navigate, restoreSavedSearch, savedSearches, t.housingMode, t.tourismMode])
  const messageItems = useMemo<MobileCollectionItem[]>(() => localThreads.map((thread) => ({ id: thread.id, title: thread.listingTitle, meta: `${thread.contactName} · ${thread.messagePreview}`, onOpen: () => navigate(`/habitacion/${thread.listingId}`) })), [localThreads, navigate])
  useEffect(() => {
    document.documentElement.classList.toggle('mobile-v2-active', shellActive)
    return () => document.documentElement.classList.remove('mobile-v2-active')
  }, [shellActive])
  useEffect(() => {
    if (step !== 'done') return
    const params = new URLSearchParams(location.search)
    if (location.pathname === '/buscar' && params.get('vista') === 'mapa') {
      setMapMode(params.get('dibujar') === '1' ? 'draw' : 'search')
      setMapQuery(params.get('q') ?? '')
      const latParam = params.get('lat')
      const lngParam = params.get('lng')
      const lat = Number(latParam)
      const lng = Number(lngParam)
      setMapCenter(latParam !== null && lngParam !== null && Number.isFinite(lat) && Number.isFinite(lng) ? { lat, lng } : undefined)
      setPage('map')
      return
    }
    if (location.pathname === '/' && params.get('panel') === 'ubicacion') {
      setPage('location')
      return
    }
    if (location.pathname === '/' && params.get('panel') === 'telefono') {
      setPage('phone')
      return
    }
    setPage('tabs')
    setTab(tabFromPath(location.pathname))
  }, [location.pathname, location.search, step])
  const persistOnboarding = () => { try { localStorage.setItem(ONBOARDING_KEY, 'done') } catch { /* private mode */ } }
  const returnToApp = () => { persistOnboarding(); setStep('done'); setPage('tabs') }
  const finishAuth = () => { persistOnboarding(); if (origin === 'startup') { setTab(tabFromPath(location.pathname)); setPage('tabs') }; setStep('done') }
  const openAccount = () => navigate(currentUser ? '/perfil' : '/acceso')
  const openLanguageSettings = () => { setOrigin('language-settings'); setStep('language') }
  const openRegionSettings = (from: 'menu' | 'location') => { setOrigin(from === 'menu' ? 'region-settings' : 'region-location'); setStep('country') }
  const handleLanguageContinue = () => { if (origin === 'language-settings') { setStep('done'); setPage('tabs'); setTab('menu') } else setStep('country') }
  const handleCountryContinue = () => { if (origin === 'region-location') { setStep('done'); navigate('/?panel=ubicacion'); return }; if (origin === 'region-settings') { setStep('done'); navigate('/menu'); return }; setStep('privacy') }
  const authBack = () => { if (origin === 'startup') setStep('privacy'); else returnToApp() }
  const openMap = (mode: MapMode, query = '') => {
    const params = new URLSearchParams()
    params.set('q', query || 'Tenerife')
    params.set('vista', 'mapa')
    if (mode === 'draw') params.set('dibujar', '1')
    navigate(`/buscar?${params.toString()}`)
  }
  const openResults = (mode: SearchMode) => navigate(`/buscar?q=Tenerife&alquiler=${mode === 'turismo' ? 'holiday' : 'long'}`)
  const openPublication = () => navigate(`${location.pathname}?gate=publicar`)
  if (!shellActive) return null
  if (step !== 'done') return <div className="m2-app notranslate" translate="no"><Onboarding step={step} origin={origin} language={language} setLanguage={setLanguage} onStep={setStep} onCountryContinue={handleCountryContinue} onLanguageContinue={handleLanguageContinue} onAuthBack={authBack} onDone={finishAuth} /></div>
  if (page === 'location') return <div className="m2-app notranslate" translate="no"><LocationScreen t={t} onBack={() => navigate('/')} onChangeRegion={() => openRegionSettings('location')} onMap={openMap} /></div>
  if (page === 'phone') return <div className="m2-app notranslate" translate="no"><PhoneSearchScreen t={t} listings={allListings} onBack={() => navigate('/?panel=ubicacion')} onFound={(listingId) => navigate(`/habitacion/${listingId}`)} /></div>
  if (page === 'map') return <div className="m2-app notranslate" translate="no"><MapScreen mode={mapMode} language={language} t={t} query={mapQuery} initialCenter={mapCenter} polygon={mapPolygon} onPolygonChange={setMapPolygon} onBack={() => navigate('/?panel=ubicacion')} onSave={() => { setQuery(mapQuery || 'Tenerife'); saveCurrentSearch() }} onList={() => navigate('/buscar?q=Tenerife')} onFilters={() => navigate('/buscar?q=Tenerife&panel=filtros')} /></div>
  return <div className="m2-app notranslate" translate="no"><main className="m2-main">{tab === 'home' ? <HomeScreen t={t} onLocation={() => navigate('/?panel=ubicacion')} onSearch={openResults} onPublish={openPublication} /> : null}{tab === 'searches' ? <EmptyScreen kind="searches" onLogin={openAccount} onExplore={() => navigate('/buscar?q=Tenerife')} authenticated={Boolean(currentUser)} t={t} items={savedSearchItems} /> : null}{tab === 'favorites' ? <EmptyScreen kind="favorites" onLogin={openAccount} onExplore={() => navigate('/buscar?q=Tenerife')} authenticated={Boolean(currentUser)} t={t} items={favoriteItems} /> : null}{tab === 'messages' ? <EmptyScreen kind="messages" onLogin={openAccount} onExplore={() => navigate('/buscar?q=Tenerife')} authenticated={Boolean(currentUser)} t={t} items={messageItems} /> : null}{tab === 'menu' ? <MenuScreen onLogin={openAccount} onLanguage={openLanguageSettings} onRegion={() => openRegionSettings('menu')} onAgencies={() => navigate('/contacto')} onPublish={openPublication} language={language} t={t} currentUserName={currentUser?.name} /> : null}</main><nav className="m2-bottom-nav" aria-label={t.mainNavigation}>{navItems.map(({ tab: itemTab, label, icon: Icon }) => <button key={itemTab} type="button" className={cn(tab === itemTab && 'is-active')} aria-current={tab === itemTab ? 'page' : undefined} onClick={() => navigate(tabRoutes[itemTab])}><Icon /><span>{label}</span></button>)}</nav></div>
}
