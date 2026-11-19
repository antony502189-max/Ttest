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
    await expect(page.getByRole('button',{name:'Dictar búsqueda',exact:true})).toBeVisible()
    await page.locator('#ai-search-text').fill('')
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

for (const width of [390, 1440]) {
  test(`registered explicit save ${width}px retries without another model call or persisted token`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.addInitScript(() => {
      const id = '00000000-0000-4000-8000-000000000011'
      localStorage.setItem('112233:language:v1', 'es')
      localStorage.setItem('112233:mobile-onboarding:v1', 'done')
      localStorage.setItem('112233:session:v1', JSON.stringify(id))
      localStorage.setItem('112233:users:v1', JSON.stringify([{ id, name: 'Synthetic', email: 'synthetic@example.test',
        password: '', passwordHash: 'offline', role: 'tenant', initials: 'S', phone: '', whatsapp: '', telegram: '', about: '',
        showPhone: false, showWhatsApp: false, emailVerified: true }]))
    })
    const sid = '00000000-0000-4000-8000-000000000001', ref = '00000000-0000-4000-8000-000000000002'
    let calls = 0, saves = 0, issues = 0
    const intent = () => ({ schema_version: 'ai-search.v1', taxonomy_version: 'rental.v1', session_id: sid, version: calls,
      criteria: { rental_mode: { strength: 'hard', value: 'long' }, ...(calls ? { furnished: { strength: 'hard', value: false } } : {}) } })
    await page.route('**/*', route => {
      const request = route.request(), url = new URL(request.url()), path = url.pathname
      if (url.hostname !== '127.0.0.1') return route.abort()
      if (path === '/api/v1/saved-searches/ai/capabilities') return route.fulfill({ json: { save: true } })
      if (path === '/api/v1/saved-searches/ai' && request.method() === 'POST') {
        expect(request.headers().authorization).toBe('Bearer synthetic-primary-token')
        expect(request.postDataJSON()).toEqual({ token: 'synthetic-signed-handoff' })
        saves++
        return route.fulfill({ status: saves === 1 ? 503 : 200, json: saves === 1 ? { detail: 'unavailable' } : { id: ref, matcher: 'ai.v1', enabled: true, revision: 1, name: '' } })
      }
      if (path.startsWith('/ai-pilot/api/v1/')) {
        expect(request.headers().authorization).toBeUndefined()
        let value: unknown
        if (path.endsWith('/private-demo/status')) value = { attempts: calls, maximum: 50, approved: true, halted: false, exhausted: false, catalog_ready: true }
        else if (path.endsWith('/capabilities')) value = { text: true, map: true, voice: true, saved_searches: false, save_handoff: true }
        else if (path.endsWith('/identity')) value = { ready: true }
        else if (path.endsWith('/quota')) value = { remaining: 3 - calls }
        else if (path.endsWith('/sessions')) value = { intent: intent(), expires_at: '2099-01-01T00:00:00Z' }
        else if (path.endsWith('/sessions/' + sid)) value = { intent: intent(), expires_at: '2099-01-01T00:00:00Z' }
        else if (path.endsWith('/query')) { calls++; value = { operation: { status: 'succeeded', remaining: 2, receipt: { result_ref: ref, count: 0 } }, cards: { cards: { items: [], total: 0, nextCursor: null, previousCursor: null }, intent_hash: 'frozen-hash' } } }
        else if (path.endsWith('/results/' + ref)) value = { result_ref: ref, count: 0, intent_hash: 'frozen-hash', intent: intent() }
        else if (path.endsWith('/results/' + ref + '/save-token')) { issues++; value = { token: 'synthetic-signed-handoff', expires_in: 300 } }
        else throw Error('Unexpected guest route: ' + path)
        return route.fulfill({ json: value })
      }
      if (path.startsWith('/api/')) return route.fulfill({ status: 404, json: {} })
      return route.continue()
    })
    await page.goto('/#/')
    await page.evaluate(async () => { const client = await import('/src/api/client.ts'); client.setAccessToken('synthetic-primary-token') })
    await page.getByRole('button', { name: 'También puedes escribir tu búsqueda', exact: true }).click()
    await page.locator('#ai-search-text').fill('sin muebles')
    await page.getByRole('button', { name: 'Buscar habitaciones', exact: true }).click()
    const save = page.getByRole('button', { name: 'Guardar búsqueda y activar avisos', exact: true })
    await expect(save).toBeVisible()
    await save.click()
    await expect(page.getByText(/No se pudo guardar\. Comprueba/)).toBeVisible()
    await save.click()
    await expect(page.getByText(/Búsqueda guardada\. Puedes pausar/)).toBeVisible()
    expect({ calls, saves, issues }).toEqual({ calls: 1, saves: 2, issues: 2 })
    expect(await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }))).not.toContain('synthetic-signed-handoff')
  })
}

