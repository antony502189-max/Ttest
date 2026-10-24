import { useEffect, useState, type FormEvent } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import {
  cancelAdvertisement, createAdCheckout, createAdvertisement, createAdminAdvertisement, getAdQuote, getAdPaymentStatus, cancelAdCheckout,
  getAdvertisement, getMyAdvertisements, getAdvertisingAvailability, updateAdvertisement, uploadAdvertisementImage,
  type AdvertisementDetail, type AdvertisementWrite, type DestinationType,
} from '@/api/commercial-advertisements'
import { AdvertisingVacancy } from '@/components/advertising-vacancy'
import { ApiError } from '@/api/client'
import { CommercialAdvertisementImage } from '@/components/commercial-advertisement-image'
import { useI18n } from '@/contexts/i18n-context'
import { advertisementPaymentSource, advertisementStatusSource } from '@/lib/commercial-advertisement-labels'
import './commercial-advertisement-pages.css'

const MAX_AD_IMAGE_BYTES = 8 * 1024 * 1024
const initial: AdvertisementWrite = { title: '', description: '', imageAssetId: '', destinationType: 'website', destination: '', packageId: 'homepage_1d' }

export function AdvertisementEditorPage() {
  const { id } = useParams()
  const [editorParams] = useSearchParams()
  const complimentary = !id && editorParams.get('admin') === '1'
  const requestedPackage = editorParams.get('plan') === 'premium' ? 'homepage_premium_1m' : 'homepage_1d'
  const navigate = useNavigate()
  const { t, locale } = useI18n()
  const [form, setForm] = useState<AdvertisementWrite>(() => ({ ...initial, packageId: requestedPackage }))
  const [advertisingPrice, setAdvertisingPrice] = useState<number | null>(null)
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
    setForm((current) => ({ ...current, packageId: requestedPackage }))
    let active = true
    setAvailabilityLoading(true)
    setAdvertisingPrice(null)
    void getAdvertisingAvailability().then((status) => {
      if (!active) return
      const premium = requestedPackage === 'homepage_premium_1m'
      const price = premium ? status.premiumMonthlyPriceCents : status.monthlyPriceCents
      const available = premium ? status.premiumAvailable : status.available
      const verified = status.currency === 'EUR' && status.months === 1 && Number.isSafeInteger(price) && (price ?? 0) > 0
      setAdvertisingPrice(verified ? price! : null)
      setFull(available === 0 || !verified)
    })
      .catch(() => { if (active) setError('No se pudo comprobar la disponibilidad. Inténtalo de nuevo.') })
      .finally(() => { if (active) setAvailabilityLoading(false) })
    return () => { active = false }
  }, [id, requestedPackage])
  useEffect(() => {
    if (!id) return
    void getAdvertisement(id).then((ad) => {
      setExisting(ad)
      setForm({ title: ad.title, description: ad.description, imageAssetId: ad.imageAssetId, destinationType: ad.destinationType, destination: ad.destination, packageId: ad.packageId === 'homepage_premium_1m' ? 'homepage_premium_1m' : 'homepage_1d' })
    }).catch((reason: Error) => setError(reason.message))
  }, [id])
  useEffect(() => () => { if (filePreview) URL.revokeObjectURL(filePreview) }, [filePreview])
  const imagePath = existing && form.imageAssetId === existing.imageAssetId ? existing.imageUrl : `/api/v1/media/${form.imageAssetId}?variant=card`
  const selectedPlacement = form.packageId === 'homepage_premium_1m' ? t('Banner Premium Principal') : t('Espacio publicitario')
  const verifiedPriceLabel = advertisingPrice !== null
    ? new Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(advertisingPrice / 100)
    : null
  const chooseFile = async (file?: File) => {
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { setError('Solo se admiten imágenes JPEG, PNG o WebP.'); return }
    if (file.size > MAX_AD_IMAGE_BYTES) { setError('La imagen supera el límite de 8 MB. Elige un archivo más pequeño.'); return }
    setBusy(true); setError(''); setFieldErrors({})
    try {
      const asset = await uploadAdvertisementImage(file)
      setForm((previous) => ({ ...previous, imageAssetId: asset.id }))
      setFilePreview(URL.createObjectURL(file))
    } catch (reason) {
      setError(reason instanceof ApiError && reason.status === 413
        ? 'La imagen supera el límite de 8 MB. Elige un archivo más pequeño.'
        : (reason as Error).message)
      if (reason instanceof ApiError) setFieldErrors(reason.fieldErrors)
    } finally { setBusy(false) }
  }
  const save = async () => {
    setBusy(true); setError(''); setFieldErrors({})
    try {
      const ad = id ? await updateAdvertisement(id, form) : complimentary ? await createAdminAdvertisement(form) : await createAdvertisement(form)
      navigate(ad.status === 'pending_payment' ? `/publicidad/${ad.id}/checkout` : '/mis-campanas', { replace: true })
    } catch (reason) { if (reason instanceof ApiError && reason.message === 'No advertising slots available') { setFull(true); setPreview(false) } else { setError((reason as Error).message); if (reason instanceof ApiError) setFieldErrors(reason.fieldErrors) } } finally { setBusy(false) }
  }
  const submit = (event: FormEvent) => { event.preventDefault(); setError(''); setPreview(true) }
  return <div className="ad-flow"><Link to="/mis-campanas" className="ad-flow__back"><ArrowLeft />{t('Mis campañas')}</Link><div className="ad-flow__heading"><span>{t('Publicidad comercial')}</span><h1>{t(id ? 'Editar publicidad' : 'Crear publicidad')}</h1><p>{t(complimentary ? 'Publica un banner durante un mes sin pago como administrador.' : 'Tu campaña será revisada antes de aparecer en la portada.')}</p></div>
    {!id && !complimentary ? <div className="ad-flow__selected-package" data-testid="advertising-editor-package">
      <strong>{selectedPlacement}</strong><span>{verifiedPriceLabel ? `${verifiedPriceLabel} / ${t('1 mes')}` : t('Comprobando disponibilidad…')}</span>
    </div> : null}
    {error ? <p role="alert" className="ad-flow__error">{t(error)}</p> : null}
    {full ? <section className="ad-flow__panel"><AdvertisingVacancy onAvailable={() => setFull(false)} /></section> : availabilityLoading ? <p role="status">{t('Comprobando disponibilidad…')}</p> : preview ? <section className="ad-flow__panel" aria-label={t('Vista previa')}><h2>{t('Vista previa')}</h2><div className="ad-flow__preview">{filePreview ? <img data-i18n-exempt src={filePreview} alt={form.title} /> : form.imageAssetId ? <CommercialAdvertisementImage path={imagePath} title={form.title} /> : null}<div><small>{t('Publicidad')}</small><h3 data-i18n-exempt>{form.title}</h3><p data-i18n-exempt>{form.description}</p><span>{form.destination}</span></div></div><div className="ad-flow__actions"><button type="button" className="ad-flow__secondary" onClick={() => setPreview(false)}>{t('Volver a editar')}</button><button type="button" disabled={busy} onClick={() => { void save() }}>{t(complimentary ? 'Publicar banner sin coste' : ['paid', 'waived'].includes(existing?.paymentStatus ?? '') && existing?.status !== 'expired' ? 'Enviar a revisión' : 'Continuar al pago')}</button></div></section> : <form className="ad-flow__panel ad-flow__form" onSubmit={submit}>
      <label>{t('Imagen publicitaria')}<input type="file" accept="image/jpeg,image/png,image/webp" required={!form.imageAssetId} disabled={busy} aria-invalid={Boolean(fieldErrors.imageAssetId)} aria-describedby={fieldErrors.imageAssetId ? 'ad-image-error' : undefined} onChange={(event) => { void chooseFile(event.target.files?.[0]) }} />{fieldErrors.imageAssetId ? <small id="ad-image-error">{t(fieldErrors.imageAssetId)}</small> : null}</label>
      {filePreview ? <img className="ad-flow__uploaded" src={filePreview} alt={t('Vista previa de la imagen')} /> : existing ? <CommercialAdvertisementImage path={existing.imageUrl} title={existing.title} /> : null}
      <label>{t('Título')}<input value={form.title} maxLength={90} minLength={3} required aria-invalid={Boolean(fieldErrors.title)} aria-describedby={fieldErrors.title ? 'ad-title-error' : undefined} onChange={(event) => setForm((previous) => ({ ...previous, title: event.target.value }))} />{fieldErrors.title ? <small id="ad-title-error">{t(fieldErrors.title)}</small> : null}</label>
      <label>{t('Descripción')}<textarea value={form.description} maxLength={300} minLength={10} required rows={4} aria-invalid={Boolean(fieldErrors.description)} aria-describedby={fieldErrors.description ? 'ad-description-error' : undefined} onChange={(event) => setForm((previous) => ({ ...previous, description: event.target.value }))} />{fieldErrors.description ? <small id="ad-description-error">{t(fieldErrors.description)}</small> : null}</label>
      <label>{t('Tipo de contacto')}<select value={form.destinationType} onChange={(event) => setForm((previous) => ({ ...previous, destinationType: event.target.value as DestinationType, destination: '' }))}><option value="website">{t('Sitio web')}</option><option value="whatsapp">WhatsApp</option><option value="phone">{t('Teléfono')}</option><option value="email">Email</option></select></label>
      <label>{t(form.destinationType === 'website' ? 'Enlace web' : form.destinationType === 'email' ? 'Correo electrónico' : 'Número de teléfono')}<input value={form.destination} type={form.destinationType === 'email' ? 'email' : form.destinationType === 'website' ? 'url' : 'tel'} required placeholder={form.destinationType === 'website' ? 'https://ejemplo.es' : undefined} aria-invalid={Boolean(fieldErrors.destination)} aria-describedby={fieldErrors.destination ? 'ad-destination-error' : undefined} onChange={(event) => setForm((previous) => ({ ...previous, destination: event.target.value }))} />{fieldErrors.destination ? <small id="ad-destination-error">{t(fieldErrors.destination)}</small> : null}</label>
      <p className="ad-flow__notice">{t('El plazo empieza cuando se aprueba tu campaña.')}</p><button type="submit" disabled={busy || !form.imageAssetId}>{t('Vista previa')}</button>
    </form>}
  </div>
}

