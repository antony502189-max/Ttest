export const publicationPhonePattern = /^\+?[\d\s-]{7,64}$/

type PublicationContact = {
  contactName: string
  contactPhone: string
  contactWhatsapp: string
  showPhone: boolean
  showWhatsApp: boolean
}

export function validatePublicationContact(contact: PublicationContact) {
  const errors: Record<string, string> = {}
  const name = contact.contactName.trim()
  if (name.length < 2 || name.length > 120) errors.contactName = "El nombre público debe tener entre 2 y 120 caracteres."

  for (const [field, value, label] of [
    ["contactPhone", contact.contactPhone, "teléfono"],
    ["contactWhatsapp", contact.contactWhatsapp, "WhatsApp"],
  ] as const) {
    const normalized = value.trim()
    if (!normalized) continue
    if (normalized.length > 64) errors[field] = `El ${label} no puede superar 64 caracteres.`
    else if (!publicationPhonePattern.test(normalized)) errors[field] = `Introduce un ${label} válido.`
  }

  if (contact.showPhone && !contact.contactPhone.trim()) errors.contactPhone = "Introduce un teléfono para mostrarlo."
  if (contact.showWhatsApp && !contact.contactWhatsapp.trim()) errors.contactWhatsapp = "Introduce un WhatsApp para mostrarlo."
  if (!contact.showPhone && !contact.showWhatsApp) errors.contactMethods = "Activa teléfono o WhatsApp como forma de contacto."
  return errors
}
