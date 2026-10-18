import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '@/api/client'
import { useI18n } from '@/contexts/i18n-context'

type Availability = { municipality: string; available: boolean; availableSlots: number; availableAt: string | null; serverNow: string }

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
        const delta = result.availableAt ? Date.parse(result.availableAt) - Date.parse(result.serverNow) : NaN
        deadline = Number.isFinite(delta) ? performance.now() + Math.max(0, delta) : null
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
    es: { loading: 'Comprobando plazas TOP…', province: 'Municipio del propietario', free: 'Plazas TOP disponibles', full: 'En este momento todas las plazas TOP de este municipio están ocupadas.', wait: 'Podrás comprar dentro de', pending: 'Pendiente de confirmación de otros pagos. La disponibilidad se actualiza automáticamente.', address: 'Verifica la dirección del propietario en tu perfil.', unavailable: 'No se pudo comprobar la disponibilidad. Inténtalo de nuevo.' },
    ru: { loading: 'Проверяем места TOP…', province: 'Муниципалитет владельца', free: 'Свободных мест TOP', full: 'На данный момент все места TOP в этом муниципалитете заняты.', wait: 'Вы сможете купить через', pending: 'Ожидается подтверждение других оплат. Доступность обновляется автоматически.', address: 'Проверьте адрес владельца в профиле.', unavailable: 'Не удалось проверить свободные места. Попробуйте ещё раз.' },
    en: { loading: 'Checking TOP places…', province: 'Owner municipality', free: 'Available TOP places', full: 'All TOP places in this municipality are currently occupied.', wait: 'You can buy in', pending: 'Awaiting confirmation of other payments. Availability updates automatically.', address: 'Verify the owner address in your profile.', unavailable: 'Could not check availability. Please try again.' },
  }[language]
  if (state.error) return <span role="alert">{state.error.includes('address') ? <Link to="/perfil">{copy.address}</Link> : copy.unavailable}</span>
  if (!state.availability) return <span role="status">{copy.loading}</span>
  const seconds = state.remaining
  const countdown = seconds === null ? null : [Math.floor(seconds / 3600), Math.floor(seconds / 60) % 60, seconds % 60].map((value) => String(value).padStart(2, '0')).join(':')
  return <div className="owner-top-dialog__next" data-testid="province-top-availability">
    <span>{copy.province}: <strong>{state.availability.municipality}</strong></span>
    {state.availability.available ? <span>{copy.free}: {state.availability.availableSlots} / 3</span> : <>
      <span role="status">{copy.full}</span>
      {countdown ? <span>{copy.wait} <strong role="timer" aria-live="off">{countdown}</strong></span> : <span>{copy.pending}</span>}
    </>}
  </div>
}
