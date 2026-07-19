import { useState, type FormEvent, type ReactNode } from 'react'
import { CheckCircle2, Eye, EyeOff, KeyRound, Mail, ShieldCheck } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { FormField } from '@/components/forms'
import { Logo } from '@/components/layout'

function AuthShell({ title, description, children, asideTitle = 'Tu próxima habitación empieza con información clara.' }: { title: string; description: string; children: ReactNode; asideTitle?: string }) {
  return <div className="auth-page"><aside><Logo /><div><span className="eyebrow">112233.es</span><h2>{asideTitle}</h2><ul><li><ShieldCheck />Condiciones visibles antes de contactar</li><li><ShieldCheck />Anunciantes con señales de confianza</li><li><ShieldCheck />Sin cargos por registrarte</li></ul></div><small>Playa de las Américas · Tenerife</small></aside><section><div className="auth-card"><h1>{title}</h1><p>{description}</p>{children}</div></section></div>
}

export function RegisterPage() {
  const [success, setSuccess] = useState(false)
  const [accepted, setAccepted] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const data = new FormData(event.currentTarget)
    const next: Record<string, string> = {}
    if (!String(data.get('name')).trim()) next.name = 'Escribe tu nombre.'
    if (!String(data.get('email')).includes('@')) next.email = 'Introduce un email válido.'
    if (String(data.get('password')).length < 8) next.password = 'Usa al menos 8 caracteres.'
    if (data.get('password') !== data.get('confirm')) next.confirm = 'Las contraseñas no coinciden.'
    if (!accepted) next.terms = 'Debes aceptar las normas para continuar.'
    setErrors(next)
    if (!Object.keys(next).length) setSuccess(true)
  }
  if (success) return <AuthShell title="Cuenta creada" description="Ya puedes guardar habitaciones y contactar con anunciantes."><Alert><CheckCircle2 /><AlertTitle>Revisa tu correo</AlertTitle><AlertDescription>Hemos enviado un enlace de confirmación a tu dirección de email.</AlertDescription></Alert><Button asChild className="w-full"><Link to="/buscar">Empezar a buscar</Link></Button></AuthShell>
  return <AuthShell title="Crea tu cuenta" description="Tardarás menos de dos minutos."><form className="auth-form" onSubmit={submit} noValidate><FormField label="Nombre" htmlFor="register-name" error={errors.name}><Input id="register-name" name="name" autoComplete="name" aria-invalid={!!errors.name} /></FormField><FormField label="Email" htmlFor="register-email" error={errors.email}><Input id="register-email" name="email" type="email" autoComplete="email" aria-invalid={!!errors.email} /></FormField><FormField label="Contraseña" htmlFor="register-password" description="Mínimo 8 caracteres." error={errors.password}><Input id="register-password" name="password" type="password" autoComplete="new-password" aria-invalid={!!errors.password} /></FormField><FormField label="Repite la contraseña" htmlFor="register-confirm" error={errors.confirm}><Input id="register-confirm" name="confirm" type="password" autoComplete="new-password" aria-invalid={!!errors.confirm} /></FormField><fieldset className="role-choice"><legend>¿Qué quieres hacer?</legend><label><input type="radio" name="role" value="tenant" defaultChecked /><span>Busco habitación<small>Guardar, comparar y contactar</small></span></label><label><input type="radio" name="role" value="host" /><span>Publico habitaciones<small>Crear y gestionar anuncios</small></span></label></fieldset><label className="terms-check"><Checkbox checked={accepted} onCheckedChange={(value) => setAccepted(value === true)} aria-invalid={!!errors.terms} /><span>Acepto los <Link to="/terminos">términos</Link>, la <Link to="/privacidad">privacidad</Link> y las <Link to="/normas-de-publicacion">normas de publicación</Link>.</span></label>{errors.terms ? <p className="field-error" role="alert">{errors.terms}</p> : null}<Button type="submit" size="lg">Crear cuenta</Button><p className="auth-switch">¿Ya tienes cuenta? <Link to="/acceso">Accede</Link></p></form></AuthShell>
}

export function LoginPage() {
  const [visible, setVisible] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const submit = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); const data = new FormData(event.currentTarget); if (!String(data.get('email')).includes('@')) setError('Revisa el email y vuelve a intentarlo.'); else navigate('/perfil') }
  return <AuthShell title="Bienvenido de nuevo" description="Accede para continuar donde lo dejaste."><form className="auth-form" onSubmit={submit} noValidate><FormField label="Email" htmlFor="login-email" error={error}><Input id="login-email" name="email" type="email" autoComplete="email" aria-invalid={!!error} /></FormField><FormField label="Contraseña" htmlFor="login-password"><div className="password-input"><Input id="login-password" name="password" type={visible ? 'text' : 'password'} autoComplete="current-password" /><Button type="button" variant="ghost" size="icon" onClick={() => setVisible((value) => !value)} aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}>{visible ? <EyeOff /> : <Eye />}</Button></div></FormField><div className="form-between"><label><Checkbox />Recuérdame</label><Link to="/recuperar-contrasena">¿Has olvidado la contraseña?</Link></div><Button type="submit" size="lg">Acceder</Button><p className="auth-switch">¿No tienes cuenta? <Link to="/registro">Crear cuenta</Link></p></form></AuthShell>
}

export function RecoverPasswordPage() {
  const [sent, setSent] = useState(false)
  return <AuthShell title="Recupera tu contraseña" description="Te enviaremos un enlace seguro para crear una nueva.">{sent ? <><Alert><Mail /><AlertTitle>Correo enviado</AlertTitle><AlertDescription>Si existe una cuenta con ese email, recibirás el enlace en unos minutos.</AlertDescription></Alert><Button asChild variant="outline" className="w-full"><Link to="/acceso">Volver al acceso</Link></Button></> : <form className="auth-form" onSubmit={(event) => { event.preventDefault(); setSent(true) }}><FormField label="Email de tu cuenta" htmlFor="recover-email"><Input id="recover-email" type="email" required autoComplete="email" /></FormField><Button size="lg"><Mail data-icon="inline-start" />Enviar enlace</Button><p className="auth-switch"><Link to="/acceso">Volver al acceso</Link></p></form>}</AuthShell>
}

export function ResetPasswordPage() {
  const [done, setDone] = useState(false)
  return <AuthShell title={done ? 'Contraseña actualizada' : 'Crea una nueva contraseña'} description={done ? 'Ya puedes acceder con tu nueva contraseña.' : 'Usa al menos 8 caracteres y evita datos fáciles de adivinar.'}>{done ? <><Alert><CheckCircle2 /><AlertTitle>Todo listo</AlertTitle><AlertDescription>El cambio se ha guardado correctamente.</AlertDescription></Alert><Button asChild className="w-full"><Link to="/acceso">Acceder</Link></Button></> : <form className="auth-form" onSubmit={(event) => { event.preventDefault(); setDone(true) }}><FormField label="Nueva contraseña" htmlFor="reset-password"><Input id="reset-password" type="password" minLength={8} required /></FormField><FormField label="Repite la contraseña" htmlFor="reset-confirm"><Input id="reset-confirm" type="password" minLength={8} required /></FormField><Button size="lg"><KeyRound data-icon="inline-start" />Guardar contraseña</Button></form>}</AuthShell>
}
