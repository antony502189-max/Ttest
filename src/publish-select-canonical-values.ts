const canonicalPublishSelectValues: Record<string, readonly string[]> = {
  'publish-bathroom': ['Baño compartido', 'Baño privado'],
  'publish-toilet': ['Aseo compartido', 'Aseo privado'],
  'publish-shower': ['Ducha compartida', 'Ducha privada'],
  'publish-kitchen': ['Cocina compartida', 'Cocina privada'],
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
  stabilizePublishSelectValues()
  const observer = new MutationObserver(stabilizePublishSelectValues)
  observer.observe(document.documentElement, { childList: true, subtree: true })
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startPublishSelectValueStabilizer, { once: true })
} else {
  startPublishSelectValueStabilizer()
}
