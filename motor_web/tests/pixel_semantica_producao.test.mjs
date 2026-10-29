import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import vm from 'node:vm';
const comum=fs.readFileSync(new URL('../comum.js',import.meta.url),'utf8');
const pixel=fs.readFileSync(new URL('../estilos/pixel.js',import.meta.url),'utf8');
function desenhar(cena,{qualidade='detalhado',tempo=1.8,continuacao=false}={}){
 const objetos=[],textos=[],janela={},motores={};
 const contexto=(principal=false)=>new Proxy({}, {get(o,k){if(k in o)return o[k];if(k==='measureText')return t=>({width:String(t).length*18});if(k==='fillText')return t=>{if(principal)textos.push(String(t));};return ()=>{};},set(o,k,v){o[k]=v;return true;}});
 const c=contexto(true),document={createElement:()=>({width:180,height:320,getContext:()=>contexto()})};
 vm.runInNewContext(comum,{window:janela});
 vm.runInNewContext(pixel.replace('function objeto(nome, x, y) {','function objeto(nome, x, y) { observar(nome);'),{window:janela,MOTORES:motores,document,observar:n=>objetos.push(n)});
 const cenas=[{ini:0,fim:3.4,cenario:'cozinha',atores:['heroi'],...cena}];if(continuacao)cenas.push({ini:3.4,fim:6,acao:'anda'});
 motores.pixel.criar({getContext:()=>c},{w:1080,h:1920,titulo:'',qualidade,hud_inicial:{ouro:120,hp:80},cenas},janela.U).quadro(tempo);
 return {objetos,textos};
}
for(const qualidade of ['detalhado','legado']){
 test(`objetos explícitos e consumo literal preservados (${qualidade})`,()=>{
  assert.deepEqual(desenhar({acao:'digita',objeto:'celular'},{qualidade}).objetos,['celular']);
  assert.deepEqual(desenhar({acao:'come',objeto:'pizza',texto:'You used COFFEE.'},{qualidade}).objetos,['cafe']);
  assert.deepEqual(desenhar({acao:'come',objeto:'email',texto:'You used COFFEE.'},{qualidade}).objetos,['email']);
  assert.deepEqual(desenhar({acao:'come',objeto:'pizza',texto:'You ate ice cream.'},{qualidade}).objetos,['sorvete']);
 });
 test(`ouro e dano não são inventados (${qualidade})`,()=>{
  assert(!desenhar({acao:'recebe',objeto:'boleto',hud:{ouro:120}},{qualidade}).objetos.includes('moeda'));
  assert(desenhar({acao:'recebe',hud:{ouro:180}},{qualidade}).objetos.includes('moeda'));
  assert(!desenhar({acao:'batalha'},{qualidade}).textos.includes('-40'));
  assert(desenhar({acao:'batalha',dano:7},{qualidade}).textos.includes('-7'));
 });
}
