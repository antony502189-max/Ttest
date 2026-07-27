import { useEffect } from 'react'
import { Mail } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
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
  const { language } = useI18n()
  const t = copy[language]

  useEffect(() => {
    document.documentElement.classList.add('mobile-v2-active')
    return () => document.documentElement.classList.remove('mobile-v2-active')
  }, [])

  const close = () => navigate('/', { replace: true })
  const back = () => {
    if (window.history.length > 1) navigate(-1)
    else close()
  }

  return <div className="m2-app notranslate" translate="no">
    <section className="m2-onboarding m2-onboarding--auth">
      <button type="button" className="m2-auth-back" onClick={back} aria-label={t.back}>‹</button>
      <button type="button" className="m2-auth-skip" onClick={close}>{t.skip}</button>
      <div className="m2-auth-panel">
        <div className="m2-brand" aria-label="www.112233.es">www.112233.es</div>
        <span>España (Tenerife)</span>
        <h1>{t.title}</h1>
        <button type="button" onClick={close}><b>G</b>{t.google}</button>
        <button type="button" onClick={close}><Mail />{t.email}</button>
        <p>{t.legal}</p>
        <Link to="/privacidad">{t.privacy}</Link>
        <Link to="/terminos">{t.terms}</Link>
      </div>
    </section>
  </div>
}
