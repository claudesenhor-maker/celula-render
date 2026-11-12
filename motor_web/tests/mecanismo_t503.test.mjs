// T503: gancho legível no mecanismo -- rótulo nunca atrás do cartaz do título, rótulo grande, objeto maior.
import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL,fileURLToPath} from 'node:url';
import puppeteer from 'puppeteer-core';
test('T503 Chrome: rótulo abaixo do cartaz no gancho, fonte >= 50 px, enquadramento mais fechado', {timeout:300000}, async()=>{
 const root=process.env.MOTOR_ROOT || path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
 const chrome=process.env.CHROME || ['/usr/bin/google-chrome','/usr/bin/chromium'].find(p=>fs.existsSync(p));
 assert(chrome,'Chrome é obrigatório para validar o renderer');
 const browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--allow-file-access-from-files','--enable-webgl','--ignore-gpu-blocklist','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(root,'palco.html')).href,{waitUntil:'networkidle0'});
  const r=await page.evaluate(async()=>{
   const calls=[],old=CanvasRenderingContext2D.prototype.fillText;
   CanvasRenderingContext2D.prototype.fillText=function(s,x,y,...a){if(this.canvas.id==='tela'){const m=this.getTransform();calls.push({s:String(s),y:m.b*x+m.d*y+m.f,font:parseFloat(this.font)});}return old.call(this,s,x,y,...a);};
   let cam;const oldRender=U3.render;U3.render=(r,s,c,...a)=>{cam=c;return oldRender(r,s,c,...a);};
   const spec={motor:'web',estilo:'mecanismo',cell_id:'controle',w:1080,h:1920,fps:30,dur_s:9,narrado:true,titulo:'How Your Airbag Really Protects You In A Crash',
    modelo:{partes:[{nome:'casca',forma:'caixa',pos:[0,1,0],tam:[3,1,1],cor:'#dd3344',casca:true},{nome:'miolo',forma:'esfera',pos:[0,1,0],tam:[.5,.5,.5],cor:'#33dd44'}]},
    cenas:[{ini:0,fim:3,acao:'corte',alvo:['miolo'],texto:'look inside now',rotulos:[{parte:'miolo',texto:'rotulo prueba'}]},{ini:3,fim:6,acao:'destaque',alvo:['miolo'],texto:'it glows here',rotulos:[{parte:'miolo',texto:'rotulo prueba'}]},{ini:6,fim:9,acao:'mostra',texto:'the end now'}],
    palavras:[{palavra:'look',ini:0,fim:.9},{palavra:'inside',ini:1,fim:1.9},{palavra:'now',ini:2,fim:2.9}]};
   const rot=t=>{calls.length=0;MOTOR.quadro(t);return calls.find(c=>c.s==='ROTULO PRUEBA');};
   await preparar(spec);
   const cedo=rot(1.5), tarde=rot(5); MOTOR.quadro(7.5);
   const d=cam.position.distanceTo(new THREE.Vector3(0,1,0)), vista=cam.view&&cam.view.enabled?cam.view.offsetY:0;
   return {cedo,tarde,d,vista};
  });
  assert.deepEqual(errors,[]);
  assert(r.cedo,'rótulo da 1ª cena aparece no gancho');
  assert(r.cedo.y>=470,'rótulo fica ABAIXO do cartaz de 2 linhas (y='+r.cedo.y+')');
  assert(r.tarde.y<470,'depois do cartaz o rótulo volta ao topo (y='+r.tarde.y+')');
  assert(r.cedo.font>=50,'rótulo legível no celular: fonte >= 50 px (era 42): '+r.cedo.font);
  assert(r.d<17.5,'câmera mais perto do objeto largo (era ~19,6): '+r.d);
  assert(r.vista>0,'objeto sobe para a faixa livre entre cartaz e legenda');
 }finally{await browser.close();}
});
