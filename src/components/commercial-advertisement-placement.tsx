import { useEffect, useState } from 'react'
import { ArrowUpRight, ChevronRight, Crown, Megaphone } from 'lucide-react'
import { Link, useNavigate } from 'react-router'
import {
  adImageUrl, getAdvertisingAvailability, getHomepageAdvertisements, getPremiumAdvertisement,
  type AdvertisingAvailability, type PublicAdvertisement,
} from '@/api/commercial-advertisements'
import { useI18n } from '@/contexts/i18n-context'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { AdvertisingVacancy } from './advertising-vacancy'
import './commercial-advertisement.css'

const SLOTS = 7
type Placement = 'premium' | 'standard'

const copy = {
  es: {
    premium: 'TOP · PUBLICIDAD DESTACADA', subtitle: 'Tu anuncio en la parte superior',
    regular: 'Espacio publicitario', regularType: 'PUBLICIDAD', period: '30 días',
    call: 'Pulsa aquí para publicar y pagar', select: 'Elige tu publicidad',
    selectHint: 'Selecciona dónde quieres que aparezca tu anuncio. El precio final se confirma antes de Stripe.',
    premiumChoice: 'Banner Premium Principal', standardChoice: 'Espacio publicitario',
    continue: 'Continuar', unavailable: 'Ocupado', noPrice: 'Precio no disponible',
  },
  en: {
    premium: 'TOP · FEATURED ADVERTISING', subtitle: 'Your ad in the top position',
    regular: 'Advertising space', regularType: 'ADVERTISEMENT', period: '30 days',
    call: 'Publish and pay', select: 'Choose advertising placement',
    selectHint: 'Choose where your ad will appear. The final amount is confirmed before Stripe.',
    premiumChoice: 'Main premium banner', standardChoice: 'Advertising space',
    continue: 'Continue', unavailable: 'Unavailable', noPrice: 'Price unavailable',
  },
  ru: {
    premium: 'TOP · ПРЕМИАЛЬНАЯ РЕКЛАМА', subtitle: 'Ваш баннер в самом верху',
    regular: 'Рекламное место', regularType: 'РЕКЛАМА', period: '30 дней',
    call: 'Разместить рекламу и оплатить', select: 'Выберите рекламное размещение',
    selectHint: 'Выберите место размещения. Окончательная стоимость подтверждается перед Stripe.',
    premiumChoice: 'Главный премиум-баннер', standardChoice: 'Обычное рекламное место',
    continue: 'Продолжить', unavailable: 'Занято', noPrice: 'Цена недоступна',
  },
} as const

