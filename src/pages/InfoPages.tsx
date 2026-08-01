import { useState, type FormEvent } from 'react'
import { ArrowRight, CheckCircle2, Cookie, FileText, HelpCircle, Mail, MessageCircle, Search, Shield, Upload } from 'lucide-react'
import { Link, useLocation } from 'react-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { FormField } from '@/components/forms'

type PageContent = {
  eyebrow: string
  title: string
  intro: string
  icon: typeof Search
  sections: { title: string; text: string; bullets?: string[] }[]
}

const privacyEmail = 'tf.shuler@gmail.com'

const pages: Record<string, PageContent> = {
  '/sobre-nosotros': {
    eyebrow: 'Sobre 112233.es',
    title: 'Una plataforma hecha solo para habitaciones.',
    intro: 'Nacimos en Tenerife para ordenar un mercado disperso y hacer visibles las condiciones que suelen aparecer demasiado tarde.',
    icon: MessageCircle,
    sections: [
      { title: 'Nuestro propósito', text: 'Reducir conversaciones incompatibles y ayudar a que inquilinos y anunciantes tomen decisiones con mejor información.' },
      {
        title: 'Qué hacemos diferente',
        text: 'Estructuramos precio, gastos, fianza, disponibilidad y convivencia desde el primer vistazo.',
        bullets: ['Solo habitaciones y estudios compactos', 'Ubicación aproximada por privacidad', 'Contacto directo y condiciones confirmadas'],
      },
      { title: 'Ámbito actual', text: 'La experiencia se centra inicialmente en Tenerife y está preparada para ampliarse a otras islas y ciudades.' },
    ],
  },
  '/como-funciona': {
    eyebrow: 'Guía rápida',
    title: 'De la búsqueda al primer mensaje.',
    intro: 'Tres pasos claros para encontrar una habitación compatible o publicar la que tienes libre.',
    icon: Search,
    sections: [
      { title: '1. Busca y filtra', text: 'Elige zona, presupuesto, fecha y condiciones de convivencia.' },
      { title: '2. Compara con contexto', text: 'Revisa gastos, fianza, disponibilidad, vivienda y perfil del anunciante.' },
      { title: '3. Contacta', text: 'Confirma que cumples las condiciones y usa únicamente los canales habilitados por el anunciante.' },
    ],
  },
  '/ayuda': {
    eyebrow: 'Centro de ayuda',
    title: 'Respuestas para avanzar sin atascarte.',
    intro: 'Encuentra ayuda sobre búsquedas, contactos, anuncios, seguridad y cuenta.',
    icon: HelpCircle,
    sections: [
      { title: 'Buscar habitación', text: 'Usa filtros de precio, zona, disponibilidad y convivencia. Puedes guardar resultados como favoritos.' },
      { title: 'Contactar con un anuncio', text: 'Antes de escribir, confirma que cumples las condiciones principales. Nunca envíes dinero sin verificar la vivienda y las condiciones.' },
      { title: 'Publicar y moderar', text: 'Para publicar se confirma el email mediante un código de seis dígitos. Los anuncios pueden pasar por revisión y su estado aparece en Mis anuncios.' },
      { title: 'Problemas y denuncias', text: 'Usa “Denunciar anuncio” para informar de datos incorrectos, fraude o contenido prohibido.' },
    ],
  },
  '/terminos': {
    eyebrow: 'Legal',
    title: 'Términos de uso',
    intro: 'Condiciones generales para buscar, publicar y contactar a través de 112233.es.',
    icon: FileText,
    sections: [
      { title: 'Naturaleza del servicio', text: '112233.es facilita la publicación, búsqueda y contacto entre personas interesadas en habitaciones o estudios. No forma parte del contrato de alquiler ni garantiza identidad, solvencia o disponibilidad.' },
      { title: 'Responsabilidad al publicar', text: 'Quien publica debe disponer de autorización y mantener correctos el precio, fotografías, gastos, disponibilidad y condiciones. No se permiten duplicados, fraude, contenido ilícito ni direcciones exactas visibles.' },
      { title: 'Moderación y seguridad', text: 'Podemos revisar, rechazar, ocultar o retirar contenido y limitar cuentas ante fraude, abuso, incumplimiento, riesgo para terceros o requerimiento legal.' },
      { title: 'Pagos y acuerdos', text: 'Verifica la vivienda, la identidad y las condiciones antes de enviar dinero o documentación sensible. La plataforma no custodia depósitos ni responde por acuerdos privados fuera del servicio.' },
      { title: 'Contacto', text: `Las consultas sobre estas condiciones pueden enviarse a ${privacyEmail}. La versión completa y directamente accesible está disponible en /terminos.` },
    ],
  },
  '/privacidad': {
    eyebrow: 'Legal',
    title: 'Política de privacidad',
    intro: 'Cómo utiliza 112233.es los datos necesarios para operar cuentas, anuncios, mapas, mensajes y seguridad.',
    icon: Shield,
    sections: [
      { title: 'Datos tratados', text: 'Podemos tratar nombre, email, contraseña cifrada, rol, avatar, preferencias, sesiones, identificador técnico de Google, anuncios, fotografías, mensajes, favoritos, búsquedas guardadas y registros de seguridad.' },
      { title: 'Finalidades', text: 'Los datos se usan para autenticar cuentas, publicar y gestionar anuncios, mostrar resultados y mapas, facilitar contactos solicitados, recuperar contraseñas y prevenir abuso o fraude.' },
      { title: 'Proveedores técnicos', text: 'La infraestructura utiliza PostgreSQL/PostGIS, Redis y MinIO. Google Identity Services y Google Maps prestan autenticación y mapas. Gmail SMTP envía códigos y avisos transaccionales.' },
      { title: 'Ubicación', text: 'La vista pública utiliza una posición aproximada. La dirección exacta, cuando se facilita para gestionar un anuncio, no debe mostrarse públicamente.' },
      { title: 'Conservación y derechos', text: `Los datos se conservan mientras la cuenta o el anuncio estén activos y durante los periodos técnicos o legales necesarios. Puede solicitar acceso, rectificación o eliminación escribiendo desde el email asociado a ${privacyEmail}.` },
      { title: 'Versión completa', text: 'La política completa y directamente accesible para usuarios y verificadores está disponible en /privacidad.' },
    ],
  },
  '/cookies': {
    eyebrow: 'Legal',
    title: 'Política de cookies',
    intro: 'Información sobre cookies y almacenamiento local utilizados por 112233.es.',
    icon: Cookie,
    sections: [
      { title: 'Necesarias', text: 'Mantienen la sesión, protegen la autenticación y permiten que las funciones esenciales respondan correctamente.' },
      { title: 'Almacenamiento local', text: 'Puede conservar preferencias de interfaz, favoritos y borradores del editor en el dispositivo utilizado.' },
      { title: 'Servicios externos', text: 'Google Identity Services y Google Maps pueden usar mecanismos técnicos propios conforme a sus políticas para prestar autenticación y mapas.' },
      { title: 'Control', text: 'Puede eliminar cookies y almacenamiento local desde el navegador. Al hacerlo se cerrará la sesión y pueden perderse preferencias o borradores guardados solo en ese dispositivo.' },
    ],
  },
  '/normas-de-publicacion': {
    eyebrow: 'Calidad y convivencia',
    title: 'Normas de publicación',
    intro: 'Anuncios claros, actuales y respetuosos generan mejores contactos.',
    icon: Upload,
    sections: [
      { title: 'Información obligatoria', text: 'Precio, gastos, fianza, disponibilidad, estancia mínima, tipo de habitación y condiciones.' },
      { title: 'Fotografías', text: 'Deben mostrar la habitación ofrecida y no incluir marcas de agua, datos personales ni imágenes engañosas.' },
      { title: 'Contenido no permitido', text: 'Fraude, duplicados, contenido sexual, direcciones públicas, suplantación y criterios discriminatorios contrarios a la normativa aplicable.' },
      { title: 'Actualización', text: 'Oculta o finaliza el anuncio cuando la habitación deje de estar disponible.' },
    ],
  },
}

