// Executar no celula-render: node --test motor_web/tests/animal_v2_t448.test.mjs
import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import puppeteer from 'puppeteer-core';

test('T448: desenho real no Chrome, gate, barras, título, peça e bounds', {timeout:120000}, async t=>{
  const chrome=process.env.CHROME || ['/usr/bin/google-chrome','/usr/bin/chromium'].find(p=>fs.existsSync(p));
  if(!chrome){t.skip('Chrome não instalado neste ambiente');return;}
  const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
  const browser=await puppeteer.launch({executablePath:chrome,headless:true,args:['--no-sandbox','--allow-file-access-from-files','--enable-webgl','--ignore-gpu-blocklist','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
  try{
    const page=await browser.newPage(); const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(pathToFileURL(path.join(root,'palco.html')).href,{waitUntil:'networkidle0'});
    const result=await page.evaluate(async()=>{
      const calls=[], rects=[],oldRR=U.rr,oldText=CanvasRenderingContext2D.prototype.fillText;
      U.rr=(c,x,y,w,h,...a)=>{if(c.canvas.id==='tela')rects.push({x,y,w,h});return oldRR(c,x,y,w,h,...a);};
      CanvasRenderingContext2D.prototype.fillText=function(s,x,y,...a){if(this.canvas.id==='tela')calls.push({s:String(s),x,y});return oldText.call(this,s,x,y,...a);};
      let sc,cam;const oldRender=U3.render;U3.render=(r,s,c,...a)=>{sc=s;cam=c;return oldRender(r,s,c,...a);};
      const spec={motor:'web',estilo:'animal',cell_id:'112117b4-380c-5d32-829f-7b94fc999eb5',w:1080,h:1920,fps:30,dur_s:12,narrado:true,titulo:'A SMALL SURVIVOR',animal:{nome:'Test animal',tamanho_m:1,partes:[{nome:'body',forma:'esfera',pos:[0,.5,0],tam:[1,.5,.4]},{nome:'jaw',forma:'caixa',pos:[.5,.5,0],tam:[.3,.1,.2]}]},stats:[{nome:'FORCE',valor:10,humano:100,unidade:'N'}],cenas:[{ini:0,fim:3,texto:'Ten newtons',acao:'stat',stat:0,hud:'HUD PROIBIDO'},{ini:3,fim:6,texto:'A hundred for you',acao:'compara',hud:'HUMANO'},{ini:6,fim:9,texto:'The jaw closes',acao:'mostra'},{ini:9,fim:12,texto:'Test animal',acao:'stat',stat:0}],palavras:[{palavra:'Ten',ini:.4,fim:.7},{palavra:'newtons',ini:.7,fim:1},{palavra:'hundred',ini:3.4,fim:3.8},{palavra:'Test',ini:9.2,fim:9.5},{palavra:'animal',ini:9.5,fim:10}]};
      await preparar(spec);
      const frame=t=>{calls.length=0;rects.length=0;MOTOR.quadro(t);return structuredClone(calls);};
      spec.cenas[3].texto='Test animal delivers ten newtons';
      spec.palavras.push({palavra:'ten',ini:9.8,fim:10.1});
      const antes=frame(.2),depois=frame(.9),gancho=frame(4),revela=frame(10.5);
      frame(4.3);const barras=structuredClone(rects.filter(r=>r.h===52));
      frame(6.01);let jaw;sc.traverse(m=>{if(m.userData?.nome==='jaw')jaw=m;});const ang0=jaw.rotation.z;frame(7.3);const ang1=jaw.rotation.z;
      frame(.2);const d1=cam.position.length();let body;sc.traverse(m=>{if(m.userData?.nome==='body')body=m;});
      const projected=new THREE.Vector3();new THREE.Box3().setFromObject(body).getCenter(projected);projected.project(cam);const focoY=projected.y;
      await preparar({...spec,animal:{...spec.animal,tamanho_m:.01}});frame(.2);const d2=cam.position.length();
      await preparar({...spec,cell_id:'outro'});const controle=frame(.9);
      return {antes,depois,gancho,revela,ang0,ang1,d1,d2,controle,barras,focoY};
    });
    assert.deepEqual(errors,[]);
    assert(!result.antes.some(x=>x.s==='FORCE'));
    assert(result.depois.some(x=>x.s==='FORCE'));
    assert(!result.depois.some(x=>x.s==='HUD PROIBIDO'));
    assert(result.gancho.some(x=>x.s==='???'));
    assert(!result.gancho.some(x=>x.s.includes('TEST ANIM')));
    assert(result.revela.some(x=>x.s==='TEST ANIM'));
    assert(Math.abs(result.ang1-result.ang0)>.1);
    assert(Math.abs(result.d1/result.d2-100)<1);
    assert(result.controle.some(x=>x.s==='TEST ANIM'));
    assert(result.depois.filter(x=>x.s==='FORCE').every(x=>x.y>=800));
    assert.deepEqual(result.barras.map(r=>Math.round(r.w)),[680,68,680,680]);
    assert(result.focoY>.25,'peça precisa aparecer acima do cartão');
    const titulo=result.depois.find(x=>x.s==='FORCE'),valor=result.depois.find(x=>/ N$/.test(x.s));
    assert(valor.y-titulo.y>=50,'nome da medida e número não podem disputar a mesma linha');
  }finally{await browser.close();}
});
