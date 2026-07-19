async (page) => {
  const outputDir = 'output/playwright/iphone-11-17'

  const devices = [
    ['iphone-11', 414, 896],
    ['iphone-11-pro', 375, 812],
    ['iphone-11-pro-max', 414, 896],
    ['iphone-12-mini', 360, 780],
    ['iphone-12', 390, 844],
    ['iphone-12-pro', 390, 844],
    ['iphone-12-pro-max', 428, 926],
    ['iphone-13-mini', 375, 812],
    ['iphone-13', 390, 844],
    ['iphone-13-pro', 390, 844],
    ['iphone-13-pro-max', 428, 926],
    ['iphone-14', 390, 844],
    ['iphone-14-plus', 428, 926],
    ['iphone-14-pro', 393, 852],
    ['iphone-14-pro-max', 430, 932],
    ['iphone-15', 393, 852],
    ['iphone-15-plus', 430, 932],
    ['iphone-15-pro', 393, 852],
    ['iphone-15-pro-max', 430, 932],
    ['iphone-16', 393, 852],
    ['iphone-16-plus', 430, 932],
    ['iphone-16-pro', 402, 874],
    ['iphone-16-pro-max', 440, 956],
    ['iphone-17e', 390, 844],
    ['iphone-17', 402, 874],
    ['iphone-air', 420, 912],
    ['iphone-17-pro', 402, 874],
    ['iphone-17-pro-max', 440, 956],
  ]

  const routes = [
    ['home', '/'],
    ['search', '/buscar'],
    ['listing', '/habitacion/arme%C3%B1ime-luminosa-01'],
    ['publish', '/publicar'],
    ['register', '/registro'],
    ['profile', '/perfil'],
    ['my-listings', '/mis-anuncios'],
    ['contact', '/contacto'],
    ['admin', '/admin'],
  ]

  const uniqueViewports = [...new Map(devices.map(([, width, height]) => [`${width}x${height}`, { width, height }])).values()]
  const results = []

  await page.emulateMedia({ reducedMotion: 'reduce', colorScheme: 'light' })

  const waitUntilReady = async () => {
    await page.waitForLoadState('domcontentloaded')
    await page.waitForFunction(() => !document.querySelector('.route-loading'))
    await page.evaluate(async () => {
      await document.fonts.ready
      const images = [...document.images].slice(0, 12)
      await Promise.all(images.map((image) => image.complete ? Promise.resolve() : new Promise((resolve) => {
        image.addEventListener('load', resolve, { once: true })
        image.addEventListener('error', resolve, { once: true })
      })))
    })
  }

  const inspect = async (device, route) => page.evaluate(({ device, route }) => {
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight
    const fixedOrSticky = [...document.querySelectorAll('*')].filter((element) => {
      const style = getComputedStyle(element)
      return (style.position === 'fixed' || style.position === 'sticky') && style.display !== 'none' && style.visibility !== 'hidden'
    }).map((element) => {
      const rect = element.getBoundingClientRect()
      return {
        selector: element.className && typeof element.className === 'string' ? element.className.split(' ').slice(0, 2).join('.') : element.tagName.toLowerCase(),
        left: Math.round(rect.left),
        right: Math.round(rect.right),
        top: Math.round(rect.top),
        bottom: Math.round(rect.bottom),
      }
    }).filter((item) => item.right > viewportWidth + 1 || item.left < -1)

    return {
      device,
      route,
      viewport: `${viewportWidth}x${viewportHeight}`,
      documentWidth: document.documentElement.scrollWidth,
      horizontalOverflow: document.documentElement.scrollWidth > viewportWidth,
      fixedOverflow: fixedOrSticky,
      language: document.documentElement.lang,
      title: document.title,
    }
  }, { device, route })

  for (const [name, width, height] of devices) {
    await page.setViewportSize({ width, height })
    await page.goto('http://127.0.0.1:4173/')
    await waitUntilReady()
    results.push(await inspect(name, 'home'))
    await page.screenshot({ path: `${outputDir}/${name}-home.png`, fullPage: true, animations: 'disabled' })
  }

  for (const { width, height } of uniqueViewports) {
    await page.setViewportSize({ width, height })
    for (const [routeName, route] of routes) {
      await page.goto(`http://127.0.0.1:4173${route}`)
      await waitUntilReady()
      results.push(await inspect(`${width}x${height}`, routeName))
      if (width === 360 || width === 440) {
        await page.screenshot({ path: `${outputDir}/${width}x${height}-${routeName}.png`, fullPage: true, animations: 'disabled' })
      }
    }
  }

  return {
    checks: results.length,
    failures: results.filter((result) => result.horizontalOverflow || result.fixedOverflow.length),
    devices: devices.length,
    uniqueViewports: uniqueViewports.length,
    routes: routes.length,
    outputDir,
  }
}
