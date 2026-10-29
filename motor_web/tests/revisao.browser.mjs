// Teste real da revisão com servidor local simulado; não usa uma API de IA externa.
import assert from 'node:assert/strict';import http from 'node:http';import fs from 'node:fs';import path from 'node:path';import os from 'node:os';import {fileURLToPath,pathToFileURL} from 'node:url';
import puppeteer from 'puppeteer-core';import {fixture} from './fixtures_graficos.mjs';import {prepararSpec} from '../diretor_visual.mjs';import {revisarAntesDoRender} from '../preflight.mjs';
let chamadas=0;const server=http.createServer((req,res)=>{let body='';req.on('data',s=>body+=s);req.on('end',()=>{const d=JSON.parse(body);assert(d.quadros.length>=3);assert(d.quadros[0].imagem.length>1000);chamadas++;
 res.setHeader('Content-Type','application/json');res.end(JSON.stringify(chamadas===1?{aprovado:false,problemas:['teste de reenquadramento'],correcoes:[{cena:1,camera:'perto',plano:{zoom:1.05}}]}:{aprovado:true,problemas:[],correcoes:[]}));});});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const anterior=process.env.VIDEO_REVISOR_URL;process.env.VIDEO_REVISOR_URL=`http://127.0.0.1:${server.address().port}`;
let browser;
try {
 browser=await puppeteer.launch({executablePath:process.env.CHROME,headless:true,args:['--no-sandbox','--allow-file-access-from-files','--enable-webgl','--ignore-gpu-blocklist','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 const page=await browser.newPage(),erros=[];page.on('pageerror',e=>erros.push(e.message));
 await page.goto(pathToFileURL(path.join(path.dirname(fileURLToPath(import.meta.url)),'../palco.html')).href,{waitUntil:'networkidle0'});
 const spec=prepararSpec(fixture('mecanismo'));spec.w=540;spec.h=960;
 await page.evaluate(s=>window.preparar(s),spec);
 const saida=path.join(fs.mkdtempSync(path.join(os.tmpdir(),'revisao-browser-')),'ensaio.mp4');
 const final=await revisarAntesDoRender(page,spec,saida);assert.equal(chamadas,2);assert.equal(final.cenas[1].camera,'perto');assert.equal(final.cenas[1].plano.zoom,1.05);assert.deepEqual(erros,[]);
 console.log(JSON.stringify({aprovado:true,chamadas,repreparacao:true,erros,relatorio:saida+'.direcao.json'}));
}finally{if(browser)await browser.close();if(anterior==null)delete process.env.VIDEO_REVISOR_URL;else process.env.VIDEO_REVISOR_URL=anterior;server.closeAllConnections();await new Promise(r=>server.close(r));}
