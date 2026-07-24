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
type AppLanguage = 'es' | 'en' | 'ru'

const languages: Array<{ value: AppLanguage; label: string }> = [
  { value: 'es', label: 'Español' },
  { value: 'en', label: 'English' },
  { value: 'ru', label: 'Русский' },
]
const countries = [{ name: 'España (Tenerife)', shape: 'ES' }]

function IdealistaWordmark({ compact = false }: { compact?: boolean }) {
  return <div className={cn('im-wordmark', compact && 'im-wordmark--compact')} aria-label="www.112233.es">www.112233.es</div>
}

function PrimaryButton({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return <button type="button" className="im-primary-button" onClick={onClick}>{children}</button>
}

function AuthPanel({ onContinue, title = 'Войти в аккаунт или зарегистрироваться' }: { onContinue: () => void; title?: string }) {
  return <div className="im-auth-panel">
    <IdealistaWordmark />
    <span className="im-auth-kicker">España (Tenerife)</span>
    <h1>{title}</h1>
    <button type="button" className="im-social-button" onClick={onContinue}><b>G</b> Продолжить с Google</button>
    <button type="button" className="im-social-button" onClick={onContinue}><Mail aria-hidden="true" /> Войти с помощью email</button>
    <p>Ознакомиться со следующей информацией:</p>
    <a href="#privacy">Политика конфиденциальности</a>
    <a href="#terms">Общие положения и условия</a>
  </div>
}

function Onboarding({ step, setStep }: { step: OnboardingStep; setStep: (step: OnboardingStep) => void }) {
  const [selectedLanguage, setSelectedLanguage] = useState<AppLanguage>('es')

  if (step === 'auth') return <section className="im-onboarding im-onboarding--auth"><button className="im-back" type="button" onClick={() => setStep('privacy')}>‹</button><button className="im-skip" type="button" onClick={() => setStep('done')}>Сейчас нет</button><AuthPanel onContinue={() => setStep('done')} /></section>

  return <section className="im-onboarding">
    <IdealistaWordmark />
    {step === 'language' ? <>
      <div className="im-onboarding-content">
        <h1>Выберите язык приложения</h1>
        <div className="im-option-list im-option-list--scroll">{languages.map(({ value, label }) => <button key={value} type="button" className={cn('im-option-row', value === selectedLanguage && 'is-selected')} onClick={() => setSelectedLanguage(value)}><span>{label}</span>{value === selectedLanguage ? <span className="im-check">✓</span> : null}</button>)}</div>
      </div>
      <PrimaryButton onClick={() => setStep('country')}>Продолжить</PrimaryButton>
    </> : null}
    {step === 'country' ? <>
      <div className="im-onboarding-content">
        <h1>Выберите регион, в котором вы ищете или имеете жильё</h1>
        <div className="im-country-list">{countries.map((country) => <button key={country.name} type="button" className="im-country-row is-selected" onClick={() => setStep('privacy')}><span className="im-country-shape">{country.shape}</span><span>{country.name}</span><span className="im-check">✓</span></button>)}</div>
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
      <button type="button" className="im-select-row"><span>Искать на Тенерифе</span><MapPin /></button>
      <PrimaryButton><Search /> Найти</PrimaryButton>
      <button type="button" className="im-outline-button">Разместить объявление</button>
    </div>
  </section>
}

function EmptyScreen({ kind, onLogin }: { kind: 'searches' | 'favorites' | 'messages'; onLogin: () => void }) {
  const data = {
    searches: { title: 'Ваши поиски', heading: 'Ваше избранное все вместе', text: 'Сохраняйте здесь частые настройки поиска для большего удобства. Также мы уведомим вас о появлении новых объявлений, совпадающих с вашими критериями.', icon: <Bell /> },
    favorites: { title: 'Избранное и списки', heading: 'У вас нет объектов в Избранное', text: 'Сохраните понравившиеся объявления в вашем аккаунте, чтобы просматривать их на телефоне, планшете или компьютере.', icon: <Heart /> },
    messages: { title: 'Чат', heading: 'Войдите в аккаунт, чтобы увидеть свои чаты', text: 'Общайтесь с владельцами объектов и рекламодателями и отвечайте на новые сообщения. Все на выходу из 112233.es.', icon: <MessageCircle /> },
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
    <button type="button" className="im-menu-row"><span>Регион поиска</span><b>España (Tenerife)</b></button>
    <button type="button" className="im-menu-row"><span>Язык</span><b>Español</b></button>
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
  const [step, setStepState] = useState<OnboardingStep>('language')
  const [tab, setTab] = useState<MobileTab>('home')
  const setStep = (next: OnboardingStep) => setStepState(next)
  useEffect(() => { document.documentElement.classList.add('idealista-mobile-active'); return () => document.documentElement.classList.remove('idealista-mobile-active') }, [])

  if (step !== 'done') return <div className="idealista-mobile-app"><Onboarding step={step} setStep={setStep} /></div>

  return <div className="idealista-mobile-app">
    <main className="im-main">
      {tab === 'home' ? <HomeScreen /> : null}
      {tab === 'searches' ? <EmptyScreen kind="searches" onLogin={() => setStepState('auth')} /> : null}
      {tab === 'favorites' ? <EmptyScreen kind="favorites" onLogin={() => setStepState('auth')} /> : null}
      {tab === 'messages' ? <EmptyScreen kind="messages" onLogin={() => setStepState('auth')} /> : null}
      {tab === 'menu' ? <MenuScreen onLogin={() => setStepState('auth')} onReset={() => setStepState('language')} /> : null}
    </main>
    <nav className="im-bottom-nav" aria-label="Основная навигация">{navItems.map(({ tab: itemTab, label, icon: Icon }) => <button key={itemTab} type="button" className={cn(tab === itemTab && 'is-active')} onClick={() => setTab(itemTab)}><Icon /><span>{label}</span></button>)}</nav>
  </div>
}
