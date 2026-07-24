import './occupant-multiselect.css'

type OccupantValue = 'anyone' | 'man' | 'woman' | 'person' | 'couple' | 'unrestricted'

const occupantOrder: OccupantValue[] = ['anyone', 'man', 'woman', 'person', 'couple', 'unrestricted']
const generalValues = new Set<OccupantValue>(['anyone', 'unrestricted'])
let selectedValues = new Set<OccupantValue>(['anyone'])
const labels = new Map<OccupantValue, string>()

function getApplyLabel() {
  const language = document.documentElement.lang
  if (language === 'ru') return 'Готово'
  if (language === 'en') return 'Done'
  return 'Listo'
}

function buildSummary() {
  const selected = occupantOrder.filter((value) => selectedValues.has(value))
  const selectedLabels = selected.map((value) => labels.get(value)).filter((label): label is string => Boolean(label))

  if (selectedLabels.length === 0) return labels.get('anyone') ?? ''
  if (selectedLabels.length === 1) return selectedLabels[0]

  const colonIndex = selectedLabels[0].indexOf(':')
  if (colonIndex === -1) return selectedLabels.join(', ')

  const prefix = selectedLabels[0].slice(0, colonIndex + 1)
  const values = selectedLabels.map((label) => {
    const index = label.indexOf(':')
    return index === -1 ? label : label.slice(index + 1).trim()
  })

  return `${prefix} ${values.join(', ')}`
}

function updateTrigger() {
  const summary = document.querySelector<HTMLElement>('.im-occupant-copy strong')
  if (summary) summary.textContent = buildSummary()
}

function syncPanel(panel: HTMLElement) {
  const options = Array.from(panel.querySelectorAll<HTMLButtonElement>('.im-occupant-option'))

  options.forEach((option, index) => {
    const value = occupantOrder[index]
    if (!value) return

    option.dataset.occupantValue = value
    const label = option.querySelector<HTMLElement>('span:first-child')?.textContent?.trim()
    if (label) labels.set(value, label)

    const selected = selectedValues.has(value)
    option.classList.toggle('is-selected', selected)
    option.setAttribute('role', 'checkbox')
    option.setAttribute('aria-checked', String(selected))
  })

  const radioGroup = panel.querySelector<HTMLElement>('[role="radiogroup"]')
  if (radioGroup) {
    radioGroup.setAttribute('role', 'group')
    radioGroup.setAttribute('aria-multiselectable', 'true')
  }

  let actions = panel.querySelector<HTMLElement>('.im-occupant-actions')
  if (!actions) {
    actions = document.createElement('div')
    actions.className = 'im-occupant-actions'

    const applyButton = document.createElement('button')
    applyButton.type = 'button'
    applyButton.className = 'im-occupant-apply'
    applyButton.addEventListener('click', () => {
      panel.querySelector<HTMLButtonElement>('header button')?.click()
    })

    actions.append(applyButton)
    panel.append(actions)
  }

  const applyButton = actions.querySelector<HTMLButtonElement>('.im-occupant-apply')
  if (applyButton) applyButton.textContent = getApplyLabel()

  updateTrigger()
}

function toggleValue(value: OccupantValue) {
  if (generalValues.has(value)) {
    selectedValues = new Set([value])
    return
  }

  selectedValues.delete('anyone')
  selectedValues.delete('unrestricted')

  if (selectedValues.has(value)) selectedValues.delete(value)
  else selectedValues.add(value)

  if (selectedValues.size === 0) selectedValues.add('anyone')
}

function handleOptionClick(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof Element)) return

  const option = target.closest<HTMLButtonElement>('.im-occupant-option')
  if (!option) return

  const value = option.dataset.occupantValue as OccupantValue | undefined
  if (!value) return

  event.preventDefault()
  event.stopPropagation()
  toggleValue(value)

  const panel = option.closest<HTMLElement>('.im-occupant-panel')
  if (panel) syncPanel(panel)
}

function startOccupantMultiselect() {
  document.documentElement.classList.add('occupant-multiselect-active')
  document.addEventListener('click', handleOptionClick, true)

  const observer = new MutationObserver(() => {
    const panel = document.querySelector<HTMLElement>('.im-occupant-panel')
    if (panel) syncPanel(panel)
  })

  observer.observe(document.body, { childList: true, subtree: true })
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', startOccupantMultiselect, { once: true })
} else {
  startOccupantMultiselect()
}