export function ContactPage() {
  const [sent, setSent] = useState(false)
  const submit = (event: FormEvent) => {
    event.preventDefault()
    setSent(true)
  }

  return (
    <div className="info-page container">
      <header className="info-hero">
        <span className="eyebrow">Contacto</span>
        <h1>¿En qué podemos ayudarte?</h1>
        <p>Cuéntanos el problema con suficiente detalle. Respondemos en horario de Canarias.</p>
      </header>
      <div className="contact-layout">
        <div className="contact-options" tabIndex={0} role="region" aria-label="Canales de contacto">
          <div>
            <Mail />
            <h2>Email</h2>
            <p>{privacyEmail}</p>
            <span>Incluye la referencia del anuncio cuando corresponda</span>
          </div>
          <div>
            <MessageCircle />
            <h2>Ayuda con anuncios</h2>
            <p>No envíes documentación sensible</p>
            <span>Describe el problema y los pasos para reproducirlo</span>
          </div>
        </div>
        {sent ? (
          <Alert>
            <CheckCircle2 />
            <AlertTitle>Consulta preparada</AlertTitle>
            <AlertDescription>Para garantizar la entrega, envía también el mensaje a {privacyEmail}.</AlertDescription>
          </Alert>
        ) : (
          <form className="contact-form" onSubmit={submit}>
            <div className="form-grid">
              <FormField label="Nombre" htmlFor="contact-name"><Input id="contact-name" required /></FormField>
              <FormField label="Email" htmlFor="contact-email"><Input id="contact-email" type="email" required /></FormField>
            </div>
            <FormField label="Motivo" htmlFor="contact-reason">
              <select id="contact-reason">
                <option>Duda sobre una habitación</option>
                <option>Problema con mi anuncio</option>
                <option>Seguridad o fraude</option>
                <option>Cuenta y acceso</option>
                <option>Otro</option>
              </select>
            </FormField>
            <FormField label="Mensaje" htmlFor="contact-message"><Textarea id="contact-message" rows={7} required /></FormField>
            <Button size="lg">Preparar consulta</Button>
          </form>
        )}
      </div>
    </div>
  )
}

