import { useLayoutEffect } from 'react'
import { useLocation, useNavigationType } from 'react-router'

type Position = { windowY: number; resultsY: number }
const positions = new Map<string, Position>()

function resultsScroller() {
  return document.querySelector<HTMLElement>('.m2-results')
}

export function ScrollRestoration() {
  const location = useLocation()
  const navigationType = useNavigationType()

  useLayoutEffect(() => {
    const previousRestoration = window.history.scrollRestoration
    window.history.scrollRestoration = 'manual'
    const key = location.key
    const saved = navigationType === 'POP' ? positions.get(key) : navigationType === 'REPLACE'
      ? { windowY: window.scrollY, resultsY: resultsScroller()?.scrollTop ?? 0 }
      : undefined
    let anchorId = ''
    try { anchorId = location.hash ? decodeURIComponent(location.hash.slice(1)) : '' } catch { /* Ignore malformed fragments. */ }
    let frame = 0
    let focusFrame = 0
    let observer: ResizeObserver | undefined
    let portalObserver: MutationObserver | undefined

    const restore = () => {
      if (anchorId) {
        const anchor = document.getElementById(anchorId)
        if (anchor) {
          anchor.scrollIntoView({ block: 'center', behavior: 'instant' })
          if (!anchor.hasAttribute('tabindex')) anchor.setAttribute('tabindex', '-1')
          anchor.focus({ preventScroll: true })
          observer?.disconnect()
          portalObserver?.disconnect()
        }
        return
      }
      window.scrollTo(0, saved?.windowY ?? 0)
      const results = resultsScroller()
      if (results) results.scrollTop = saved?.resultsY ?? 0
      if (saved && window.scrollY >= saved.windowY - 2 &&
        (!saved.resultsY || (results && results.scrollTop >= saved.resultsY - 2))) {
        observer?.disconnect()
        portalObserver?.disconnect()
      }
    }

    // A lazy route can grow after the first paint. Retry as its content grows.
    frame = window.requestAnimationFrame(restore)
    const target = document.getElementById('main-content')
    if (saved && target) {
      observer = new ResizeObserver(restore)
      observer.observe(target)
    }
    if (saved || anchorId) {
      portalObserver = new MutationObserver(restore)
      portalObserver.observe(document.body, { childList: true, subtree: true })
    }
    const record = () => {
      positions.set(key, { windowY: window.scrollY, resultsY: resultsScroller()?.scrollTop ?? positions.get(key)?.resultsY ?? 0 })
    }
    document.addEventListener('scroll', record, { passive: true, capture: true })
    if (navigationType === 'POP') focusFrame = window.requestAnimationFrame(() => {
      if (document.activeElement === document.body) target?.focus({ preventScroll: true })
    })
    return () => {
      record()
      document.removeEventListener('scroll', record, true)
      observer?.disconnect()
      portalObserver?.disconnect()
      window.cancelAnimationFrame(frame)
      window.cancelAnimationFrame(focusFrame)
      window.history.scrollRestoration = previousRestoration
    }
  }, [location.key, location.hash, navigationType])
  return null
}
