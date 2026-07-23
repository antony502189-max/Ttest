import { useEffect } from 'react'
import { useI18n, type Language } from '@/contexts/i18n-context'

type LocalizedText = { ru: string; en: string }

const exactTranslations: Record<string, LocalizedText> = {
  'Tipo de propiedad': { ru: 'Тип объекта', en: 'Property type' },
  'Precio por noche': { ru: 'Цена за ночь', en: 'Price per night' },
  'Precio por mes': { ru: 'Цена за месяц', en: 'Price per month' },
  'Desde': { ru: 'От', en: 'From' },
  'Hasta': { ru: 'До', en: 'To' },
  'Precio mínimo': { ru: 'Минимальная цена', en: 'Minimum price' },
  'Precio máximo': { ru: 'Максимальная цена', en: 'Maximum price' },
  'Rango de precio': { ru: 'Диапазон цен', en: 'Price range' },
  'Requisito para la persona inquilina': { ru: 'Требования к жильцу', en: 'Tenant requirements' },
  'Tamaño mínimo (m²)': { ru: 'Минимальная площадь (м²)', en: 'Minimum size (m²)' },
  'Tamaño máximo (m²)': { ru: 'Максимальная площадь (м²)', en: 'Maximum size (m²)' },
  'Capacidad de la habitación': { ru: 'Вместимость комнаты', en: 'Room capacity' },
  'Disponible para esta fecha': { ru: 'Доступно на выбранную дату', en: 'Available on this date' },
  'Estancia mínima aceptada': { ru: 'Минимальный срок аренды', en: 'Minimum accepted stay' },
  'Estancia mínima: hasta (noches)': { ru: 'Минимальный срок — не более (ночей)', en: 'Minimum stay up to (nights)' },
  'Disponible hasta al menos': { ru: 'Доступно как минимум до', en: 'Available at least until' },
  'Condiciones destacadas': { ru: 'Основные условия', en: 'Key conditions' },
  'Espacios y equipamiento': { ru: 'Помещения и оснащение', en: 'Spaces and equipment' },
  'Fianza y vivienda': { ru: 'Депозит и жильё', en: 'Deposit and household' },
  'Residentes actuales': { ru: 'Текущие жильцы', en: 'Current residents' },
  'Tipo de anunciante': { ru: 'Тип арендодателя', en: 'Advertiser type' },
  'Más antiguos': { ru: 'Сначала старые', en: 'Oldest first' },
  'Precio más alto': { ru: 'Сначала дороже', en: 'Highest price' },
  'Filtrar resultados': { ru: 'Фильтровать результаты', en: 'Filter results' },
  'Recibe avisos cuando haya habitaciones nuevas.': { ru: 'Получайте уведомления о новых комнатах.', en: 'Get alerts when new rooms appear.' },
  'Ajusta las condiciones y revisa cuántas habitaciones coinciden.': { ru: 'Настройте условия и проверьте количество подходящих комнат.', en: 'Adjust the conditions and check how many rooms match.' },
  'Filtros de búsqueda': { ru: 'Фильтры поиска', en: 'Search filters' },
  'Limpiar': { ru: 'Очистить', en: 'Clear' },
  'Borrar': { ru: 'Сбросить', en: 'Clear' },
  'Habitaciones': { ru: 'Комнаты', en: 'Rooms' },
  'Particular': { ru: 'Частное лицо', en: 'Private advertiser' },
  'Profesional': { ru: 'Профессионал', en: 'Professional' },
  'Sin fianza': { ru: 'Без депозита', en: 'No deposit' },
  'Hasta 1 mes': { ru: 'До 1 месяца', en: 'Up to 1 month' },
  'Más de 1 mes': { ru: 'Более 1 месяца', en: 'More than 1 month' },
}

const textOriginals = new WeakMap<Text, string>()
const textApplied = new WeakMap<Text, string>()
const attributeOriginals = new WeakMap<Element, Map<string, string>>()
const attributeApplied = new WeakMap<Element, Map<string, string>>()
const dynamicOriginals = new WeakMap<Element, string>()
const dynamicApplied = new WeakMap<Element, string>()
const translatedAttributes = ['aria-label', 'placeholder', 'title'] as const

