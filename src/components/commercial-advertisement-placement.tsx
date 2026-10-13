import { useEffect, useState } from 'react'
import { ArrowUpRight, Megaphone } from 'lucide-react'
import { Link } from 'react-router'
import { adImageUrl, getAdvertisingAvailability, getHomepageAdvertisements, type PublicAdvertisement } from '@/api/commercial-advertisements'
import { useI18n } from '@/contexts/i18n-context'
import { AdvertisingVacancy } from './advertising-vacancy'
import './commercial-advertisement.css'

const SLOTS = 7

export function CommercialAdvertisementPlacement({ mobile = false }: { mobile?: boolean }) {
  const { t } = useI18n()
  const [ads, setAds] = useState<PublicAdvertisement[]>([])
  const [available, setAvailable] = useState<number | null>(null)
  const [imageFailures, setImageFailures] = useState<Set<string>>(() => new Set())
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  useEffect(() => {
    let active = true
    const load = async () => {
      const [items, capacity] = await Promise.allSettled([getHomepageAdvertisements(), getAdvertisingAvailability()])
      if (!active) return
      if (items.status === 'fulfilled') { setAds(items.value.slice(0, SLOTS)); setImageFailures(new Set()); setFailed(false) }
      else setFailed(true)
      setAvailable(capacity.status === 'fulfilled' ? capacity.value.available : null)
      setLoading(false)
    }
    void load()
    const timer = window.setInterval(() => void load(), 60_000)
    return () => { active = false; window.clearInterval(timer) }
  }, [])
  return <section className={`commercial-ad commercial-ad--slots ${mobile ? 'commercial-ad--mobile' : ''}`} aria-label={t('Publicidad comercial')}>
    <div className="commercial-ad__header"><div className="commercial-ad__eyebrow"><Megaphone aria-hidden="true" />{t('Publicidad')}</div><span>{t('1 € · 1 día')}</span></div>
    {loading ? <p role="status">{t('Cargando publicidad…')}</p> : failed ? <p role="status">{t('No se pudo cargar la publicidad. Inténtalo más tarde.')}</p> : <div className="commercial-ad__slots">
      {Array.from({ length: SLOTS }, (_, index) => {
        const ad = ads[index]
        if (!ad) return <div className="commercial-ad__slot commercial-ad__slot--empty" key={`empty-${index}`} data-testid="advertising-slot"><Megaphone aria-hidden="true" /><span>{t('Espacio publicitario')}</span></div>
        const isExternal = /^https?:/.test(ad.destinationUrl)
        return <article className="commercial-ad__slot" key={ad.id} data-testid="advertising-slot" data-ad-id={ad.id}>
          <div className="commercial-ad__visual">{imageFailures.has(ad.id) ? <Megaphone aria-hidden="true" /> : <img data-i18n-exempt src={adImageUrl(ad.imageUrl)} width={ad.imageWidth} height={ad.imageHeight} loading="lazy" decoding="async" alt={ad.title} onError={() => setImageFailures((current) => new Set(current).add(ad.id))} />}</div>
          <div className="commercial-ad__copy"><h2 data-i18n-exempt>{ad.title}</h2><p data-i18n-exempt>{ad.description}</p><a className="commercial-ad__more" href={ad.destinationUrl} target={isExternal ? '_blank' : undefined} rel={isExternal ? 'noopener noreferrer sponsored' : 'sponsored'}>{t('Más información')}<ArrowUpRight aria-hidden="true" /></a></div>
        </article>
      })}
    </div>}
    {available === 0 ? <AdvertisingVacancy /> : <div className="commercial-ad__house"><div><h2>{t('Tu anuncio podría estar aquí')}</h2><p>{t('Da a conocer tu negocio a la comunidad de 112233.es.')}</p></div><Link className="commercial-ad__cta" to="/publicidad/nueva">{t('Publicar publicidad')}<ArrowUpRight aria-hidden="true" /></Link></div>}
  </section>
}
