import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fetchAdminTab, type AdminTabSources } from '../src/lib/admin-tab-loader'

test.describe('mobile menu values never split across lines', () => {
  for (const width of [320, 390, 430]) {
    test(`Russian region and language values are one-line at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 })
      await page.addInitScript(() => {
        localStorage.setItem('112233:mobile-onboarding:v1', 'done')
        localStorage.setItem('112233:language:v1', 'ru')
      })
      await page.goto('/#/menu')
      const menu = page.getByTestId('mobile-menu')
      await expect(menu).toBeVisible()
      const values = menu.locator('.m2-menu-row__trailing b')
      await expect(values).toHaveCount(2)
      await expect(values.nth(0)).toHaveText('España')
      await expect(values.nth(1)).toHaveText('Русский')
      for (const value of await values.all()) {
        const metrics = await value.evaluate((node) => {
          const style = getComputedStyle(node)
          const rect = node.getBoundingClientRect()
          return {
            whiteSpace: style.whiteSpace,
            wordBreak: style.wordBreak,
            height: rect.height,
            maxLineHeight: parseFloat(style.lineHeight),
            clientWidth: node.clientWidth,
            scrollWidth: node.scrollWidth,
          }
        })
        expect(metrics.whiteSpace).toBe('nowrap')
        expect(metrics.wordBreak).toBe('normal')
        expect(metrics.height).toBeLessThanOrEqual(metrics.maxLineHeight + 2)
        expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1)
      }
      const noOverflow = await page.evaluate(() =>
        document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)
      expect(noOverflow).toBe(true)
    })
  }
})

test.describe('production admin data loading is scoped by tab', () => {
  function sources(calls: string[]): AdminTabSources {
    return {
      users: async () => { calls.push('users'); return [] },
      listings: async () => { calls.push('listings'); return [] },
      homepageHero: async () => { calls.push('homepageHero'); return null },
      reports: async () => { calls.push('reports'); return [] },
      activity: async () => { calls.push('activity'); return [] },
      settings: async () => { calls.push('settings'); return [] },
    }
  }

  test('users never wait for listings, reports, audit, homepage or admins', async () => {
    const calls: string[] = []
    const result = await fetchAdminTab('users', sources(calls))
    expect(result).toEqual({ tab: 'users', users: [] })
    expect(calls).toEqual(['users'])
  })

  test('switching admin tabs fetches only that tab and its required dependencies', async () => {
    const calls: string[] = []
    const api = sources(calls)
    expect(await fetchAdminTab('listings', api)).toEqual({ tab: 'listings', listings: [], homepageHero: null })
    expect(calls.sort()).toEqual(['homepageHero', 'listings'])
    calls.length = 0
    expect(await fetchAdminTab('reports', api)).toEqual({ tab: 'reports', reports: [] })
    expect(calls).toEqual(['reports'])
    calls.length = 0
    expect(await fetchAdminTab('advertisements', api)).toBeNull()
    expect(calls).toHaveLength(0)
  })

  test('failed users fetch rejects quickly, supports retry, and the screen keeps an actionable error', async () => {
    const calls: string[] = []
    const api = sources(calls)
    let attempts = 0
    api.users = async () => {
      attempts += 1
      if (attempts === 1) throw new Error('Temporalmente no disponible')
      return []
    }
    await expect(fetchAdminTab('users', api)).rejects.toThrow('Temporalmente no disponible')
    await expect(fetchAdminTab('users', api)).resolves.toEqual({ tab: 'users', users: [] })
    expect(attempts).toBe(2)
    expect(calls).toEqual([])

    const screen = readFileSync(new URL('../src/pages/AdminPage.tsx', import.meta.url), 'utf8')
    expect(screen).toContain("setLoadErrors((current) => ({ ...current, [target]: errorMessage(error) }))")
    expect(screen).toContain('className="admin-load-error" role="alert"')
    expect(screen).toContain("void loadSection(section, true)")
    expect(screen).toContain("const loading = loadingSections.includes('users')")
  })
})
