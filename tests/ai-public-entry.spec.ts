import { expect, test } from '@playwright/test'

for (const width of [390, 1440]) for (const ready of [true, false]) {
  test(`public home ${width}px ready=${ready}: bounded guest API and unchanged manual controls`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => {
      localStorage.setItem('112233:language:v1', 'es')
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
    })
    const sid = '00000000-0000-4000-8000-000000000001'
    const ref = '00000000-0000-4000-8000-000000000002'
    let calls = 0, version = 0
    const intent = () => ({ schema_version: 'ai-search.v1', taxonomy_version: 'rental.v1', session_id: sid, version,
      criteria: { rental_mode: { strength: 'hard', value: 'long' }, ...(version ? {budget:{strength:'hard',value:{amount:'600',currency:'EUR',period:'monthly'}}} : {}) } })
    const paths: string[] = []
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname
      if (url.hostname !== '127.0.0.1') return route.abort()
      if (path.startsWith('/api/v1/ai-search/')) throw Error('AI escaped its isolated guest route')
      if (path.startsWith('/ai-pilot/api/v1/')) {
        paths.push(path)
        expect(request.headers().authorization).toBeUndefined()
        let value: unknown
        if (path.endsWith('/private-demo/status')) value = {attempts:calls,maximum:50,approved:true,halted:false,exhausted:false,catalog_ready:ready}
        else if (path.endsWith('/capabilities')) value = {text:true,map:true,voice:true,saved_searches:false}
        else if (path.endsWith('/identity')) value = {ready:true}
        else if (path.endsWith('/quota')) value = {remaining:3-calls}
        else if (path.endsWith('/sessions')) {
          expect(request.postDataJSON().rental_mode).toBe('long')
          value = {intent:intent(),expires_at:'2099-01-01T00:00:00Z'}
        } else if (path.endsWith('/query')) {
          expect(ready).toBe(true)
          expect(request.postDataJSON().text).toBe('до 600 евро в месяц')
          calls++; version++
          value = {operation:{status:'succeeded',remaining:2,receipt:{result_ref:ref,count:0}},cards:{cards:{items:[],total:0,nextCursor:null,previousCursor:null},intent_hash:'public-hash'}}
        } else if (path.endsWith('/sessions/'+sid)) value = {intent:intent(),expires_at:'2099-01-01T00:00:00Z'}
        else if (path.endsWith('/results/'+ref)) value = {result_ref:ref,count:0,intent_hash:'public-hash',intent:intent()}
        else if (path.endsWith('/cards')) value = {cards:{items:[],total:0,nextCursor:null,previousCursor:null},intent_hash:'public-hash'}
        else throw Error('Unexpected public AI request: '+path)
        return route.fulfill({json:value})
      }
      if (path.startsWith('/api/')) return route.fulfill({status:404,json:{detail:'Not found'}})
      return route.continue()
    })
    await page.goto('/#/')
    const manual = page.getByRole('button', {name:width === 390 ? 'Buscar' : 'Ver habitaciones',exact:true})
    await expect(manual).toBeVisible()
    const voice = page.getByRole('button', {name:'Buscar con mi voz',exact:true})
    await expect(voice).toBeVisible()
    await expect(voice).toHaveCSS('background-color','rgb(201, 255, 39)')
    await page.screenshot({path:`output/ai-home-public-${width}-${ready}.png`,fullPage:true})
    await voice.click()
    await expect(page.getByRole('button',{name:'Надиктовать запрос',exact:true})).toBeVisible()
    await page.locator('#ai-search-text').fill('hasta 500 euros al mes mi nombre es Ana')
    const submit = page.getByRole('button',{name:'Buscar habitaciones',exact:true})
    await expect(submit).toBeDisabled()
    await page.locator('#ai-search-text').fill('до 600 евро в месяц')
    if (ready) {
      await expect(submit).toBeEnabled()
      await submit.click()
      await expect(page.getByText('600 EUR / mes',{exact:true}).first()).toBeVisible()
      expect(calls).toBe(1)
      await page.reload()
      await page.getByRole('button',{name:'También puedes escribir tu búsqueda',exact:true}).click()
      await expect(page.getByText('600 EUR / mes',{exact:true}).first()).toBeVisible()
      expect(calls).toBe(1)
    } else await expect(submit).toBeDisabled()
    expect(paths).toContain('/ai-pilot/api/v1/private-demo/status')
  })
}
