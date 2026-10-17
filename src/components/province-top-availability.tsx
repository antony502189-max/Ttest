import { useCallback, useEffect, useState } from 'react'
import { api } from '@/api/client'
import { useI18n } from '@/contexts/i18n-context'

type Availability = { province: string; available: boolean; availableSlots: number; availableAt: string | null; serverNow: string }

export function useProvinceTopAvailability(listingId: string, days: number, enabled: boolean) {
  const [availability, setAvailability] = useState<Availability | null>(null)
  const [error, setError] = useState('')
  const [remaining, setRemaining] = useState<number | null>(null)
  const [revision, setRevision] = useState(0)
  const refresh = useCallback(() => setRevision((value) => value + 1), [])
  useEffect(() => {
    setAvailability(null); setError(''); setRemaining(null)
    if (!enabled || !listingId || !Number.isInteger(days) || days < 10 || days > 365) return
    const controller = new AbortController()
    let deadline: number | null = null
    let refreshing = false
    const load = async () => {
      if (refreshing) return
      refreshing = true
      try {
        const result = await api<Availability>(`/payments/listings/${listingId}/top/availability?days=${days}`, { signal: controller.signal })
        if (controller.signal.aborted) return
        deadline = result.availableAt ? performance.now() + Math.max(0, Date.parse(result.availableAt) - Date.parse(result.serverNow)) : null
        setAvailability(result); setError('')
        setRemaining(deadline === null ? null : Math.max(0, Math.ceil((deadline - performance.now()) / 1000)))
      } catch (reason) { if (!controller.signal.aborted) { setAvailability(null); setError((reason as Error).message) } }
      finally { refreshing = false }
    }
    void load()
    const poll = window.setInterval(() => { void load() }, 15000)
    const tick = window.setInterval(() => {
      if (deadline === null) return
      const seconds = Math.max(0, Math.ceil((deadline - performance.now()) / 1000))
      setRemaining(seconds)
      if (!seconds) { deadline = null; void load() }
    }, 1000)
    return () => { controller.abort(); window.clearInterval(poll); window.clearInterval(tick) }
  }, [days, enabled, listingId, revision])
  return { availability, error, remaining, refresh, canBuy: Boolean(availability?.available) && !error }
}

export function ProvinceTopAvailability({ state }: { state: ReturnType<typeof useProvinceTopAvailability> }) {
  const { language } = useI18n()
  const copy = {
    es: { loading: 'Comprobando plazas TOP…', province: 'Provincia del anuncio', free: 'Plazas TOP disponibles', full: 'En este momento todas las plazas TOP de esta provincia están ocupadas.', wait: 'Podrás comprar dentro de', pending: 'Pendiente de confirmación de otros pagos. La disponibilidad se actualiza automáticamente.', address: 'Comprueba el código postal del anuncio.', unavailable: 'No se pudo comprobar la disponibilidad. Inténtalo de nuevo.' },
    ru: { loading: 'Проверяем места TOP…', province: 'Провинция объявления', free: 'Свободных мест TOP', full: 'На данный момент все места TOP в этой провинции заняты.', wait: 'Вы сможете купить через', pending: 'Ожидается подтверждение других оплат. Доступность обновляется автоматически.', address: 'Проверьте почтовый индекс в адресе объявления.', unavailable: 'Не удалось проверить свободные места. Попробуйте ещё раз.' },
    en: { loading: 'Checking TOP places…', province: 'Listing province', free: 'Available TOP places', full: 'All TOP places in this province are currently occupied.', wait: 'You can buy in', pending: 'Awaiting confirmation of other payments. Availability updates automatically.', address: 'Check the postcode in the listing address.', unavailable: 'Could not check availability. Please try again.' },
  }[language]
  if (state.error) return <span role="alert">{state.error.includes('postcode') ? copy.address : copy.unavailable}</span>
  if (!state.availability) return <span role="status">{copy.loading}</span>
  const seconds = state.remaining
  const countdown = seconds === null ? null : [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60].map((value) => String(value).padStart(2, '0')).join(':')
  return <div className="owner-top-dialog__next" data-testid="province-top-availability">
    <span>{copy.province}: <strong>{state.availability.province}</strong></span>
    {state.availability.available ? <span>{copy.free}: {state.availability.availableSlots} / 3</span> : <>
      <span role="status">{copy.full}</span>
      {countdown ? <span>{copy.wait} <strong role="timer" aria-live="off">{countdown}</strong></span> : <span>{copy.pending}</span>}
    </>}
  </div>
}
