import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

const productionCompose = readFileSync('docker-compose.production.yml', 'utf8')
const backendConfig = readFileSync('backend/app/core/config.py', 'utf8')
const migration = readFileSync('backend/alembic/versions/0041_direct_publish_existing_pending.py', 'utf8')

test('production owner publication cannot fall back to a moderation queue', async () => {
  expect(productionCompose).toContain('AUTO_PUBLISH_LISTINGS: "true"')
  expect(backendConfig).toContain('AUTO_PUBLISH_LISTINGS must be true in production')
  expect(backendConfig).toContain('if not self.auto_publish_listings:')
})

test('legacy live internal pending listings are repaired to published on deploy', async () => {
  expect(migration).toContain("WHERE status = 'pending'")
  expect(migration).toContain('AND is_external IS FALSE')
  expect(migration).toContain('AND deleted_at IS NULL')
  expect(migration).toContain("SET status = 'published'")
  expect(migration).toContain("'pending', 'published'")
  expect(migration).toContain('SET version = version + 1')
})
