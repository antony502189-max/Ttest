import { useLayoutEffect } from 'react'

const initializedMapScreens = new WeakSet<HTMLElement>()

function disableAutomaticDrawing(root: HTMLElement) {
  if (initializedMapScreens.has(root)) return

  if (root.dataset.testid !== 'map-draw') {
    initializedMapScreens.add(root)
    return
  }

  const drawingButton = root.querySelector<HTMLButtonElement>('.m2-draw-actions .m2-draw-cta')
  if (!drawingButton) return

  const drawingIsActive = root.classList.contains('is-freehand-drawing')
    || drawingButton.getAttribute('aria-pressed') === 'true'

  if (!drawingIsActive) {
    initializedMapScreens.add(root)
    return
  }

  if (drawingButton.disabled) return

  initializedMapScreens.add(root)
  drawingButton.click()
}

export function MobileMapDrawingActivationFix() {
  useLayoutEffect(() => {
    let scheduledFrame = 0

    const synchronize = () => {
      scheduledFrame = 0
      document.querySelectorAll<HTMLElement>('.m2-map-screen').forEach(disableAutomaticDrawing)
    }

    const scheduleSynchronize = () => {
      if (scheduledFrame) return
      scheduledFrame = requestAnimationFrame(synchronize)
    }

    const observer = new MutationObserver(scheduleSynchronize)
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ['class', 'disabled', 'aria-pressed'],
    })

    scheduleSynchronize()

    return () => {
      observer.disconnect()
      if (scheduledFrame) cancelAnimationFrame(scheduledFrame)
    }
  }, [])

  return null
}
