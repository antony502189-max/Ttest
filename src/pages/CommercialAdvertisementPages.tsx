import { useEffect, useState, type FormEvent } from 'react'
import { ArrowLeft } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router'
import {
  cancelAdvertisement, completeAdTestPayment, createAdCheckout, createAdvertisement,
  getAdvertisement, getMyAdvertisements, updateAdvertisement, uploadAdvertisementImage,
  type AdvertisementDetail, type AdvertisementWrite, type DestinationType,
} from '@/api/commercial-advertisements'
import { ApiError } from '@/api/client'
import { CommercialAdvertisementImage } from '@/components/commercial-advertisement-image'
import { useI18n } from '@/contexts/i18n-context'
import './commercial-advertisement-pages.css'

const initial: AdvertisementWrite = { title: '', description: '', imageAssetId: '', destinationType: 'website', destination: '', packageId: 'test_homepage_30d' }

function statusLabel(value: string, endsAt?: string | null) {
  if (value === 'active' && endsAt && new Date(endsAt).getTime() <= Date.now()) return 'Expirada'
  return ({ pending_payment: 'Pendiente de pago', pending_review: 'Pendiente de revisión', active: 'Activa', expired: 'Expirada', rejected: 'Rechazada', cancelled: 'Cancelada' } as Record<string, string>)[value] ?? value
}

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
  useEffect(() => {
    if (!id) return
    void getAdvertisement(id).then((ad) => {
      setExisting(ad)
      setForm({ title: ad.title, description: ad.description, imageAssetId: ad.imageAssetId, destinationType: ad.destinationType, destination: ad.destination, packageId: 'test_homepage_30d' })
    }).catch((reason: Error) => setError(reason.message))
  }, [id])
  useEffect(() => () => { if (filePreview) URL.revokeObjectURL(filePreview) }, [filePreview])
  const imagePath = existing && form.imageAssetId === existing.imageAssetId ? existing.imageUrl : `/api/v1/media/${form.imageAssetId}?variant=card`
  const chooseFile = async (file?: File) => {
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { setError(t('Solo se admiten imágenes JPEG, PNG o WebP.')); return }
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
    } catch (reason) { setError((reason as Error).message); if (reason instanceof ApiError) setFieldErrors(reason.fieldErrors) } finally { setBusy(false) }
  }
  const submit = (event: FormEvent) => { event.preventDefault(); setError(''); setPreview(true) }
  return <div className="ad-flow"><Link to="/mis-campanas" className="ad-flow__back"><ArrowLeft />{t('Mis campañas')}</Link><div className="ad-flow__heading"><span>{t('Publicidad comercial')}</span><h1>{t(id ? 'Editar publicidad' : 'Crear publicidad')}</h1><p>{t('Tu campaña será revisada antes de aparecer en la portada.')}</p></div>
    {error ? <p role="alert" className="ad-flow__error">{error}</p> : null}
    {preview ? <section className="ad-flow__panel" aria-label={t('Vista previa')}><h2>{t('Vista previa')}</h2><div className="ad-flow__preview">{filePreview ? <img src={filePreview} alt={form.title} /> : form.imageAssetId ? <CommercialAdvertisementImage path={imagePath} title={form.title} /> : null}<div><small>{t('Publicidad')}</small><h3>{form.title}</h3><p>{form.description}</p><span>{form.destination}</span></div></div><div className="ad-flow__actions"><button type="button" className="ad-flow__secondary" onClick={() => setPreview(false)}>{t('Volver a editar')}</button><button type="button" disabled={busy} onClick={() => { void save() }}>{t(existing?.paymentStatus === 'paid' ? 'Enviar a revisión' : 'Continuar al pago de prueba')}</button></div></section> : <form className="ad-flow__panel ad-flow__form" onSubmit={submit}>
      <label>{t('Imagen publicitaria')}<input type="file" accept="image/jpeg,image/png,image/webp" required={!form.imageAssetId} disabled={busy} aria-invalid={Boolean(fieldErrors.imageAssetId)} aria-describedby={fieldErrors.imageAssetId ? 'ad-image-error' : undefined} onChange={(event) => { void chooseFile(event.target.files?.[0]) }} />{fieldErrors.imageAssetId ? <small id="ad-image-error">{fieldErrors.imageAssetId}</small> : null}</label>
      {filePreview ? <img className="ad-flow__uploaded" src={filePreview} alt={t('Vista previa de la imagen')} /> : existing ? <CommercialAdvertisementImage path={existing.imageUrl} title={existing.title} /> : null}
      <label>{t('Título')}<input value={form.title} maxLength={90} minLength={3} required aria-invalid={Boolean(fieldErrors.title)} aria-describedby={fieldErrors.title ? 'ad-title-error' : undefined} onChange={(event) => setForm({ ...form, title: event.target.value })} />{fieldErrors.title ? <small id="ad-title-error">{fieldErrors.title}</small> : null}</label>
      <label>{t('Descripción')}<textarea value={form.description} maxLength={300} minLength={10} required rows={4} aria-invalid={Boolean(fieldErrors.description)} aria-describedby={fieldErrors.description ? 'ad-description-error' : undefined} onChange={(event) => setForm({ ...form, description: event.target.value })} />{fieldErrors.description ? <small id="ad-description-error">{fieldErrors.description}</small> : null}</label>
      <label>{t('Tipo de contacto')}<select value={form.destinationType} onChange={(event) => setForm({ ...form, destinationType: event.target.value as DestinationType, destination: '' })}><option value="website">{t('Sitio web')}</option><option value="whatsapp">WhatsApp</option><option value="phone">{t('Teléfono')}</option><option value="email">Email</option></select></label>
      <label>{t(form.destinationType === 'website' ? 'Enlace web' : form.destinationType === 'email' ? 'Correo electrónico' : 'Número de teléfono')}<input value={form.destination} type={form.destinationType === 'email' ? 'email' : form.destinationType === 'website' ? 'url' : 'tel'} required placeholder={form.destinationType === 'website' ? 'https://ejemplo.es' : undefined} aria-invalid={Boolean(fieldErrors.destination)} aria-describedby={fieldErrors.destination ? 'ad-destination-error' : undefined} onChange={(event) => setForm({ ...form, destination: event.target.value })} />{fieldErrors.destination ? <small id="ad-destination-error">{fieldErrors.destination}</small> : null}</label>
      <p className="ad-flow__notice">{t('Paquete de prueba · 30 días. No se realizará ningún cargo.')}</p><button type="submit" disabled={busy || !form.imageAssetId}>{t('Vista previa')}</button>
    </form>}
  </div>
}

