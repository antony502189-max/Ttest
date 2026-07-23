import { useLayoutEffect } from 'react'
import { useLocation } from 'react-router-dom'

const SWITCH_SELECTOR = '.rental-switch--home'
const INITIAL_STATE_ATTRIBUTE = 'data-awaiting-choice'

export function RentalSwitchFeedback() {
  const { pathname } = useLocation()

  useLayoutEffect(() => {
    if (pathname !== '/') return

    let interacted = false

    const applyInitialState = () => {
      const switchElement = document.querySelector<HTMLElement>(SWITCH_SELECTOR)
      if (!switchElement || interacted) return
      switchElement.setAttribute(INITIAL_STATE_ATTRIBUTE, 'true')
    }

    const handleClick = (event: MouseEvent) => {
      if (!(event.target instanceof Element)) return
      const button = event.target.closest(`${SWITCH_SELECTOR} button`)
      if (!button) return

      interacted = true
      button.closest<HTMLElement>(SWITCH_SELECTOR)?.removeAttribute(INITIAL_STATE_ATTRIBUTE)
    }

    applyInitialState()

    const observer = new MutationObserver(applyInitialState)
    observer.observe(document.body, { childList: true, subtree: true })
    document.addEventListener('click', handleClick, true)

    return () => {
      observer.disconnect()
      document.removeEventListener('click', handleClick, true)
      document.querySelector<HTMLElement>(SWITCH_SELECTOR)?.removeAttribute(INITIAL_STATE_ATTRIBUTE)
    }
  }, [pathname])

  return null
}
