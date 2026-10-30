import assert from 'node:assert/strict';import test from 'node:test';import http from 'node:http';
import {prepararSpec,instantesRevisao,aplicarCorrecoes,consultarRevisor} from '../diretor_visual.mjs';
import {fixture} from './fixtures_graficos.mjs';

test('planejamento mantém fatos e dados antigos e resolve a câmera do mecanismo',()=>{
 const original=fixture('mecanismo'),antes=JSON.stringify(original),s=prepararSpec(original);
 assert.equal(JSON.stringify(original),antes);assert.equal(s.cenas[0].camera,'frente');assert.equal(s.modelo.partes.length,original.modelo.partes.length);
 assert.equal(s.cenas[1].rotulos[0].texto,'Filament');assert.equal(s.cenas[0].plano.zoom,1);
});
test('recusa estúdio vazio, alvo inexistente e cronologia sobreposta',()=>{
 const s=fixture('mecanismo');s.modelo.partes=[];assert.throws(()=>prepararSpec(s),/sem peças/);
 const a=fixture('mecanismo');a.cenas[0]={...a.cenas[0],acao:'gira',alvo:'fantasma'};assert.throws(()=>prepararSpec(a),/inexistente/);
 const b=fixture('pixel');b.cenas[1].ini=2;assert.throws(()=>prepararSpec(b),/intervalo/);
});
test('amostras incluem começo e fim sem ultrapassar o vídeo',()=>{
 const s=prepararSpec(fixture('escala')),tempos=instantesRevisao(s);
 assert.equal(tempos[0],0);assert.equal(tempos.at(-1),8-1/30);assert(tempos.some(t=>t>4&&t<8));assert(tempos.every(t=>t>=0&&t<8));
 const muitos={...s,cenas:Array.from({length:40},(_,i)=>({ini:i*2,fim:i*2+2})),dur_s:80};assert.equal(instantesRevisao(muitos).length,16);
});
test('revisor pode corrigir plano, preservando narração e peças',()=>{
 const s=prepararSpec(fixture('mecanismo'));const r=aplicarCorrecoes(s,{aprovado:false,problemas:['detalhe distante'],correcoes:[{cena:1,camera:'perto',plano:{zoom:1.1}}]});
 assert.equal(r.cenas[1].camera,'perto');assert.equal(r.cenas[1].plano.zoom,1.1);assert.deepEqual(r.modelo,s.modelo);
});
test('rejeita código, edição de texto, zoom excessivo e câmera incompatível',()=>{
 const s=prepararSpec(fixture('mecanismo'));
 for(const patch of [{cena:0,texto:'altere o fato'},{cena:0,plano:{zoom:8}},{cena:0,camera:'eval(x)'},{cena:0,plano:{script:'alert(1)'}}])
  assert.throws(()=>aplicarCorrecoes(s,{aprovado:true,problemas:[],correcoes:[patch]}));
 assert.throws(()=>aplicarCorrecoes(s,{aprovado:'sim',correcoes:[]}));
});
test('orbita usa data explícita reproduzível',()=>{
 const s=fixture('orbita');delete s.data_referencia;assert.equal(prepararSpec(s).data_referencia,'2000-01-01T12:00:00Z');
 s.data_referencia='inválida';assert.throws(()=>prepararSpec(s),/data_referencia/);
});
test('ponte HTTP recebe quadros e devolve JSON; erros não aprovam silenciosamente',async()=>{
 const server=http.createServer((req,res)=>{let body='';req.on('data',b=>body+=b);req.on('end',()=>{const dados=JSON.parse(body);assert.equal(dados.quadros[0].t,0);assert(dados.instrucao.includes('Não invente'));res.setHeader('Content-Type','application/json');res.end(JSON.stringify({aprovado:true,problemas:[],correcoes:[]}));});});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try {const r=await consultarRevisor(`http://127.0.0.1:${server.address().port}`,{quadros:[{t:0,imagem:'data:image/jpeg;base64,AA=='}]});assert.equal(r.aprovado,true);}
 finally {server.closeAllConnections();await new Promise(r=>server.close(r));}
 await assert.rejects(()=>consultarRevisor('http://127.0.0.1:1',{}, {timeout:30}));
});


test('amostra os dois lados do corte e os beats explícitos sem inventar aprovação',()=>{
 const s=fixture('mecanismo');s.cenas[0].marcos_visuais=[{local_s:1,evento:'contato'}];
 const prepared=prepararSpec(s),times=instantesRevisao(prepared);
 assert(times.includes(1));assert(times.includes(1-1/30));assert(times.includes(4-1/30));assert(times.includes(4));
 s.cenas[0].marcos_visuais=[{local_s:9,evento:'contato'}];assert.throws(()=>prepararSpec(s),/marcos/);
});
