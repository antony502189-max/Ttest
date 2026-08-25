import './customer-card-clickability.css'
import './listing-main-landmark'

const CARD_SELECTOR = '.property-card, .m2-result-card'
const INTERACTIVE_SELECTOR = 'a, button, input, select, textarea, label, [role="button"], [role="menuitem"], [role="checkbox"], [role="radio"]'

function openCard(card: HTMLElement) {
  if (card.classList.contains('m2-result-card')) {
    card.querySelector<HTMLButtonElement>('.m2-result-card__image-button')?.click()
    return
  }
  card.querySelector<HTMLElement>('.property-card__body-link')?.click()
}

document.addEventListener('click', (event) => {
  const target = event.target
  if (!(target instanceof Element)) return
  const card = target.closest<HTMLElement>(CARD_SELECTOR)
  if (!card || target.closest(INTERACTIVE_SELECTOR)) return
  openCard(card)
})
