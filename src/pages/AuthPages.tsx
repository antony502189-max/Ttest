import { useState, type FormEvent, type ReactNode } from 'react'
import { CheckCircle2, KeyRound, Mail, ShieldCheck } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { FormField } from '@/components/forms'
import { Logo } from '@/components/layout'
import { useApp } from '@/contexts/app-context'
import { requestPasswordReset, resetPassword, verifyEmail } from '@/api/auth'
import type { UserRole } from '@/types'

function AuthShell({ title, description, children, asideTitle = 'Tu próxima habitación empieza con información clara.' }: { title: string; description: string; children: ReactNode; asideTitle?: string }) {
  return <div className="auth-page"><aside><Logo /><div><span className="eyebrow">112233.es</span><h2>{asideTitle}</h2><ul><li><ShieldCheck />Condiciones visibles antes de contactar</li><li><ShieldCheck />Anunciantes con señales de confianza</li><li><ShieldCheck />Demo local sin datos reales</li></ul></div><small>Tenerife · frontend demo</small></aside><section><div className="auth-card"><h1>{title}</h1><p>{description}</p>{children}</div></section></div>
}

export function RegisterPage() {
  const { register } = useApp()
  const [success, setSuccess] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const submit = async (event: FormEvent<HTMLFormElement>) => {
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
      const error = await register({ name, email, password, role: String(data.get('role')) as UserRole })
      if (error) next.email = error
      else setSuccess(true)
    }
    setErrors(next)
    if (Object.keys(next).length) window.setTimeout(() => form.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(), 0)
  }
  if (success) return <AuthShell title="Cuenta creada" description="La sesión demo ya está activa."><Alert><CheckCircle2 /><AlertTitle>Registro completado</AlertTitle><AlertDescription>En producción se enviaría un enlace de confirmación. En esta demo puedes continuar directamente.</AlertDescription></Alert><Button asChild className="w-full"><Link to="/perfil">Abrir mi perfil</Link></Button></AuthShell>
  return <AuthShell title="Crea tu cuenta" description="Tardarás menos de dos minutos."><form className="auth-form" onSubmit={submit} noValidate><FormField label="Nombre" htmlFor="register-name" error={errors.name}><Input id="register-name" name="name" autoComplete="name" aria-invalid={!!errors.name} aria-describedby={errors.name ? 'register-name-error' : undefined} /></FormField><FormField label="Email" htmlFor="register-email" error={errors.email}><Input id="register-email" name="email" type="email" autoComplete="email" aria-invalid={!!errors.email} /></FormField><FormField label="Contraseña" htmlFor="register-password" description="Mínimo 8 caracteres." error={errors.password}><Input id="register-password" name="password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} /></FormField><FormField label="Repite la contraseña" htmlFor="register-confirm" error={errors.confirm}><Input id="register-confirm" name="confirm" type="password" autoComplete="new-password" aria-invalid={!!errors.confirm} /></FormField><fieldset className="role-choice"><legend>¿Qué quieres hacer?</legend><label><input type="radio" name="role" value="tenant" defaultChecked /><span>Busco habitación<small>Guardar, comparar y contactar</small></span></label><label><input type="radio" name="role" value="host" /><span>Publico habitaciones<small>Crear y gestionar anuncios</small></span></label></fieldset><label className="terms-check"><Checkbox checked={accepted} onCheckedChange={(value) => setAccepted(value === true)} aria-invalid={!!errors.terms} /><span>Acepto los <Link to="/terminos">términos</Link>, la <Link to="/privacidad">privacidad</Link> y las <Link to="/normas-de-publicacion">normas de publicación</Link>.</span></label>{errors.terms ? <p className="field-error" role="alert">{errors.terms}</p> : null}<Button type="submit" size="lg">Crear cuenta</Button><p className="auth-switch">¿Ya tienes cuenta? <Link to="/acceso">Accede</Link></p></form></AuthShell>
}

