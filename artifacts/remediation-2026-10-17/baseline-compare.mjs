import {chromium,expect} from '../../output/remediation-frontend/node_modules/@playwright/test/index.mjs';
import {writeFile} from 'node:fs/promises';
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
const results=[];
try {
 for(const [name,port] of [['parent',4193],['fixed',4192]]) {
  const context=await browser.newContext({viewport:{width:1280,height:900}});
  await context.addInitScript(()=>{localStorage.setItem('112233:language:v1','ru');localStorage.setItem('112233:mobile-onboarding:v1','done');});
  const page=await context.newPage();await page.route('https://**/*',r=>r.abort());
  const errors=[];page.on('response',r=>{if(r.status()===403) errors.push(r.url());});
  await page.goto(`http://127.0.0.1:${port}/#/`,{waitUntil:'domcontentloaded'});
  await page.locator('.location-selector-trigger').first().click();
  const dialog=page.getByRole('dialog');
  await expect.poll(async()=>Math.round((await dialog.boundingBox()).width)).toBe(1216);
  await page.evaluate(()=>document.fonts.ready);
  const rect=await dialog.boundingBox();
  const actions=await dialog.locator('.location-action-list').innerText();
  await dialog.screenshot({path:`artifacts/remediation-2026-10-17/selector-${name}-1280.png`});
  results.push({name,rect,actions,font403:errors.length});
  await context.close();
 }
 await writeFile('artifacts/remediation-2026-10-17/design-comparison.json',JSON.stringify(results,null,2));
 console.log(JSON.stringify(results));
}finally{await browser.close();}
