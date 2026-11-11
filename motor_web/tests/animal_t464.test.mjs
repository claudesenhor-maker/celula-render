import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import puppeteer from 'puppeteer-core';

test('T464: anatomia orgânica, assunto seguro, números legíveis e quadro sem estado', {timeout:120000}, async t=>{
 const chrome=process.env.CHROME||['/usr/bin/google-chrome','/usr/bin/chromium'].find(fs.existsSync);
 if(!chrome){t.skip('Chrome ausente');return;}
 const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
 const b=await puppeteer.launch({executablePath:chrome,args:['--no-sandbox','--allow-file-access-from-files','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try {
 const p=await b.newPage();const errors=[];p.on('pageerror',e=>errors.push(e.message));
 await p.goto(pathToFileURL(path.join(root,'palco.html')).href,{waitUntil:'networkidle0'});
 const result=await p.evaluate(async()=>{
  let scene,cam;const old=U3.render;U3.render=(r,s,c,...a)=>{scene=s;cam=c;return old(r,s,c,...a)};
  const spec={motor:'web',estilo:'animal',w:1080,h:1920,fps:30,dur_s:9,narrado:true,cell_id:'112117b4-380c-5d32-829f-7b94fc999eb5',titulo:'A living specimen',animal:{nome:'African elephant',tamanho_m:6,partes:[{nome:'body',forma:'cilindro',pos:[0,1,0],tam:[2,1.4,1],giro:[0,0,90]},{nome:'ear_left',forma:'caixa',pos:[.7,1.2,.5],tam:[.8,1,.1]},{nome:'jaw',forma:'caixa',pos:[1,1,0],tam:[.3,.2,.3]}]},stats:[{nome:'ENERGY USE WITH A LONG LABEL',valor:1460,humano:3,unidade:'% OF NORMAL'}],cenas:[{ini:0,fim:3,acao:'stat',stat:0,texto:'1460'},{ini:3,fim:6,acao:'compara',texto:'Three for you'},{ini:6,fim:9,acao:'mostra',hud:'A LONG FACT MUST REMAIN FULLY LEGIBLE',texto:'The jaw closes'}],palavras:[{palavra:'1460',ini:.4,fim:.8},{palavra:'Three',ini:3.4,fim:3.8}]};
  await preparar(spec);
  const bounds=[];let organic=false;
  for(const time of [0,.2,1.8,4.2,7.3]){
   MOTOR.quadro(time);scene.updateMatrixWorld(true);let subject;scene.traverse(m=>{if(m.userData?.animal464)subject=m; if(m.userData?.nome==='ear_left')organic=m.geometry.type!=='ExtrudeGeometry'||m.geometry.parameters?.shapes?.curves?.some(c=>c.type==='CubicBezierCurve');});
   if(subject){const box=new THREE.Box3().setFromObject(subject),pts=[];
    for(const x of [box.min.x,box.max.x])for(const y of [box.min.y,box.max.y])for(const z of [box.min.z,box.max.z]){const v=new THREE.Vector3(x,y,z).project(cam);pts.push([(v.x+1)*540,(1-v.y)*960]);}
    bounds.push({x0:Math.min(...pts.map(v=>v[0])),x1:Math.max(...pts.map(v=>v[0])),y0:Math.min(...pts.map(v=>v[1])),y1:Math.max(...pts.map(v=>v[1]))});
   }
  }
  const draw=t=>{MOTOR.quadro(t);return document.getElementById('tela').toDataURL();};
  const a=draw(7.3);draw(.2);const deterministic=a===draw(7.3);
  const rects=[],texts=[],rr=U.rr,ft=CanvasRenderingContext2D.prototype.fillText;
  U.rr=(c,x,y,w,h,...a)=>{if(c.canvas.id==='tela')rects.push({x,y,w,h});return rr(c,x,y,w,h,...a)};
  CanvasRenderingContext2D.prototype.fillText=function(s,x,y,...a){if(this.canvas.id==='tela'){const w=this.measureText(s).width;const l=this.textAlign==='right'?x-w:this.textAlign==='center'?x-w/2:x;texts.push({s:String(s),l,r:l+w,y});}return ft.call(this,s,x,y,...a)};
  MOTOR.quadro(1.8);
  return {bounds,organic,deterministic,rects:rects.filter(r=>r.h>200&&r.h<500),texts};
 });
 assert.deepEqual(errors,[]);
 assert.equal(result.bounds.length,5,'animal precisa estar identificado para auditar a caixa inteira');
 assert(result.organic,'orelha deve ter contorno curvo');
 for(const r of result.bounds){assert(r.x0>=65&&r.x1<=895,JSON.stringify(r));assert(r.y0>=320&&r.y1<=1020,JSON.stringify(r));assert(Math.max(r.y1-r.y0,r.x1-r.x0)>=430,'assunto pequeno');}
 assert(result.deterministic,'buscar quadros fora de ordem não altera pose');
 assert(result.rects.every(r=>r.x+r.w<=905),'cartão fora da área do app');
 assert(result.texts.some(x=>x.s.includes('% OF NORMAL')),'unidade completa deve ser preservada');
 assert(result.texts.filter(x=>x.s.includes('NORMAL')).every(x=>x.l>=70&&x.r<=880),'métrica longa deve caber');
 }finally{await b.close();}
});