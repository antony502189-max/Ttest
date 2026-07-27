import { useEffect, useState, type FormEvent } from 'react'
import { Mail } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'
import '@/mobile-app-v2.css'

const copy = {
  es: {
    title: 'Inicia sesión o regístrate',
    google: 'Continuar con Google',
    email: 'Iniciar sesión con email',
    legal: 'Consulta la siguiente información:',
    privacy: 'Política de privacidad',
    terms: 'Términos y condiciones',
    skip: 'Ahora no',
    back: 'Volver',
  },
  en: {
    title: 'Sign in or create an account',
    google: 'Continue with Google',
    email: 'Sign in with email',
    legal: 'Review the following information:',
    privacy: 'Privacy policy',
    terms: 'Terms and conditions',
    skip: 'Not now',
    back: 'Back',
  },
  ru: {
    title: 'Войдите или зарегистрируйтесь',
    google: 'Продолжить с Google',
    email: 'Войти с помощью email',
    legal: 'Ознакомьтесь со следующей информацией:',
    privacy: 'Политика конфиденциальности',
    terms: 'Условия использования',
    skip: 'Сейчас нет',
    back: 'Назад',
  },
} as const

export function UnifiedAuthPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { language } = useI18n()
  const { login } = useApp()
  const t = copy[language]
  const [showEmail, setShowEmail] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    document.documentElement.classList.add('mobile-v2-active')
    return () => document.documentElement.classList.remove('mobile-v2-active')
  }, [])

  const close = () => navigate('/', { replace: true })
  const back = () => {
    if (window.history.length > 1) navigate(-1)
    else close()
  }
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSubmitting(true)
    const message = await login(email, password)
    setSubmitting(false)
    if (message) { setError(message); return }
    const state = location.state as { returnTo?: string } | null
    navigate(state?.returnTo ?? '/', { replace: true })
  }

  return <div className="m2-app notranslate" translate="no">
    <section className="m2-onboarding m2-onboarding--auth">
      <button type="button" className="m2-auth-back" onClick={back} aria-label={t.back}>‹</button>
      <button type="button" className="m2-auth-skip" onClick={close}>{t.skip}</button>
      <div className="m2-auth-panel">
        <div className="m2-brand" aria-label="www.112233.es">www.112233.es</div>
        <span>España (Tenerife)</span>
        <h1>{t.title}</h1>
        <button type="button" disabled title="Google sign-in is not configured yet"><b>G</b>{t.google}</button>
        {!showEmail ? <button type="button" onClick={() => setShowEmail(true)}><Mail />{t.email}</button> : <form className="m2-auth-form" onSubmit={submit}>
          <input aria-label="Email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required placeholder="Email" />
          <input aria-label="Contraseña" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required placeholder="Contraseña" />
          {error ? <p role="alert">{error}</p> : null}
          <button type="submit" disabled={submitting}>{submitting ? '…' : t.email}</button>
          <Link to="/registro">Crear una cuenta</Link>
        </form>}
        <p>{t.legal}</p>
        <Link to="/privacidad">{t.privacy}</Link>
        <Link to="/terminos">{t.terms}</Link>
      </div>
    </section>
  </div>
}
