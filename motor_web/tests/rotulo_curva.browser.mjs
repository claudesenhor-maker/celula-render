// Regressão visual/geométrica: marcador do rótulo deve estar no cano, inclusive com pivô.
import assert from 'node:assert/strict';import path from 'node:path';import {pathToFileURL} from 'node:url';
import puppeteer from 'puppeteer-core';import {fixture} from './fixtures_graficos.mjs';
const browser=await puppeteer.launch({executablePath:process.env.CHROME,headless:true,timeout:90000,args:['--no-sandbox','--allow-file-access-from-files','--enable-webgl','--ignore-gpu-blocklist','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.resolve('motor_web/palco.html')).href,{waitUntil:'networkidle0'});
 await page.evaluate(()=>{
  const Scene=THREE.Scene,Camera=THREE.PerspectiveCamera,arc=CanvasRenderingContext2D.prototype.arc;
  THREE.Scene=function(...args){const sc=new Scene(...args);window._sceneTeste=sc;return sc;};THREE.Scene.prototype=Scene.prototype;
  THREE.PerspectiveCamera=function(...args){const cam=new Camera(...args);window._camTeste=cam;return cam;};THREE.PerspectiveCamera.prototype=Camera.prototype;
  window._dots=[];CanvasRenderingContext2D.prototype.arc=function(x,y,r,...args){if(this.canvas.id==='tela'&&r===11)_dots.push([x,y]);return arc.call(this,x,y,r,...args);};
 });
 const spec=fixture('mecanismo');spec.modelo.partes=[{nome:'cano',forma:'tubo',pos:[0,1,0],tam:[1,1,1],pivo:[0,.2,0],caminho:[[0,0,0],[.6,.2,0],[.7,1,0]],raio:.05,cor:'#C88752',material:'metal'}];
 spec.cenas=[{ini:0,fim:8,acao:'mostra',camera:'frente',rotulos:[{parte:'cano',texto:'Cano'}]}];
 await page.evaluate(s=>preparar(s),spec);const result=await page.evaluate(()=>{
  quadro(1.5,'image/png');let mesh;_sceneTeste.traverse(m=>{if(m.userData.nome==='cano')mesh=m;});
  const point=mesh.geometry.parameters.path.points[1].clone();point.y-=.2;mesh.localToWorld(point);point.project(_camTeste);
  const expected=[(point.x*.5+.5)*1080,(-point.y*.5+.5)*1920],dot=_dots.at(-1);
  return {expected,dot,distancia:Math.hypot(dot[0]-expected[0],dot[1]-expected[1])};
 });
 assert.deepEqual(errors,[]);assert(result.distancia<1e-6,JSON.stringify(result));console.log(JSON.stringify({teste:'rotulo-na-curva-com-pivo',...result,errors}));
}finally{await browser.close();}