export function AdvertisementCheckoutPage() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const { t, locale } = useI18n()
  const paymentReturn = searchParams.get('payment') === 'return'
  const paymentCancelled = searchParams.get('payment') === 'cancelled'
  const [ad, setAd] = useState<AdvertisementDetail | null>(null)
  const [quote, setQuote] = useState<{ days: number; months?: number; amountCents: number; currency: string } | null>(null)
  useEffect(() => {
    if (!id) { setQuote(null); return }
    let active = true
    setQuote(null)
    void getAdQuote(id).then((price) => { if (active) { setQuote(price); setFull(!price.available) } })
      .catch((reason: Error) => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [id])
  const [full, setFull] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [reviewRequired, setReviewRequired] = useState(false)
  const [cancelled, setCancelled] = useState(false)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    if (!id) return
    let active = true
    let timer: number | undefined
    setAd(null); setQuote(null); setError(''); setReviewRequired(false); setCancelled(false)
    const load = async () => {
      if (paymentReturn) {
        const status = await getAdPaymentStatus(id)
        if (!active) return
        setReviewRequired(status.fulfillmentStatus === 'review_required')
        setFailed(status.orderStatus === 'failed')
        if (['paid', 'expired', 'failed'].includes(status.orderStatus ?? '')) window.clearInterval(timer)
      }
      const item = await getAdvertisement(id)
      if (!active) return
      setAd(item)
      if (item.paymentStatus === 'paid') setError('')
      if (item.paymentReviewRequired) setReviewRequired(true)
    }
    const initialize = async () => {
      if (paymentCancelled) {
        const result = await cancelAdCheckout(id)
        if (active) setCancelled(result.cancelled)
      }
      await load()
    }
    void initialize().catch((reason: Error) => { if (active) setError(reason.message) })
    if (paymentReturn) timer = window.setInterval(() => void load().catch((reason: Error) => { if (active) setError(reason.message) }), 3000)
    const stop = window.setTimeout(() => window.clearInterval(timer), 180000)
    return () => { active = false; window.clearInterval(timer); window.clearTimeout(stop) }
  }, [id, paymentReturn, paymentCancelled])
  const refresh = async () => {
    if (!id) return
    const status = await getAdPaymentStatus(id)
    if (status.paymentStatus === 'paid') setError('')
    setReviewRequired(status.fulfillmentStatus === 'review_required')
    setAd(await getAdvertisement(id))
  }
  const pay = async () => {
    if (!id) return
    setBusy(true); setError('')
    try { const checkout = await createAdCheckout(id); window.location.assign(checkout.url) }
    catch (reason) {
      if (reason instanceof ApiError && reason.message === 'No advertising slots available') setFull(true)
      else { setError((reason as Error).message); await refresh().catch(() => undefined) }
      setBusy(false)
    }
  }
  const cancel = async () => {
    if (!id) return
    setBusy(true); setError('')
    try { const result = await cancelAdCheckout(id); setCancelled(result.cancelled); await refresh() }
    catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="ad-flow">
    <Link to="/mis-campanas" className="ad-flow__back"><ArrowLeft />{t('Mis campañas')}</Link>
    <div className="ad-flow__heading"><span>{t('Pago')}</span><h1>{t('Confirmar publicidad')}</h1></div>
    {error ? <p role="alert" className="ad-flow__error">{t(error)}</p> : null}
    {ad ? <section className="ad-flow__panel">
      <div className="ad-flow__preview"><CommercialAdvertisementImage path={ad.imageUrl} title={ad.title} /><div><small>{t('Publicidad')}</small><h2 data-i18n-exempt>{ad.title}</h2><p data-i18n-exempt>{ad.description}</p></div></div>
      {ad.status === 'pending_payment' && quote ? <p className="ad-flow__price">{new Intl.NumberFormat(locale, { style: 'currency', currency: quote.currency }).format(quote.amountCents / 100)} · {t('1 mes')}</p> : null}
      <p>{t('El plazo empieza cuando se aprueba tu campaña.')}</p>
      {cancelled ? <p role="status">{t('Pago cancelado. El espacio reservado se ha liberado.')}</p> : null}
      {failed ? <p role="status">{t('Pago fallido. Puedes volver a intentarlo.')}</p> : null}
      {reviewRequired ? <p role="alert">{t('El pago se ha recibido, pero necesita revisión. Contacta con soporte; no vuelvas a pagar.')}</p>
        : ad.status === 'pending_payment' && paymentReturn && !cancelled && !failed ? <><p role="status">{t('Estamos confirmando el pago. Puedes consultar tus campañas en unos segundos.')}</p><button type="button" disabled={busy} onClick={() => void cancel()}>{t('Cancelar pago')}</button></>
        : ad.status === 'pending_payment' ? <><div className="ad-flow__actions"><button type="button" disabled={busy || !quote || full} onClick={() => void pay()}>{t('Pagar con Stripe')}</button><button type="button" disabled={busy} className="ad-flow__secondary" onClick={() => void cancel()}>{t('Cancelar pago')}</button></div>{full ? <AdvertisingVacancy /> : null}</>
        : <p role="status">{t(ad.paymentStatus === 'paid' && ad.status === 'pending_review' ? 'Pago confirmado · pendiente de revisión' : advertisementStatusSource(ad.status))}</p>}
    </section> : <p role="status">{t('Cargando publicidad…')}</p>}
  </div>
}

