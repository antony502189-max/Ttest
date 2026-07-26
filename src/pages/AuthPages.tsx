import { useState, type FormEvent, type ReactNode } from 'react'
import { CheckCircle2, Eye, EyeOff, KeyRound, Mail, ShieldCheck } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { FormField } from '@/components/forms'
import { Logo } from '@/components/layout'
import { useApp } from '@/contexts/app-context'
import type { UserRole } from '@/types'

function AuthShell({ title, description, children, asideTitle = 'Tu próxima habitación empieza con información clara.' }: { title: string; description: string; children: ReactNode; asideTitle?: string }) {
  return <div className="auth-page"><aside><Logo /><div><span className="eyebrow">112233.es</span><h2>{asideTitle}</h2><ul><li><ShieldCheck />Condiciones visibles antes de contactar</li><li><ShieldCheck />Anunciantes con señales de confianza</li><li><ShieldCheck />Demo local sin datos reales</li></ul></div><small>Tenerife · frontend demo</small></aside><section><div className="auth-card"><h1>{title}</h1><p>{description}</p>{children}</div></section></div>
}

export function RegisterPage() {
  const { register } = useApp()
  const [success, setSuccess] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const next: Record<string, string> = {}
    const name = String(data.get('name')).trim()
    const email = String(data.get('email')).trim()
    const password = String(data.get('password'))
    if (!name) next.name = 'Escribe tu nombre.'
    if (!/^\S+@\S+\.\S+$/.test(email)) next.email = 'Introduce un email válido.'
    if (password.length < 8) next.password = 'Usa al menos 8 caracteres.'
    if (password !== data.get('confirm')) next.confirm = 'Las contraseñas no coinciden.'
    if (!accepted) next.terms = 'Debes aceptar las normas para continuar.'
    if (!Object.keys(next).length) {
      const error = register({ name, email, password, role: String(data.get('role')) as UserRole })
      if (error) next.email = error
      else setSuccess(true)
    }
    setErrors(next)
    if (Object.keys(next).length) window.setTimeout(() => form.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(), 0)
  }
  if (success) return <AuthShell title="Cuenta creada" description="La sesión demo ya está activa."><Alert><CheckCircle2 /><AlertTitle>Registro completado</AlertTitle><AlertDescription>En producción se enviaría un enlace de confirmación. En esta demo puedes continuar directamente.</AlertDescription></Alert><Button asChild className="w-full"><Link to="/perfil">Abrir mi perfil</Link></Button></AuthShell>
  return <AuthShell title="Crea tu cuenta" description="Tardarás menos de dos minutos."><form className="auth-form" onSubmit={submit} noValidate><FormField label="Nombre" htmlFor="register-name" error={errors.name}><Input id="register-name" name="name" autoComplete="name" aria-invalid={!!errors.name} aria-describedby={errors.name ? 'register-name-error' : undefined} /></FormField><FormField label="Email" htmlFor="register-email" error={errors.email}><Input id="register-email" name="email" type="email" autoComplete="email" aria-invalid={!!errors.email} /></FormField><FormField label="Contraseña" htmlFor="register-password" description="Mínimo 8 caracteres." error={errors.password}><Input id="register-password" name="password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} /></FormField><FormField label="Repite la contraseña" htmlFor="register-confirm" error={errors.confirm}><Input id="register-confirm" name="confirm" type="password" autoComplete="new-password" aria-invalid={!!errors.confirm} /></FormField><fieldset className="role-choice"><legend>¿Qué quieres hacer?</legend><label><input type="radio" name="role" value="tenant" defaultChecked /><span>Busco habitación<small>Guardar, comparar y contactar</small></span></label><label><input type="radio" name="role" value="host" /><span>Publico habitaciones<small>Crear y gestionar anuncios</small></span></label></fieldset><label className="terms-check"><Checkbox checked={accepted} onCheckedChange={(value) => setAccepted(value === true)} aria-invalid={!!errors.terms} /><span>Acepto los <Link to="/terminos">términos</Link>, la <Link to="/privacidad">privacidad</Link> y las <Link to="/normas-de-publicacion">normas de publicación</Link>.</span></label>{errors.terms ? <p className="field-error" role="alert">{errors.terms}</p> : null}<Button type="submit" size="lg">Crear cuenta</Button><p className="auth-switch">¿Ya tienes cuenta? <Link to="/acceso">Accede</Link></p></form></AuthShell>
}

