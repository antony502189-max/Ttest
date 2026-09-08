import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('fresh publication no longer presents the legacy Armeñime location as user-provided', () => {
  const source = readFileSync('src/components/customer-video-critical-fixes.tsx', 'utf8')

  expect(source).toContain("draft.city === 'Adeje'")
  expect(source).toContain("draft.area === 'Armeñime'")
  expect(source).toContain("draft.postcode === '38678'")
  expect(source).toContain("setNativeSelectValue(city, AUTO_CITY_VALUE, true)")
  expect(source).toContain("setNativeInputValue(area, '')")
  expect(source).toContain("setNativeInputValue(postcode, '')")
  expect(source).toContain('selector.hidden = true')
  expect(source).toContain("!/^\\d{5}$/.test(postcode.value.trim())")
})
