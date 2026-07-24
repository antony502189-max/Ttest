import { useEffect, useMemo, useState } from 'react'
import { ArrowDownUp, ArrowLeft, ChevronDown, Heart, Map, MessageSquare, Phone, SlidersHorizontal, Trash2, X } from 'lucide-react'
import { useApp } from '@/contexts/app-context'
import { cn } from '@/lib/utils'
import type { Listing } from '@/types'
import '@/mobile-listings-experience.css'

type Lang = 'es' | 'en' | 'ru'
type Panel = 'results' | 'filters' | 'sort'
type Sort = 'relevance' | 'cheap' | 'expensive' | 'saved-new' | 'saved-old' | 'reduced' | 'sqm-cheap' | 'sqm-expensive' | 'area-large' | 'area-small' | 'floor-high' | 'floor-low'
type Tx = 'buy' | 'rent'
type RentKind = 'long' | 'holiday'
type Filters = { tx: Tx; minPrice: number; maxPrice: number; minArea: number; maxArea: number; types: string[]; rooms: number[]; rentKinds: RentKind[] }

const defaults: Filters = { tx: 'rent', minPrice: 0, maxPrice: 1500, minArea: 0, maxArea: 50, types: [], rooms: [], rentKinds: ['long', 'holiday'] }
const sorts: Sort[] = ['relevance', 'cheap', 'expensive', 'saved-new', 'saved-old', 'reduced', 'sqm-cheap', 'sqm-expensive', 'area-large', 'area-small', 'floor-high', 'floor-low']
const copy = {
  es: { back:'Volver',close:'Cerrar',results:'viviendas',zone:'Tenerife',filters:'Filtros',order:'Orden',map:'Mapa',showing:'Mostrando',of:'de',top:'Destacado',contact:'Contactar',call:'Llamar',discard:'Descartar',favorite:'Favorito',buy:'Comprar',rent:'Alquilar',property:'Tipo de inmueble',residential:'Viviendas',price:'Precio',area:'Superficie',min:'Mín',max:'Máx',housing:'Tipo de vivienda',rooms:'Número de habitaciones',one:'1 habitación',two:'2 habitaciones',individual:'Habitaciones individuales',shared:'Habitaciones compartidas',studio:'Estudios',rentType:'Tipo de alquiler',long:'Larga estancia',holiday:'Turismo',show:'Ver anuncios',clear:'Limpiar',empty:'No hay anuncios que coincidan con estos filtros.',relevance:'Relevancia',cheap:'Más baratos',expensive:'Más caros',savedNew:'Guardados recientemente',savedOld:'Guardados anteriormente',reduced:'Precio rebajado',sqmCheap:'Menor precio por m²',sqmExpensive:'Mayor precio por m²',areaLarge:'Mayor superficie',areaSmall:'Menor superficie',floorHigh:'Plantas altas',floorLow:'Plantas bajas'},
  en: { back:'Back',close:'Close',results:'properties',zone:'Tenerife',filters:'Filters',order:'Order',map:'Map',showing:'Showing',of:'of',top:'Featured',contact:'Contact',call:'Call',discard:'Discard',favorite:'Favorite',buy:'Buy',rent:'Rent',property:'Property type',residential:'Residential properties',price:'Price',area:'Area',min:'Min',max:'Max',housing:'Property category',rooms:'Number of rooms',one:'1 room',two:'2 rooms',individual:'Individual rooms',shared:'Shared rooms',studio:'Studios',rentType:'Rental type',long:'Long stay',holiday:'Tourism',show:'View listings',clear:'Clear',empty:'No listings match these filters.',relevance:'Relevance',cheap:'Cheapest',expensive:'Most expensive',savedNew:'Saved recently',savedOld:'Saved earlier',reduced:'Reduced price',sqmCheap:'Lowest price per m²',sqmExpensive:'Highest price per m²',areaLarge:'Largest area',areaSmall:'Smallest area',floorHigh:'Upper floors',floorLow:'Lower floors'},
  ru: { back:'Назад',close:'Закрыть',results:'объявлений',zone:'Тенерифе',filters:'Фильтры',order:'Порядок',map:'Карта',showing:'Просмотр',of:'из',top:'Топ',contact:'Связаться',call:'Позвонить',discard:'Скрыть',favorite:'Избранное',buy:'Купить',rent:'Снять',property:'Тип недвижимости',residential:'Жилые объекты',price:'Цена',area:'Площадь',min:'Мин',max:'Макс',housing:'Тип жилья',rooms:'Количество комнат',one:'1 комната',two:'2 комнаты',individual:'Отдельные комнаты',shared:'Общие комнаты',studio:'Студии',rentType:'Тип аренды',long:'Долгосрочная',holiday:'Туризм',show:'Перейти к объявлениям',clear:'Сбросить',empty:'Нет объявлений, подходящих под выбранные фильтры.',relevance:'Релевантность',cheap:'Дешевые',expensive:'Дорогие',savedNew:'Сохраненные недавно',savedOld:'Сохраненные раньше',reduced:'Со сниженной ценой',sqmCheap:'Дешевые евро/м²',sqmExpensive:'Дорогие евро/м²',areaLarge:'С большей площадью',areaSmall:'С меньшей площадью',floorHigh:'Верхние этажи',floorLow:'Нижние этажи'},
} as const

