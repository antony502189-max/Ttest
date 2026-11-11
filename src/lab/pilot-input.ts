// UI bounds only. Whole-request minimization and fact coverage are enforced by the server.
export const pilotInput = {
  maxLength: 2000,
  placeholder: 'Комната в Madrid, до 700 евро в месяц, 2 взрослых, 0 детей, с мебелью и балконом',
  hint: 'Опишите место, цену и её период, взрослых и детей, тип жилья и нужные условия. Уточнение меняет только названные условия. Не указывайте контакты или личные сведения. Непонятные условия потребуют уточнения; свойства без подтверждения в источниках не считаются совпадением.',
  validate(text: string) {
    return Boolean(text.trim()) && text.length <= 2000 && ![...text].some(char => char.charCodeAt(0) < 32)
  },
}
