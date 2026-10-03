export function advertisementStatusSource(value: string, endsAt?: string | null) {
  if (value === 'active' && endsAt && new Date(endsAt).getTime() <= Date.now()) return 'Expirada'
  return ({ pending_payment: 'Pendiente de pago', pending_review: 'Pendiente de revisión', active: 'Activa', expired: 'Expirada', rejected: 'Rechazada', cancelled: 'Cancelada' } as Record<string, string>)[value] ?? value
}

export function advertisementPaymentSource(value: string) {
  return ({ paid: 'Pagado (prueba)', unpaid: 'Sin pagar' } as Record<string, string>)[value] ?? value
}

export function advertisementDestinationSource(value: string) {
  return ({ website: 'Sitio web', phone: 'Teléfono', whatsapp: 'WhatsApp', email: 'Correo electrónico' } as Record<string, string>)[value] ?? value
}