const demoAccounts = [
  ['Inquilina', 'inquilina@112233.es', 'demo112233'],
  ['Anfitrión', 'anfitrion@112233.es', 'demo112233'],
  ['Admin', 'admin@112233.es', 'admin112233'],
] as const

export function LoginPage() {
  const { login } = useApp()
  const [visible, setVisible] = useState(false)
  const [error, setError] = useState('')
  const [credentials, setCredentials] = useState({ email: '', password: '' })
  const navigate = useNavigate()
  const location = useLocation()
  const returnTo = (location.state as { returnTo?: string } | null)?.returnTo || '/perfil'
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const nextError = login(credentials.email, credentials.password)
    setError(nextError ?? '')
    if (!nextError) navigate(returnTo, { replace: true })
  }
  return <AuthShell title="Bienvenido de nuevo" description="Accede con una cuenta demo o con la que hayas registrado."><div className="demo-credentials" aria-label="Cuentas de demostración"><strong>Cuentas demo</strong>{demoAccounts.map(([label, email, password]) => <button type="button" key={email} onClick={() => setCredentials({ email, password })}><span>{label}</span><small>{email}</small></button>)}</div><form className="auth-form" onSubmit={submit} noValidate><FormField label="Email" htmlFor="login-email" error={error}><Input id="login-email" name="email" type="email" autoComplete="email" value={credentials.email} onChange={(event) => setCredentials({ ...credentials, email: event.target.value })} aria-invalid={!!error} /></FormField><FormField label="Contraseña" htmlFor="login-password"><div className="password-input"><Input id="login-password" name="password" type={visible ? 'text' : 'password'} autoComplete="current-password" value={credentials.password} onChange={(event) => setCredentials({ ...credentials, password: event.target.value })} /><Button type="button" variant="ghost" size="icon" onClick={() => setVisible((value) => !value)} aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}>{visible ? <EyeOff /> : <Eye />}</Button></div></FormField><div className="form-between"><span>Solo datos de demostración</span><Link to="/recuperar-contrasena">¿Has olvidado la contraseña?</Link></div><Button type="submit" size="lg">Acceder</Button><p className="auth-switch">¿No tienes cuenta? <Link to="/registro">Crear cuenta</Link></p></form></AuthShell>
}

export function RecoverPasswordPage() {
  const [sent, setSent] = useState(false)
  return <AuthShell title="Recupera tu contraseña" description="Simularemos el envío de un enlace seguro.">{sent ? <><Alert><Mail /><AlertTitle>Solicitud registrada</AlertTitle><AlertDescription>En esta demo no se envían correos reales. Continúa al formulario de restablecimiento.</AlertDescription></Alert><Button asChild><Link to="/restablecer-contrasena">Crear nueva contraseña</Link></Button></> : <form className="auth-form" onSubmit={(event) => { event.preventDefault(); setSent(true) }}><FormField label="Email de tu cuenta" htmlFor="recover-email"><Input id="recover-email" type="email" required autoComplete="email" /></FormField><Button size="lg"><Mail data-icon="inline-start" />Solicitar enlace demo</Button></form>}</AuthShell>
}

export function ResetPasswordPage() {
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const data = new FormData(event.currentTarget); const password = String(data.get('password')); if (password.length < 8 || password !== data.get('confirm')) setError('Las contraseñas deben coincidir y tener al menos 8 caracteres.'); else { setError(''); setDone(true) } }
  return <AuthShell title={done ? 'Contraseña actualizada' : 'Crea una nueva contraseña'} description={done ? 'Ya puedes acceder con tu nueva contraseña demo.' : 'Usa al menos 8 caracteres.'}>{done ? <><Alert><CheckCircle2 /><AlertTitle>Todo listo</AlertTitle><AlertDescription>El flujo demo se ha completado.</AlertDescription></Alert><Button asChild><Link to="/acceso">Acceder</Link></Button></> : <form className="auth-form" onSubmit={submit}><FormField label="Nueva contraseña" htmlFor="reset-password" error={error}><Input id="reset-password" name="password" type="password" minLength={8} required aria-invalid={!!error} /></FormField><FormField label="Repite la contraseña" htmlFor="reset-confirm"><Input id="reset-confirm" name="confirm" type="password" minLength={8} required /></FormField><Button size="lg"><KeyRound data-icon="inline-start" />Guardar contraseña</Button></form>}</AuthShell>
}
