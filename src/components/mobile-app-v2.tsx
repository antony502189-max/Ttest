import { useEffect, useMemo, useRef, useState, type MutableRefObject, type ReactNode } from 'react'
import { useLocation, useNavigate } from 'react-router'
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
import { requestCurrentLocation, type GeolocationFailure } from '@/lib/geolocation'
import { googleMapsConfig, loadGoogleMaps } from '@/lib/google-maps/loader'
import { persistListingAccessProfile, readListingAccessProfile, type HomeOccupantChoice } from '@/lib/listing-access'
import { selectMobileSearchListings } from '@/lib/mobile-search'
import { filtersToParams } from '@/lib/search'
import { filtersForRentalMode } from '@/lib/price-filter-controls'
import type { Listing } from '@/types'
import '@/mobile-app-v2.css'
import '@/mobile-favorites-selection.css'

type OnboardingStep = 'language' | 'country' | 'privacy' | 'auth' | 'done'
type OnboardingOrigin = 'startup' | 'language-settings' | 'region-settings' | 'region-location' | 'account'
type MobileTab = 'home' | 'searches' | 'favorites' | 'menu'
type AppLanguage = Language
type SearchMode = 'vivienda' | 'turismo' | null
type AppPage = 'tabs' | 'location' | 'map'
type MapMode = 'draw' | 'search'
type OccupantOption = 'anyone' | 'man' | 'woman' | 'person' | 'couple' | 'unrestricted'
type MapStatus = 'loading' | 'ready' | 'error'
type LocationStatus = 'idle' | 'loading' | 'success' | GeolocationFailure | 'empty'
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
    login: 'Iniciar sesión', menu: 'Menú', loginDescription: 'Sincroniza tus favoritos y búsquedas en el ordenador, la tableta y el teléfono móvil.',
    yourProperties: 'Tus propiedades', findAgencies: 'Buscar agencias para vender', publishYourAd: 'Publica tu anuncio', settings: 'Ajustes', searchRegion: 'Región de búsqueda',
    language: 'Idioma', appearance: 'Apariencia', appearanceDefault: 'Predeterminada (clara)', about: 'Acerca de la aplicación', version: 'Versión 14.5.0',
    home: 'Inicio', searches: 'Búsquedas', favorites: 'Favoritos', mainNavigation: 'Navegación principal', heroAlt: 'Interior de una vivienda',
    locationTitle: '¿Dónde buscas?', regionSearch: 'Búsqueda en Tenerife', change: 'Cambiar', locationPlaceholder: 'Municipio, zona o dirección', alsoYouCan: 'También puedes',
    drawZone: 'Dibujar tu zona', redrawZone: 'Volver a dibujar', cancelDrawing: 'Cancelar dibujo', clearZone: 'Eliminar zona', drawInstruction: 'Mantén pulsado y dibuja el contorno',
    drawingInstruction: 'Rodea la zona y suelta el dedo', drawTooShort: 'Dibuja una zona más grande con un solo movimiento', areaReady: 'Zona seleccionada',
    searchOnMap: 'Buscar en el mapa', searchNearby: 'Buscar alrededor de ti', searchByPhone: 'Buscar por teléfono', mapDrawTitle: 'Tu propia zona', visibleArea: 'Zona visible', filters: 'Filtros', list: 'Listado',
    phoneIntro: '¿Has visto un cartel de "se vende" o "se alquila"? Introduce los datos para buscarlo', phone: 'Teléfono', operation: 'Operación',
    buy: 'Comprar', rent: 'Alquilar', type: 'Tipo', homes: 'Viviendas', invalidPhone: 'Introduce un teléfono válido', phoneNotFound: 'No hemos encontrado ningún anuncio con ese teléfono.',
    searchArea: 'Buscar en esta zona', save: 'Guardar', saved: 'Guardado', layers: 'Cambiar capas', locate: 'Mi ubicación', mapLoading: 'Cargando mapa…', mapError: 'No se pudo cargar Google Maps',
    locating: 'Buscando tu ubicación…', locationFound: 'Ubicación encontrada', locationDenied: 'No has permitido acceder a tu ubicación', locationUnavailable: 'Tu ubicación no está disponible',
    locationTimeout: 'La búsqueda de ubicación ha tardado demasiado', locationUnsupported: 'Este navegador no ofrece geolocalización', locationOutside: 'Tu ubicación está fuera de Tenerife',
    nearbyEmpty: 'No hay anuncios cerca de esta ubicación', back: 'Volver', close: 'Cerrar', clear: 'Borrar búsqueda',
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
    login: 'Sign in', menu: 'Menu', loginDescription: 'Sync your favorites and searches across your computer, tablet, and mobile phone.', yourProperties: 'Your properties',
    findAgencies: 'Find agencies to sell', publishYourAd: 'Publish your ad', settings: 'Settings', searchRegion: 'Search region', language: 'Language', appearance: 'Appearance',
    appearanceDefault: 'Default (light)', about: 'About the app', version: 'Version 14.5.0', home: 'Home', searches: 'Searches', favorites: 'Favorites',
    mainNavigation: 'Main navigation', heroAlt: 'Home interior', locationTitle: 'Where are you looking?', regionSearch: 'Searching in Tenerife', change: 'Change',
    locationPlaceholder: 'Town, area or address', alsoYouCan: 'You can also', drawZone: 'Draw your own area', redrawZone: 'Draw again', cancelDrawing: 'Cancel drawing',
    clearZone: 'Delete area', drawInstruction: 'Press and draw the area outline', drawingInstruction: 'Draw around the area and release',
    drawTooShort: 'Draw a larger area in one continuous movement', areaReady: 'Area selected', searchOnMap: 'Search on the map', searchNearby: 'Search around you', searchByPhone: 'Search by phone', mapDrawTitle: 'Your own area',
    phoneIntro: 'Have you seen a "for sale" or "for rent" sign? Enter the details to find it', phone: 'Phone', operation: 'Operation',
    buy: 'Buy', rent: 'Rent', type: 'Type', homes: 'Homes', invalidPhone: 'Enter a valid phone number', phoneNotFound: 'We could not find a listing with that phone number.',
    visibleArea: 'Visible area', filters: 'Filters', list: 'List', save: 'Save', saved: 'Saved', layers: 'Change map layers', locate: 'My location', mapLoading: 'Loading map…',
    mapError: 'Google Maps could not be loaded', searchArea: 'Search this area', locating: 'Finding your location…', locationFound: 'Location found', locationDenied: 'Location permission was denied',
    locationUnavailable: 'Your location is unavailable', locationTimeout: 'Finding your location took too long', locationUnsupported: 'This browser does not provide geolocation',
    locationOutside: 'Your location is outside Tenerife', nearbyEmpty: 'There are no listings near this location', back: 'Back', close: 'Close', clear: 'Clear search',
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
    login: 'Войти в аккаунт', menu: 'Меню', loginDescription: 'Синхронизируйте избранное и поиски на компьютере, планшете и мобильном телефоне.',
    yourProperties: 'Ваши объекты', findAgencies: 'Искать агентства для продажи', publishYourAd: 'Опубликовать своё объявление', settings: 'Настройки', searchRegion: 'Регион поиска',
    language: 'Язык', appearance: 'Внешний вид', appearanceDefault: 'По умолчанию (светлый)', about: 'О приложении', version: 'Версия 14.5.0', home: 'Главная',
    searches: 'Поиски', favorites: 'Избранное', mainNavigation: 'Основная навигация', heroAlt: 'Интерьер жилого помещения', locationTitle: 'Где вы ищете?',
    regionSearch: 'Поиск на Тенерифе', change: 'Изменить', locationPlaceholder: 'Город, район или адрес', alsoYouCan: 'Также вы можете', drawZone: 'Нарисовать свою зону',
    redrawZone: 'Нарисовать заново', cancelDrawing: 'Отменить рисование', clearZone: 'Удалить зону', drawInstruction: 'Зажмите и нарисуйте контур зоны',
    drawingInstruction: 'Обведите нужную территорию и отпустите', drawTooShort: 'Нарисуйте область побольше одним непрерывным движением', areaReady: 'Зона выбрана',
    searchOnMap: 'Искать на карте', searchNearby: 'Искать рядом с вами', searchByPhone: 'Искать по телефону', mapDrawTitle: 'Ваша собственная зона', visibleArea: 'Видимая зона', filters: 'Фильтры', list: 'Перечень', save: 'Сохранить',
    phoneIntro: 'Вы видели объявление «продаётся» или «сдаётся»? Введите данные, чтобы найти его', phone: 'Телефон', operation: 'Операция',
    buy: 'Купить', rent: 'Снять', type: 'Тип', homes: 'Жильё', invalidPhone: 'Введите корректный номер телефона', phoneNotFound: 'Объявление с таким номером телефона не найдено.',
    saved: 'Сохранено', layers: 'Сменить слой карты', locate: 'Моё местоположение', mapLoading: 'Загрузка карты…', mapError: 'Не удалось загрузить Google Maps',
    searchArea: 'Искать в этой области', locating: 'Определяем местоположение…', locationFound: 'Местоположение найдено', locationDenied: 'Доступ к местоположению отклонён',
    locationUnavailable: 'Местоположение недоступно', locationTimeout: 'Определение местоположения заняло слишком много времени', locationUnsupported: 'Этот браузер не поддерживает геолокацию',
    locationOutside: 'Вы находитесь за пределами Тенерифе', nearbyEmpty: 'Рядом с этим местом объявлений нет', back: 'Назад', close: 'Закрыть', clear: 'Очистить поиск',
  },
} as const

