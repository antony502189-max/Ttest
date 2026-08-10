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
