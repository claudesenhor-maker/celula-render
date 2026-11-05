// ANIMAL -- ficha de animal em 3D (23/10, ANIMAL SPECS; um nicho e um motor
// por canal). O animal e' descrito pela IA em formas simples (como o objeto do
// `mecanismo`), fica no tamanho REAL ao lado de uma pessoa, e cada numero da
// frase vira um cartao com barra contra o humano ("mordida 23x a sua").
//
//   spec.animal: { nome, tamanho_m (comprimento real), partes: [{nome, forma, cor, pos, tam, giro}] }
//     -- partes cujo nome tem leg/perna/pata/paw/tail/cauda/rabo/wing/asa/jaw/mandibula
//        ganham movimento (andar, abanar, bater asa, morder)
//   spec.stats: [{ nome, valor, unidade, humano }]      -- humano = o mesmo numero numa pessoa
//   cena: { texto, acao: "mostra|stat|compara|corre|ataca", stat: indice|nome, hud }
//
// CONTRATO (comum.js): `quadro(t)` sem estado entre quadros.
(function () {
  'use strict';
// T448 ANIMAL V2
// T448: funções puras; marcas do áudio são a única fonte de tempo dos números.
const ANIMAL_V2_CANAL = '112117b4-380c-5d32-829f-7b94fc999eb5';
function animalV2Ativo(s) { return s.cell_id === ANIMAL_V2_CANAL && s.animal_v2 !== false; }
function animalV2Normal(s) { return String(s || '').toLowerCase().replace(/[^a-z0-9.%-]+/g,' ').trim(); }
function animalV2Numero(s) {
  const t=animalV2Normal(s).replace(/[.,!?;:]$/,'');
  if (/^-?\d+(?:\.\d+)?%?$/.test(t)) return Number(t.replace('%',''));
  if(t==='hundred')return 100;
  const ns=['zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen'];
  if(ns.includes(t)) return ns.indexOf(t);
  const tens={twenty:20,thirty:30,forty:40,fifty:50,sixty:60,seventy:70,eighty:80,ninety:90};
  const ps=t.split(/[- ]/); if(tens[ps[0]]) return tens[ps[0]]+(ns.indexOf(ps[1])>0?ns.indexOf(ps[1]):0);
  return null;
}
function animalV2Instante(spec, cena, stat, campo='valor') {
  if(!stat || !Array.isArray(spec.palavras)) return null;
  const ws=spec.palavras.filter(w=>Number.isFinite(w.ini)&&w.ini>=cena.ini-.001&&w.ini<cena.fim);
  const alvo=Number(stat[campo]); if(!Number.isFinite(alvo))return null;
  for(let i=0;i<ws.length;i++) {
    let n=animalV2Numero(ws[i].palavra); if(n===null)continue;
    let j=i+1;const seguinte=animalV2Numero(ws[j]?.palavra);
    if(n>=20 && n<100 && n%10===0 && seguinte>0 && seguinte<10){n+=seguinte;j++;}
    if(animalV2Normal(ws[j]?.palavra)==='point' && animalV2Numero(ws[j+1]?.palavra)!==null){n+=animalV2Numero(ws[j+1]?.palavra)/10;j+=2;}
    if(ws.slice(j,j+3).map(w=>animalV2Normal(w.palavra)).join(' ')==='and a half'){n+=.5;j+=3;}
    const prox=animalV2Normal(ws[j]?.palavra), unidade=String(stat.unidade||'').toLowerCase();
    if(prox==='hundred')n*=100; if(prox==='thousand')n*=1000; if(prox==='million')n*=1e6;
    if(/year/.test(prox)&&/day/.test(unidade))n*=365;
    if(/week/.test(prox)&&/day/.test(unidade))n*=7;
    if(Math.abs(n-alvo)<=Math.max(.00001,Math.abs(alvo)*.005))return ws[i].ini;
  }
  return null;
}
function animalV2Progresso(t, inicio) { if(inicio===null||t<inicio)return 0; const q=Math.min(1,Math.max(0,(t-inicio)/.8)); return q*q*(3-2*q); }
function animalV2Barras(a,b,qa,qb) { const mx=Math.max(Math.abs(a),Math.abs(b),1e-9);return [Math.max(0,a)/mx*qa,Math.max(0,b)/mx*qb]; }
function animalV2Revelacao(s) {
  const nome=animalV2Normal(s.animal?.nome).split(' ').filter(Boolean);
  if(!nome.length)return Infinity;
  const ws=s.palavras||[];
  for(let i=0;i<ws.length;i++)if(nome.every((p,j)=>animalV2Normal(ws[i+j]?.palavra)===p))return ws[i].ini;
  return Infinity;
}

  function criar(tela, spec, U) {
    const T = window.THREE, c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const gl = document.createElement('canvas'); gl.width = W; gl.height = H;
    const R = new T.WebGLRenderer({ canvas: gl, antialias: true, preserveDrawingBuffer: true }); R.setSize(W, H, false);
    const cam = new T.PerspectiveCamera(36, W / H, 0.01, 5000);
    const sc = new T.Scene();
    U3.estudio(R, sc, T, { reflexo: false, sombra: false, exposicao: 1.1 });
    const habitat = String((spec.animal || {}).habitat || 'savana');
    const HAB = { savana: ['#C9A46A','#F0C890','#5E7A3A'], floresta: ['#6F8254','#92B1A5','#305C48'], gelo: ['#E2EBF1','#CFDFEB','#BBCAD8'], deserto: ['#D6AE78','#E2C7A5','#B89870'] }[habitat] || ['#C9A46A','#F0C890','#5E7A3A'];
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const vet = (v, a, b, p) => [0, 1, 2].map((i) => num(Array.isArray(v) ? v[i] : undefined, a, b, p[i]));
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const materiais = new Map();
    const M = (cor, tipo='pele') => { const k=cor+tipo; if(!materiais.has(k)) materiais.set(k,U3.material(T,cor,tipo));return materiais.get(k); };
    const F = U3.formas(T);
    // Curvas suaves no protagonista; não gastar tesselação de macro nos olhos/fundo.
    const esferaAnimal=new T.SphereGeometry(.5,24,16),cilindroAnimal=new T.CylinderGeometry(.5,.5,1,20);
    F.esfera=()=>esferaAnimal;F.cilindro=()=>cilindroAnimal;

    // ---- savana ao entardecer: ceu quente, chao de terra com faixas de capim
    { const cv = document.createElement('canvas'); cv.width = 4; cv.height = 256; const g = cv.getContext('2d'); const gr = g.createLinearGradient(0, 0, 0, 256);
      gr.addColorStop(0, '#2B5C8A'); gr.addColorStop(0.55, '#E8A86A'); gr.addColorStop(0.8, '#F6D29A'); gr.addColorStop(1, '#F6D29A'); g.fillStyle = gr; g.fillRect(0, 0, 4, 256); sc.background = new T.CanvasTexture(cv); sc.background.encoding = T.sRGBEncoding; }
    sc.fog = new T.Fog(HAB[1], 40, 260);
    sc.add(new T.HemisphereLight('#FFF4E0', '#6B5A3A', 0.7));
    const sol = new T.DirectionalLight('#FFE2B8', 0.95); sol.position.set(-6, 9, 7); sc.add(sol);
    const texChao = (() => { const cv = document.createElement('canvas'); cv.width = cv.height = 256; const g = cv.getContext('2d'); g.fillStyle = HAB[0]; g.fillRect(0, 0, 256, 256);
      const r = U.rng(5); for (let i = 0; i < 900; i++) { g.fillStyle = r() < 0.5 ? 'rgba(120,96,50,0.25)' : 'rgba(150,170,80,0.28)'; g.fillRect(r() * 256, r() * 256, 2 + r() * 6, 2 + r() * 3); }
      const t = new T.CanvasTexture(cv); t.encoding = T.sRGBEncoding; t.wrapS = t.wrapT = T.RepeatWrapping; return t; })();
    const chao = new T.Mesh(new T.PlaneGeometry(2000, 2000), new T.MeshLambertMaterial({ map: texChao })); chao.rotation.x = -Math.PI / 2; sc.add(chao);
    // acacias e pedras ao longe (paisagem fixa, da semente)
    { const r = U.rng(spec.semente || 'savana'), n = 26;
      const fundoMat=cor=>new T.MeshLambertMaterial({color:new T.Color(cor).convertSRGBToLinear()});
      const troncos = new T.InstancedMesh(new T.CylinderGeometry(.5,.5,1,10), fundoMat('#5B4128'), n);
      const copas = new T.InstancedMesh(new T.IcosahedronGeometry(.5,1), fundoMat(HAB[2]), n);
      const o = new T.Object3D();
      for (let i=0;i<n;i++) {const d=30+r()*150,a=(r()-.5)*Math.PI*1.6,x=Math.sin(a)*d,z=-Math.cos(a)*d,s=.8+r()*1.4;
        o.position.set(x,1.5*s,z);o.scale.set(.35*s,3*s,.35*s);o.updateMatrix();troncos.setMatrixAt(i,o.matrix);
        const rocha = habitat === 'gelo' || habitat === 'deserto';
        o.position.set(x,(rocha ? .6 : 3.3)*s,z);o.scale.set(5*s,(rocha?1:1.3)*s,4*s);o.updateMatrix();copas.setMatrixAt(i,o.matrix);}
      if(habitat !== 'gelo' && habitat !== 'deserto') sc.add(troncos);sc.add(copas); }


    // ---- o animal (normalizado: o COMPRIMENTO vira `tamanho_m` metros)
    const an = spec.animal || {}, tamReal = num(an.tamanho_m, 0.01, 40, 2);
    const bicho = new T.Group(), corpo = new T.Group(); bicho.add(corpo); sc.add(bicho);
    const moveis = [];
    const v2 = animalV2Ativo(spec), revelacaoV2 = animalV2Revelacao(spec);
    (Array.isArray(an.partes) ? an.partes.slice(0, 30) : []).forEach((p, i) => {
      const m = new T.Mesh((F[p.forma] || F.caixa)(), M(corOk(p.cor, '#9A7B55'), p.material || 'pele'));
      const pos = vet(p.pos, -10, 10, [0, 0.5, 0]), tam = vet(p.tam, 0.01, 10, [1, 1, 1]), giro = vet(p.giro, -360, 360, [0, 0, 0]).map((a) => (a * Math.PI) / 180);
      m.position.set(...pos); m.scale.set(...tam); m.rotation.set(...giro);
      const nome = String(p.nome || '').toLowerCase();
      const tipo = /leg|perna|pata|paw|foot|pe\b/.test(nome) ? 'perna' : /tail|cauda|rabo/.test(nome) ? 'cauda' : /wing|asa|fin|nadadeira/.test(nome) ? 'asa' : /jaw|mandibula|boca|mouth/.test(nome) ? 'boca' : null;
      // Pivôs nas juntas: pata no topo, asa/mandíbula no encaixe explícito.
      const pv = new T.Vector3(...vet(p.pivo, -2, 2, tipo === 'perna' ? [0, 0.5, 0] : [0,0,0]));
      if (pv.lengthSq()) { m.geometry=m.geometry.clone();m.geometry.translate(-pv.x,-pv.y,-pv.z);
        pv.multiply(m.scale).applyEuler(m.rotation);m.position.add(pv); }
      m.userData = { nome, escalaBase:tam.slice(), giro, tipo, fase: Number.isFinite(p.fase) ? p.fase : (pos[0] >= 0 ? 0 : Math.PI) + (pos[2] >= 0 ? 0 : Math.PI) }; corpo.add(m); if (tipo) moveis.push(m);
    });
    if (!corpo.children.length) { const m = new T.Mesh(F.capsula(), M('#9A7B55')); m.rotation.z = Math.PI / 2; m.scale.set(1, 2, 1); m.position.y = 0.6; corpo.add(m); }
    { const b = new T.Box3().setFromObject(corpo), s = new T.Vector3(); b.getSize(s); const comp = Math.max(1e-3, s.x, s.z, s.y * 0.6);
      const k = tamReal / comp; corpo.scale.setScalar(k); corpo.position.y = -b.min.y * k; }
    const caixaB = new T.Box3().setFromObject(bicho), tamB = new T.Vector3(); caixaB.getSize(tamB);
    const sombraCv=document.createElement('canvas');sombraCv.width=sombraCv.height=64;const sg=sombraCv.getContext('2d'),gr=sg.createRadialGradient(32,32,0,32,32,32);
    gr.addColorStop(0,'rgba(0,0,0,.4)');gr.addColorStop(1,'rgba(0,0,0,0)');sg.fillStyle=gr;sg.fillRect(0,0,64,64);
    const sombra=new T.Mesh(new T.PlaneGeometry(1,1),new T.MeshBasicMaterial({map:new T.CanvasTexture(sombraCv),transparent:true,depthWrite:false}));
    sombra.rotation.x=-Math.PI/2;sombra.position.y=.008;sombra.scale.set(tamB.x*1.25,tamB.z*1.7,1);sc.add(sombra);

    // a pessoa de referencia (1,75 m), que aparece no `compara`
    const pessoa = new T.Group();
    { const add = (geo, cor, p, s) => { const m = new T.Mesh(geo, M(cor)); m.position.set(...p); m.scale.set(...s); pessoa.add(m); };
      add(F.cilindro(), '#3E6FB0', [0, 1.15, 0], [0.42, 0.65, 0.26]); add(F.esfera(), '#F0C8A0', [0, 1.62, 0], [0.26, 0.28, 0.26]);
      add(F.cilindro(), '#2D3A4F', [-0.11, 0.42, 0], [0.15, 0.84, 0.15]); add(F.cilindro(), '#2D3A4F', [0.11, 0.42, 0], [0.15, 0.84, 0.15]);
      add(F.cilindro(), '#F0C8A0', [-0.27, 1.12, 0], [0.09, 0.62, 0.09]); add(F.cilindro(), '#F0C8A0', [0.27, 1.12, 0], [0.09, 0.62, 0.09]); }
    sc.add(pessoa);

    const stats = (Array.isArray(spec.stats) ? spec.stats.slice(0, 8) : []).map((s) => ({
      nome: String((s && s.nome) || '').toUpperCase().slice(0, 22), valor: num(s && s.valor, -1e9, 1e12, 0), unidade: String((s && s.unidade) || '').slice(0, 10),
      humano: s && s.humano != null ? num(s.humano, -1e9, 1e12, null) : null,
    }));
    const statDe = (cn, i) => { if (typeof cn.stat === 'number') return stats[U.clamp(Math.round(cn.stat), 0, stats.length - 1)];
      const k = stats.findIndex((s) => s.nome === String(cn.stat || '').toUpperCase()); return stats[k >= 0 ? k : Math.min(i, stats.length - 1)]; };

    function animalV2PrimeiraMarca(st,campo,t) {
      for(const cena of spec.cenas) {
        if(cena.ini>t)break;
        const marco=animalV2Instante(spec,cena,st,campo);
        if(marco!==null)return marco;
      }
      return null;
    }
    const hfov = 2 * Math.atan(Math.tan((cam.fov * Math.PI) / 360) * cam.aspect);
    function quadroDo3D(t) {
      const { c: cn, i, k, local } = U.cenaEm(spec, t), acao = cn.acao || 'mostra';
      const comp = acao === 'compara', corre = acao === 'corre', ataca = acao === 'ataca';
      // Uma peça funcional em todo ciclo, inclusive em cenas mostra/stat.
      const textoV2 = animalV2Normal(cn.texto);
      const chaveV2 = /eye|pupil|vision|light/.test(textoV2) ? /eye|pupil|olho/ : /jaw|bite|bone|crush/.test(textoV2) ? /jaw|boca|mandibula/ : /lung|air|breath|energy|muscle/.test(textoV2) ? /belly|body|muscle|lung|corpo/ : /jaw|mouth|head|body|corpo/;
      const focoV2 = corpo.children.find(m=>chaveV2.test(m.userData.nome||'')) || corpo.children[0];
      if(v2) corpo.children.forEach(m=>{if(m.userData.escalaBase)m.scale.set(...m.userData.escalaBase);});
      // pernas, cauda, asas e boca
      moveis.forEach((m) => { const u = m.userData; m.rotation.set(...u.giro);
        const vel = corre ? 11 : 2.2, amp = corre ? 0.55 : 0.08;
        if (u.tipo === 'perna') m.rotation.z += Math.sin(t * vel + u.fase) * amp;
        if (u.tipo === 'cauda') m.rotation.y += Math.sin(t * 3 + u.fase) * 0.35;
        if (u.tipo === 'asa') m.rotation.x += Math.sin(t * (corre ? 14 : 4) + u.fase) * 0.5;
        if (u.tipo === 'boca') m.rotation.z += ataca ? -Math.max(0, Math.sin(Math.min(1, k * 1.6) * Math.PI)) * 0.6 : 0; });
      if(v2 && focoV2) {
        const pulso = Math.sin(Math.PI * U.clamp(local / Math.max(.3,(cn.fim-cn.ini-.22)),0,1));
        if(/jaw|boca|mandibula/.test(focoV2.userData.nome||'')) focoV2.rotation.z -= pulso*.48;
        else { focoV2.scale.y *= 1+.20*pulso; focoV2.scale.z *= 1+.12*pulso; }
      }
      // respira; no `corre` quica; no `ataca` da o bote
      corpo.scale.y = corpo.scale.x * (1 + 0.015 * Math.sin(t * 2.4));
      let x = 0, y = 0;
      if (corre) y = Math.abs(Math.sin(t * 11)) * tamB.y * 0.05;
      if (ataca) x = Math.sin(U.clamp(k * 1.6, 0, 1) * Math.PI) * tamB.x * 0.35;
      bicho.position.set(x, y, 0); sombra.position.x=x;
      // o chao anda debaixo de quem corre (a textura desliza)
      texChao.offset.x = corre ? -local * 0.9 : 0; texChao.repeat.set(400, 400);
      // a pessoa entra de lado no `compara` (e fica nas cenas seguintes se a anterior comparou)
      const pessoaVis = comp || (i > 0 && spec.cenas[i - 1].acao === 'compara' && local < 0.4);
      pessoa.visible = pessoaVis; pessoa.position.set(-(tamB.x / 2 + 0.55), 0, 0.35); pessoa.rotation.y = 0.5;
      // camera: o animal (ou animal + pessoa) cabe na largura, olhando de 3/4
      const alvoW = (comp ? tamB.x + 1.3 : Math.max(tamB.x, tamB.z)) * 0.85, alvoH = comp ? Math.max(tamB.y, 1.8) : tamB.y;
      const d = Math.max((alvoW / 2) / Math.tan(hfov / 2) * 1.12, (alvoH * 1.2) / Math.tan((cam.fov * Math.PI) / 360));
      const ang = (corre ? 1.35 : 0.55) + Math.sin(t * 0.25) * 0.35 + (acao === 'mostra' ? local * 0.25 : 0);
      const cx = (comp ? -0.6 : 0) + x * 0.8, cy = alvoH * 0.55, shake = ataca && k > 0.35 && k < 0.6 ? Math.sin(t * 90) * tamB.y * 0.02 : 0;
      const dd = d * (1 - 0.06 * U.saida(U.clamp(local / 0.6, 0, 1)));
      cam.position.set(cx + Math.sin(ang) * dd, cy + dd * 0.22 + shake, Math.cos(ang) * dd); cam.near = dd / 500; cam.far = dd * 60; cam.updateProjectionMatrix();
      // mirar ABAIXO do animal o sobe na tela: o meio fica livre para o cartao e a legenda mora em 70%
      cam.lookAt(cx, cy * (acao === 'stat' || corre ? 0.05 : 0.4), 0);
      if(v2) {
        // Enquadrar pela caixa REAL da parte/animal; sem crop fixo e sem mínimo de 1 m.
        bicho.updateMatrixWorld(true);
        const box = new T.Box3().setFromObject(focoV2), size = new T.Vector3(), center = new T.Vector3();
        if(comp)box.setFromObject(bicho).expandByObject(pessoa);
        box.getSize(size); box.getCenter(center);
        const extent = Math.max(size.x,size.y,size.z,.0001);
        const dist = Math.max(extent/Math.tan(hfov/2),extent/Math.tan(cam.fov*Math.PI/360))*1.3;
        const blend = i===0 ? U.clamp(local/2.5,0,1) : .18;
        const todo = new T.Vector3(); caixaB.getCenter(todo);
        if(!comp)center.lerp(todo,blend*.55);
        const dv = dist*(1+blend*1.8);
        cam.position.set(center.x+Math.sin(ang)*dv,center.y+dv*.18,center.z+Math.cos(ang)*dv);
        cam.near=Math.max(.000001,dv/500);cam.far=Math.max(300,dv*60);cam.updateProjectionMatrix();
        // A peça fica acima da ficha, em ~28% da altura; mirar no centro a escondia atrás do cartão.
        cam.lookAt(center.x,center.y-dv*.14,center.z);
      }
      U3.render(R, sc, cam, spec, t); c.drawImage(gl, 0, 0, W, H);
      return { cn, i, k, local, acao };
    }

    const fmt = (v) => (Math.abs(v) >= 1e6 ? (v / 1e6).toLocaleString('en-US', { maximumFractionDigits: 1 }) + 'M' : Math.abs(v) >= 1e4 ? Math.round(v).toLocaleString('en-US')
      : v.toLocaleString('en-US', { maximumFractionDigits: Math.abs(v) < 10 ? 1 : 0 }));
    // CARTAO DO NUMERO: conta ate o valor e compara com o humano em barras
    function cartao(st, local, t, cn) {
      if (!st) return;
      const marcoV2 = v2 ? animalV2Instante(spec,cn,st) : null;
      if(v2 && (marcoV2===null || t<marcoV2))return;
      const ent = U.mola(v2 ? t-marcoV2 : local - 0.1, 10); if (ent <= 0) return;
      const q = v2 ? animalV2Progresso(t,marcoV2) : U.suave(U.clamp((local - 0.25) / 1.1, 0, 1));
      const x0 = 70, w = W - 140, y0 = H * 0.42, h = 360;
      c.save(); c.translate(W / 2, y0 + h / 2); c.scale(ent, ent); c.translate(-W / 2, -(y0 + h / 2));
      U.rr(c, x0, y0, w, h, 34); c.fillStyle = 'rgba(24,20,14,0.86)'; c.fill(); c.lineWidth = 6; c.strokeStyle = '#F6C445'; c.stroke();
      c.textBaseline = 'middle'; c.textAlign = 'left'; c.font = (v2 ? '40px' : '50px')+' "Lilita One", sans-serif'; c.fillStyle = '#F6C445'; c.fillText(st.nome, x0 + 40, y0 + (v2 ? 36 : 58));
      c.textAlign = 'right'; c.font = '96px "Lilita One", sans-serif'; c.fillStyle = '#FFFFFF'; const numeroV2=fmt(st.valor*q)+(st.unidade?' '+st.unidade.toUpperCase():'');
      if(v2) {let fonte=68;c.font=fonte+'px "Lilita One", sans-serif';while(c.measureText(numeroV2).width>w-80&&fonte>26)c.font=(--fonte)+'px "Lilita One", sans-serif';}
      c.fillText(numeroV2, x0+w-40,y0+(v2 ? 106 : 64));
      if (st.humano != null && st.valor > 0) {
        const mx = Math.max(st.valor, st.humano, 1e-9), bw = w - 260, by = y0 + 150;
        const nomeA = v2 && t<revelacaoV2 ? '???' : String((spec.animal || {}).nome || 'ANIMAL').toUpperCase().slice(0, 9);
        [[nomeA, st.valor, '#F6C445'], ['HUMAN', st.humano, '#9AA7B8']].forEach(([n, v, cor], j) => {
          const yy = by + j * 82;
          const qBarra = v2 ? animalV2Progresso(t,animalV2PrimeiraMarca(st,j===0?'valor':'humano',t)) : q; c.textAlign = 'left'; c.font = '40px "Lilita One", sans-serif'; c.fillStyle = cor; c.fillText(n, x0 + 40, yy + 26);
          U.rr(c, x0 + 220, yy, bw, 52, 14); c.fillStyle = 'rgba(255,255,255,0.12)'; c.fill();
          U.rr(c, x0 + 220, yy, Math.max(v2 ? 0 : 14, bw * (v / mx) * qBarra), 52, 14); c.fillStyle = cor; c.fill();
        });
        const vezes = st.humano > 0 ? st.valor / st.humano : 0;
        if (!v2 && vezes >= 1.5 && q > 0.9) { const s = U.mola(local - 1.35, 12); c.save(); c.translate(x0 + w - 120, y0 + h - 4); c.rotate(-0.08); c.scale(s, s);
          c.font = '78px "Lilita One", sans-serif'; c.textAlign = 'center'; const tx = 'x' + fmt(vezes), tw = c.measureText(tx).width + 50;
          U.rr(c, -tw / 2, -52, tw, 104, 24); c.fillStyle = '#E4572E'; c.fill(); c.fillStyle = '#FFFFFF'; c.fillText(tx, 0, 6); c.restore(); }
      }
      c.restore();
    }
    // VELOCIMETRO do `corre`
    function velocimetro(st, local) {
      const v = st && /speed|veloc|km|mph/i.test(st.nome + st.unidade) ? st : stats.find((s) => /speed|veloc/i.test(s.nome)) || null; if (!v) return;
      const q = U.saida(U.clamp(local / 1.2, 0, 1)), cx = W / 2, cy = H * 0.53, r = 170, a0 = Math.PI * 0.8, a1 = Math.PI * 2.2;
      c.save(); c.lineCap = 'round'; c.lineWidth = 34; c.strokeStyle = 'rgba(0,0,0,0.45)'; c.beginPath(); c.arc(cx, cy, r, a0, a1); c.stroke();
      c.strokeStyle = '#F6C445'; c.beginPath(); c.arc(cx, cy, r, a0, a0 + (a1 - a0) * q * 0.85); c.stroke();
      c.font = '92px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillStyle = '#FFFFFF'; c.lineWidth = 12; c.strokeStyle = '#1B1B1B';
      const tx = fmt(v.valor * q); c.strokeText(tx, cx, cy); c.fillText(tx, cx, cy); c.font = '42px "Lilita One", sans-serif'; c.strokeText(v.unidade.toUpperCase(), cx, cy + 74); c.fillText(v.unidade.toUpperCase(), cx, cy + 74); c.restore();
      // linhas de velocidade
      const r2 = U.rng(9); c.save(); c.strokeStyle = 'rgba(255,255,255,0.55)'; c.lineWidth = 6;
      for (let j = 0; j < 14; j++) { const y = H * (0.2 + r2() * 0.45), x = ((r2() * W - local * 2600) % (W + 400) + W + 400) % (W + 400) - 200; c.beginPath(); c.moveTo(x, y); c.lineTo(x + 160 + r2() * 160, y); c.stroke(); }
      c.restore();
    }
    function etiquetaAltura(acao, local) {
      if (acao !== 'compara' || local < 0.5) return;
      const v = tamReal, txt = (v >= 1 ? v.toLocaleString('en-US', { maximumFractionDigits: 1 }) + ' M' : Math.round(v * 100) + ' CM') + '  vs  1.75 M';
      const s = U.mola(local - 0.5, 10); c.save(); c.translate(W / 2, H * 0.6); c.scale(s, s); c.font = '70px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
      const w = c.measureText(txt).width + 60; U.rr(c, -w / 2, -54, w, 108, 26); c.fillStyle = '#1B1B1B'; c.fill(); c.fillStyle = '#F6C445'; c.fillText(txt, 0, 4); c.restore();
    }

    function quadro(t) {
      const { cn, i, k, local, acao } = quadroDo3D(t);
      if (i > 0 && local < 0.1) { c.fillStyle = 'rgba(255,255,255,' + (0.3 * (1 - local / 0.1)).toFixed(2) + ')'; c.fillRect(0, 0, W, H); }
      if (acao === 'ataca' && k > 0.35 && k < 0.5) { c.fillStyle = 'rgba(255,60,40,0.18)'; c.fillRect(0, 0, W, H); }
      if (acao === 'stat' || (v2 && i<2)) {
        const st = v2 && i<2 ? statDe(spec.cenas[0],0) : statDe(cn,i);
        // O comparativo do gancho permanece na mesma escala entre as duas falas.
        const cenaDado = v2 && i<2 ? {ini:spec.cenas[0].ini,fim:spec.cenas[Math.min(1,spec.cenas.length-1)].fim} : cn;
        cartao(st, v2 && i<2 ? t : local, t, cenaDado);
      }
      if (acao === 'corre') { if(v2)cartao(statDe(cn,i),local,t,cn);else velocimetro(statDe(cn, i), local); }
      if(!v2) etiquetaAltura(acao, local);
      if ((!v2 || (t>=3 && i>=2)) && cn.hud && typeof cn.hud !== 'object' && acao !== 'stat' && local > 0.3) { const s = U.mola(local - 0.3, 10); c.save(); c.translate(W / 2, 330); c.scale(s, s);
        c.font = '120px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; const txt = U.hud(c, cn.hud, c.canvas.width * 0.84 - 70, 22), w = c.measureText(txt).width + 70;
        U.rr(c, -w / 2, -78, w, 156, 34); c.fillStyle = '#1B1B1B'; c.fill(); c.fillStyle = '#F6C445'; c.fillText(txt, 0, 6); c.restore(); }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 150, fundo: '#F6C445', borda: '#1B1B1B', cor: '#1B1B1B', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '100px "Lilita One", sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#F6C445', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro, dispose: () => U3.liberar(R, sc) };
  }
  MOTORES.animal = { criar };
})();
