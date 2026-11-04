// Mesmos specs/tempos para base e candidato. Vídeos de inspeção, sem publicação.
import fs from 'node:fs';import path from 'node:path';import {pathToFileURL} from 'node:url';import {spawn} from 'node:child_process';
import puppeteer from 'puppeteer-core';import {COMPARACOES} from './comparacoes.fixtures.mjs';
const raiz=path.resolve(process.argv[2]||'motor_web'),saida=path.resolve(process.argv[3]||'docs/experimentos-2026-10-29/depois');
fs.mkdirSync(saida,{recursive:true});
const fps=12, chrome=process.env.CHROME||'/home/azureuser/.cache/ms-playwright/chromium-1140/chrome-linux/chrome';
const browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--allow-file-access-from-files','--enable-webgl','--ignore-gpu-blocklist','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const results=[];
try{for(const [nome,spec] of Object.entries(COMPARACOES).sort(([a],[b])=>(a==='mecanismo')-(b==='mecanismo'))){
 if(process.env.ESTILO && process.env.ESTILO!==nome)continue;
 const page=await browser.newPage();const erros=[];page.on('pageerror',e=>erros.push(e.message));
 await page.goto(pathToFileURL(path.join(raiz,'palco.html')).href,{waitUntil:'networkidle0'});
 const prep=await page.evaluate(s=>window.preparar(s),spec);if(!prep.fontes.every(Boolean))throw Error('Fontes ausentes: '+nome);
 fs.writeFileSync(path.join(saida,nome+'.json'),JSON.stringify(spec,null,2));
 const probeTimes=[.5,2.5,4.5,5.5],ms=[];
 for(const t of probeTimes){if(process.env.RETOMAR && fs.existsSync(path.join(saida,`${nome}-${t}.png`)))continue;const start=performance.now();const frame=await page.evaluate(t=>window.quadro(t,'image/png'),t);ms.push(performance.now()-start);fs.writeFileSync(path.join(saida,`${nome}-${t}.png`),Buffer.from(frame.split(',')[1],'base64'));}
 // Ordem inversa para detectar acúmulo de estado. Comparação exata em pixel/2D;
 // 3D permite pequena diferença de rasterização, registrada sem aprovação fictícia.
 const repeated=await page.evaluate(()=>window.quadro(2.5,'image/png'));
 const stable=Buffer.from(repeated.split(',')[1],'base64').equals(fs.readFileSync(path.join(saida,`${nome}-2.5.png`)));
 fs.writeFileSync(path.join(saida,`${nome}-repetido.png`),Buffer.from(repeated.split(',')[1],'base64'));
 const diff=await page.evaluate(async({a,b})=>{
  const cv=document.createElement('canvas');cv.width=1080;cv.height=1920;const ctx=cv.getContext('2d',{willReadFrequently:true});
  const pixels=async src=>{const im=new Image();im.src=src;await im.decode();ctx.clearRect(0,0,1080,1920);ctx.drawImage(im,0,0);return ctx.getImageData(0,0,1080,1920).data;};
  const aa=await pixels(a),bb=await pixels(b);let max=0,alterados=0;
  for(let i=0;i<aa.length;i+=4){let delta=0;for(let j=0;j<4;j++)delta=Math.max(delta,Math.abs(aa[i+j]-bb[i+j]));max=Math.max(max,delta);if(delta)alterados++;}
  return {delta_maximo:max,pixels_alterados:alterados,equivalente:max<=1 && alterados<=1080*1920*.01};
 },{a:'data:image/png;base64,'+fs.readFileSync(path.join(saida,`${nome}-2.5.png`)).toString('base64'),b:repeated});
 // A inspeção acima permanece integral. O vídeo usa 3D interno a 50%,
 // com composição/textos na grade original, igualmente nos dois candidatos.
 if(nome==='mecanismo')await page.evaluate(async s=>{
  const Original=THREE.WebGLRenderer;
  THREE.WebGLRenderer=function(...args){const renderer=new Original(...args);renderer.setPixelRatio(.5);return renderer;};
  THREE.WebGLRenderer.prototype=Original.prototype;
  await window.preparar(s);
 },spec);
 const ff=spawn('ffmpeg',['-loglevel','error','-y','-f','image2pipe','-vcodec','mjpeg','-r',String(fps),'-i','pipe:0','-vf','scale=540:960:flags=neighbor','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',path.join(saida,nome+'.mp4')]);
 let fferr='';ff.stderr.on('data',s=>fferr+=s);const done=new Promise((resolve,reject)=>{ff.once('error',reject);ff.once('exit',code=>code===0?resolve():reject(Error(fferr)));});
 for(let f=0;f<spec.dur_s*fps;f++){if(f%24===0)console.log(nome+' quadro '+f+'/'+spec.dur_s*fps);const frame=await page.evaluate(t=>window.quadro(t,'image/jpeg',.94),f/fps);if(!ff.stdin.write(Buffer.from(frame.split(',')[1],'base64')))await new Promise(resolve=>ff.stdin.once('drain',resolve));}
 ff.stdin.end();await done;
 const result={nome,fontes:prep.fontes,erros,quadro_repetido_identico:stable,diferenca_repeticao:diff,ms_amostras:ms,metricas:await page.evaluate(()=>window.METRICAS_RENDER),fps_previa:fps,escala_interna_3d_previa:nome==='mecanismo'?.5:1,duracao_s:spec.dur_s};results.push(result);console.log(JSON.stringify(result));await page.close();if(erros.length)throw Error(erros.join(';'));
}}finally{await browser.close();const file=path.join(saida,'resultados.json');const antigos=process.env.ESTILO && fs.existsSync(file)?JSON.parse(fs.readFileSync(file,'utf8')).filter(x=>x.nome!==process.env.ESTILO):[];fs.writeFileSync(file,JSON.stringify([...antigos,...results],null,2));}
