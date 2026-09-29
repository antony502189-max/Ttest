import { useEffect, useState } from 'react'
import { ArrowUpRight, Megaphone } from 'lucide-react'
import { Link } from 'react-router'
import { adImageUrl, getHomepageAdvertisements, type PublicAdvertisement } from '@/api/commercial-advertisements'
import { useI18n } from '@/contexts/i18n-context'
import './commercial-advertisement.css'

export function CommercialAdvertisementPlacement({ mobile = false }: { mobile?: boolean }) {
  const { t } = useI18n()
  const [ad, setAd] = useState<PublicAdvertisement | null>(null)
  const [imageFailed, setImageFailed] = useState(false)
  useEffect(() => {
    let active = true
    void getHomepageAdvertisements().then((items) => { if (active) setAd(items[0] ?? null) }).catch(() => { if (active) setAd(null) })
    return () => { active = false }
  }, [])
  const destination = ad?.destinationUrl
  const isExternal = destination?.startsWith('http:') || destination?.startsWith('https:')
  return <section className={`commercial-ad ${mobile ? 'commercial-ad--mobile' : ''}`} aria-label={t('Publicidad comercial')}>
    <div className="commercial-ad__eyebrow"><Megaphone aria-hidden="true" />{t('Publicidad')}</div>
    {ad ? <div className="commercial-ad__content">
      <div className="commercial-ad__visual">{imageFailed ? <Megaphone aria-hidden="true" /> : <img src={adImageUrl(ad.imageUrl)} width={ad.imageWidth} height={ad.imageHeight} loading="lazy" decoding="async" alt={ad.title} onError={() => setImageFailed(true)} />}</div>
      <div className="commercial-ad__copy"><h2>{ad.title}</h2><p>{ad.description}</p><a className="commercial-ad__cta" href={destination} target={isExternal ? '_blank' : undefined} rel={isExternal ? 'noopener noreferrer sponsored' : 'sponsored'}>{t('Más información')}<ArrowUpRight aria-hidden="true" /></a></div>
    </div> : <div className="commercial-ad__house"><div className="commercial-ad__mark"><Megaphone aria-hidden="true" /></div><div><h2>{t('Tu anuncio podría estar aquí')}</h2><p>{t('Da a conocer tu negocio a la comunidad de 112233.es.')}</p></div><Link className="commercial-ad__cta" to="/publicidad/nueva">{t('Publicar publicidad')}<ArrowUpRight aria-hidden="true" /></Link></div>}
  </section>
}
