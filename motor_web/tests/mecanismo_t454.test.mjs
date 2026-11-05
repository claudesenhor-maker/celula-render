import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import puppeteer from 'puppeteer-core';
test('T454 Chrome: close usa bounds, contexto sempre visível, cartaz livre, controles intactos', {timeout:300000}, async()=>{
 const root=process.env.MOTOR_ROOT || path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
 const chrome=process.env.CHROME || ['/usr/bin/google-chrome','/usr/bin/chromium'].find(p=>fs.existsSync(p));
 assert(chrome,'Chrome é obrigatório para validar o renderer');
 const browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--allow-file-access-from-files','--enable-webgl','--ignore-gpu-blocklist','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(root,'palco.html')).href,{waitUntil:'networkidle0'});
 const r=await page.evaluate(async()=>{
  const calls=[],old=CanvasRenderingContext2D.prototype.fillText;
  CanvasRenderingContext2D.prototype.fillText=function(s,...a){if(this.canvas.id==='tela')calls.push(String(s));return old.call(this,s,...a);};
  let cam,sc;const oldRender=U3.render;U3.render=(r,s,c,...a)=>{cam=c;sc=s;return oldRender(r,s,c,...a);};
  const spec={motor:'web',estilo:'mecanismo',cell_id:'d582b3d9-b0f7-5eee-84f5-19f407fccba7',w:1080,h:1920,fps:30,dur_s:7,narrado:true,titulo:'LA TRABA DE TU BOLÍGRAFO',modelo:{partes:[{nome:'casca',forma:'cilindro',pos:[0,1,0],tam:[.8,2,.8],cor:'#dd3344',casca:true},{nome:'mola',forma:'mola',pos:[0,1,0],tam:[.04,.04,.04],cor:'#eedd33'}]},cenas:[{ini:0,fim:7,texto:'Mira la goma',acao:'destaque',camera:'perto',alvo:['mola'],hud:'HUD PRUEBA',rotulos:[{parte:'mola',texto:'ROTULO PRUEBA'}]}],palavras:[{palavra:'Mira',ini:0,fim:7}]};
  const frame=t=>{calls.length=0;MOTOR.quadro(t);return [...calls];};
  await preparar(spec);const early=frame(1.5),late=frame(4),small=cam.position.distanceTo(new THREE.Vector3(0,2.1,0));
  const refEvery=[];for(let f=0;f<210;f+=30)refEvery.push(frame(f/30).includes('OBJETO COMPLETO'));
  const posSmall=cam.position.clone();let shell;sc.traverse(m=>{if(m.userData?.nome==='casca')shell=m;});const contextoOculto=!shell.visible;
  const big=structuredClone(spec);big.modelo.partes[1].tam=[.4,.4,.4];await preparar(big);frame(4);const posBig=cam.position.clone();
  await preparar({...spec,cell_id:'controle'});const control=frame(1.5),controlLate=frame(4);
  return {contextoOculto,early,late,refEvery,ratio:posBig.distanceTo(new THREE.Vector3(0,2.1,0))/small,camMove:posBig.distanceTo(posSmall),control,controlLate};
 });
 assert.deepEqual(errors,[]);
 assert(r.contextoOculto,'carcaça não pode ocultar a peça selecionada no close');
 assert(!r.early.includes('HUD PRUEBA'));
 assert(!r.early.includes('ROTULO PRUEBA'));
 assert(r.early.includes('OBJETO COMPLETO'));
 assert(r.early.some(s=>s.toUpperCase()==='MIRA'),'legenda inferior continua acessível no gancho');
 assert(r.refEvery.every(Boolean),'cada close deve manter referência, inclusive transição');
 assert(r.late.includes('HUD PRUEBA'));
 assert(r.late.includes('ROTULO PRUEBA'));
 assert(r.camMove>1,'câmera deve responder ao tamanho da peça');
 assert(!r.control.includes('OBJETO COMPLETO'));
 assert(r.control.includes('HUD PRUEBA'));
 assert(!r.controlLate.includes('OBJETO COMPLETO'));
 }finally{await browser.close();}
});