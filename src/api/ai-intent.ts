import type { RentalMode } from '@/types'

type Criterion<T> = { strength: 'hard' | 'soft'; value: T }
export type AICriteria = {
  rental_mode?: Criterion<RentalMode>
  budget?: Criterion<{ amount: string; currency: 'EUR'; period: 'monthly' | 'nightly' | 'weekly' }>
  geography?: Criterion<{ province_code: string; municipality_code?: string; zone_id?: string }>
  accommodation?: Criterion<{ kind: 'room' | 'shared_room' | 'studio' | 'one_bedroom' | 'catalog_other'; catalog_code?: string }>
  party?: Criterion<{ adults: number; children: number; relationship: 'couple' | 'friends' | 'family' | 'unspecified' }>
  pets?: Criterion<{ species: 'dog' | 'cat' | 'other'; size: 'small' | 'medium' | 'large' | 'unspecified'; count: number }[]>
  smoking?: Criterion<{ scope: 'indoors' | 'outdoors' | 'balcony' | 'terrace' }>
  furnished?: Criterion<boolean>
  bills_included?: Criterion<boolean>
  deposit?: Criterion<{ kind: 'money'; amount: string; currency: 'EUR'; period: 'one_off' } | { kind: 'quantity'; value: number; unit: 'months' }>
  balcony?: Criterion<boolean>
  terrace?: Criterion<boolean>
  amenities?: Criterion<string[]>
  dates?: Criterion<{ check_in: string; check_out: string }>
  stay?: Criterion<{ value: number; unit: 'nights' | 'months' }>
}
export type AIIntent = { schema_version: 'ai-search.v1'; taxonomy_version: 'rental.v1'; session_id: string; version: number; criteria: AICriteria }
export type AICommittedIntent = { result_ref: string; count: number; intent_hash: string; intent: AIIntent }
export type ConditionRow = { name: keyof AICriteria; strength: 'hard' | 'soft'; label: string; value: string }
type Translate = (source: string) => string

function check(ok: unknown): asserts ok { if (!ok) throw new Error('Unsupported intent') }
function object(value: unknown, required: string[], optional: string[] = []): Record<string, unknown> {
  check(value !== null && typeof value === 'object' && !Array.isArray(value))
  const row = value as Record<string, unknown>
  check(required.every(key => Object.hasOwn(row, key)) && Object.keys(row).every(key => [...required, ...optional].includes(key)))
  return row
}
function choice(value: unknown, labels: Record<string, string>, t: Translate): string {
  check(typeof value === 'string' && Object.hasOwn(labels, value))
  return t(labels[value])
}
function quantity(value: unknown, min = 1, max = 2147483647): string {
  check(typeof value === 'number' && Number.isSafeInteger(value) && value >= min && value <= max)
  return String(value)
}
function code(value: unknown, pattern = /^[a-z0-9][a-z0-9_-]{0,63}$/): string {
  check(typeof value === 'string' && pattern.test(value))
  return value
}
function money(value: unknown): string { check(typeof value === 'string' && value.length <= 16 && /^(0|[1-9][0-9]*)(\.[0-9]{1,2})?$/.test(value)); return value }
function list(value: unknown, max: number): unknown[] { check(Array.isArray(value) && value.length > 0 && value.length <= max); return value }
function date(value: unknown): string {
  const text = code(value, /^\d{4}-\d{2}-\d{2}$/)
  check(Number.isFinite(Date.parse(text)) && new Date(text).toISOString().slice(0, 10) === text)
  return text
}
const modeLabels = { long: 'Vivienda', holiday: 'Turismo' }
export const aiModeLabel = (mode: RentalMode, t: Translate) => choice(mode, modeLabels, t)

