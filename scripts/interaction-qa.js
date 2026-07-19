async (page) => {
  const results = []
  const test = async (name, run) => {
    try { await run(); results.push({ name, status: 'pass' }) }
    catch (error) { results.push({ name, status: 'fail', error: String(error).slice(0, 300) }) }
  }
  await page.setViewportSize({ width: 1440, height: 900 })

  await test('Buscar habitación', async () => {
    await page.goto('http://127.0.0.1:4173/')
    await page.getByLabel('Ciudad, barrio o zona').fill('Los Cristianos')
    await page.getByRole('button', { name: 'Buscar', exact: true }).click()
    await page.waitForURL(/\/buscar/)
  })
  await test('Aplicar filtros', async () => {
    await page.goto('http://127.0.0.1:4173/buscar')
    await page.getByRole('button', { name: /Todos los filtros/ }).click()
    await page.locator('.filter-drawer label').filter({ hasText: 'Costa Adeje' }).click()
    await page.getByRole('button', { name: /Mostrar \d+ habitaciones/ }).click()
    await page.getByText(/activos/).waitFor()
  })
  await test('Cambiar lista y mapa', async () => {
    await page.goto('http://127.0.0.1:4173/buscar')
    await page.getByRole('button', { name: 'Mapa', exact: true }).click()
    await page.locator('.mock-map').waitFor({ state: 'visible' })
  })
  await test('Abrir anuncio y galería', async () => {
    await page.goto('http://127.0.0.1:4173/habitacion/arme%C3%B1ime-luminosa-01')
    const before = await page.locator('.gallery-main img').getAttribute('src')
    await page.getByRole('button', { name: 'Foto siguiente' }).click()
    const after = await page.locator('.gallery-main img').getAttribute('src')
    if (before === after) throw new Error('La galería no cambió de imagen')
  })
  await test('Añadir a favoritos', async () => {
    await page.goto('http://127.0.0.1:4173/buscar')
    await page.evaluate(() => localStorage.removeItem('112233:favorites:v1'))
    await page.reload()
    const button = page.locator('.results-list .favorite-button').first()
    await button.click()
    if (await button.getAttribute('aria-pressed') !== 'true') throw new Error('Favorito no quedó activo')
  })
  await test('Registro con validación', async () => {
    await page.goto('http://127.0.0.1:4173/registro')
    await page.getByLabel('Nombre').fill('Lucía Demo')
    await page.getByLabel('Email').fill('lucia@example.es')
    await page.getByLabel('Contraseña', { exact: true }).fill('segura-112233')
    await page.getByLabel('Repite la contraseña').fill('segura-112233')
    await page.getByRole('checkbox').click()
    await page.getByRole('button', { name: 'Crear cuenta' }).click()
    await page.getByRole('heading', { name: 'Cuenta creada' }).waitFor()
  })
  await test('Editar perfil', async () => {
    await page.goto('http://127.0.0.1:4173/perfil')
    await page.getByRole('button', { name: 'Editar perfil' }).click()
    await page.getByLabel('Nombre').fill('Lucía Martín Demo')
    await page.getByRole('button', { name: 'Guardar cambios' }).click()
    await page.getByText('Cambios guardados correctamente.').waitFor()
  })
  await test('Crear anuncio y vista previa', async () => {
    await page.goto('http://127.0.0.1:4173/publicar')
    for (let step = 0; step < 9; step++) await page.getByRole('button', { name: /Continuar/ }).click()
    await page.getByRole('heading', { name: 'Revisa antes de publicar' }).waitFor()
    await page.getByRole('button', { name: 'Vista previa completa' }).click()
    await page.getByRole('dialog').waitFor()
    await page.keyboard.press('Escape')
    await page.getByRole('button', { name: /Enviar a revisión/ }).click()
    await page.getByRole('heading', { name: 'Tu habitación está en revisión' }).waitFor()
  })
  await test('Gestionar anuncio propio', async () => {
    await page.goto('http://127.0.0.1:4173/mis-anuncios')
    await page.getByRole('link', { name: 'Editar' }).first().click()
    await page.waitForURL(/\/editar$/)
    await page.getByRole('heading', { name: 'Editar habitación' }).waitFor()
  })
  await test('Enviar denuncia', async () => {
    await page.goto('http://127.0.0.1:4173/habitacion/arme%C3%B1ime-luminosa-01')
    await page.getByRole('button', { name: 'Denunciar anuncio' }).click()
    await page.getByLabel('Datos incorrectos').click()
    await page.getByRole('button', { name: 'Enviar denuncia' }).click()
    await page.getByText(/Denuncia enviada/).waitFor()
  })
  await test('Confirmar condiciones y contactar', async () => {
    await page.goto('http://127.0.0.1:4173/habitacion/arme%C3%B1ime-luminosa-01')
    const whatsapp = page.getByRole('button', { name: 'WhatsApp' }).first()
    if (!(await whatsapp.isDisabled())) throw new Error('WhatsApp debería iniciar desactivado')
    await page.getByText('Confirmo que cumplo las condiciones principales del anuncio.').first().click()
    if (await whatsapp.isDisabled()) throw new Error('WhatsApp no se activó')
  })
  await test('Navegación móvil', async () => {
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('http://127.0.0.1:4173/')
    await page.getByRole('navigation', { name: 'Navegación móvil' }).getByRole('link', { name: 'Mapa' }).click()
    await page.waitForURL(/vista=mapa/)
    await page.locator('.mock-map').waitFor({ state: 'visible' })
  })
  await test('Teclado y foco visible', async () => {
    await page.goto('http://127.0.0.1:4173/registro')
    await page.keyboard.press('Tab')
    const focused = await page.evaluate(() => ({ tag: document.activeElement?.tagName, outline: getComputedStyle(document.activeElement).outlineStyle }))
    if (!focused.tag || focused.outline === 'none') throw new Error(`Foco no visible: ${JSON.stringify(focused)}`)
  })
  return results
}