type MobileCopy = Record<keyof typeof copy.es, string>

const favoriteActionCopy: Record<AppLanguage, {
  startDelete: string
  cancel: string
  selectAll: string
  clearSelection: string
  selected: (count: number) => string
  removeSelected: (count: number) => string
  selectListing: (title: string) => string
  deselectListing: (title: string) => string
}> = {
  es: {
    startDelete: 'Seleccionar favoritos para eliminar',
    cancel: 'Cancelar',
    selectAll: 'Seleccionar todo',
    clearSelection: 'Quitar selección',
    selected: (count) => `${count} ${count === 1 ? 'seleccionado' : 'seleccionados'}`,
    removeSelected: (count) => `Eliminar seleccionados (${count})`,
    selectListing: (title) => `Seleccionar ${title} para eliminar`,
    deselectListing: (title) => `Quitar ${title} de la selección`,
  },
  en: {
    startDelete: 'Select favorites to remove',
    cancel: 'Cancel',
    selectAll: 'Select all',
    clearSelection: 'Clear selection',
    selected: (count) => `${count} selected`,
    removeSelected: (count) => `Remove selected (${count})`,
    selectListing: (title) => `Select ${title} for removal`,
    deselectListing: (title) => `Deselect ${title}`,
  },
  ru: {
    startDelete: 'Выбрать избранное для удаления',
    cancel: 'Отмена',
    selectAll: 'Выбрать всё',
    clearSelection: 'Снять выделение',
    selected: (count) => `Выбрано: ${count}`,
    removeSelected: (count) => `Удалить выбранные (${count})`,
    selectListing: (title) => `Выбрать «${title}» для удаления`,
    deselectListing: (title) => `Снять выбор с «${title}»`,
  },
}

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
  return <div className="m2-auth-panel"><Brand /><span>España (Tenerife)</span><h1>{t.authTitle}</h1><button type="button" onClick={onContinue}><b>G</b>{t.googleContinue}</button><button type="button" onClick={onContinue}><Mail />{t.emailLogin}</button><p>{t.legalIntro}</p><a href="#/privacidad">{t.privacyPolicy}</a><a href="#/terminos">{t.terms}</a></div>
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
    {step === 'privacy' ? <><div className="m2-onboarding__content m2-privacy"><h1>{t.privacyTitle}</h1><p>{t.privacyText}</p><a className="m2-privacy__policy" href="#/privacidad">{t.privacyPolicy}</a></div><PrimaryButton onClick={() => onStep('auth')}>{t.continue}</PrimaryButton></> : null}
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

