import { useEffect, useState, type FormEvent } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import {
  cancelAdvertisement, createAdCheckout, createAdvertisement, getAdQuote,
  getAdvertisement, getMyAdvertisements, getAdvertisingAvailability, updateAdvertisement, uploadAdvertisementImage,
  type AdvertisementDetail, type AdvertisementWrite, type DestinationType,
} from '@/api/commercial-advertisements'
import { AdvertisingVacancy } from '@/components/advertising-vacancy'
import { ApiError } from '@/api/client'
import { CommercialAdvertisementImage } from '@/components/commercial-advertisement-image'
import { useI18n } from '@/contexts/i18n-context'
import { advertisementStatusSource } from '@/lib/commercial-advertisement-labels'
import './commercial-advertisement-pages.css'

const initial: AdvertisementWrite = { title: '', description: '', imageAssetId: '', destinationType: 'website', destination: '', packageId: 'homepage_1d' }

export function AdvertisementEditorPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { t } = useI18n()
  const [form, setForm] = useState<AdvertisementWrite>(initial)
  const [existing, setExisting] = useState<AdvertisementDetail | null>(null)
  const [preview, setPreview] = useState(false)
  const [filePreview, setFilePreview] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [full, setFull] = useState(false)
  const [availabilityLoading, setAvailabilityLoading] = useState(!id)
  useEffect(() => {
    if (id) return
    let active = true
    void getAdvertisingAvailability().then((status) => { if (active) setFull(status.available === 0) })
      .catch(() => { if (active) setError('No se pudo comprobar la disponibilidad. Inténtalo de nuevo.') })
      .finally(() => { if (active) setAvailabilityLoading(false) })
    return () => { active = false }
  }, [id])
  useEffect(() => {
    if (!id) return
    void getAdvertisement(id).then((ad) => {
      setExisting(ad)
      setForm({ title: ad.title, description: ad.description, imageAssetId: ad.imageAssetId, destinationType: ad.destinationType, destination: ad.destination, packageId: 'homepage_1d' })
    }).catch((reason: Error) => setError(reason.message))
  }, [id])
  useEffect(() => () => { if (filePreview) URL.revokeObjectURL(filePreview) }, [filePreview])
  const imagePath = existing && form.imageAssetId === existing.imageAssetId ? existing.imageUrl : `/api/v1/media/${form.imageAssetId}?variant=card`
  const chooseFile = async (file?: File) => {
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { setError('Solo se admiten imágenes JPEG, PNG o WebP.'); return }
    setBusy(true); setError(''); setFieldErrors({})
    try {
      const asset = await uploadAdvertisementImage(file)
      setForm((previous) => ({ ...previous, imageAssetId: asset.id }))
      setFilePreview(URL.createObjectURL(file))
    } catch (reason) { setError((reason as Error).message); if (reason instanceof ApiError) setFieldErrors(reason.fieldErrors) } finally { setBusy(false) }
  }
  const save = async () => {
    setBusy(true); setError(''); setFieldErrors({})
    try {
      const ad = id ? await updateAdvertisement(id, form) : await createAdvertisement(form)
      navigate(ad.status === 'pending_payment' ? `/publicidad/${ad.id}/checkout` : '/mis-campanas', { replace: true })
    } catch (reason) { if (reason instanceof ApiError && reason.message === 'No advertising slots available') { setFull(true); setPreview(false) } else { setError((reason as Error).message); if (reason instanceof ApiError) setFieldErrors(reason.fieldErrors) } } finally { setBusy(false) }
  }
  const submit = (event: FormEvent) => { event.preventDefault(); setError(''); setPreview(true) }
  return <div className="ad-flow"><Link to="/mis-campanas" className="ad-flow__back"><ArrowLeft />{t('Mis campañas')}</Link><div className="ad-flow__heading"><span>{t('Publicidad comercial')}</span><h1>{t(id ? 'Editar publicidad' : 'Crear publicidad')}</h1><p>{t('Tu campaña será revisada antes de aparecer en la portada.')}</p></div>
    {error ? <p role="alert" className="ad-flow__error">{t(error)}</p> : null}
    {full ? <section className="ad-flow__panel"><AdvertisingVacancy onAvailable={() => setFull(false)} /></section> : availabilityLoading ? <p role="status">{t('Comprobando disponibilidad…')}</p> : preview ? <section className="ad-flow__panel" aria-label={t('Vista previa')}><h2>{t('Vista previa')}</h2><div className="ad-flow__preview">{filePreview ? <img data-i18n-exempt src={filePreview} alt={form.title} /> : form.imageAssetId ? <CommercialAdvertisementImage path={imagePath} title={form.title} /> : null}<div><small>{t('Publicidad')}</small><h3 data-i18n-exempt>{form.title}</h3><p data-i18n-exempt>{form.description}</p><span>{form.destination}</span></div></div><div className="ad-flow__actions"><button type="button" className="ad-flow__secondary" onClick={() => setPreview(false)}>{t('Volver a editar')}</button><button type="button" disabled={busy} onClick={() => { void save() }}>{t(existing?.paymentStatus === 'paid' && existing.status !== 'expired' ? 'Enviar a revisión' : 'Continuar al pago')}</button></div></section> : <form className="ad-flow__panel ad-flow__form" onSubmit={submit}>
      <label>{t('Imagen publicitaria')}<input type="file" accept="image/jpeg,image/png,image/webp" required={!form.imageAssetId} disabled={busy} aria-invalid={Boolean(fieldErrors.imageAssetId)} aria-describedby={fieldErrors.imageAssetId ? 'ad-image-error' : undefined} onChange={(event) => { void chooseFile(event.target.files?.[0]) }} />{fieldErrors.imageAssetId ? <small id="ad-image-error">{t(fieldErrors.imageAssetId)}</small> : null}</label>
      {filePreview ? <img className="ad-flow__uploaded" src={filePreview} alt={t('Vista previa de la imagen')} /> : existing ? <CommercialAdvertisementImage path={existing.imageUrl} title={existing.title} /> : null}
      <label>{t('Título')}<input value={form.title} maxLength={90} minLength={3} required aria-invalid={Boolean(fieldErrors.title)} aria-describedby={fieldErrors.title ? 'ad-title-error' : undefined} onChange={(event) => setForm((previous) => ({ ...previous, title: event.target.value }))} />{fieldErrors.title ? <small id="ad-title-error">{t(fieldErrors.title)}</small> : null}</label>
      <label>{t('Descripción')}<textarea value={form.description} maxLength={300} minLength={10} required rows={4} aria-invalid={Boolean(fieldErrors.description)} aria-describedby={fieldErrors.description ? 'ad-description-error' : undefined} onChange={(event) => setForm((previous) => ({ ...previous, description: event.target.value }))} />{fieldErrors.description ? <small id="ad-description-error">{t(fieldErrors.description)}</small> : null}</label>
      <label>{t('Tipo de contacto')}<select value={form.destinationType} onChange={(event) => setForm((previous) => ({ ...previous, destinationType: event.target.value as DestinationType, destination: '' }))}><option value="website">{t('Sitio web')}</option><option value="whatsapp">WhatsApp</option><option value="phone">{t('Teléfono')}</option><option value="email">Email</option></select></label>
      <label>{t(form.destinationType === 'website' ? 'Enlace web' : form.destinationType === 'email' ? 'Correo electrónico' : 'Número de teléfono')}<input value={form.destination} type={form.destinationType === 'email' ? 'email' : form.destinationType === 'website' ? 'url' : 'tel'} required placeholder={form.destinationType === 'website' ? 'https://ejemplo.es' : undefined} aria-invalid={Boolean(fieldErrors.destination)} aria-describedby={fieldErrors.destination ? 'ad-destination-error' : undefined} onChange={(event) => setForm((previous) => ({ ...previous, destination: event.target.value }))} />{fieldErrors.destination ? <small id="ad-destination-error">{t(fieldErrors.destination)}</small> : null}</label>
      <p className="ad-flow__notice">{t('Publicidad · 1 día · 1 €. El plazo empieza cuando se aprueba tu campaña.')}</p><button type="submit" disabled={busy || !form.imageAssetId}>{t('Vista previa')}</button>
    </form>}
  </div>
}

