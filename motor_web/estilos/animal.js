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
function animalV2Titulo(s,t,revelacao) {
  const titulo=String(s.titulo||'');if(t>=revelacao)return titulo;
  const nome=String(s.animal?.nome||'');
  const i=nome?titulo.toLowerCase().indexOf(nome.toLowerCase()):-1;
  const semNome=i>=0?titulo.slice(0,i)+titulo.slice(i+nome.length):titulo.includes(':')?titulo.slice(titulo.indexOf(':')+1):titulo;
  return semNome.replace(/^[\s:—-]+|[\s:—-]+$/g,'')||'???';
}
function animalV2Fmt(v) { return Number(v).toLocaleString('en-US', {maximumSignificantDigits: 6}); }
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
    U3.estudio(R, sc, T, { reflexo: false, sombra: false, exposicao: 1.03 });
    const habitat = String((spec.animal || {}).habitat || 'savana');
    const HAB = { savana: ['#C9A46A','#F0C890','#5E7A3A'], floresta: ['#6F8254','#92B1A5','#305C48'], gelo: ['#E2EBF1','#CFDFEB','#BBCAD8'], deserto: ['#D6AE78','#E2C7A5','#B89870'] }[habitat] || ['#C9A46A','#F0C890','#5E7A3A'];
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const vet = (v, a, b, p) => [0, 1, 2].map((i) => num(Array.isArray(v) ? v[i] : undefined, a, b, p[i]));
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const materiais = new Map();
    const M = (cor, tipo='pele') => { const k=cor+tipo; if(!materiais.has(k)) materiais.set(k,U3.material(T,cor,tipo));return materiais.get(k); };
    const F = U3.formas(T);
    // Curvas suaves no protagonista; não gastar tesselação de macro nos olhos/fundo.
    const esferaAnimal=new T.SphereGeometry(.5,32,24),cilindroAnimal=new T.LatheGeometry(Array.from({length:25},(_,i)=>{const y=i/24-.5;return new T.Vector2(.48*Math.pow(Math.max(.001,Math.sin(Math.PI*i/24)),.22),y);}),32);
    F.esfera=()=>esferaAnimal;F.cilindro=()=>cilindroAnimal;

    // T464: acabamento procedural, sem assets pagos nem alteração do spec.
    const aquatico = /fish|shark|lungfish|peixe|tubar/i.test(spec.animal?.nome||'');
    const ave = /bird|eagle|owl|parrot|penguin|ave|pássaro/i.test(spec.animal?.nome||'');
    const pele = document.createElement('canvas');pele.width=pele.height=256;
    {const g=pele.getContext('2d'),r=U.rng('pele464');g.fillStyle='#c5c3b7';g.fillRect(0,0,256,256);
     for(let i=0;i<1200;i++){const x=r()*256,y=r()*256;g.strokeStyle='rgba(40,35,30,'+(.06+r()*.15)+')';g.lineWidth=.5+r();g.beginPath();g.moveTo(x,y);g.quadraticCurveTo(x+4,y-2,x+7,y+1);g.stroke();}}
    const peleTex=new T.CanvasTexture(pele);peleTex.wrapS=peleTex.wrapT=T.RepeatWrapping;peleTex.encoding=T.sRGBEncoding;
    const organica = (p) => {
      const n=String(p.nome||'').toLowerCase();
      if(/ear|orelha|wing|asa|fin|nadadeira/.test(n)) {
        const sh=new T.Shape();sh.moveTo(-.45,.38);sh.bezierCurveTo(-.2,.58,.2,.58,.43,.35);
        sh.bezierCurveTo(.65,.08,.42,-.35,.12,-.5);sh.bezierCurveTo(-.12,-.56,-.48,-.27,-.5,.05);sh.bezierCurveTo(-.54,.22,-.5,.3,-.45,.38);
        const g=new T.ExtrudeGeometry(sh,{depth:.65,bevelEnabled:true,bevelThickness:.17,bevelSize:.06,bevelSegments:3,steps:1,curveSegments:12});g.translate(0,0,-.325);g.computeVertexNormals();return g;
      }
      if(/body|belly|corpo|breast|head|jaw|boca|foot|pad/.test(n))return esferaAnimal;
      if(p.forma==='cilindro')return cilindroAnimal;
      if(p.forma==='capsula')return esferaAnimal;
      return (F[p.forma]||F.esfera)();
    };
    // ---- savana ao entardecer: ceu quente, chao de terra com faixas de capim
    { const cv = document.createElement('canvas'); cv.width = 4; cv.height = 256; const g = cv.getContext('2d'); const gr = g.createLinearGradient(0, 0, 0, 256);
      gr.addColorStop(0, '#2B5C8A'); gr.addColorStop(0.55, '#E8A86A'); gr.addColorStop(0.8, '#F6D29A'); gr.addColorStop(1, '#F6D29A'); g.fillStyle = gr; g.fillRect(0, 0, 4, 256); sc.background = new T.CanvasTexture(cv); sc.background.encoding = T.sRGBEncoding; }
    sc.fog = new T.Fog(HAB[1], 65, 260);
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
    const bicho = new T.Group(), corpo = new T.Group(); bicho.userData.animal464=true; bicho.add(corpo); sc.add(bicho);
    const moveis = [];
    const v2 = animalV2Ativo(spec), revelacaoV2 = animalV2Revelacao(spec);
    (Array.isArray(an.partes) ? an.partes.slice(0, 30) : []).forEach((p, i) => {
      const m = new T.Mesh(organica(p), M(corOk(p.cor, '#9A7B55'), p.material || 'pele'));
      const pos = vet(p.pos, -10, 10, [0, 0.5, 0]), tam = vet(p.tam, 0.01, 10, [1, 1, 1]), giro = vet(p.giro, -360, 360, [0, 0, 0]).map((a) => (a * Math.PI) / 180);
      // Specs descrevem torso com comprimento no maior eixo, mesmo quando
      // a primitiva veio girada como cilindro. A anatomia mantém esse comprimento.
      if(/^(body|corpo|belly)$/.test(String(p.nome)) && Math.abs(giro[2])>1.3 && Math.abs(giro[2])<1.8){const a=Math.max(tam[0],tam[1]),b=Math.min(tam[0],tam[1]);tam[0]=a;tam[1]=b;giro[2]=0;}
      m.position.set(...pos); m.scale.set(...tam); m.rotation.set(...giro);
      if(!/eye|olho|tusk|dente/.test(String(p.nome))){m.material.map=peleTex;m.material.roughness=.88;}
      if(/eye|olho/.test(String(p.nome))){const brilho=new T.Mesh(esferaAnimal,new T.MeshBasicMaterial({color:'#ffffff'}));brilho.scale.set(.23,.23,.23);brilho.position.set(.14,.18,.43);m.add(brilho);}
      if(ave && /wing/.test(String(p.nome))){for(let j=0;j<7;j++){const pena=new T.Mesh(esferaAnimal,M(j>3?'#353a3d':corOk(p.cor,'#9c978e')));pena.position.set(-.36+j*.105,-.2-j*.035,0);pena.scale.set(.2,.8,.9);pena.rotation.z=-.25;m.add(pena);}}

      const nome = String(p.nome || '').toLowerCase();
      const tipo = /leg|perna|pata|paw|foot|pe\b/.test(nome) ? 'perna' : /tail|cauda|rabo/.test(nome) ? 'cauda' : /wing|asa|fin|nadadeira/.test(nome) ? 'asa' : /jaw|mandibula|boca|mouth/.test(nome) ? 'boca' : null;
      // Pivôs nas juntas: pata no topo, asa/mandíbula no encaixe explícito.
      const pv = new T.Vector3(...vet(p.pivo, -2, 2, tipo === 'perna' ? [0, 0.5, 0] : [0,0,0]));
      if (pv.lengthSq()) { m.geometry=m.geometry.clone();m.geometry.translate(-pv.x,-pv.y,-pv.z);
        pv.multiply(m.scale).applyEuler(m.rotation);m.position.add(pv); }
      m.userData = { nome, escalaBase:tam.slice(), giro, tipo, fase: Number.isFinite(p.fase) ? p.fase : (pos[0] >= 0 ? 0 : Math.PI) + (pos[2] >= 0 ? 0 : Math.PI) }; corpo.add(m); if (tipo) moveis.push(m);
    });
    // Peixes: uma superfície contínua da cauda ao focinho. Os cilindros do
    // contrato definem medidas e cor, não uma pilha de troncos desconectados.
    if(aquatico){
      const tronco=corpo.children.filter(m=>/^(body|body_rear|belly|head|snout|tail)$/.test(m.userData.nome||''));
      if(tronco.length>=3){
        const body=tronco.find(m=>m.userData.nome==='body')||tronco[0],bb=new T.Box3();tronco.forEach(m=>bb.expandByObject(m));
        const x0=bb.min.x,x1=bb.max.x,len=x1-x0;
        const radius=Math.max(.015,Math.min(body.scale.y,body.scale.z)*.52);
        const profile=[[0,.05],[.08,.25],[.23,.55],[.42,.82],[.62,1],[.78,1.08],[.9,.94],[.97,.55],[1,.03]];
        const curve=new T.CatmullRomCurve3(profile.map(([u,v])=>new T.Vector3(v*radius,x0+u*len,0)));
        const points=curve.getPoints(60).map(v=>new T.Vector2(Math.max(radius*.02,v.x),v.y));
        const geo=new T.LatheGeometry(points,40);geo.rotateZ(-Math.PI/2);
        const m=new T.Mesh(geo,body.material);m.position.y=body.position.y;m.userData={nome:'body',giro:[0,0,0],escalaBase:[1,1,1]};corpo.add(m);
        tronco.forEach(m=>{corpo.remove(m);const i=moveis.indexOf(m);if(i>=0)moveis.splice(i,1);});
        // Brilho longitudinal e escamas pequenas vêm da textura procedural.
        m.material.roughness=.6;
      }
    }
    // Juntas compartilhadas: coxa, canela e pé seguem a mesma perna.
    const juntas=new Map();
    for(const m of corpo.children.slice())if(m.userData.tipo==='perna'){
      const n=m.userData.nome,side=/left|esquer/.test(n)?'left':/right|direit/.test(n)?'right':String(m.position.z>=0);
      const key=(/front|frente/.test(n)?'front':/back|rear|tras/.test(n)?'back':'leg')+side;
      if(!juntas.has(key))juntas.set(key,[]);juntas.get(key).push(m);
    }
    for(const ms of juntas.values()){
      const box=new T.Box3();ms.forEach(m=>box.expandByObject(m));const center=box.getCenter(new T.Vector3()),g=new T.Group();
      g.position.set(center.x,box.max.y,center.z);g.userData={nome:'joint',giro:[0,0,0],tipo:'perna',fase:ms[0].userData.fase};
      corpo.add(g);for(const m of ms){corpo.remove(m);m.position.sub(g.position);g.add(m);moveis.splice(moveis.indexOf(m),1);}moveis.push(g);
    }
    // Tromba contínua: respeita a curva dada pelas partes, sem juntas abertas.
    const tromba=corpo.children.filter(m=>/trunk_(upper|mid|tip)/.test(m.userData.nome||'')).sort((a,b)=>b.position.y-a.position.y);
    if(tromba.length>=3){const pts=[tromba[0].position.clone().add(new T.Vector3(0,tromba[0].scale.y*.5,0)),...tromba.map(m=>m.position.clone()),tromba.at(-1).position.clone().add(new T.Vector3(0,-tromba.at(-1).scale.y*.45,0))];
      const g=new T.TubeGeometry(new T.CatmullRomCurve3(pts),40,.5,16,false),ps=g.attributes.position;
      // Afinar ao longo da curva, do encaixe até a ponta.
      for(let i=0;i<=40;i++){const k=i/40,center=new T.CatmullRomCurve3(pts).getPointAt(k),radius=.45*(1-k)+.16*k;
       for(let j=0;j<=16;j++){const id=i*17+j,v=new T.Vector3().fromBufferAttribute(ps,id);v.sub(center).multiplyScalar(radius).add(center);ps.setXYZ(id,v.x,v.y,v.z);}}
      g.computeVertexNormals();const m=new T.Mesh(g,tromba[0].material);m.userData={nome:'trunk',giro:[0,0,0],tipo:'tromba',fase:0};corpo.add(m);moveis.push(m);
      tromba.forEach(m=>corpo.remove(m));}
    if (!corpo.children.length) { const m = new T.Mesh(F.capsula(), M('#9A7B55')); m.rotation.z = Math.PI / 2; m.scale.set(1, 2, 1); m.position.y = 0.6; corpo.add(m); }
    { const b = new T.Box3().setFromObject(corpo), s = new T.Vector3(); b.getSize(s); const comp = Math.max(1e-3, s.x, s.z, s.y * 0.6);
      const k = tamReal / comp; corpo.scale.setScalar(k); corpo.position.y = -b.min.y * k; }
    const caixaB = new T.Box3().setFromObject(bicho), tamB = new T.Vector3(); caixaB.getSize(tamB);
    const sombraCv=document.createElement('canvas');sombraCv.width=sombraCv.height=64;const sg=sombraCv.getContext('2d'),gr=sg.createRadialGradient(32,32,0,32,32,32);
    gr.addColorStop(0,'rgba(0,0,0,.4)');gr.addColorStop(1,'rgba(0,0,0,0)');sg.fillStyle=gr;sg.fillRect(0,0,64,64);
    const sombra=new T.Mesh(new T.PlaneGeometry(1,1),new T.MeshBasicMaterial({map:new T.CanvasTexture(sombraCv),transparent:true,depthWrite:false}));
    sombra.rotation.x=-Math.PI/2;sombra.position.y=.008;sombra.scale.set(tamB.x*1.25,tamB.z*1.7,1);sc.add(sombra);

    // Habitat em camadas: relva e pedras à escala do sujeito, em vez de areia vazia.
    {const r=U.rng(String(spec.semente||'')+'habitat464'),scale=Math.max(tamReal,.15);
     const geo=new T.ConeGeometry(1,1,4),mat=new T.MeshLambertMaterial({color:habitat==='gelo'?'#d7e6ed':aquatico?'#447c6b':'#6c7742'});
     const grass=new T.InstancedMesh(geo,mat,170),o=new T.Object3D();
     for(let i=0;i<170;i++){const x=(r()-.5)*scale*8,z=(r()-.5)*scale*5;
      const h=scale*(.025+r()*.065);o.position.set(x,h/2,z);o.scale.set(h*.2,h,h*.2);o.rotation.set(0,r()*6.28,(r()-.5)*.25);o.updateMatrix();grass.setMatrixAt(i,o.matrix);}sc.add(grass);
     const rocks=new T.InstancedMesh(new T.IcosahedronGeometry(1,1),new T.MeshLambertMaterial({color:'#817e69'}),18);
     for(let i=0;i<18;i++){const a=r()*6.28,d=scale*(1+r()*3),h=scale*(.025+r()*.06);o.position.set(Math.sin(a)*d,h*.3,Math.cos(a)*d);o.rotation.set(r(),r(),r());o.scale.set(h*1.8,h,h*1.1);o.updateMatrix();rocks.setMatrixAt(i,o.matrix);}sc.add(rocks);}

    // a pessoa de referencia (1,75 m), que aparece no `compara`
    const pessoa = new T.Group();
    { const add=(geo,cor,p,s)=>{const m=new T.Mesh(geo,M(cor));m.position.set(...p);m.scale.set(...s);pessoa.add(m);};
      add(esferaAnimal,'#376b78',[0,1.17,0],[.46,.65,.28]);
      add(esferaAnimal,'#d39b77',[0,1.61,0],[.25,.28,.25]);
      add(esferaAnimal,'#302a26',[0,1.71,-.025],[.26,.09,.23]);
      add(esferaAnimal,'#d39b77',[0,1.42,0],[.13,.16,.13]);
      add(esferaAnimal,'#273a48',[0,.86,0],[.35,.22,.25]);
      for(const side of [-1,1]){
       add(cilindroAnimal,'#273a48',[side*.1,.47,0],[.16,.78,.17]);
       add(esferaAnimal,'#252c30',[side*.1,.05,.07],[.19,.1,.32]);
       add(cilindroAnimal,'#376b78',[side*.25,1.25,0],[.14,.3,.14]);
       add(cilindroAnimal,'#d39b77',[side*.29,1.04,.025],[.1,.31,.1]);
       add(esferaAnimal,'#d39b77',[side*.3,.86,.025],[.11,.15,.09]);
      }
    }
    sc.add(pessoa);

    const stats = (Array.isArray(spec.stats) ? spec.stats.slice(0, 8) : []).map((s) => ({
      nome: String((s && s.nome) || '').toUpperCase().slice(0, 22), valor: num(s && s.valor, -1e9, 1e12, 0), unidade: String((s && s.unidade) || '').slice(0, 40),
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
      corpo.children.forEach(m=>{if(m.userData.escalaBase)m.scale.set(...m.userData.escalaBase);});
      // pernas, cauda, asas e boca
      moveis.forEach((m) => { const u = m.userData; m.rotation.set(...u.giro);
        const vel = corre ? 11 : 2.2, amp = corre ? 0.55 : 0.08;
        if (u.tipo === 'perna') m.rotation.z += Math.sin(t * vel + u.fase) * amp;
        if (u.tipo === 'cauda') m.rotation.y += Math.sin(t * 3 + u.fase) * 0.35;
        if(u.tipo==='tromba')m.rotation.z=Math.sin(t*.9)*.015;
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
      texChao.offset.x = corre ? -local * 0.9 : 0; texChao.repeat.set(180, 180);
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
      // T464: caixa animada inteira dentro do assunto (90..875, 350..1000).
      // Ajuste por projeção inclui profundidade, humano e zoom do diretor.
      bicho.updateMatrixWorld(true);pessoa.updateMatrixWorld(true);
      const box=new T.Box3().setFromObject(bicho);if(comp)box.expandByObject(pessoa);
      const center=box.getCenter(new T.Vector3()),size=box.getSize(new T.Vector3());
      const theta=.36+Math.sin(t*.19)*.13+(acao==='mostra'?.12*Math.sin(local*.3):0);
      const zoom=Number(cn.plano?.zoom)||1;cam.zoom=U.clamp(zoom,.75,1.35);
      // Descentrar o sujeito para a esquerda e acima da ficha, sem recorte 2D.
      cam.setViewOffset(W,H,W*.055,H*.148,W,H);
      const corners=[];for(const xx of [box.min.x,box.max.x])for(const yy of [box.min.y,box.max.y])for(const zz of [box.min.z,box.max.z])corners.push(new T.Vector3(xx,yy,zz));
      let lo=Math.max(size.x,size.y,size.z)*.5,hi=Math.max(size.x,size.y,size.z)*15;
      const pose=dd=>{cam.position.set(center.x+Math.sin(theta)*dd,center.y+dd*.12,center.z+Math.cos(theta)*dd);cam.near=Math.max(1e-6,dd/500);cam.far=Math.max(300,dd*100);cam.lookAt(center);cam.updateProjectionMatrix();cam.updateMatrixWorld(true);};
      for(let j=0;j<18;j++){const dd=(lo+hi)/2;pose(dd);const pts=corners.map(v=>v.clone().project(cam));
       const fit=pts.every(v=>v.z<1&&v.x>=-0.82&&v.x<=.62&&v.y>=-.04&&v.y<=.64);if(fit)hi=dd;else lo=dd;}
      pose(hi*1.015);
      U3.render(R, sc, cam, spec, t); c.drawImage(gl, 0, 0, W, H);
      return { cn, i, k, local, acao };
    }

    const fmt = (v) => v2 ? animalV2Fmt(v) : (Math.abs(v) >= 1e6 ? (v / 1e6).toLocaleString('en-US', { maximumFractionDigits: 1 }) + 'M' : Math.abs(v) >= 1e4 ? Math.round(v).toLocaleString('en-US')
      : v.toLocaleString('en-US', { maximumFractionDigits: Math.abs(v) < 10 ? 1 : 0 }));
    // CARTAO DO NUMERO: conta ate o valor e compara com o humano em barras
    function cartao(st, local, t, cn) {
      if (!st) return;
      const valorV2 = v2 ? animalV2Instante(spec,cn,st) : null;
      const humanoV2 = v2 ? animalV2PrimeiraMarca(st,'humano',t) : null;
      const marcoV2 = v2 ? Math.min(...[valorV2,humanoV2].filter(x=>x!==null)) : null;
      if(v2 && (!Number.isFinite(marcoV2) || t<marcoV2))return;
      const ent = Math.min(1,U.mola(v2 ? t-marcoV2 : local - 0.1, 10)); if (ent <= 0) return;
      const q = v2 ? animalV2Progresso(t,valorV2) : U.suave(U.clamp((local - 0.25) / 1.1, 0, 1));
      const x0 = 70, w = W * .74, y0 = H * .52, h = 300;
      c.save(); c.translate(W / 2, y0 + h / 2); c.scale(ent, ent); c.translate(-W / 2, -(y0 + h / 2));
      U.rr(c, x0, y0, w, h, 34); c.fillStyle = 'rgba(24,20,14,0.86)'; c.fill(); c.lineWidth = 6; c.strokeStyle = '#F6C445'; c.stroke();
      c.textBaseline = 'middle'; c.textAlign = 'left'; { let fr = v2 ? 40 : 44; c.font = fr + 'px "Lilita One", sans-serif'; while (c.measureText(st.nome).width > w - 80 && fr > 24) c.font = (--fr) + 'px "Lilita One", sans-serif'; } c.fillStyle = '#F6C445'; c.fillText(st.nome, x0 + 40, y0 + 30);
      c.textAlign = 'right'; c.font = '96px "Lilita One", sans-serif'; c.fillStyle = '#FFFFFF'; const numeroV2=(v2 && (valorV2===null || t<valorV2) ? '—' : fmt(st.valor*q))+(st.unidade?' '+st.unidade.toUpperCase():'');
      // v2 05/11: rótulo e número em linhas próprias (antes "TIME WITHOUT WA" colidia com "1,460 DAYS")
      {let fonte=v2?68:92;c.font=fonte+'px "Lilita One", sans-serif';while(c.measureText(numeroV2).width>w-80&&fonte>26)c.font=(--fonte)+'px "Lilita One", sans-serif';}
      c.fillText(numeroV2, x0+w-40,y0+90);
      if (st.humano != null && st.valor > 0) {
        const mx = Math.max(st.valor, st.humano, 1e-9), bw = w - 260, by = y0 + 130;
        const nomeA = v2 && t<revelacaoV2 ? '???' : String((spec.animal || {}).nome || 'ANIMAL').toUpperCase().slice(0, 9);
        [[nomeA, st.valor, '#F6C445'], ['HUMAN', st.humano, '#9AA7B8']].forEach(([n, v, cor], j) => {
          const yy = by + j * 74;
          const qBarra = v2 ? animalV2Progresso(t,animalV2PrimeiraMarca(st,j===0?'valor':'humano',t)) : q; c.textAlign = 'left'; c.font = '40px "Lilita One", sans-serif'; c.fillStyle = cor; c.fillText(n, x0 + 40, yy + 26);
          U.rr(c, x0 + 220, yy, bw, 52, 14); c.fillStyle = 'rgba(255,255,255,0.12)'; c.fill();
          U.rr(c, x0 + 220, yy, Math.max(v2 ? 0 : 14, bw * (v / mx) * qBarra), 52, 14); c.fillStyle = cor; c.fill();
          if(v2 && qBarra>0) {c.textAlign='right';c.font='26px "Lilita One", sans-serif';c.fillStyle='#FFFFFF';c.fillText(fmt(v*qBarra),x0+w-40,yy+26);}
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
      const s = U.mola(local - 0.5, 10); c.save(); c.translate(W * .43, H * 0.60); c.scale(s, s); c.font = '52px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
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
      if ((!v2 || (t>=3 && i>=2)) && cn.hud && typeof cn.hud!=='object' && acao!=='stat' && local>.3) {
        c.save();c.font='52px "Lilita One", sans-serif';c.textAlign='center';c.textBaseline='middle';
        const txt=String(cn.hud).toUpperCase(),layout=U.textoAjustado(c,txt,W*.70,130,28),h=layout.linhas.length*layout.lh+34;
        U.rr(c,65,190,W*.74,h,22);c.fillStyle='rgba(20,34,33,.93)';c.fill();c.fillStyle='#f4d58a';
        layout.linhas.forEach((l,j)=>c.fillText(l,W*.43,207+layout.lh*(j+.5)));c.restore();
      }
      U.cartaz(c, v2 ? {...spec,titulo:animalV2Titulo(spec,t,revelacaoV2)} : spec, t, { fonte: '84px "Lilita One", sans-serif', y: 150, fundo: '#F6C445', borda: '#1B1B1B', cor: '#1B1B1B', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '100px "Lilita One", sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#F6C445', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro, dispose: () => U3.liberar(R, sc) };
  }
  MOTORES.animal = { criar };
})();
