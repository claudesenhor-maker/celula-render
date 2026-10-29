// CHROME=/.../chrome node motor_web/tests/auditar_graficos.mjs [raiz-do-motor] [pasta-saida]
import fs from 'node:fs';import path from 'node:path';import {pathToFileURL,fileURLToPath} from 'node:url';
import puppeteer from 'puppeteer-core';import {FIXTURES,fixture} from './fixtures_graficos.mjs';
const raiz=path.resolve(process.argv[2]||path.join(path.dirname(fileURLToPath(import.meta.url)),'..'));
const saida=path.resolve(process.argv[3]||'docs/melhoria-motores-2026-10-26/atual');fs.mkdirSync(saida,{recursive:true});
const browser=await puppeteer.launch({executablePath:process.env.CHROME,headless:true,args:['--no-sandbox','--allow-file-access-from-files','--enable-webgl','--ignore-gpu-blocklist','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const resultados=[];
try{for(const estilo of Object.keys(FIXTURES)){
 if(process.env.ESTILO && process.env.ESTILO!==estilo)continue;
 const page=await browser.newPage(),erros=[];page.on('pageerror',e=>erros.push(e.message));
 await page.goto(pathToFileURL(path.join(raiz,'palco.html')).href,{waitUntil:'networkidle0',timeout:60000});
 const spec=fixture(estilo);fs.writeFileSync(path.join(saida,estilo+'.json'),JSON.stringify(spec,null,2));
 const prep=await page.evaluate(s=>window.preparar(s),spec),tempos=[];const frames=[];
 for(const t of [0,1.5,4.5,6]){const inicio=performance.now();const q=await page.evaluate(t=>{const imagem=window.quadro(t,'image/png');return {imagem,metricas:window.METRICAS_RENDER||null};},t);
  tempos.push(performance.now()-inicio);frames.push(q.imagem);fs.writeFileSync(path.join(saida,`${estilo}-${t}.png`),Buffer.from(q.imagem.split(',')[1],'base64'));}
 const repetido=await page.evaluate(()=>window.quadro(1.5,'image/png'));
 const diferenca=await page.evaluate(async({a,b})=>{const ca=document.createElement('canvas');ca.width=1080;ca.height=1920;const ctx=ca.getContext('2d',{willReadFrequently:true});
  const pixels=async url=>{const im=new Image();im.src=url;await im.decode();ctx.clearRect(0,0,1080,1920);ctx.drawImage(im,0,0);return ctx.getImageData(0,0,1080,1920).data;};
  const aa=await pixels(a),bb=await pixels(b);let max=0,alterados=0,maiores4=0;for(let i=0;i<aa.length;i+=4){let d=0;for(let j=0;j<3;j++)d=Math.max(d,Math.abs(aa[i+j]-bb[i+j]));max=Math.max(max,d);if(d)alterados++;if(d>4)maiores4++;}return {max,alterados,maiores4};
 },{a:frames[1],b:repetido});
 const suavizacao=await page.evaluate(()=>SAIDA_INICIO_T272.getContext('2d').imageSmoothingEnabled);
 const stats=await page.evaluate(()=>window.METRICAS_RENDER||null);
 const resultado={estilo,erros,fontes:prep.fontes,ms:tempos,diferenca,suavizacao,metricas:stats};resultados.push(resultado);console.log(JSON.stringify(resultado));
 await page.close();
}}finally{await browser.close();fs.writeFileSync(path.join(saida,process.env.ESTILO?'resultados-'+process.env.ESTILO+'.json':'resultados.json'),JSON.stringify(resultados,null,2));}
if(resultados.some(r=>r.erros.length||r.diferenca.maiores4>1080*1920*.001))process.exitCode=1;