export function AdvertisementCheckoutPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const { t } = useI18n()
  const paymentReturn = searchParams.get('payment') === 'return'
  const [ad, setAd] = useState<AdvertisementDetail | null>(null)
  const [quote, setQuote] = useState<{ days: number; amountCents: number; currency: string } | null>(null)
  const [full, setFull] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!id) return
    void getAdvertisement(id).then((item) => {
      setAd(item)
      if (item.status === 'pending_payment' && !paymentReturn) void getAdQuote(id).then((price) => { setQuote(price); setFull(!price.available) }).catch((reason: Error) => setError(reason.message))
    }).catch((reason: Error) => setError(reason.message))
    if (paymentReturn) {
      const timer = window.setInterval(() => { void getAdvertisement(id).then(setAd).catch(() => undefined) }, 3000)
      const stop = window.setTimeout(() => window.clearInterval(timer), 30000)
      return () => { window.clearInterval(timer); window.clearTimeout(stop) }
    }
  }, [id, paymentReturn])
  const pay = async () => {
    if (!id) return
    setBusy(true); setError('')
    try { const checkout = await createAdCheckout(id); window.location.assign(checkout.url) }
    catch (reason) {
      if (reason instanceof ApiError && reason.message === 'No advertising slots available') setFull(true)
      else setError((reason as Error).message)
      setBusy(false)
    }
  }
  return <div className="ad-flow"><Link to="/mis-campanas" className="ad-flow__back"><ArrowLeft />{t('Mis campañas')}</Link><div className="ad-flow__heading"><span>{t('Pago')}</span><h1>{t('Confirmar publicidad')}</h1></div>{error ? <p role="alert" className="ad-flow__error">{t(error)}</p> : null}{ad ? <section className="ad-flow__panel"><div className="ad-flow__preview"><CommercialAdvertisementImage path={ad.imageUrl} title={ad.title} /><div><small>{t('Publicidad')}</small><h2 data-i18n-exempt>{ad.title}</h2><p data-i18n-exempt>{ad.description}</p></div></div><p>{t(quote?.days === 30 || ad.packageId === 'test_homepage_30d' ? 'Publicidad · 30 días' : 'Publicidad · 1 día · 1 €')}</p>{quote?.days === 30 ? <p>{new Intl.NumberFormat('es-ES', { style: 'currency', currency: quote.currency }).format(quote.amountCents / 100)}</p> : null}<p>{t('El plazo empieza cuando se aprueba tu campaña.')}</p>{ad.status === 'pending_payment' && paymentReturn ? <p role="status">{t('Estamos confirmando el pago. Puedes consultar tus campañas en unos segundos.')}</p> : ad.status === 'pending_payment' ? <><button type="button" disabled={busy || !quote || full} onClick={() => void pay()}>{t('Pagar con Stripe')}</button>{full ? <AdvertisingVacancy /> : null}</> : <p role="status">{t(ad.paymentStatus === 'paid' && ad.status === 'pending_review' ? 'Pago confirmado · pendiente de revisión' : advertisementStatusSource(ad.status))}</p>}</section> : null}</div>
}

