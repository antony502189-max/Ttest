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

const desktopIcons: Record<string, string> = {
  hombre: occupantManIcon,
  mujer: occupantWomanIcon,
  'una persona': occupantPersonIcon,
  pareja: occupantCoupleIcon,
  familia: occupantFamilyIcon,
  'sin restricción': occupantAnyIcon,
  'sin restriccion': occupantAnyIcon,
  'con mascotas': occupantPetsIcon,
}

function referenceImage(src: string, className: string) {
  const image = document.createElement('img')
  image.src = src
  image.alt = ''
  image.className = className
  image.setAttribute('aria-hidden', 'true')
  image.decoding = 'async'
  return image
}

function applyMobileReferenceIcons() {
  document.querySelectorAll<HTMLElement>('.m2-custom-occupant-list > button[data-m2-occupant-key]').forEach((button) => {
    const key = button.dataset.m2OccupantKey
    const src = key ? mobileIcons[key] : undefined
    if (!src) return
    const row = button.querySelector('span')
    if (!row) return
    const current = row.querySelector<HTMLImageElement>('.m2-reference-occupant-icon')
    if (current?.src === src) return
    current?.remove()
    row.querySelector('b')?.remove()
    row.prepend(referenceImage(src, 'm2-reference-occupant-icon'))
  })
}

function applyDesktopReferenceIcons() {
  document.querySelectorAll<HTMLButtonElement>('.mandatory-choice').forEach((button) => {
    const label = button.querySelector('span')?.textContent?.trim().toLocaleLowerCase('es') ?? ''
    const src = desktopIcons[label]
    if (!src) return
    const current = button.querySelector<HTMLImageElement>('.mandatory-choice__reference-icon')
    if (current?.src === src) return
    current?.remove()
    button.querySelector(':scope > svg')?.remove()
    button.prepend(referenceImage(src, 'mandatory-choice__reference-icon'))
  })
}

function applyReferenceIcons() {
  applyMobileReferenceIcons()
  applyDesktopReferenceIcons()
}

let scheduled = false
const schedule = () => {
  if (scheduled) return
  scheduled = true
  window.requestAnimationFrame(() => {
    scheduled = false
    applyReferenceIcons()
  })
}

schedule()

const observer = new MutationObserver(schedule)
observer.observe(document.documentElement, { childList: true, subtree: true })
