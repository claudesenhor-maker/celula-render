// A galeria precisa funcionar também em Chromium sem H.264.
import puppeteer from 'puppeteer-core';import assert from 'node:assert/strict';import fs from 'node:fs';import {fileURLToPath,pathToFileURL} from 'node:url';import path from 'node:path';
const arquivo=path.resolve(process.argv[2]||fileURLToPath(new URL('../../docs/experimentos-2026-10-29/index.html',import.meta.url)));
const browser=await puppeteer.launch({executablePath:process.env.CHROME||'/home/azureuser/.cache/ms-playwright/chromium-1140/chrome-linux/chrome',headless:true,args:['--no-sandbox']});
try{const page=await browser.newPage(),erros=[];page.on('pageerror',e=>erros.push(e.message));await page.goto(pathToFileURL(arquivo).href);
 await page.waitForFunction(()=>[...document.querySelectorAll('video')].length===6&&[...document.querySelectorAll('video')].every(v=>v.readyState>=1));
 const videos=await page.evaluate(()=>[...document.querySelectorAll('video')].map(v=>({largura:v.videoWidth,altura:v.videoHeight,duracao:v.duration,formato:v.currentSrc.slice(0,20)})));
 assert(videos.every(v=>v.largura===540&&v.altura===960&&Math.abs(v.duracao-6)<.01));
 await page.evaluate(()=>{const r=document.querySelector('input');r.value='4.5';r.dispatchEvent(new Event('input'));});
 await page.waitForFunction(()=>[...document.querySelectorAll('video')].slice(0,2).every(v=>Math.abs(v.currentTime-4.5)<.01));
 await page.evaluate(()=>{const r=document.querySelector('input');r.value='0';r.dispatchEvent(new Event('input'));});
 await page.click('.play');await page.waitForFunction(()=>[...document.querySelectorAll('video')].slice(0,2).every(v=>!v.paused));
 await page.click('.play');await page.waitForFunction(()=>[...document.querySelectorAll('video')].slice(0,2).every(v=>v.paused));
 assert.deepEqual(erros,[]);
 const resultado={videos,controles_sincronizados:true,reproduz_e_pausa:true,erros};fs.writeFileSync(path.join(path.dirname(arquivo),'galeria-verificada.json'),JSON.stringify(resultado,null,2));console.log(JSON.stringify(resultado));
}finally{await browser.close()}