export function MyAdvertisementPage() {
  const { t, locale } = useI18n()
  const [items, setItems] = useState<AdvertisementDetail[]>([])
  const [error, setError] = useState('')
  const reload = () => void getMyAdvertisements().then(setItems).catch((reason: Error) => setError(reason.message))
  useEffect(reload, [])
  const cancel = async (id: string) => { try { await cancelAdvertisement(id); reload() } catch (reason) { setError((reason as Error).message) } }
  return <div className="ad-flow"><div className="ad-flow__heading"><span>{t('Publicidad comercial')}</span><h1>{t('Mis campañas')}</h1><p>{t('Gestiona tus anuncios publicitarios por separado de tus viviendas.')}</p></div><Link className="ad-flow__button" to="/publicidad/nueva">{t('Crear publicidad')}</Link>{error ? <p role="alert" className="ad-flow__error">{t(error)}</p> : null}<div className="ad-flow__list">{items.map((ad) => <article key={ad.id} className="ad-flow__panel ad-flow__row"><CommercialAdvertisementImage path={ad.imageUrl} title={ad.title} /><div><h2 data-i18n-exempt>{ad.title}</h2><p data-i18n-exempt>{ad.description}</p><p>{t(advertisementStatusSource(ad.status, ad.endsAt))} · {t(ad.paymentStatus === 'paid' ? 'Pagado' : 'Sin pagar')}</p><small>{new Date(ad.createdAt).toLocaleDateString(locale)} {ad.startsAt ? ` · ${new Date(ad.startsAt).toLocaleDateString(locale)} – ${ad.endsAt ? new Date(ad.endsAt).toLocaleDateString(locale) : '∞'}` : ''}</small>{ad.moderationNote ? <p data-i18n-exempt>{ad.moderationNote}</p> : null}<div className="ad-flow__actions">{ad.status !== 'cancelled' ? <Link to={`/publicidad/${ad.id}/editar`}>{t('Editar')}</Link> : null}{ad.status === 'pending_payment' ? <Link to={`/publicidad/${ad.id}/checkout`}>{t('Pagar')}</Link> : null}{ad.status !== 'cancelled' ? <button type="button" className="ad-flow__secondary" onClick={() => { void cancel(ad.id) }}>{t('Cancelar')}</button> : null}</div></div></article>)}</div>{!items.length && !error ? <p>{t('Todavía no tienes campañas publicitarias.')}</p> : null}</div>
}
