import { expect, test } from '@playwright/test'

for(const width of [390,1440]) for(const detail of ['AI_REQUEST_INVALID','OTHER_BAD_REQUEST']) test(`voice ${width}px 400 ${detail} respects the exact pre-reservation contract`,async({page})=>{
  await page.setViewportSize({width,height:1000})
  const sid='00000000-0000-4000-8000-000000000041'
  let uploads=0,operationReads=0
  const session={intent:{schema_version:'ai-search.v1',taxonomy_version:'rental.v1',session_id:sid,version:0,criteria:{rental_mode:{strength:'hard',value:'long'}}},expires_at:'2099-01-01T00:00:00Z'}
  await page.route('**/ai-pilot/api/**',async route=>{
    const path=new URL(route.request().url()).pathname
    if(path.endsWith('/voice')){uploads++;return route.fulfill({status:400,json:{detail}})}
    if(path.includes('/operations/'))operationReads++
    const value=path.endsWith('/private-demo/status')?{attempts:9,maximum:50,approved:true,halted:false,exhausted:false,catalog_ready:true}
      :path.endsWith('/capabilities')?{text:true,map:true,voice:true,saved_searches:false}
      :path.endsWith('/quota')?{remaining:3}
      :path.endsWith('/identity')?{ready:true}:session
    return route.fulfill({json:value})
  })
  await page.goto('./#/')
  await page.getByRole('button',{name:'Buscar con la voz',exact:true}).click()
  const mic=page.getByRole('button',{name:'Надиктовать запрос',exact:true})
  await mic.click();await expect(page.getByText('Идёт запись…',{exact:true})).toBeVisible()
  await page.waitForTimeout(300)
  await page.getByRole('button',{name:'Остановить и искать',exact:true}).click()
  if(detail==='AI_REQUEST_INVALID'){
    await expect(mic).toBeEnabled()
    await expect(page.getByRole('button',{name:'Проверить результат попытки',exact:true})).toHaveCount(0)
    await page.reload()
    await page.getByRole('button',{name:'Buscar con la voz',exact:true}).click()
    await expect(mic).toBeEnabled()
    expect(operationReads).toBe(0)
  }else{
    await expect(page.getByRole('button',{name:'Проверить результат попытки',exact:true})).toBeEnabled()
    await expect(mic).toBeDisabled()
  }
  expect(uploads).toBe(1)
})

for(const width of [390,1440]) for(const failure of ['INTENT_UNSUPPORTED','VOICE_CAPACITY_LIMIT']) test(`voice ${width}px processing ${failure} is distinct from replay and unlocks the microphone`, async ({page}) => {
  await page.setViewportSize({width,height:1000})
  const sid='00000000-0000-4000-8000-000000000031'
  let release=()=>{}, uploads=0
  const gate=new Promise<void>(resolve=>{release=resolve})
  let settledKey=''
  const session={intent:{schema_version:'ai-search.v1',taxonomy_version:'rental.v1',session_id:sid,version:0,criteria:{rental_mode:{strength:'hard',value:'long'}}},expires_at:'2099-01-01T00:00:00Z'}
  await page.route('**/ai-pilot/api/**',async route=>{
    const path=new URL(route.request().url()).pathname
    let value:unknown
    if(path.endsWith('/private-demo/status'))value={attempts:8,maximum:50,approved:true,halted:false,exhausted:false,catalog_ready:true}
    else if(path.endsWith('/capabilities'))value={text:true,map:true,voice:true,saved_searches:false}
    else if(path.endsWith('/quota'))value={remaining:3}
    else if(path.endsWith('/identity'))value={ready:true}
    else if(path.endsWith('/sessions')||path.endsWith('/sessions/'+sid))value=session
    else if(path.endsWith('/voice')){
      uploads++;settledKey=route.request().postDataJSON().idempotency_key;await gate
      value={operation:{status:'failed',remaining:3,failure_code:failure,receipt:null},cards:null}
    }else throw Error('Unexpected voice request '+path)
    return route.fulfill({json:value})
  })
  await page.goto('./#/')
  await page.getByRole('button',{name:'Buscar con la voz',exact:true}).click()
  const mic=page.getByRole('button',{name:'Надиктовать запрос',exact:true})
  await mic.click()
  await expect(page.getByText('Идёт запись…',{exact:true})).toBeVisible()
  await page.waitForTimeout(300)
  await page.getByRole('button',{name:'Остановить и искать',exact:true}).click()
  try {
    await expect(page.locator('[data-voice-unavailable]')).toHaveText('Обрабатываем запрос и ищем варианты…')
    await expect(page.getByRole('button',{name:'Проверить результат попытки',exact:true})).toHaveCount(0)
    await expect(mic).toBeDisabled()
  }finally{release()}
  await expect(page.getByText(failure==='INTENT_UNSUPPORTED'?'Не удалось разобрать бюджет из записи. Повторите или введите его текстом. Поиск не списан.':'Сервер распознавания занят. Повторите запись позже. Поиск не списан.',{exact:true})).toBeVisible()
  await expect(mic).toBeEnabled()
  await expect(page.locator('[data-voice-unavailable]')).toHaveCount(0)
  expect(await page.evaluate(()=>JSON.stringify(Object.values(sessionStorage)))).not.toContain(settledKey)
  expect(uploads).toBe(1)
})

