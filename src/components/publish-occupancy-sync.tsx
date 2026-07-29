import { useEffect } from 'react'

function setNativeSelectValue(select: HTMLSelectElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value')?.set
  setter?.call(select, value)
  select.dispatchEvent(new Event('input', { bubbles: true }))
  select.dispatchEvent(new Event('change', { bubbles: true }))
}

function requiredCapacity(requirement: string) {
  if (requirement === 'couple') return '2'
  if (['single-man', 'single-woman', 'single-person'].includes(requirement)) return '1'
  return null
}

export function PublishOccupancySync() {
  useEffect(() => {
    let synchronizing = false
    let frame = 0

    const synchronizeFromRequirement = () => {
      if (synchronizing) return
      const requirement = document.querySelector<HTMLSelectElement>('#publish-tenant-requirement')
      const capacity = document.querySelector<HTMLSelectElement>('#publish-capacity')
      if (!requirement || !capacity) return
      const expected = requiredCapacity(requirement.value)
      if (!expected || capacity.value === expected) return
      synchronizing = true
      setNativeSelectValue(capacity, expected)
      synchronizing = false
    }

    const synchronizeFromCapacity = (capacity: HTMLSelectElement) => {
      if (synchronizing) return
      const requirement = document.querySelector<HTMLSelectElement>('#publish-tenant-requirement')
      if (!requirement) return
      let expected = requirement.value
      if (capacity.value === '2' && ['single-man', 'single-woman', 'single-person'].includes(requirement.value)) expected = 'couple'
      if (capacity.value === '1' && requirement.value === 'couple') expected = 'single-person'
      if (expected === requirement.value) return
      synchronizing = true
      setNativeSelectValue(requirement, expected)
      synchronizing = false
    }

    const handleChange = (event: Event) => {
      const target = event.target
      if (!(target instanceof HTMLSelectElement) || synchronizing) return
      if (target.id === 'publish-tenant-requirement') synchronizeFromRequirement()
      if (target.id === 'publish-capacity') synchronizeFromCapacity(target)
    }

    const scheduleSynchronization = () => {
      window.cancelAnimationFrame(frame)
      frame = window.requestAnimationFrame(synchronizeFromRequirement)
    }

    document.addEventListener('change', handleChange)
    const observer = new MutationObserver(scheduleSynchronization)
    observer.observe(document.body, { childList: true, subtree: true })
    scheduleSynchronization()

    return () => {
      window.cancelAnimationFrame(frame)
      observer.disconnect()
      document.removeEventListener('change', handleChange)
    }
  }, [])

  return null
}