// Validate the whole summary before showing any of it. New schemas, fields or
// enum values must never produce a plausible but incomplete list of conditions.
export function aiConditionRows(intent: AIIntent, t: Translate): ConditionRow[] | null {
  try {
    object(intent, ['schema_version', 'taxonomy_version', 'session_id', 'version', 'criteria'])
    check(intent.schema_version === 'ai-search.v1' && intent.taxonomy_version === 'rental.v1')
    code(intent.session_id, /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i)
    quantity(intent.version, 0)
    const formatters: { [K in keyof AICriteria]-?: (value: unknown) => [string, string] } = {
      rental_mode: value => ['Modo de alquiler', choice(value, modeLabels, t)],
      budget: value => {
        const v = object(value, ['amount', 'currency', 'period']); check(v.currency === 'EUR')
        return ['Presupuesto máximo', `${money(v.amount)} EUR / ${choice(v.period, { monthly: 'mes', nightly: 'noche', weekly: 'semana' }, t)}`]
      },
      geography: value => {
        const v = object(value, ['province_code'], ['municipality_code', 'zone_id'])
        const parts = [`${t('Provincia INE')}: ${code(v.province_code, /^\d{2}$/)}`]
        if (v.municipality_code !== undefined) {
          const municipality = code(v.municipality_code, /^\d{5}$/); check(municipality.startsWith(String(v.province_code)))
          parts.push(`${t('Municipio INE')}: ${municipality}`)
        }
        if (v.zone_id !== undefined) { check(v.municipality_code !== undefined); parts.push(`${t('Código de zona')}: ${code(v.zone_id)}`) }
        return ['Ubicación', parts.join(' · ')]
      },
      accommodation: value => {
        const v = object(value, ['kind'], ['catalog_code'])
        const label = choice(v.kind, { room: 'Habitación', shared_room: 'Habitación compartida', studio: 'Estudio', one_bedroom: 'Un dormitorio', catalog_other: 'Código de alojamiento' }, t)
        check((v.kind === 'catalog_other') === (v.catalog_code !== undefined))
        return ['Alojamiento', v.kind === 'catalog_other' ? `${label}: ${code(v.catalog_code)}` : label]
      },
      party: value => {
        const v = object(value, ['adults', 'children', 'relationship'])
        const adults = quantity(v.adults, 1, 10), children = quantity(v.children, 0, 10); check(Number(adults) + Number(children) <= 10)
        return ['Personas', `${t('Adultos')}: ${adults} · ${t('Niños')}: ${children} · ${choice(v.relationship, { couple: 'Pareja', friends: 'Amigos', family: 'Familia', unspecified: 'Sin especificar' }, t)}`]
      },
      pets: value => {
        const pets = list(value, 10), scopes = new Set<string>(); let count = 0
        const values = pets.map(pet => {
          const v = object(pet, ['species', 'size', 'count']); const scope = `${v.species}:${v.size}`
          check(!scopes.has(scope)); scopes.add(scope); count += Number(quantity(v.count, 1, 10))
          return `${choice(v.species, { dog: 'Perro', cat: 'Gato', other: 'Otro animal' }, t)} · ${choice(v.size, { small: 'Pequeño', medium: 'Mediano', large: 'Grande', unspecified: 'Sin especificar' }, t)} × ${v.count}`
        }); check(count <= 10)
        return ['Mascotas', values.join('; ')]
      },
      smoking: value => ['Fumar', choice(object(value, ['scope']).scope, { indoors: 'Interior', outdoors: 'Exterior', balcony: 'Balcón', terrace: 'Terraza' }, t)],
      furnished: value => ['Amueblado', boolean(value, t)],
      bills_included: value => ['Gastos incluidos', boolean(value, t)],
      deposit: value => {
        const v = object(value, ['kind'], ['amount', 'currency', 'period', 'value', 'unit'])
        if (v.kind === 'money') { object(v, ['kind', 'amount', 'currency', 'period']); check(v.currency === 'EUR' && v.period === 'one_off'); return ['Fianza máxima', `${money(v.amount)} EUR · ${t('Pago único')}`] }
        object(v, ['kind', 'value', 'unit']); check(v.kind === 'quantity' && v.unit === 'months')
        return ['Fianza máxima', `${quantity(v.value, 0)} ${t('meses')}`]
      },
      balcony: value => ['Balcón', boolean(value, t)],
      terrace: value => ['Terraza', boolean(value, t)],
      amenities: value => {
        const codes = list(value, 100).map(v => code(v)); check(new Set(codes).size === codes.length)
        return ['Códigos de servicios', codes.join(', ')]
      },
      dates: value => {
        const v = object(value, ['check_in', 'check_out']); const start = date(v.check_in), end = date(v.check_out); check(end > start)
        return ['Fechas', `${t('Entrada')}: ${start} · ${t('Salida')}: ${end}`]
      },
      stay: value => { const v = object(value, ['value', 'unit']); return ['Estancia', `${quantity(v.value)} ${choice(v.unit, { nights: 'noches', months: 'meses' }, t)}`] },
    }
    const criteria = object(intent.criteria, [], Object.keys(formatters))
    return Object.entries(criteria).map(([key, value]) => {
      const v = object(value, ['strength', 'value']); check(v.strength === 'hard' || v.strength === 'soft')
      const name = key as keyof AICriteria
      const [label, formatted] = formatters[name](v.value)
      return { name, strength: v.strength, label: t(label), value: formatted }
    })
  } catch { return null }
}
function boolean(value: unknown, t: Translate): string { check(typeof value === 'boolean'); return t(value ? 'Sí' : 'No') }
