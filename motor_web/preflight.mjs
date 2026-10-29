import fs from 'node:fs';
import path from 'node:path';
import {instantesRevisao,consultarRevisor,aplicarCorrecoes,MOTORES_3D,CAMERAS} from './diretor_visual.mjs';

export async function amostrar(page,spec,pasta,rodada=0) {
 fs.mkdirSync(pasta,{recursive:true});const quadros=[];
 for(const t of instantesRevisao(spec)) {
  const inicio=performance.now();
  const q=await page.evaluate(t=>{
   window.quadro(t,'image/jpeg',.8);
   const cv=document.createElement('canvas');cv.width=360;cv.height=640;
   const g=cv.getContext('2d',{willReadFrequently:true});g.imageSmoothingEnabled=SPEC_INICIO_T272.estilo!=='pixel';
   g.drawImage(SAIDA_INICIO_T272,0,0,cv.width,cv.height);
   const pixels=g.getImageData(40,130,240,270).data;let min=255,max=0,soma=0,soma2=0,n=0;
   for(let i=0;i<pixels.length;i+=16){const l=(pixels[i]+pixels[i+1]+pixels[i+2])/3;min=Math.min(min,l);max=Math.max(max,l);soma+=l;soma2+=l*l;n++;}
   return {imagem:cv.toDataURL('image/jpeg',.88),luma:soma/n,variancia:soma2/n-(soma/n)**2,faixa:max-min,metricas:window.METRICAS_RENDER};
  },t);
  const arquivo=path.join(pasta,`r${rodada}-${t.toFixed(3)}.jpg`);
  fs.writeFileSync(arquivo,Buffer.from(q.imagem.split(',')[1],'base64'));
  quadros.push({t,cena:spec.cenas.findIndex(c=>t>=c.ini&&t<c.fim),arquivo,ms:performance.now()-inicio,...q});
 }
 return quadros;
}

export async function revisarAntesDoRender(page,inicial,saida) {
 let spec=inicial;const endpoint=process.env.VIDEO_REVISOR_URL, historico=[];
 // Sem endpoint há análise estrutural/técnica; nunca simula aprovação semântica por IA.
 for(let rodada=0;rodada<2;rodada++) {
  const quadros=await amostrar(page,spec,saida+'.previas',rodada);
  const vazios=quadros.filter(q=>q.faixa<3);
  const registro={rodada,modo:endpoint?'visao-configurada':'tecnico-local',quadros:quadros.map(({imagem,...resto})=>resto)};historico.push(registro);
  const salvar=()=>fs.writeFileSync(saida+'.direcao.json',JSON.stringify({versao:1,historico},null,2));
  if(vazios.length){registro.erro='quadro sem contraste no assunto';salvar();throw Error('[diretor] quadro sem conteúdo visual: '+vazios.map(q=>q.t).join(','));}
  if(!endpoint){salvar();return spec;}
  let resposta;
  try {resposta=await consultarRevisor(endpoint,{spec:Object.fromEntries(['estilo','titulo','dur_s','w','h','cenas','modelo','animal','itens','ativo','data_referencia'].filter(k=>spec[k]!=null).map(k=>[k,spec[k]])),capacidades:{cameras:CAMERAS[spec.estilo]||[],plano:MOTORES_3D.includes(spec.estilo)?(spec.estilo==='lowpoly'?['zoom']:['zoom','exposicao']):[]},quadros:quadros.map(({arquivo,...q})=>q)},{token:process.env.VIDEO_REVISOR_TOKEN||''});}
  catch(e){registro.erro=e.message;salvar();throw e;}
  registro.revisao=resposta;salvar();
  // Valida mesmo a aprovação: não ignora campos ilegais em resposta aprovada.
  let novo;try {novo=aplicarCorrecoes(spec,resposta);}catch(e){registro.erro=e.message;salvar();throw e;}
  if(resposta.aprovado && resposta.correcoes.length===0)return spec;
  if(rodada===1 || !resposta.correcoes.length)throw Error('[diretor] revisão visual não aprovada; confira '+saida+'.direcao.json');
  spec=novo;await page.evaluate(s=>window.preparar(s),spec);
 }
 throw Error('revisão não concluída');
}
