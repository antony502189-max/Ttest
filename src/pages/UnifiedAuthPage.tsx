import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowLeft, Mail } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'
import '@/mobile-app-v2.css'
import '@/auth-account.css'

type GoogleCredentialResponse = { credential: string }
type GoogleButtonOptions = {
  type: 'standard'
  theme: 'filled_black'
  size: 'large'
  text: 'continue_with'
  shape: 'rectangular'
  logo_alignment: 'left'
  width: number
}
type GoogleIdentityApi = {
  accounts: { id: {
    initialize: (options: { client_id: string; callback: (response: GoogleCredentialResponse) => void; cancel_on_tap_outside?: boolean }) => void
    renderButton: (parent: HTMLElement, options: GoogleButtonOptions) => void
    cancel?: () => void
  } }
}

declare global { interface Window { google?: GoogleIdentityApi } }

const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined
const mockMode = import.meta.env.VITE_ENABLE_MOCK_MODE === '1'
const mockGoogleAccount = {
  name: 'Usuario Google Demo',
  email: 'google.demo@112233.es',
  password: 'GoogleDemo112233!',
} as const

const copy = {
  es: {
    title: 'Inicia sesión o regístrate', google: 'Continuar con Google', email: 'Iniciar sesión con email',
    legal: 'Consulta la siguiente información:', privacy: 'Política de privacidad', terms: 'Términos y condiciones',
    back: 'Volver', country: 'España y Andorra', changeCountry: 'Cambiar país', password: 'Contraseña',
    create: 'Crear una cuenta', forgot: '¿Has olvidado tu contraseña?', googleMissing: 'Google todavía no está configurado para este entorno.',
  },
  en: {
    title: 'Sign in or create an account', google: 'Continue with Google', email: 'Sign in with email',
    legal: 'Review the following information:', privacy: 'Privacy policy', terms: 'Terms and conditions',
    back: 'Back', country: 'Spain and Andorra', changeCountry: 'Change country', password: 'Password',
    create: 'Create an account', forgot: 'Forgot your password?', googleMissing: 'Google is not configured for this environment yet.',
  },
  ru: {
    title: 'Войти в аккаунт или зарегистрироваться', google: 'Продолжить с Google', email: 'Войти с помощью email',
    legal: 'Ознакомьтесь со следующей информацией:', privacy: 'Политика конфиденциальности', terms: 'Общие положения и условия',
    back: 'Назад', country: 'Испания и Андорра', changeCountry: 'Изменить страну', password: 'Пароль',
    create: 'Создать аккаунт', forgot: 'Забыли пароль?', googleMissing: 'Google ещё не настроен для этого окружения.',
  },
} as const

