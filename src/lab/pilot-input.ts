// UI hint only. The server's positive grammar remains authoritative.
const clear = new Set(['убери ограничение бюджета', 'без ограничения бюджета', 'без бюджета', 'remove budget', 'remove the budget limit', 'no budget limit', 'sin límite de presupuesto', 'sin limite de presupuesto', 'quita el presupuesto', 'все варианты', 'покажи все варианты', 'all options', 'show all options', 'todas las opciones'])
const patterns = [
  /^(?:ищу |нужна |покажи |теперь )?(?:комнат[ау] |варианты )?(?:до|бюджет до|не дороже) ([1-9][0-9]{1,3})(?: евро| €)?(?: в месяц|\/мес)$/,
  /^(?:find |show |now )?(?:a room |rooms )?(?:under|up to|budget up to) ([1-9][0-9]{1,3})(?: euros| eur| €)?(?: per month|\/month)$/,
  /^(?:busco |ahora )?(?:una habitación |una habitacion |habitaciones )?(?:hasta|menos de) ([1-9][0-9]{1,3})(?: euros| eur| €)?(?: al mes|\/mes)$/,
]
export const pilotInput = {
  maxLength: 160,
  placeholder: 'до 600 евро в месяц',
  hint: 'Только бюджет €50–1000 в месяц: «до 600 евро в месяц», «теперь до 400 евро в месяц» или «убери ограничение бюджета». Другие условия и личные сведения не поддерживаются.',
  validate(text: string) {
    if (!text || text.length > 160 || [...text].some(char => char.charCodeAt(0) < 32)) return false
    const value = text.toLowerCase().trim().replace(/[.!?]+$/, '').trim()
    if (clear.has(value)) return true
    return patterns.some(pattern => { const match = value.match(pattern); return match && Number(match[1]) >= 50 && Number(match[1]) <= 1000 })
  },
}
