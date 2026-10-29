// LOWPOLY v2 -- "E se...?" narrado num mundo-diorama 3D (22/10; v1 de 13/10, HISTORICO §109).
//
// POR QUE A v2 (22/10, ordem do dono: "a animacao do TINY WHAT IF esta ruim,
// foque na qualidade e no SENTIDO da animacao")
//   A v1 tinha 14 eventos e nenhum ligava a imagem a frase: no video dos oceanos
//   (46740f18) "os oceanos secaram" virou `encolhe` (uma pessoa encolhendo),
//   "a chuva para" virou `chuva_meteoros` e "11 km de profundidade" virou o
//   planeta parando de girar. O roteirista era obrigado a variar a acao com um
//   vocabulario curto demais, e o motor ignorava `hud`, `objeto` e `hora`.
//
// O QUE MUDOU
//   1. SENTIDO: ~30 eventos que ilustram frases comuns de "what if" (seca,
//      chove, erupcao, impacto, vento, incendio, derrete, sem_ar, mostra...).
//      `acaoCoerente` e' a rede de seguranca: se a frase fala de chuva e a
//      acao escolhida nao tem nada a ver, troca pela que a frase descreve
//      (e avisa no console). Funciona tambem com roteiro antigo na fila.
//   2. NUMERO NA TELA: o numero que a narracao diz ("70 degrees Celsius",
//      "11 kilometers", "86%") aparece num cartao que conta ate o valor, e a
//      marca de tempo ("WITHIN WEEKS") aparece num selo. `hud` do roteiro,
//      quando vem, manda.
//   3. QUALIDADE: cada cena e' um diorama redondo (o "tiny world" do canal)
//      com terreno facetado, ceu em degrade pela hora, sol/lua, neblina e
//      sombra; o planeta e' um globo inteiro no quadro, com oceano separado
//      (que pode secar), nuvens e lua. As pessoas tem rosto (piscam, boca
//      muda com a emocao) e poses (frio, calor, susto, aponta, comemora,
//      flutua, sufoca). Passagem de cena com dissolve curto + empurrao de
//      camera, no lugar do flash branco.
//
// CONTRATO (comum.js): `quadro(t)` nao guarda estado entre chamadas -- tudo o
// que anda vem de `t`, da cena e da semente. Particulas sao posicoes calculadas
// de `t`, nunca integradas.
(function () {
  'use strict';

  // ---------------------------------------------------------------- sentido
  // Palavras que DESCREVEM cada evento (ingles e portugues). A acao escolhida
  // pelo roteirista vale se a frase tem alguma pista dela, ou se a frase nao
  // tem pista de nada (ai a escolha dele e' tao boa quanto qualquer outra).
  const PISTAS = {
    estiagem: /\b(rain stops|no rain|stop(s|ped)? raining|drought|never rain|without rain|estiagem|parar de chover|sem chuva)/i,
    erupcao: /\b(volcan\w*|erupt\w*|lava|magma|vulc\w*|erup\w*)/i,
    impacto: /\b(asteroid|comet|impact|collid\w*|crash(es|ed)? into|hit(s)? (the )?earth|asteroide|cometa|colis\w*)/i,
    chuva_meteoros: /\b(meteor\w*|shooting stars|meteoro\w*)/i,
    sem_ar: /\b(oxygen|breath\w*|suffocat\w*|air (runs out|disappear\w*|vanish\w*)|no air|oxig\w*|respir\w*|sufoc\w*)/i,
    derrete: /\b(melt\w*|ice caps?|glacier\w*|derret\w*|geleira)/i,
    sol_cresce: /\b(sun (grows|expand\w*|swallow\w*)|red giant|gigante vermelha)/i,
    aurora: /\b(aurora\w*|northern lights|magnetic field|campo magn\w*)/i,
    congela: /\b(freez\w*|frozen|ice age|ice\b|icy|below zero|minus \d+|snowball|congel\w*|gelo|gelad\w*)/i,
    inunda: /\b(flood\w*|c(a|o)me(s)? back|rush\w* back|sea levels? ris\w*|underwater|submerg\w*|tsunami|wave\b|inund\w*|alag\w*|submers\w*)/i,
    seca: /\b(drain|drained|dry|dried|dries|vanish\w* ocean|ocean\w* vanish|no (more )?water|empty (sea|ocean)|seafloor|sea floor|seca|secou|secar|esvazi)/i,
    chove: /\b(rain(s|ed|ing|fall|storm|y)?|downpour|monsoon|chuva|chove)\b/i,
    tremor: /\b(quake\w*|earthquake|shak\w*|tremor|rumbl\w*|terremoto|trem\w*)/i,
    explode: /\b(explod\w*|explosion|blast|bomb|boom|explo\w*)/i,
    noite_eterna: /\b(dark(ness)?|eternal night|night forever|no (sun|daylight)|sun (goes out|disappear\w*|vanish\w*)|escur\w*|noite eterna)/i,
    amanhece: /\b(sunrise|dawn|daylight return\w*|sun (comes|came) back|amanhec\w*|nascer do sol)/i,
    para_de_girar: /\b(stop\w* (spinning|rotating|turning)|rotation|spin(s|ning)?\b|day (would )?last|parar de girar|rota\w*|gira\w*)/i,
    gravidade_zero: /\b(gravity|weightless|float\w*|gravidade|flutu\w*)/i,
    vento: /\b(wind\w*|hurricane\w*|tornado\w*|storm\w*|gust\w*|vento\w*|furac\w*|tempestade)/i,
    incendio: /\b(fire\w*|burn\w*|wildfire\w*|flames?|smoke|inc[eê]ndi\w*|queima\w*|fogo|fuma\w*)/i,
    murcha: /\b(plants? die|forests? die|crops? fail|wither\w*|dead trees|die standing|murch\w*|plantas morr\w*)/i,
    brota: /\b(grow back|regrow\w*|bloom\w*|sprout\w*|green again|brot\w*|florest\w* volt\w*)/i,
    esquenta: /\b(heat|hot\b|hotter|boil\w*|scorch\w*|bak\w*|degrees|celsius|fahrenheit|warm\w*|calor|quente|ferv\w*|graus)/i,
    cresce: /\b(grow(s|ing)?\b|grew|giant|expand\w*|cresc\w*|gigante)/i,
    encolhe: /\b(shrink\w*|shrunk|miniature|encolh\w*)/i,
    lua_perto: /\b(moon\b|tides?|lua|mar[eé])/i,
    multidao: /\b(everyone|people|humans|humanity|crowd|billion people|population|todo mundo|pessoas|humanidade|popula\w*)/i,
    corre: /\b(run(s|ning)?|flee\w*|escape\w*|panic\w*|corr\w*|fug\w*)/i,
    anda: /\b(walk\w*|step\w*|anda\w*|caminh\w*)/i,
  };
  // As que NUNCA trocam: neutras de proposito.
  const NEUTRAS = { mostra: 1, compara: 1, orbita: 1 };
  // As que so' fazem sentido se a frase falar delas: sem pista nenhuma na
  // frase, um planeta parando ou um meteoro caindo CONTA OUTRA HISTORIA
  // (o "11 km de canions" do 46740f18 virou o planeta freando). Ai a cena
  // vira `mostra`: o lugar, a camera andando e o numero da frase.
  const SO_COM_PISTA = { para_de_girar: 1, chuva_meteoros: 1, impacto: 1, explode: 1, gravidade_zero: 1, congela: 1, esquenta: 1, inunda: 1, seca: 1,
    erupcao: 1, tremor: 1, noite_eterna: 1, sol_cresce: 1, encolhe: 1, cresce: 1, sem_ar: 1, incendio: 1, aurora: 1, lua_perto: 1, derrete: 1, estiagem: 1, chove: 1, vento: 1 };

  function acaoCoerente(cn, i) {
    const txt = String(cn.texto || ''), pedida = cn.acao || 'mostra';
    if (NEUTRAS[pedida] || (PISTAS[pedida] && PISTAS[pedida].test(txt))) return pedida;
    // a primeira pista que bate, na ordem de PISTAS (do mais especifico ao geral)
    for (const a of Object.keys(PISTAS)) {
      if (PISTAS[a].test(txt)) {
        if (a !== pedida) console.log('[lowpoly] cena ' + i + ": '" + pedida + "' -> '" + a + "' (a frase descreve " + a + ')');
        return a;
      }
    }
    if (SO_COM_PISTA[pedida]) { console.log('[lowpoly] cena ' + i + ": '" + pedida + "' -> 'mostra' (a frase nao fala disso)"); return 'mostra'; }
    return pedida;
  }

  // O NUMERO DA FRASE: "70 degrees Celsius" -> "70°C"; "86%" -> "86%".
  const UNID = [
    [/^(%|percent|por cento)/i, '%'], [/^(°\s?c|degrees? celsius|celsius|graus celsius|graus)/i, '°C'],
    [/^(°\s?f|degrees? fahrenheit|fahrenheit)/i, '°F'], [/^degrees?/i, '°'],
    [/^(km\/h|kilometers? (per|an) hour|quil[oô]metros por hora)/i, ' KM/H'], [/^(mph|miles per hour)/i, ' MPH'],
    [/^(km|kilomet(er|re)s?|quil[oô]metros?)/i, ' KM'], [/^(miles?)/i, ' MILES'], [/^(meters?|metres?|metros?)\b/i, ' M'],
    [/^(feet|ft)\b/i, ' FT'], [/^(billion|bilh[oõ]es)/i, ' BILLION'], [/^(million|milh[oõ]es)/i, ' MILLION'],
    [/^(trillion|trilh[oõ]es)/i, ' TRILLION'], [/^(years?|anos?)/i, ' YEARS'], [/^(days?|dias?)/i, ' DAYS'],
    [/^(hours?|horas?)/i, ' HOURS'], [/^(minutes?|minutos?)/i, ' MIN'], [/^(seconds?|segundos?)/i, ' SEC'],
    [/^(times|vezes|x)\b/i, 'x'], [/^(tons?|toneladas?)/i, ' TONS'],
  ];
  function hudDaCena(cn) {
    if (cn.hud != null && typeof cn.hud !== 'object' && String(cn.hud).trim()) return String(cn.hud).trim().toUpperCase().slice(0, 18);
    const t = String(cn.texto || '');
    const re = /(-?\d[\d,.]*\d|\d)\s*/g; let m;
    while ((m = re.exec(t))) {
      const resto = t.slice(m.index + m[0].length);
      for (const [r, u] of UNID) if (r.test(resto)) return (m[1] + u).toUpperCase();
    }
    return '';
  }
  const TEMPO_RE = /\b(in the first (few )?(seconds?|minutes?|hours?|days?|weeks?|months?|years?)|within (seconds|minutes|hours|days|weeks|months|years|decades|a (day|week|month|year|decade))|after (a|an|one|two|three|\d+|a few) (seconds?|minutes?|hours?|days?|weeks?|months?|years?|decades?|centur(y|ies))|\d+ (seconds?|minutes?|hours?|days?|years?) later|by (day|week|year) \d+|em (poucos )?(segundos|minutos|horas|dias|semanas|meses|anos)|depois de (um|uma|\d+) \w+)/i;
  function tempoDaCena(cn) { const m = String(cn.texto || '').match(TEMPO_RE); return m ? m[0].toUpperCase() : ''; }

  // ------------------------------------------------------------------ paleta
  const COR = {
    pele: ['#F2C9A5', '#D9A47E', '#A8724F', '#7A4E35'], roupa: ['#E46A86', '#3E7CB1', '#F2B705', '#5DAA5A', '#8E6CCF', '#EF7D3C'],
    cabelo: ['#3A2A22', '#1E1A18', '#B5652E', '#E8C46A'], calca: '#3B4A63',
  };
  const CEU = { // [topo, horizonte] por hora
    dia: ['#5FB3F0', '#CFEFFF'], entardecer: ['#3D3B7A', '#FF9E6B'], aurora: ['#6D7FD1', '#FFD3A8'], noite: ['#05081C', '#1C2A55'],
    tempestade: ['#3E4655', '#8A94A3'], quente: ['#E4572E', '#FFD27A'], frio: ['#9CC9E8', '#F2FAFF'], cinza: ['#7C7C7C', '#C9C2B4'],
    espaco: ['#02030C', '#0B1030'],
  };

  function criar(tela, spec, U) {
    const T = window.THREE;
    const c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const gl = document.createElement('canvas'); gl.width = W; gl.height = H;
    const R = new T.WebGLRenderer({ canvas: gl, antialias: true, preserveDrawingBuffer: true });
    R.setSize(W, H, false);
    const cam = new T.PerspectiveCamera(38, W / H, 0.1, 400);

    // ---------------------------------------------------------- utilitarios
    const caixas = new Map();
    const caixaGeo=(...dims)=>{const k=dims.join(':');if(!caixas.has(k))caixas.set(k,new T.BoxGeometry(...dims));return caixas.get(k);};
    const matCache = {};
    const M = (cor, o) => {
      o = o || {};
      const k = cor + JSON.stringify(o);
      if (!matCache[k] || o.unico) {
        const m = new T.MeshLambertMaterial({  color: cor, emissive: o.emis || '#000000', transparent: !!o.op, opacity: o.op || 1 });
        if (o.unico) return m;
        matCache[k] = m;
      }
      return matCache[k];
    };
    // FACETADO SEM CUSTO POR PIXEL (22/10): o Phong com flatShading custava
    // ~1,3 s por quadro no SwiftShader do runner. Geometria nao-indexada com a
    // normal da FACE em cada vertice da o mesmo facetado no Lambert, que
    // ilumina por vertice.
    const facetada = new WeakMap();
    function facetar(raiz) {
      raiz.traverse(q=>{
        if(!q.isMesh || q.material.isMeshBasicMaterial)return;
        if(facetada.has(q.geometry)){q.geometry=facetada.get(q.geometry);return;}
        const original=q.geometry,g=original.index?original.toNonIndexed():original;
        g.computeVertexNormals();facetada.set(original,g);facetada.set(g,g);q.geometry=g;
      });
    }
    // SOMBRA DE CONTATO (22/10): a sombra projetada de verdade custava ~240 ms
    // por quadro no SwiftShader (amostragem do mapa em cada pixel). Uma mancha
    // suave no pe de cada coisa assenta o objeto no chao, que e' o que a sombra
    // fazia aqui, e custa quase nada.
    const TX_SOMBRA = (() => { const cv = document.createElement('canvas'); cv.width = cv.height = 64; const g = cv.getContext('2d'); const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32); gr.addColorStop(0, 'rgba(0,0,0,0.55)'); gr.addColorStop(0.6, 'rgba(0,0,0,0.25)'); gr.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gr; g.fillRect(0, 0, 64, 64); return new T.CanvasTexture(cv); })();
    const MAT_SOMBRA = new T.MeshBasicMaterial({ map: TX_SOMBRA, transparent: true, depthWrite: false });
    const sombra = (m, faz, recebe, tam) => {
      if (faz === false) return m;
      const b = new T.Box3().setFromObject(m), lx = Math.max(0.5, b.max.x - b.min.x), lz = Math.max(0.5, b.max.z - b.min.z);
      const s0 = new T.Mesh(new T.PlaneGeometry(1, 1), MAT_SOMBRA); s0.rotation.x = -Math.PI / 2; s0.position.set(0.25, 0.03, 0.2); s0.scale.set((tam || 1) * lx * 1.5, (tam || 1) * lz * 1.5, 1); s0.userData.sombra = 1;
      m.add(s0); m.userData.sombra = s0; return m;
    };
    // ruido de valor deterministico (sem estado)
    const hash = (x, y, z) => { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return s - Math.floor(s); };
    function ruido(x, y, z) {
      const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z), xf = x - xi, yf = y - yi, zf = z - zi;
      const s = (k) => k * k * (3 - 2 * k), u = s(xf), v = s(yf), w = s(zf);
      let r = 0;
      for (let a = 0; a < 2; a++) for (let b = 0; b < 2; b++) for (let d = 0; d < 2; d++) {
        r += hash(xi + a, yi + b, zi + d) * (a ? u : 1 - u) * (b ? v : 1 - v) * (d ? w : 1 - w);
      }
      return r;
    }
    const fbm = (x, y, z) => ruido(x, y, z) * 0.6 + ruido(x * 2.1, y * 2.1, z * 2.1) * 0.28 + ruido(x * 4.3, y * 4.3, z * 4.3) * 0.12;
    function texturaGradiente(cores) {
      const cv = document.createElement('canvas'); cv.width = 4; cv.height = 256; const g = cv.getContext('2d');
      const gr = g.createLinearGradient(0, 0, 0, 256); gr.addColorStop(0, cores[0]); gr.addColorStop(0.62, cores[1]); gr.addColorStop(1, cores[1]);
      g.fillStyle = gr; g.fillRect(0, 0, 4, 256); const tx = new T.CanvasTexture(cv); return tx;
    }
    function texturaBrilho(cor) {
      const cv = document.createElement('canvas'); cv.width = cv.height = 128; const g = cv.getContext('2d');
      const gr = g.createRadialGradient(64, 64, 0, 64, 64, 64); gr.addColorStop(0, cor); gr.addColorStop(0.35, cor.replace('1)', '0.45)')); gr.addColorStop(1, cor.replace('1)', '0)'));
      g.fillStyle = gr; g.fillRect(0, 0, 128, 128); return new T.CanvasTexture(cv);
    }
    const TX_PONTO = texturaBrilho('rgba(255,255,255,1)');
    function brilho(cor, tam) {
      const s = new T.Sprite(new T.SpriteMaterial({ map: texturaBrilho(cor), transparent: true, depthWrite: false, blending: T.AdditiveBlending }));
      s.scale.set(tam, tam, 1); return s;
    }
    function particulas(n, cor, tam, op) {
      const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(new Float32Array(n * 3), 3));
      const p = new T.Points(g, new T.PointsMaterial({ color: cor, size: tam, map: TX_PONTO, transparent: true, opacity: op == null ? 0.95 : op, depthWrite: false }));
      p.frustumCulled = false; return p;
    }
    function riscos(n, cor, op) { // chuva/vento: segmentos de reta
      const g = new T.BufferGeometry(); g.setAttribute('position', new T.Float32BufferAttribute(new Float32Array(n * 6), 3));
      const l = new T.LineSegments(g, new T.LineBasicMaterial({ color: cor, transparent: true, opacity: op || 0.7 })); l.frustumCulled = false; return l;
    }

    // -------------------------------------------------------------- objetos
    function arvore(tipo, cor) {
      const g = new T.Group();
      const tr = new T.Mesh(new T.CylinderGeometry(0.1, 0.15, 0.7, 5), M('#7A5232')); tr.position.y = 0.35; g.add(tr);
      if (tipo === 'pinheiro') { [0, 1, 2].forEach((k) => { const co = new T.Mesh(new T.ConeGeometry(0.75 - k * 0.2, 0.9, 7), M(cor || '#3F8F55')); co.position.y = 0.9 + k * 0.45; g.add(co); }); }
      else if (tipo === 'cacto') { g.remove(tr); const b = new T.Mesh(new T.CylinderGeometry(0.22, 0.25, 1.6, 7), M('#5E9E4A')); b.position.y = 0.8; g.add(b); [-1, 1].forEach((s) => { const a = new T.Mesh(new T.CylinderGeometry(0.12, 0.12, 0.6, 6), M('#5E9E4A')); a.position.set(s * 0.32, 1.0 + s * 0.15, 0); g.add(a); }); }
      else { const co = new T.Mesh(new T.IcosahedronGeometry(0.75, 0), M(cor || '#5DAA5A')); co.position.y = 1.25; co.scale.set(1, 0.95, 1); g.add(co); }
      g.userData.copa = g.children.filter((q) => q !== tr);
      return sombra(g);
    }
    function predio(w, h, d, cor, r) {
      const g = new T.Group();
      const b = new T.Mesh(caixaGeo(w, h, d), M(cor)); b.position.y = h / 2; g.add(b);
      const jan = M('#FFE9A8', { emis: '#000000' }), janN = M('#FFD66B', { emis: '#B88A1A' });
      const anda = Math.max(1, Math.floor(h / 0.7));
      g.userData.janelas = [];
      const gruposJan = new Map();
      // 23/10: janelas nas QUATRO faces (so' a da frente tinha, e ela olhava para o centro: da camera o predio era uma caixa lisa)
      for (let k = 0; k < anda; k++) for (let f = 0; f < 4; f++) for (const s of [-1, 1]) {
        if (r() < 0.22) continue;
        const larg = f % 2 ? d : w, prof = f % 2 ? w : d;
        const j = new T.Mesh(caixaGeo(larg * 0.22, 0.28, 0.04), jan);
        const ang = (f * Math.PI) / 2; j.position.set(Math.sin(ang) * (prof / 2 + 0.02) + Math.cos(ang) * s * larg * 0.24, 0.45 + k * 0.7, Math.cos(ang) * (prof / 2 + 0.02) - Math.sin(ang) * s * larg * 0.24);
        j.rotation.y = ang; j.updateMatrix();
        if(!gruposJan.has(larg))gruposJan.set(larg,[]);gruposJan.get(larg).push(j.matrix.clone());
      }
      gruposJan.forEach((matrizes,larg)=>{const inst=new T.InstancedMesh(caixaGeo(larg*.22,.28,.04),jan,matrizes.length);
        matrizes.forEach((m,i)=>inst.setMatrixAt(i,m));g.add(inst);g.userData.janelas.push(inst);});
      const laje = new T.Mesh(caixaGeo(w * 1.06, 0.14, d * 1.06), M(new T.Color(cor).multiplyScalar(0.78).getStyle())); laje.position.y = h + 0.07; g.add(laje);
      g.userData.matNoite = janN; g.userData.matDia = jan;
      return sombra(g, true, true);
    }
    function casa(cor) {
      const g = new T.Group();
      const b = new T.Mesh(caixaGeo(1.2, 0.9, 1.0), M(cor || '#F3E3C3')); b.position.y = 0.45; g.add(b);
      const t = new T.Mesh(new T.ConeGeometry(0.98, 0.7, 4), M('#C8553D')); t.position.y = 1.25; t.rotation.y = Math.PI / 4; g.add(t);
      const p = new T.Mesh(caixaGeo(0.28, 0.45, 0.04), M('#7A5232')); p.position.set(0, 0.23, 0.51); g.add(p);
      return sombra(g, true, true);
    }
    function carro(cor) {
      const g = new T.Group();
      const b = new T.Mesh(caixaGeo(0.9, 0.3, 0.45), M(cor)); b.position.y = 0.25; g.add(b);
      const t = new T.Mesh(caixaGeo(0.5, 0.22, 0.4), M('#DDEBF5')); t.position.set(-0.05, 0.5, 0); g.add(t);
      [[-0.3, 0.23], [0.3, 0.23], [-0.3, -0.23], [0.3, -0.23]].forEach(([x, z]) => { const r = new T.Mesh(new T.CylinderGeometry(0.11, 0.11, 0.08, 8), M('#222')); r.rotation.x = Math.PI / 2; r.position.set(x, 0.11, z); g.add(r); });
      return sombra(g);
    }
    function nuvem(r, cor) {
      const g = new T.Group();
      for (let k = 0; k < 4; k++) { const s = new T.Mesh(new T.IcosahedronGeometry(0.5 + r() * 0.4, 0), M(cor || '#FFFFFF', { op: 0.92 })); s.position.set((k - 1.5) * 0.55, r() * 0.25, r() * 0.3); g.add(s); }
      g.scale.set(1, 0.55, 0.8);
      return g;
    }
    function pinguim() {
      const g = new T.Group();
      const b = new T.Mesh(new T.IcosahedronGeometry(0.35, 1), M('#1E2430')); b.scale.set(1, 1.35, 1); b.position.y = 0.45; g.add(b);
      const f = new T.Mesh(new T.IcosahedronGeometry(0.27, 1), M('#F4F4F4')); f.scale.set(1, 1.3, 0.6); f.position.set(0, 0.42, 0.17); g.add(f);
      const bi = new T.Mesh(new T.ConeGeometry(0.07, 0.18, 4), M('#F2A007')); bi.rotation.x = Math.PI / 2; bi.position.set(0, 0.72, 0.33); g.add(bi);
      return sombra(g);
    }
    function peixe(cor) {
      const g = new T.Group();
      const b = new T.Mesh(new T.IcosahedronGeometry(0.25, 0), M(cor || '#F28C38')); b.scale.set(1.5, 0.8, 0.5); g.add(b);
      const c2 = new T.Mesh(new T.ConeGeometry(0.16, 0.25, 4), M(cor || '#F28C38')); c2.rotation.z = Math.PI / 2; c2.position.x = -0.42; g.add(c2);
      return sombra(g);
    }
    function guardaChuva(cor) {
      const g = new T.Group();
      const c1 = new T.Mesh(new T.ConeGeometry(0.75, 0.35, 8, 1, true), M(cor || '#E2574C')); c1.position.y = 2.95; g.add(c1);
      const h = new T.Mesh(new T.CylinderGeometry(0.03, 0.03, 1.2, 4), M('#333')); h.position.y = 2.35; g.add(h);
      return sombra(g);
    }
    function vulcao(r) {
      const g = new T.Group();
      const geo = new T.CylinderGeometry(0.9, 4.2, 4.2, 10, 3, true), p = geo.attributes.position;
      for (let i = 0; i < p.count; i++) { const y = p.getY(i); if (y < 2 && y > -2) { const s = 1 + (hash(p.getX(i), y, p.getZ(i)) - 0.5) * 0.18; p.setX(i, p.getX(i) * s); p.setZ(i, p.getZ(i) * s); } }
      geo.computeVertexNormals();
      const cone = new T.Mesh(geo, M('#5A4048')); cone.position.y = 2.1; g.add(cone);
      const lava = new T.Mesh(new T.CylinderGeometry(0.85, 0.85, 0.2, 10), M('#FF6A2A', { emis: '#FF4A00' })); lava.position.y = 4.15; g.add(lava);
      g.userData.lava = lava;
      return sombra(g, true, true);
    }
    function gelo() { const m = new T.Mesh(caixaGeo(1.1, 2.9, 1.1), new T.MeshLambertMaterial({  color: '#BFE8FF', transparent: true, opacity: 0.55 })); m.position.y = 1.45; return m; }

    // -------------------------------------------------------------- pessoa
    function pessoa(r, idx) {
      const g = new T.Group(), corpo = new T.Group(); g.add(corpo);
      const roupa = COR.roupa[idx % COR.roupa.length], pele = COR.pele[Math.floor(r() * COR.pele.length)], cab = COR.cabelo[Math.floor(r() * COR.cabelo.length)];
      const tronco = new T.Mesh(new T.CylinderGeometry(0.33, 0.42, 1.0, 7), M(roupa)); tronco.position.y = 1.2; corpo.add(tronco);
      const quadril = new T.Mesh(new T.CylinderGeometry(0.46, 0.4, 0.25, 7), M(COR.calca)); quadril.position.y = 0.62; corpo.add(quadril);
      // 23/10 (dono: "pessoas confusas"): cabeca proporcional ao corpo (era 0,46 para um tronco de 1,0 e o
      // cabelo uma bola MAIOR que ela); cabelo em touca, olhos pequenos, pescoco.
      const pescoco = new T.Mesh(new T.CylinderGeometry(0.11, 0.13, 0.18, 6), M(pele)); pescoco.position.y = 1.76; corpo.add(pescoco);
      const cabeca = new T.Group(); cabeca.position.y = 2.06; corpo.add(cabeca);
      const crane = new T.Mesh(new T.IcosahedronGeometry(0.34, 1), M(pele)); crane.scale.set(1, 1.08, 0.98); cabeca.add(crane);
      const estilo = Math.floor(r() * 3);
      const cabelo = new T.Mesh(new T.SphereGeometry(0.375, 10, 6, 0, Math.PI * 2, 0, Math.PI * (estilo === 1 ? 0.62 : 0.5)), M(cab));
      cabelo.position.set(0, 0.05, -0.02); cabelo.rotation.x = -0.25; cabeca.add(cabelo);
      if (estilo === 2) { const coque = new T.Mesh(new T.IcosahedronGeometry(0.15, 1), M(cab)); coque.position.set(0, 0.3, -0.24); cabeca.add(coque); }
      const olhoM = M('#151515'), olhos = [];
      [-0.12, 0.12].forEach((x) => { const o = new T.Mesh(new T.SphereGeometry(0.052, 8, 6), olhoM); o.position.set(x, 0.03, 0.31); cabeca.add(o); olhos.push(o);
        const b = new T.Mesh(new T.SphereGeometry(0.017, 5, 4), M('#FFFFFF')); b.position.set(x + 0.016, 0.05, 0.355); cabeca.add(b); olhos.push(b); });
      const bocaRiso = new T.Mesh(new T.TorusGeometry(0.075, 0.018, 4, 8, Math.PI), M('#5A2020')); bocaRiso.rotation.z = Math.PI; bocaRiso.position.set(0, -0.12, 0.315); cabeca.add(bocaRiso);
      const bocaO = new T.Mesh(new T.CircleGeometry(0.055, 8), M('#5A2020')); bocaO.position.set(0, -0.14, 0.335); cabeca.add(bocaO);
      const bocaReta = new T.Mesh(caixaGeo(0.11, 0.022, 0.02), M('#5A2020')); bocaReta.position.set(0, -0.13, 0.335); cabeca.add(bocaReta);
      const membros = [];
      [[-0.55, 1.6, 'b'], [0.55, 1.6, 'b'], [-0.2, 0.58, 'p'], [0.2, 0.58, 'p']].forEach(([x, y, tipo]) => {
        const piv = new T.Group(); piv.position.set(x, y, 0);
        const l = tipo === 'b' ? 0.75 : 0.6;
        const m = new T.Mesh(new T.CylinderGeometry(tipo === 'b' ? 0.11 : 0.14, tipo === 'b' ? 0.1 : 0.13, l, 6), M(tipo === 'b' ? roupa : COR.calca)); m.position.y = -l / 2; piv.add(m);
        const ponta = new T.Mesh(tipo === 'b' ? new T.IcosahedronGeometry(0.12, 0) : caixaGeo(0.22, 0.12, 0.34), M(tipo === 'b' ? pele : '#2B2B2B'));
        ponta.position.set(0, -l, tipo === 'b' ? 0 : 0.06); piv.add(ponta);
        corpo.add(piv); membros.push(piv);
      });
      const suor = []; for (let k = 0; k < 3; k++) { const s = new T.Mesh(new T.IcosahedronGeometry(0.06, 0), M('#7CC7FF')); s.visible = false; cabeca.add(s); suor.push(s); }
      g.userData = { corpo, cabeca, membros, olhos, bocaRiso, bocaO, bocaReta, suor, fase: r() * 10 };
      return sombra(g);
    }
    // POSES: cada modo diz ombros (x frente/tras, z abre), quadril, corpo, cabeca e boca.
    function posar(p, modo, t, k) {
      const u = p.userData, m = u.membros, tf = t + u.fase;
      const rot = (q, x, z) => { q.rotation.x = x; q.rotation.z = z || 0; };
      let boca = 'riso', olhoS = 1, bob = 0, inclina = 0, cabX = Math.sin(tf * 0.9) * 0.05, cabZ = Math.sin(tf * 1.3) * 0.06, tremor = 0, agach = 1;
      const anda = (vel, amp) => { const a = tf * vel; rot(m[0], Math.sin(a) * amp, 0.08); rot(m[1], -Math.sin(a) * amp, -0.08); rot(m[2], -Math.sin(a) * amp); rot(m[3], Math.sin(a) * amp); bob = Math.abs(Math.sin(a)) * 0.12 * amp; };
      switch (modo) {
        case 'anda': anda(6, 0.6); break;
        case 'corre': anda(11, 1.05); inclina = 0.25; boca = 'O'; break;
        case 'surpreso': rot(m[0], 0, 2.5 + Math.sin(tf * 9) * 0.12); rot(m[1], 0, -2.5 - Math.sin(tf * 9) * 0.12); rot(m[2], 0); rot(m[3], 0); boca = 'O'; olhoS = 1.35; bob = Math.max(0, U.mola(k * 3, 10) - 0.9) * 0.6; break;
        case 'frio': rot(m[0], -0.9, -0.9); rot(m[1], -0.9, 0.9); rot(m[2], 0); rot(m[3], 0); tremor = 0.035; boca = 'reta'; agach = 0.95; break;
        case 'calor': rot(m[0], 0.1, 0.15); rot(m[1], -2.3 + Math.sin(tf * 14) * 0.35, -0.4); rot(m[2], 0); rot(m[3], 0); boca = 'O'; u.suor.forEach((s, j) => { s.visible = true; const q = (tf * 0.9 + j / 3) % 1; s.position.set(-0.35 + j * 0.35, 0.3 - q * 0.9, 0.3); }); break;
        case 'aponta': rot(m[0], 0, 0.1); rot(m[1], -1.45, -0.25); rot(m[2], 0); rot(m[3], 0); cabX = -0.15; boca = 'O'; break;
        case 'olha_cima': rot(m[0], 0, 0.15); rot(m[1], 0, -0.15); rot(m[2], 0); rot(m[3], 0); cabX = -0.55; boca = 'O'; olhoS = 1.2; break;
        case 'comemora': { const s = Math.abs(Math.sin(tf * 7)); rot(m[0], 0, 2.7 + s * 0.2); rot(m[1], 0, -2.7 - s * 0.2); rot(m[2], 0); rot(m[3], 0); bob = s * 0.35; break; }
        case 'flutua': rot(m[0], 0.3, 1.2 + Math.sin(tf) * 0.2); rot(m[1], -0.3, -1.2 - Math.sin(tf) * 0.2); rot(m[2], 0.4, 0.3); rot(m[3], -0.3, -0.3); boca = 'O'; break;
        case 'sufoca': rot(m[0], -2.0, -0.6); rot(m[1], -2.0, 0.6); rot(m[2], 0); rot(m[3], 0); boca = 'O'; inclina = Math.sin(tf * 3) * 0.12; agach = 0.94; break;
        case 'medo': rot(m[0], -0.4, 2.85); rot(m[1], -0.4, -2.85); rot(m[2], 0.2); rot(m[3], -0.2); boca = 'O'; tremor = 0.025; agach = 0.9; olhoS = 1.3; break;
        case 'nada': rot(m[0], 0.5 + Math.sin(tf * 4) * 0.4, 0.6); rot(m[1], -0.5 - Math.sin(tf * 4) * 0.4, -0.6); rot(m[2], Math.sin(tf * 4) * 0.4); rot(m[3], -Math.sin(tf * 4) * 0.4); boca = 'O'; break;
        default: rot(m[0], Math.sin(tf * 1.4) * 0.05, 0.1); rot(m[1], -Math.sin(tf * 1.4) * 0.05, -0.1); rot(m[2], 0); rot(m[3], 0);
      }
      if (modo !== 'calor') u.suor.forEach((s) => { s.visible = false; });
      u.corpo.position.y = bob; u.corpo.rotation.x = inclina; u.corpo.scale.y = agach * (1 + Math.sin(tf * 2.2) * 0.012);
      u.corpo.position.x = tremor ? Math.sin(tf * 60) * tremor : 0;
      u.cabeca.rotation.x = cabX; u.cabeca.rotation.z = cabZ;
      // piscar: 0,12 s a cada ~3,7 s
      const pisca = ((tf % 3.7) < 0.12) ? 0.12 : 1;
      u.olhos.forEach((o, j) => { if (j % 2 === 0) o.scale.set(olhoS, olhoS * pisca, olhoS); else o.visible = pisca === 1; });
      u.bocaRiso.visible = boca === 'riso'; u.bocaO.visible = boca === 'O'; u.bocaReta.visible = boca === 'reta';
    }

    // ------------------------------------------------------------- cenarios
    // Cada cena e' um DIORAMA: um disco de terra flutuando no ceu, com borda de
    // estratos. E' a cara "tiny world" do canal e resolve o enquadramento 9:16:
    // o mundo inteiro cabe no quadro e a camera gira em volta dele.
    const RAIO = 8;
    function terreno(cen, r) {
      const cores = { deserto: ['#E8B86A', '#D9A050'], polo: ['#F4F7FA', '#DCE9F2'], vulcao: ['#5A4048', '#46323A'], floresta: ['#78B66B', '#5E9E55'],
        oceano: ['#E8D9A8', '#D8C690'], cidade: ['#9CB48A', '#8AA57A'], montanha: ['#7FAF6E', '#8C8C8C'], praia: ['#EBD9A6', '#D9C48E'], campo: ['#9BC46A', '#86B25A'], lua: ['#B9B4AA', '#9C978E'] }[cen] || ['#9CB48A', '#8AA57A'];
      const aneis = 14, segs = 40, pos = [], idx = [], cor = [];
      const alt = (x, z) => {
        const d = Math.hypot(x, z) / RAIO, borda = U.clamp((1 - d) * 4, 0, 1);
        let h = (fbm(x * 0.18 + 3, 0.5, z * 0.18) - 0.45) * (cen === 'montanha' ? 4.2 : cen === 'deserto' ? 1.6 : 0.9);
        if (cen === 'montanha') h += Math.max(0, 2.6 - Math.hypot(x + 2, z + 3) * 0.7);
        if (cen === 'lua') { const cr = [[2, -2, 1.4], [-3, 1, 1.0], [1, 3, 0.8]]; cr.forEach(([cx, cz, rr]) => { const q = Math.hypot(x - cx, z - cz) / rr; if (q < 1.3) h += q < 1 ? -(1 - q * q) * 0.5 : (1.3 - q) * 0.6; }); }
        // praca central plana: e' onde fica quem age
        const centro = U.clamp(Math.hypot(x, z - 1) / 3.2, 0, 1);
        return h * borda * centro;
      };
      for (let a = 0; a <= aneis; a++) for (let s = 0; s < segs; s++) {
        const rr = (a / aneis) * RAIO, ang = (s / segs) * Math.PI * 2 + (a % 2) * (Math.PI / segs);
        const x = Math.cos(ang) * rr, z = Math.sin(ang) * rr; pos.push(x, alt(x, z), z);
      }
      for (let a = 0; a < aneis; a++) for (let s = 0; s < segs; s++) {
        const i0 = a * segs + s, i1 = a * segs + (s + 1) % segs, j0 = (a + 1) * segs + s, j1 = (a + 1) * segs + (s + 1) % segs;
        idx.push(i0, i1, j0, i1, j1, j0);
      }
      // nao-indexado para a cor por FACE (o low-poly le a face, nao o vertice)
      const g0 = new T.BufferGeometry(); g0.setAttribute('position', new T.Float32BufferAttribute(pos, 3)); g0.setIndex(idx);
      const g = g0.toNonIndexed(), p = g.attributes.position;
      for (let i = 0; i < p.count; i += 3) {
        const yM = (p.getY(i) + p.getY(i + 1) + p.getY(i + 2)) / 3, hv = hash(p.getX(i), p.getZ(i), 7);
        const cx = (p.getX(i) + p.getX(i + 1) + p.getX(i + 2)) / 3, cz = (p.getZ(i) + p.getZ(i + 1) + p.getZ(i + 2)) / 3;
        // manchas grandes (ruido), nao face a face: face a face vira zebra
        const mancha = U.suave((fbm(cx * 0.22 + 9, 1.3, cz * 0.22) - 0.42) / 0.16);
        let col = new T.Color(cores[0]).lerp(new T.Color(cores[1]), mancha);
        if (cen === 'montanha' && yM > 1.6) col = new T.Color(yM > 2.4 ? '#F4F7FA' : '#8C8C8C');
        col.offsetHSL(0, 0, (hv - 0.5) * 0.035);
        for (let k = 0; k < 3; k++) cor.push(col.r, col.g, col.b);
      }
      g.setAttribute('color', new T.Float32BufferAttribute(cor, 3)); g.computeVertexNormals();
      const topo = new T.Mesh(g, new T.MeshLambertMaterial({  vertexColors: true }));
      const grupo = new T.Group(); grupo.add(topo);
      // borda de estratos (terra, pedra) -- o diorama
      const lados = [['#8B5E3C', 0.0, 0.9], ['#6E4A30', 0.9, 0.8], ['#5B5B66', 1.7, 1.3]];
      lados.forEach(([cc, y0, hh], j) => { const l = new T.Mesh(new T.CylinderGeometry(RAIO * (1 - j * 0.07), RAIO * (1 - (j + 1) * 0.07), hh, segs, 1, true), M(cc)); l.position.y = -y0 - hh / 2 - 0.01; grupo.add(l); });
      const base = new T.Mesh(new T.ConeGeometry(RAIO * 0.79, 2.6, segs), M('#4A4A55')); base.rotation.x = Math.PI; base.position.y = -3.0 - 1.3; grupo.add(base);
      grupo.userData = { topo, alt };
      return grupo;
    }

    // OBJETOS CRIADOS PELA IA (22/10, ordem do dono: "criar objetos livremente
    // durante a execucao, nao algo fechado por codigo"). A cena pode trazer
    // `criar`: uma lista de objetos DESCRITOS EM DADOS que a IA monta a partir
    // da frase -- nada e' executado como codigo. Cada objeto:
    //   { "modelo": "pessoa|arvore|pinheiro|cacto|casa|predio|carro|nuvem|pinguim|peixe|vulcao|gelo"   (peca pronta)
    //     ou "partes": [{ "forma": "caixa|esfera|cone|cilindro|icosa|toro|piramide",
    //                     "cor": "#hex", "pos": [x,y,z], "tam": [sx,sy,sz], "giro": [rx,ry,rz], "brilha": bool }],
    //     "pos": [x, z] ou [x, y, z], "escala": n, "giro": graus em y,
    //     "anim": [{ "de": 0..1, "ate": 0..1, "mover": [dx,dy,dz], "girar": [voltas x,y,z],
    //                "escalar": fator, "surgir": bool, "sumir": bool, "pulsar": bool }] }
    // Limites: 12 objetos e 14 partes por objeto; numeros fora da faixa sao
    // cortados. O tempo e' o `k` da cena (0..1): nada guarda estado entre quadros.
    const FORMAS = {
      caixa: () => caixaGeo(1, 1, 1), esfera: () => new T.IcosahedronGeometry(0.5, 1), cone: () => new T.ConeGeometry(0.5, 1, 7),
      cilindro: () => new T.CylinderGeometry(0.5, 0.5, 1, 8), icosa: () => new T.IcosahedronGeometry(0.5, 0), toro: () => new T.TorusGeometry(0.4, 0.12, 6, 12),
      piramide: () => new T.ConeGeometry(0.6, 1, 4),
    };
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const vet = (v, a, b, p) => [0, 1, 2].map((i) => num(Array.isArray(v) ? v[i] : undefined, a, b, p[i]));
    const corOk = (c, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(c || '')) ? c : p);
    function pecaPronta(nome, r) {
      return ({ pessoa: () => pessoa(r, 1), arvore: () => arvore('redonda'), pinheiro: () => arvore('pinheiro'), cacto: () => arvore('cacto'),
        casa: () => casa(), predio: () => predio(1.2, 3, 1.2, '#C9B79C', r), carro: () => carro('#E2574C'), nuvem: () => nuvem(r),
        pinguim: () => pinguim(), peixe: () => peixe(), vulcao: () => vulcao(r), gelo: () => gelo() }[nome] || (() => null))();
    }
    function montarCriados(cn, idx, o, r) {
      const lista = Array.isArray(cn.criar) ? cn.criar.slice(0, 12) : [];
      o.criados = [];
      lista.forEach((d, j) => {
        try {
          let g = d.modelo ? pecaPronta(String(d.modelo), r) : null;
          if (!g) {
            g = new T.Group();
            (Array.isArray(d.partes) ? d.partes.slice(0, 14) : []).forEach((pt) => {
              const f = FORMAS[pt.forma] || FORMAS.caixa;
              const cor = corOk(pt.cor, '#CCCCCC');
              const m = new T.Mesh(f(), M(cor, pt.brilha ? { emis: cor } : undefined));
              m.position.set(...vet(pt.pos, -20, 20, [0, 0.5, 0]));
              m.scale.set(...vet(pt.tam, 0.02, 20, [1, 1, 1]));
              m.rotation.set(...vet(pt.giro, -360, 360, [0, 0, 0]).map((a) => (a * Math.PI) / 180));
              g.add(m);
            });
            if (!g.children.length) return;
            sombra(g);
          }
          const pos = Array.isArray(d.pos) && d.pos.length === 3 ? vet(d.pos, -30, 30, [0, 0, 0]) : (() => { const [x, z] = vet(d.pos, -30, 30, [0, 0, 0]); return [x, null, z]; })();
          if (pos[1] === null) pos[1] = o.terreno ? o.terreno.userData.alt(pos[0], pos[2]) : 0;
          g.position.set(pos[0], pos[1], pos[2]);
          const esc = num(d.escala, 0.05, 30, 1); g.scale.setScalar(esc);
          g.rotation.y = (num(d.giro, -360, 360, 0) * Math.PI) / 180;
          g.userData.criado = { base: g.position.clone(), esc, giro: g.rotation.clone(), anim: Array.isArray(d.anim) ? d.anim.slice(0, 6) : [] };
          o.sc.add(g); o.criados.push(g);
        } catch (e) { console.log('[lowpoly] cena ' + idx + ': objeto criado ' + j + ' ignorado (' + e.message + ')'); }
      });
      if (o.criados.length) console.log('[lowpoly] cena ' + idx + ': ' + o.criados.length + ' objeto(s) criado(s) pela IA');
    }
    function animarCriados(o, k, t) {
      (o.criados || []).forEach((g) => {
        const u = g.userData.criado; let px = u.base.x, py = u.base.y, pz = u.base.z, rx = u.giro.x, ry = u.giro.y, rz = u.giro.z, s = u.esc, vis = true;
        u.anim.forEach((a) => {
          const de = num(a.de, 0, 1, 0), ate = Math.max(de + 0.01, num(a.ate, 0, 1, 1)), q = U.suave((k - de) / (ate - de));
          if (a.mover) { const m = vet(a.mover, -40, 40, [0, 0, 0]); px += m[0] * q; py += m[1] * q; pz += m[2] * q; }
          if (a.girar) { const g2 = vet(a.girar, -20, 20, [0, 0, 0]); rx += g2[0] * q * Math.PI * 2; ry += g2[1] * q * Math.PI * 2; rz += g2[2] * q * Math.PI * 2; }
          if (a.escalar != null) s *= U.lerp(1, num(a.escalar, 0, 30, 1), q);
          if (a.surgir) { s *= U.mola(Math.max(0, k - de) * 3, 10); if (k < de) vis = false; }
          if (a.sumir && k > ate) vis = false;
          if (a.pulsar && k >= de && k <= ate) s *= 1 + 0.08 * Math.sin(t * 9);
        });
        g.position.set(px, py, pz); g.rotation.set(rx, ry, rz); g.scale.setScalar(Math.max(0.0001, s)); g.visible = vis;
      });
    }

    function montar(cn, idx) {
      const sc = new T.Scene(), r = U.rng((spec.semente || 'lp') + ':' + idx);
      const acao = cn.acaoV2, cen = cn.cenario || 'cidade';
      const globo = cen === 'planeta' || cen === 'espaco';
      // hora: a do roteiro, senao a que a acao pede
      const horaPad = { noite_eterna: 'dia', amanhece: 'noite', aurora: 'noite', esquenta: 'quente', estiagem: 'quente', sol_cresce: 'quente', congela: 'frio', chove: 'tempestade', vento: 'tempestade', sem_ar: 'cinza', incendio: 'entardecer', erupcao: 'entardecer' }[acao];
      const hora = globo ? 'espaco' : (cn.hora && CEU[cn.hora] ? cn.hora : horaPad || 'dia');
      sc.background = texturaGradiente(CEU[hora]);
      const o = { sc, cen, acao, globo, hora, gente: [], extras: [], arvores: [], predios: [], carros: [], nuvens: [], peixes: [], fx: {} };
      const hemi = new T.HemisphereLight('#ffffff', '#5a6078', hora === 'noite' ? 0.35 : 0.62); sc.add(hemi); o.hemi = hemi;
      const sol = new T.DirectionalLight(hora === 'entardecer' || hora === 'quente' ? '#FFD2A0' : '#ffffff', hora === 'noite' ? 0.25 : 0.85);
      sol.position.set(8, 14, 9); sc.add(sol); o.sol = sol;
      const recorte=new T.DirectionalLight('#BBD8F5',hora==='noite'?.10:.18);recorte.position.set(-7,5,-8);sc.add(recorte);

      if (globo) {
        const pts = new T.BufferGeometry(), v = [];
        for (let i = 0; i < 1400; i++) { const a = r() * Math.PI * 2, b = Math.acos(2 * r() - 1), d = 120; v.push(d * Math.sin(b) * Math.cos(a), d * Math.cos(b), d * Math.sin(b) * Math.sin(a)); }
        pts.setAttribute('position', new T.Float32BufferAttribute(v, 3)); sc.add(new T.Points(pts, new T.PointsMaterial({ color: '#ffffff', size: 0.45, map: TX_PONTO, transparent: true, depthWrite: false })));
        // terra: icosaedro deslocado pelo ruido; oceano: esfera separada (pode secar)
        const RG = 3, geo = new T.IcosahedronGeometry(RG, 4), p = geo.attributes.position, cores = [];
        const sem = r() * 10, hs = [];
        for (let i = 0; i < p.count; i++) {
          const x = p.getX(i), y = p.getY(i), z = p.getZ(i), h = fbm(x * 0.55 + sem, y * 0.55, z * 0.55) - 0.5; hs.push(h);
          const s = 1 + (h > 0 ? h * 0.16 : h * 0.12); p.setXYZ(i, x * s, y * s, z * s);
        }
        for (let i = 0; i < p.count; i += 3) {
          const h = (hs[i] + hs[i + 1] + hs[i + 2]) / 3, lat = Math.abs((p.getY(i) + p.getY(i + 1) + p.getY(i + 2)) / 3) / RG;
          let col = h > 0.27 ? '#8A8A8A' : h > 0.13 ? '#4E8F4E' : h > 0.03 ? '#5DAA5A' : h > 0 ? '#E8D9A8' : h > -0.12 ? '#C9B88A' : '#9E8A68';
          if (lat > 0.93) col = '#F4F7FA';
          if (h > 0.04 && lat < 0.35 && hash(i, 1, 2) > 0.6) col = '#D9B26F';
          const cc = new T.Color(col); for (let k = 0; k < 3; k++) cores.push(cc.r, cc.g, cc.b);
        }
        geo.setAttribute('color', new T.Float32BufferAttribute(cores, 3)); geo.computeVertexNormals();
        const terra = new T.Mesh(geo, new T.MeshLambertMaterial({  vertexColors: true }));
        const mar = new T.Mesh(new T.IcosahedronGeometry(RG * 1.005, 3), new T.MeshLambertMaterial({  color: '#2F7FD1', transparent: true, opacity: 0.92 }));
        const nuv = new T.Group(); for (let k = 0; k < 9; k++) { const n = nuvem(r); n.scale.set(0.22, 0.09, 0.22); n.children.forEach((q) => { q.material = M('#FFFFFF', { op: 0.85 }); }); const a = r() * Math.PI * 2, b = Math.acos(2 * r() - 1) * 0.8 + 0.3; n.position.set(Math.sin(b) * Math.cos(a), Math.cos(b), Math.sin(b) * Math.sin(a)).multiplyScalar(RG * 1.12); n.lookAt(0, 0, 0); n.rotateX(Math.PI / 2); nuv.add(n); }
        const halo = brilho('rgba(120,180,255,1)', RG * 3.1);
        const g = new T.Group(); g.add(terra); g.add(mar); g.add(nuv); sc.add(halo); sc.add(g);
        g.rotation.z = 0.41; // a inclinacao da Terra
        o.globoG = g; o.terra = terra; o.mar = mar; o.nuvG = nuv; o.halo = halo;
        const lua = new T.Mesh(new T.IcosahedronGeometry(0.75, 1), M('#B9B4AA')); sc.add(lua); o.lua = lua;
        const solS = brilho('rgba(255,230,160,1)', 9); solS.position.set(-26, 10, -30); sc.add(solS); o.solS = solS;
        sol.position.set(-20, 8, 14);
      } else {
        const tr = terreno(cen === 'oceano' ? 'praia' : cen, r); sc.add(tr); o.terreno = tr;
        sc.fog = new T.Fog(new T.Color(CEU[hora][1]), 30, 70);
        const solS = brilho(hora === 'noite' ? 'rgba(220,230,255,1)' : 'rgba(255,240,190,1)', hora === 'noite' ? 3 : 4.5); solS.material.opacity = 0.85; sc.add(solS); o.solS = solS;
        const livre = (x, z) => Math.hypot(x, z - 1) > 2.6 && Math.hypot(x, z) < RAIO - 0.8;
        // 23/10 (dono: "cenarios confusos"): predio, casa e piramide entre a camera e quem age tapavam a cena.
        // A camera anda pelo arco da frente (azimute ~ -0,7..2,1 rad a partir de +z): construcao so' fora dele;
        // arvore na frente so' pequena e na borda.
        const atras = (x, z) => Math.cos(Math.atan2(x, z) - 0.7) < 0.12;
        const livreFundo = (x, z) => livre(x, z) && atras(x, z);
        const livreArvore = (x, z) => livre(x, z) && (atras(x, z) || Math.hypot(x, z) > RAIO - 1.8);
        const sobre = (m, x, z) => { m.position.set(x, tr.userData.alt(x, z), z); sc.add(m); return m; };
        const espalha = (n, fn, ok) => { let k = 0, tent = 0; while (k < n && tent++ < n * 30) { const a = r() * Math.PI * 2, d = 2.8 + r() * (RAIO - 3.6), x = Math.cos(a) * d, z = Math.sin(a) * d; if (!(ok || livreArvore)(x, z)) continue; fn(x, z, k++); } };
        if (cen === 'cidade') {
          espalha(13, (x, z) => { const h = 1.2 + r() * 3.8; const b = sobre(predio(1.0 + r() * 0.5, h, 1.0, ['#E4E1D6', '#C9B79C', '#A8B8C8', '#D9A28B', '#B7C9A8'][Math.floor(r() * 5)], r), x, z); b.rotation.y = Math.atan2(x, z); o.predios.push(b); }, livreFundo);
          for (let i = 0; i < 4; i++) { const k = carro(['#E2574C', '#F2B705', '#3E7CB1', '#5DAA5A'][i]); sc.add(k); o.carros.push(k); }
          espalha(5, (x, z) => o.arvores.push(sobre(arvore('redonda'), x, z)), livreFundo);
        }
        if (cen === 'floresta' || cen === 'campo') espalha(cen === 'campo' ? 8 : 26, (x, z) => { const a = sobre(arvore(r() < 0.5 ? 'pinheiro' : 'redonda'), x, z); a.scale.setScalar(0.8 + r() * 0.6); o.arvores.push(a); });
        if (cen === 'campo') espalha(3, (x, z) => { const c2 = sobre(casa(), x, z); c2.rotation.y = Math.atan2(x, z); o.predios.push(c2); }, livreFundo);
        if (cen === 'polo') { espalha(10, (x, z) => { const a = sobre(arvore('pinheiro', '#E8F2F6'), x, z); o.arvores.push(a); }); espalha(4, (x, z) => { const pg = sobre(pinguim(), x, z); pg.rotation.y = r() * 6; o.extras.push(pg); }); }
        if (cen === 'deserto') { espalha(6, (x, z) => o.arvores.push(sobre(arvore('cacto'), x, z))); const pir = new T.Mesh(new T.ConeGeometry(2.2, 2.6, 4), M('#D9B26F')); sombra(pir, true, true); sobre(pir, 3.5, -4.5).position.y += 1.3; }
        if (cen === 'montanha') espalha(10, (x, z) => o.arvores.push(sobre(arvore('pinheiro'), x, z)));
        if (cen === 'lua') { const terraC = brilho('rgba(110,170,255,1)', 6); terraC.position.set(-6, 14, -18); sc.add(terraC); }
        if (cen === 'vulcao' || acao === 'erupcao') { const v = vulcao(r); v.position.set(0.5, 0, -4.2); if (cen !== 'vulcao') v.scale.setScalar(0.7); sc.add(v); o.vulcao = v; }
        if (cen === 'oceano' || cen === 'praia' || acao === 'inunda' || acao === 'seca' || acao === 'derrete') {
          const nivel0 = cen === 'oceano' || cen === 'praia' || acao === 'seca' ? 0.18 : -0.6;
          const ag = new T.Mesh(new T.CylinderGeometry(RAIO + 0.02, RAIO + 0.02, 4, 48, 1), new T.MeshLambertMaterial({  color: '#3C9BD6', transparent: true, opacity: 0.82 }));
          ag.userData.nivel0 = nivel0; sc.add(ag); o.agua = ag;
          if (cen === 'oceano' || acao === 'seca') { for (let k = 0; k < 5; k++) { const f = peixe(['#F28C38', '#F2B705', '#E46A86'][k % 3]); f.scale.setScalar(1.6); sc.add(f); o.peixes.push(f); } }
          if (cen === 'oceano' && acao !== 'inunda' && acao !== 'seca') { // 23/10: o pier onde a gente fica (antes: em pe dentro da agua)
            const pier = new T.Group(); const tabua = M('#A0703F'), tabua2 = M('#8C5F33');
            for (let k = 0; k < 9; k++) { const tb = new T.Mesh(caixaGeo(4.2, 0.12, 0.34), k % 2 ? tabua : tabua2); tb.position.set(0, 0.42, -0.2 + k * 0.36); pier.add(tb); }
            [[-1.9, -0.2], [1.9, -0.2], [-1.9, 2.7], [1.9, 2.7]].forEach(([x, z]) => { const st = new T.Mesh(new T.CylinderGeometry(0.1, 0.1, 1.2, 6), tabua2); st.position.set(x, 0.0, z); pier.add(st); });
            sombra(pier); sc.add(pier); o.pier = pier;
          }
          if (cen === 'oceano') { // um barquinho
            const b = new T.Group(); const casco = new T.Mesh(caixaGeo(1.4, 0.35, 0.6), M('#C8553D')); b.add(casco); const v2 = new T.Mesh(new T.ConeGeometry(0.45, 1.1, 3), M('#FFFFFF')); v2.position.y = 0.7; b.add(v2); sombra(b); sc.add(b); o.barco = b;
          }
        }
        for (let k = 0; k < 4; k++) { const n = nuvem(r, hora === 'tempestade' || hora === 'cinza' ? '#9AA3B0' : '#FFFFFF'); n.userData = { a: r() * 6.28, h: 7 + r() * 3, d: 5 + r() * 4 }; sc.add(n); o.nuvens.push(n); }
        // gente: 1 protagonista no centro + figurantes; multidao = 14
        const n = acao === 'multidao' || acao === 'sem_ar' || acao === 'corre' ? 12 : Math.max(1, (cn.atores || ['pessoa']).length) + (cen === 'cidade' ? 2 : 1);
        for (let i = 0; i < Math.min(14, n); i++) {
          const p = pessoa(r, i);
          if (i === 0) p.position.set(0, 0, 1.6);
          else {
            // atras e dos lados (a camera vem da frente) e a 1 m de qualquer outro: nada de gente na frente do protagonista
            let x = 0, z = 0;
            for (let tent = 0; tent < 40; tent++) { const a = Math.PI * (0.95 + r() * 1.1), d = 1.3 + r() * (n > 6 ? 2.8 : 2.0); x = Math.cos(a) * d; z = 1.2 + Math.sin(a) * d * 0.75;
              if (o.gente.every((q) => Math.hypot(q.position.x - x, q.position.z - z) > 1.0)) break; }
            p.position.set(x, 0, z); p.rotation.y = Math.atan2(-x, 6 - z) * 0.6 + (r() - 0.5) * 0.5; p.scale.setScalar(0.85);
          }
          p.userData.x0 = p.position.x; p.userData.z0 = p.position.z; p.userData.y0 = tr.userData.alt(p.position.x, p.position.z);
          if (o.pier) { p.userData.y0 = 0.48; p.userData.x0 = U.clamp(p.position.x, -1.8, 1.8); p.userData.z0 = U.clamp(p.position.z, -0.2, 2.7); }
          sc.add(p); o.gente.push(p);
        }
        if (acao === 'chove') o.gente.slice(0, 2).forEach((p) => { const gc = guardaChuva(['#E2574C', '#3E7CB1'][o.gente.indexOf(p) % 2]); gc.position.set(0.55, -0.2, 0); p.userData.corpo.add(gc); });
        if (acao === 'congela') o.gelos = o.gente.map((p) => { const gg = gelo(); gg.visible = false; p.add(gg); return gg; });
      }
      // efeitos por acao (particulas)
      const fx = o.fx;
      if (acao === 'chove' || acao === 'vento' || acao === 'chuva_meteoros') fx.chuva = riscos(acao === 'chove' ? 520 : 160, acao === 'chuva_meteoros' ? '#FFB24A' : '#CFE6FF', acao === 'chove' ? 0.55 : 0.6);
      if (acao === 'congela' || (hora === 'frio' && !globo)) fx.neve = particulas(360, '#FFFFFF', 0.22, 0.95);
      if (acao === 'erupcao' || acao === 'incendio') { fx.brasas = particulas(260, '#FF7A2A', 0.3, 1); fx.fumaca = particulas(160, '#4A4A4A', 1.6, 0.55); }
      if (acao === 'sem_ar' || acao === 'estiagem') fx.poeira = particulas(220, '#C9B79C', 0.5, 0.5);
      if (acao === 'gravidade_zero') fx.flutua = particulas(80, '#7CC7FF', 0.35, 0.9);
      if (acao === 'aurora' || acao === 'noite_eterna') fx.estrelas = particulas(300, '#FFFFFF', 0.25, 0);
      if (acao === 'explode') { const b = new T.Mesh(new T.IcosahedronGeometry(1, 1), new T.MeshBasicMaterial({ color: '#FFB347', transparent: true, opacity: 0 })); b.position.set(0, 2, -5.5); b.add(brilho('rgba(255,170,60,1)', 5)); sc.add(b); fx.bola = b; }
      if (acao === 'explode' || acao === 'impacto') { const onda = new T.Mesh(new T.RingGeometry(0.8, 1.4, 48), new T.MeshBasicMaterial({ color: '#FFF3C4', transparent: true, opacity: 0, side: T.DoubleSide, depthWrite: false })); onda.rotation.x = -Math.PI / 2; sc.add(onda); fx.onda = onda; }
      if (acao === 'impacto' || acao === 'chuva_meteoros') {
        o.rochas = []; const nr = acao === 'impacto' ? 1 : 9;
        for (let k = 0; k < nr; k++) { const m = new T.Mesh(new T.IcosahedronGeometry(acao === 'impacto' ? (globo ? 0.6 : 1.0) : 0.3 + r() * 0.25, 0), M('#7A6A5E', { emis: '#3A1500' })); const b = brilho('rgba(255,140,40,1)', acao === 'impacto' ? 4 : 1.6); m.add(b); m.userData = { x: (r() - 0.5) * 12, z: (r() - 0.5) * 8 - 1, fase: r() }; sc.add(m); o.rochas.push(m); }
      }
      if (acao === 'aurora') { o.auroras = []; for (let k = 0; k < 3; k++) { const pl = new T.Mesh(new T.PlaneGeometry(26, 3.2, 24, 1), new T.MeshBasicMaterial({ color: ['#4CFFB0', '#5CC8FF', '#B07CFF'][k], transparent: true, opacity: 0, side: T.DoubleSide, depthWrite: false, blending: T.AdditiveBlending })); pl.position.set(0, 13 + k * 1.2, -14 - k * 2); pl.userData.base = pl.geometry.attributes.position.array.slice(); sc.add(pl); o.auroras.push(pl); } }
      if (acao === 'lua_perto' && !globo) { const lu = new T.Mesh(new T.IcosahedronGeometry(3.2, 2), M('#CFCAC0')); lu.position.set(-5, 16, -26); sc.add(lu); o.luaGrande = lu; }
      if (!globo && (acao === 'compara' || acao === 'cresce' || acao === 'encolhe')) {
        // a regua de altura ao lado de quem cresce: a escala precisa de referencia
        const regua = new T.Group(); for (let k = 0; k < 10; k++) { const s = new T.Mesh(caixaGeo(0.18, 0.5, 0.18), M(k % 2 ? '#1B1B1B' : '#FFD23F')); s.position.y = 0.25 + k * 0.5; regua.add(s); }
        regua.position.set(1.6, 0, 1.4); sc.add(regua); o.regua = regua;
      }
      Object.values(fx).forEach((f) => { if (f.isPoints || f.isLineSegments) sc.add(f); });
      montarCriados(cn, idx, o, r);
      facetar(sc);
      return o;
    }

    spec.cenas.forEach((cn, i) => { cn.acaoV2 = acaoCoerente(cn, i); cn.hudV2 = hudDaCena(cn); cn.tempoV2 = tempoDaCena(cn); });
    const cenas = spec.cenas.map(montar);

    // MODO de quem age, pela acao (o protagonista) e de quem assiste (figurantes)
    const MODO = {
      anda: ['anda', 'parado'], corre: ['corre', 'corre'], para_de_girar: ['surpreso', 'medo'], congela: ['frio', 'frio'], esquenta: ['calor', 'calor'],
      inunda: ['nada', 'nada'], cresce: ['surpreso', 'olha_cima'], encolhe: ['surpreso', 'aponta'], tremor: ['medo', 'medo'], chuva_meteoros: ['corre', 'corre'],
      noite_eterna: ['olha_cima', 'olha_cima'], gravidade_zero: ['flutua', 'flutua'], multidao: ['anda', 'anda'], seca: ['aponta', 'olha_cima'],
      chove: ['parado', 'corre'], estiagem: ['calor', 'calor'], erupcao: ['aponta', 'corre'], impacto: ['olha_cima', 'medo'], vento: ['medo', 'medo'],
      incendio: ['medo', 'corre'], derrete: ['calor', 'aponta'], sem_ar: ['sufoca', 'sufoca'], murcha: ['calor', 'parado'], brota: ['comemora', 'comemora'],
      mostra: ['aponta', 'parado'], compara: ['aponta', 'olha_cima'], explode: ['medo', 'medo'], aurora: ['olha_cima', 'comemora'], amanhece: ['comemora', 'comemora'],
      lua_perto: ['olha_cima', 'aponta'], sol_cresce: ['calor', 'olha_cima'], orbita: ['parado', 'parado'],
    };

    // NO CEU, NO QUADRO: sol, lua grande, aurora e o asteroide vem de onde a
    // camera esta olhando (a camera gira; um astro com posicao fixa saia do
    // quadro em metade das cenas). `lado` -1..1, `alto` 0..1 da tela.
    // (com o "para cima" DA CAMERA: a camera aerea olha para baixo, e um
    // "para cima" do mundo jogava a aurora para fora do quadro)
    const _v = new T.Vector3(), _f = new T.Vector3(), _d = new T.Vector3(), _u = new T.Vector3();
    function noCeu(obj, lado, alto, dist) {
      cam.updateMatrixWorld(); cam.getWorldDirection(_f); _u.set(0, 1, 0).applyQuaternion(cam.quaternion); _d.crossVectors(_f, _u).normalize();
      _v.copy(cam.position).addScaledVector(_f, dist).addScaledVector(_d, lado * dist * 0.17).addScaledVector(_u, alto * dist * 0.3);
      obj.position.copy(_v); return obj;
    }
    // ------------------------------------------------------------ desenho 3D
    function pose3D(o, cn, t, k, local) {
      const acao = o.acao, D = Math.max(0.01, cn.fim - cn.ini);
      // ---- camera
      const cam0 = cn.camera || (o.globo ? 'orbita' : 'orbita');
      let ang = 0.5 * Math.sin(t * 0.21) + k * 0.55, dist = o.globo ? 15.5 : 21, alt = o.globo ? 2 : 9.5, alvoY = o.globo ? 0 : 1.6;
      if (cam0 === 'orbita') ang += k * 0.9;
      if (cam0 === 'zoom_in') dist *= U.lerp(1.12, 0.62, U.suave(k));
      if (cam0 === 'zoom_out') dist *= U.lerp(0.62, 1.1, U.suave(k));
      if (cam0 === 'sobrevoo') { alt = o.globo ? 9 : 16; dist *= 0.72; }
      if (cam0 === 'perto') { dist *= o.globo ? 0.7 : 0.55; alt *= o.globo ? 1 : 0.42; alvoY = o.globo ? 0 : 1.7; ang = 0.25 * Math.sin(t * 0.3); }
      if (!o.globo && (acao === 'cresce') ) alvoY += U.saida(k) * 2.5;
      if (!o.globo && (acao === 'noite_eterna' || acao === 'aurora' || acao === 'lua_perto' || acao === 'impacto' || acao === 'chuva_meteoros' || acao === 'sol_cresce')) { alt *= 0.55; alvoY = 4 + 2 * U.suave(k); }
      // empurrao de entrada: a cena chega 10% mais perto e assenta (substitui o flash)
      dist *= 1 - 0.1 * (1 - U.saida(U.clamp(local / 0.5, 0, 1)));
      const foco = !o.globo && cam0 === 'perto' ? 1.6 : 0;
      cam.position.set(Math.sin(ang) * dist, alt, Math.cos(ang) * dist + foco); cam.lookAt(0, alvoY, foco);
      const sacode = acao === 'tremor' ? 0.35 : acao === 'erupcao' ? 0.18 * U.suave(k) : acao === 'explode' || acao === 'impacto' ? (k > 0.55 && k < 0.8 ? 0.6 * (1 - (k - 0.55) / 0.25) : 0) : acao === 'para_de_girar' && k > 0.3 && k < 0.65 ? 0.25 : 0;
      if (sacode) { const rr = U.rng(Math.floor(t * 30)); cam.position.x += (rr() - 0.5) * sacode; cam.position.y += (rr() - 0.5) * sacode * 0.7; }
      // ---- sol / ceu
      if (o.solS && !o.globo) {
        let sa = 0.9; // altura do sol (0 = horizonte)
        if (acao === 'noite_eterna') sa = U.lerp(0.9, -0.4, U.suave(k * 1.3));
        if (acao === 'amanhece') sa = U.lerp(-0.4, 0.9, U.suave(k * 1.3));
        noCeu(o.solS, -0.45, U.clamp(0.25 + sa * 0.55, -0.2, 0.9), 34);
        if (acao === 'sol_cresce') o.solS.scale.setScalar(4.5 + U.saida(k) * 22);
        const luz = U.clamp(sa + 0.35, 0.08, 1);
        if (acao === 'noite_eterna' || acao === 'amanhece') {
          o.sol.intensity = 0.85 * luz; o.hemi.intensity = 0.2 + 0.45 * luz;
          const c0 = new T.Color(CEU.noite[0]).lerp(new T.Color(CEU.dia[0]), luz), c1 = new T.Color(CEU.noite[1]).lerp(new T.Color(CEU.dia[1]), luz);
          o.sc.background = o.sc.background && o.sc.background.isColor ? o.sc.background.copy(c0) : c0.clone(); if (o.sc.fog) o.sc.fog.color.copy(c1);
          // predio criado pela IA nao tem janelas proprias (23/10: 3 renders do MINI QUE PASARIA cairam aqui)
          o.predios.forEach((b) => (b.userData.janelas || []).forEach((j) => { const m = luz < 0.45 ? b.userData.matNoite : b.userData.matDia; if (m) j.material = m; }));
        }
        if (o.fx.estrelas) { o.fx.estrelas.material.opacity = acao === 'aurora' ? 0.9 : U.clamp(1 - luz * 1.6, 0, 1); }
      }
      if (o.fx.estrelas && !o.fx.estrelas.userData.ok) { const a = o.fx.estrelas.geometry.attributes.position, rr = U.rng(99); for (let j = 0; j < a.count; j++) { const th = rr() * Math.PI * 2, ph = rr() * 1.2; a.setXYZ(j, Math.cos(th) * 40 * Math.cos(ph), 8 + Math.sin(ph) * 30, Math.sin(th) * 40 * Math.cos(ph) - 10); } a.needsUpdate = true; o.fx.estrelas.userData.ok = 1; }
      // ---- globo
      if (o.globo) {
        // angulo = INTEGRAL da velocidade (frear multiplicando o angulo faria o globo girar para tras)
        const vel = (s) => (acao === 'para_de_girar' ? 1 - U.saida(U.clamp((s / D) * 1.5, 0, 1)) : 1);
        let a = 0; const n = 40; for (let j = 0; j < n; j++) a += vel(((j + 0.5) / n) * local) * (local / n);
        o.globoG.rotation.y = cn.ini * 0.35 + a * 0.6;
        o.nuvG.rotation.y = a * 0.15 + t * 0.04;
        o.lua.position.set(Math.cos(t * 0.35 + 1) * 7.5, Math.sin(t * 0.35 + 1) * 1.4, Math.sin(t * 0.35 + 1) * 7.5);
        if (acao === 'lua_perto') { const q = U.suave(k); o.lua.position.multiplyScalar(U.lerp(1, 0.55, q)); o.lua.scale.setScalar(U.lerp(1, 2.2, q)); }
        if (acao === 'seca') { o.mar.scale.setScalar(U.lerp(1.0, 0.9, U.suave(k * 1.2))); o.mar.material.opacity = U.lerp(0.92, 0.65, k); }
        if (acao === 'inunda' || acao === 'derrete') o.mar.scale.setScalar(U.lerp(1.0, 1.045, U.suave(k)));
        if (acao === 'congela') o.mar.material.color.set(new T.Color('#2F7FD1').lerp(new T.Color('#DDF2FF'), U.suave(k)));
        if (acao === 'esquenta' || acao === 'sol_cresce' || acao === 'estiagem') { o.terra.material.color = new T.Color('#ffffff').lerp(new T.Color('#FFB27A'), U.suave(k) * 0.6); o.mar.material.color.set(new T.Color('#2F7FD1').lerp(new T.Color('#5A8FB0'), U.suave(k))); }
        if (acao === 'noite_eterna') o.sol.intensity = U.lerp(0.85, 0.05, U.suave(k));
        if (o.rochas && acao === 'impacto') { const m = o.rochas[0], q = U.clamp(k / 0.6, 0, 1); m.visible = q < 1; m.position.set(U.lerp(-14, 0, q) * 1.0, U.lerp(8, 1.6, q), U.lerp(-6, 2.6, q)); }
        o.halo.material.opacity = 0.75;
      }
      // ---- agua
      if (o.agua) {
        const n0 = o.agua.userData.nivel0;
        let nivel = n0 + Math.sin(t * 1.4) * 0.04;
        if (acao === 'inunda') nivel = U.lerp(-0.6, 2.4, U.suave(k));
        if (acao === 'seca') nivel = U.lerp(1.3, -2.2, U.suave(U.clamp((k - 0.08) * 1.25, 0, 1)));
        if (acao === 'derrete') nivel = U.lerp(-0.6, 1.1, U.suave(k));
        o.agua.position.y = nivel - 2; o.agua.userData.nivel = nivel;
        o.agua.material.color.set(acao === 'congela' ? new T.Color('#3C9BD6').lerp(new T.Color('#E6F6FF'), U.suave(k)) : '#3C9BD6');
        o.peixes.forEach((f, j) => {
          const a = t * 0.6 + j * 1.3, d = 3 + j * 0.8;
          if (acao === 'seca' && nivel < -0.2) { // no seco: o peixe se debate no chao
            f.position.set(Math.cos(j * 1.3) * d, (o.terreno ? o.terreno.userData.alt(Math.cos(j * 1.3) * d, Math.sin(j * 1.3) * d) : 0) + 0.15 + Math.abs(Math.sin(t * 9 + j)) * 0.25, Math.sin(j * 1.3) * d);
            f.rotation.set(Math.sin(t * 12 + j) * 0.6, j, Math.PI / 2);
          } else { f.position.set(Math.cos(a) * d, Math.min(nivel - 0.35, -0.1), Math.sin(a) * d); f.rotation.set(0, -a, 0); }
        });
        if (o.barco) { const by = Math.max(nivel, (o.terreno ? -0.2 : 0)) + 0.18; o.barco.position.set(4.5, acao === 'seca' ? Math.max(by, -1.2) : by, -2); o.barco.rotation.z = acao === 'seca' && nivel < -1 ? 0.4 : Math.sin(t * 1.6) * 0.08; }
      }
      // ---- vulcao
      if (o.vulcao) { const ativo = acao === 'erupcao' ? U.suave(k * 1.5) : acao === 'tremor' ? 0.3 : 0.1; o.vulcao.userData.lava.scale.set(1, 1 + ativo * 3, 1); o.vulcao.userData.lava.material.emissive.set(new T.Color('#FF4A00').multiplyScalar(0.6 + 0.4 * Math.sin(t * 6) * ativo)); }
      // ---- natureza
      const morre = acao === 'murcha' || acao === 'estiagem' || (acao === 'esquenta' && k > 0.3) ? U.suave(acao === 'esquenta' ? (k - 0.3) / 0.7 : k) : acao === 'brota' ? 1 - U.suave(k) : 0;
      const vento = acao === 'vento' ? 0.35 + 0.2 * Math.sin(t * 7) : 0;
      o.arvores.forEach((a, j) => {
        a.rotation.z = vento * (1 + (j % 3) * 0.2) + (morre * 0.35 * ((j % 2) ? 1 : -1));
        a.userData.copa.forEach((q) => { if (!q.userData.c0) q.userData.c0 = q.material.color.clone(); if (morre > 0 || acao === 'incendio' || acao === 'congela') { q.material = q.material.userData && q.material.userData.unico ? q.material : M(q.userData.c0.getStyle(), { unico: true }); q.material.userData = { unico: 1 };
          const alvo = acao === 'congela' ? new T.Color('#EAF6FF') : acao === 'incendio' ? new T.Color('#3A2A22') : new T.Color('#8A6A3A');
          q.material.color.copy(q.userData.c0).lerp(alvo, acao === 'incendio' ? U.suave(k * 1.3) : acao === 'congela' ? U.suave(k) : morre); } });
        if (acao === 'derrete') a.scale.set(1, U.lerp(1, 0.35, U.suave(k)), 1);
        if (acao === 'brota' || acao === 'cresce' && j % 2) a.scale.setScalar(U.lerp(acao === 'brota' ? 0.3 : 1, 1, U.saida(k)) * (0.8 + (j % 5) * 0.12));
      });
      if (o.terreno && (acao === 'congela' || acao === 'estiagem' || acao === 'esquenta' || acao === 'incendio' || acao === 'brota')) {
        const tp = o.terreno.userData.topo; if (!tp.userData.c0) { tp.userData.c0 = tp.geometry.attributes.color.array.slice(); }
        const alvo = { congela: [0.92, 0.96, 1], estiagem: [0.78, 0.6, 0.38], esquenta: [0.85, 0.62, 0.36], incendio: [0.25, 0.2, 0.18], brota: [0.36, 0.72, 0.35] }[acao];
        const q = acao === 'brota' ? U.suave(k) : U.suave(k * 1.2), a = tp.geometry.attributes.color, c0 = tp.userData.c0;
        for (let j = 0; j < a.array.length; j++) a.array[j] = c0[j] + (alvo[j % 3] - c0[j]) * q * 0.85;
        a.needsUpdate = true;
      }
      o.carros.forEach((m, j) => { const a = (t * 0.25 + j / 4) * Math.PI * 2 * (acao === 'para_de_girar' ? 0.3 : 1), d = RAIO - 1.4; m.position.set(Math.cos(a) * d, (o.terreno ? o.terreno.userData.alt(Math.cos(a) * d, Math.sin(a) * d) : 0) + (acao === 'gravidade_zero' ? U.saida(k) * (2 + j) : 0), Math.sin(a) * d); m.rotation.y = -a; if (acao === 'inunda' && o.agua) m.position.y = Math.max(m.position.y, o.agua.userData.nivel - 0.1); });
      o.nuvens.forEach((n, j) => { const u = n.userData, a = u.a + t * (acao === 'vento' ? 0.6 : 0.05); n.position.set(Math.cos(a) * u.d, u.h, Math.sin(a) * u.d - 2); n.visible = (acao !== 'estiagem' || k < 0.4 + j * 0.1) && cam0 !== 'sobrevoo' && o.hora !== 'noite' && acao !== 'aurora' && acao !== 'noite_eterna'; });
      // ---- pessoas
      const [mh, mf] = MODO[acao] || ['parado', 'parado'];
      o.gente.forEach((p, j) => {
        const u = p.userData, modo = j === 0 ? mh : mf;
        posar(p, modo, t, k);
        let y = u.y0 || 0, x = u.x0, z = u.z0;
        if (modo === 'anda' || modo === 'corre') {
          // andar EM VOLTA da praca: quem anda nao atravessa o mundo nem sai do quadro
          const vel = modo === 'corre' ? 0.55 : 0.22, a = local * vel + j * 0.9, d = j === 0 ? 1.8 : 2.2 + (j % 4) * 0.7;
          x = Math.cos(a) * d; z = 1 + Math.sin(a) * d * 0.7; p.rotation.y = -a + (modo === 'corre' ? 0 : 0);
          p.rotation.y = Math.atan2(-Math.sin(a) * d, Math.cos(a) * d * 0.7);
          y = o.terreno ? o.terreno.userData.alt(x, z) : 0;
        } else if (j === 0) p.rotation.y = 0.15 * Math.sin(t * 0.4);
        if (acao === 'cresce' && j === 0) p.scale.setScalar(U.lerp(1, 3.2, U.saida(k)));
        if (acao === 'encolhe' && j === 0) p.scale.setScalar(U.lerp(1, 0.22, U.saida(k)));
        if (acao === 'gravidade_zero') { y += U.saida(k) * (2.2 + j * 0.5); p.rotation.x = t * 0.4 * (j % 2 ? 1 : -1); p.rotation.z = t * 0.25; }
        if (acao === 'para_de_girar' && k > 0.3) { x += (k - 0.3) * 3.2; p.rotation.z = -0.6 * U.saida((k - 0.3) / 0.7); }
        if (acao === 'vento') { x += Math.sin(t * 3 + j) * 0.05 + 0.25; p.rotation.z = -0.25; }
        if (acao === 'inunda' && o.agua) y = Math.max(y, o.agua.userData.nivel - 1.4);
        if (acao === 'impacto' && k > 0.6) { p.rotation.x = -U.saida((k - 0.6) / 0.2) * 1.3; }
        p.position.set(x, y, z);
      });
      if (o.gelos) o.gelos.forEach((g, j) => { const q = U.clamp((k - 0.55 - j * 0.02) / 0.2, 0, 1); g.visible = q > 0; g.scale.set(1, q, 1); g.position.y = 1.45 * q; });
      if (o.regua) { o.regua.visible = true; o.regua.position.x = 1.6 + (acao === 'cresce' ? U.saida(k) * 1.6 : 0); }
      if (o.luaGrande) { const q = U.suave(k); noCeu(o.luaGrande, 0.35, 0.55 - q * 0.1, 52 - q * 12); o.luaGrande.scale.setScalar(1 + q * 0.9); }
      if (o.auroras) o.auroras.forEach((pl, j) => { noCeu(pl, 0, 0.55 + j * 0.08, 26 + j * 3); pl.lookAt(cam.position.x, pl.position.y, cam.position.z); pl.material.opacity = 0.32 * U.suave(k * 2); const a = pl.geometry.attributes.position, b = pl.userData.base; for (let q = 0; q < a.count; q++) a.setZ(q, b[q * 3 + 2] + Math.sin(b[q * 3] * 0.35 + t * (0.8 + j * 0.3)) * 1.6); a.needsUpdate = true; });
      // ---- particulas (posicao = funcao de t)
      const fx = o.fx, rr = U.rng(17);
      if (fx.chuva) {
        const a = fx.chuva.geometry.attributes.position, met = acao === 'chuva_meteoros', ven = acao === 'vento';
        for (let j = 0; j < a.count / 2; j++) {
          const x0 = (rr() - 0.5) * 22, z0 = (rr() - 0.5) * 16 - 1, fase = rr(), vel = met ? 0.35 : ven ? 1.6 : 1.8;
          const q = ((local * vel + fase) % 1), y = 16 - q * 17;
          const dx = met ? 2.2 : ven ? 1.6 : 0.12, dy = met ? -2.0 : ven ? -0.2 : -0.7;
          const xx = x0 + (met ? (1 - q) * 9 : ven ? q * 14 - 7 : 0);
          a.setXYZ(j * 2, xx, y, z0); a.setXYZ(j * 2 + 1, xx - dx, y - dy, z0);
        }
        a.needsUpdate = true; fx.chuva.visible = !(acao === 'chove' && false);
      }
      if (o.rochas && acao === 'chuva_meteoros') o.rochas.forEach((m) => { const d = m.userData, q = (local * 0.45 + d.fase) % 1; m.position.set(d.x + 9 * (1 - q), 15 * (1 - q) + 0.2, d.z); m.rotation.x = q * 6; });
      if (o.rochas && acao === 'impacto' && !o.globo) { const m = o.rochas[0], q = U.clamp(k / 0.6, 0, 1); m.visible = q < 1; noCeu(m, -0.5, 0.75, 34); const x0 = m.position.clone(); m.position.lerpVectors(x0, new T.Vector3(0, 0.5, -1), U.entrada(q)); m.rotation.set(q * 5, q * 3, 0); }
      if (fx.onda) { const q = U.clamp((k - 0.6) / 0.35, 0, 1); fx.onda.scale.setScalar(0.5 + q * (o.globo ? 4 : 9)); fx.onda.material.opacity = q > 0 ? 0.9 * (1 - q) : 0; fx.onda.position.y = o.globo ? 0 : 0.3; if (o.globo) { fx.onda.position.set(0, 1.3, 2.75); fx.onda.lookAt(0, 2.6, 5.5); fx.onda.scale.setScalar(0.2 + q * 1.6); } }
      if (fx.bola) { const q = U.clamp((k - 0.5) / 0.3, 0, 1); fx.bola.visible = q > 0; fx.bola.scale.setScalar(0.2 + U.saida(q) * 3); fx.bola.material.opacity = q > 0 ? 0.95 * (1 - U.suave(U.clamp((k - 0.75) / 0.25, 0, 1))) : 0; fx.bola.material.color.set(new T.Color('#FFF1B0').lerp(new T.Color('#E2572C'), q)); }
      if (fx.neve) { const a = fx.neve.geometry.attributes.position; for (let j = 0; j < a.count; j++) { const x0 = (rr() - 0.5) * 22, z0 = (rr() - 0.5) * 16, f = rr(), q = (local * 0.12 + f) % 1; a.setXYZ(j, x0 + Math.sin(t + j) * 0.4, 13 - q * 14, z0); } a.needsUpdate = true; fx.neve.material.opacity = acao === 'congela' ? U.clamp(k * 3, 0, 0.95) : 0.8; }
      if (fx.brasas) {
        const v0 = o.vulcao ? o.vulcao.position : new T.Vector3(0, 0, 0), topo = o.vulcao ? 4.2 * o.vulcao.scale.y : 1.5, a = fx.brasas.geometry.attributes.position, b = fx.fumaca.geometry.attributes.position, forca = acao === 'erupcao' ? U.suave(k * 1.6) : 0.8;
        for (let j = 0; j < a.count; j++) {
          const f = rr(), th = rr() * 6.28, vv = 2.5 + rr() * 4, q = (local * 0.7 + f) % 1;
          if (acao === 'incendio') { const ar = o.arvores[j % Math.max(1, o.arvores.length)]; const px = ar ? ar.position.x : (rr() - 0.5) * 10, pz = ar ? ar.position.z : (rr() - 0.5) * 8; a.setXYZ(j, px + Math.sin(th) * 0.4, (ar ? ar.position.y : 0) + 0.8 + q * 2.4, pz + Math.cos(th) * 0.3); }
          else a.setXYZ(j, v0.x + Math.cos(th) * q * vv * 0.6 * forca, v0.y + topo + (vv * q - 4.9 * q * q * 1.1) * 2 * forca, v0.z + Math.sin(th) * q * vv * 0.6 * forca);
        }
        for (let j = 0; j < b.count; j++) { const f = rr(), q = (local * 0.18 + f) % 1, th = rr() * 6.28; const bx = acao === 'incendio' ? (rr() - 0.5) * 10 : v0.x, bz = acao === 'incendio' ? (rr() - 0.5) * 8 : v0.z; b.setXYZ(j, bx + Math.cos(th) * q * 3 + q * 2, (acao === 'incendio' ? 1.5 : v0.y + topo) + q * 9 * (acao === 'erupcao' ? forca : 1), bz + Math.sin(th) * q * 2); }
        a.needsUpdate = true; b.needsUpdate = true; fx.fumaca.material.opacity = 0.5 * (acao === 'erupcao' ? forca : 1);
      }
      if (fx.poeira) { const a = fx.poeira.geometry.attributes.position; for (let j = 0; j < a.count; j++) { const x0 = (rr() - 0.5) * 20, y0 = rr() * 8, z0 = (rr() - 0.5) * 14; a.setXYZ(j, ((x0 + local * 1.2 + 10) % 20) - 10, y0 + Math.sin(t + j) * 0.3, z0); } a.needsUpdate = true; fx.poeira.material.opacity = 0.55 * U.suave(k * 2); }
      if (fx.flutua) { const a = fx.flutua.geometry.attributes.position; for (let j = 0; j < a.count; j++) { const x0 = (rr() - 0.5) * 12, z0 = (rr() - 0.5) * 10, f = rr(); a.setXYZ(j, x0 + Math.sin(t * 0.5 + j) * 0.5, U.saida(k) * (1 + f * 6) + 0.2, z0); } a.needsUpdate = true; }
      animarCriados(o, k, t);
      // a ultima coisa do 3D: o desenho
      U3.render(R, o.sc, cam, spec, t);
    }

    // --------------------------------------------------- camada 2D por cima
    // a vinheta e' a mesma em todo quadro: gradiente de tela cheia recalculado
    // custava ~170 ms por quadro
    const VINHETA = document.createElement('canvas'); VINHETA.width = W; VINHETA.height = H;
    { const g = VINHETA.getContext('2d'), v = g.createRadialGradient(W / 2, H * 0.45, H * 0.3, W / 2, H * 0.45, H * 0.75); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.32)'); g.fillStyle = v; g.fillRect(0, 0, W, H); }
    function tinta(o, k) {
      const a = o.acao;
      const cor = { congela: [150, 210, 255, 0.28], esquenta: [255, 110, 30, 0.22], estiagem: [255, 160, 60, 0.16], sem_ar: [120, 110, 90, 0.3], incendio: [255, 90, 20, 0.16], sol_cresce: [255, 60, 20, 0.3] }[a];
      if (cor) { c.fillStyle = 'rgba(' + cor[0] + ',' + cor[1] + ',' + cor[2] + ',' + (cor[3] * U.suave(k)).toFixed(3) + ')'; c.fillRect(0, 0, W, H); }
      // geada nas bordas
      if (a === 'congela' && k > 0.25) { const q = U.suave((k - 0.25) / 0.75), g = c.createRadialGradient(W / 2, H / 2, H * 0.25, W / 2, H / 2, H * 0.62); g.addColorStop(0, 'rgba(255,255,255,0)'); g.addColorStop(1, 'rgba(235,248,255,' + (0.75 * q).toFixed(3) + ')'); c.fillStyle = g; c.fillRect(0, 0, W, H); }
      // ar tremendo de calor: faixas que ondulam
      if ((a === 'esquenta' || a === 'estiagem' || a === 'sol_cresce') && k > 0.2) { c.save(); c.globalAlpha = 0.12 * U.suave(k); c.fillStyle = '#FFE0B0'; for (let j = 0; j < 9; j++) { const y = H * 0.25 + j * 110 + Math.sin(k * 20 + j) * 14; c.fillRect(0, y, W, 6); } c.restore(); }
      // clarao do impacto / explosao
      if ((a === 'impacto' || a === 'explode') && k > 0.58 && k < 0.85) { const q = 1 - (k - 0.58) / 0.27; c.fillStyle = 'rgba(255,248,220,' + (0.85 * q * q).toFixed(3) + ')'; c.fillRect(0, 0, W, H); }
      // vinheta (todo quadro): segura o olho no centro
      c.drawImage(VINHETA, 0, 0);
    }
    // O CARTAO DO NUMERO: conta de 0 ate o valor em 0,7 s, com mola na entrada.
    function cartaoNumero(cn, t) {
      const txt = cn.hudV2; if (!txt) return;
      const local = t - cn.ini, ent = U.mola(local - 0.25, 10); if (local < 0.25) return;
      let mostra = txt; const m = txt.match(/^(-?)([\d,.]*\d)(.*)$/);
      if (m) { const alvo = parseFloat(m[2].replace(/,/g, '')); const dec = (m[2].split('.')[1] || '').length; const q = U.saida(U.clamp((local - 0.25) / 0.7, 0, 1)); let v = (alvo * q).toFixed(dec); if (m[2].indexOf(',') >= 0) v = Number(v).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }); mostra = m[1] + v + m[3]; }
      const y = cn.ini < 3.2 ? 520 : 330; // na cena 1 o cartaz do titulo ocupa o alto
      c.save(); c.translate(W / 2, y); c.scale(ent, ent); c.rotate(-0.03);
      c.font = '150px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
      const w = Math.min(W * 0.9, c.measureText(mostra).width + 90);
      U.rr(c, -w / 2, -95, w, 190, 40); c.fillStyle = '#1B1B1B'; c.fill(); U.rr(c, -w / 2 + 10, -85, w - 20, 170, 32); c.fillStyle = '#FFD23F'; c.fill();
      c.fillStyle = '#1B1B1B'; c.fillText(mostra, 0, 6, w - 50);
      c.restore();
    }
    function seloTempo(cn, t) {
      const txt = cn.tempoV2; if (!txt) return;
      const local = t - cn.ini; if (local < 0.05) return;
      const ent = U.saida(U.clamp(local / 0.35, 0, 1));
      c.save(); c.font = '58px "Lilita One", sans-serif'; c.textAlign = 'left'; c.textBaseline = 'middle';
      const w = c.measureText(txt).width + 60, x = -w + ent * (w + 50), y = cn.ini < 3.2 ? 380 : 190;
      U.rr(c, x, y - 45, w, 90, 45); c.fillStyle = 'rgba(27,27,27,0.85)'; c.fill();
      c.fillStyle = '#FFFFFF'; c.fillText(txt, x + 30, y + 3);
      c.restore();
    }

    // ---------------------------------------------------------------- quadro
    function quadro(t) {
      const { c: cn, i, k, local } = U.cenaEm(spec, t);
      pose3D(cenas[i], cn, t, k, local);
      c.globalAlpha = 1; c.drawImage(gl, 0, 0, W, H);
      // passagem: os primeiros 0,25 s dissolvem a partir do fim da cena anterior
      const PASSA = 0.25;
      if (i > 0 && local < PASSA) {
        const ant = spec.cenas[i - 1], ka = 1;
        pose3D(cenas[i - 1], ant, t, ka, t - ant.ini);
        c.globalAlpha = 1 - U.suave(local / PASSA); c.drawImage(gl, 0, 0, W, H); c.globalAlpha = 1;
      }
      tinta(cenas[i], k);
      seloTempo(cn, t);
      cartaoNumero(cn, t);
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 170, fundo: '#FFD23F', borda: '#1B1B1B', cor: '#1B1B1B', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '104px "Lilita One", sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#FFD23F', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro, dispose: () => { cenas.forEach(o => U3.liberarCena(o.sc)); R.dispose(); R.forceContextLoss(); } };
  }
  MOTORES.lowpoly = { criar };
})();
