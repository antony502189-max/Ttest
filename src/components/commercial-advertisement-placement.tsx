import { useEffect, useRef, useState } from 'react'
import { ArrowUpRight, ChevronLeft, ChevronRight, Megaphone } from 'lucide-react'
import { Link } from 'react-router'
import { adImageUrl, getAdvertisingAvailability, getHomepageAdvertisements, type PublicAdvertisement } from '@/api/commercial-advertisements'
import { useI18n } from '@/contexts/i18n-context'
import { AdvertisingVacancy } from './advertising-vacancy'
import './commercial-advertisement.css'

const SLOTS = 7
const AUTOPLAY_MS = 5000
const centeredOffset = (viewport: HTMLElement, slide: HTMLElement) => slide.offsetLeft - (viewport.clientWidth - slide.offsetWidth) / 2

export function CommercialAdvertisementPlacement({ mobile = false }: { mobile?: boolean }) {
  const { t } = useI18n()
  const [ads, setAds] = useState<PublicAdvertisement[]>([])
  const [available, setAvailable] = useState<number | null>(null)
  const [imageFailures, setImageFailures] = useState<Set<string>>(() => new Set())
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)
  const [slide, setSlide] = useState(0)
  const [hovered, setHovered] = useState(false)
  const [focused, setFocused] = useState(false)
  const [touching, setTouching] = useState(false)
  const [inView, setInView] = useState(false)
  const [pageVisible, setPageVisible] = useState(!document.hidden)
  const [reducedMotion, setReducedMotion] = useState(false)
  const viewport = useRef<HTMLDivElement>(null)
  const slideCount = Math.min(ads.length + 1, SLOTS)
  const activeSlide = slide % slideCount
  const showSlide = (index: number) => {
    const element = viewport.current
    const target = element?.children[index] as HTMLElement | undefined
    if (element && target) element.scrollTo({ left: centeredOffset(element, target), behavior: reducedMotion ? 'instant' : 'smooth' })
  }
  const move = (direction: number) => showSlide((activeSlide + direction + slideCount) % slideCount)

  useEffect(() => {
    const update = () => setPageVisible(!document.hidden)
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])
  useEffect(() => {
    const preference = window.matchMedia('(prefers-reduced-motion: reduce)')
    const update = () => setReducedMotion(preference.matches)
    update()
    preference.addEventListener('change', update)
    return () => preference.removeEventListener('change', update)
  }, [])
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
  useEffect(() => {
    const element = viewport.current
    if (!element) return
    const observer = new IntersectionObserver(([entry]) => setInView(entry.intersectionRatio >= .5), { threshold: .5 })
    observer.observe(element)
    return () => observer.disconnect()
  }, [loading, failed])
  useEffect(() => {
    // A changed inventory starts at the first banner, including after an empty response.
    setSlide(0)
    viewport.current?.scrollTo({ left: 0, behavior: 'instant' })
  }, [slideCount])
  useEffect(() => {
    if (slideCount < 2 || loading || failed || hovered || focused || touching || !inView || !pageVisible || reducedMotion) return
    const timer = window.setTimeout(() => {
      if (document.hidden) return
      const element = viewport.current
      const target = element?.children[(activeSlide + 1) % slideCount] as HTMLElement | undefined
      if (element && target) element.scrollTo({ left: centeredOffset(element, target), behavior: 'smooth' })
    }, AUTOPLAY_MS)
    return () => window.clearTimeout(timer)
  }, [activeSlide, slideCount, loading, failed, hovered, focused, touching, inView, pageVisible, reducedMotion])

  return <section className={`commercial-ad commercial-ad--slots ${mobile ? 'commercial-ad--mobile' : ''}`} aria-label={t('Publicidad comercial')}
    onPointerEnter={(event) => { if (event.pointerType === 'mouse') setHovered(true) }} onPointerLeave={() => setHovered(false)}
    onFocusCapture={() => setFocused(true)} onBlurCapture={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false) }}>
    <div className="commercial-ad__header"><div className="commercial-ad__eyebrow"><Megaphone aria-hidden="true" />{t('Publicidad')}</div></div>
    {loading ? <p role="status">{t('Cargando publicidad…')}</p> : failed ? <p role="status">{t('No se pudo cargar la publicidad. Inténtalo más tarde.')}</p> : <>
      <div className="commercial-ad__slides" ref={viewport} data-single={slideCount === 1} onTouchStart={() => setTouching(true)} onTouchEnd={() => setTouching(false)} onTouchCancel={() => setTouching(false)}
        onScroll={(event) => {
          const element = event.currentTarget
          let nearest = 0
          for (let index = 1; index < element.children.length; index++) {
            if (Math.abs(centeredOffset(element, element.children[index] as HTMLElement) - element.scrollLeft) < Math.abs(centeredOffset(element, element.children[nearest] as HTMLElement) - element.scrollLeft)) nearest = index
          }
          setSlide(nearest)
        }}>
        {Array.from({ length: slideCount }, (_, index) => {
          const ad = ads[index]
          if (!ad) return <div className="commercial-ad__slot commercial-ad__slot--empty" key={`empty-${index}`} aria-hidden={index !== activeSlide} inert={index !== activeSlide} data-testid="advertising-slot"><h2>{t('Tu anuncio podría estar aquí')}</h2></div>
          const isExternal = /^https?:/.test(ad.destinationUrl)
          return <article className="commercial-ad__slot" key={ad.id} aria-hidden={index !== activeSlide} inert={index !== activeSlide} data-testid="advertising-slot" data-ad-id={ad.id}>
            <div className="commercial-ad__visual">{imageFailures.has(ad.id) ? <Megaphone aria-hidden="true" /> : <img data-i18n-exempt src={adImageUrl(ad.imageUrl)} width={ad.imageWidth} height={ad.imageHeight} loading="lazy" decoding="async" alt={ad.title} onError={() => setImageFailures((current) => new Set(current).add(ad.id))} />}</div>
            <div className="commercial-ad__copy"><h2 data-i18n-exempt>{ad.title}</h2><p data-i18n-exempt>{ad.description}</p><a className="commercial-ad__more" href={ad.destinationUrl} target={isExternal ? '_blank' : undefined} rel={isExternal ? 'noopener noreferrer sponsored' : 'sponsored'}>{t('Más información')}<ArrowUpRight aria-hidden="true" /></a></div>
          </article>
        })}
      </div>
      {slideCount > 1 ? <div className="commercial-ad__carousel">
        <button type="button" className="commercial-ad__carousel-arrow" aria-label={t('Publicidad anterior')} onClick={() => move(-1)}><ChevronLeft aria-hidden="true" /></button>
        <span className="commercial-ad__carousel-position" aria-live={focused ? 'polite' : 'off'} aria-atomic="true">{activeSlide + 1} / {slideCount}</span>
        <div className="commercial-ad__carousel-dots">{Array.from({ length: slideCount }, (_, index) => <button type="button" key={index} className={index === activeSlide ? 'is-active' : ''} aria-label={`${t('Publicidad')} ${index + 1}`} aria-current={index === activeSlide ? 'true' : undefined} onClick={() => showSlide(index)} />)}</div>
        <button type="button" className="commercial-ad__carousel-arrow" aria-label={t('Publicidad siguiente')} onClick={() => move(1)}><ChevronRight aria-hidden="true" /></button>
      </div> : null}
    </>}
    {available === 0 ? <AdvertisingVacancy /> : <div className="commercial-ad__house"><div>{failed ? <h2>{t('Tu anuncio podría estar aquí')}</h2> : null}<p>{t('Da a conocer tu negocio a la comunidad de 112233.es.')}</p></div><Link className="commercial-ad__cta" to="/publicidad/nueva">{t('Publicar publicidad')}<ArrowUpRight aria-hidden="true" /></Link></div>}
  </section>
}
