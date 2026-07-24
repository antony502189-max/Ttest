import { useEffect, useState, type ReactNode } from 'react'
import {
  Bell,
  Building2,
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
  Settings,
  UserRound,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import '@/idealista-mobile-app.css'

type OnboardingStep = 'language' | 'country' | 'privacy' | 'auth' | 'done'
type MobileTab = 'home' | 'searches' | 'favorites' | 'messages' | 'menu'
type AppLanguage = 'English' | 'Español' | 'Русский'

const ONBOARDING_KEY = '112233:idealista-mobile-onboarding:v1'

const languages: AppLanguage[] = ['English', 'Español', 'Русский']
const countries = [
  { name: 'Испания и Андорра', shape: 'ES' },
  { name: 'Италия', shape: 'IT' },
  { name: 'Португалия', shape: 'PT' },
]

function IdealistaWordmark({ compact = false }: { compact?: boolean }) {
  return <div className={cn('im-wordmark', compact && 'im-wordmark--compact')} aria-label="WWW 11-22-33.ms">WWW 11-22-33.ms</div>
}

function PrimaryButton({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return <button type="button" className="im-primary-button" onClick={onClick}>{children}</button>
}

function AuthPanel({ onContinue, title = 'Войти в аккаунт или зарегистрироваться' }: { onContinue: () => void; title?: string }) {
  return <div className="im-auth-panel">
    <IdealistaWordmark />
    <span className="im-auth-kicker">Испания и Андорра</span>
    <h1>{title}</h1>
    <button type="button" className="im-social-button" onClick={onContinue}><b>G</b> Продолжить с Google</button>
    <button type="button" className="im-social-button" onClick={onContinue}><Mail aria-hidden="true" /> Войти с помощью email</button>
    <p>Ознакомиться со следующей информацией:</p>
    <a href="#privacy">Политика конфиденциальности</a>
    <a href="#terms">Общие положения и условия</a>
  </div>
}

function Onboarding({ step, setStep }: { step: OnboardingStep; setStep: (step: OnboardingStep) => void }) {
  const [selectedLanguage, setSelectedLanguage] = useState<AppLanguage>('English')

  if (step === 'auth') return <section className="im-onboarding im-onboarding--auth"><button className="im-back" type="button" onClick={() => setStep('privacy')}>‹</button><button className="im-skip" type="button" onClick={() => setStep('done')}>Сейчас нет</button><AuthPanel onContinue={() => setStep('done')} /></section>

  return <section className="im-onboarding">
    <IdealistaWordmark />
    {step === 'language' ? <>
      <div className="im-onboarding-content">
        <h1>Выберите язык приложения</h1>
        <div className="im-option-list im-option-list--scroll">{languages.map((language) => <button key={language} type="button" className={cn('im-option-row', language === selectedLanguage && 'is-selected')} onClick={() => setSelectedLanguage(language)}><span>{language}</span>{language === selectedLanguage ? <span className="im-check">✓</span> : null}</button>)}</div>
      </div>
      <PrimaryButton onClick={() => setStep('country')}>Продолжить</PrimaryButton>
    </> : null}
    {step === 'country' ? <>
      <div className="im-onboarding-content">
        <h1>Выберите страну, в которой вы ищете или имеете жилье</h1>
        <div className="im-country-list">{countries.map((country, index) => <button key={country.name} type="button" className={cn('im-country-row', index === 0 && 'is-selected')} onClick={() => index === 0 && setStep('privacy')}><span className="im-country-shape">{country.shape}</span><span>{country.name}</span>{index === 0 ? <span className="im-check">✓</span> : null}</button>)}</div>
      </div>
      <PrimaryButton onClick={() => setStep('privacy')}>Продолжить</PrimaryButton>
    </> : null}
    {step === 'privacy' ? <>
      <div className="im-onboarding-content im-privacy-copy">
        <h1>Спасибо, что установили наше приложение</h1>
        <p>Далее, мы должны попросить у вас разрешение на персонализацию доступного функционала в зависимости от пользования сайтом и приложением. Мы будем предлагать вам, если вы дадите согласие.</p>
      </div>
      <PrimaryButton onClick={() => setStep('auth')}>Продолжить</PrimaryButton>
    </> : null}
  </section>
}

function HomeScreen() {
  return <section className="im-screen im-home-screen">
    <header className="im-topbar"><IdealistaWordmark compact /></header>
    <div className="im-hero-photo" role="img" aria-label="Дом с бассейном" />
    <div className="im-search-card">
      <div className="im-mode-switch"><button className="is-active" type="button">Купить</button><button type="button">Снять</button></div>
      <button type="button" className="im-select-row"><span>Жилые объекты</span><ChevronDown /></button>
      <button type="button" className="im-select-row"><span>Искать в Испании</span><MapPin /></button>
      <PrimaryButton><Search /> Найти</PrimaryButton>
      <button type="button" className="im-outline-button">Разместить объявление</button>
    </div>
  </section>
}

function EmptyScreen({ kind, onLogin }: { kind: 'searches' | 'favorites' | 'messages'; onLogin: () => void }) {
  const data = {
    searches: { title: 'Ваши поиски', heading: 'Ваше избранное все вместе', text: 'Сохраняйте здесь частые настройки поиска для большего удобства. Также мы уведомим вас о появлении новых объявлений, совпадающих с вашими критериями.', icon: <Bell /> },
    favorites: { title: 'Избранное и списки', heading: 'У вас нет объектов в Избранное', text: 'Сохраните понравившиеся объявления в вашем аккаунте, чтобы просматривать их на телефоне, планшете или компьютере.', icon: <Heart /> },
    messages: { title: 'Чат', heading: 'Войдите в аккаунт, чтобы увидеть свои чаты', text: 'Общайтесь с владельцами объектов и рекламодателями и отвечайте на новые сообщения. Все на выходу из idealista.', icon: <MessageCircle /> },
  }[kind]
  return <section className="im-screen im-empty-screen">
    <header className="im-section-header">{data.title}</header>
    <div className="im-empty-illustration">{data.icon}</div>
    <h1>{data.heading}</h1>
    <p>{data.text}</p>
    <PrimaryButton onClick={onLogin}>Войти в аккаунт</PrimaryButton>
  </section>
}

function MenuScreen({ onLogin, onReset }: { onLogin: () => void; onReset: () => void }) {
  return <section className="im-screen im-menu-screen">
    <header className="im-section-header">Меню</header>
    <div className="im-menu-login"><UserRound /><div><h2>Войти в аккаунт</h2><p>Синхронизируйте избранное и поиски на компьютере, планшете и мобильном телефоне.</p></div></div>
    <PrimaryButton onClick={onLogin}>Войти в аккаунт</PrimaryButton>
    <h3>Ваши объекты</h3>
    <button type="button" className="im-menu-row"><span><Building2 />Оцените свой дом бесплатно</span><ChevronRight /></button>
    <button type="button" className="im-menu-row"><span><Search />Искать агентства для продажи</span><ChevronRight /></button>
    <button type="button" className="im-menu-row"><span><Plus />Опубликуйте свое объявление</span><ChevronRight /></button>
    <h3>Настройки</h3>
    <button type="button" className="im-menu-row"><span>Страна поиска</span><b>Испания и Андорра</b></button>
    <button type="button" className="im-menu-row"><span>Язык</span><b>Русский</b></button>
    <button type="button" className="im-menu-row"><span>Внешний вид</span><b>По умолчанию (темный)</b></button>
    <h3>Услуги для вас</h3>
    <button type="button" className="im-menu-row"><span><Settings />Ипотека</span><ChevronRight /></button>
    <button type="button" className="im-menu-row"><span>Страхование от неуплат</span><ChevronRight /></button>
    <button type="button" className="im-menu-row"><span>News</span><ChevronRight /></button>
    <button type="button" className="im-menu-row" onClick={onReset}><span>О приложении</span><b>Версия 14.5.0</b></button>
  </section>
}

const navItems: Array<{ tab: MobileTab; label: string; icon: typeof Home }> = [
  { tab: 'home', label: 'Главная', icon: Home },
  { tab: 'searches', label: 'Поиски', icon: Bell },
  { tab: 'favorites', label: 'Избранное', icon: Heart },
  { tab: 'messages', label: 'Чат', icon: MessageCircle },
  { tab: 'menu', label: 'Меню', icon: Menu },
]

export function IdealistaMobileApp() {
  const [step, setStepState] = useState<OnboardingStep>(() => {
    try { return localStorage.getItem(ONBOARDING_KEY) === 'done' ? 'done' : 'language' } catch { return 'language' }
  })
  const [tab, setTab] = useState<MobileTab>('home')
  const setStep = (next: OnboardingStep) => {
    setStepState(next)
    if (next === 'done') { try { localStorage.setItem(ONBOARDING_KEY, 'done') } catch { /* no-op */ } }
  }
  useEffect(() => { document.documentElement.classList.add('idealista-mobile-active'); return () => document.documentElement.classList.remove('idealista-mobile-active') }, [])

  if (step !== 'done') return <div className="idealista-mobile-app"><Onboarding step={step} setStep={setStep} /></div>

  return <div className="idealista-mobile-app">
    <main className="im-main">
      {tab === 'home' ? <HomeScreen /> : null}
      {tab === 'searches' ? <EmptyScreen kind="searches" onLogin={() => setStepState('auth')} /> : null}
      {tab === 'favorites' ? <EmptyScreen kind="favorites" onLogin={() => setStepState('auth')} /> : null}
      {tab === 'messages' ? <EmptyScreen kind="messages" onLogin={() => setStepState('auth')} /> : null}
      {tab === 'menu' ? <MenuScreen onLogin={() => setStepState('auth')} onReset={() => { try { localStorage.removeItem(ONBOARDING_KEY) } catch { /* no-op */ }; setStepState('language') }} /> : null}
    </main>
    <nav className="im-bottom-nav" aria-label="Основная навигация">{navItems.map(({ tab: itemTab, label, icon: Icon }) => <button key={itemTab} type="button" className={cn(tab === itemTab && 'is-active')} onClick={() => setTab(itemTab)}><Icon /><span>{label}</span></button>)}</nav>
  </div>
}