for (const state of ['stale', 'quota', 'approved']) test(`voice explains ${state} availability beside the microphone`, async ({ page }) => {
  let calls = 0
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => { throw new Error('Microphone must not open') }
  })
  await page.route('**/*', route => {
    const path = new URL(route.request().url()).pathname
    if (!path.includes('/api/')) return route.continue()
    if (path.endsWith('/private-demo/status')) return route.fulfill({json:{attempts:8,maximum:50,exhausted:false,halted:state === 'stale',approved:true,catalog_ready:state !== 'stale'}})
    if (path.endsWith('/capabilities')) return route.fulfill({json:{text:true,map:true,voice:true,saved_searches:false}})
    if (path.endsWith('/quota')) return route.fulfill({json:{remaining:state === 'quota' ? 0 : 3}})
    if (path.endsWith('/voice') || path.endsWith('/query')) calls++
    return route.fulfill({json:{}})
  })
  await page.goto('./#/')
  await page.getByRole('button',{name:'Buscar con la voz',exact:true}).click()
  const mic = page.getByRole('button',{name:'Надиктовать запрос',exact:true})
  if (state === 'approved') {
    await expect(mic).toBeEnabled()
    await expect(page.locator('[data-voice-unavailable]')).toHaveCount(0)
  } else {
    await expect(mic).toBeDisabled()
    await expect(page.locator('[data-voice-unavailable]')).toContainText(state === 'stale' ? 'Каталог устарел' : 'Лимит запросов исчерпан')
    await expect(mic).toHaveAccessibleDescription(state === 'stale' ? /Каталог устарел/ : /Лимит запросов исчерпан/)
  }
  expect(calls).toBe(0)
})

for (const width of [390, 1440]) test(`voice ${width}px cancels, retries exact PCM and restores without audio`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 })
  const sid = '00000000-0000-4000-8000-000000000011', ref = '00000000-0000-4000-8000-000000000012'
  let version = 0, executions = 0, lost = false
  const uploads: {audio_base64:string}[] = []
  const intent = () => ({schema_version:'ai-search.v1',taxonomy_version:'rental.v1',session_id:sid,version,
    criteria:{rental_mode:{strength:'hard',value:'long'},...(version ? {budget:{strength:'hard',value:{amount:'600',currency:'EUR',period:'monthly'}}} : {})}})
  const cards = () => ({cards:{items:[],total:0,nextCursor:null,previousCursor:null},intent_hash:'voice-hash'})
  await page.addInitScript(() => {
    const capture = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices)
    ;(window as unknown as {voiceTracks: MediaStreamTrack[]}).voiceTracks = []
    navigator.mediaDevices.getUserMedia = async constraints => {
      const stream = await capture(constraints)
      ;(window as unknown as {voiceTracks: MediaStreamTrack[]}).voiceTracks.push(...stream.getTracks())
      return stream
    }
  })
  await page.route('**/*', async route => {
    const path = new URL(route.request().url()).pathname
    if (!path.includes('/api/')) return route.continue()
    expect(path.startsWith('/ai-pilot/api/')).toBe(true)
    let value: unknown
    if (path.endsWith('/private-demo/status')) value = {attempts:executions,maximum:50,approved:true,halted:false,exhausted:false,catalog_ready:true}
    else if (path.endsWith('/capabilities')) value = {text:true,map:true,voice:true,saved_searches:false}
    else if (path.endsWith('/quota')) value = {remaining:3-executions}
    else if (path.endsWith('/identity')) value = {ready:true}
    else if (path.endsWith('/sessions') || path.endsWith('/sessions/'+sid)) value = {intent:intent(),expires_at:'2099-01-01T00:00:00Z'}
    else if (path.endsWith('/voice')) {
      const audio = route.request().postDataJSON(); uploads.push(audio)
      expect(audio.media_type).toBe('audio/wav'); expect(audio.text).toBeUndefined()
      const bytes = Buffer.from(audio.audio_base64,'base64')
      expect(bytes.subarray(0,4).toString()).toBe('RIFF'); expect(bytes.readUInt32LE(24)).toBe(16000)
      expect(bytes.length).toBeGreaterThanOrEqual(3244); expect(bytes.length).toBeLessThanOrEqual(480044)
      if (!lost) { lost=true; version=1; executions=1; return route.fulfill({status:503,json:{detail:'LOST_ACK'}}) }
      value = {operation:{status:'succeeded',remaining:2,receipt:{result_ref:ref,count:0}},cards:cards()}
    } else if (path.includes('/operations/')) value = {status:'succeeded',idempotency_key:path.split('/').at(-1),remaining:2,receipt:{result_ref:ref,count:0}}
    else if (path.endsWith('/cards')) value = cards()
    else if (path.endsWith('/results/'+ref)) value = {result_ref:ref,count:0,intent_hash:'voice-hash',intent:intent()}
    else throw new Error('Unexpected voice endpoint '+path)
    return route.fulfill({json:value})
  })
  await page.goto('./#/')
  await page.getByRole('button',{name:'Escribir mi búsqueda',exact:true}).click()
  await page.getByRole('button',{name:'Надиктовать запрос',exact:true}).click()
  await expect(page.getByText('Идёт запись…',{exact:true})).toBeVisible()
  await page.screenshot({path:`output/ai-voice-20261108/recording-${width}.png`})
  await page.getByRole('button',{name:'Отменить запись',exact:true}).click()
  expect(uploads).toHaveLength(0)
  expect(await page.evaluate(() => (window as unknown as {voiceTracks: MediaStreamTrack[]}).voiceTracks.every(track => track.readyState === 'ended'))).toBe(true)
  await page.getByRole('button',{name:'Надиктовать запрос',exact:true}).click()
  await expect(page.getByText('Идёт запись…',{exact:true})).toBeVisible()
  await page.waitForTimeout(300) // At least 100ms of actual worklet PCM.
  await page.getByRole('button',{name:'Остановить и искать',exact:true}).click()
  await page.getByRole('button',{name:'Проверить результат попытки',exact:true}).click()
  await expect(page.getByText('Búsquedas disponibles hoy: 2')).toBeVisible()
  expect(uploads).toHaveLength(2); expect(uploads[0]).toEqual(uploads[1]); expect(executions).toBe(1)
  expect(await page.evaluate(() => (window as unknown as {voiceTracks: MediaStreamTrack[]}).voiceTracks.every(track => track.readyState === 'ended'))).toBe(true)
  expect(await page.evaluate(() => JSON.stringify([Object.values(localStorage),Object.values(sessionStorage)]))).not.toContain(uploads[0].audio_base64)
  await page.reload()
  await page.getByRole('button',{name:'Escribir mi búsqueda',exact:true}).click()
  await expect(page.getByText('600 EUR / mes').first()).toBeVisible()
  expect(uploads).toHaveLength(2)
})

