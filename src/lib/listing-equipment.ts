export type EquipmentField = 'bedding' | 'refrigerator' | 'balcony' | 'washingMachine'

export type EquipmentSelections = {
  bedding: '' | 'included' | 'not_included'
  refrigerator: '' | 'individual' | 'shared' | 'none'
  balcony: '' | 'yes' | 'no'
  washingMachine: '' | 'individual' | 'shared' | 'none'
}

type EquipmentValue = EquipmentSelections[EquipmentField]

const definitions = {
  bedding: {
    options: {
      included: 'Ropa de cama incluida',
      not_included: 'Ropa de cama no incluida',
    },
    legacy: {},
  },
  refrigerator: {
    options: {
      individual: 'Frigorífico individual',
      shared: 'Frigorífico compartido',
      none: 'Sin frigorífico',
    },
    legacy: {},
  },
  balcony: {
    options: {
      yes: 'Balcón disponible',
      no: 'Sin balcón',
    },
    legacy: {
      Balcón: 'yes',
    },
  },
  washingMachine: {
    options: {
      individual: 'Lavadora individual',
      shared: 'Lavadora compartida',
      none: 'Sin lavadora',
    },
    legacy: {
      Lavadora: 'shared',
    },
  },
} as const

export const newListingEquipmentDefaults: EquipmentSelections = {
  bedding: 'included',
  refrigerator: 'shared',
  balcony: 'no',
  washingMachine: 'shared',
}

export const legacyGenericEquipmentAmenities = new Set(['Balcón', 'Lavadora'])

function definitionFor(field: EquipmentField) {
  return definitions[field] as {
    options: Record<string, string>
    legacy: Record<string, EquipmentValue>
  }
}

export function readEquipmentAmenities(amenities: string[]): EquipmentSelections {
  const result: EquipmentSelections = {
    bedding: '',
    refrigerator: '',
    balcony: '',
    washingMachine: '',
  }

  for (const field of Object.keys(definitions) as EquipmentField[]) {
    const definition = definitionFor(field)
    const option = Object.entries(definition.options).find(([, label]) => amenities.includes(label))
    if (option) {
      result[field] = option[0] as never
      continue
    }
    const legacy = Object.entries(definition.legacy).find(([label]) => amenities.includes(label))
    if (legacy) result[field] = legacy[1] as never
  }

  return result
}

export function writeEquipmentAmenity(
  amenities: string[],
  field: EquipmentField,
  value: EquipmentValue,
): string[] {
  const definition = definitionFor(field)
  const labels = new Set([...Object.values(definition.options), ...Object.keys(definition.legacy)])
  const cleaned = amenities.filter((item) => !labels.has(item))
  if (!value) return cleaned
  const label = definition.options[value]
  return label ? [...cleaned, label] : cleaned
}

export function withEquipmentDefaults(amenities: string[]): string[] {
  let next = [...amenities]
  const current = readEquipmentAmenities(next)
  for (const field of Object.keys(definitions) as EquipmentField[]) {
    const value = current[field] || newListingEquipmentDefaults[field]
    next = writeEquipmentAmenity(next, field, value)
  }
  return next
}

export function normalizeEquipmentAmenities(amenities: string[]): string[] {
  let next = [...amenities]
  const current = readEquipmentAmenities(next)
  for (const field of Object.keys(definitions) as EquipmentField[]) {
    if (current[field]) next = writeEquipmentAmenity(next, field, current[field])
  }
  return next
}