for (const width of [390, 1440]) for (const flow of ["register", "login", "login-then-register"]) test(`${flow} returns to the owned AI result ${width}px without another search or automatic save`, async ({ page }) => {
  await page.setViewportSize({width,height:1000})
  const sid='00000000-0000-4000-8000-000000000081',ref='00000000-0000-4000-8000-000000000082'
  await page.addInitScript(({sid,ref})=>{
    localStorage.setItem('112233:language:v1','es');localStorage.setItem('112233:mobile-onboarding:v1','done')
    sessionStorage.setItem('112233:ai-continuation:v1:public-guest',JSON.stringify({sessionId:sid,resultRef:ref}))
  },{sid,ref})
  const intent={schema_version:'ai-search.v1',taxonomy_version:'rental.v1',session_id:sid,version:1,
    criteria:{rental_mode:{strength:'hard',value:'long'},budget:{strength:'hard',value:{amount:'700',currency:'EUR',period:'monthly'}},furnished:{strength:'hard',value:true}}}
  let searches=0,saves=0,tokens=0
  await page.route('**/*',route=>{
    const r=route.request(),url=new URL(r.url()),p=url.pathname
    if(url.hostname!=='127.0.0.1')return route.abort()
    if(p==='/api/v1/saved-searches/ai/capabilities')return route.fulfill({json:{save:true}})
    if(p==='/api/v1/saved-searches/ai'&&r.method()==='POST'){
      saves++;expect(r.headers().authorization).toBe('Bearer synthetic-primary-token')
      return route.fulfill({json:{id:ref,matcher:'ai.v1',enabled:true,revision:1,name:''}})
    }
    if(p.startsWith('/ai-pilot/api/v1/')){
      expect(r.headers().authorization).toBeUndefined()
      if(p.endsWith('/query')||p.endsWith('/voice')){searches++;throw Error('Registration must not search again')}
      let value:unknown
      if(p.endsWith('/private-demo/status'))value={attempts:30,maximum:50,approved:false,halted:true,catalog_ready:true,local_housing_available:true}
      else if(p.endsWith('/capabilities'))value={text:true,map:true,voice:true,saved_searches:false,save_handoff:true}
      else if(p.endsWith('/quota'))value={remaining:0}
      else if(p.endsWith('/sessions/'+sid))value={intent,expires_at:'2099-01-01T00:00:00Z'}
      else if(p.endsWith('/results/'+ref))value={result_ref:ref,count:0,intent_hash:'registration-owned',intent}
      else if(p.endsWith('/cards'))value={cards:{items:[],total:0,nextCursor:null,previousCursor:null},intent_hash:'registration-owned'}
      else if(p.endsWith('/save-token')){tokens++;value={token:'synthetic-signed-handoff',expires_in:300}}
      else throw Error('Unexpected request '+p)
      return route.fulfill({json:value})
    }
    if(p.startsWith('/api/'))return route.fulfill({status:404,json:{}})
    return route.continue()
  })
  await page.goto('/#/')
  await page.getByRole('button',{name:'También puedes escribir tu búsqueda',exact:true}).click()
  await page.getByRole('link',{name:'Regístrate para guardar esta búsqueda',exact:true}).click()
  if (flow !== 'register') {
    await page.getByRole('link',{name:'Accede',exact:true}).click()
    if (flow === 'login') await page.getByRole('button',{name:'Continuar con Google',exact:false}).click()
    else {
      await page.getByRole('button',{name:'Iniciar sesión con email',exact:true}).click()
      await page.getByRole('link',{name:'Crear una cuenta',exact:true}).click()
    }
  }
  if (flow !== 'login') {
    await page.locator('#register-name').fill('Synthetic Registration')
    await page.locator('#register-email').fill(`registration-${width}@example.test`)
    await page.locator('#register-password').fill('Synthetic-password-2026!')
    await page.locator('#register-confirm').fill('Synthetic-password-2026!')
    await page.getByRole('checkbox').check()
    await page.getByRole('button',{name:'Crear cuenta',exact:true}).click()
    await page.getByRole('link',{name:'Volver a mi búsqueda',exact:true}).click()
  }
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByText('700 EUR / mes',{exact:true}).first()).toBeVisible()
  const save=page.getByRole('button',{name:'Guardar búsqueda y activar avisos',exact:true})
  await expect(save).toBeEnabled();expect({searches,saves,tokens}).toEqual({searches:0,saves:0,tokens:0})
  await page.evaluate(async()=>{const client=await import('/src/api/client.ts');client.setAccessToken('synthetic-primary-token')})
  await save.click();await expect(page.getByText(/Búsqueda guardada\. Puedes pausar/)).toBeVisible()
  expect({searches,saves,tokens}).toEqual({searches:0,saves:1,tokens:1})
  const stored=await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}))
  expect(stored).not.toContain('synthetic-signed-handoff')
})

