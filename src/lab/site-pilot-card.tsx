import type { Listing } from '@/types'

export function PropertyCard({ listing }: { listing: Listing }) {
  let source: URL | undefined
  try {
    const url = new URL(listing.sourceUrl ?? '')
    if (url.protocol === 'https:' && ['www.pisocompartido.com', 'pisocompartido.com'].includes(url.hostname)) source = url
  } catch { /* No guessed links or ordinary marketplace routes. */ }
  return <article style={{ border: '1px solid #cbd5c0', borderRadius: 12, padding: 16 }} data-i18n-exempt>
    <h4>{listing.title}</h4><p>{listing.city} · {listing.area}</p>
    <p>{listing.price} € / месяц</p>
    <p>Источник: {listing.primarySource}</p>
    {source ? <a href={source.href} target="_blank" rel="noopener noreferrer">Открыть публичное объявление</a> : null}
  </article>
}