function translateExact(value: string, language: Language) {
  if (language === 'es') return value
  const match = value.match(/^(\s*)(.*?)(\s*)$/s)
  if (!match) return value
  const translated = exactTranslations[match[2]]?.[language]
  return translated ? `${match[1]}${translated}${match[3]}` : value
}

function roomWord(count: number, language: Exclude<Language, 'es'>) {
  if (language === 'en') return count === 1 ? 'room' : 'rooms'
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return 'комната'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'комнаты'
  return 'комнат'
}

function translateDynamic(value: string, language: Language) {
  if (language === 'es') return value
  let match: RegExpMatchArray | null
  if ((match = value.match(/^(\d+)\s+habitaci(?:ó|o)n(?:es)?\s+en\s+(.+)$/i))) {
    const count = Number(match[1])
    return language === 'ru'
      ? `${count} ${roomWord(count, language)} в ${match[2]}`
      : `${count} ${roomWord(count, language)} in ${match[2]}`
  }
  if ((match = value.match(/^Mostrar\s+(\d+)\s+habitaciones$/i))) {
    const count = Number(match[1])
    return language === 'ru'
      ? `Показать: ${count} ${roomWord(count, language)}`
      : `Show ${count} ${roomWord(count, language)}`
  }
  if ((match = value.match(/^Borrar filtros\s+\((\d+)\)$/i))) {
    return language === 'ru' ? `Сбросить фильтры (${match[1]})` : `Clear filters (${match[1]})`
  }
  return value
}

function applyTextNode(node: Text, language: Language) {
  const current = node.data
  const previousApplied = textApplied.get(node)
  let original = textOriginals.get(node)
  const currentKey = current.trim()

  if (!original && exactTranslations[currentKey]) {
    original = current
    textOriginals.set(node, current)
  } else if (original && previousApplied !== undefined && current !== previousApplied && exactTranslations[currentKey]) {
    original = current
    textOriginals.set(node, current)
  }

  if (!original) return
  const next = translateExact(original, language)
  textApplied.set(node, next)
  if (current !== next) node.data = next
}

function applyAttributes(element: Element, language: Language) {
  let originals = attributeOriginals.get(element)
  let applied = attributeApplied.get(element)
  if (!originals) {
    originals = new Map()
    attributeOriginals.set(element, originals)
  }
  if (!applied) {
    applied = new Map()
    attributeApplied.set(element, applied)
  }

  translatedAttributes.forEach((attribute) => {
    const current = element.getAttribute(attribute)
    if (current === null) return
    const currentKey = current.trim()
    const previousApplied = applied?.get(attribute)
    if (!originals?.has(attribute) && exactTranslations[currentKey]) originals?.set(attribute, current)
    else if (previousApplied !== undefined && current !== previousApplied && exactTranslations[currentKey]) originals?.set(attribute, current)
    const original = originals?.get(attribute)
    if (!original) return
    const next = translateExact(original, language)
    applied?.set(attribute, next)
    if (current !== next) element.setAttribute(attribute, next)
  })
}

function applySubtree(root: Node, language: Language) {
  if (root.nodeType === Node.TEXT_NODE) {
    applyTextNode(root as Text, language)
    return
  }
  if (root.nodeType !== Node.ELEMENT_NODE && root.nodeType !== Node.DOCUMENT_FRAGMENT_NODE) return
  if (root.nodeType === Node.ELEMENT_NODE) applyAttributes(root as Element, language)
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT)
  let node = walker.nextNode()
  while (node) {
    if (node.nodeType === Node.TEXT_NODE) applyTextNode(node as Text, language)
    else applyAttributes(node as Element, language)
    node = walker.nextNode()
  }
}

function applyDynamicElement(element: Element, language: Language) {
  const current = element.textContent?.trim() ?? ''
  const previousApplied = dynamicApplied.get(element)
  let original = dynamicOriginals.get(element)
  const translatedCurrent = translateDynamic(current, language)

  if (!original && translatedCurrent !== current) {
    original = current
    dynamicOriginals.set(element, current)
  } else if (original && previousApplied !== undefined && current !== previousApplied && translateDynamic(current, language) !== current) {
    original = current
    dynamicOriginals.set(element, current)
  }

  if (!original) return
  const next = translateDynamic(original, language)
  dynamicApplied.set(element, next)
  if (current !== next) element.textContent = next
}

