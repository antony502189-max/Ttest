import { useEffect, useState } from 'react'
import { getAdminAdvertisements, moderateAdvertisement, type AdminAdvertisement } from '@/api/commercial-advertisements'
import { CommercialAdvertisementImage } from '@/components/commercial-advertisement-image'
import { useI18n } from '@/contexts/i18n-context'
import { advertisementDestinationSource, advertisementPaymentSource, advertisementStatusSource } from '@/lib/commercial-advertisement-labels'
import '@/pages/commercial-advertisement-pages.css'

export function AdminCommercialAdvertisements() {
  const { t, locale } = useI18n()
  const [items, setItems] = useState<AdminAdvertisement[]>([])
  const [filter, setFilter] = useState('')
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const reload = () => void getAdminAdvertisements(filter || undefined).then(setItems).catch((reason: Error) => setError(reason.message))
  useEffect(reload, [filter])
  const act = async (id: string, action: 'approve' | 'reject' | 'deactivate') => {
    setBusy(id); setError('')
    try { await moderateAdvertisement(id, action, notes[id]); setNotes((current) => ({ ...current, [id]: '' })); reload() }
    catch (reason) { setError((reason as Error).message) } finally { setBusy('') }
  }
  return <section className="ad-flow" style={{ width: '100%', margin: 0 }}><div className="ad-flow__heading"><span>{t('Publicidad comercial')}</span><h1>{t('Moderación de publicidad')}</h1></div><label>{t('Estado')} <select value={filter} onChange={(event) => setFilter(event.target.value)}><option value="">{t('Todos')}</option><option value="pending_review">{t('Pendiente de revisión')}</option><option value="active">{t('Activa')}</option><option value="expired">{t('Expirada')}</option><option value="rejected">{t('Rechazada')}</option><option value="cancelled">{t('Cancelada')}</option></select></label>{error ? <p className="ad-flow__error" role="alert">{t(error)}</p> : null}<div className="ad-flow__list">{items.map((ad) => <article className="ad-flow__panel ad-flow__row" key={ad.id}><CommercialAdvertisementImage path={ad.imageUrl} title={ad.title} /><div><small>{t('Publicidad')} · {ad.ownerEmail}</small><h2 data-i18n-exempt>{ad.title}</h2><p data-i18n-exempt>{ad.description}</p><p>{t(advertisementDestinationSource(ad.destinationType))}: {ad.destination}</p><p>{t(advertisementStatusSource(ad.status))} · {t(advertisementPaymentSource(ad.paymentStatus))}</p><p>{new Date(ad.createdAt).toLocaleDateString(locale)}{ad.startsAt ? ` · ${new Date(ad.startsAt).toLocaleDateString(locale)} – ${ad.endsAt ? new Date(ad.endsAt).toLocaleDateString(locale) : '∞'}` : ''}</p>{ad.status === 'pending_review' ? <><label>{t('Nota de moderación')}<input value={notes[ad.id] ?? ''} maxLength={1000} onChange={(event) => setNotes((current) => ({ ...current, [ad.id]: event.target.value }))} /></label><div className="ad-flow__actions"><button type="button" disabled={busy === ad.id} onClick={() => { void act(ad.id, 'approve') }}>{t('Aprobar')}</button><button type="button" className="ad-flow__secondary" disabled={busy === ad.id} onClick={() => { void act(ad.id, 'reject') }}>{t('Rechazar')}</button></div></> : null}{ad.status === 'active' ? <button type="button" className="ad-flow__secondary" disabled={busy === ad.id} onClick={() => { void act(ad.id, 'deactivate') }}>{t('Desactivar')}</button> : null}</div></article>)}</div>{items.length === 0 ? <p>{t('No hay campañas en este estado.')}</p> : null}</section>
}