export function AdvertisementCheckoutPage() {
  const { id } = useParams()
  const { t } = useI18n()
  const navigate = useNavigate()
  const [ad, setAd] = useState<AdvertisementDetail | null>(null)
  const [price, setPrice] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!id) return
    void getAdvertisement(id).then((item) => {
      setAd(item)
      if (item.status === 'pending_payment') void createAdCheckout(id).then((checkout) => setPrice(checkout.displayPrice)).catch((reason: Error) => setError(reason.message))
    }).catch((reason: Error) => setError(reason.message))
  }, [id])
  const complete = async () => {
    if (!id) return
    setBusy(true); setError('')
    try { await completeAdTestPayment(id); navigate('/mis-campanas', { replace: true }) }
    catch (reason) { setError((reason as Error).message); setBusy(false) }
  }
  return <div className="ad-flow"><Link to="/mis-campanas" className="ad-flow__back"><ArrowLeft />{t('Mis campañas')}</Link><div className="ad-flow__heading"><span>{t('Pago de prueba')}</span><h1>{t('Confirmar publicidad')}</h1></div>{error ? <p role="alert" className="ad-flow__error">{error}</p> : null}{ad ? <section className="ad-flow__panel"><div className="ad-flow__preview"><CommercialAdvertisementImage path={ad.imageUrl} title={ad.title} /><div><small>{t('Publicidad')}</small><h2>{ad.title}</h2><p>{ad.description}</p></div></div><p>{t('Paquete de prueba · 30 días. No se realizará ningún cargo.')}</p><p>{price ? t(price) : t('Pago de prueba')}</p>{ad.status === 'pending_payment' ? <button type="button" disabled={busy || !price} onClick={() => { void complete() }}>{t('Simular pago')}</button> : <p role="status">{t('Pago completado · pendiente de revisión')}</p>}</section> : null}</div>
}

export function MyAdvertisementPage() {
  const { t } = useI18n()
  const [items, setItems] = useState<AdvertisementDetail[]>([])
  const [error, setError] = useState('')
  const reload = () => void getMyAdvertisements().then(setItems).catch((reason: Error) => setError(reason.message))
  useEffect(reload, [])
  const cancel = async (id: string) => { try { await cancelAdvertisement(id); reload() } catch (reason) { setError((reason as Error).message) } }
  return <div className="ad-flow"><div className="ad-flow__heading"><span>{t('Publicidad comercial')}</span><h1>{t('Mis campañas')}</h1><p>{t('Gestiona tus anuncios publicitarios por separado de tus viviendas.')}</p></div><Link className="ad-flow__button" to="/publicidad/nueva">{t('Crear publicidad')}</Link>{error ? <p role="alert" className="ad-flow__error">{error}</p> : null}<div className="ad-flow__list">{items.map((ad) => <article key={ad.id} className="ad-flow__panel ad-flow__row"><CommercialAdvertisementImage path={ad.imageUrl} title={ad.title} /><div><h2>{ad.title}</h2><p>{t(statusLabel(ad.status, ad.endsAt))} · {t(ad.paymentStatus === 'paid' ? 'Pagado (prueba)' : 'Sin pagar')}</p><small>{new Date(ad.createdAt).toLocaleDateString()} {ad.startsAt ? ` · ${new Date(ad.startsAt).toLocaleDateString()} – ${ad.endsAt ? new Date(ad.endsAt).toLocaleDateString() : '∞'}` : ''}</small>{ad.moderationNote ? <p>{ad.moderationNote}</p> : null}<div className="ad-flow__actions">{ad.status !== 'cancelled' ? <Link to={`/publicidad/${ad.id}/editar`}>{t('Editar')}</Link> : null}{ad.status === 'pending_payment' ? <Link to={`/publicidad/${ad.id}/checkout`}>{t('Pago de prueba')}</Link> : null}{ad.status !== 'cancelled' ? <button type="button" className="ad-flow__secondary" onClick={() => { void cancel(ad.id) }}>{t('Cancelar')}</button> : null}</div></div></article>)}</div>{!items.length && !error ? <p>{t('Todavía no tienes campañas publicitarias.')}</p> : null}</div>
}
