import {
  occupantAnyIcon,
  occupantCoupleIcon,
  occupantFamilyIcon,
  occupantManIcon,
  occupantPersonIcon,
  occupantPetsIcon,
  occupantWomanIcon,
} from '@/assets/occupants'

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

const modeCopy: Record<ModeLocale, Array<{ title: string; subtitle: string; aria: string }>> = {
  es: [
    { title: 'HABITACIONES', subtitle: 'LARGA ESTANCIA', aria: 'Habitaciones, larga estancia' },
    { title: 'HABITACIONES', subtitle: 'TURÍSTICAS', aria: 'Habitaciones turísticas' },
  ],
  en: [
    { title: 'ROOMS', subtitle: 'LONG STAY', aria: 'Rooms, long stay' },
    { title: 'ROOMS', subtitle: 'TOURIST', aria: 'Tourist rooms' },
  ],
  ru: [
    { title: 'КОМНАТЫ', subtitle: 'ДОЛГОСРОЧНО', aria: 'Комнаты, долгосрочная аренда' },
    { title: 'КОМНАТЫ', subtitle: 'ТУРИЗМ', aria: 'Туристические комнаты' },
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
    if (!labels) return
    button.dataset.referenceTitle = labels.title
    button.dataset.referenceSubtitle = labels.subtitle
    button.setAttribute('aria-label', labels.aria)
  })
}

function applyReferenceIcons() {
  document.querySelectorAll<HTMLElement>('.m2-custom-occupant-list > button[data-m2-occupant-key]').forEach((button) => {
    const key = button.dataset.m2OccupantKey
    const src = key ? mobileIcons[key] : undefined
    if (!src) return
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

const mayContainReferenceUi = (node: Node) => {
  if (!(node instanceof Element)) return false
  const selector = '.m2-mode-switch, .m2-custom-occupant-sheet, .m2-custom-occupant-list, [data-m2-occupant-key]'
  return node.matches(selector) || Boolean(node.querySelector(selector))
}

const observer = new MutationObserver((mutations) => {
  if (mutations.some((mutation) => Array.from(mutation.addedNodes).some(mayContainReferenceUi))) schedule()
})
observer.observe(document.body, { childList: true, subtree: true })

const occupantInteractionSelector = '.m2-occupant-trigger, [data-m2-occupant-key], [data-m2-occupant-close]'
document.addEventListener('click', (event) => {
  const target = event.target
  if (!(target instanceof Element) || !target.closest(occupantInteractionSelector)) return
  schedule()
}, true)

schedule()
