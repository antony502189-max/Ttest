import { chromium, expect } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
const dir = new URL('./', import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1');
const browser = await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const results=[];
const base='http://127.0.0.1:4174';
async function setup(width) {
 const context=await browser.newContext({viewport:{width,height:900}});
 await context.addInitScript(()=>{localStorage.setItem('112233:session:v1',JSON.stringify('host-demo'));localStorage.setItem('112233:mobile-onboarding:v1','done');localStorage.setItem('112233:language:v1','ru');});
 const page=await context.newPage();
 page.setDefaultNavigationTimeout(90000);
 await page.route('https://**/*',r=>r.abort());
 return {context,page};
}
try {
 for(const width of [320,768,1280]) {
  const {context,page}=await setup(width);
  await page.goto(base+'/#/?panel=ubicacion',{waitUntil:'domcontentloaded'});
  if(width>=768){await page.locator('.search-location .location-selector-trigger').first().click();}
  await expect(page.getByTestId('province-suggestions')).toBeVisible();
  const container=width>=768?page.getByRole('dialog'):page.locator('.m2-location');
  await page.screenshot({path:dir+`/location-${width}.png`,fullPage:true});
  results.push({case:'province-selector',width,layout:await container.evaluate(e=>({rect:e.getBoundingClientRect().toJSON(),overflow:getComputedStyle(e).overflow,minHeight:getComputedStyle(e).minHeight})),document:await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight})),search:await page.getByRole('searchbox').boundingBox()});
  await context.close();
 }
 const {context,page}=await setup(1280);
 let requests=0;
 const serverTime=Date.now();
 const expires=serverTime+4000;
 await page.clock.install({time:new Date(serverTime+86400000)});
 await page.route('**/payments/listings/*/top/availability?*',route=>{requests++; const released=requests>=2; return route.fulfill({json:{province:'Madrid',available:released,availableSlots:released?1:0,serverNow:new Date(serverTime).toISOString(),availableAt:new Date(expires).toISOString()}});});
 await page.goto(base+'/#/mis-anuncios',{waitUntil:'domcontentloaded'});
 await page.getByTestId('owner-top-promote-button').first().click();
 await page.getByTestId('owner-promotion-choices').getByRole('button').last().click();
 await expect(page.getByRole('timer')).toHaveText('00:00:04');
 await expect(page.getByRole('dialog').getByRole('status')).toContainText('все места TOP');
 results.push({case:'clock-plus-24h',timer:await page.getByRole('timer').innerText(),soldOutMessage:await page.getByRole('dialog').getByRole('status').innerText(),continueDisabled:await page.getByRole('button',{name:'Продолжить',exact:true}).isDisabled()});
 await page.clock.fastForward(5000);
 await expect(page.getByRole('button',{name:'Продолжить',exact:true})).toBeEnabled();
 results.push({case:'zero-revalidation',requests,continueEnabled:true});
 await context.close();
} catch(error) {results.push({error:String(error),stack:error.stack});process.exitCode=1;}
finally {await writeFile(dir+'/ui-results.json',JSON.stringify(results,null,2));await browser.close();console.log(JSON.stringify(results,null,2));}
