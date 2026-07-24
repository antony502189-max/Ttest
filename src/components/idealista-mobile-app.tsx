import { useEffect, useState, type ReactNode } from 'react'
import {
  Bell,
  ChevronDown,
  ChevronRight,
  Heart,
  Home,
  Mail,
  MapPin,
  Menu,
  MessageCircle,
  Plus,
  Search,
  UserRound,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import '@/idealista-mobile-app.css'

type OnboardingStep = 'language' | 'country' | 'privacy' | 'auth' | 'done'
type MobileTab = 'home' | 'searches' | 'favorites' | 'messages' | 'menu'
type AppLanguage = 'es' | 'en' | 'ru'

const LANGUAGE_KEY = '112233:idealista-mobile-language:v1'

const languages: Array<{ value: AppLanguage; label: string }> = [
  { value: 'es', label: 'Español' },
  { value: 'en', label: 'English' },
  { value: 'ru', label: 'Русский' },
]

const copy = {
  es: {
    languageTitle: 'Selecciona el idioma de la aplicación',
    continue: 'Continuar',
    regionTitle: 'Selecciona la región en la que buscas o tienes una vivienda',
    privacyTitle: 'Gracias por instalar nuestra aplicación',
    privacyText: 'A continuación, necesitamos pedirte permiso para personalizar las funciones disponibles según el uso que hagas del sitio web y de la aplicación. Si das tu consentimiento, podremos ofrecerte contenido más relevante.',
    skip: 'Ahora no',
    authTitle: 'Inicia sesión o regístrate',
    googleContinue: 'Continuar con Google',
    emailLogin: 'Iniciar sesión con email',
    legalIntro: 'Consulta la siguiente información:',
    privacyPolicy: 'Política de privacidad',
    terms: 'Términos y condiciones',
    buy: 'Comprar',
    rent: 'Alquilar',
    residential: 'Viviendas',
    searchTenerife: 'Buscar en Tenerife',
    search: 'Buscar',
    publishAd: 'Publicar anuncio',
    searchesTitle: 'Tus búsquedas',
    searchesHeading: 'Todas tus búsquedas en un solo lugar',
    searchesText: 'Guarda aquí tus búsquedas habituales para acceder a ellas más fácilmente. También te avisaremos cuando aparezcan nuevos anuncios que coincidan con tus criterios.',
    favoritesTitle: 'Favoritos y listas',
    favoritesHeading: 'No tienes viviendas en favoritos',
    favoritesText: 'Guarda los anuncios que te gusten en tu cuenta para consultarlos desde el teléfono, la tableta o el ordenador.',
    chatTitle: 'Chat',
    chatHeading: 'Inicia sesión para ver tus chats',
    chatText: 'Habla con propietarios y anunciantes y responde a los mensajes nuevos. Todas tus conversaciones estarán disponibles en 112233.es.',
    login: 'Iniciar sesión',
    menu: 'Menú',
    loginDescription: 'Sincroniza tus favoritos y búsquedas en el ordenador, la tableta y el teléfono móvil.',
    yourProperties: 'Tus propiedades',
    findAgencies: 'Buscar agencias para vender',
    publishYourAd: 'Publica tu anuncio',
    settings: 'Ajustes',
    searchRegion: 'Región de búsqueda',
    language: 'Idioma',
    appearance: 'Apariencia',
    appearanceDefault: 'Predeterminada (oscura)',
    about: 'Acerca de la aplicación',
    version: 'Versión 14.5.0',
    home: 'Inicio',
    searches: 'Búsquedas',
    favorites: 'Favoritos',
    chat: 'Chat',
    mainNavigation: 'Navegación principal',
    heroAlt: 'Interior de una vivienda',
  },
  en: {
    languageTitle: 'Select the app language',
    continue: 'Continue',
    regionTitle: 'Select the region where you are looking for or own a property',
    privacyTitle: 'Thank you for installing our app',
    privacyText: 'Next, we need to ask for your permission to personalize the available features based on how you use the website and the app. If you agree, we can show you more relevant content.',
    skip: 'Not now',
    authTitle: 'Sign in or create an account',
    googleContinue: 'Continue with Google',
    emailLogin: 'Sign in with email',
    legalIntro: 'Review the following information:',
    privacyPolicy: 'Privacy policy',
    terms: 'Terms and conditions',
    buy: 'Buy',
    rent: 'Rent',
    residential: 'Residential properties',
    searchTenerife: 'Search in Tenerife',
    search: 'Search',
    publishAd: 'Publish an ad',
    searchesTitle: 'Your searches',
    searchesHeading: 'All your searches in one place',
    searchesText: 'Save your frequent searches here for easier access. We will also notify you when new ads match your criteria.',
    favoritesTitle: 'Favorites and lists',
    favoritesHeading: 'You have no favorite properties',
    favoritesText: 'Save the ads you like to your account and view them on your phone, tablet, or computer.',
    chatTitle: 'Chat',
    chatHeading: 'Sign in to view your chats',
    chatText: 'Talk to property owners and advertisers and reply to new messages. All your conversations will be available on 112233.es.',
    login: 'Sign in',
    menu: 'Menu',
    loginDescription: 'Sync your favorites and searches across your computer, tablet, and mobile phone.',
    yourProperties: 'Your properties',
    findAgencies: 'Find agencies to sell',
    publishYourAd: 'Publish your ad',
    settings: 'Settings',
    searchRegion: 'Search region',
    language: 'Language',
    appearance: 'Appearance',
    appearanceDefault: 'Default (dark)',
    about: 'About the app',
    version: 'Version 14.5.0',
    home: 'Home',
    searches: 'Searches',
    favorites: 'Favorites',
    chat: 'Chat',
    mainNavigation: 'Main navigation',
    heroAlt: 'Home interior',
  },
  ru: {
    languageTitle: 'Выберите язык приложения',
    continue: 'Продолжить',
    regionTitle: 'Выберите регион, в котором вы ищете или имеете жильё',
    privacyTitle: 'Спасибо, что установили наше приложение',
    privacyText: 'Далее нам нужно попросить разрешение на персонализацию доступных функций в зависимости от использования сайта и приложения. Если вы согласитесь, мы сможем показывать более подходящий контент.',
    skip: 'Сейчас нет',
    authTitle: 'Войти в аккаунт или зарегистрироваться',
    googleContinue: 'Продолжить с Google',
    emailLogin: 'Войти с помощью email',
    legalIntro: 'Ознакомьтесь со следующей информацией:',
    privacyPolicy: 'Политика конфиденциальности',
    terms: 'Общие положения и условия',
    buy: 'Купить',
    rent: 'Снять',
    residential: 'Жилые объекты',
    searchTenerife: 'Искать на Тенерифе',
    search: 'Найти',
    publishAd: 'Разместить объявление',
    searchesTitle: 'Ваши поиски',
    searchesHeading: 'Все ваши поиски в одном месте',
    searchesText: 'Сохраняйте здесь частые настройки поиска для большего удобства. Также мы уведомим вас о появлении новых объявлений, совпадающих с вашими критериями.',
    favoritesTitle: 'Избранное и списки',
    favoritesHeading: 'У вас нет объектов в избранном',
    favoritesText: 'Сохраните понравившиеся объявления в аккаунте, чтобы просматривать их на телефоне, планшете или компьютере.',
    chatTitle: 'Чат',
    chatHeading: 'Войдите в аккаунт, чтобы увидеть свои чаты',
    chatText: 'Общайтесь с владельцами объектов и рекламодателями и отвечайте на новые сообщения. Все разговоры будут доступны на 112233.es.',
    login: 'Войти в аккаунт',
    menu: 'Меню',
    loginDescription: 'Синхронизируйте избранное и поиски на компьютере, планшете и мобильном телефоне.',
    yourProperties: 'Ваши объекты',
    findAgencies: 'Искать агентства для продажи',
    publishYourAd: 'Опубликовать своё объявление',
    settings: 'Настройки',
    searchRegion: 'Регион поиска',
    language: 'Язык',
    appearance: 'Внешний вид',
    appearanceDefault: 'По умолчанию (тёмный)',
    about: 'О приложении',
    version: 'Версия 14.5.0',
    home: 'Главная',
    searches: 'Поиски',
    favorites: 'Избранное',
    chat: 'Чат',
    mainNavigation: 'Основная навигация',
    heroAlt: 'Интерьер жилого помещения',
  },
} as const

type MobileCopy = Record<keyof typeof copy.es, string>

function IdealistaWordmark({ compact = false }: { compact?: boolean }) {
  return <div className={cn('im-wordmark', compact && 'im-wordmark--compact')} aria-label="www.112233.es">www.112233.es</div>
}

function PrimaryButton({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return <button type="button" className="im-primary-button" onClick={onClick}>{children}</button>
}

function AuthPanel({ onContinue, t }: { onContinue: () => void; t: MobileCopy }) {
  return <div className="im-auth-panel">
    <IdealistaWordmark />
    <span className="im-auth-kicker">España (Tenerife)</span>
    <h1>{t.authTitle}</h1>
    <button type="button" className="im-social-button" onClick={onContinue}><b>G</b> {t.googleContinue}</button>
    <button type="button" className="im-social-button" onClick={onContinue}><Mail aria-hidden="true" /> {t.emailLogin}</button>
    <p>{t.legalIntro}</p>
    <a href="#privacy">{t.privacyPolicy}</a>
    <a href="#terms">{t.terms}</a>
  </div>
}

function Onboarding({ step, setStep, language, setLanguage }: { step: OnboardingStep; setStep: (step: OnboardingStep) => void; language: AppLanguage; setLanguage: (language: AppLanguage) => void }) {
  const t: MobileCopy = copy[language]

  if (step === 'auth') return <section className="im-onboarding im-onboarding--auth"><button className="im-back" type="button" onClick={() => setStep('privacy')}>‹</button><button className="im-skip" type="button" onClick={() => setStep('done')}>{t.skip}</button><AuthPanel onContinue={() => setStep('done')} t={t} /></section>

  return <section className="im-onboarding">
    <IdealistaWordmark />
    {step === 'language' ? <>
      <div className="im-onboarding-content">
        <h1>{t.languageTitle}</h1>
        <div className="im-option-list im-option-list--scroll">{languages.map(({ value, label }) => <button key={value} type="button" className={cn('im-option-row', value === language && 'is-selected')} onClick={() => setLanguage(value)}><span lang={value}>{label}</span>{value === language ? <span className="im-check">✓</span> : null}</button>)}</div>
      </div>
      <PrimaryButton onClick={() => setStep('country')}>{t.continue}</PrimaryButton>
    </> : null}
    {step === 'country' ? <>
      <div className="im-onboarding-content">
        <h1>{t.regionTitle}</h1>
        <div className="im-country-list"><button type="button" className="im-country-row is-selected" aria-pressed="true"><span className="im-country-shape">ES</span><span>España (Tenerife)</span><span className="im-check">✓</span></button></div>
      </div>
      <PrimaryButton onClick={() => setStep('privacy')}>{t.continue}</PrimaryButton>
    </> : null}
    {step === 'privacy' ? <>
      <div className="im-onboarding-content im-privacy-copy">
        <h1>{t.privacyTitle}</h1>
        <p>{t.privacyText}</p>
      </div>
      <PrimaryButton onClick={() => setStep('auth')}>{t.continue}</PrimaryButton>
    </> : null}
  </section>
}

function HomeScreen({ t }: { t: MobileCopy }) {
  return <section className="im-screen im-home-screen">
    <header className="im-topbar"><IdealistaWordmark compact /></header>
    <div className="im-hero-photo" role="img" aria-label={t.heroAlt} />
    <div className="im-search-card">
      <div className="im-mode-switch"><button className="is-active" type="button">{t.buy}</button><button type="button">{t.rent}</button></div>
      <button type="button" className="im-select-row"><span>{t.residential}</span><ChevronDown /></button>
      <button type="button" className="im-select-row"><span>{t.searchTenerife}</span><MapPin /></button>
      <PrimaryButton><Search /> {t.search}</PrimaryButton>
      <button type="button" className="im-outline-button">{t.publishAd}</button>
    </div>
  </section>
}

function EmptyScreen({ kind, onLogin, t }: { kind: 'searches' | 'favorites' | 'messages'; onLogin: () => void; t: MobileCopy }) {
  const data = {
    searches: { title: t.searchesTitle, heading: t.searchesHeading, text: t.searchesText, icon: <Bell /> },
    favorites: { title: t.favoritesTitle, heading: t.favoritesHeading, text: t.favoritesText, icon: <Heart /> },
    messages: { title: t.chatTitle, heading: t.chatHeading, text: t.chatText, icon: <MessageCircle /> },
  }[kind]
  return <section className="im-screen im-empty-screen">
    <header className="im-section-header">{data.title}</header>
    <div className="im-empty-illustration">{data.icon}</div>
    <h1>{data.heading}</h1>
    <p>{data.text}</p>
    <PrimaryButton onClick={onLogin}>{t.login}</PrimaryButton>
  </section>
}

function MenuScreen({ onLogin, onReset, language, t }: { onLogin: () => void; onReset: () => void; language: AppLanguage; t: MobileCopy }) {
  const languageLabel = languages.find((item) => item.value === language)?.label ?? 'Español'
  return <section className="im-screen im-menu-screen">
    <header className="im-section-header">{t.menu}</header>
    <div className="im-menu-login"><UserRound /><div><h2>{t.login}</h2><p>{t.loginDescription}</p></div></div>
    <PrimaryButton onClick={onLogin}>{t.login}</PrimaryButton>
    <h3>{t.yourProperties}</h3>
    <button type="button" className="im-menu-row"><span><Search />{t.findAgencies}</span><ChevronRight /></button>
    <button type="button" className="im-menu-row"><span><Plus />{t.publishYourAd}</span><ChevronRight /></button>
    <h3>{t.settings}</h3>
    <button type="button" className="im-menu-row"><span>{t.searchRegion}</span><b>España (Tenerife)</b></button>
    <button type="button" className="im-menu-row"><span>{t.language}</span><b>{languageLabel}</b></button>
    <button type="button" className="im-menu-row"><span>{t.appearance}</span><b>{t.appearanceDefault}</b></button>
    <button type="button" className="im-menu-row" onClick={onReset}><span>{t.about}</span><b>{t.version}</b></button>
  </section>
}

function getNavItems(t: MobileCopy): Array<{ tab: MobileTab; label: string; icon: typeof Home }> {
  return [
    { tab: 'home', label: t.home, icon: Home },
    { tab: 'searches', label: t.searches, icon: Bell },
    { tab: 'favorites', label: t.favorites, icon: Heart },
    { tab: 'messages', label: t.chat, icon: MessageCircle },
    { tab: 'menu', label: t.menu, icon: Menu },
  ]
}

export function IdealistaMobileApp() {
  const [step, setStepState] = useState<OnboardingStep>('language')
  const [language, setLanguageState] = useState<AppLanguage>(() => {
    try {
      const saved = localStorage.getItem(LANGUAGE_KEY)
      return saved === 'es' || saved === 'en' || saved === 'ru' ? saved : 'es'
    } catch { return 'es' }
  })
  const [tab, setTab] = useState<MobileTab>('home')
  const t: MobileCopy = copy[language]
  const navItems = getNavItems(t)

  const setLanguage = (next: AppLanguage) => {
    setLanguageState(next)
    try { localStorage.setItem(LANGUAGE_KEY, next) } catch { /* no-op */ }
  }

  useEffect(() => {
    document.documentElement.classList.add('idealista-mobile-active')
    return () => document.documentElement.classList.remove('idealista-mobile-active')
  }, [])
  useEffect(() => { document.documentElement.lang = language }, [language])

  if (step !== 'done') return <div className="idealista-mobile-app"><Onboarding step={step} setStep={setStepState} language={language} setLanguage={setLanguage} /></div>

  return <div className="idealista-mobile-app">
    <main className="im-main">
      {tab === 'home' ? <HomeScreen t={t} /> : null}
      {tab === 'searches' ? <EmptyScreen kind="searches" onLogin={() => setStepState('auth')} t={t} /> : null}
      {tab === 'favorites' ? <EmptyScreen kind="favorites" onLogin={() => setStepState('auth')} t={t} /> : null}
      {tab === 'messages' ? <EmptyScreen kind="messages" onLogin={() => setStepState('auth')} t={t} /> : null}
      {tab === 'menu' ? <MenuScreen onLogin={() => setStepState('auth')} onReset={() => setStepState('language')} language={language} t={t} /> : null}
    </main>
    <nav className="im-bottom-nav" aria-label={t.mainNavigation}>{navItems.map(({ tab: itemTab, label, icon: Icon }) => <button key={itemTab} type="button" className={cn(tab === itemTab && 'is-active')} onClick={() => setTab(itemTab)}><Icon /><span>{label}</span></button>)}</nav>
  </div>
}
