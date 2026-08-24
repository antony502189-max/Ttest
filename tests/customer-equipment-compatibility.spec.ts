import { expect, test } from '@playwright/test'
import { translateText } from '../src/contexts/i18n-context'
import { listingMatchesAmenityFilter } from '../src/lib/listing-equipment'

test('CUSTOMER-PREDEPLOY generic equipment filters match structured positive values', () => {
  expect(listingMatchesAmenityFilter(['Balcón'], 'Balcón')).toBe(true)
  expect(listingMatchesAmenityFilter(['Balcón disponible'], 'Balcón')).toBe(true)
  expect(listingMatchesAmenityFilter(['Lavadora'], 'Lavadora')).toBe(true)
  expect(listingMatchesAmenityFilter(['Lavadora individual'], 'Lavadora')).toBe(true)
  expect(listingMatchesAmenityFilter(['Lavadora compartida'], 'Lavadora')).toBe(true)
  expect(listingMatchesAmenityFilter(['Sin balcón'], 'Balcón')).toBe(false)
  expect(listingMatchesAmenityFilter(['Sin lavadora'], 'Lavadora')).toBe(false)
  expect(listingMatchesAmenityFilter(['Ascensor'], 'Ascensor')).toBe(true)
  expect(listingMatchesAmenityFilter(['Terraza'], 'Ascensor')).toBe(false)
})

test('CUSTOMER-PREDEPLOY new equipment copy is localized in RU and EN', () => {
  const values = [
    'Ropa de cama', 'Incluida', 'No incluida', 'Ropa de cama incluida', 'Ropa de cama no incluida',
    'Frigorífico', 'Individual / privado', 'No disponible', 'Frigorífico individual', 'Frigorífico compartido', 'Sin frigorífico',
    'Sí, disponible', 'Balcón disponible', 'Sin balcón', 'Individual / privada', 'Compartida',
    'Lavadora individual', 'Lavadora compartida', 'Sin lavadora',
  ]
  for (const value of values) {
    expect(translateText(value, 'ru'), `RU translation for ${value}`).not.toBe(value)
    expect(translateText(value, 'en'), `EN translation for ${value}`).not.toBe(value)
  }
})