function HomeScreen({ t, mode, onMode, onLocation, onSearch, onPublish }: { t: MobileCopy; mode: SearchMode; onMode: (mode: Exclude<SearchMode, null>) => void; onLocation: () => void; onSearch: () => void; onPublish: () => void }) {
  return <section className="m2-screen m2-home"><header className="m2-topbar"><Brand compact /></header><div className="m2-hero" role="img" aria-label={t.heroAlt} /><div className="m2-search-card"><div className="m2-mode-switch" role="group" aria-label={`${t.housingMode} / ${t.tourismMode}`}><button type="button" className={cn(mode === 'vivienda' && 'is-active')} onClick={() => onMode('vivienda')} aria-label={t.housingMode} aria-pressed={mode === 'vivienda'}><span className="m2-mode-icon m2-mode-icon--home"><Home /></span><span>{t.housingMode}</span></button><button type="button" className={cn(mode === 'turismo' && 'is-active')} onClick={() => onMode('turismo')} aria-label={t.tourismMode} aria-pressed={mode === 'turismo'}><span className="m2-mode-icon m2-mode-icon--tourism"><BriefcaseBusiness /></span><span>{t.tourismMode}</span></button></div><OccupantSelector t={t} /><button type="button" className="m2-select-row" onClick={onLocation}><span>{t.searchTenerife}</span><MapPin /></button><PrimaryButton onClick={onSearch} testId="open-location"><Search />{t.search}</PrimaryButton><button type="button" className="m2-outline" onClick={onPublish}>{t.publishAd}</button></div></section>
}

function locationStatusMessage(t: MobileCopy, status: LocationStatus) {
  if (status === 'loading') return t.locating
  if (status === 'success') return t.locationFound
  if (status === 'denied') return t.locationDenied
  if (status === 'unavailable') return t.locationUnavailable
  if (status === 'timeout') return t.locationTimeout
  if (status === 'unsupported') return t.locationUnsupported
  if (status === 'outside') return t.locationOutside
  if (status === 'empty') return t.nearbyEmpty
  return ''
}

