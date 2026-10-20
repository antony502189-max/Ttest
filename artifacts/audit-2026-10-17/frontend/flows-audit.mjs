import { chromium, expect } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
const dir = new URL('./', import.meta.url).pathname.replace(/^\/([A-Z]:)/, '$1');
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
const results=[];
async function setup(width=1280){
 const context=await browser.newContext({viewport:{width,height:900}});
 await context.addInitScript(()=>{localStorage.setItem('112233:session:v1',JSON.stringify('host-demo'));localStorage.setItem('112233:mobile-onboarding:v1','done');localStorage.setItem('112233:language:v1','ru');});
 const page=await context.newPage();page.setDefaultNavigationTimeout(90000);await page.route('https://**/*',r=>r.abort());return {context,page};
}
async function run(name,fn){try{results.push({name,...await fn()});}catch(e){results.push({name,error:String(e),stack:e.stack});}}
try {
 await run('Madrid-real-user-autocomplete',async()=>{
  const {context,page}=await setup();
  await page.goto('http://127.0.0.1:4174/#/publicar',{waitUntil:'commit'});
  await expect(page.locator('#publish-street[data-address-autocomplete="native"]')).toBeVisible();
  await page.evaluate(()=>{window.__112233TestAddressPredictions=async()=>[{label:'Calle Mayor 1, 28013 Madrid, Spain',detail:{formattedAddress:'Calle Mayor 1, 28013 Madrid, Spain',coordinates:{lat:40.4168,lng:-3.7038},addressComponents:[{longText:'Calle Mayor',types:['route']},{longText:'1',types:['street_number']},{longText:'28013',types:['postal_code']},{longText:'Madrid',types:['locality']},{longText:'Centro',types:['neighborhood']},{longText:'Spain',types:['country']}]}}];});
  await page.locator('#publish-street').fill('Calle Mayor 1, Madrid');
  await page.locator('.publish-address-prediction').first().click();
  await expect(page.locator('.publish-address-assist__status')).toContainText('Не удалось открыть');
  const state=await page.evaluate(()=>({province:document.querySelector('#publish-province').value,postcode:document.querySelector('#publish-postcode').value,city:document.querySelector('#publish-city').value,status:document.querySelector('.publish-address-assist__status').textContent,center:window.__googleMapsTestLastMap?{lat:window.__googleMapsTestLastMap.getCenter().lat(),lng:window.__googleMapsTestLastMap.getCenter().lng()}:null}));
  await page.screenshot({path:dir+'/madrid-autocomplete-rejected.png'});await context.close();return state;
 });
 await run('approved-parent-desktop-selector',async()=>{
  const {context,page}=await setup();
  await page.goto('http://127.0.0.1:4185/#/',{waitUntil:'commit'});
  await page.locator('.search-location .location-selector-trigger').first().click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.waitForTimeout(300);
  await page.screenshot({path:dir+'/baseline-selector-1280.png'});
  const state=await page.getByRole('dialog').evaluate(e=>({rect:e.getBoundingClientRect().toJSON(),className:e.className,text:e.textContent.slice(0,1000)}));
  await context.close();return state;
 });
 await run('current-desktop-selector',async()=>{
  const {context,page}=await setup();await page.goto('http://127.0.0.1:4174/#/',{waitUntil:'commit'});await page.locator('.search-location .location-selector-trigger').first().click();await expect(page.getByRole('dialog')).toBeVisible();await page.waitForTimeout(300);await page.screenshot({path:dir+'/current-selector-1280.png'});
  const state=await page.getByRole('dialog').evaluate(e=>({rect:e.getBoundingClientRect().toJSON(),className:e.className,rowBackground:getComputedStyle(e.querySelector('.m2-community-option')).backgroundColor,listBackground:getComputedStyle(e.querySelector('.m2-community-suggestions')).backgroundColor}));await context.close();return state;
 });
 await run('Madrid-map-camera',async()=>{
  const {context,page}=await setup(390);
  await page.goto('http://127.0.0.1:4174/#/buscar?q=Madrid&provincia=28&vista=mapa&alquiler=long',{waitUntil:'commit'});
  await expect(page.locator('[data-test-map-sdk="1"]')).toHaveCount(1);
  await expect.poll(()=>page.evaluate(()=>Boolean(window.__googleMapsTestLastMap))).toBe(true);
  await page.waitForTimeout(500);
  const state=await page.evaluate(()=>({header:document.querySelector('.m2-map-results-header').textContent,center:{lat:window.__googleMapsTestLastMap.getCenter().lat(),lng:window.__googleMapsTestLastMap.getCenter().lng()},zoom:window.__googleMapsTestLastMap.getZoom()}));
  await page.screenshot({path:dir+'/madrid-map-camera.png'});await context.close();return state;
 });
 await run('countdown-reload-minus-24h',async()=>{
  const {context,page}=await setup();const start=Date.now(),expires=start+3665000;let requests=0;
  await page.clock.install({time:new Date(start-86400000)});
  await page.route('**/payments/listings/*/top/availability?*',route=>{requests++;return route.fulfill({json:{province:'Madrid',available:false,availableSlots:0,serverNow:new Date(start).toISOString(),availableAt:new Date(expires).toISOString()}})});
  async function open(){await page.goto('http://127.0.0.1:4174/#/mis-anuncios',{waitUntil:'commit'});await page.getByTestId('owner-top-promote-button').first().click();await page.getByTestId('owner-promotion-choices').getByRole('button').last().click();await expect(page.getByRole('timer')).toHaveText(/01:01:0[45]/);return page.getByRole('timer').innerText();}
  const before=await open();await page.reload({waitUntil:'commit'});const after=await open();await context.close();return{before,after,requests,note:'API fixture sends unchanged authoritative time on every request; proves browser wall clock offset does not alter timer and reload fetches API.'};
 });
} finally {await writeFile(dir+'/flows-results.json',JSON.stringify(results,null,2));await browser.close();console.log(JSON.stringify(results,null,2));}
