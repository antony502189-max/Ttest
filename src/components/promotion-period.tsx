import { CalendarDays } from 'lucide-react'
import { useI18n } from '@/contexts/i18n-context'
import { Button } from '@/components/ui/button'
import './promotion-period.css'

const DAY_MS = 86400000

function dateValue(value: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return NaN
  const time = Date.parse(`${value}T00:00:00Z`)
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value ? time : NaN
}

export function promotionDate(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

export function addPromotionDays(start: string, days: number) {
  return new Date(dateValue(start) + days * DAY_MS).toISOString().slice(0, 10)
}

export function promotionDays(start: string, end: string) {
  return (dateValue(end) - dateValue(start)) / DAY_MS
}

export function PromotionPeriod({ start, end, onChange }: { start: string; end: string; onChange: (date: string) => void }) {
  const { t, locale } = useI18n()
  const days = promotionDays(start, end)
  const valid = Number.isInteger(days) && days >= 10 && days <= 365
  const formatDate = (value: string) => new Intl.DateTimeFormat(locale, { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: 'UTC' }).format(dateValue(value))

  return <div className="promotion-period">
    <div className="promotion-period__presets" role="group" aria-label={t('Duración de TOP')}>
      {[10, 14, 21, 30].map((duration) => <Button type="button" key={duration} variant="outline" aria-pressed={days === duration} onClick={() => onChange(addPromotionDays(start, duration))}>{t(`${duration} días`)}</Button>)}
    </div>
    <label>{t('Desde')}<input type="date" value={start} readOnly aria-describedby="top-period-note" /></label>
    <label>{t('Hasta')}<input type="date" value={end} min={addPromotionDays(start, 10)} max={addPromotionDays(start, 365)} onChange={(event) => onChange(event.target.value)} aria-invalid={!valid} aria-describedby={!valid ? 'top-period-error top-period-note' : 'top-period-note'} /></label>
    {valid ? <div className="promotion-period__summary" aria-live="polite"><CalendarDays aria-hidden="true" /><span><strong>{t(`${days} días`)}</strong><small>{formatDate(start)} → {formatDate(end)}</small></span></div> : <p className="field-error" role="alert" id="top-period-error">{t('Elige un periodo de entre 10 y 365 días.')}</p>}
    <p className="promotion-period__note" id="top-period-note">{t('El plazo empieza cuando se confirma el pago. Si ya tienes TOP, se añaden los días al plazo actual.')}</p>
  </div>
}