test('ordinary registration still leads to the profile', async ({page})=>{
  await page.addInitScript(()=>{localStorage.setItem('112233:language:v1','es');localStorage.setItem('112233:mobile-onboarding:v1','done')})
  await page.route('**/*',r=>new URL(r.request().url()).hostname!=='127.0.0.1'?r.abort():r.continue())
  await page.goto('/#/registro')
  await page.locator('#register-name').fill('Ordinary Synthetic')
  await page.locator('#register-email').fill('ordinary-registration@example.test')
  await page.locator('#register-password').fill('Synthetic-password-2026!')
  await page.locator('#register-confirm').fill('Synthetic-password-2026!')
  await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Crear cuenta',exact:true}).click()
  await expect(page.getByRole('link',{name:'Abrir mi perfil',exact:true})).toHaveAttribute('href','#/perfil')
  await expect(page.getByRole('link',{name:'Volver a mi búsqueda',exact:true})).toHaveCount(0)
})

for(const pending of [false,true]) test(`catalog status recovers automatically without dispatch; pending=${pending}`,async({page})=>{
  await page.clock.install()
  await page.addInitScript(()=>{localStorage.setItem('112233:language:v1','es');localStorage.setItem('112233:mobile-onboarding:v1','done')})
  let ready=pending,statusReads=0
  const keys:string[]=[]
  const sid='00000000-0000-4000-8000-000000000091'
  const session={intent:{schema_version:'ai-search.v1',taxonomy_version:'rental.v1',session_id:sid,version:0,criteria:{rental_mode:{strength:'hard',value:'long'}}},expires_at:'2099-01-01T00:00:00Z'}
  await page.route('**/*',route=>{
    const r=route.request(),u=new URL(r.url()),p=u.pathname
    if(u.hostname!=='127.0.0.1')return route.abort()
    if(p.startsWith('/ai-pilot/api/')){
      let value:unknown
      if(p.endsWith('/private-demo/status')){statusReads++;value={attempts:30,maximum:50,approved:false,halted:true,exhausted:false,catalog_ready:ready,local_housing_available:ready}}
      else if(p.endsWith('/capabilities'))value={text:true,map:true,voice:true,saved_searches:false}
      else if(p.endsWith('/quota'))value={remaining:3}
      else if(p.endsWith('/identity'))value={ready:true}
      else if(p.endsWith('/sessions')||p.endsWith('/sessions/'+sid))value=session
      else if(p.endsWith('/query')){
        keys.push(r.postDataJSON().idempotency_key)
        if(keys.length===1){ready=false;return route.fulfill({status:503,json:{detail:'SOURCE_COVERAGE_UNAVAILABLE'}})}
        value={operation:{status:'failed',remaining:3,failure_code:'INTENT_CLARIFICATION_REQUIRED',receipt:null},cards:null}
      }else throw Error('Unexpected recovery route '+p)
      return route.fulfill({json:value})
    }
    if(p.startsWith('/api/'))return route.fulfill({status:404,json:{}})
    return route.continue()
  })
  await page.goto('/#/');await page.getByRole('button',{name:'También puedes escribir tu búsqueda',exact:true}).click()
  await page.locator('#ai-search-text').fill('до 600 евро в месяц')
  if(pending){await page.getByRole('button',{name:'Buscar habitaciones',exact:true}).click();await expect(page.getByRole('button',{name:'Проверить результат попытки',exact:true})).toBeEnabled()}
  await expect(page.locator('[data-private-demo-status]')).toContainText(/actualiza|actualizando/)
  const stored=await page.evaluate(()=>sessionStorage.getItem('112233:ai-continuation:v1:public-guest'))
  const before=statusReads;ready=true;await page.clock.fastForward(5100)
  await expect(page.locator('[data-private-demo-status]')).toContainText('Busca por voz o texto')
  expect(statusReads).toBeGreaterThan(before);expect(keys.length).toBe(pending?1:0)
  expect(await page.evaluate(()=>sessionStorage.getItem('112233:ai-continuation:v1:public-guest'))).toBe(stored)
  if(pending){await page.getByRole('button',{name:'Проверить результат попытки',exact:true}).click();await expect(page.getByRole('button',{name:'Dictar búsqueda',exact:true})).toBeEnabled();expect(keys.length).toBe(2);expect(keys[0]).toBe(keys[1])}
  else await expect(page.getByRole('button',{name:'Buscar habitaciones',exact:true})).toBeEnabled()
  ready=false;await page.evaluate(()=>window.dispatchEvent(new Event('focus')))
  await expect(page.locator('[data-private-demo-status]')).toContainText('actualizando')
  await page.getByRole('button',{name:'Cerrar',exact:true}).click()
  // Radix retains the closing dialog until its exit animation finishes. With
  // the fake clock installed, finish that animation before testing unmount.
  await page.clock.runFor(500)
  await expect(page.locator('[data-private-demo-status]')).toHaveCount(0)
  const afterClose=statusReads;await page.clock.fastForward(15000);expect(statusReads).toBe(afterClose)
})