export function InfoPage() {
  const { pathname } = useLocation()
  if (pathname === '/contacto') return <ContactPage />
  const content = pages[pathname] ?? pages['/sobre-nosotros']
  const Icon = content.icon

  return (
    <div className="info-page container">
      <header className="info-hero">
        <div className="info-icon"><Icon /></div>
        <span className="eyebrow">{content.eyebrow}</span>
        <h1>{content.title}</h1>
        <p>{content.intro}</p>
      </header>
      <div className="info-layout">
        <aside>
          <nav aria-label="En esta sección">
            {Object.entries(pages).map(([path, page]) => (
              <Link key={path} to={path} aria-current={pathname === path ? 'page' : undefined}>{page.title}</Link>
            ))}
          </nav>
        </aside>
        <article>
          {content.sections.map((section) => (
            <section key={section.title}>
              <h2>{section.title}</h2>
              <p>{section.text}</p>
              {section.bullets ? (
                <ul>{section.bullets.map((bullet) => <li key={bullet}><CheckCircle2 />{bullet}</li>)}</ul>
              ) : null}
            </section>
          ))}
          <div className="info-cta">
            <h2>¿Necesitas una respuesta concreta?</h2>
            <p>El centro de ayuda reúne preguntas habituales y nuestro equipo puede revisar casos específicos.</p>
            <div>
              <Button asChild><Link to="/ayuda">Ir a ayuda <ArrowRight data-icon="inline-end" /></Link></Button>
              <Button asChild variant="outline"><Link to="/contacto">Contactar</Link></Button>
            </div>
          </div>
        </article>
      </div>
    </div>
  )
}
