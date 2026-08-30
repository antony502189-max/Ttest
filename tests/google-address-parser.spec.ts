import { expect, test } from '@playwright/test'

test('Google address parsing retains only reliable structured fields', async ({ page }) => {
  await page.goto('/')
  const parsed = await page.evaluate(async () => {
    const { parseGoogleAddress } = await import('/src/lib/google-maps/address.ts')
    return parseGoogleAddress([
      { long_name: 'Avenida V Centenario', short_name: 'Av. V Centenario', types: ['route'] },
      { long_name: '1', short_name: '1', types: ['street_number'] },
      { long_name: '38660', short_name: '38660', types: ['postal_code'] },
      { long_name: 'Costa Adeje', short_name: 'Costa Adeje', types: ['locality'] },
      { long_name: 'Adeje', short_name: 'Adeje', types: ['administrative_area_level_3'] },
      { long_name: 'Costa Adeje', short_name: 'Costa Adeje', types: ['sublocality_level_1', 'sublocality'] },
    ], 'Avenida V Centenario, 1, 38660 Adeje, Spain', { lat: 28.083, lng: -16.73 })
  })

  expect(parsed).toMatchObject({
    street: 'Avenida V Centenario 1', postcode: '38660', city: 'Adeje', area: 'Costa Adeje',
    coordinates: { lat: 28.083, lng: -16.73 },
  })
})

test('partial Google results and stale request versions cannot erase newer state', async ({ page }) => {
  await page.goto('/')
  const result = await page.evaluate(async () => {
    const { createRequestVersionGate, parseGoogleAddress } = await import('/src/lib/google-maps/address.ts')
    const gate = createRequestVersionGate()
    const first = gate.next()
    const second = gate.next()
    const partial = parseGoogleAddress([{ long_name: '38660', short_name: '38660', types: ['postal_code'] }], '', { lat: 28.08, lng: -16.72 })
    return { firstIsCurrent: gate.isCurrent(first), secondIsCurrent: gate.isCurrent(second), partial }
  })

  expect(result.firstIsCurrent).toBe(false)
  expect(result.secondIsCurrent).toBe(true)
  expect(result.partial).toEqual({ formattedAddress: '', postcode: '38660', coordinates: { lat: 28.08, lng: -16.72 } })
})

test('Tenerife boundary validation rejects an outside place before it can be applied', async ({ page }) => {
  await page.goto('/')
  const locations = await page.evaluate(async () => {
    const { isInsideTenerife } = await import('/src/lib/tenerife.ts')
    return { adeje: isInsideTenerife({ lat: 28.083, lng: -16.73 }), madrid: isInsideTenerife({ lat: 40.4168, lng: -3.7038 }) }
  })

  expect(locations).toEqual({ adeje: true, madrid: false })
})
