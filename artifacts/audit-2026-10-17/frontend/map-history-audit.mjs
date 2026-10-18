import { chromium, expect } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
const context=await browser.newContext({viewport:{width:390,height:844}});
await context.addInitScript(()=>{
 localStorage.setItem('112233:mobile-onboarding:v1','done');localStorage.setItem('112233:language:v1','ru');
 localStorage.setItem('112233:map-last-search-area:v2',JSON.stringify({center:{lat:28.2916,lng:-16.6291},savedAt:Date.now()}));
});
const page=await context.newPage();await page.route('https://**/*',r=>r.abort());
const results=[];
try {
 for(const path of ['q=Madrid&provincia=28','q=Madrid&comunidad=13']){
  await page.goto('http://127.0.0.1:4174/#/buscar?'+path+'&vista=mapa&alquiler=long',{waitUntil:'commit'});
  await expect(page.locator('[data-test-map-sdk="1"]')).toHaveCount(1);await page.waitForTimeout(350);
  results.push(await page.evaluate(()=>({hash:location.hash,center:{lat:window.__googleMapsTestLastMap.getCenter().lat(),lng:window.__googleMapsTestLastMap.getCenter().lng()},zoom:window.__googleMapsTestLastMap.getZoom()})));
  if(path.includes('provincia')) await page.screenshot({path:'artifacts/audit-2026-10-17/frontend/madrid-map-history.png'});
  await page.goto('http://127.0.0.1:4174/#/',{waitUntil:'commit'});
 }
}finally{await writeFile('artifacts/audit-2026-10-17/frontend/map-history-results.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results,null,2));await browser.close();}