function LocationScreen({ t, onBack, onChangeRegion, onMap, onNearby, nearbyStatus }: {
  t: MobileCopy
  onBack: () => void
  onChangeRegion: () => void
  onMap: (mode: MapMode, query?: string) => void
  onNearby: () => void
  nearbyStatus: LocationStatus
}) {
  const [query, setQuery] = useState('')
  const submit = (event: React.FormEvent) => { event.preventDefault(); onMap('search', query.trim()) }
  const statusMessage = locationStatusMessage(t, nearbyStatus)
  return <section className="m2-screen m2-location" data-testid="location-screen"><BackHeader title={t.locationTitle} onBack={onBack} backLabel={t.back} /><div className="m2-location__body"><div className="m2-location-region"><strong>{t.regionSearch}</strong><button type="button" onClick={onChangeRegion}>{t.change}</button></div><form className="m2-location-search" onSubmit={submit}><Search /><input value={query} onChange={(event) => setQuery(event.target.value)} type="search" placeholder={t.locationPlaceholder} aria-label={t.locationPlaceholder} />{query ? <button type="button" className="m2-location-clear" onClick={() => setQuery('')} aria-label={t.clear}><X /></button> : null}</form><h2>{t.alsoYouCan}</h2><button type="button" className="m2-location-action" onClick={() => onMap('draw')} data-testid="draw-zone"><span><PenTool /></span><strong>{t.drawZone}</strong><ChevronRight /></button><button type="button" className="m2-location-action" onClick={() => onMap('search')} data-testid="search-map"><span><Map /></span><strong>{t.searchOnMap}</strong><ChevronRight /></button><button type="button" className="m2-location-action" onClick={onNearby} disabled={nearbyStatus === 'loading'} data-testid="search-nearby"><span><Crosshair /></span><strong>{t.searchNearby}</strong><ChevronRight /></button>{statusMessage ? <p className={cn('m2-location-feedback', !['loading', 'success'].includes(nearbyStatus) && 'is-error')} role={nearbyStatus === 'loading' ? 'status' : 'alert'}>{statusMessage}</p> : null}</div></section>
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
        const { maps } = await loadGoogleMaps()
        const GoogleMap = maps.Map
        if (cancelled || !containerRef.current) return
        const mapId = googleMapsConfig.mapId
        const hasInitialCenter = initialLat !== undefined && initialLng !== undefined
        const map = new GoogleMap(containerRef.current, { center: hasInitialCenter ? { lat: initialLat, lng: initialLng } : TENERIFE_CENTER, zoom: hasInitialCenter ? 14 : query ? 12 : 10, mapId: mapId || undefined, styles: mapId ? undefined : darkMapStyles, disableDefaultUI: true, gestureHandling: 'greedy', clickableIcons: false, backgroundColor: '#142536', minZoom: 8, maxZoom: 19, restriction: { latLngBounds: { north: 29.2, south: 27.1, east: -15.3, west: -18.2 }, strictBounds: false } })
        mapRef.current = map
        google.maps.event.addListenerOnce(map, 'tilesloaded', () => { if (!cancelled) { setStatus('ready'); onStatus('ready') } })
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

function MapScreen({ mode, language, t, query, initialCenter, polygon, items, onPolygonChange, onBack, onSave, onList, onFilters, onSearchArea }: {
  mode: MapMode; language: AppLanguage; t: MobileCopy; query: string; initialCenter?: MapPoint; polygon: MapPoint[]; items: Listing[]; onPolygonChange: (polygon: MapPoint[]) => void; onBack: () => void; onSave?: () => void; onList?: () => void; onFilters?: () => void; onSearchArea?: () => void
}) {
  const mapRef = useRef<google.maps.Map | null>(null)
  const userMarkerRef = useRef<google.maps.marker.AdvancedMarkerElement | null>(null)
  const [mapType, setMapType] = useState<'roadmap' | 'hybrid'>('roadmap')
  const [saved, setSaved] = useState(false)
  const [mapStatus, setMapStatus] = useState<MapStatus>('loading')
  const [locationStatus, setLocationStatus] = useState<LocationStatus>('idle')
  const [drawing, setDrawing] = useState(false)
  const toggleLayers = () => { const next = mapType === 'roadmap' ? 'hybrid' : 'roadmap'; setMapType(next); mapRef.current?.setMapTypeId(next) }
  const showUserMarker = async (coordinates: MapPoint) => {
    await loadGoogleMaps()
    if (!mapRef.current) return
    if (!userMarkerRef.current) {
      const content = document.createElement('span')
      content.className = 'm2-user-location-marker'
      content.setAttribute('aria-label', t.locationFound)
      userMarkerRef.current = new google.maps.marker.AdvancedMarkerElement({ map: mapRef.current, position: coordinates, content, title: t.locationFound, zIndex: 5000 })
    } else {
      userMarkerRef.current.map = mapRef.current
      userMarkerRef.current.position = coordinates
    }
  }
  const locate = async () => {
    setLocationStatus('loading')
    const result = await requestCurrentLocation()
    if (!result.ok) { setLocationStatus(result.reason); return }
    mapRef.current?.panTo(result.coordinates)
    mapRef.current?.setZoom(14)
    await showUserMarker(result.coordinates)
    setLocationStatus('success')
  }
  useEffect(() => {
    if (mapStatus !== 'ready' || !initialCenter) return
    void showUserMarker(initialCenter)
    return () => { if (userMarkerRef.current) userMarkerRef.current.map = null }
    // Marker creation is tied to the resolved initial coordinates and map readiness.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialCenter?.lat, initialCenter?.lng, mapStatus])
  const locationMessage = locationStatusMessage(t, locationStatus)
  const mainDrawLabel = drawing ? t.cancelDrawing : polygon.length >= 3 ? t.redrawZone : t.drawZone
  const toggleDrawing = () => setDrawing((current) => !current)
  return <section className={cn('m2-map-screen', drawing && 'is-freehand-drawing', polygon.length >= 3 && 'has-drawn-zone')} data-testid={mapStatus === 'ready' ? `map-${mode}` : undefined}>
    {mode === 'draw' ? <BackHeader title={t.mapDrawTitle} onBack={onBack} backLabel={t.back} /> : <><header className="m2-map-results-header"><button type="button" className="m2-icon-button" onClick={onBack} aria-label={t.back}><ChevronLeft /></button><div><strong>Tenerife</strong><small>{query || t.visibleArea}</small></div><button type="button" className={cn('m2-save', saved && 'is-saved')} onClick={() => { if (!saved) onSave?.(); setSaved((value) => !value) }} aria-pressed={saved}>{saved ? <Check /> : <Bell />}{saved ? t.saved : t.save}</button></header><div className="m2-map-toolbar"><button type="button" onClick={onFilters}><SlidersHorizontal />{t.filters}</button><button type="button" onClick={onList}><Menu />{t.list}</button></div></>}
    <GoogleMapCanvas language={language} t={t} mapRef={mapRef} query={query} initialCenter={initialCenter} onStatus={setMapStatus} />
    <MobileMapListingsLayer mapRef={mapRef} mapReady={mapStatus === 'ready'} language={language} drawing={drawing} items={items} />
    <FreehandAreaLayer mapRef={mapRef} mapReady={mapStatus === 'ready'} active={drawing} setActive={setDrawing} polygon={polygon} onPolygonChange={onPolygonChange} t={t} />
    <div className="m2-map-controls"><button type="button" onClick={toggleLayers} aria-label={t.layers} aria-pressed={mapType === 'hybrid'} disabled={mapStatus !== 'ready' || drawing}><Layers3 /></button><button type="button" onClick={locate} aria-label={t.locate} disabled={mapStatus !== 'ready' || locationStatus === 'loading' || drawing}><Crosshair /></button></div>
    {locationMessage ? <div className={cn('m2-location-toast', !['loading', 'success'].includes(locationStatus) && 'is-error')} role="status">{locationMessage}</div> : null}
    {polygon.length >= 3 && !drawing ? <button type="button" className="m2-search-area" data-testid="search-this-area" onClick={onSearchArea}><Search />{t.searchArea}</button> : null}
    <div className="m2-draw-actions">{polygon.length >= 3 && !drawing ? <button type="button" className="m2-clear-zone" onClick={() => onPolygonChange([])} aria-label={t.clearZone}><Trash2 /></button> : null}<button type="button" className="m2-draw-cta" onClick={toggleDrawing} disabled={mapStatus !== 'ready'} aria-pressed={drawing}><PenTool />{mainDrawLabel}</button></div>
  </section>
}

type MobileCollectionItem = { id: string; title: string; meta: string; onOpen: () => void }

function EmptyScreen({ kind, onLogin, onExplore, authenticated, t, items = [] }: { kind: 'searches' | 'favorites'; onLogin: () => void; onExplore: () => void; authenticated: boolean; t: MobileCopy; items?: MobileCollectionItem[] }) {
  const data = { searches: { title: t.searchesTitle, heading: t.searchesHeading, text: t.searchesText, icon: <Bell /> }, favorites: { title: t.favoritesTitle, heading: t.favoritesHeading, text: t.favoritesText, icon: <Heart /> } }[kind]
  if (items.length) return <section className="m2-screen m2-empty m2-collection"><header>{data.title}</header><div className="m2-collection__list">{items.map((item) => <button type="button" key={item.id} onClick={item.onOpen}><span><strong>{item.title}</strong><small>{item.meta}</small></span><ChevronRight /></button>)}</div></section>
  const heading = authenticated && kind === 'searches' ? t.searchesEmpty : data.heading
  const text = authenticated && kind === 'searches' ? t.searchesEmptyText : data.text
  return <section className="m2-screen m2-empty"><header>{data.title}</header><div className="m2-empty__icon">{data.icon}</div><h1>{heading}</h1><p>{text}</p><PrimaryButton onClick={authenticated ? onExplore : onLogin}>{authenticated ? t.search : t.login}</PrimaryButton></section>
}

function FavoritesCollectionScreen({ items, onRemove, onLogin, onExplore, authenticated, language, t }: {
  items: MobileCollectionItem[]
  onRemove: (id: string) => void
  onLogin: () => void
  onExplore: () => void
  authenticated: boolean
  language: AppLanguage
  t: MobileCopy
}) {
  const actionCopy = favoriteActionCopy[language]
  const [selecting, setSelecting] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(() => new Set())

  useEffect(() => {
    const available = new Set(items.map((item) => item.id))
    setSelected((current) => new Set([...current].filter((id) => available.has(id))))
    if (!items.length) setSelecting(false)
  }, [items])

  if (!items.length) return <EmptyScreen kind="favorites" onLogin={onLogin} onExplore={onExplore} authenticated={authenticated} t={t} />

  const allSelected = selected.size === items.length
  const stopSelecting = () => { setSelecting(false); setSelected(new Set()) }
  const toggleSelected = (id: string) => setSelected((current) => {
    const next = new Set(current)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    return next
  })
  const toggleAll = () => setSelected(allSelected ? new Set() : new Set(items.map((item) => item.id)))
  const removeSelected = () => {
    const ids = [...selected]
    if (!ids.length) return
    ids.forEach(onRemove)
    stopSelecting()
  }

  return <section className="m2-screen m2-empty m2-collection">
    <header className="m2-collection__header">
      <span>{t.favoritesTitle}</span>
      <button
        type="button"
        className="m2-favorites-trash"
        aria-label={selecting ? actionCopy.cancel : actionCopy.startDelete}
        aria-pressed={selecting}
        onClick={() => { if (selecting) stopSelecting(); else setSelecting(true) }}
      >{selecting ? <X /> : <Trash2 />}</button>
    </header>
    {selecting ? <div className="m2-favorites-selection-bar" role="toolbar" aria-label={actionCopy.startDelete}>
      <strong aria-live="polite">{actionCopy.selected(selected.size)}</strong>
      <div className="m2-favorites-selection-actions">
        <button type="button" onClick={toggleAll}>{allSelected ? actionCopy.clearSelection : actionCopy.selectAll}</button>
        <button type="button" onClick={stopSelecting}>{actionCopy.cancel}</button>
        <button type="button" className="m2-favorites-remove-selected" disabled={!selected.size} onClick={removeSelected}><Trash2 />{actionCopy.removeSelected(selected.size)}</button>
      </div>
    </div> : null}
    <div className="m2-collection__list">
      {items.map((item) => {
        const isSelected = selected.has(item.id)
        return <button
          type="button"
          key={item.id}
          className={cn(selecting && 'm2-favorite-item--selecting', isSelected && 'm2-favorite-item--selected')}
          aria-pressed={selecting ? isSelected : undefined}
          aria-label={selecting ? (isSelected ? actionCopy.deselectListing(item.title) : actionCopy.selectListing(item.title)) : undefined}
          onClick={selecting ? () => toggleSelected(item.id) : item.onOpen}
        >
          <span><strong>{item.title}</strong><small>{item.meta}</small></span>
          {selecting ? <span className="m2-favorites-select-indicator" aria-hidden="true">{isSelected ? <Check /> : null}</span> : <ChevronRight />}
        </button>
      })}
    </div>
  </section>
}

function MenuScreen({ onLogin, onLanguage, onRegion, onAgencies, onPublish, language, t, currentUserName }: { onLogin: () => void; onLanguage: () => void; onRegion: () => void; onAgencies: () => void; onPublish: () => void; language: AppLanguage; t: MobileCopy; currentUserName?: string }) {
  const languageLabel = languages.find((item) => item.value === language)?.label ?? 'Español'
  return <section className="m2-screen m2-menu"><header>{t.menu}</header><div className="m2-menu-login"><UserRound /><div><h2>{currentUserName ?? t.login}</h2><p>{t.loginDescription}</p></div></div><PrimaryButton onClick={onLogin}>{currentUserName ? t.yourProperties : t.login}</PrimaryButton><h3>{t.yourProperties}</h3><button type="button" className="m2-menu-row" onClick={onAgencies}><span><Search />{t.findAgencies}</span><ChevronRight /></button><button type="button" className="m2-menu-row" onClick={onPublish}><span><Plus />{t.publishYourAd}</span><ChevronRight /></button><h3>{t.settings}</h3><button type="button" className="m2-menu-row" onClick={onRegion}><span>{t.searchRegion}</span><b>España (Tenerife)</b></button><button type="button" className="m2-menu-row" onClick={onLanguage}><span>{t.language}</span><b>{languageLabel}</b></button><button type="button" className="m2-menu-row"><span>{t.appearance}</span><b>{t.appearanceDefault}</b></button><button type="button" className="m2-menu-row"><span>{t.about}</span><b>{t.version}</b></button></section>
}

function getNavItems(t: MobileCopy): Array<{ tab: MobileTab; label: string; icon: typeof Home }> {
  return [{ tab: 'home', label: t.home, icon: Home }, { tab: 'searches', label: t.searches, icon: Bell }, { tab: 'favorites', label: t.favorites, icon: Heart }, { tab: 'menu', label: t.menu, icon: Menu }]
}

const tabRoutes: Record<MobileTab, string> = {
  home: '/',
  searches: '/busquedas-guardadas',
  favorites: '/favoritos',
  menu: '/menu',
}

function tabFromPath(pathname: string): MobileTab {
  if (pathname === '/busquedas-guardadas') return 'searches'
  if (pathname === '/favoritos') return 'favorites'
  if (pathname === '/menu') return 'menu'
  return 'home'
}

export function MobileAppV2() {
  const location = useLocation()
  const navigate = useNavigate()
  const { language, setLanguage } = useI18n()
  const { allListings, discarded, favorites, toggleFavorite, savedSearches, mapPolygon, setMapPolygon, saveCurrentSearch, restoreSavedSearch, query, setQuery, rentalMode, filters, setFilters, currentUser } = useApp()
  const [step, setStep] = useState<OnboardingStep>(() => {
    const navigation = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined
    try {
      const stored = localStorage.getItem(ONBOARDING_KEY)
      if (stored === 'done:refreshable' && navigation?.type === 'reload') return 'language'
      return stored === 'done' || stored === 'done:refreshable' ? 'done' : 'language'
    } catch { return 'language' }
  })
  const [origin, setOrigin] = useState<OnboardingOrigin>('startup')
  const [page, setPage] = useState<AppPage>('tabs')
  const [mapMode, setMapMode] = useState<MapMode>('search')
  const [mapQuery, setMapQuery] = useState('')
  const [mapCenter, setMapCenter] = useState<MapPoint | undefined>()
  const [nearbyStatus, setNearbyStatus] = useState<LocationStatus>('idle')
  const [tab, setTab] = useState<MobileTab>(() => tabFromPath(location.pathname))
  const [homeMode, setHomeMode] = useState<SearchMode>(null)
  const [mobileViewport, setMobileViewport] = useState(() => window.matchMedia('(max-width: 767px), (max-height: 480px) and (max-width: 900px)').matches)
  const shellActive = mobileViewport && ['/', '/buscar', '/favoritos', '/busquedas-guardadas', '/menu'].includes(location.pathname)
  const t: MobileCopy = copy[language]
  const navItems = getNavItems(t)
  const mapItems = useMemo(() => selectMobileSearchListings({
    listings: allListings,
    discarded,
    rentalMode,
    filters,
    polygon: mapPolygon,
    query: mapQuery || query,
    params: new URLSearchParams(location.search),
  }), [allListings, discarded, filters, location.search, mapPolygon, mapQuery, query, rentalMode])
  const favoriteItems = useMemo<MobileCollectionItem[]>(() => allListings.filter((listing) => favorites.has(listing.id)).map((listing) => ({ id: listing.id, title: listing.title, meta: `${listing.area}, ${listing.city} · ${listing.price} €`, onOpen: () => navigate(`/habitacion/${listing.id}`) })), [allListings, favorites, navigate])
  const savedSearchItems = useMemo<MobileCollectionItem[]>(() => savedSearches.map((search) => ({ id: search.id, title: search.query, meta: search.rentalMode === 'holiday' ? t.tourismMode : t.housingMode, onOpen: () => { restoreSavedSearch(search.id); navigate(`/buscar?q=${encodeURIComponent(search.query)}&alquiler=${search.rentalMode}`) } })), [navigate, restoreSavedSearch, savedSearches, t.housingMode, t.tourismMode])
  useEffect(() => {
    document.documentElement.classList.toggle('mobile-v2-active', shellActive)
    return () => document.documentElement.classList.remove('mobile-v2-active')
  }, [shellActive])
  useEffect(() => {
    const media = window.matchMedia('(max-width: 767px), (max-height: 480px) and (max-width: 900px)')
    const update = () => setMobileViewport(media.matches)
    media.addEventListener('change', update)
    return () => media.removeEventListener('change', update)
  }, [])
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
    setPage('tabs')
    setTab(tabFromPath(location.pathname))
  }, [location.pathname, location.search, step])
  useEffect(() => {
    if (!shellActive || location.pathname !== '/buscar') return
    const polygonParam = new URLSearchParams(location.search).get('poligono')
    const routePolygon = polygonParam
      ? polygonParam.split(';').map((pair) => pair.split(',').map(Number)).filter((pair) => pair.length === 2 && pair.every(Number.isFinite)).map(([lat, lng]) => ({ lat, lng }))
      : []
    const nextPolygon = routePolygon.length >= 3 ? routePolygon : []
    if (JSON.stringify(nextPolygon) !== JSON.stringify(mapPolygon)) setMapPolygon(nextPolygon)
  }, [location.pathname, location.search, mapPolygon, setMapPolygon, shellActive])
  useEffect(() => {
    if (location.pathname !== '/buscar') return
    setHomeMode(rentalMode === 'holiday' ? 'turismo' : 'vivienda')
  }, [location.pathname, rentalMode])
  const persistOnboarding = () => { try { localStorage.setItem(ONBOARDING_KEY, 'done:refreshable') } catch { /* private mode */ } }
  const returnToApp = () => { persistOnboarding(); setStep('done'); setPage('tabs') }
  const finishAuth = () => { persistOnboarding(); if (origin === 'startup') { setTab(tabFromPath(location.pathname)); setPage('tabs') }; setStep('done') }
  const openAccount = () => navigate(currentUser ? '/perfil' : '/acceso')
  const openLanguageSettings = () => { setOrigin('language-settings'); setStep('language') }
  const openRegionSettings = (from: 'menu' | 'location') => { setOrigin(from === 'menu' ? 'region-settings' : 'region-location'); setStep('country') }
  const handleLanguageContinue = () => { if (origin === 'language-settings') { setStep('done'); setPage('tabs'); setTab('menu') } else setStep('country') }
  const handleCountryContinue = () => { if (origin === 'region-location') { setStep('done'); navigate('/?panel=ubicacion'); return }; if (origin === 'region-settings') { setStep('done'); navigate('/menu'); return }; setStep('privacy') }
  const authBack = () => { if (origin === 'startup') setStep('privacy'); else returnToApp() }
  const openMap = (mode: MapMode, query = '') => {
    const params = filtersToParams(filters)
    params.set('q', query || 'Tenerife')
    params.set('vista', 'mapa')
    params.set('alquiler', rentalMode)
    if (mapPolygon.length >= 3) params.set('poligono', mapPolygon.map((point) => `${point.lat.toFixed(5)},${point.lng.toFixed(5)}`).join(';'))
    if (mode === 'draw') params.set('dibujar', '1')
    navigate(`/buscar?${params.toString()}`)
  }
  const openNearby = async () => {
    setNearbyStatus('loading')
    const result = await requestCurrentLocation()
    if (!result.ok) { setNearbyStatus(result.reason); return }
    const params = filtersToParams(filters)
    params.set('q', 'Tenerife')
    params.set('vista', 'mapa')
    params.set('cerca', '1')
    params.set('radio', '30')
    params.set('lat', String(result.coordinates.lat))
    params.set('lng', String(result.coordinates.lng))
    params.set('alquiler', rentalMode)
    setNearbyStatus('success')
    navigate(`/buscar?${params.toString()}`)
  }
  const commitMobilePolygon = (polygon: MapPoint[]) => {
    setMapPolygon(polygon)
    const params = new URLSearchParams(location.search)
    if (polygon.length >= 3) params.set('poligono', polygon.map((point) => `${point.lat.toFixed(5)},${point.lng.toFixed(5)}`).join(';'))
    else params.delete('poligono')
    navigate(`${location.pathname}?${params.toString()}`, { replace: true })
  }
  const navigateFromMap = (target: 'list' | 'filters' | 'area') => {
    const params = new URLSearchParams(location.search)
    params.delete('dibujar')
    params.delete('vista')
    params.delete('pagina')
    if (target === 'filters') params.set('panel', 'filtros')
    else params.delete('panel')
    if (target === 'area' && mapPolygon.length >= 3) {
      params.set('poligono', mapPolygon.map((point) => `${point.lat.toFixed(5)},${point.lng.toFixed(5)}`).join(';'))
    }
    navigate(`/buscar?${params.toString()}`)
  }
  const searchThisMapArea = () => {
    const params = new URLSearchParams(location.search)
    params.delete('dibujar')
    params.delete('pagina')
    navigate(`/buscar?${params.toString()}`)
  }
  const runHomeSearch = () => {
    const mode = homeMode === 'turismo' ? 'holiday' : 'long'
    const nextFilters = filtersForRentalMode(filters, mode)
    if (nextFilters !== filters) setFilters(nextFilters)
    const params = filtersToParams(nextFilters)
    params.set('q', 'Tenerife')
    params.set('alquiler', mode)
    navigate(`/buscar?${params.toString()}`)
  }
  const openPublication = () => navigate(`${location.pathname}?gate=publicar`)
  if (!shellActive) return null
  if (step !== 'done') return <div className="m2-app notranslate" translate="no"><Onboarding step={step} origin={origin} language={language} setLanguage={setLanguage} onStep={setStep} onCountryContinue={handleCountryContinue} onLanguageContinue={handleLanguageContinue} onAuthBack={authBack} onDone={finishAuth} /></div>
  if (page === 'location') return <div className="m2-app notranslate" translate="no"><LocationScreen t={t} onBack={() => navigate('/')} onChangeRegion={() => openRegionSettings('location')} onMap={openMap} onNearby={() => { void openNearby() }} nearbyStatus={nearbyStatus} /></div>
  if (page === 'map') return <div className="m2-app notranslate" translate="no"><MapScreen mode={mapMode} language={language} t={t} query={mapQuery} initialCenter={mapCenter} polygon={mapPolygon} items={mapItems} onPolygonChange={commitMobilePolygon} onBack={() => navigate('/?panel=ubicacion')} onSave={() => { setQuery(mapQuery || 'Tenerife'); saveCurrentSearch() }} onList={() => navigateFromMap('list')} onFilters={() => navigateFromMap('filters')} onSearchArea={searchThisMapArea} /></div>
  return <div className="m2-app notranslate" translate="no"><main className="m2-main">{tab === 'home' ? <HomeScreen t={t} mode={homeMode} onMode={setHomeMode} onLocation={() => navigate('/?panel=ubicacion')} onSearch={runHomeSearch} onPublish={openPublication} /> : null}{tab === 'searches' ? <EmptyScreen kind="searches" onLogin={openAccount} onExplore={() => navigate('/buscar?q=Tenerife')} authenticated={Boolean(currentUser)} t={t} items={savedSearchItems} /> : null}{tab === 'favorites' ? <FavoritesCollectionScreen items={favoriteItems} onRemove={toggleFavorite} onLogin={openAccount} onExplore={() => navigate('/buscar?q=Tenerife')} authenticated={Boolean(currentUser)} language={language} t={t} /> : null}{tab === 'menu' ? <MenuScreen onLogin={openAccount} onLanguage={openLanguageSettings} onRegion={() => openRegionSettings('menu')} onAgencies={() => navigate('/contacto')} onPublish={openPublication} language={language} t={t} currentUserName={currentUser?.name} /> : null}</main><nav className="m2-bottom-nav" aria-label={t.mainNavigation}>{navItems.map(({ tab: itemTab, label, icon: Icon }) => <button key={itemTab} type="button" className={cn(tab === itemTab && 'is-active')} aria-current={tab === itemTab ? 'page' : undefined} onClick={() => navigate(tabRoutes[itemTab])}><Icon /><span>{label}</span></button>)}</nav></div>
}
