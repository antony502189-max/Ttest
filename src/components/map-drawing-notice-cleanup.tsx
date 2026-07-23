import { useEffect } from 'react'

const DRAWING_NOTICE_PATTERNS = [
  'zona aplicada',
  'zona dibujada aplicada',
]

function removeDrawingNotices(root: ParentNode) {
  root.querySelectorAll<HTMLElement>('[data-sonner-toast], [data-sonner-toaster] [role="status"]').forEach((notice) => {
    const text = notice.textContent?.trim().toLocaleLowerCase() ?? ''
    if (DRAWING_NOTICE_PATTERNS.some((pattern) => text.includes(pattern))) notice.remove()
  })
}

export function MapDrawingNoticeCleanup() {
  useEffect(() => {
    removeDrawingNotices(document)

    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
          if (!(node instanceof Element)) return
          const text = node.textContent?.trim().toLocaleLowerCase() ?? ''
          if (DRAWING_NOTICE_PATTERNS.some((pattern) => text.includes(pattern))) {
            const toast = node.closest<HTMLElement>('[data-sonner-toast]')
            ;(toast ?? node).remove()
            return
          }
          removeDrawingNotices(node)
        })
      })
    })

    observer.observe(document.body, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [])

  return null
}
