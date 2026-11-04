import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import * as T from 'three';
import {prepararSpec} from '../diretor_visual.mjs';
import {fixture} from './fixtures_graficos.mjs';
const win={};vm.runInNewContext(fs.readFileSync(new URL('../comum3d.js',import.meta.url),'utf8'),{window:win});
const criar=p=>win.U3.geometriaPeca(T,p,()=>new T.SphereGeometry(.5));
test('perfil mantém pescoço e ombro mensuráveis em vez de esfera',()=>{
 const g=criar({perfil:[[.15,-.5],[.15,-.3],[.45,0],[.5,.2],[0,.5]]});g.computeBoundingBox();
 assert.equal(g.type,'LatheGeometry');assert(Math.abs(g.boundingBox.max.x-.5)<1e-6);
 const a=g.attributes.position;assert(Array.from(a.array).every(Number.isFinite));g.dispose();
 assert.equal(criar({}).type,'SphereGeometry');
});
test('curva contínua chega às conexões e não cria coordenadas inválidas',()=>{
 const pts=[[-1,0,0],[-1,1,0],[0,1,0],[1,0,0]],g=criar({caminho:pts,raio:.05});
 assert.equal(g.type,'TubeGeometry');assert(g.parameters.path.getPoint(0).distanceTo(new T.Vector3(...pts[0]))<1e-6);
 assert(g.parameters.path.getPoint(1).distanceTo(new T.Vector3(...pts.at(-1)))<1e-6);
 assert(Array.from(g.attributes.normal.array).every(Number.isFinite));g.dispose();
});
test('dados malformados e orçamento geométrico são recusados antes de alocar',()=>{
 for(const p of [{perfil:[[0,0],[1,1],[1,0]]},{perfil:[[0,0],[1,1e-300],[0,1]]},{perfil:Array(33).fill([1,0])},{caminho:[[0,0,0],[0,0,0]],raio:.05},{caminho:[[0,0,0],[3,0,0]],raio:.05}]){
  assert.throws(()=>criar(p));const s=fixture('mecanismo');Object.assign(s.modelo.partes[0],p);assert.throws(()=>prepararSpec(s));
 }
});


test('interpolação do perfil suaviza contorno sem criar raios negativos/overshoot',()=>{
 const profile=[[.15,-.5],[.15,-.3],[.45,0],[.5,.2],[0,.5]],g=criar({perfil:profile});
 const points=g.parameters.points;assert.equal(points.length,17);
 for(let i=0;i<profile.length-1;i++)for(let j=0;j<4;j++){
  const p=points[i*4+j];assert(p.x>=Math.min(profile[i][0],profile[i+1][0])-1e-9);assert(p.x<=Math.max(profile[i][0],profile[i+1][0])+1e-9);
  if(i*4+j)assert(p.y>points[i*4+j-1].y);
 }
 assert(Array.from(g.attributes.normal.array).every(Number.isFinite));g.dispose();
});