export function UnifiedAuthPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { language } = useI18n()
  const { currentUser, login, loginGoogle, selectGoogleRole, register } = useApp()
  const t = copy[language]
  const googleButtonRef = useRef<HTMLDivElement>(null)
  const [showEmail, setShowEmail] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [googleReady, setGoogleReady] = useState(mockMode)

  const finishLogin = useCallback(() => {
    const state = location.state as { returnTo?: string } | null
    navigate(state?.returnTo ?? '/', { replace: true })
  }, [location.state, navigate])

  useEffect(() => {
    document.documentElement.classList.add('mobile-v2-active')
    return () => document.documentElement.classList.remove('mobile-v2-active')
  }, [])

  useEffect(() => {
    if (currentUser && currentUser.role !== 'pending') finishLogin()
  }, [currentUser, finishLogin])

  const acceptGoogleCredential = useCallback(async (credential: string) => {
    setError('')
    setSubmitting(true)
    const message = await loginGoogle(credential)
    setSubmitting(false)
    if (message) { setError(message); return }
    finishLogin()
  }, [finishLogin, loginGoogle])

  useEffect(() => {
    if (mockMode || !googleClientId) return
    let cancelled = false
    let frame = 0

    const renderGoogleButton = () => {
      const api = window.google?.accounts.id
      const container = googleButtonRef.current
      if (!api || !container || cancelled) return
      container.replaceChildren()
      api.initialize({
        client_id: googleClientId,
        callback: ({ credential }) => { void acceptGoogleCredential(credential) },
        cancel_on_tap_outside: false,
      })
      const width = Math.max(220, Math.min(400, Math.floor(container.getBoundingClientRect().width || 360)))
      api.renderButton(container, {
        type: 'standard', theme: 'filled_black', size: 'large', text: 'continue_with',
        shape: 'rectangular', logo_alignment: 'left', width,
      })
      setGoogleReady(true)
    }

    const initialize = () => { frame = window.requestAnimationFrame(renderGoogleButton) }
    if (window.google?.accounts.id) {
      initialize()
      return () => {
        cancelled = true
        window.cancelAnimationFrame(frame)
        window.google?.accounts.id.cancel?.()
      }
    }
    const existing = document.getElementById('google-identity-services') as HTMLScriptElement | null
    if (existing) {
      existing.addEventListener('load', initialize)
      initialize()
      return () => {
        cancelled = true
        existing.removeEventListener('load', initialize)
        window.cancelAnimationFrame(frame)
      }
    }

    const script = document.createElement('script')
    script.id = 'google-identity-services'
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.addEventListener('load', initialize)
    script.addEventListener('error', () => { if (!cancelled) setError(t.googleMissing) })
    document.head.append(script)
    return () => {
      cancelled = true
      script.removeEventListener('load', initialize)
      window.cancelAnimationFrame(frame)
      window.google?.accounts.id.cancel?.()
    }
  }, [acceptGoogleCredential, t.googleMissing])

  const runMockGoogle = async () => {
    setError('')
    setSubmitting(true)
    const registrationError = await register({ ...mockGoogleAccount, role: 'tenant' })
    const message = registrationError ? await login(mockGoogleAccount.email, mockGoogleAccount.password) : null
    setSubmitting(false)
    if (message) { setError(message); return }
    finishLogin()
  }

  const chooseGoogleRole = async (role: 'tenant' | 'host') => {
    setError('')
    setSubmitting(true)
    const message = await selectGoogleRole(role)
    setSubmitting(false)
    if (message) setError(message)
  }

  const back = () => {
    if (window.history.length > 1) navigate(-1)
    else navigate('/', { replace: true })
  }

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    const message = await login(email, password)
    setSubmitting(false)
    if (message) { setError(message); return }
    finishLogin()
  }

  return <div className="m2-app m2-auth-screen notranslate" translate="no">
    <header className="m2-auth-appbar">
      <button type="button" onClick={back} aria-label={t.back}><ArrowLeft /></button>
      <strong>{t.title}</strong>
    </header>
    <main className="m2-auth-content">
      <div className="m2-brand" aria-label="www.112233.es">www.112233.es</div>
      <div className="m2-auth-region"><span>{t.country}</span><button type="button" onClick={() => navigate('/?panel=ubicacion')}>{t.changeCountry}</button></div>
      <h1>{t.title}</h1>

      {currentUser?.role === 'pending' ? <>
        <h2>¿Qué quieres hacer?</h2>
        <button type="button" className="m2-auth-choice" disabled={submitting} onClick={() => { void chooseGoogleRole('tenant') }}>Busco vivienda</button>
        <button type="button" className="m2-auth-choice" disabled={submitting} onClick={() => { void chooseGoogleRole('host') }}>Publico vivienda</button>
      </> : mockMode ? <button type="button" className="m2-auth-choice" disabled={submitting} onClick={() => { void runMockGoogle() }}><b className="m2-google-mark">G</b>{t.google}</button>
        : googleClientId ? <div ref={googleButtonRef} className="m2-auth-google-slot" aria-label={t.google} data-ready={googleReady ? '1' : '0'} />
          : <button type="button" className="m2-auth-choice" disabled title={t.googleMissing}><b className="m2-google-mark">G</b>{t.google}</button>}

      {!showEmail ? <button type="button" className="m2-auth-choice" onClick={() => { setError(''); setShowEmail(true) }}><Mail />{t.email}</button>
        : <form className="m2-auth-form m2-auth-form--expanded" onSubmit={submit}>
          <input aria-label="Email" type="email" autoComplete="email" value={email} onChange={(event) => { setEmail(event.target.value); setError('') }} required placeholder="Email" />
          <input id="login-password" aria-label={t.password} type="password" autoComplete="current-password" value={password} onChange={(event) => { setPassword(event.target.value); setError('') }} required placeholder={t.password} />
          <button type="submit" disabled={submitting}>{submitting ? '…' : t.email}</button>
          <div className="m2-auth-form-links"><Link to="/registro">{t.create}</Link><Link to="/recuperar-contrasena">{t.forgot}</Link></div>
        </form>}

      {error ? <p className="m2-auth-error" role="alert">{error}</p> : null}
      {!mockMode && googleClientId && !googleReady ? <p className="m2-auth-status" role="status">…</p> : null}
      <div className="m2-auth-legal"><p>{t.legal}</p><Link to="/privacidad">{t.privacy}</Link><Link to="/terminos">{t.terms}</Link></div>
    </main>
  </div>
}
