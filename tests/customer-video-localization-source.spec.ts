import { readFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'

test('owner empty-state copy follows selected language', () => {
  const source = readFileSync('src/components/customer-video-critical-fixes.tsx', 'utf8')
  expect(source).toContain('Нет объявлений с таким статусом')
  expect(source).toContain('Выберите другой статус или создайте новое объявление.')
  expect(source).toContain('No listings have this status')
  expect(source).toContain('No hay anuncios con este estado')
})
