import { useEffect, useMemo, useState } from 'react'
import { ArrowUpRight, ChevronLeft, ChevronRight, Megaphone } from 'lucide-react'
import { Link } from 'react-router'
import { adImageUrl, getHomepageAdvertisements, type PublicAdvertisement } from '@/api/commercial-advertisements'
import { useI18n } from '@/contexts/i18n-context'
import './commercial-advertisement.css'

const ROTATION_MS = 8_000

export function CommercialAdvertisementPlacement({ mobile = false }: { mobile?: boolean }) {
  const { t } = useI18n()
  const [ads, setAds] = useState<PublicAdvertisement[]>([])
  const [index, setIndex] = useState(0)
  const [imageFailures, setImageFailures] = useState<Set<string>>(() => new Set())
  const [hovered, setHovered] = useState(false)
  const [focusWithin, setFocusWithin] = useState(false)

  useEffect(() => {
    let active = true
    void getHomepageAdvertisements()
      .then((items) => {
        if (!active) return
        setAds(items.slice(0, 12))
        setIndex(0)
        setImageFailures(new Set())
      })
      .catch(() => {
        if (!active) return
        setAds([])
        setIndex(0)
      })
    return () => { active = false }
  }, [])

  const reducedMotion = useMemo(
    () => typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    [],
  )

  useEffect(() => {
    if (ads.length <= 1 || reducedMotion || hovered || focusWithin) return
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % ads.length), ROTATION_MS)
    return () => window.clearInterval(timer)
  }, [ads.length, focusWithin, hovered, reducedMotion])

  const ad = ads[index] ?? null
  const move = (direction: -1 | 1) => {
    if (ads.length <= 1) return
    setIndex((current) => (current + direction + ads.length) % ads.length)
  }
  const destination = ad?.destinationUrl
  const isExternal = destination?.startsWith('http:') || destination?.startsWith('https:')
  const imageFailed = ad ? imageFailures.has(ad.id) : false

  return <section
    className={`commercial-ad ${mobile ? 'commercial-ad--mobile' : ''}`}
    aria-label={t('Publicidad comercial')}
    aria-roledescription={ads.length > 1 ? t('Carrusel') : undefined}
    onMouseEnter={() => setHovered(true)}
    onMouseLeave={() => setHovered(false)}
    onFocusCapture={() => setFocusWithin(true)}
    onBlurCapture={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setFocusWithin(false)
    }}
  >
    <div className="commercial-ad__eyebrow"><Megaphone aria-hidden="true" />{t('Publicidad')}</div>
    {ad ? <>
      <div className="commercial-ad__content" data-testid="commercial-ad-slide" data-ad-id={ad.id}>
        <div className="commercial-ad__visual">
          {imageFailed
            ? <Megaphone data-i18n-exempt aria-label={ad.title} />
            : <img
                data-i18n-exempt
                src={adImageUrl(ad.imageUrl)}
                width={ad.imageWidth}
                height={ad.imageHeight}
                loading="lazy"
                decoding="async"
                alt={ad.title}
                onError={() => setImageFailures((current) => new Set(current).add(ad.id))}
              />}
        </div>
        <div className="commercial-ad__copy">
          <h2 data-i18n-exempt>{ad.title}</h2>
          <p data-i18n-exempt>{ad.description}</p>
          <a className="commercial-ad__cta" href={destination} target={isExternal ? '_blank' : undefined} rel={isExternal ? 'noopener noreferrer sponsored' : 'sponsored'}>
            {t('Más información')}<ArrowUpRight aria-hidden="true" />
          </a>
        </div>
      </div>
      {ads.length > 1 ? <div className="commercial-ad__carousel" aria-label={t('Publicidad comercial')}>
        <button type="button" className="commercial-ad__carousel-arrow" onClick={() => move(-1)} aria-label={t('Publicidad anterior')}><ChevronLeft /></button>
        <div className="commercial-ad__carousel-position" aria-live="polite">{index + 1} / {ads.length}</div>
        <div className="commercial-ad__carousel-dots" role="group" aria-label={t('Seleccionar publicidad')}>
          {ads.map((item, itemIndex) => <button
            key={item.id}
            type="button"
            className={itemIndex === index ? 'is-active' : undefined}
            aria-label={`${t('Mostrar publicidad')} ${itemIndex + 1}`}
            aria-current={itemIndex === index ? 'true' : undefined}
            onClick={() => setIndex(itemIndex)}
          />)}
        </div>
        <button type="button" className="commercial-ad__carousel-arrow" onClick={() => move(1)} aria-label={t('Publicidad siguiente')}><ChevronRight /></button>
      </div> : null}
    </> : <div className="commercial-ad__house">
      <div className="commercial-ad__mark"><Megaphone aria-hidden="true" /></div>
      <div><h2>{t('Tu anuncio podría estar aquí')}</h2><p>{t('Da a conocer tu negocio a la comunidad de 112233.es.')}</p></div>
      <Link className="commercial-ad__cta" to="/publicidad/nueva">{t('Publicar publicidad')}<ArrowUpRight aria-hidden="true" /></Link>
    </div>}
  </section>
}
