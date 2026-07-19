async (page) => {
  const viewports = [
    { width: 375, height: 812 },
    { width: 390, height: 844 },
    { width: 768, height: 1024 },
    { width: 1024, height: 768 },
    { width: 1440, height: 900 },
  ]
  const routes = [
    ['home', '/'],
    ['search', '/buscar'],
    ['listing', '/habitacion/arme%C3%B1ime-luminosa-01'],
    ['register', '/registro'],
    ['profile', '/perfil'],
    ['favorites', '/favoritos'],
    ['my-listings', '/mis-anuncios'],
    ['publish', '/publicar'],
    ['admin', '/admin'],
  ]
  const results = []
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('http://127.0.0.1:4173/')
  await page.evaluate(() => localStorage.clear())
  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    for (const [name, route] of routes) {
      await page.goto(`http://127.0.0.1:4173${route}`, { waitUntil: 'domcontentloaded' })
      await page.locator('main').first().waitFor({ state: 'visible' })
      await page.evaluate(async () => {
        await document.fonts.ready
        await Promise.allSettled(Array.from(document.images).map((img) => img.complete ? Promise.resolve() : new Promise((resolve) => { img.addEventListener('load', resolve, { once: true }); img.addEventListener('error', resolve, { once: true }) })))
      })
      const health = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
        scrollWidth: document.documentElement.scrollWidth,
        clientWidth: document.documentElement.clientWidth,
        title: document.querySelector('h1')?.textContent?.trim() || '',
      }))
      results.push({ name, width: viewport.width, ...health })
      await page.screenshot({ path: `output/playwright/responsive/final-${name}-${viewport.width}.png`, fullPage: true, animations: 'disabled' })
    }
  }
  return results
}
