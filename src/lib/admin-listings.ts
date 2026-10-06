export type AdminRentalModeFilter = '' | 'long' | 'holiday'

export function adminRentalModeLabel(mode: string) {
  if (mode === 'long') return 'Larga estancia'
  if (mode === 'holiday') return 'Corta estancia'
  return '—'
}

export function matchesAdminRentalMode(mode: string, filter: AdminRentalModeFilter) {
  return !filter || mode === filter
}
