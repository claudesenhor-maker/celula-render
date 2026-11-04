import fs from 'node:fs';import vm from 'node:vm';import test from 'node:test';import assert from 'node:assert/strict';
function carregar(estilo){
 const calls=[],objetos=[],texts=[],window={},MOTORES={};
 const ctx=new Proxy({globalAlpha:1,measureText:s=>({width:String(s).length*20}),createLinearGradient:()=>({addColorStop(){}}),createRadialGradient:()=>({addColorStop(){}})}, {get(o,k){if(k in o)return o[k];return (...args)=>{calls.push({op:k,args,cor:o.fillStyle});if(k==='fillText')texts.push(args[0]);};},set(o,k,v){o[k]=v;return true;}});
 const document={createElement:()=>({width:0,height:0,getContext:()=>ctx})};
 vm.runInNewContext(fs.readFileSync(new URL('../comum.js',import.meta.url),'utf8'),{window,document});
 let source=fs.readFileSync(new URL(`../estilos/${estilo}.js`,import.meta.url),'utf8');
 if(estilo==='pixel')source=source.replace('function objeto(nome, x, y) {','function objeto(nome, x, y) { observar(nome,x,y);');
 vm.runInNewContext(source,{window,document,MOTORES,observar:(nome,x,y)=>objetos.push({nome,x,y})});
 return {calls,objetos,texts,render(cena){return MOTORES[estilo].criar({getContext:()=>ctx},{w:1080,h:1920,titulo:'',cenas:[{ini:0,fim:6,...cena}]},window.U);}};
}
test('escala preserva comprimentos 1:2:4 no mesmo eixo, com valores explícitos',()=>{
 const h=carregar('enem'),motor=h.render({acao:'esquema',esquema:'escala',itens:['A','B','C'],valores:[1,2,4],unidade:'cm'});h.calls.length=0;motor.quadro(5.8);
 const barras=h.calls.filter(c=>c.op==='fillRect' && c.args[3]===42 && ['#8FD3FF','#B8F5A0','#FFE066'].includes(c.cor));
 assert.equal(barras.length,3);assert.equal(barras[0].args[0],barras[2].args[0]);
 assert.equal(barras[1].args[2]/barras[0].args[2],2);assert.equal(barras[2].args[2]/barras[0].args[2],4);
 assert(h.texts.includes('4 cm'));
});
test('medidas ausentes ou inválidas não geram comparação quantitativa falsa',()=>{
 for(const valores of [undefined,[1],[1,-2],[1,null],[1,Infinity],['1',2]]){
  const h=carregar('enem');h.render({acao:'esquema',esquema:'escala',itens:['A','B'],valores}).quadro(5.8);
  assert(!h.calls.some(c=>c.op==='fillRect'&&c.args[3]===42));
 }
});
test('café sobe à boca, retorna à mão e não acumula estado entre buscas',()=>{
 const h=carregar('pixel'),motor=h.render({acao:'come',objeto:'cafe',atores:['heroi'],texto:'Você usou café.'});
 const at=t=>{h.objetos.length=0;motor.quadro(t);return {...h.objetos[0]};};
 const inicio=at(.3),boca=at(3),fim=at(5.8),repetido=at(3);
 assert.equal(boca.nome,'cafe');assert(boca.y<inicio.y-8);assert(boca.x<inicio.x);assert.deepEqual(fim,inicio);assert.deepEqual(repetido,boca);
});

test('direção bloqueia escalas sem medidas antes da exportação',async()=>{
 const {prepararSpec}=await import('../diretor_visual.mjs');
 const spec={estilo:'enem',dur_s:6,cenas:[{ini:0,fim:6,acao:'esquema',esquema:'escala',itens:['A','B'],valores:[1,2]}]};
 assert.equal(prepararSpec(spec).cenas[0].valores[1],2);
 for(const valores of [[1,0],[1],[1,null]])assert.throws(()=>prepararSpec({...spec,cenas:[{...spec.cenas[0],valores}]}),/medidas positivas/);
});
