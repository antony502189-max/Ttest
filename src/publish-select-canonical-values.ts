const canonicalPublishSelectValues: Record<string, readonly string[]> = {
  'publish-bathroom': ['Baño compartido', 'Baño privado'],
  'publish-toilet': ['Aseo compartido', 'Aseo privado'],
  'publish-shower': ['Ducha compartida', 'Ducha privada'],
  'publish-kitchen': ['Cocina compartida', 'Cocina privada'],
}

const canonicalDraftValues: Record<string, string> = {
  'Baño compartido': 'Baño compartido',
  'Baño privado': 'Baño privado',
  'Общая ванная': 'Baño compartido',
  'Собственная ванная': 'Baño privado',
  'Shared bathroom': 'Baño compartido',
  'Private bathroom': 'Baño privado',

  'Aseo compartido': 'Aseo compartido',
  'Aseo privado': 'Aseo privado',
  'Общий туалет': 'Aseo compartido',
  'Собственный туалет': 'Aseo privado',
  'Shared toilet': 'Aseo compartido',
  'Private toilet': 'Aseo privado',

  'Ducha compartida': 'Ducha compartida',
  'Ducha privada': 'Ducha privada',
  'Общий душ': 'Ducha compartida',
  'Собственный душ': 'Ducha privada',
  'Shared shower': 'Ducha compartida',
  'Private shower': 'Ducha privada',

  'Cocina compartida': 'Cocina compartida',
  'Cocina privada': 'Cocina privada',
  'Общая кухня': 'Cocina compartida',
  'Собственная кухня': 'Cocina privada',
  'Shared kitchen': 'Cocina compartida',
  'Private kitchen': 'Cocina privada',
}

const draftFields = ['bathroom', 'toilet', 'shower', 'kitchen'] as const

function normalizeDraftObject(value: unknown): boolean {
  if (!value || typeof value !== 'object') return false
  const draft = value as Record<string, unknown>
  let changed = false

  for (const field of draftFields) {
    const current = draft[field]
    if (typeof current !== 'string') continue
    const canonical = canonicalDraftValues[current]
    if (!canonical || canonical === current) continue
    draft[field] = canonical
    changed = true
  }

  return changed
}

function migrateStoredPublicationDrafts() {
  const keys = ['112233:listing-draft:v3', '112233:listing-draft:v2'] as const

  for (const key of keys) {
    try {
      const raw = localStorage.getItem(key)
      if (!raw) continue
      const parsed = JSON.parse(raw) as unknown
      const draft = key.endsWith(':v3') && parsed && typeof parsed === 'object'
        ? (parsed as Record<string, unknown>).data
        : parsed
      if (normalizeDraftObject(draft)) localStorage.setItem(key, JSON.stringify(parsed))
    } catch {
      // PublishPage already falls back safely when a stored draft is malformed.
      // Keep that behavior and avoid making startup depend on draft migration.
    }
  }
}

function stabilizePublishSelectValues() {
  for (const [id, values] of Object.entries(canonicalPublishSelectValues)) {
    const select = document.getElementById(id)
    if (!(select instanceof HTMLSelectElement)) continue

    values.forEach((value, index) => {
      const option = select.options.item(index)
      if (!option) return
      // These four legacy selects render localized text as their option body.
      // Without an explicit value attribute, translating that body also changes
      // HTMLSelectElement.value and leaks localized strings into ListingDraft.
      // Keep the UI label translatable while pinning the domain value expected
      // by the frontend model and backend schema.
      if (option.getAttribute('value') !== value) option.setAttribute('value', value)
    })
  }
}

function startPublishSelectValueStabilizer() {
  migrateStoredPublicationDrafts()
  stabilizePublishSelectValues()
  const observer = new MutationObserver(stabilizePublishSelectValues)
  observer.observe(document.documentElement, { childList: true, subtree: true })
}

if (document.readyState === 'loading') {
  // Run migration immediately so React hydrates from canonical draft values.
  migrateStoredPublicationDrafts()
  document.addEventListener('DOMContentLoaded', startPublishSelectValueStabilizer, { once: true })
} else {
  startPublishSelectValueStabilizer()
}
