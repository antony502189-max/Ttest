import { useEffect, useState } from 'react'
import { useLocation } from 'react-router'
import { PublishExactAddressSync } from '@/components/publish-exact-address-sync'
import { PublishSmartAddressAutocomplete } from '@/components/publish-smart-address-autocomplete'

type AddressComponent = { longText?: string; long_name?: string; types: string[] }
type AddressDetail = { addressComponents?: AddressComponent[] }

const DRAFT_KEY = '112233:listing-draft:v3'

function readPublicationKey() {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    if (!raw) return ''
    const parsed = JSON.parse(raw) as { data?: { publicationKey?: string } }
    return parsed.data?.publicationKey ?? ''
  } catch {
    return ''
  }
}

function component(components: AddressComponent[], type: string) {
  const item = components.find((entry) => entry.types.includes(type))
  return (item?.longText ?? item?.long_name ?? '').trim()
}

function normalize(value: string) {
  return value.trim().toLocaleLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

function setAddressSyncedValue(element: HTMLInputElement | null, value: string) {
  if (!element || element.value === value) return
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
  element.dataset.locationAddressSync = 'true'
  try {
    setter?.call(element, value)
    element.dispatchEvent(new Event('input', { bubbles: true }))
    element.dispatchEvent(new Event('change', { bubbles: true }))
  } finally {
    delete element.dataset.locationAddressSync
  }
}

function PublishPostcodeAreaNormalizer() {
  useEffect(() => {
    const handleResolved = (event: Event) => {
      const street = document.querySelector<HTMLInputElement>('#publish-street')?.value.trim() ?? ''
      const postcode = document.querySelector<HTMLInputElement>('#publish-postcode')?.value.trim() ?? ''
      if (street || !/^\d{5}$/.test(postcode)) return

      const components = (event as CustomEvent<AddressDetail>).detail?.addressComponents ?? []
      const municipality = component(components, 'administrative_area_level_3')
        || component(components, 'administrative_area_level_4')
      const locality = component(components, 'locality')
      const area = component(components, 'sublocality_level_1')
        || component(components, 'sublocality')
        || component(components, 'neighborhood')
        || (locality && normalize(locality) !== normalize(municipality) ? locality : '')
        || municipality
        || locality

      setAddressSyncedValue(document.querySelector<HTMLInputElement>('#publish-area'), area)
    }

    window.addEventListener('112233:map-address-resolved', handleResolved)
    return () => window.removeEventListener('112233:map-address-resolved', handleResolved)
  }, [])

  return null
}

export function PublishAddressLifecycle() {
  const { pathname } = useLocation()
  const [publicationKey, setPublicationKey] = useState(readPublicationKey)

  useEffect(() => {
    const sync = () => {
      const next = readPublicationKey()
      setPublicationKey((current) => current === next ? current : next)
    }
    const observer = new MutationObserver(sync)
    observer.observe(document.body, { childList: true, subtree: true })
    window.addEventListener('storage', sync)
    sync()
    return () => {
      observer.disconnect()
      window.removeEventListener('storage', sync)
    }
  }, [pathname])

  return <>
    <PublishExactAddressSync key={`${pathname}:${publicationKey}`} />
    <PublishSmartAddressAutocomplete />
    <PublishPostcodeAreaNormalizer />
  </>
}
