// Direção e revisão limitadas a dados, antes da codificação. Nenhum código de IA é executado.
export const CAMERAS = {
 mecanismo: ['orbita','perto','frente','cima'], lowpoly: ['orbita','perto','zoom_in','zoom_out','sobrevoo'],
};
export const MOTORES_3D = ['lowpoly','mecanismo','escala','animal','orbita','micro'];
export const BRIEF = `Você é diretor de animação explicativa. Analise os quadros na ordem temporal e confronte cada imagem com a ação e a narração da cena. Priorize: objeto reconhecível, contato e montagem plausíveis, causa e consequência visíveis, material distinto, detalhe útil no close, continuidade, rótulos legíveis e ausência de sobreposição. Preserve a identidade de cada estilo: pixel na grade, silhueta com contraste, mangueira com atuação, 3D com luz e volume. Não invente fatos, não troque textos, cronologia nem números. Em caso de dúvida, relate o problema. Responda JSON {aprovado:boolean, problemas:[string], correcoes:[{cena:indice, camera?:string, plano?:{zoom:number,exposicao:number}}]}. Correções devem ser mínimas, baseadas em defeitos observados; não aplique zoom para disfarçar modelo inadequado. Um problema de anatomia, geometria ou explicação deve reprovar, pois esses campos não podem ser reparados por esta interface.`;
const finite = x => typeof x === 'number' && Number.isFinite(x);
export function prepararSpec(entrada) {
 const spec=structuredClone(entrada), erros=[], avisos=[];
 spec.w ??=1080;spec.h ??=1920;spec.fps ??=30;
 for(const [k,min,max] of [['w',180,3840],['h',320,3840],['fps',1,60],['dur_s',.1,1800]])
  if(!finite(spec[k]) || spec[k]<min || spec[k]>max)erros.push(`${k}: número fora de ${min}..${max}`);
 if(spec.w%2 || spec.h%2)erros.push('dimensões precisam ser pares para yuv420p');
 if(!Array.isArray(spec.cenas)||!spec.cenas.length)erros.push('cenas ausentes');
 if(erros.length)throw Error('[diretor] '+erros.join('; '));
 let fim=0;
 spec.cenas.forEach((c,i)=>{
  if(!finite(c.ini)||!finite(c.fim)||c.ini<0||c.fim<=c.ini||c.ini<fim-.001||c.fim>spec.dur_s+.001)erros.push(`cena ${i}: intervalo inválido`);
  if(c.ini>fim+.001)avisos.push(`cena ${i}: lacuna na linha do tempo`);fim=c.fim;
  if(c.plano!=null && (typeof c.plano!=='object'||Array.isArray(c.plano)))erros.push(`cena ${i}: plano inválido`);
  c.plano={...(c.plano||{})};
  for(const [key,min,max] of [['zoom',.75,1.35],['exposicao',.75,1.3]])if(c.plano[key]!=null && (!finite(c.plano[key])||c.plano[key]<min||c.plano[key]>max))erros.push(`cena ${i}: ${key} fora do limite`);
  c.plano.zoom ??=1;
  if(spec.estilo==='mecanismo' && !c.camera)c.camera=['gira','move','destaque'].includes(c.acao)?'perto':'frente';
  if(c.marcos_visuais!=null && (!Array.isArray(c.marcos_visuais)||c.marcos_visuais.length>4||c.marcos_visuais.some(m=>!m||!finite(m.local_s)||m.local_s<0||m.local_s>=c.fim-c.ini||!['antecipacao','contato','consequencia','revelacao'].includes(m.evento))))erros.push(`cena ${i}: marcos visuais inválidos`);
  if(c.rotulos?.length>4)avisos.push(`cena ${i}: apenas quatro rótulos serão mostrados`);
 });
 if(spec.estilo==='mecanismo') {
  const ps=spec.modelo?.partes;
  if(!Array.isArray(ps)||!ps.length)erros.push('mecanismo sem peças');
  else {const nomes=ps.map(p=>String(p.nome||'').toLowerCase());
   if(new Set(nomes).size!==nomes.length)erros.push('nomes de peças duplicados');
   if(ps.length>40)erros.push('modelo excede 40 peças');
   const pontos=(v,d,min)=>Array.isArray(v)&&v.length>=min&&v.length<=32&&v.every(q=>Array.isArray(q)&&q.length===d&&q.every(n=>finite(n)&&Math.abs(n)<=2));
   ps.forEach((p,i)=>{
    if(p.perfil!=null && (!pontos(p.perfil,2,3)||p.perfil.some(q=>q[0]<0)||!p.perfil.some(q=>q[0]>0)||p.perfil.some((q,j,a)=>j&&q[1]-a[j-1][1]<.0001)))erros.push(`peça ${i}: perfil inválido`);
    if(p.caminho!=null && (!pontos(p.caminho,3,2)||p.caminho.some((q,j,a)=>j&&q.every((n,k)=>n===a[j-1][k]))||!finite(p.raio)||p.raio<.005||p.raio>.25))erros.push(`peça ${i}: caminho/raio inválido`);
    if(p.perfil!=null && p.caminho!=null)erros.push(`peça ${i}: use perfil ou caminho`);
   });
   spec.cenas.forEach((c,i)=>{const al=Array.isArray(c.alvo)?c.alvo:c.alvo?[c.alvo]:[];
    if(al.some(n=>!nomes.includes(String(n).toLowerCase())))erros.push(`cena ${i}: peça alvo inexistente`);
    if(['gira','move','destaque'].includes(c.acao)&&!al.length)erros.push(`cena ${i}: ação precisa de alvo`);
    if(c.acao==='fluxo'&&(!Array.isArray(c.fluxo?.caminho)||c.fluxo.caminho.length<2))erros.push(`cena ${i}: fluxo sem caminho`);
   });
  }
 }
 if(spec.estilo==='escala' && (!Array.isArray(spec.itens)||!spec.itens.length))erros.push('escala sem itens');
 if(spec.estilo==='animal' && !spec.animal?.partes?.length)erros.push('animal sem partes: fallback não é modelo apto a publicar');
 if(spec.estilo==='orbita') {spec.data_referencia ??='2000-01-01T12:00:00Z';if(!Number.isFinite(Date.parse(spec.data_referencia)))erros.push('data_referencia inválida');}
 if(spec.estilo==='pixel')spec.cenas.forEach((c,i)=>{if(c.texto && c.fim-c.ini < c.texto.length/14+.4)avisos.push(`cena ${i}: pouco tempo para leitura`);});
 if(erros.length)throw Error('[diretor] '+erros.join('; '));
 spec.direcao_visual={versao:1,estrategia:'planejar-amostrar-revisar-renderizar',avisos};
 return spec;
}
export function instantesRevisao(spec, limite=16) {
 if(!Number.isInteger(limite)||limite<2||limite>64)throw Error('limite de amostras: 2..64');
 const fps=spec.fps, fim=Math.max(0,spec.dur_s-1/fps);
 const normalizar=xs=>[...new Set(xs.map(t=>Math.min(fim,Math.max(0,Math.round(t*fps)/fps))))].sort((a,b)=>a-b);
 // Prioriza bordas dos cortes e eventos planejados. Sem análise semântica automática.
 const criticos=normalizar([0,fim,...spec.cenas.flatMap(c=>[
  c.ini-1/fps,c.ini,...(c.marcos_visuais||[]).flatMap(m=>[c.ini+m.local_s-1/fps,c.ini+m.local_s,c.ini+m.local_s+1/fps])])]);
 const reduzir=(xs,n)=>Array.from({length:n},(_,i)=>xs[Math.round(i*(xs.length-1)/(n-1))]);
 if(criticos.length>=limite)return reduzir(criticos,limite);
 const outros=normalizar(spec.cenas.flatMap(c=>[c.ini+Math.min(.35,(c.fim-c.ini)*.15),(c.ini+c.fim)/2])).filter(t=>!criticos.includes(t));
 const vagas=limite-criticos.length;
 const extras=outros.length<=vagas?outros:vagas===1?[outros[Math.floor(outros.length/2)]]:reduzir(outros,vagas);
 return normalizar([...criticos,...extras]);
}
export function aplicarCorrecoes(spec, resposta) {
 if(typeof resposta?.aprovado!=='boolean'||!Array.isArray(resposta.problemas)||!Array.isArray(resposta.correcoes))throw Error('revisor: resposta fora do contrato');
 if(resposta.correcoes.length>spec.cenas.length*2)throw Error('revisor: correções em excesso');
 const novo=structuredClone(spec);
 for(const patch of resposta.correcoes) {
  if(!Number.isInteger(patch.cena)||!novo.cenas[patch.cena])throw Error('revisor: cena inválida');
  if(Object.keys(patch).some(k=>!['cena','camera','plano'].includes(k)))throw Error('revisor: campo de correção não permitido');
  const cn=novo.cenas[patch.cena];
  if(patch.camera!=null){if(!CAMERAS[spec.estilo]?.includes(patch.camera))throw Error('revisor: câmera não suportada');cn.camera=patch.camera;}
  if(patch.plano){if(!MOTORES_3D.includes(spec.estilo))throw Error('revisor: este motor 2D não oferece correção de plano');if(spec.estilo==='lowpoly' && patch.plano.exposicao!=null)throw Error('revisor: lowpoly usa iluminação própria');if(typeof patch.plano!=='object'||Array.isArray(patch.plano)||Object.keys(patch.plano).some(k=>!['zoom','exposicao'].includes(k)))throw Error('revisor: plano inválido');cn.plano={...cn.plano,...patch.plano};}
 }
 return prepararSpec(novo);
}
export async function consultarRevisor(endpoint, dados, {token='', timeout=60000}={}) {
 const res=await fetch(endpoint,{method:'POST',signal:AbortSignal.timeout(timeout),headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},body:JSON.stringify({versao:1,instrucao:BRIEF,...dados})});
 if(!res.ok)throw Error(`revisor HTTP ${res.status}`);
 const texto=await res.text();if(texto.length>100000)throw Error('resposta do revisor excedeu limite');return JSON.parse(texto);
}
