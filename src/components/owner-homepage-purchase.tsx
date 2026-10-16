import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { api } from '@/api/client'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { MediaImage } from '@/components/media-image'
import { promotionDurationLabel, formatPromotionPrice, type PromotionHours } from '@/lib/promotion-offers'
import './owner-homepage-purchase.css'

type Quote = { amountCents: number; currency: string; offers: { durationHours: PromotionHours; amountCents: number }[]; available: boolean; endsAt: string | null; reservedListingId: string | null; featuredListingId: string | null }
type Status = { orderStatus: string | null; fulfillmentStatus: string | null; endsAt: string | null }

export function OwnerHomepagePurchase({ listingId = '', onClose, onBack }: { listingId?: string; onClose: () => void; onBack: () => void }) {
  const { ownedListings, currentUser } = useApp()
  const { t, locale, language } = useI18n()
  const [params] = useSearchParams()
  const returnedId = params.get('homepage')
  const payment = params.get('payment')
  const listings = ownedListings.filter((item) => item.ownerUserId === currentUser?.id && item.status === 'Publicado' && !item.isExternal && item.images.length > 0)
  const open = Boolean(listingId)
  const selected = listingId
  const [quote, setQuote] = useState<Quote | null>(null)
  const [durationHours, setDurationHours] = useState<PromotionHours>(12)
  const selectedOffer = quote?.offers?.find((offer) => offer.durationHours === durationHours)
  const [status, setStatus] = useState<Status | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!listingId && !returnedId) return
    setQuote(null); setStatus(null); setError('')
    let active = true
    let timer: ReturnType<typeof setTimeout>
    let attempts = 0
    const load = async () => {
      try {
        const price = await api<Quote>('/payments/homepage/quote')
        if (!active) return
        setQuote(price)
        const id = returnedId || price.reservedListingId || (price.endsAt ? price.featuredListingId : null)
        if (id) {
          const result = await api<Status>(`/payments/listings/${id}/homepage/status`)
          if (!active) return
          setStatus(result)
          if (result.orderStatus === 'pending' && ++attempts < 60) timer = setTimeout(() => void load(), 3000)
        }
      } catch (reason) { if (active) setError((reason as Error).message) }
    }
    const initialize = async () => {
      if (returnedId && payment === 'cancelled') {
        try { await api(`/payments/listings/${returnedId}/homepage/checkout/cancel`, { method: 'POST' }) }
        catch (reason) { if (active) setError((reason as Error).message) }
      }
      await load()
    }
    void initialize()
    return () => { active = false; clearTimeout(timer) }
  }, [returnedId, payment, listingId])
  const pay = async () => {
    if (!selectedOffer) return
    setBusy(true); setError('')
    try {
      const result = await api<{ url: string }>(`/payments/listings/${selected}/homepage/checkout`, { method: 'POST', body: JSON.stringify({ durationHours }) })
      window.location.assign(result.url)
    } catch (reason) { setError((reason as Error).message); setBusy(false) }
  }
  const cancel = async () => {
    const id = quote?.reservedListingId || returnedId
    if (!id) return
    setBusy(true); setError('')
    try {
      await api(`/payments/listings/${id}/homepage/checkout/cancel`, { method: 'POST' })
      setQuote(await api<Quote>('/payments/homepage/quote'))
      setStatus(await api<Status>(`/payments/listings/${id}/homepage/status`))
    } catch (reason) { setError((reason as Error).message) }
    finally { setBusy(false) }
  }
  const review = status?.fulfillmentStatus === 'review_required'
  return <>
    {returnedId && status?.endsAt ? <p role="status">{t('En portada hasta')} {new Date(status.endsAt).toLocaleDateString(locale)}</p> : null}
    {error && !open && returnedId ? <p role="alert">{t(error)}</p> : null}
    {review ? <p role="alert">{t('El pago se ha recibido, pero necesita revisión. Contacta con soporte; no vuelvas a pagar.')}</p> : null}
    {status?.orderStatus === 'pending' ? <p role="status">{t('Estamos confirmando el pago de portada.')}</p> : null}
    {status?.orderStatus === 'failed' ? <p role="status">{t('Pago fallido. Puedes volver a intentarlo.')}</p> : null}
    {status?.fulfillmentStatus === 'revoked' ? <p role="status">{t('Pago devuelto · servicio finalizado')}</p> : null}
    <Dialog open={open} onOpenChange={(next) => { if (!next) onClose() }}><DialogContent className="owner-top-dialog"><DialogHeader><DialogTitle>{t('Tu anuncio en portada')}</DialogTitle><DialogDescription>{t('Su foto aparecerá en la portada con un enlace al anuncio.')}</DialogDescription></DialogHeader>
      <div className="owner-top-dialog__list" role="list">{listings.filter((listing) => listing.id === selected).map((listing) => <div key={listing.id} className="owner-top-dialog__option is-selected" data-listing-id={listing.id}><MediaImage src={listing.images[0]} variant="thumb" alt="" /><span><strong>{listing.title}</strong><small>{listing.area} · {listing.price} €</small></span></div>)}</div>
      <div className="owner-top-dialog__next">
        {quote?.offers?.length ? <div className="owner-promotion-duration-options" role="group" aria-label={t('Duración de portada')}>
          {quote.offers.map((offer) => <button type="button" key={offer.durationHours}
            className={`owner-promotion-duration-option ${durationHours === offer.durationHours ? 'is-selected' : ''}`}
            aria-pressed={durationHours === offer.durationHours}
            onClick={() => setDurationHours(offer.durationHours)}>
            <span>{promotionDurationLabel(offer.durationHours, language)}</span>
            <strong>{formatPromotionPrice(offer.amountCents, locale)}</strong>
          </button>)}
        </div> : <span role="status">{t('Cargando…')}</span>}
        {selectedOffer ? <strong className="owner-promotion-price">{formatPromotionPrice(selectedOffer.amountCents, locale)} · {promotionDurationLabel(durationHours, language)}</strong> : null}
        <span>{t('El plazo empieza cuando se confirma el pago.')}</span>
        {quote && !quote.available && quote.reservedListingId !== selected ? <span role="status">{t('La portada está ocupada. Vuelve a intentarlo cuando quede libre.')}{quote.endsAt ? ` ${new Date(quote.endsAt).toLocaleDateString(locale)}` : ''}</span> : null}
        {error ? <span role="alert">{t(error)}</span> : null}
        <Button disabled={busy || !selected || !selectedOffer || review || (!quote?.available && quote?.reservedListingId !== selected)} onClick={() => void pay()}>{t('Pagar con Stripe')}</Button>
        <Button variant="outline" disabled={busy} onClick={onBack}>{t('Volver')}</Button>
        {quote?.reservedListingId ? <Button variant="outline" disabled={busy} onClick={() => void cancel()}>{t('Cancelar pago')}</Button> : null}
      </div>
    </DialogContent></Dialog>
  </>
}