function applyDynamicContent(language: Language) {
  document.querySelectorAll('#results-title, .filter-footer button:last-child, .applied-filters__clear').forEach((element) => applyDynamicElement(element, language))

  document.querySelectorAll<HTMLElement>('.filter-sidebar__result').forEach((element) => {
    const count = Number(element.querySelector('strong')?.textContent ?? 0)
    const textNode = [...element.childNodes].find((node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) as Text | undefined
    if (!textNode) return
    const next = language === 'es' ? ' habitaciones' : language === 'ru' ? ` ${roomWord(count, language)}` : ` ${roomWord(count, language)}`
    if (textNode.data !== next) textNode.data = next
  })
}

function setNativeInputValue(input: HTMLInputElement, value: number) {
  const next = String(value)
  if (input.value === next) return
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
  setter?.call(input, next)
  input.dispatchEvent(new Event('input', { bubbles: true }))
}

function boundedInteger(input: HTMLInputElement) {
  const parsed = Number(input.value.replace(',', '.'))
  const min = input.min === '' ? 0 : Number(input.min)
  const labelText = input.closest('label')?.textContent ?? ''
  const fallbackMax = /Estancia mínima|Минимальный срок|Minimum stay/i.test(labelText) ? 365 : Number.POSITIVE_INFINITY
  const max = input.max === '' ? fallbackMax : Number(input.max)
  const safeMin = Number.isFinite(min) ? min : 0
  const safeMax = Number.isFinite(max) ? max : Number.POSITIVE_INFINITY
  const rounded = Number.isFinite(parsed) ? Math.round(parsed) : safeMin
  return Math.min(safeMax, Math.max(safeMin, rounded))
}

function normalizePair(input: HTMLInputElement, selector: string) {
  const container = input.closest(selector)
  if (!container) return
  const inputs = [...container.querySelectorAll<HTMLInputElement>('input[type="number"]')]
  if (inputs.length !== 2) return
  const [minimum, maximum] = inputs
  const minValue = boundedInteger(minimum)
  const maxValue = boundedInteger(maximum)
  if (minValue <= maxValue) return
  if (input === minimum) setNativeInputValue(maximum, minValue)
  else setNativeInputValue(minimum, maxValue)
}

function normalizeNumericInput(input: HTMLInputElement) {
  setNativeInputValue(input, boundedInteger(input))
  normalizePair(input, '.filter-price-fields')
  const compactGrid = input.closest('.form-grid--compact')
  if (input.closest('.filter-panel') && compactGrid?.querySelectorAll('input[type="number"]').length === 2) normalizePair(input, '.form-grid--compact')
}

export function SearchExperienceGuards() {
  const { language } = useI18n()

  useEffect(() => {
    let frame = 0
    const applyAll = () => {
      applySubtree(document.body, language)
      applyDynamicContent(language)
    }
    const schedule = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(applyAll)
    }

    schedule()
    const observer = new MutationObserver(schedule)
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: [...translatedAttributes],
    })

    const handleFocusOut = (event: FocusEvent) => {
      const input = event.target
      if (input instanceof HTMLInputElement && input.type === 'number' && input.closest('.filter-panel')) normalizeNumericInput(input)
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      const input = event.target
      if (input instanceof HTMLInputElement && input.type === 'number' && input.closest('.filter-panel') && ['e', 'E', '+', '-'].includes(event.key)) event.preventDefault()
    }
    const handleWheel = (event: WheelEvent) => {
      const input = event.target
      if (input instanceof HTMLInputElement && input.type === 'number' && input.closest('.filter-panel') && document.activeElement === input) input.blur()
    }

    document.addEventListener('focusout', handleFocusOut, true)
    document.addEventListener('keydown', handleKeyDown, true)
    document.addEventListener('wheel', handleWheel, { capture: true, passive: true })

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      document.removeEventListener('focusout', handleFocusOut, true)
      document.removeEventListener('keydown', handleKeyDown, true)
      document.removeEventListener('wheel', handleWheel, true)
    }
  }, [language])

  return null
}
