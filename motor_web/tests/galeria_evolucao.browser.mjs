// Verifica reprodução/controles da galeria local; não julga qualidade visual.
import assert from 'node:assert/strict';import fs from 'node:fs';import path from 'node:path';import {pathToFileURL} from 'node:url';import puppeteer from 'puppeteer-core';
const root=path.resolve('docs/evolucao-mineracao-2026-10-29');
const browser=await puppeteer.launch({executablePath:process.env.CHROME,headless:true,timeout:90000,args:['--no-sandbox','--allow-file-access-from-files']});
try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(root,'comparacao.html')).href,{waitUntil:'networkidle0'});
 await page.waitForFunction(()=>[...document.querySelectorAll('video')].length===6&&[...document.querySelectorAll('video')].every(v=>v.readyState>=1),{timeout:30000});
 await page.evaluate(()=>{const slider=document.getElementById('time');slider.value=4.5;slider.dispatchEvent(new Event('input'));});
 await page.waitForFunction(()=>[...document.querySelectorAll('video')].every(v=>Math.abs(v.currentTime-4.5)<.1));
 const videos=await page.evaluate(()=>[...document.querySelectorAll('video')].map(v=>({w:v.videoWidth,h:v.videoHeight,dur_s:v.duration,webm:v.currentSrc.endsWith('.webm'),t:v.currentTime})));
 await page.click('#play');await page.waitForFunction(()=>[...document.querySelectorAll('video')].every(v=>!v.paused));await page.click('#play');
 const paused=await page.evaluate(()=>[...document.querySelectorAll('video')].every(v=>v.paused));
 assert.equal(videos.length,6);assert(videos.every(v=>v.w===540&&v.h===960&&v.webm&&Math.abs(v.dur_s-6)<.1));assert(paused);assert.deepEqual(errors,[]);
 const result={videos,busca_sincronizada:true,play_pause:true,errors,modo:'teste de funcionamento; sem avaliação semântica'};
 fs.writeFileSync(path.join(root,'galeria-verificada.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({videos:6,busca_sincronizada:true,play_pause:true,errors}));
}finally{await browser.close();}