export function MyAdvertisementPage() {
  const { t, locale } = useI18n()
  const [items, setItems] = useState<AdvertisementDetail[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const reload = () => {
    setLoading(true)
    setError('')
    void getMyAdvertisements()
      .then(setItems)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }
  useEffect(reload, [])
  const cancel = async (id: string) => { try { await cancelAdvertisement(id); reload() } catch (reason) { setError((reason as Error).message) } }
  return <div className="ad-flow"><div className="ad-flow__campaign-heading"><Link to="/" className="ad-flow__back ad-flow__back--home" aria-label={t('Volver al inicio')} title={t('Volver al inicio')}><ArrowLeft aria-hidden="true" /></Link><div className="ad-flow__heading"><span>{t('Publicidad comercial')}</span><h1>{t('Mis campañas')}</h1><p>{t('Gestiona tus anuncios publicitarios por separado de tus viviendas.')}</p></div></div><Link className="ad-flow__button" to="/publicidad/nueva">{t('Crear publicidad')}</Link>{error ? <p role="alert" className="ad-flow__error">{t(error)}</p> : null}<div className="ad-flow__list">{items.map((ad) => <article key={ad.id} className="ad-flow__panel ad-flow__row"><CommercialAdvertisementImage path={ad.imageUrl} title={ad.title} /><div><h2 data-i18n-exempt>{ad.title}</h2><p data-i18n-exempt>{ad.description}</p><p>{t(advertisementStatusSource(ad.status, ad.endsAt))} · {t(ad.paymentReviewRequired ? 'Pago en revisión' : advertisementPaymentSource(ad.paymentStatus))}</p><small>{new Date(ad.createdAt).toLocaleDateString(locale)} {ad.startsAt ? ` · ${new Date(ad.startsAt).toLocaleDateString(locale)} – ${ad.endsAt ? new Date(ad.endsAt).toLocaleDateString(locale) : '∞'}` : ''}</small>{ad.paymentReviewRequired ? <p role="alert">{t('El pago se ha recibido, pero necesita revisión. Contacta con soporte; no vuelvas a pagar.')}</p> : null}{ad.moderationNote ? <p data-i18n-exempt>{ad.moderationNote}</p> : null}<div className="ad-flow__actions">{ad.status !== 'cancelled' ? <Link to={`/publicidad/${ad.id}/editar`}>{t('Editar')}</Link> : null}{ad.status === 'pending_payment' && !ad.paymentReviewRequired ? <Link to={`/publicidad/${ad.id}/checkout`}>{t('Pagar')}</Link> : null}{ad.status !== 'cancelled' ? <button type="button" className="ad-flow__secondary" onClick={() => { void cancel(ad.id) }}>{t('Cancelar')}</button> : null}</div></div></article>)}</div>{loading && !items.length ? <p role="status">{t('Cargando campañas…')}</p> : null}{error ? <button type="button" className="ad-flow__retry" onClick={reload}>{t('Reintentar')}</button> : null}{!loading && !items.length && !error ? <p>{t('Todavía no tienes campañas publicitarias.')}</p> : null}</div>
}