/** Paid placement and the checkout amount are independently verified server-side. */
export function CommercialAdvertisementPlacement({ mobile = false }: { mobile?: boolean }) {
  const { t, locale, language } = useI18n()
  const navigate = useNavigate()
  const words = copy[language]
  const [ads, setAds] = useState<PublicAdvertisement[]>([])
  const [premiumAds, setPremiumAds] = useState<PublicAdvertisement[]>([])
  const [capacity, setCapacity] = useState<AdvertisingAvailability | null>(null)
  const [imageFailures, setImageFailures] = useState<Set<string>>(() => new Set())
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [choice, setChoice] = useState<Placement | null>(null)

  useEffect(() => {
    let active = true
    const load = async () => {
      const [items, premium, availability] = await Promise.allSettled([
        getHomepageAdvertisements(), getPremiumAdvertisement(), getAdvertisingAvailability(),
      ])
      if (!active) return
      if (items.status === 'fulfilled') {
        setAds(items.value.slice(0, SLOTS))
        setImageFailures(new Set())
        setFailed(false)
      } else setFailed(true)
      setPremiumAds(premium.status === 'fulfilled' ? premium.value.slice(0, 1) : [])
      setCapacity(availability.status === 'fulfilled' ? availability.value : null)
      setLoading(false)
    }
    void load()
    const timer = window.setInterval(() => void load(), 60_000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])

  const validPrice = Boolean(capacity && capacity.currency === 'EUR' && capacity.months === 1)
  const standardPrice = validPrice && Number.isSafeInteger(capacity?.monthlyPriceCents) && (capacity?.monthlyPriceCents ?? 0) > 0
    ? capacity!.monthlyPriceCents : null
  const premiumPrice = validPrice && Number.isSafeInteger(capacity?.premiumMonthlyPriceCents) && (capacity?.premiumMonthlyPriceCents ?? 0) > 0
    ? capacity!.premiumMonthlyPriceCents! : null
  const formatMoney = (cents: number) => new Intl.NumberFormat(locale, {
    style: 'currency', currency: 'EUR', minimumFractionDigits: 0, maximumFractionDigits: 0,
  }).format(cents / 100)
  const priceText = (cents: number | null) => cents == null ? words.noPrice : `${formatMoney(cents)} / ${words.period}`
  const premiumAvailable = premiumPrice !== null && capacity?.premiumAvailable === 1 && premiumAds.length === 0
  const standardAvailable = standardPrice !== null && (capacity?.available ?? 0) > 0
  const canContinue = choice === 'premium' ? premiumAvailable : choice === 'standard' && standardAvailable
  const choose = (placement: Placement) => setChoice(placement)
  const proceed = () => {
    if (!choice || !canContinue) return
    navigate(`/publicidad/nueva?plan=${choice}`)
    setChoice(null)
  }

  const premiumAd = premiumAds[0]
  return <section className={`commercial-ad commercial-ad--slots commercial-ad--redesign ${mobile ? 'commercial-ad--mobile' : ''}`} aria-label={t('Publicidad comercial')}>
    <div className="commercial-ad__premium" data-testid="premium-advertising-banner">
      {premiumAd ? <article className="commercial-ad__premium-occupied" data-ad-id={premiumAd.id}>
        <div className="commercial-ad__premium-heading"><Crown aria-hidden="true" /><span>{words.premium}</span></div>
        <div className="commercial-ad__premium-paid">
          <div className="commercial-ad__premium-photo">
            {imageFailures.has(premiumAd.id) ? <Megaphone aria-hidden="true" /> : <img src={adImageUrl(premiumAd.imageUrl)} alt="" loading="lazy" onError={() => setImageFailures((x) => new Set(x).add(premiumAd.id))} />}
          </div>
          <div><strong data-i18n-exempt>{premiumAd.title}</strong><small data-i18n-exempt>{premiumAd.description}</small>
            <a className="commercial-ad__premium-link" href={premiumAd.destinationUrl} rel="sponsored noopener noreferrer" target="_blank">{t('Más información')} <ArrowUpRight aria-hidden="true" /></a>
          </div>
        </div>
      </article> : <div className="commercial-ad__premium-unoccupied">
        <div className="commercial-ad__premium-head">
          <Crown className="commercial-ad__crown" aria-hidden="true" />
          <div className="commercial-ad__premium-title"><strong>{words.premium}</strong><span>{words.subtitle}</span></div>
          {premiumPrice !== null ? <div className="commercial-ad__premium-cost" data-testid="premium-advertising-price"><strong>{formatMoney(premiumPrice)}</strong><span>/ {words.period}</span></div> : null}
        </div>
        <button type="button" className="commercial-ad__premium-action" onClick={() => choose('premium')} disabled={!premiumAvailable}>
          <Megaphone aria-hidden="true" /><span>{premiumAvailable ? words.call : words.unavailable}</span><ChevronRight aria-hidden="true" />
        </button>
      </div>}
    </div>
    <div className="commercial-ad__header">
      <div className="commercial-ad__eyebrow"><Megaphone aria-hidden="true" />{t('Publicidad')}</div>
      {standardPrice !== null ? <div className="commercial-ad__monthly-price" data-testid="advertising-monthly-price">
        <span>{new Intl.NumberFormat(locale, { style: 'currency', currency: 'EUR', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(standardPrice / 100)}</span>
        <span className="commercial-ad__monthly-price-unit">/ {t('Mes').toLocaleLowerCase(locale)}</span>
      </div> : null}
    </div>
    {loading ? <p role="status">{t('Cargando publicidad…')}</p> : failed ? <p role="status">{t('No se pudo cargar la publicidad. Inténtalo más tarde.')}</p> : <div className="commercial-ad__slots">
      {Array.from({ length: SLOTS }, (_, index) => {
        const ad = ads[index]
        if (!ad) return <button type="button" className="commercial-ad__slot commercial-ad__slot--empty" key={`empty-${index}`} data-testid="advertising-slot" onClick={() => choose('standard')} disabled={!standardAvailable}>
          <span className="commercial-ad__slot-icon"><Megaphone aria-hidden="true" /></span>
          <span className="commercial-ad__slot-copy"><strong>{words.regular}</strong><small>{words.regularType}</small></span>
          {standardPrice !== null ? <span className="commercial-ad__slot-price" data-testid="advertising-slot-price">{priceText(standardPrice)}</span> : null}
          <ChevronRight className="commercial-ad__slot-chevron" aria-hidden="true" />
        </button>
        const isExternal = /^https?:/.test(ad.destinationUrl)
        return <article className="commercial-ad__slot" key={ad.id} data-testid="advertising-slot" data-ad-id={ad.id}>
          <div className="commercial-ad__visual">{imageFailures.has(ad.id) ? <Megaphone aria-hidden="true" /> : <img data-i18n-exempt src={adImageUrl(ad.imageUrl)} width={ad.imageWidth} height={ad.imageHeight} loading="lazy" decoding="async" alt={ad.title} onError={() => setImageFailures((current) => new Set(current).add(ad.id))} />}</div>
          <div className="commercial-ad__copy"><h2 data-i18n-exempt>{ad.title}</h2><p data-i18n-exempt>{ad.description}</p><a className="commercial-ad__more" href={ad.destinationUrl} target={isExternal ? '_blank' : undefined} rel={isExternal ? 'noopener noreferrer sponsored' : 'sponsored'}>{t('Más información')}<ArrowUpRight aria-hidden="true" /></a></div>
        </article>
      })}
    </div>}
    {capacity?.available === 0 ? <AdvertisingVacancy /> : <div className="commercial-ad__house"><div><h2>{t('Tu anuncio podría estar aquí')}</h2><p>{t('Da a conocer tu negocio a la comunidad de 112233.es.')}</p></div><Link className="commercial-ad__cta" to="/publicidad/nueva">{t('Publicar publicidad')}<ArrowUpRight aria-hidden="true" /></Link></div>}
    <Dialog open={choice !== null} onOpenChange={(next) => { if (!next) setChoice(null) }}>
      <DialogContent className="commercial-ad__picker" data-testid="advertising-package-picker">
        <DialogHeader><DialogTitle>{words.select}</DialogTitle><DialogDescription>{words.selectHint}</DialogDescription></DialogHeader>
        <div className="commercial-ad__plans" role="group" aria-label={words.select}>
          <button type="button" className={choice === 'premium' ? 'is-selected' : ''} aria-pressed={choice === 'premium'} onClick={() => setChoice('premium')} disabled={!premiumAvailable}>
            <Crown aria-hidden="true" /><span><strong>{words.premiumChoice}</strong><small>{premiumAvailable ? words.subtitle : words.unavailable}</small></span><b>{priceText(premiumPrice)}</b>
          </button>
          <button type="button" className={choice === 'standard' ? 'is-selected' : ''} aria-pressed={choice === 'standard'} onClick={() => setChoice('standard')} disabled={!standardAvailable}>
            <Megaphone aria-hidden="true" /><span><strong>{words.standardChoice}</strong><small>{standardAvailable ? words.regularType : words.unavailable}</small></span><b>{priceText(standardPrice)}</b>
          </button>
        </div>
        <button className="commercial-ad__picker-continue" type="button" disabled={!canContinue} onClick={proceed}>{words.continue}<ChevronRight aria-hidden="true" /></button>
      </DialogContent>
    </Dialog>
  </section>
}
