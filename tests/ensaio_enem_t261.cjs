'use strict';
// T261: exercita o roteador real sem GPU/rede; isto NÃO valida o MP4.
const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
const raiz = process.argv[2] || path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(raiz, 'motor_web/palco.html'), 'utf8');
const scripts = [...html.matchAll(/<script src="([^"]+)"><\/script>/g)].map(m => m[1]);
assert(scripts.includes('estilos/enem.js'), 'ENEM existe mas o palco não carrega seu motor');
for (const nome of ['mapa','animal','linha_tempo','orbita','micro']) assert(scripts.includes('estilos/'+nome+'.js'), nome+' preservado');
assert.equal(scripts.filter(s => s === 'estilos/enem.js').length, 1);
const registro = { MOTORES: {}, window: {} };
vm.runInNewContext(fs.readFileSync(path.join(raiz,'motor_web/estilos/enem.js'),'utf8'), registro);
assert.equal(typeof registro.MOTORES.enem.criar, 'function');
const inline = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
let recebido;
const tela = { toDataURL: ()=>'quadro' };
const browser = { window: {}, MOTORES: { enem: {criar:(canvas,spec)=>{recebido=spec; return {quadro:()=>{}};}} }, U:{},
 document:{getElementById:()=>tela,fonts:{load:async()=>[],ready:Promise.resolve(),check:()=>true}},console };
vm.runInNewContext(inline,browser);
(async()=>{
 const spec = {estilo:'enem',w:1080,h:1920,cenas:[{acao:'pergunta'}]};
 const r = await browser.window.preparar(spec);
 assert.equal(r.ok,true); assert.equal(recebido,spec);
 assert.equal(browser.window.quadro(0),'quadro');
 await assert.rejects(()=>browser.window.preparar({...spec,estilo:'nao_existe'}),/estilo desconhecido/);
 console.log('T261 ENEM: registro, carregamento e roteador OK; MP4 ainda exige ensaio');
})().catch(e=>{console.error(e);process.exitCode=1;});
