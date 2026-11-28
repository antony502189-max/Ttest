// UI bounds only. Whole-request minimization and fact coverage are enforced by the server.
export const pilotInput = {
  maxLength: 2000,
  placeholder: 'Una habitación hasta 700 euros al mes, amueblada y con gastos incluidos',
  hint: 'Indica el lugar, el tipo de vivienda, el presupuesto y tus requisitos. Puedes cambiar una condición después. No incluyas contactos ni datos personales. Solo mostramos coincidencias con condiciones confirmadas.',
  validate(text: string) {
    return Boolean(text.trim()) && text.length <= 2000
      && ![...text].some(char => char.charCodeAt(0) < 32 && !'\t\r\n'.includes(char))
  },
}
