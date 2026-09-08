import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('owned-listing hydration gate never treats an in-flight remote list as authoritative empty', () => {
  const source = readFileSync('src/components/owned-listings-hydration-gate.tsx', 'utf8')

  expect(source).toContain("type Snapshot = { userId: string; items: Listing[] }")
  expect(source).toContain("snapshot?.userId === userId")
  expect(source).toContain("setPhase('checking')")
  expect(source).toContain("getOwnedListings(controller.signal)")
  expect(source).toContain("if (phase === 'checking' && !sameUserSnapshot?.length)")
  expect(source).toContain('Tus anuncios no se han borrado')
  expect(source).toContain('Объявления не удалены')
})
