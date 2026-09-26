import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

const read = (path: string) => readFileSync(path, 'utf8')

test('page and step back navigation uses the same ArrowLeft glyph', () => {
  const directNavigationFiles = [
    'src/components/mobile-publication-gate.tsx',
    'src/components/mobile-app-v2.tsx',
    'src/components/mobile-search-results-v2.tsx',
    'src/pages/ProfilePage.tsx',
    'src/pages/UnifiedAuthPage.tsx',
    'src/pages/ListingPage.tsx',
    'src/pages/SearchPage.tsx',
    'src/pages/AccountPages.tsx',
    'src/pages/PublishPage.tsx',
    'src/pages/AdminPage.tsx',
    'src/components/listing-location-section.tsx',
    'src/pages/ListingEditPage.tsx',
    'src/pages/ListingCreatePage.tsx',
    'src/components/map/zone-selection-map.tsx',
    'src/components/moderation-gate.tsx',
  ]

  for (const path of directNavigationFiles) {
    expect(read(path), path).toContain('ArrowLeft')
  }

  expect(read('src/components/mobile-publication-gate.tsx')).not.toContain('ChevronLeft')
  expect(read('src/components/mobile-search-results-v2.tsx')).not.toContain('ChevronLeft')
  expect(read('src/components/mobile-app-v2.tsx')).not.toContain('ChevronLeft')
  expect(read('src/components/mobile-app-v2.tsx')).not.toContain('>‹</button>')
})

test('canonical arrow appearance is global and applied after page-specific layout styles', () => {
  const css = read('src/bolder-back-navigation-arrows.css')
  const main = read('src/main.tsx')
  const moderation = read('src/components/moderation-gate.tsx')

  expect(css).toContain('svg.lucide-arrow-left')
  expect(css).toContain('width: 1.45rem !important')
  expect(css).toContain('height: 1.45rem !important')
  expect(css).toContain('flex: 0 0 1.45rem')
  expect(css).toContain('color: #638000 !important')
  expect(css).toContain('fill: none !important')
  expect(css).toContain('stroke: currentColor !important')
  expect(css).toContain('stroke-width: 3.25 !important')
  expect(css).toContain('stroke-linecap: round')
  expect(css).toContain('stroke-linejoin: round')
  expect(moderation).toContain('<ArrowLeft aria-hidden="true" />Volver')

  const canonicalImport = "import './bolder-back-navigation-arrows.css'"
  expect(main.indexOf(canonicalImport)).toBeGreaterThan(main.indexOf("import './customer-listing-photo-fit.css'"))
})
