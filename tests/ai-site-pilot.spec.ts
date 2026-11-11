import { expect, test } from '@playwright/test'

for (const width of [390, 1440]) for (const state of ['pending', 'approved', 'unavailable', 'malformed', 'stale']) {
  test(`site pilot ${width}px ${state} preserves protected-path UI boundary`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => {
      for (const key of ['112233:favorites:v2', '112233:listing-draft:v3', '112233:language:v1', '112233:saved-searches:v3', '112233:listing-pending-media:v1', 'third-party-computed-key']) localStorage.setItem(key, 'ordinary-site-storage-sentinel')
      sessionStorage.setItem('112233:ai-continuation:v1:guest', 'ordinary-session-sentinel')
    })
    const paid: string[] = [], external: string[] = [], apiPaths: string[] = []
    await page.route('**/*', route => {
      const url = new URL(route.request().url())
      if (url.hostname !== '127.0.0.1') { external.push(url.hostname); return route.abort() }
      if (url.pathname.startsWith('/api/')) throw new Error('Pilot escaped its API path')
      if (url.pathname.startsWith('/ai-pilot/api/')) {
        apiPaths.push(url.pathname)
        if (url.pathname.endsWith('/private-demo/status')) return state === 'unavailable' ? route.abort() : route.fulfill({ json: {
          attempts: state === 'malformed' ? '0' : 0, maximum: 50, exhausted: false, halted: !['approved','stale'].includes(state), approved: ['approved','stale'].includes(state), catalog_ready: state !== 'stale',
        } })
        if (url.pathname.endsWith('/capabilities')) return route.fulfill({ json: { text: true, map: true, voice: false, saved_searches: false } })
        if (url.pathname.endsWith('/quota')) return route.fulfill({ json: { remaining: 3 } })
        if (url.pathname.endsWith('/query')) { paid.push(url.pathname); return route.abort() }
        return route.fulfill({ json: {} })
      }
      return route.continue()
    })
    await page.goto('./#/')
    await expect(page.getByRole('heading', { name: 'Поиск жилья с AI', exact: true })).toBeVisible()
    await page.getByRole('button', { name: 'Escribir mi búsqueda', exact: true }).click()
    await expect(page.locator('[data-private-demo-status]')).toContainText(state === 'approved' ? '0/50'
      : state === 'pending' ? 'Страница подготовлена' : state === 'stale' ? 'Каталог устарел' : 'временно недоступна')
    await expect(page.getByLabel('Modo para esta búsqueda', { exact: true })).toHaveValue('long')
    await page.getByLabel('Cuéntanos qué necesitas', { exact: true }).fill('до 600 евро в месяц')
    const submit = page.getByRole('button', { name: 'Buscar habitaciones', exact: true })
    if (state === 'approved') await expect(submit).toBeEnabled()
    else await expect(submit).toBeDisabled()
    await page.evaluate(() => fetch('https://pilot-csp.invalid/').catch(() => undefined))
    expect(paid).toEqual([])
    expect(external).toEqual([])
    expect(apiPaths).toContain('/ai-pilot/api/v1/private-demo/status')
    expect(await page.evaluate(() => ['112233:favorites:v2', '112233:listing-draft:v3', '112233:language:v1', '112233:saved-searches:v3', '112233:listing-pending-media:v1', 'third-party-computed-key'].every(key => localStorage.getItem(key) === 'ordinary-site-storage-sentinel'))).toBe(true)
    expect(await page.evaluate(() => sessionStorage.getItem('112233:ai-continuation:v1:guest'))).toBe('ordinary-session-sentinel')
    await expect(page.locator('#ai-search-text')).toHaveAttribute('maxlength', '2000')
    if (state === 'approved') {
      await page.locator('#ai-search-text').fill('rooms under 500 euros per month with a cat')
      await expect(submit).toBeEnabled()
      await expect(page.getByText(/Опишите место, цену/).last()).toBeVisible()
    }
  })
}

