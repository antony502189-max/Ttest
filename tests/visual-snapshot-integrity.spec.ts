import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { expect, test } from '@playwright/test'

const here = dirname(fileURLToPath(import.meta.url))
const visualSpecs = [
  'master-task-visual.spec.ts',
  'visual-parity.spec.ts',
]

test('approved visual snapshots do not hide page content before capture', () => {
  for (const filename of visualSpecs) {
    const source = readFileSync(join(here, filename), 'utf8')
    expect(source, `${filename} must not inject CSS before approved screenshots`).not.toContain('addStyleTag')
    expect(source, `${filename} must not hide DOM from approved screenshots`).not.toMatch(/display\s*:\s*none\s*!important/i)
  }
})
