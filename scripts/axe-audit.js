async (page) => {
  const routes = ['/', '/buscar', '/habitacion/arme%C3%B1ime-luminosa-01', '/registro', '/perfil', '/mis-anuncios', '/publicar', '/admin']
  const widths = [{ width: 390, height: 844 }, { width: 1440, height: 900 }]
  const report = []
  for (const viewport of widths) {
    await page.setViewportSize(viewport)
    for (const route of routes) {
      await page.goto(`http://127.0.0.1:4173${route}`, { waitUntil: 'domcontentloaded' })
      await page.addScriptTag({ path: 'node_modules/axe-core/axe.min.js' })
      const violations = await page.evaluate(async () => {
        const result = await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } })
        return result.violations.map((item) => ({ id: item.id, impact: item.impact, help: item.help, nodes: item.nodes.slice(0, 3).map((node) => node.target.join(' ')) }))
      })
      report.push({ route, width: viewport.width, violations })
    }
  }
  return report
}
