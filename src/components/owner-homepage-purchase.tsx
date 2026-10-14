import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Home } from 'lucide-react'
import { api } from '@/api/client'
import { useApp } from '@/contexts/app-context'
import { useI18n } from '@/contexts/i18n-context'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { MediaImage } from '@/components/media-image'
import './owner-homepage-purchase.css'

type Quote = { available: boolean; endsAt: string | null; reservedListingId: string | null; featuredListingId: string | null }
type Status = { orderStatus: string | null; fulfillmentStatus: string | null; endsAt: string | null }

export function OwnerHomepagePurchase() {
  const { ownedListings, currentUser } = useApp()
  const { t, locale } = useI18n()
  const [params] = useSearchParams()
  const returnedId = params.get('homepage')
  const payment = params.get('payment')
  const listings = ownedListings.filter((item) => item.ownerUserId === currentUser?.id && item.status === 'Publicado' && !item.isExternal && item.images.length > 0)
  const [open, setOpen] = useState(false)
  const [selected, setSelected] = useState('')
  const [quote, setQuote] = useState<Quote | null>(null)
  const [status, setStatus] = useState<Status | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
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
  }, [returnedId, payment, open])
  const pay = async () => {
    setBusy(true); setError('')
    try {
      const result = await api<{ url: string }>(`/payments/listings/${selected}/homepage/checkout`, { method: 'POST' })
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
    <section className="owner-top-cta owner-homepage-cta" aria-label={t('Tu anuncio en portada')}>
      <div className="owner-top-cta__copy"><span className="owner-top-cta__eyebrow"><Home aria-hidden="true" /></span><div><strong>{t('Tu anuncio en portada')}</strong><p>{t('60 € · 1 mes · enlace directo a tu anuncio')}</p>{status?.endsAt ? <small>{t('En portada hasta')} {new Date(status.endsAt).toLocaleDateString(locale)}</small> : null}</div></div>
      <Button className="owner-top-cta__button" disabled={!listings.length || busy || review || Boolean(status?.endsAt)} onClick={() => { setSelected(quote?.reservedListingId || listings[0]?.id || ''); setError(''); setOpen(true) }}>{t('Destacar en portada')}</Button>
    </section>
    {error && !open ? <p role="alert">{t(error)}</p> : null}
    {review ? <p role="alert">{t('El pago se ha recibido, pero necesita revisión. Contacta con soporte; no vuelvas a pagar.')}</p> : null}
    {status?.orderStatus === 'pending' ? <p role="status">{t('Estamos confirmando el pago de portada.')}</p> : null}
    {status?.orderStatus === 'failed' ? <p role="status">{t('Pago fallido. Puedes volver a intentarlo.')}</p> : null}
    {status?.fulfillmentStatus === 'revoked' ? <p role="status">{t('Pago devuelto · servicio finalizado')}</p> : null}
    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="owner-top-dialog"><DialogHeader><DialogTitle>{t('Tu anuncio en portada')}</DialogTitle><DialogDescription>{t('Selecciona tu anuncio. Su foto aparecerá en la portada durante un mes con un enlace al anuncio.')}</DialogDescription></DialogHeader>
      <div className="owner-top-dialog__list" role="list">{listings.map((listing) => <button key={listing.id} type="button" aria-pressed={selected === listing.id} className={`owner-top-dialog__option ${selected === listing.id ? 'is-selected' : ''}`} onClick={() => setSelected(listing.id)}><MediaImage src={listing.images[0]} variant="thumb" alt="" /><span><strong>{listing.title}</strong><small>{listing.area} · {listing.price} €</small></span></button>)}</div>
      <div className="owner-top-dialog__next"><strong>{t('60 € · 1 mes · enlace directo a tu anuncio')}</strong><span>{t('El mes empieza cuando se confirma el pago.')}</span>
        {quote && !quote.available && quote.reservedListingId !== selected ? <span role="status">{t('La portada está ocupada. Vuelve a intentarlo cuando quede libre.')}{quote.endsAt ? ` ${new Date(quote.endsAt).toLocaleDateString(locale)}` : ''}</span> : null}
        {error ? <span role="alert">{t(error)}</span> : null}
        <Button disabled={busy || !selected || !quote || review || (!quote.available && quote.reservedListingId !== selected)} onClick={() => void pay()}>{t('Pagar con Stripe')}</Button>
        {quote?.reservedListingId ? <Button variant="outline" disabled={busy} onClick={() => void cancel()}>{t('Cancelar pago')}</Button> : null}
      </div>
    </DialogContent></Dialog>
  </>
}
