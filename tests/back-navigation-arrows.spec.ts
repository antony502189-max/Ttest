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
  ]

  for (const path of directNavigationFiles) {
    expect(read(path), path).toContain('ArrowLeft')
  }

  expect(read('src/components/mobile-publication-gate.tsx')).not.toContain('ChevronLeft')
  expect(read('src/components/mobile-search-results-v2.tsx')).not.toContain('ChevronLeft')
  expect(read('src/components/mobile-app-v2.tsx')).not.toContain('ChevronLeft')
  expect(read('src/components/mobile-app-v2.tsx')).not.toContain('>‹</button>')
})

test('canonical arrow sizing is applied after page-specific layout styles', () => {
  const css = read('src/bolder-back-navigation-arrows.css')
  const main = read('src/main.tsx')

  for (const selector of [
    '.m2-back-header .lucide-arrow-left',
    '.m2-results__header > button .lucide-arrow-left',
    '.m2-map-results-header .lucide-arrow-left',
    '.m2-publication-gate__header > button .lucide-arrow-left',
    '.m2-auth-back .lucide-arrow-left',
    '.m2-auth-appbar > button .lucide-arrow-left',
    '.m2-account-appbar > button .lucide-arrow-left',
    '.mobile-map-screen__header .lucide-arrow-left',
    '.mobile-results-topbar .lucide-arrow-left',
    '.listing-actionbar [aria-label="Volver al listado"] .lucide-arrow-left',
    '.owner-mobile-appbar .lucide-arrow-left',
    '.publish-header .lucide-arrow-left',
    '.wizard-actions .lucide-arrow-left',
    '.listing-edit-back .lucide-arrow-left',
    '.listing-location-dialog__back .lucide-arrow-left',
    '.location-selector-dialog__header .lucide-arrow-left',
    '.zone-selection__breadcrumb .lucide-arrow-left',
    '.admin-back .lucide-arrow-left',
  ]) {
    expect(css).toContain(selector)
  }

  expect(css).toContain('width: 1.45rem')
  expect(css).toContain('height: 1.45rem')
  expect(css).toContain('flex: 0 0 1.45rem')
  expect(css).toContain('stroke-width: 3.25')

  const canonicalImport = "import './bolder-back-navigation-arrows.css'"
  expect(main.indexOf(canonicalImport)).toBeGreaterThan(main.indexOf("import './customer-listing-photo-fit.css'"))
})
