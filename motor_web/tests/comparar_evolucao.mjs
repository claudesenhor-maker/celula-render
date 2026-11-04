// CHROME=... node motor_web/tests/comparar_evolucao.mjs /base/motor_web /saida
import {createHash} from 'node:crypto';import fs from 'node:fs';import path from 'node:path';import {pathToFileURL} from 'node:url';
import {spawnSync} from 'node:child_process';import puppeteer from 'puppeteer-core';import {fixture} from './fixtures_graficos.mjs';
const base=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
const lamp=fixture('mecanismo');Object.assign(lamp,{titulo:'Lâmpada: forma e interior',w:1080,h:1920,dur_s:6,fps:12});
const glass=lamp.modelo.partes.find(p=>p.nome==='vidro');
// Perfil original inspirado na função/silhueta observada, sem copiar assets.
glass.perfil=[[.17,-.5],[.17,-.4],[.21,-.3],[.32,-.18],[.45,-.02],[.5,.14],[.48,.28],[.37,.41],[.2,.48],[0,.5]];
lamp.cenas=[{ini:0,fim:3,acao:'mostra',camera:'frente'},{ini:3,fim:6,acao:'corte',camera:'frente',alvo:['filamento'],rotulos:[{parte:'filamento',texto:'Filamento'}]}];
const coil=structuredClone(lamp);coil.titulo='Serpentina: percurso conectado';
const points=[];for(let i=0;i<=24;i++){const a=i/24*Math.PI*6;points.push([Math.cos(a)*.65,-.8+i/24*1.6,Math.sin(a)*.32]);}
coil.modelo={partes:[{nome:'serpentina',forma:'tubo',caminho:points,raio:.055,pos:[0,1,0],tam:[1,1,1],cor:'#C88752',material:'metal'},
 {nome:'suporte',forma:'caixa',pos:[0,.08,0],tam:[1.7,.15,.9],cor:'#4E6679',material:'plastico'}]};
coil.cenas=[{ini:0,fim:3,acao:'mostra',camera:'orbita'},{ini:3,fim:6,acao:'fluxo',camera:'orbita',fluxo:{caminho:points.map(p=>[p[0],p[1]+1,p[2]]),cor:'#75DFFF'},rotulos:[{parte:'serpentina',texto:'Percurso'}]}];
const pixel=fixture('pixel');Object.assign(pixel,{w:1080,h:1920,dur_s:6,fps:12});pixel.cenas.forEach((c,i)=>{c.ini=i*3;c.fim=i*3+3;});
const specs={lampada:lamp,serpentina:coil,pixel};fs.writeFileSync(path.join(out,'specs.json'),JSON.stringify(specs,null,2));
const b=await puppeteer.launch({executablePath:process.env.CHROME,headless:true,args:['--no-sandbox','--allow-file-access-from-files','--enable-webgl','--ignore-gpu-blocklist','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const reportFile=path.join(out,'medicoes.json');const report=process.env.VARIANTE&&fs.existsSync(reportFile)?JSON.parse(fs.readFileSync(reportFile)):[];
try{for(const [version,root] of [['antes',base],['depois',path.resolve('motor_web')]])for(const [name,spec] of Object.entries(specs)){
 if(process.env.VARIANTE&&process.env.VARIANTE!==version)continue;
 if(process.env.CENA&&process.env.CENA!==name)continue;
 const sourceHashes=Object.fromEntries(['comum3d.js',`estilos/${spec.estilo}.js`].map(f=>[f,createHash('sha256').update(fs.readFileSync(path.join(root,f))).digest('hex')]));
 const dir=path.join(out,version,name);fs.mkdirSync(dir,{recursive:true});const page=await b.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(root,'palco.html')).href,{waitUntil:'networkidle0'});
 const start=performance.now();await page.evaluate(s=>preparar(s),spec);const preparation=performance.now()-start,times=[];
 for(let i=0;i<spec.fps*spec.dur_s;i++){
  const st=performance.now();const frame=await page.evaluate(t=>quadro(t,'image/png'),i/spec.fps);times.push(performance.now()-st);
  fs.writeFileSync(path.join(dir,`${String(i).padStart(3,'0')}.png`),Buffer.from(frame.split(',')[1],'base64'));
 }
 const original=fs.readFileSync(path.join(dir,'018.png'));const repeat=await page.evaluate(()=>quadro(1.5,'image/png'));
 const deterministic=original.equals(Buffer.from(repeat.split(',')[1],'base64'));
 const metrics=await page.evaluate(()=>window.METRICAS_RENDER||null);const heap=(await page.metrics()).JSHeapUsedSize;
 const ff=spawnSync('ffmpeg',['-v','error','-y','-framerate',String(spec.fps),'-i',path.join(dir,'%03d.png'),'-c:v','libx264','-crf','20','-pix_fmt','yuv420p',path.join(out,`${version}-${name}.mp4`)],{encoding:'utf8'});
 if(ff.status!==0)throw Error(ff.stderr);
 for(const n of [0,4,18,35,36,37,54,71])fs.copyFileSync(path.join(dir,`${String(n).padStart(3,'0')}.png`),path.join(out,`${version}-${name}-${(n/spec.fps).toFixed(3)}.png`));
 const result={version,name,sourceHashes,width:spec.w,height:spec.h,fps:spec.fps,frames:times.length,preparation_ms:preparation,frame_mean_ms:times.reduce((a,b)=>a+b,0)/times.length,frame_p95_ms:[...times].sort((a,b)=>a-b)[Math.floor(times.length*.95)],js_heap_bytes:heap,metrics,deterministic,errors};
 const old=report.findIndex(r=>r.version===version&&r.name===name);if(old>=0)report.splice(old,1);report.push(result);fs.writeFileSync(reportFile,JSON.stringify(report,null,2));console.log(JSON.stringify(result));await page.close();
}}finally{await b.close();fs.writeFileSync(path.join(out,'medicoes.json'),JSON.stringify(report,null,2));}
if(report.some(x=>x.errors.length||!x.deterministic))process.exitCode=1;