test('voice permission denial preserves text fallback and performs no upload', async ({ page }) => {
  await page.addInitScript(() => {
    navigator.mediaDevices.getUserMedia = async () => { throw new DOMException('fixture denial','NotAllowedError') }
  })
  await page.route('**/ai-pilot/api/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/capabilities')) return route.fulfill({json:{text:true,map:true,voice:true,saved_searches:false}})
    if (path.endsWith('/private-demo/status')) return route.fulfill({json:{attempts:0,maximum:50,approved:true,halted:false,exhausted:false,catalog_ready:true}})
    if (path.endsWith('/quota')) return route.fulfill({json:{remaining:3}})
    throw new Error('Unexpected upload '+path)
  })
  await page.goto('./#/')
  await page.getByRole('button',{name:'Escribir mi búsqueda',exact:true}).click()
  await page.getByRole('button',{name:'Надиктовать запрос',exact:true}).click()
  await expect(page.getByRole('alert')).toContainText('Разрешите доступ')
  await page.locator('#ai-search-text').fill('до 600 евро в месяц')
  await expect(page.getByRole('button',{name:'Buscar habitaciones',exact:true})).toBeEnabled()
})

test('closing while microphone permission is pending stops a late stream without uploading', async ({ page }) => {
  await page.addInitScript(() => {
    const state = window as unknown as {releaseVoicePermission: () => void; lateTrackStopped: boolean}
    state.lateTrackStopped = false
    navigator.mediaDevices.getUserMedia = () => new Promise<MediaStream>(resolve => {
      state.releaseVoicePermission = () => resolve({ getTracks: () => [{ stop: () => { state.lateTrackStopped = true } }] } as unknown as MediaStream)
    })
  })
  await page.route('**/ai-pilot/api/**', route => {
    const path = new URL(route.request().url()).pathname
    if (path.endsWith('/capabilities')) return route.fulfill({json:{text:true,map:true,voice:true,saved_searches:false}})
    if (path.endsWith('/private-demo/status')) return route.fulfill({json:{attempts:0,maximum:50,approved:true,halted:false,exhausted:false,catalog_ready:true}})
    if (path.endsWith('/quota')) return route.fulfill({json:{remaining:3}})
    throw new Error('Unexpected upload '+path)
  })
  await page.goto('./#/')
  await page.getByRole('button',{name:'Escribir mi búsqueda',exact:true}).click()
  await page.getByRole('button',{name:'Надиктовать запрос',exact:true}).click()
  await expect(page.getByText('Ожидаем доступ к микрофону…',{exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Cerrar',exact:true}).click()
  await page.evaluate(() => (window as unknown as {releaseVoicePermission: () => void}).releaseVoicePermission())
  await expect.poll(() => page.evaluate(() => (window as unknown as {lateTrackStopped: boolean}).lateTrackStopped)).toBe(true)
})