const lang = (): Lang => { try { const v = localStorage.getItem('112233:mobile-language:v2'); return v === 'en' || v === 'ru' ? v : 'es' } catch { return 'es' } }
const toggle = <T,>(items:T[], value:T) => items.includes(value) ? items.filter((item) => item !== value) : [...items, value]
const floorOf = (listing:Listing) => [...listing.id].reduce((n, ch) => (n * 31 + ch.charCodeAt(0)) % 11, 0)

function sortName(t: typeof copy.es, value: Sort) {
  const names: Record<Sort,string> = { relevance:t.relevance,cheap:t.cheap,expensive:t.expensive,'saved-new':t.savedNew,'saved-old':t.savedOld,reduced:t.reduced,'sqm-cheap':t.sqmCheap,'sqm-expensive':t.sqmExpensive,'area-large':t.areaLarge,'area-small':t.areaSmall,'floor-high':t.floorHigh,'floor-low':t.floorLow }
  return names[value]
}

function ListingCard({ listing, t, favorite, onFavorite, onDiscard }:{ listing:Listing; t:typeof copy.es; favorite:boolean; onFavorite:()=>void; onDiscard:()=>void }) {
  const phone = listing.contactPhone?.replace(/\s+/g,'')
  const wa = listing.contactWhatsapp?.replace(/\D/g,'')
  return <article className="ml-card" data-listing-id={listing.id}>
    <div className="ml-card__image-wrap"><img src={listing.images[0]} alt={listing.title} loading="lazy" /><span className="ml-card__photo-count">1/{listing.images.length}</span><span className="ml-card__featured">{t.top}</span></div>
    <div className="ml-card__body"><div className="ml-card__media-icons" aria-hidden="true"><span>▧</span><span>⌂</span><span>3D</span><span>▣</span><span>⌖</span></div><h2>{listing.title}</h2><strong className="ml-card__price">{new Intl.NumberFormat('es-ES').format(listing.price)} € <small>/{listing.cadence}</small></strong><p className="ml-card__meta"><span>{listing.roomType}</span><span>{listing.roomSizeM2} m²</span><span>{listing.area}</span></p><span className="ml-card__tag">{listing.advertiserType}</span>
      <div className="ml-card__actions">{wa ? <a href={`https://wa.me/${wa}`} target="_blank" rel="noreferrer"><MessageSquare />{t.contact}</a> : null}{phone ? <a href={`tel:${phone}`}><Phone />{t.call}</a> : null}<button type="button" className="ml-icon-action" onClick={onDiscard} aria-label={t.discard}><Trash2 /></button><button type="button" className={cn('ml-icon-action',favorite&&'is-active')} onClick={onFavorite} aria-label={t.favorite} aria-pressed={favorite}><Heart /></button></div>
    </div>
  </article>
}

