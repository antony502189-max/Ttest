import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { getAdminAdvertisements, getPaymentReviews, moderateAdvertisement, resolvePayment, type AdminAdvertisement, type PaymentReview } from '@/api/commercial-advertisements'
import { CommercialAdvertisementImage } from '@/components/commercial-advertisement-image'
import { useI18n } from '@/contexts/i18n-context'
import { advertisementDestinationSource, advertisementPaymentSource, advertisementStatusSource } from '@/lib/commercial-advertisement-labels'
import '@/pages/commercial-advertisement-pages.css'

export function AdminCommercialAdvertisements() {
  const { t, locale } = useI18n()
  const [items, setItems] = useState<AdminAdvertisement[]>([])
  const [payments, setPayments] = useState<PaymentReview[]>([])
  const [paymentError, setPaymentError] = useState(false)
  useEffect(() => { void getPaymentReviews().then(setPayments).catch(() => setPaymentError(true)) }, [])
  const [filter, setFilter] = useState('')
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [sessions, setSessions] = useState<Record<string, string>>({})
  const resolve = async (id: string, action: 'refund' | 'restore' | 'reconcile') => {
    const reason = (notes[id] ?? '').trim()
    if (reason.length < 10) { setError('Indica un motivo de al menos 10 caracteres.'); return }
    if (action === 'refund' && !window.confirm(t('¿Devolver el importe pendiente y finalizar el servicio de este pago?'))) return
    setBusy(id); setError('')
    try {
      await resolvePayment(id, action, reason, sessions[id])
      setPayments(await getPaymentReviews()); reload()
    } catch (reason) { setError((reason as Error).message) }
    finally { setBusy('') }
  }
  const reload = () => void getAdminAdvertisements(filter || undefined).then(setItems).catch((reason: Error) => setError(reason.message))
  useEffect(reload, [filter])
  const act = async (id: string, action: 'approve' | 'reject' | 'deactivate') => {
    setBusy(id); setError('')
    try { await moderateAdvertisement(id, action, notes[id]); setNotes((current) => ({ ...current, [id]: '' })); reload(); setPayments(await getPaymentReviews()) }
    catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }
  return <section className="ad-flow" style={{ width: '100%', margin: 0 }}>
    <div className="ad-flow__heading"><span>{t('Publicidad comercial')}</span><h1>{t('Moderación de publicidad')}</h1></div>
    <Link className="ad-flow__button" to="/publicidad/nueva?admin=1">{t('Publicar banner sin coste')}</Link>
    {paymentError ? <p role="alert">{t('No se pudieron cargar los pagos pendientes de revisión.')}</p> : null}
    {payments.length ? <section className="ad-flow__panel"><h2>{t('Pagos que necesitan revisión')}</h2>{payments.map(payment => <div key={payment.id}>
      <p data-i18n-exempt>{payment.id} · {(payment.amountCents / 100).toFixed(2)} € · {payment.note}</p>
      <label>{t('Motivo de resolución')}<input value={notes[payment.id] ?? ''} maxLength={1000} onChange={event => setNotes(current => ({ ...current, [payment.id]: event.target.value }))} /></label>
      {payment.status === 'creating' ? <label>{t('Sesión Stripe verificada')}<input value={sessions[payment.id] ?? ''} onChange={event => setSessions(current => ({ ...current, [payment.id]: event.target.value }))} /></label> : null}
      <div className="ad-flow__actions">
        {payment.status === 'creating' ? <button disabled={busy === payment.id} onClick={() => void resolve(payment.id, 'reconcile')}>{t('Conciliar pago')}</button> : <>
          <button disabled={busy === payment.id} onClick={() => void resolve(payment.id, 'restore')}>{t('Restaurar servicio')}</button>
          <button className="ad-flow__secondary" disabled={busy === payment.id} onClick={() => void resolve(payment.id, 'refund')}>{t('Devolver pago')}</button>
        </>}
      </div>
    </div>)}</section> : null}
    <label>{t('Estado')} <select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="">{t('Todos')}</option><option value="pending_review">{t('Pendiente de revisión')}</option><option value="active">{t('Activa')}</option><option value="expired">{t('Expirada')}</option><option value="rejected">{t('Rechazada')}</option><option value="cancelled">{t('Cancelada')}</option></select></label>
    {error ? <p className="ad-flow__error" role="alert">{t(error)}</p> : null}
    <div className="ad-flow__list">{items.map((ad) => <article className="ad-flow__panel ad-flow__row" key={ad.id}><CommercialAdvertisementImage path={ad.imageUrl} title={ad.title} /><div>
      <small>{t('Publicidad')} · {ad.ownerEmail}</small><h2 data-i18n-exempt>{ad.title}</h2><p data-i18n-exempt>{ad.description}</p><p>{t(advertisementDestinationSource(ad.destinationType))}: {ad.destination}</p><p>{t(advertisementStatusSource(ad.status))} · {t(advertisementPaymentSource(ad.paymentStatus))}</p>
      <p>{new Date(ad.createdAt).toLocaleDateString(locale)}{ad.startsAt ? ` · ${new Date(ad.startsAt).toLocaleDateString(locale)} – ${ad.endsAt ? new Date(ad.endsAt).toLocaleDateString(locale) : '∞'}` : ''}</p>
      {ad.status === 'pending_review' ? <><label>{t('Nota de moderación')}<input value={notes[ad.id] ?? ''} maxLength={1000} onChange={(event) => setNotes((current) => ({ ...current, [ad.id]: event.target.value }))} /></label><div className="ad-flow__actions"><button type="button" disabled={busy === ad.id} onClick={() => { void act(ad.id, 'approve') }}>{t('Aprobar')}</button><button type="button" className="ad-flow__secondary" disabled={busy === ad.id} onClick={() => { void act(ad.id, 'reject') }}>{t('Rechazar y eliminar')}</button></div></> : null}
      {ad.status === 'active' ? <button type="button" className="ad-flow__secondary" disabled={busy === ad.id} onClick={() => { void act(ad.id, 'deactivate') }}>{t('Desactivar')}</button> : null}
      {ad.paymentOrderId && ad.paymentStatus === 'paid' ? <><label>{t('Motivo de resolución')}<input value={notes[ad.paymentOrderId] ?? ''} maxLength={1000} onChange={event => setNotes(current => ({ ...current, [ad.paymentOrderId!]: event.target.value }))} /></label><button className="ad-flow__secondary" disabled={busy === ad.paymentOrderId} onClick={() => void resolve(ad.paymentOrderId!, 'refund')}>{t('Devolver pago')}</button></> : null}
    </div></article>)}</div>{items.length === 0 ? <p>{t('No hay campañas en este estado.')}</p> : null}
  </section>
}