export function RecoverPasswordPage() {
  const [sent, setSent] = useState(false)
  const [token, setToken] = useState<string | null>(null)
  const [error, setError] = useState('')
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')
    try {
      const result = await requestPasswordReset(String(new FormData(event.currentTarget).get('email')).trim())
      setToken(result.resetToken ?? null)
      setSent(true)
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo solicitar el restablecimiento.') }
  }
  return <AuthShell title="Recupera tu contraseña" description="Te enviaremos un enlace seguro para crear una contraseña nueva.">{sent ? <><Alert><Mail /><AlertTitle>Solicitud registrada</AlertTitle><AlertDescription>Si existe una cuenta con ese email, recibirás las instrucciones de restablecimiento.</AlertDescription></Alert>{token ? <Button asChild><Link to={`/restablecer-contrasena?token=${encodeURIComponent(token)}`}>Crear nueva contraseña</Link></Button> : null}</> : <form className="auth-form" onSubmit={submit}><FormField label="Email de tu cuenta" htmlFor="recover-email" error={error}><Input id="recover-email" name="email" type="email" required autoComplete="email" aria-invalid={Boolean(error)} /></FormField><Button size="lg"><Mail data-icon="inline-start" />Solicitar enlace</Button></form>}</AuthShell>
}

export function ResetPasswordPage() {
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const [params] = useSearchParams()
  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const password = String(data.get('password'))
    const token = params.get('token')
    if (!token) { setError('El enlace de restablecimiento no es válido o ha caducado.'); return }
    if (password.length < 12 || password !== data.get('confirm')) { setError('Las contraseñas deben coincidir y tener al menos 12 caracteres.'); return }
    try { await resetPassword(token, password); setError(''); setDone(true) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo actualizar la contraseña.') }
  }
  return <AuthShell title={done ? 'Contraseña actualizada' : 'Crea una nueva contraseña'} description={done ? 'Ya puedes acceder con tu nueva contraseña.' : 'Usa al menos 12 caracteres.'}>{done ? <><Alert><CheckCircle2 /><AlertTitle>Todo listo</AlertTitle><AlertDescription>Tu contraseña se ha actualizado y las sesiones anteriores se han cerrado.</AlertDescription></Alert><Button asChild><Link to="/acceso">Acceder</Link></Button></> : <form className="auth-form" onSubmit={submit}><FormField label="Nueva contraseña" htmlFor="reset-password" error={error}><Input id="reset-password" name="password" type="password" minLength={12} required aria-invalid={!!error} /></FormField><FormField label="Repite la contraseña" htmlFor="reset-confirm"><Input id="reset-confirm" name="confirm" type="password" minLength={12} required /></FormField><Button size="lg"><KeyRound data-icon="inline-start" />Guardar contraseña</Button></form>}</AuthShell>
}

export function VerifyEmailPage() {
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')
  const [params] = useSearchParams()
  const submit = async () => {
    const token = params.get('token')
    if (!token) { setError('El enlace de confirmación no es válido o ha caducado.'); return }
    try { await verifyEmail(token); setError(''); setDone(true) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'No se pudo confirmar el correo.') }
  }
  return <AuthShell title={done ? 'Correo confirmado' : 'Confirma tu correo'} description={done ? 'Tu dirección de correo ya está verificada.' : 'Confirma tu dirección para completar la seguridad de tu cuenta.'}>{done ? <><Alert><CheckCircle2 /><AlertTitle>Todo listo</AlertTitle><AlertDescription>Ya puedes continuar usando tu cuenta.</AlertDescription></Alert><Button asChild><Link to="/">Ir al inicio</Link></Button></> : <><FormField label="Enlace de confirmación" htmlFor="verification-token" error={error}><Input id="verification-token" value={params.get('token') ?? ''} readOnly aria-invalid={!!error} /></FormField><Button size="lg" onClick={submit}><Mail data-icon="inline-start" />Confirmar correo</Button></>}</AuthShell>
}
