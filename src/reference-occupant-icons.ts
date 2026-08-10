import {
  occupantAnyIcon,
  occupantCoupleIcon,
  occupantFamilyIcon,
  occupantManIcon,
  occupantPersonIcon,
  occupantPetsIcon,
  occupantWomanIcon,
} from '@/assets/occupants'
import { occupantObjectUrl } from '@/assets/occupants/object-url'

const mobileIcons: Record<string, string> = {
  one: occupantPersonIcon,
  two: occupantCoupleIcon,
  man: occupantManIcon,
  woman: occupantWomanIcon,
  children: occupantFamilyIcon,
  pets: occupantPetsIcon,
  unrestricted: occupantAnyIcon,
}

type ModeLocale = 'es' | 'en' | 'ru'

const modeCopy: Record<ModeLocale, Array<{ title: string; subtitle: string }>> = {
  es: [
    { title: 'HABITACIONES', subtitle: 'LARGA ESTANCIA' },
    { title: 'HABITACIONES', subtitle: 'TURÍSTICAS' },
  ],
  en: [
    { title: 'ROOMS', subtitle: 'LONG STAY' },
    { title: 'ROOMS', subtitle: 'TOURIST' },
  ],
  ru: [
    { title: 'КОМНАТЫ', subtitle: 'ДОЛГОСРОЧНО' },
    { title: 'КОМНАТЫ', subtitle: 'ТУРИЗМ' },
  ],
}

function detectModeLocale(buttons: HTMLElement[]): ModeLocale {
  const text = buttons.map((button) => button.textContent ?? '').join(' ').toLocaleLowerCase()
  if (/жиль|туризм/.test(text)) return 'ru'
  if (/housing|tourism/.test(text)) return 'en'
  return 'es'
}

function applyReferenceModeLabels() {
  const buttons = Array.from(document.querySelectorAll<HTMLElement>('.m2-mode-switch > button'))
  if (buttons.length !== 2) return
  const copy = modeCopy[detectModeLocale(buttons)]
  buttons.forEach((button, index) => {
    const labels = copy[index]
    const labelTarget = button.querySelector<HTMLElement>('span:last-child')
    if (!labels || !labelTarget) return
    labelTarget.dataset.referenceTitle = labels.title
    labelTarget.dataset.referenceSubtitle = labels.subtitle
    button.setAttribute('aria-label', `${labels.title} ${labels.subtitle}`)
  })
}

function applyReferenceIcons() {
  document.querySelectorAll<HTMLElement>('.m2-custom-occupant-list > button[data-m2-occupant-key]').forEach((button) => {
    const key = button.dataset.m2OccupantKey
    const dataUri = key ? mobileIcons[key] : undefined
    if (!dataUri) return
    const src = occupantObjectUrl(dataUri)
    const row = button.querySelector('span')
    if (!row) return
    const current = row.querySelector<HTMLImageElement>('.m2-reference-occupant-icon')
    if (current?.src === src) return

    const image = document.createElement('img')
    image.src = src
    image.alt = ''
    image.className = 'm2-reference-occupant-icon'
    image.setAttribute('aria-hidden', 'true')
    image.decoding = 'async'

    current?.remove()
    row.querySelector('b')?.remove()
    row.prepend(image)
  })
}

function applyReferenceUi() {
  applyReferenceModeLabels()
  applyReferenceIcons()
}

let scheduled = false
const schedule = () => {
  if (scheduled) return
  scheduled = true
  window.requestAnimationFrame(() => {
    scheduled = false
    applyReferenceUi()
  })
}

const referenceSelector = '.m2-mode-switch, .m2-custom-occupant-sheet, .m2-custom-occupant-list, [data-m2-occupant-key]'
const mayContainReferenceUi = (node: Node) => {
  if (!(node instanceof Element)) return false
  return node.matches(referenceSelector) || Boolean(node.querySelector(referenceSelector))
}

const mutationTouchesReferenceUi = (mutation: MutationRecord) => {
  if (mutation.type === 'characterData') {
    return mutation.target.parentElement?.closest('.m2-mode-switch') !== null
  }
  return Array.from(mutation.addedNodes).some(mayContainReferenceUi)
}

const observer = new MutationObserver((mutations) => {
  if (mutations.some(mutationTouchesReferenceUi)) schedule()
})
observer.observe(document.body, { childList: true, subtree: true, characterData: true })

const occupantInteractionSelector = '.m2-occupant-trigger, [data-m2-occupant-key], [data-m2-occupant-close]'
document.addEventListener('click', (event) => {
  const target = event.target
  if (!(target instanceof Element) || !target.closest(occupantInteractionSelector)) return
  schedule()
}, true)

schedule()