test('approved click, same-key lost ACK replay, refinement and reload use only AI routes', async ({ page }) => {
  const sid = '00000000-0000-4000-8000-000000000001'
  const refs = ['00000000-0000-4000-8000-000000000002', '00000000-0000-4000-8000-000000000003']
  let version = 0, modelCalls = 0, lost = false
  const operations = new Map<string, object>()
  const messages: {idempotency_key: string; expected_version: number; text: string}[] = []
  const intent = (v: number) => ({ schema_version: 'ai-search.v1', taxonomy_version: 'rental.v1', session_id: sid, version: v,
    criteria: { rental_mode: {strength:'hard',value:'long'}, ...(v ? {budget:{strength:'hard',value:{amount:v===1?'600':'400',currency:'EUR',period:'monthly'}}} : {}) } })
  const cards = (v: number) => ({cards:{items:[],total:0,nextCursor:null,previousCursor:null},intent_hash:'hash-'+v})
  await page.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (url.hostname !== '127.0.0.1') throw new Error('External request')
    if (!path.includes('/api/')) return route.continue()
    if (!path.startsWith('/ai-pilot/api/v1/ai-search/') && !path.endsWith('/private-demo/status')) throw new Error('Nonpilot API: '+path)
    let value: unknown
    if (path.endsWith('/private-demo/status')) value = {attempts:modelCalls,maximum:50,approved:true,halted:false,exhausted:false,catalog_ready:true}
    else if (path.endsWith('/capabilities')) value = {text:true,map:true,voice:false,saved_searches:false}
    else if (path.endsWith('/identity')) value = {ready:true}
    else if (path.endsWith('/quota')) value = {remaining:3-modelCalls}
    else if (path.endsWith('/sessions')) { expect(route.request().postDataJSON().rental_mode).toBe('long'); value = {intent:intent(0),expires_at:'2099-01-01T00:00:00Z'} }
    else if (path.endsWith('/sessions/'+sid)) value = {intent:intent(version),expires_at:'2099-01-01T00:00:00Z'}
    else if (path.endsWith('/query')) {
      const message = route.request().postDataJSON(); messages.push(message)
      if (!operations.has(message.idempotency_key)) {
        expect(message.expected_version).toBe(version)
        version++; modelCalls++
        operations.set(message.idempotency_key, {operation:{status:'succeeded',remaining:3-modelCalls,receipt:{result_ref:refs[version-1],count:0}},cards:cards(version)})
      }
      if (!lost) { lost=true; return route.fulfill({status:503,json:{detail:'LOST_ACK'}}) }
      value = operations.get(message.idempotency_key)
    } else if (path.endsWith('/cards')) value = cards(version)
    else if (refs.some(ref => path.endsWith('/results/'+ref))) value = {result_ref:refs[version-1],count:0,intent_hash:'hash-'+version,intent:intent(version)}
    else throw new Error('Unexpected pilot endpoint: '+path)
    return route.fulfill({json:value})
  })
  for (const hash of ['registro','acceso','publicar','publicidad/nueva','admin','mis-campanas']) {
    await page.goto('./#/'+hash)
    await expect(page.getByRole('heading',{name:'Поиск жилья с AI',exact:true})).toBeVisible()
    await expect(page.locator('input[type=password],input[type=email]')).toHaveCount(0)
  }
  await page.getByRole('button',{name:'Escribir mi búsqueda',exact:true}).click()
  await page.locator('#ai-search-text').fill('до 600 евро в месяц')
  await page.getByRole('button',{name:'Buscar habitaciones',exact:true}).click()
  await page.getByRole('button',{name:'Проверить результат попытки',exact:true}).click()
  await expect(page.getByText('Búsquedas disponibles hoy: 2')).toBeVisible()
  await page.locator('#ai-search-text').fill('теперь до 400 евро в месяц')
  await page.getByRole('button',{name:'Actualizar búsqueda',exact:true}).click()
  await expect(page.getByText('Búsquedas disponibles hoy: 1')).toBeVisible()
  expect(messages[0]).toEqual(messages[1])
  expect(messages.map(m=>m.expected_version)).toEqual([0,0,1])
  await page.reload()
  await page.getByRole('button',{name:'Escribir mi búsqueda',exact:true}).click()
  await expect(page.getByText('400 EUR / mes').first()).toBeVisible()
  expect(modelCalls).toBe(2)
  expect(messages).toHaveLength(3)
})
