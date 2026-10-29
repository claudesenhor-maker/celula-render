import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';import os from 'node:os';import path from 'node:path';import http from 'node:http';
import {revisarAntesDoRender} from '../preflight.mjs';import {prepararSpec} from '../diretor_visual.mjs';import {fixture} from './fixtures_graficos.mjs';
const imagem='data:image/jpeg;base64,/9j/2Q==';
const pagina=(faixa=100)=>({preparacoes:0,async evaluate(fn,arg){if(typeof arg==='object'){this.preparacoes++;return {ok:true};}return {imagem,luma:80,variancia:300,faixa,metricas:{chamadas:10}};}});
async function comServidor(responder,teste){const servidor=http.createServer((req,res)=>{let b='';req.on('data',s=>b+=s);req.on('end',()=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify(responder(JSON.parse(b))));});});
 await new Promise(r=>servidor.listen(0,'127.0.0.1',r));const anterior=process.env.VIDEO_REVISOR_URL;process.env.VIDEO_REVISOR_URL=`http://127.0.0.1:${servidor.address().port}`;
 try{await teste();}finally{if(anterior==null)delete process.env.VIDEO_REVISOR_URL;else process.env.VIDEO_REVISOR_URL=anterior;servidor.closeAllConnections();await new Promise(r=>servidor.close(r));}}
function pasta(){return path.join(fs.mkdtempSync(path.join(os.tmpdir(),'diretor-teste-')),'video.mp4');}

test('conferência local registra modo técnico e recusa imagem vazia',async()=>{
 const previo=process.env.VIDEO_REVISOR_URL;delete process.env.VIDEO_REVISOR_URL;
 try{const s=prepararSpec(fixture('mecanismo')),saida=pasta();await revisarAntesDoRender(pagina(),s,saida);
 const r=JSON.parse(fs.readFileSync(saida+'.direcao.json'));assert.equal(r.historico[0].modo,'tecnico-local');assert.equal(r.historico[0].revisao,undefined);
 await assert.rejects(()=>revisarAntesDoRender(pagina(0),s,pasta()),/sem conteúdo/);
 }finally{if(previo!=null)process.env.VIDEO_REVISOR_URL=previo;}
});
test('ciclo exige nova revisão após aplicar correção e não transmite configuração de voz',async()=>{
 let chamadas=0;const s=prepararSpec(fixture('mecanismo'));s.voz={token:'NUNCA_ENVIAR'};
 await comServidor(dados=>{chamadas++;assert(!JSON.stringify(dados).includes('NUNCA_ENVIAR'));assert(dados.quadros[0].imagem.startsWith('data:image/jpeg'));
 return chamadas===1?{aprovado:false,problemas:['detalhe pequeno'],correcoes:[{cena:1,camera:'perto',plano:{zoom:1.1}}]}:{aprovado:true,problemas:[],correcoes:[]};
 },async()=>{const p=pagina(),saida=pasta(),resultado=await revisarAntesDoRender(p,s,saida);assert.equal(chamadas,2);assert.equal(p.preparacoes,1);assert.equal(resultado.cenas[1].plano.zoom,1.1);assert.equal(JSON.parse(fs.readFileSync(saida+'.direcao.json')).historico.length,2);});
});
test('reprovação persiste e impede continuar após o orçamento de uma correção',async()=>{
 let chamadas=0;await comServidor(()=>{chamadas++;return {aprovado:false,problemas:['modelo inadequado'],correcoes:[{cena:0,plano:{zoom:1.05}}]};},async()=>{
 await assert.rejects(()=>revisarAntesDoRender(pagina(),prepararSpec(fixture('mecanismo')),pasta()),/não aprovada/);assert.equal(chamadas,2);
 });
});