export function MobileListingsExperience() {
  const { allListings, favorites, toggleFavorite, discarded, discardListing } = useApp()
  const [open,setOpen] = useState(false), [panel,setPanel] = useState<Panel>('results'), [language,setLanguage] = useState<Lang>(lang), [filters,setFilters] = useState<Filters>(defaults), [sort,setSort] = useState<Sort>('relevance')
  const t = copy[language] as typeof copy.es

  useEffect(() => { const timer = setInterval(() => { const next=lang(); setLanguage((cur)=>cur===next?cur:next) },400); return ()=>clearInterval(timer) },[])
  useEffect(() => {
    const handler = (event:MouseEvent) => {
      if (!matchMedia('(max-width: 767px)').matches) return
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>('button,a') : null
      if (!target) return
      const mainSearch = target.matches('[data-testid="open-location"]')
      const mapList = Boolean(target.closest('.m2-map-toolbar')) && /listado|list|перечень/i.test(target.textContent??'')
      if (!mainSearch && !mapList) return
      event.preventDefault(); event.stopPropagation(); event.stopImmediatePropagation(); setLanguage(lang()); setPanel('results'); setOpen(true)
    }
    document.addEventListener('click',handler,true); return ()=>document.removeEventListener('click',handler,true)
  },[])
  useEffect(() => { if (!open) return; const old=document.body.style.overflow; document.body.style.overflow='hidden'; return()=>{document.body.style.overflow=old} },[open])

  const base = useMemo(()=>allListings.filter((x)=>x.status==='Publicado'&&!discarded.has(x.id)),[allListings,discarded])
  const filtered = useMemo(()=>base.filter((x)=>x.price>=filters.minPrice&&x.price<=filters.maxPrice&&x.roomSizeM2>=filters.minArea&&x.roomSizeM2<=filters.maxArea&&(!filters.types.length||filters.types.includes(x.roomType))&&(!filters.rooms.length||filters.rooms.includes(x.roomCapacity))&&(filters.tx==='buy'||!filters.rentKinds.length||filters.rentKinds.includes(x.rentalMode))),[base,filters])
  const sorted = useMemo(()=>[...filtered].sort((a,b)=>{
    if(sort==='cheap')return a.price-b.price;if(sort==='expensive')return b.price-a.price;if(sort==='saved-new')return Number(favorites.has(b.id))-Number(favorites.has(a.id))||+new Date(b.publishedAt)-+new Date(a.publishedAt);if(sort==='saved-old')return Number(favorites.has(b.id))-Number(favorites.has(a.id))||+new Date(a.publishedAt)-+new Date(b.publishedAt);if(sort==='reduced')return a.price-b.price||b.views-a.views;if(sort==='sqm-cheap')return a.price/a.roomSizeM2-b.price/b.roomSizeM2;if(sort==='sqm-expensive')return b.price/b.roomSizeM2-a.price/a.roomSizeM2;if(sort==='area-large')return b.roomSizeM2-a.roomSizeM2;if(sort==='area-small')return a.roomSizeM2-b.roomSizeM2;if(sort==='floor-high')return floorOf(b)-floorOf(a);if(sort==='floor-low')return floorOf(a)-floorOf(b);return +new Date(b.publishedAt)-+new Date(a.publishedAt)
  }),[favorites,filtered,sort])

  const openMap = () => { setOpen(false); if(document.querySelector('.m2-map-screen'))return; document.querySelector<HTMLButtonElement>('.m2-select-row')?.click(); setTimeout(()=>document.querySelector<HTMLButtonElement>('[data-testid="search-map"]')?.click(),80) }
  if(!open)return null

  return <section className="ml-shell notranslate" translate="no">
    {panel==='results'?<><header className="ml-results-header"><button type="button" onClick={()=>setOpen(false)} aria-label={t.back}><ArrowLeft /></button><div><strong>{sorted.length} {t.results}</strong><small>{t.zone}</small></div></header><nav className="ml-results-toolbar"><button type="button" onClick={()=>setPanel('filters')}><SlidersHorizontal />{t.filters}</button><button type="button" onClick={()=>setPanel('sort')}><ArrowDownUp />{t.order}</button><button type="button" onClick={openMap}><Map />{t.map}</button></nav><div className="ml-results-summary">{t.showing} {sorted.length} {t.of} {base.length}</div><main className="ml-results-list">{sorted.length?sorted.map((x)=><ListingCard key={x.id} listing={x} t={t} favorite={favorites.has(x.id)} onFavorite={()=>toggleFavorite(x.id)} onDiscard={()=>discardListing(x.id)} />):<div className="ml-empty">{t.empty}</div>}</main></>:null}
    {panel==='sort'?<div className="ml-sheet-page"><header><button type="button" onClick={()=>setPanel('results')} aria-label={t.close}><X /></button><strong>{t.order}</strong></header><div className="ml-sort-list" role="radiogroup">{sorts.map((value)=><button key={value} type="button" role="radio" aria-checked={sort===value} onClick={()=>{setSort(value);setPanel('results')}}><span>{sortName(t,value)}</span><i>{sort===value?'●':''}</i></button>)}</div></div>:null}
    {panel==='filters'?<div className="ml-sheet-page ml-filter-page"><header><button type="button" onClick={()=>setPanel('results')} aria-label={t.close}><X /></button><strong>{t.filters}</strong><button type="button" className="ml-clear" onClick={()=>setFilters({...defaults,types:[],rooms:[],rentKinds:['long','holiday']})}>{t.clear}</button></header><div className="ml-filter-scroll"><div className="ml-transaction"><button type="button" className={cn(filters.tx==='buy'&&'is-active')} onClick={()=>setFilters((f)=>({...f,tx:'buy'}))}>{t.buy}</button><button type="button" className={cn(filters.tx==='rent'&&'is-active')} onClick={()=>setFilters((f)=>({...f,tx:'rent'}))}>{t.rent}</button></div><label className="ml-select-field"><span>{t.property}</span><select defaultValue="residential"><option value="residential">{t.residential}</option></select><ChevronDown /></label>
      <fieldset><legend>{t.price}</legend><div className="ml-two-fields"><label><span>{t.min}</span><input type="number" min="0" value={filters.minPrice} onChange={(e)=>setFilters((f)=>({...f,minPrice:+e.target.value||0}))}/></label><label><span>{t.max}</span><input type="number" min="0" value={filters.maxPrice} onChange={(e)=>setFilters((f)=>({...f,maxPrice:+e.target.value||0}))}/></label></div></fieldset>
      <fieldset><legend>{t.area}</legend><div className="ml-two-fields"><label><span>{t.min}</span><input type="number" min="0" value={filters.minArea} onChange={(e)=>setFilters((f)=>({...f,minArea:+e.target.value||0}))}/></label><label><span>{t.max}</span><input type="number" min="0" value={filters.maxArea} onChange={(e)=>setFilters((f)=>({...f,maxArea:+e.target.value||0}))}/></label></div></fieldset>
      <fieldset><legend>{t.rooms}</legend><div className="ml-check-list">{[[1,t.one],[2,t.two]].map(([value,label])=><label key={String(value)}><input type="checkbox" checked={filters.rooms.includes(value as number)} onChange={()=>setFilters((f)=>({...f,rooms:toggle(f.rooms,value as number)}))}/><span>{label}</span></label>)}</div></fieldset>
      <fieldset><legend>{t.housing}</legend><div className="ml-check-list">{[['Habitación individual',t.individual],['Habitación compartida',t.shared],['Estudio',t.studio]].map(([value,label])=><label key={value}><input type="checkbox" checked={filters.types.includes(value)} onChange={()=>setFilters((f)=>({...f,types:toggle(f.types,value)}))}/><span>{label}</span></label>)}</div></fieldset>
      {filters.tx==='rent'?<fieldset><legend>{t.rentType}</legend><div className="ml-check-list">{[['long',t.long],['holiday',t.holiday]].map(([value,label])=><label key={value}><input type="checkbox" checked={filters.rentKinds.includes(value as RentKind)} onChange={()=>setFilters((f)=>({...f,rentKinds:toggle(f.rentKinds,value as RentKind)}))}/><span>{label}</span></label>)}</div></fieldset>:null}</div><div className="ml-filter-footer"><button type="button" onClick={()=>setPanel('results')}>{t.show} · {sorted.length}</button></div></div>:null}
  </section>
}
