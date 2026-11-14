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
    dia: ['#2C7DD6', '#73BCF3', '#CFEFFF', '#FFF2D6'],   // v6: 4 tons (zenite, ceu, horizonte, brilho quente) entardecer: ['#3D3B7A', '#FF9E6B'], aurora: ['#6D7FD1', '#FFD3A8'], noite: ['#05081C', '#1C2A55'],
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
    // T503 (12/11): a faixa util do quadro fica entre o cartaz (topo) e a legenda (70%); o fundo era ~30% de grama vazia.
    // A cena sobe 6% e a camera chega 10% mais perto (so no mundo plano; o globo ja cabe).
    // Enquanto o cartaz do titulo esta na tela (3 s) a cena fica 2% mais BAIXA (a cabeca do protagonista nao entra no cartaz);
    // depois sobe 6%. Aplicado por quadro em pose3D.
    const ZOOM503 = 0.9;

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
        if(!q.isMesh || q.material.isMeshBasicMaterial || q.userData.liso)return;   // v4: personagem fica liso
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
      const gr = g.createLinearGradient(0, 0, 0, 256); if (cores.length >= 4) { gr.addColorStop(0, cores[0]); gr.addColorStop(0.35, cores[1]); gr.addColorStop(0.62, cores[2]); gr.addColorStop(0.78, cores[3]); gr.addColorStop(1, cores[2]); } else { gr.addColorStop(0, cores[0]); gr.addColorStop(0.62, cores[1]); gr.addColorStop(1, cores[1]); }
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
    // v5 (14/11, dono: "melhore muito a qualidade 3D dos personagens, mais detalhes, menos partes do corpo em conflito,
    // anime as pessoas; bonecos estaticos"). v4 tinha braco e perna de UMA peca girando no ombro/quadril: toda pose
    // enfiava a mao no tronco e a perna andava dura. Agora: COTOVELO e JOELHO (cada membro em 2 segmentos), ombro afastado
    // do tronco, palpebra de verdade (pisca sem achatar o olho), cabelo com volume, cinto, gola, bolso, cadarco.
    // E o boneco nunca fica parado: respira, troca o peso, olha em volta, gesticula e mexe a boca quando a narracao fala.
    const PM = {};
    const MP = (cor, o) => {
      o = o || {}; const k = cor + JSON.stringify(o);
      if (!PM[k]) PM[k] = new T.MeshLambertMaterial({ color: cor, emissive: o.emis || '#000000', transparent: !!o.op, opacity: o.op || 1, depthWrite: !o.op });
      return PM[k];
    };
    const GP = {};
    const capsula = (r, l) => { const k = 'c' + r + ':' + l; if (!GP[k]) { const pts = [];
      for (let i = 0; i <= 8; i++) { const a = -Math.PI / 2 + (i / 8) * (Math.PI / 2); pts.push(new T.Vector2(Math.cos(a) * r, Math.sin(a) * r - l / 2)); }
      for (let i = 0; i <= 8; i++) { const a = (i / 8) * (Math.PI / 2); pts.push(new T.Vector2(Math.cos(a) * r, Math.sin(a) * r + l / 2)); }
      pts[0].x = 0.0001; pts[pts.length - 1].x = 0.0001; GP[k] = new T.LatheGeometry(pts, 24); } return GP[k]; };
    const esfera = (r, a, b) => { const k = 's' + r + ':' + a + ':' + b; if (!GP[k]) GP[k] = new T.SphereGeometry(r, 28, 20, 0, Math.PI * 2, a || 0, b || Math.PI); return GP[k]; };
    const mesh = (geo, mat, x, y, z, pai) => { const m = new T.Mesh(geo, mat); m.userData.liso = true; m.position.set(x || 0, y || 0, z || 0); if (pai) pai.add(m); return m; };
    function pessoa(r, idx) {
      const g = new T.Group(), corpo = new T.Group(); g.add(corpo);
      const roupa = COR.roupa[idx % COR.roupa.length], pele = COR.pele[Math.floor(r() * COR.pele.length)], cab = COR.cabelo[Math.floor(r() * COR.cabelo.length)];
      const cPele = new T.Color(pele), mPele = MP(pele, { emis: cPele.clone().multiplyScalar(0.3).getStyle() });   // 0,3: rosto escuro sem 'barba' de sombra
      const mRoupa = MP(roupa), mCalca = MP(COR.calca), mCab = MP(cab), mSapato = MP('#2A2A30');
      const escuro = new T.Color(roupa).multiplyScalar(0.72).getStyle(), mEscuro = MP(escuro);
      // tronco: quadril, barriga, peito -- o tronco e' um grupo que respira e inclina sem mexer nos pes
      const tronco = new T.Group(); tronco.position.y = 0.9; corpo.add(tronco);
      const quadril = mesh(capsula(0.29, 0.14), mCalca, 0, 0, 0, tronco); quadril.rotation.z = Math.PI / 2; quadril.scale.set(1, 1.05, 0.8);
      mesh(new T.TorusGeometry(0.315, 0.03, 8, 32), MP('#3A2A20'), 0, 0.1, 0, tronco).rotation.x = Math.PI / 2;   // cinto
      mesh(new T.BoxGeometry(0.09, 0.07, 0.02), MP('#C9A64A'), 0, 0.1, 0.24, tronco);                               // fivela
      const peito = mesh(capsula(0.34, 0.4), mRoupa, 0, 0.44, 0, tronco); peito.scale.set(1.0, 1, 0.72);
      const barra = mesh(new T.TorusGeometry(0.33, 0.03, 8, 30), mEscuro, 0, 0.15, 0, tronco); barra.rotation.x = Math.PI / 2; barra.scale.set(1.02, 0.74, 1);
      const gola = mesh(new T.TorusGeometry(0.12, 0.035, 8, 20), mEscuro, 0, 0.77, 0.02, tronco); gola.rotation.x = Math.PI / 2;
      mesh(new T.BoxGeometry(0.13, 0.11, 0.02), mEscuro, 0.15, 0.55, 0.245, tronco);                                 // bolso
      mesh(new T.CylinderGeometry(0.095, 0.11, 0.16, 18), mPele, 0, 0.82, 0, tronco);                                // pescoco
      // cabeca
      const cabeca = new T.Group(); cabeca.position.y = 1.16; tronco.add(cabeca);
      const crane = mesh(esfera(0.37), mPele, 0, 0, 0, cabeca); crane.scale.set(1, 1.04, 0.96);
      [-1, 1].forEach((s) => { const o = mesh(esfera(0.085), mPele, s * 0.36, -0.02, 0, cabeca); o.scale.set(0.55, 1, 0.8); });
      const nariz = mesh(esfera(0.055), MP(cPele.clone().multiplyScalar(0.94).getStyle()), 0, -0.05, 0.36, cabeca); nariz.scale.set(1, 0.9, 0.8);
      [-1, 1].forEach((s) => { const b = mesh(new T.CircleGeometry(0.06, 20), MP('#FF7A8A', { op: 0.32 }), s * 0.2, -0.1, 0.33, cabeca); b.rotation.y = s * 0.45; });
      // cabelo com volume: calota + franja + mechas laterais; estilo 1 longo, 2 coque, 3 cacheado
      const estilo = Math.floor(r() * 4);
      const calota = mesh(esfera(0.398, 0, Math.PI * (estilo === 1 ? 0.6 : 0.48)), mCab, 0, 0.05, -0.03, cabeca); calota.rotation.x = -0.55;
      for (let j = 0; j < 5; j++) { const m = mesh(capsula(0.06, 0.12), mCab, -0.2 + j * 0.1, 0.29 - Math.abs(j - 2) * 0.02, 0.25 - Math.abs(j - 2) * 0.03, cabeca); m.rotation.set(1.2, 0, (j - 2) * 0.25); }
      [-1, 1].forEach((s) => { const m = mesh(esfera(0.12), mCab, s * 0.33, 0.12, -0.05, cabeca); m.scale.set(0.6, 1.1, 1); });
      if (estilo === 1) { const nuca = mesh(new T.SphereGeometry(0.39, 24, 16, Math.PI * 1.05, Math.PI * 0.9, Math.PI * 0.3, Math.PI * 0.45), mCab, 0, -0.02, -0.06, cabeca); nuca.scale.set(1.05, 1.15, 1); }   // so' ATRAS (dava a volta e cobria o rosto: a 'barba')
      if (estilo === 2) { mesh(esfera(0.15), mCab, 0, 0.36, -0.22, cabeca); mesh(new T.TorusGeometry(0.1, 0.025, 6, 16), MP('#E8473C'), 0, 0.3, -0.2, cabeca).rotation.x = 1; }
      if (estilo === 3) for (let j = 0; j < 9; j++) { const a = (j / 9) * Math.PI * 2; mesh(esfera(0.11), mCab, Math.cos(a) * 0.3, 0.2 + Math.sin(j * 1.7) * 0.05, Math.sin(a) * 0.3 - 0.05, cabeca); }
      // olhos com palpebra: [grupoEsq, brilhoEsq, grupoDir, brilhoDir]
      const olhos = [], sobr = [], palp = [];
      const mBranco = MP('#FFFFFF'), mIris = MP(['#3B2A20', '#2E5E8C', '#3E6B3A'][Math.floor(r() * 3)]), mPup = MP('#0C0C0C'), mBrilho = MP('#FFFFFF', { emis: '#FFFFFF' });
      [-0.13, 0.13].forEach((x) => {
        const og = new T.Group(); og.position.set(x, 0.05, 0.315); cabeca.add(og);
        const br = mesh(esfera(0.075), mBranco, 0, 0, 0, og); br.scale.set(0.85, 1.05, 0.5);
        const iris = new T.Group(); og.add(iris); og.userData.iris = iris;
        mesh(esfera(0.047), mIris, 0, -0.005, 0.03, iris).scale.set(1, 1, 0.45);
        mesh(esfera(0.026), mPup, 0, -0.005, 0.045, iris).scale.set(1, 1, 0.4);
        olhos.push(og);
        const b = mesh(esfera(0.014), mBrilho, x + 0.018, 0.075, 0.37, cabeca); olhos.push(b);
        const pl = mesh(esfera(0.08, 0, Math.PI / 2), mPele, x, 0.06, 0.315, cabeca); pl.scale.set(0.9, 1, 0.62); pl.rotation.x = 0.1; palp.push(pl);
        const s = mesh(capsula(0.017, 0.085), mCab, x, 0.17, 0.33, cabeca); s.rotation.z = Math.PI / 2 + (x < 0 ? -0.12 : 0.12); sobr.push(s);
      });
      const mBoca = MP('#7A2B2B');
      const bocaRiso = mesh(new T.TorusGeometry(0.075, 0.02, 10, 24, Math.PI), mBoca, 0, -0.15, 0.33, cabeca); bocaRiso.rotation.z = Math.PI;
      const bocaO = new T.Group(); bocaO.position.set(0, -0.17, 0.33); cabeca.add(bocaO);
      mesh(esfera(0.06), mBoca, 0, 0, 0, bocaO).scale.set(0.85, 1.1, 0.35);
      mesh(esfera(0.03), MP('#E86A6A'), 0, -0.025, 0.012, bocaO).scale.set(1.2, 0.7, 0.3);
      mesh(new T.BoxGeometry(0.07, 0.018, 0.01), MP('#FFFFFF'), 0, 0.045, 0.02, bocaO);   // dentes de cima
      const bocaReta = mesh(capsula(0.016, 0.09), mBoca, 0, -0.15, 0.34, cabeca); bocaReta.rotation.z = Math.PI / 2;
      // bracos: ombro -> (manga + braco) -> COTOVELO -> (antebraco + mao); pernas: quadril -> coxa -> JOELHO -> canela + sapato
      const membros = [], cot = [], joe = [];
      [[-0.47, 1.6, 'b'], [0.47, 1.6, 'b'], [-0.16, 0.86, 'p'], [0.16, 0.86, 'p']].forEach(([x, y, tipo]) => {
        const piv = new T.Group(); piv.position.set(x, y, 0);
        const s = Math.sign(x);
        if (tipo === 'b') {
          mesh(esfera(0.125), mRoupa, 0, 0, 0, piv).scale.set(1, 1, 0.9);
          mesh(capsula(0.105, 0.14), mRoupa, 0, -0.13, 0, piv);
          mesh(new T.TorusGeometry(0.1, 0.022, 6, 18), mEscuro, 0, -0.22, 0, piv).rotation.x = Math.PI / 2;   // punho da manga
          mesh(capsula(0.08, 0.12), mPele, 0, -0.3, 0, piv);
          const c2 = new T.Group(); c2.position.y = -0.38; piv.add(c2);
          mesh(esfera(0.082), mPele, 0, 0, 0, c2);
          mesh(capsula(0.076, 0.18), mPele, 0, -0.14, 0, c2);
          const mao = new T.Group(); mao.position.y = -0.32; c2.add(mao);
          mesh(esfera(0.098), mPele, 0, -0.02, 0.01, mao).scale.set(0.95, 1.05, 0.72);
          const ded = mesh(capsula(0.05, 0.07), mPele, 0, -0.1, 0.02, mao); ded.scale.set(1.6, 1, 0.9);
          const pol = mesh(capsula(0.033, 0.06), mPele, -s * 0.075, -0.0, 0.05, mao); pol.rotation.z = s * 0.7;
          cot.push(c2);
        } else {
          mesh(capsula(0.13, 0.2), mCalca, 0, -0.2, 0, piv);
          const c2 = new T.Group(); c2.position.y = -0.4; piv.add(c2);
          mesh(esfera(0.125), mCalca, 0, 0, 0, c2);
          mesh(capsula(0.118, 0.14), mCalca, 0, -0.13, 0, c2);
          mesh(new T.CylinderGeometry(0.1, 0.1, 0.07, 18), MP('#F4F4F4'), 0, -0.3, 0, c2);
          const sap = mesh(esfera(0.14), mSapato, 0, -0.39, 0.07, c2); sap.scale.set(0.95, 0.6, 1.45);
          const sola = mesh(esfera(0.14, Math.PI * 0.5, Math.PI * 0.5), MP('#EDEDED'), 0, -0.405, 0.07, c2); sola.scale.set(0.97, 0.45, 1.48);
          mesh(new T.BoxGeometry(0.1, 0.012, 0.03), MP('#EDEDED'), 0, -0.33, 0.19, c2).rotation.x = 0.5;   // cadarco
          joe.push(c2);
        }
        corpo.add(piv); membros.push(piv);
      });
      // o tronco carrega os ombros: braco acompanha a respiracao e a inclinacao
      membros.slice(0, 2).forEach((b) => { tronco.attach(b); });
      const suor = []; for (let k = 0; k < 3; k++) { const s = mesh(esfera(0.055), MP('#7CC7FF'), 0, 0, 0, cabeca); s.scale.set(0.8, 1.2, 0.8); s.visible = false; suor.push(s); }
      g.traverse((o) => { if (o.isMesh) o.castShadow = true; });
      g.userData = { corpo, tronco, cabeca, membros, cot, joe, olhos, palp, sobr, bocaRiso, bocaO, bocaReta, suor, fase: r() * 10, mao: r() < 0.5 ? 0 : 1 };
      return sombra(g);
    }
    // POSES v5: ombro (x frente/tras, z abre), COTOVELO (dobra para a frente), quadril, JOELHO; e por baixo de tudo
    // o MOVIMENTO DE BASE (respira, troca o peso, olha em volta, gesticula). `fala` 0..1 = a narracao esta falando agora.
    function posar(p, modo, t, k, fala) {
      const u = p.userData, m = u.membros, tf = t + u.fase, cot = u.cot || [], joe = u.joe || [];
      const rot = (q, x, z) => { q.rotation.x = x; q.rotation.z = z || 0; };
      const dobra = (q, a) => { if (q) q.rotation.x = -a; };            // cotovelo: antebraco para a frente
      const flex = (q, a) => { if (q) q.rotation.x = a; };              // joelho: canela para tras
      let boca = 'riso', olhoS = 1, bob = 0, inclina = 0, cabX = Math.sin(tf * 0.9) * 0.05, cabZ = Math.sin(tf * 1.3) * 0.05, tremor = 0, agach = 1;
      let cabY = 0.35 * Math.sin(tf * 0.37) * Math.sin(tf * 0.11 + 1);   // olha em volta devagar
      // base: bracos soltos com cotovelo levemente dobrado e balanco; joelhos quase retos
      let cE = 0.22 + 0.06 * Math.sin(tf * 1.1), cD = 0.22 + 0.06 * Math.sin(tf * 1.1 + 1), jE = 0.04, jD = 0.04;
      const peso = Math.sin(tf * 0.8);                                   // troca o peso de perna
      const anda = (vel, amp) => { const a = tf * vel; rot(m[0], Math.sin(a) * amp, 0.1); rot(m[1], -Math.sin(a) * amp, -0.1); rot(m[2], -Math.sin(a) * amp); rot(m[3], Math.sin(a) * amp);
        jE = Math.max(0, Math.sin(a)) * amp * 1.3 + 0.05; jD = Math.max(0, -Math.sin(a)) * amp * 1.3 + 0.05; cE = cD = 0.35 + amp * 0.7; bob = Math.abs(Math.sin(a)) * 0.1 * amp; cabY *= 0.3; };
      switch (modo) {
        case 'anda': anda(6, 0.6); break;
        case 'corre': anda(11, 1.0); cE = cD = 1.5; inclina = 0.22; boca = 'O'; break;
        case 'surpreso': rot(m[0], -0.2, 1.1 + Math.sin(tf * 9) * 0.08); rot(m[1], -0.2, -1.1 - Math.sin(tf * 9) * 0.08); cE = cD = 1.2; rot(m[2], 0); rot(m[3], 0); boca = 'O'; olhoS = 1.3; bob = Math.max(0, U.mola(k * 3, 10) - 0.9) * 0.6; cabY *= 0.2; break;
        case 'frio': rot(m[0], -0.5, -0.35); rot(m[1], -0.5, 0.35); cE = cD = 1.9; rot(m[2], 0); rot(m[3], 0); jE = jD = 0.12; tremor = 0.03; boca = 'reta'; agach = 0.96; cabY *= 0.3; break;
        case 'calor': rot(m[0], 0.05, 0.2); rot(m[1], -1.2 + Math.sin(tf * 14) * 0.25, -0.35); cD = 1.6; rot(m[2], 0); rot(m[3], 0); boca = 'O';
          u.suor.forEach((s, j) => { s.visible = true; const q = (tf * 0.9 + j / 3) % 1; s.position.set(-0.35 + j * 0.35, 0.3 - q * 0.9, 0.3); }); break;
        case 'aponta': rot(m[0], 0, 0.15); rot(m[1], -1.45, -0.2); cD = 0.05; rot(m[2], 0); rot(m[3], 0); cabX = -0.1; cabY = 0.15; boca = 'O'; break;
        case 'olha_cima': rot(m[0], 0, 0.15); rot(m[1], -0.25, -0.15); cD = 0.9; rot(m[2], 0); rot(m[3], 0); cabX = -0.5; cabY *= 0.3; boca = 'O'; olhoS = 1.2; break;
        case 'comemora': { const s = Math.abs(Math.sin(tf * 7)); rot(m[0], 0, 2.5 + s * 0.2); rot(m[1], 0, -2.5 - s * 0.2); cE = cD = 0.3; rot(m[2], 0); rot(m[3], 0); jE = jD = s * 0.4; bob = s * 0.3; break; }
        case 'flutua': rot(m[0], 0.3, 1.2 + Math.sin(tf) * 0.2); rot(m[1], -0.3, -1.2 - Math.sin(tf) * 0.2); rot(m[2], 0.4, 0.25); rot(m[3], -0.3, -0.25); jE = 0.6; jD = 0.3; boca = 'O'; break;
        case 'sufoca': rot(m[0], -0.9, -0.25); rot(m[1], -0.9, 0.25); cE = cD = 2.0; rot(m[2], 0); rot(m[3], 0); boca = 'O'; inclina = Math.sin(tf * 3) * 0.12; agach = 0.95; jE = jD = 0.2; break;
        case 'medo': rot(m[0], -0.6, 0.5); rot(m[1], -0.6, -0.5); cE = cD = 2.1; rot(m[2], 0.15); rot(m[3], -0.15); jE = jD = 0.35; boca = 'O'; tremor = 0.02; agach = 0.92; olhoS = 1.3; cabY *= 0.4; break;
        case 'nada': rot(m[0], 0.5 + Math.sin(tf * 4) * 0.4, 0.6); rot(m[1], -0.5 - Math.sin(tf * 4) * 0.4, -0.6); cE = cD = 0.5; rot(m[2], Math.sin(tf * 4) * 0.4); rot(m[3], -Math.sin(tf * 4) * 0.4); jE = 0.3 + Math.sin(tf * 4) * 0.2; jD = 0.3 - Math.sin(tf * 4) * 0.2; boca = 'O'; break;
        default: {
          // PARADO nao e' estatico: troca o peso e, quando a narracao fala, a mao da vez GESTICULA
          rot(m[0], Math.sin(tf * 1.4) * 0.05, 0.12); rot(m[1], -Math.sin(tf * 1.4) * 0.05, -0.12); rot(m[2], 0, -0.03 * peso); rot(m[3], 0, -0.03 * peso);
          jE = 0.04 + Math.max(0, peso) * 0.12; jD = 0.04 + Math.max(0, -peso) * 0.12;
          if (fala > 0) { const b = u.mao, gesto = Math.sin(tf * 2.3) * 0.5 + 0.5;
            rot(m[b], -0.55 - gesto * 0.35, (b ? -1 : 1) * (0.25 + gesto * 0.15)); if (b) cD = 1.3 + Math.sin(tf * 4.1) * 0.25; else cE = 1.3 + Math.sin(tf * 4.1) * 0.25; }
        }
      }
      if (modo !== 'calor') u.suor.forEach((s) => { s.visible = false; });
      dobra(cot[0], cE); dobra(cot[1], cD); flex(joe[0], jE); flex(joe[1], jD);
      // abaixa o corpo o quanto os joelhos dobram (o pe nao afunda no chao)
      const dobraJ = Math.min(jE, jD), desce = 0.4 * (1 - Math.cos(dobraJ)) * 0.9;
      u.corpo.position.y = bob - desce; u.corpo.rotation.x = inclina; u.corpo.scale.y = agach;
      u.corpo.position.x = (tremor ? Math.sin(tf * 60) * tremor : 0) + (modo === 'parado' || !modo ? peso * 0.025 : 0);
      u.corpo.rotation.z = modo === 'parado' || !modo ? -peso * 0.025 : 0;
      if (u.tronco) { const resp = Math.sin(tf * 2.2); u.tronco.scale.set(1 + resp * 0.012, 1 + resp * 0.018, 1 + resp * 0.02); }
      u.cabeca.rotation.x = cabX; u.cabeca.rotation.z = cabZ; u.cabeca.rotation.y = cabY;
      // olhos acompanham a cabeca (as pupilas olham antes); piscar fecha a PALPEBRA
      const pisca = ((tf % 3.7) < 0.13);
      u.olhos.forEach((o, j) => { if (j % 2 === 0) { o.scale.setScalar(olhoS); if (o.userData.iris) o.userData.iris.position.x = cabY * 0.04; } else o.visible = !pisca; });
      if (u.palp) u.palp.forEach((pl) => { pl.rotation.x = pisca ? 1.45 : 0.1 - (olhoS - 1) * 0.6; });
      // boca: quando a narracao fala, abre e fecha no ritmo das silabas
      const falaAgora = fala > 0 && boca !== 'O';
      u.bocaRiso.visible = boca === 'riso' && !falaAgora; u.bocaO.visible = boca === 'O' || falaAgora; u.bocaReta.visible = boca === 'reta' && !falaAgora;
      u.bocaO.scale.set(1, falaAgora ? 0.35 + 0.65 * Math.abs(Math.sin(tf * 13)) : 1, 1);
      if (u.sobr) u.sobr.forEach((s, j) => { const lado = j ? 1 : -1, susto = olhoS > 1.15, tenso = boca === 'reta';
        s.position.y = 0.17 + (susto ? 0.045 : boca === 'O' ? 0.02 : 0) + (falaAgora ? 0.01 * Math.sin(tf * 3) : 0); s.rotation.z = Math.PI / 2 + lado * (susto ? -0.28 : tenso ? 0.32 : 0.12); });
    }
    // a narracao esta falando em t? (boca e gesto do protagonista)
    const PAL = Array.isArray(spec.palavras) ? spec.palavras : [];
    function falaEm(t) { let lo = 0, hi = PAL.length - 1; while (lo <= hi) { const mid = (lo + hi) >> 1, w = PAL[mid]; if (t < w.ini) hi = mid - 1; else if (t > w.fim) lo = mid + 1; else return 1; } return 0; }

    // ------------------------------------------------------------- cenarios
    // Cada cena e' um DIORAMA: um disco de terra flutuando no ceu, com borda de
    // estratos. E' a cara "tiny world" do canal e resolve o enquadramento 9:16:
    // o mundo inteiro cabe no quadro e a camera gira em volta dele.
    const RAIO = 8;
    function terreno(cen, r) {
      const cores = { deserto: ['#E8B86A', '#D9A050'], polo: ['#F4F7FA', '#DCE9F2'], vulcao: ['#5A4048', '#46323A'], floresta: ['#78B66B', '#5E9E55'],
        oceano: ['#E8D9A8', '#D8C690'], areia_movedica: ['#EED9A0', '#E0C688'], cidade: ['#9CB48A', '#8AA57A'], montanha: ['#7FAF6E', '#8C8C8C'], praia: ['#EBD9A6', '#D9C48E'], campo: ['#9BC46A', '#86B25A'], lua: ['#B9B4AA', '#9C978E'] }[cen] || ['#9CB48A', '#8AA57A'];
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
          if (d.modelo === 'pessoa') g.userData.ehPessoa = true;
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
        if (g.userData.ehPessoa) posar(g, (MODO[o.acao] || ['parado'])[0], t, k, falaEm(t));   // v3: a pessoa criada pela IA tambem se mexe
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

    // v3 (13/11, T503 'melhore brutalmente'): o CENARIO vem da historia. Areia movedica virava 'praia' (gente em pe
    // dentro do mar) e 'cocina que explota' virava uma rua de predios com uma caixa cinza.
    const CEN_PISTAS = [
      ['areia_movedica', /(arena movediza|areia movedi[cç]a|quicksand)/i],
      ['cozinha', /\b(cocinas?|cozinhas?|kitchens?|hornos?|fornos?|ovens?|estufas?|fog[aã]o|stoves?|microondas|micro-ondas|microwaves?|harina|farinha|flour|sart[eé]n|frigideira|frying pan|nevera|geladeira|fridge)\b/i],
    ];
    // o cenario achado vale para o VIDEO: "Tus pies se hundirían" nao repete "arena movediza", mas e' a mesma areia
    const pistaDe = (txt) => { for (const [c, re] of CEN_PISTAS) if (re.test(txt)) return c; return null; };
    const CEN_VIDEO = pistaDe([spec.titulo].concat(spec.cenas.map((c) => c.texto)).join(' | '));
    const GENERICOS = { praia: 1, oceano: 1, cidade: 1, campo: 1, deserto: 1 };
    function cenarioDaCena(cn) {
      const proprio = pistaDe(String(cn.texto || ''));
      if (proprio) return proprio;
      if (CEN_VIDEO && (!cn.cenario || GENERICOS[cn.cenario])) return CEN_VIDEO;
      return cn.cenario || 'cidade';
    }
    // COZINHA: ambiente interno (piso de ladrilho, duas paredes, bancada com fogao, armarios, janela, geladeira).
    function cozinha(r, fogo) {
      const g = new T.Group();
      const piso = new T.Group();
      for (let i = -6; i < 6; i++) for (let j = -5; j < 5; j++) { const q = new T.Mesh(caixaGeo(1, 0.1, 1), M((i + j) % 2 ? '#E9E1D3' : '#CFC3AE')); q.position.set(i + 0.5, -0.05, j + 0.5); piso.add(q); }
      g.add(piso);
      const parede = M('#F2D7A6'), parede2 = M('#E8C690');
      const fundo = new T.Mesh(caixaGeo(12, 6, 0.3), parede); fundo.position.set(0, 3, -3.6); g.add(fundo);
      const lado = new T.Mesh(caixaGeo(0.3, 6, 10), parede2); lado.position.set(-5.6, 3, 1.3); g.add(lado);
      const azul = M('#3E7CB1'), tampo = M('#F4F1EA');
      const banc = new T.Mesh(caixaGeo(8, 1.1, 1.3), azul); banc.position.set(0, 0.55, -2.8); g.add(banc);
      const tp = new T.Mesh(caixaGeo(8.2, 0.16, 1.45), tampo); tp.position.set(0, 1.18, -2.8); g.add(tp);
      for (let k = 0; k < 5; k++) { const p2 = new T.Mesh(caixaGeo(0.04, 0.9, 0.02), M('#2D5F8C')); p2.position.set(-3.2 + k * 1.6, 0.55, -2.14); g.add(p2); }
      const fog = new T.Mesh(caixaGeo(1.8, 0.08, 1.1), M('#2B2B2B')); fog.position.set(1.4, 1.3, -2.8); g.add(fog);
      const bocas = [];
      [[-0.45, -0.25], [0.45, -0.25], [-0.45, 0.25], [0.45, 0.25]].forEach(([x, z]) => { const b = new T.Mesh(new T.TorusGeometry(0.18, 0.04, 4, 12), M(fogo ? '#FF7A2A' : '#555', fogo ? { emis: '#FF4A00' } : undefined)); b.rotation.x = Math.PI / 2; b.position.set(1.4 + x, 1.36, -2.8 + z); g.add(b); bocas.push(b); });
      const arm = M('#FFFFFF');
      for (let k = 0; k < 4; k++) { const a = new T.Mesh(caixaGeo(1.7, 1.2, 0.7), arm); a.position.set(-3 + k * 1.95, 4.1, -3.1); g.add(a); const pux = new T.Mesh(caixaGeo(0.3, 0.06, 0.06), M('#999')); pux.position.set(-3 + k * 1.95, 3.65, -2.72); g.add(pux); }
      const jan = new T.Mesh(caixaGeo(2.2, 1.6, 0.1), M('#BFE3FF', { emis: '#3A6A8A' })); jan.position.set(-2.2, 2.6, -3.42); g.add(jan);
      const mold = new T.Mesh(caixaGeo(2.4, 0.12, 0.14), M('#FFFFFF')); mold.position.set(-2.2, 1.75, -3.4); g.add(mold);
      const gel = new T.Mesh(caixaGeo(1.4, 3.6, 1.3), M('#DCE3E8')); gel.position.set(-4.6, 1.8, -2.6); g.add(gel);
      const panela = new T.Mesh(new T.CylinderGeometry(0.32, 0.28, 0.32, 10), M('#B0B6BC')); panela.position.set(1.85, 1.52, -2.55); g.add(panela);
      const lamp = new T.Mesh(new T.ConeGeometry(0.45, 0.4, 10, 1, true), M('#2B2B2B')); lamp.position.set(0, 5.1, -0.5); g.add(lamp);
      const lb = brilho('rgba(255,225,160,1)', 2.2); lb.position.set(0, 4.85, -0.5); g.add(lb);
      g.userData = { alt: () => 0, bocas, interior: true };
      return g;
    }
    function enfeitar(cen, r, sobre, o) {
      const pedra = (s0) => { const m = new T.Mesh(new T.DodecahedronGeometry(0.22 * s0, 0), M(['#9A958C', '#8A847A', '#B0A99E'][Math.floor(r() * 3)])); m.rotation.set(r() * 3, r() * 3, r() * 3); m.scale.y = 0.7; return m; };
      const arbusto = () => { const g = new T.Group(), cor = ['#5E9E55', '#4E8C48', '#6DAA5E'][Math.floor(r() * 3)]; for (let j = 0; j < 3; j++) { const b = new T.Mesh(new T.IcosahedronGeometry(0.28 + r() * 0.12, 0), M(cor)); b.position.set((j - 1) * 0.25, 0.22, (r() - 0.5) * 0.2); g.add(b); } return g; };
      const flor = () => { const g = new T.Group(), h = new T.Mesh(new T.CylinderGeometry(0.015, 0.015, 0.3, 4), M('#4E8C48')); h.position.y = 0.15; g.add(h); const f = new T.Mesh(new T.IcosahedronGeometry(0.07, 0), M(['#FFFFFF', '#FFD23F', '#F27DA3', '#B07CFF'][Math.floor(r() * 4)])); f.position.y = 0.32; g.add(f); return g; };
      const cerca = () => { const g = new T.Group(), mad = M('#B98A5A'); for (let j = 0; j < 3; j++) { const p0 = new T.Mesh(caixaGeo(0.08, 0.6, 0.08), mad); p0.position.set(j * 0.5 - 0.5, 0.3, 0); g.add(p0); } [0.2, 0.45].forEach((y) => { const tb = new T.Mesh(caixaGeo(1.15, 0.07, 0.05), mad); tb.position.set(0, y, 0); g.add(tb); }); g.rotation.y = r() * 3; return g; };
      const poste = () => { const g = new T.Group(); const h = new T.Mesh(new T.CylinderGeometry(0.04, 0.05, 2.2, 6), M('#4A4F57')); h.position.y = 1.1; g.add(h); const l = new T.Mesh(new T.IcosahedronGeometry(0.14, 1), M('#FFF2C4', { emis: '#C9A64A' })); l.position.y = 2.25; g.add(l); return g; };
      const cone = () => { const g = new T.Group(); const c0 = new T.Mesh(new T.ConeGeometry(0.16, 0.42, 8), M('#F27A2A')); c0.position.y = 0.21; g.add(c0); const f = new T.Mesh(new T.CylinderGeometry(0.105, 0.125, 0.07, 8), M('#FFFFFF')); f.position.y = 0.22; g.add(f); return g; };
      const caixote = () => { const m = new T.Mesh(caixaGeo(0.45, 0.45, 0.45), M('#C49A5E')); m.position.y = 0.22; m.rotation.y = r() * 3; const g = new T.Group(); g.add(m); return g; };
      const placa = () => { const g = new T.Group(); const h = new T.Mesh(caixaGeo(0.06, 0.9, 0.06), M('#6E6E6E')); h.position.y = 0.45; g.add(h); const pl = new T.Mesh(caixaGeo(0.5, 0.5, 0.04), M('#FFD23F')); pl.position.y = 0.95; pl.rotation.z = Math.PI / 4; g.add(pl); const x = new T.Mesh(caixaGeo(0.06, 0.28, 0.05), M('#1B1B1B')); x.position.set(0, 0.97, 0.03); g.add(x); return g; };
      const osso = () => { const g = new T.Group(), b = M('#EFE8D8'); const h = new T.Mesh(new T.CylinderGeometry(0.03, 0.03, 0.4, 5), b); h.rotation.z = Math.PI / 2; h.position.y = 0.05; g.add(h); [-0.2, 0.2].forEach((x) => { const e = new T.Mesh(new T.IcosahedronGeometry(0.06, 0), b); e.position.set(x, 0.05, 0); g.add(e); }); g.rotation.y = r() * 3; return g; };
      const tabelas = { deserto: [pedra, pedra, osso, arbusto, placa], areia_movedica: [pedra, osso, placa, arbusto, pedra], polo: [pedra, pedra, placa], vulcao: [pedra, pedra, pedra, placa, osso],
        floresta: [arbusto, arbusto, flor, flor, pedra, cerca], campo: [flor, flor, arbusto, cerca, pedra, caixote], cidade: [poste, cone, caixote, placa, arbusto, pedra], praia: [pedra, arbusto, pedra],
        montanha: [pedra, pedra, arbusto, flor, cerca], lua: [pedra, pedra, pedra] };
      const lista = tabelas[cen] || [pedra, arbusto, flor, cerca, caixote];
      const n = 30 + Math.floor(r() * 10);
      for (let k = 0; k < n; k++) {
        const a = r() * Math.PI * 2, d = 3.4 + Math.pow(r(), 0.8) * 4.3, x = Math.cos(a) * d, z = Math.sin(a) * d;
        if (z > 2.2 && Math.abs(x) < 2.2) continue;   // nunca entre a camera e o protagonista
        const m = lista[k % lista.length](0.7 + r() * 0.9); if (m.isMesh) { const g = new T.Group(); g.add(m); m.position.y = 0.08; sobre(g, x, z); } else sobre(m, x, z);
      }
    }
    // ---------------------------------------------------------------- praia v6
    // 14/11 (dono: "no estilo da agua salgada melhore bruscamente a qualidade do cenario de fundo, o chao, o ceu, o
    // conteudo"). Antes: um cilindro azul liso cortando o disco de areia, ceu de 2 cores, um pier e um barquinho.
    // Agora: OCEANO ate' o horizonte com ondas e cor por profundidade, espuma na beira, areia com grao e faixa molhada,
    // coqueiros, guarda-sois, toalhas, bola, castelo, prancha, posto de salva-vidas, ilhas, veleiros e gaivotas.
    function oceanoGrande() {
      const geo = new T.PlaneGeometry(260, 260, 90, 90); geo.rotateX(-Math.PI / 2);
      const p = geo.attributes.position, cols = [], base = new Float32Array(p.count * 2);
      const raso = new T.Color('#43D3CF'), medio = new T.Color('#1E9BD7'), fundo = new T.Color('#0B5BA6');
      for (let i = 0; i < p.count; i++) { const x = p.getX(i), z = p.getZ(i), d = Math.hypot(x, z); base[i * 2] = x; base[i * 2 + 1] = z;
        const q1 = U.clamp((d - RAIO + 1) / 6, 0, 1), q2 = U.clamp((d - RAIO - 6) / 40, 0, 1);
        const cc = raso.clone().lerp(medio, q1).lerp(fundo, q2); const brilhoV = 0.92 + 0.16 * hash(x * 0.7, 0, z * 0.7); cols.push(cc.r * brilhoV, cc.g * brilhoV, cc.b * brilhoV); }
      geo.setAttribute('color', new T.Float32BufferAttribute(cols, 3));
      const m = new T.Mesh(geo, new T.MeshLambertMaterial({ vertexColors: true, transparent: true, opacity: 0.94 }));
      m.userData.ondas = (t, nivel) => { for (let i = 0; i < p.count; i++) { const x = base[i * 2], z = base[i * 2 + 1], d = Math.hypot(x, z); if (d > 60) continue;
        p.setY(i, 0.09 * Math.sin(x * 0.55 + t * 1.6) + 0.07 * Math.sin(z * 0.8 - t * 1.2) + 0.04 * Math.sin((x + z) * 1.7 + t * 2.4)); }
        p.needsUpdate = true; geo.computeVertexNormals(); m.position.y = nivel; };
      return m;
    }
    function espuma() {
      const cv = document.createElement('canvas'); cv.width = 256; cv.height = 16; const g = cv.getContext('2d'), rr2 = U.rng('espuma');
      for (let k = 0; k < 90; k++) { g.fillStyle = 'rgba(255,255,255,' + (0.4 + rr2() * 0.6).toFixed(2) + ')'; g.beginPath(); g.ellipse(rr2() * 256, 8 + (rr2() - 0.5) * 8, 4 + rr2() * 10, 2 + rr2() * 3, 0, 0, Math.PI * 2); g.fill(); }
      const tx = new T.CanvasTexture(cv); tx.wrapS = T.RepeatWrapping; tx.repeat.set(6, 1);
      const m = new T.Mesh(new T.RingGeometry(RAIO - 0.6, RAIO + 0.7, 96, 1), new T.MeshBasicMaterial({ map: tx, transparent: true, opacity: 0.8, depthWrite: false }));
      m.rotation.x = -Math.PI / 2; m.userData.tx = tx; return m;
    }
    function coqueiro(r) {
      const g = new T.Group(), tronco = M('#9B7149'), folha = M('#3E9E4A'), folha2 = M('#2F8A3E');
      let x = 0, y = 0; const curva = 0.35 + r() * 0.25;
      for (let k = 0; k < 7; k++) { const s = new T.Mesh(new T.CylinderGeometry(0.13 - k * 0.01, 0.16 - k * 0.01, 0.55, 7), tronco); s.position.set(x, y + 0.27, 0); s.rotation.z = -curva * k / 7; g.add(s);
        x += Math.sin(curva * k / 7) * 0.55; y += Math.cos(curva * k / 7) * 0.52; }
      for (let k = 0; k < 7; k++) { const f = new T.Mesh(new T.ConeGeometry(0.22, 1.9, 4, 1), k % 2 ? folha : folha2); f.position.set(x, y + 0.1, 0); f.rotation.set(0, (k / 7) * Math.PI * 2, 1.25); f.translateY(0.85); g.add(f); }
      for (let k = 0; k < 3; k++) { const c0 = new T.Mesh(new T.IcosahedronGeometry(0.11, 0), M('#6B4A2B')); c0.position.set(x + Math.cos(k * 2.1) * 0.15, y - 0.08, Math.sin(k * 2.1) * 0.15); g.add(c0); }
      g.userData.copa = g.children.filter((m) => m.geometry && m.geometry.type === 'ConeGeometry').map((m) => { m.material = m.material.clone(); return m; });
      return sombra(g);
    }
    function guardaSol(r) {
      const g = new T.Group(), cores = [['#E8473C', '#FFFFFF'], ['#3E7CB1', '#FFD23F'], ['#5DAA5A', '#FFFFFF']][Math.floor(r() * 3)];
      const h = new T.Mesh(new T.CylinderGeometry(0.035, 0.035, 2.0, 6), M('#EDEDED')); h.position.y = 1.0; h.rotation.z = 0.12; g.add(h);
      for (let k = 0; k < 8; k++) { const fatia = new T.Mesh(new T.ConeGeometry(1.15, 0.45, 3, 1, true, (k / 8) * Math.PI * 2, Math.PI / 4), M(cores[k % 2])); fatia.material.side = T.DoubleSide; fatia.position.set(0.12, 2.05, 0); g.add(fatia); }
      const toalha = new T.Mesh(caixaGeo(0.9, 0.03, 1.7), M(cores[0])); toalha.position.set(0.9, 0.03, 0.4); toalha.rotation.y = 0.3; g.add(toalha);
      const listra = new T.Mesh(caixaGeo(0.9, 0.035, 0.25), M(cores[1])); listra.position.set(0.9, 0.035, 0.4); listra.rotation.y = 0.3; g.add(listra);
      return sombra(g);
    }
    function propsPraia(r, sobre, livreFundo, o) {
      const pos = (ok) => { for (let k = 0; k < 40; k++) { const a = r() * Math.PI * 2, d = 3.2 + r() * (RAIO - 4.4), x = Math.cos(a) * d, z = Math.sin(a) * d; if (ok(x, z)) return [x, z]; } return null; };
      for (let k = 0; k < 4; k++) { const p = pos(livreFundo); if (p) { const cq = sobre(coqueiro(r), p[0], p[1]); cq.rotation.y = r() * 6; cq.scale.setScalar(0.9 + r() * 0.4); o.arvores.push(cq); } }
      for (let k = 0; k < 2; k++) { const p = pos(livreFundo); if (p) sobre(guardaSol(r), p[0], p[1]).rotation.y = r() * 6; }
      let p = pos(livreFundo); if (p) { const bola = new T.Group(); ['#E8473C', '#FFFFFF', '#3E7CB1', '#FFD23F'].forEach((cc, j) => { const gm = new T.Mesh(new T.SphereGeometry(0.28, 12, 8, (j / 4) * Math.PI * 2, Math.PI / 2), M(cc)); bola.add(gm); }); bola.position.y = 0.28; const gb = new T.Group(); gb.add(bola); sobre(gb, p[0], p[1]); o.extras.push(gb); }
      p = pos(livreFundo); if (p) { const cs = new T.Group(), ar = M('#E3C88E'); [[0, 0.3, 0, 0.9, 0.6], [-0.35, 0.75, 0, 0.25, 0.5], [0.35, 0.75, 0, 0.25, 0.5], [0, 0.85, 0, 0.3, 0.7]].forEach(([x, y, z, w, h]) => { const m = new T.Mesh(caixaGeo(w, h, w), ar); m.position.set(x, y, z); cs.add(m); }); sobre(sombra(cs), p[0], p[1]); }
      p = pos(livreFundo); if (p) { const pr = new T.Mesh(capsula(0.22, 1.5), M('#FF9A3C')); pr.scale.z = 0.25; pr.rotation.z = 0.25; pr.position.y = 0.95; const gp = new T.Group(); gp.add(pr); sobre(sombra(gp), p[0], p[1]); }
      p = pos(livreFundo); if (p) { const tw = new T.Group(), br = M('#FFFFFF'), vm = M('#E8473C');
        [[-0.4, -0.4], [0.4, -0.4], [-0.4, 0.4], [0.4, 0.4]].forEach(([x, z]) => { const l = new T.Mesh(caixaGeo(0.08, 1.6, 0.08), br); l.position.set(x, 0.8, z); tw.add(l); });
        const cab = new T.Mesh(caixaGeo(1.1, 0.7, 1.1), vm); cab.position.y = 1.9; tw.add(cab); const tet = new T.Mesh(new T.ConeGeometry(0.85, 0.5, 4), br); tet.position.y = 2.5; tet.rotation.y = Math.PI / 4; tw.add(tet);
        const tw2 = sobre(sombra(tw), p[0], p[1]); tw2.rotation.y = Math.atan2(-p[0], -p[1]); }
      // horizonte: ilhas, veleiros e gaivotas
      for (let k = 0; k < 3; k++) { const a = -2.4 + k * 0.9 + r() * 0.3, d = 55 + r() * 25, ilha = new T.Group(); const mo = new T.Mesh(new T.ConeGeometry(4 + r() * 4, 3 + r() * 3, 8), M('#4E8A55')); mo.position.y = 1; ilha.add(mo); const pr2 = new T.Mesh(new T.CylinderGeometry(5.5, 6.5, 0.6, 10), M('#E3CF98')); ilha.add(pr2); ilha.position.set(Math.sin(a) * d, 0, -Math.cos(a) * d); o.extras.push(ilha); ilha.userData.fixo = true; }
      o.veleiros = []; for (let k = 0; k < 3; k++) { const b = new T.Group(); const cs = new T.Mesh(caixaGeo(1.2, 0.3, 0.45), M('#FFFFFF')); b.add(cs); const vl = new T.Mesh(new T.ConeGeometry(0.5, 1.4, 3), M(['#FFFFFF', '#E8473C', '#FFD23F'][k])); vl.position.y = 0.85; b.add(vl); b.userData = { a: r() * 6.28, d: 22 + k * 7 }; o.veleiros.push(b); }
      o.gaivotas = []; for (let k = 0; k < 5; k++) { const gv = new T.Group(), mb = M('#FFFFFF'); [-1, 1].forEach((s) => { const asa = new T.Mesh(caixaGeo(0.45, 0.03, 0.12), mb); asa.position.x = s * 0.2; asa.userData.lado = s; gv.add(asa); }); gv.userData = { a: r() * 6.28, h: 5.5 + r() * 2.5, d: 4 + r() * 4, v: 0.25 + r() * 0.2 }; o.gaivotas.push(gv); }
      return [...o.veleiros, ...o.gaivotas, ...o.extras.filter((e) => e.userData.fixo)];
    }
    function areiaDetalhe(tr) {   // grao + faixa molhada perto da borda
      const tp = tr.userData && tr.userData.topo; if (!tp || !tp.geometry.attributes.color) return;
      const a = tp.geometry.attributes.color, p = tp.geometry.attributes.position;
      for (let i = 0; i < a.count; i++) { const x = p.getX(i), z = p.getZ(i), d = Math.hypot(x, z) / RAIO, grao = 0.94 + 0.12 * hash(x * 3.1, 0, z * 3.1), molhado = d > 0.82 ? 0.78 : 1;
        a.setXYZ(i, a.getX(i) * grao * molhado, a.getY(i) * grao * molhado, a.getZ(i) * grao * (molhado < 1 ? 0.9 : 1)); }
      a.needsUpdate = true;
    }
    // AREIA MOVEDICA: a poca escura com aneis que ondulam em volta de quem afunda
    function poca() {
      const g = new T.Group();
      const d = new T.Mesh(new T.CircleGeometry(2.1, 28), M('#A98A55')); d.rotation.x = -Math.PI / 2; d.position.y = 0.04; g.add(d);
      const aneis = [];
      for (let k = 0; k < 3; k++) { const a = new T.Mesh(new T.RingGeometry(0.5, 0.62, 28), new T.MeshBasicMaterial({ color: '#7A5E34', transparent: true, opacity: 0.6, side: T.DoubleSide, depthWrite: false })); a.rotation.x = -Math.PI / 2; a.position.y = 0.06; g.add(a); aneis.push(a); }
      g.userData = { aneis }; return g;
    }

    function montar(cn, idx) {
      const sc = new T.Scene(), r = U.rng((spec.semente || 'lp') + ':' + idx);
      const acao = cn.acaoV2, cen = cenarioDaCena(cn);
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
        const interior = cen === 'cozinha';
        const fogo = /(fuego|fogo|fire|llama|chama|explo|incend)/i.test(String(cn.texto || '') + ' ' + String(spec.titulo || ''));
        const tr = interior ? cozinha(r, fogo) : terreno(cen === 'oceano' ? 'praia' : cen, r); sc.add(tr); o.terreno = tr; o.interior = interior;
        if (interior) { sc.background = new T.Color('#F2D7A6'); o.bocas = tr.userData.bocas; }
        else sc.fog = new T.Fog(new T.Color(CEU[hora][1]), 30, 70);
        // v3: o sol era um borrao que estourava o quadro; menor e mais suave
        const solS = brilho(hora === 'noite' ? 'rgba(220,230,255,1)' : 'rgba(255,240,190,1)', hora === 'noite' ? 2.2 : 2.6); solS.material.opacity = 0.6; if (!interior) sc.add(solS); o.solS = interior ? null : solS;
        if (cen === 'areia_movedica') { const pc = poca(); pc.position.set(0, 0, 1.6); sc.add(pc); o.poca = pc; }
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
        const marAberto = (cen === 'oceano' || cen === 'praia') && acao !== 'inunda' && acao !== 'seca' && acao !== 'derrete';
        if (cen === 'oceano' || cen === 'praia' || cen === 'deserto' || cen === 'areia_movedica') areiaDetalhe(tr);
        if (marAberto) {   // v6: oceano ate' o horizonte, espuma, praia viva
          const og = oceanoGrande(); sc.add(og); o.oceano = og; const es = espuma(); sc.add(es); o.espuma = es;
          propsPraia(r, sobre, livreFundo, o).forEach((m) => sc.add(m));
          if (cen === 'oceano') { const pier = new T.Group(); const tabua = M('#A0703F'), tabua2 = M('#8C5F33');
            for (let k = 0; k < 9; k++) { const tb = new T.Mesh(caixaGeo(4.2, 0.12, 0.34), k % 2 ? tabua : tabua2); tb.position.set(0, 0.42, -0.2 + k * 0.36); pier.add(tb); }
            [[-1.9, -0.2], [1.9, -0.2], [-1.9, 2.7], [1.9, 2.7]].forEach(([x, z]) => { const st = new T.Mesh(new T.CylinderGeometry(0.1, 0.1, 1.2, 6), tabua2); st.position.set(x, 0.0, z); pier.add(st); });
            sombra(pier); sc.add(pier); o.pier = pier; }
        }
        if (!marAberto && (cen === 'oceano' || cen === 'praia' || acao === 'inunda' || acao === 'seca' || acao === 'derrete')) {
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
        // v5 (14/11, dono: "melhorar o 3D, deixar ainda mais detalhista"): o diorama tinha chao, 2-3 arvores e gente.
        // Agora 30-40 detalhes pelo tipo de cenario (pedra, arbusto, flor, cerca, poste, placa, cone, caixote, osso...),
        // num anel que nao invade a praca central de quem atua.
        if (!o.interior && !globo) enfeitar(cen, r, sobre, o);
        for (let k = 0; k < (o.interior ? 0 : 4); k++) { const n = nuvem(r, hora === 'tempestade' || hora === 'cinza' ? '#9AA3B0' : '#FFFFFF'); n.userData = { a: r() * 6.28, h: 7 + r() * 3, d: 5 + r() * 4 }; sc.add(n); o.nuvens.push(n); }
        // gente: 1 protagonista no centro + figurantes; multidao = 14
        // v3: 'corre' fazia 12 bonecos tapando a acao; e quando a IA ja cria a pessoa (cn.criar), o protagonista
        // padrao ficava DUPLICADO ao lado dela. Agora: multidao so' quando a cena pede; pessoa criada = protagonista.
        const iaCriaPessoa = Array.isArray(cn.criar) && cn.criar.some((d) => d && d.modelo === 'pessoa');
        const n = acao === 'multidao' || acao === 'sem_ar' ? 12 : iaCriaPessoa ? 0 : acao === 'corre' ? 3 : Math.max(1, (cn.atores || ['pessoa']).length) + (cen === 'cidade' ? 2 : 1);
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
      const vo503 = U.lerp(-0.02, 0.06, U.suave(U.clamp((t - 3.0) / 0.5, 0, 1)));
      cam.setViewOffset(W, H, 0, Math.round(H * vo503), W, H);
      // v5 (14/11, dono: "mais ritmo, mais mudanca"): sem camera do roteiro, cada cena tem um PLANO diferente em rodizio
      // e cena com mais de 3,2 s ganha um CORTE no meio (vai para o rosto, ou do rosto para o aberto): a imagem muda a
      // cada ~1,5-2,5 s, como nos canais de referencia.
      const PLANOS = ['orbita', 'perto', 'baixo', 'cima', 'lateral', 'zoom_in'];
      const iCena = Math.max(0, spec.cenas.indexOf(cn));
      let cam0 = cn.camera || (o.globo ? 'orbita' : PLANOS[iCena % PLANOS.length]);
      if (!o.globo && !o.interior && D > 3.2 && local > D * 0.52) cam0 = cam0 === 'perto' ? 'orbita' : 'perto';
      if (!o.globo && o.interior && D > 3.2 && local > D * 0.52) cam0 = cam0 === 'perto' ? 'lateral' : 'perto';
      // v3: a camera ficava a 19 m -- gente com 15% da altura do quadro e metade de ceu/mar vazio. Agora ~14 m (25%).
      let ang = 0.5 * Math.sin(t * 0.21) + k * 0.55, dist = o.globo ? 15.5 : 14.5, alt = o.globo ? 2 : 6.2, alvoY = o.globo ? 0 : 1.5;
      if (cam0 === 'orbita') ang += k * 0.9;
      if (cam0 === 'zoom_in') dist *= U.lerp(1.12, 0.62, U.suave(k));
      if (cam0 === 'zoom_out') dist *= U.lerp(0.62, 0.95, U.suave(k));
      if (cam0 === 'sobrevoo') { alt = o.globo ? 9 : 16; dist *= 0.72; }
      if (cam0 === 'baixo') { dist *= 0.62; alt = 0.7; alvoY = 2.3; ang = 0.35 * Math.sin(t * 0.25) - 0.3; }   // contra-plongee: a ameaca fica grande
      if (cam0 === 'cima') { dist *= 0.5; alt = 12.5; alvoY = 0.6; ang = 0.2 + k * 0.5; }                      // de cima: mostra o espaco todo
      if (cam0 === 'lateral') { ang = 1.15 - k * 0.45; dist *= 0.78; alt *= 0.6; }                             // travelling lateral
      if (cam0 === 'perto') { dist *= o.globo ? 0.7 : 0.55; alt *= o.globo ? 1 : 0.42; alvoY = o.globo ? 0 : 1.7; ang = 0.25 * Math.sin(t * 0.3); }
      if (!o.globo && (acao === 'cresce') ) alvoY += U.saida(k) * 2.5;
      if (!o.globo && (acao === 'noite_eterna' || acao === 'aurora' || acao === 'lua_perto' || acao === 'impacto' || acao === 'chuva_meteoros' || acao === 'sol_cresce')) { alt *= 0.55; alvoY = 4 + 2 * U.suave(k); }
      if (o.interior) { dist = Math.min(dist, 9.5); alt = Math.min(alt, 4.2); ang = U.clamp(ang, -0.45, 0.6); alvoY = 1.4; }   // cozinha: dentro do comodo
      // empurrao de entrada: a cena chega 10% mais perto e assenta (substitui o flash)
      dist *= 1 - 0.1 * (1 - U.saida(U.clamp(local / 0.5, 0, 1)));
      // 14/11 (dono: imagens nao centralizadas): a camera girava em volta de (0,0) e o protagonista fica em z=1,6 -- com o giro
      // ele escorregava para o lado. Agora a camera sempre mira o protagonista.
      const foco = !o.globo ? (o.gente && o.gente[0] ? o.gente[0].userData.z0 : 1.6) : 0;
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
      // ---- v3: poca de areia movedica (aneis que se abrem) e o fogo do fogao tremendo
      if (o.poca) o.poca.userData.aneis.forEach((a, j) => { const q = (t * 0.55 + j / 3) % 1; a.scale.setScalar(1 + q * 2.6); a.material.opacity = 0.6 * (1 - q); });
      if (o.bocas) o.bocas.forEach((b, j) => { if (b.material.emissive) b.material.emissive.setRGB(1, 0.29 + 0.12 * Math.sin(t * 13 + j), 0); });
      // ---- mar aberto (v6): ondas, espuma que pulsa e corre, veleiros ao longe, gaivotas batendo asa
      if (o.oceano) { o.oceano.userData.ondas(t, 0.12);
        if (o.espuma) { o.espuma.position.y = 0.2 + Math.sin(t * 1.6) * 0.03; o.espuma.material.opacity = 0.55 + 0.25 * Math.sin(t * 1.3); o.espuma.userData.tx.offset.x = t * 0.05; o.espuma.scale.setScalar(1 + 0.012 * Math.sin(t * 1.6)); }
        (o.veleiros || []).forEach((b) => { const u = b.userData, a = u.a + t * 0.03; b.position.set(Math.cos(a) * u.d, 0.25 + Math.sin(t * 1.5 + u.a) * 0.08, Math.sin(a) * u.d); b.rotation.y = -a; b.rotation.z = Math.sin(t * 1.2 + u.a) * 0.06; });
        (o.gaivotas || []).forEach((gv) => { const u = gv.userData, a = u.a + t * u.v; gv.position.set(Math.cos(a) * u.d, u.h + Math.sin(t * 0.8 + u.a) * 0.3, Math.sin(a) * u.d - 1); gv.rotation.y = -a;
          gv.children.forEach((asa) => { asa.rotation.z = asa.userData.lado * 0.5 * Math.sin(t * 9 + u.a); }); }); }
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
        posar(p, modo, t, k, j === 0 ? falaEm(t) : 0);
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
        if (o.poca && j === 0) y -= 0.35 + 0.5 * U.suave(k);   // v3: quem esta na areia movedica afunda
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
    // v5 (14/11, dono: "mais informacao para prender"): NIVEL DE PERIGO que sobe a cada cena (1..5 marcas), com a cor
    // indo do verde ao vermelho; no fim do video, borda vermelha pulsando. A luz da cena esquenta junto.
    const ROT_PERIGO = /^es/i.test(spec.idioma || '') ? 'PELIGRO' : /^pt/i.test(spec.idioma || '') ? 'PERIGO' : 'DANGER';
    function perigo(i, t, local) {
      if (spec.titulo && t < 3.3) return;
      const N = spec.cenas.length, nivel = Math.min(5, 1 + Math.floor((i / Math.max(1, N - 1)) * 4.999)), ant = i > 0 ? Math.min(5, 1 + Math.floor(((i - 1) / Math.max(1, N - 1)) * 4.999)) : nivel;
      const cores = ['#5DBB63', '#B6D93A', '#FFD23F', '#FF9A3C', '#E8473C'];
      const sobe = nivel > ant ? U.mola(local - 0.1, 10) : 1;
      c.save(); c.translate(W / 2, 1490);
      const L = 520, h = 34, x0 = -L / 2;
      c.font = '40px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'bottom'; c.lineWidth = 8; c.strokeStyle = '#1B1B1B'; c.strokeText(ROT_PERIGO, 0, -12); c.fillStyle = '#FFFFFF'; c.fillText(ROT_PERIGO, 0, -12);
      for (let j = 0; j < 5; j++) {
        const x = x0 + j * (L / 5) + 6, w = L / 5 - 12, on = j < nivel - 1 || (j === nivel - 1);
        U.rr(c, x, 0, w, h, 10); c.fillStyle = 'rgba(0,0,0,0.45)'; c.fill();
        if (on) { const sc2 = j === nivel - 1 ? sobe : 1; c.save(); c.translate(x + w / 2, h / 2); c.scale(sc2, sc2); U.rr(c, -w / 2, -h / 2, w, h, 10); c.fillStyle = cores[j]; c.fill(); c.restore(); }
      }
      c.restore();
      if (nivel >= 5) { const a = 0.18 + 0.12 * Math.sin(t * 6); const g = c.createRadialGradient(W / 2, H / 2, H * 0.32, W / 2, H / 2, H * 0.7); g.addColorStop(0, 'rgba(232,71,60,0)'); g.addColorStop(1, 'rgba(232,71,60,' + a.toFixed(3) + ')'); c.fillStyle = g; c.fillRect(0, 0, W, H); }
      else if (nivel >= 3) { c.fillStyle = 'rgba(255,120,40,' + (0.035 * (nivel - 2)).toFixed(3) + ')'; c.fillRect(0, 0, W, H); }
    }
    // ---------------------------------------------------------------- esquema
    // v2 (14/11, dono: "na explicacao com imagem voce entendeu errado: ficou so' uma box a mais poluindo a tela; faca
    // aparecer ocupando a TELA INTEIRA explicando o que acontece -- a pessoa ingerindo agua salgada e gastando agua para
    // limpar -- e a entrada de cada elemento com efeito sonoro"). O esquema agora e' uma CENA DE INFOGRAFICO em tela cheia
    // (o 3D sai durante ela). `cena.esquema`:
    //   {tipo:'corpo', itens:[{alvo:'boca|estomago|sangue|rins|bexiga|pele|cerebro|coracao|pulmao', texto, fluxo?:'entra'|'sai', icone?}],
    //    balanco?:{entra:'BEBISTE', sai:'PIERDES', razao:1.3}}
    //   {tipo:'passos', itens:[{icone, texto}]}   {tipo:'barras', itens:[{texto, valor}], unidade?, sem_valor?}   {tipo:'medidor', texto, valor, max?, unidade?}
    // Cada item entra em ini + 0,35 + j*0,55 s (o som sai em montar_web.eventos_sonoros no mesmo tempo).
    const ESQ_T0 = 0.35, ESQ_DT = 0.55;
    const ICONES_ESQ = {
      gota: (g) => { g.beginPath(); g.moveTo(0, -0.85); g.bezierCurveTo(0.55, -0.15, 0.62, 0.2, 0.55, 0.38); g.arc(0, 0.32, 0.56, 0.1, Math.PI - 0.1); g.bezierCurveTo(-0.62, 0.2, -0.55, -0.15, 0, -0.85); g.fill(); },
      sal: (g) => { [[-0.35, 0.25], [0.3, 0.3], [0, -0.2], [-0.45, -0.35], [0.45, -0.25]].forEach(([x, y], j) => { g.save(); g.translate(x, y); g.rotate(j * 0.5); g.fillRect(-0.18, -0.18, 0.36, 0.36); g.restore(); }); },
      copo: (g) => { g.beginPath(); g.moveTo(-0.5, -0.7); g.lineTo(0.5, -0.7); g.lineTo(0.38, 0.75); g.lineTo(-0.38, 0.75); g.closePath(); g.globalAlpha = 0.35; g.fill(); g.globalAlpha = 1; g.beginPath(); g.moveTo(-0.45, -0.1); g.lineTo(0.45, -0.1); g.lineTo(0.38, 0.75); g.lineTo(-0.38, 0.75); g.closePath(); g.fill(); },
      rim: (g) => { [-1, 1].forEach((s) => { g.beginPath(); g.ellipse(s * 0.38, 0, 0.3, 0.55, 0, 0, Math.PI * 2); g.fill(); }); },
      sol: (g) => { g.beginPath(); g.arc(0, 0, 0.42, 0, Math.PI * 2); g.fill(); g.lineWidth = 0.14; for (let j = 0; j < 8; j++) { const a = j * Math.PI / 4; g.beginPath(); g.moveTo(Math.cos(a) * 0.58, Math.sin(a) * 0.58); g.lineTo(Math.cos(a) * 0.85, Math.sin(a) * 0.85); g.stroke(); } },
      fogo: (g) => { g.beginPath(); g.moveTo(0, -0.9); g.bezierCurveTo(0.5, -0.3, 0.7, 0.1, 0.5, 0.5); g.quadraticCurveTo(0.2, 0.85, 0, 0.85); g.quadraticCurveTo(-0.2, 0.85, -0.5, 0.5); g.bezierCurveTo(-0.7, 0.1, -0.3, -0.2, -0.15, -0.45); g.bezierCurveTo(-0.05, -0.2, 0.1, -0.45, 0, -0.9); g.fill(); },
      nuvem: (g) => { [[-0.4, 0.15, 0.32], [0, -0.1, 0.42], [0.42, 0.15, 0.32], [0, 0.25, 0.35]].forEach(([x, y, r]) => { g.beginPath(); g.arc(x, y, r, 0, Math.PI * 2); g.fill(); }); },
      pessoa: (g) => { g.beginPath(); g.arc(0, -0.52, 0.28, 0, Math.PI * 2); g.fill(); g.beginPath(); g.moveTo(-0.5, 0.85); g.quadraticCurveTo(-0.5, -0.15, 0, -0.15); g.quadraticCurveTo(0.5, -0.15, 0.5, 0.85); g.closePath(); g.fill(); },
      alerta: (g) => { g.beginPath(); g.moveTo(0, -0.85); g.lineTo(0.85, 0.7); g.lineTo(-0.85, 0.7); g.closePath(); g.fill(); g.fillStyle = '#FFFFFF'; g.fillRect(-0.08, -0.35, 0.16, 0.6); g.beginPath(); g.arc(0, 0.45, 0.1, 0, Math.PI * 2); g.fill(); },
      relogio: (g) => { g.lineWidth = 0.16; g.beginPath(); g.arc(0, 0, 0.72, 0, Math.PI * 2); g.stroke(); g.beginPath(); g.moveTo(0, 0); g.lineTo(0, -0.45); g.moveTo(0, 0); g.lineTo(0.32, 0.12); g.stroke(); },
      check: (g) => { g.lineWidth = 0.26; g.lineCap = 'round'; g.beginPath(); g.moveTo(-0.6, 0.05); g.lineTo(-0.15, 0.5); g.lineTo(0.65, -0.45); g.stroke(); },
      x: (g) => { g.lineWidth = 0.26; g.lineCap = 'round'; g.beginPath(); g.moveTo(-0.55, -0.55); g.lineTo(0.55, 0.55); g.moveTo(0.55, -0.55); g.lineTo(-0.55, 0.55); g.stroke(); },
      seta_cima: (g) => { g.beginPath(); g.moveTo(0, -0.85); g.lineTo(0.7, 0); g.lineTo(0.25, 0); g.lineTo(0.25, 0.8); g.lineTo(-0.25, 0.8); g.lineTo(-0.25, 0); g.lineTo(-0.7, 0); g.closePath(); g.fill(); },
      seta_baixo: (g) => { g.save(); g.rotate(Math.PI); ICONES_ESQ.seta_cima(g); g.restore(); },
      onda: (g) => { g.lineWidth = 0.18; g.lineCap = 'round'; [-0.35, 0.05, 0.45].forEach((y) => { g.beginPath(); for (let x = -0.8; x <= 0.8; x += 0.05) g.lineTo(x, y + Math.sin(x * 6) * 0.12); g.stroke(); }); },
      graos: (g) => { for (let j = 0; j < 14; j++) { const a = j * 2.4, r = 0.18 + (j % 4) * 0.17; g.beginPath(); g.arc(Math.cos(a) * r, Math.sin(a) * r, 0.11, 0, Math.PI * 2); g.fill(); } },
      casa: (g) => { g.beginPath(); g.moveTo(0, -0.8); g.lineTo(0.8, -0.1); g.lineTo(0.6, -0.1); g.lineTo(0.6, 0.75); g.lineTo(-0.6, 0.75); g.lineTo(-0.6, -0.1); g.lineTo(-0.8, -0.1); g.closePath(); g.fill(); g.fillStyle = '#FFFFFF'; g.fillRect(-0.15, 0.25, 0.3, 0.5); },
      raio: (g) => { g.beginPath(); g.moveTo(0.2, -0.9); g.lineTo(-0.45, 0.1); g.lineTo(-0.02, 0.1); g.lineTo(-0.2, 0.9); g.lineTo(0.5, -0.15); g.lineTo(0.05, -0.15); g.closePath(); g.fill(); },
    };
    const COR_ICONE = { gota: '#4FA8FF', sal: '#E8EDF2', copo: '#4FA8FF', rim: '#FF6B6B', sol: '#FFB13B', fogo: '#FF5A3C', nuvem: '#C9D3DC', pessoa: '#7FB2FF', alerta: '#FF5A3C',
      relogio: '#FFFFFF', check: '#3DDC84', x: '#FF5A3C', seta_cima: '#3DDC84', seta_baixo: '#FF5A3C', onda: '#4FA8FF', graos: '#E8C07A', casa: '#B99CFF', raio: '#FFD23F' };
    // fundo de infografico: azul-noite, grade fina, vinheta (pre-desenhado uma vez)
    const FUNDO_ESQ = U.camada(W, H, (g) => {
      const gr = g.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, '#0E2236'); gr.addColorStop(1, '#14324F'); g.fillStyle = gr; g.fillRect(0, 0, W, H);
      g.strokeStyle = 'rgba(255,255,255,0.05)'; g.lineWidth = 2; for (let x = 0; x < W; x += 60) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H); g.stroke(); } for (let y = 0; y < H; y += 60) { g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }
      const v = g.createRadialGradient(W / 2, H * 0.45, H * 0.2, W / 2, H * 0.5, H * 0.75); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.45)'); g.fillStyle = v; g.fillRect(0, 0, W, H);
    });
    // ORGAOS na silhueta (centro x, y do corpo de 1000 px de altura comecando em y=330)
    const CX_C = W / 2 - 110, Y_C = 330;
    const ORG = { boca: [0, 120], cerebro: [0, 45], estomago: [30, 400], sangue: [-70, 330], coracao: [-30, 300], pulmao: [40, 290], rins: [0, 470], bexiga: [0, 600], pele: [-140, 420] };
    function silhueta(g) {
      g.save(); g.translate(CX_C, Y_C); g.fillStyle = 'rgba(127,178,255,0.16)'; g.strokeStyle = '#7FB2FF'; g.lineWidth = 6;
      g.beginPath(); g.ellipse(0, 70, 78, 92, 0, 0, Math.PI * 2); g.fill(); g.stroke();                                   // cabeca
      g.beginPath(); g.moveTo(-34, 160); g.lineTo(34, 160); g.lineTo(40, 195); g.lineTo(150, 225); g.quadraticCurveTo(185, 240, 190, 300);
      g.lineTo(205, 560); g.lineTo(165, 565); g.lineTo(140, 330); g.lineTo(125, 600); g.lineTo(110, 990); g.lineTo(30, 990); g.lineTo(5, 650);
      g.lineTo(-5, 650); g.lineTo(-30, 990); g.lineTo(-110, 990); g.lineTo(-125, 600); g.lineTo(-140, 330); g.lineTo(-165, 565); g.lineTo(-205, 560);
      g.lineTo(-190, 300); g.quadraticCurveTo(-185, 240, -150, 225); g.lineTo(-40, 195); g.closePath(); g.fill(); g.stroke();
      // esofago/caminho (tracejado) e orgaos em contorno
      g.setLineDash([10, 10]); g.lineWidth = 4; g.strokeStyle = 'rgba(255,255,255,0.35)'; g.beginPath(); g.moveTo(0, 125); g.lineTo(0, 380); g.stroke(); g.setLineDash([]);
      g.restore();
    }
    function orgao(g, nome, aceso, t) {
      const [ox, oy] = ORG[nome] || ORG.estomago, x = CX_C + ox, y = Y_C + oy, pul = aceso ? 1 + 0.06 * Math.sin(t * 9) : 1;
      g.save(); g.translate(x, y); g.scale(pul, pul); g.lineWidth = 5; g.strokeStyle = aceso ? '#FFFFFF' : 'rgba(255,255,255,0.35)';
      const fill = (c2) => { g.fillStyle = aceso ? c2 : 'rgba(255,255,255,0.08)'; g.fill(); g.stroke(); };
      if (nome === 'estomago') { g.beginPath(); g.ellipse(0, 0, 60, 42, -0.5, 0, Math.PI * 2); fill('#FF9F45'); }
      else if (nome === 'rins') { [-1, 1].forEach((s) => { g.beginPath(); g.ellipse(s * 55, 0, 26, 42, s * 0.2, 0, Math.PI * 2); fill('#FF6B6B'); }); }
      else if (nome === 'bexiga') { g.beginPath(); g.ellipse(0, 0, 40, 34, 0, 0, Math.PI * 2); fill('#FFD23F'); }
      else if (nome === 'coracao') { g.beginPath(); g.moveTo(0, 30); g.bezierCurveTo(-55, -5, -30, -45, 0, -18); g.bezierCurveTo(30, -45, 55, -5, 0, 30); fill('#FF5A6E'); }
      else if (nome === 'pulmao') { [-1, 1].forEach((s) => { g.beginPath(); g.ellipse(s * 45 - 40, 0, 34, 62, 0, 0, Math.PI * 2); fill('#FF9FB0'); }); }
      else if (nome === 'cerebro') { g.beginPath(); g.ellipse(0, 0, 55, 38, 0, 0, Math.PI * 2); fill('#FFB3C7'); }
      else if (nome === 'boca') { g.beginPath(); g.ellipse(0, 0, 26, 12, 0, 0, Math.PI * 2); fill('#FF6B6B'); }
      else if (nome === 'sangue') { g.lineWidth = aceso ? 9 : 5; g.strokeStyle = aceso ? '#FF4A5A' : 'rgba(255,255,255,0.3)'; g.beginPath(); g.moveTo(0, -60); g.bezierCurveTo(40, 0, -40, 60, 0, 160); g.stroke(); g.beginPath(); g.moveTo(140, -40); g.bezierCurveTo(120, 60, 160, 120, 130, 200); g.stroke(); }
      else if (nome === 'pele') { g.lineWidth = aceso ? 10 : 4; g.strokeStyle = aceso ? '#4FA8FF' : 'rgba(255,255,255,0.25)'; g.beginPath(); g.arc(140, -40, 90, Math.PI * 0.6, Math.PI * 1.4); g.stroke(); }
      g.restore(); return [x, y];
    }
    function particulas(g, de, ate, local, tipo, n) {   // fluxo animado (posicoes calculadas de t, sem estado)
      for (let k = 0; k < n; k++) { const q = ((local * 0.9 + k / n) % 1), x = U.lerp(de[0], ate[0], q) + Math.sin(q * 9 + k) * 12, y = U.lerp(de[1], ate[1], q);
        g.save(); g.translate(x, y); g.scale(14, 14); g.globalAlpha = Math.sin(q * Math.PI); g.fillStyle = tipo === 'sal' ? '#F2F5F8' : '#4FA8FF'; (ICONES_ESQ[tipo] || ICONES_ESQ.gota)(g); g.restore(); }
    }
    function etiqueta(g, txt, x, y, ax, ay, s, cor) {
      g.save(); g.lineWidth = 5; g.strokeStyle = '#FFFFFF'; g.beginPath(); g.moveTo(ax, ay); g.lineTo(x - 20, y); g.stroke(); g.beginPath(); g.arc(ax, ay, 9, 0, Math.PI * 2); g.fillStyle = '#FFF'; g.fill();
      g.translate(x, y); g.scale(s, s); g.font = '52px "Lilita One", sans-serif'; g.textAlign = 'left'; g.textBaseline = 'middle';
      const ls = U.linhas(g, String(txt || '').toUpperCase(), 330).slice(0, 3), w = Math.max(...ls.map((l) => g.measureText(l).width)) + 50, h = ls.length * 58 + 34;
      U.rr(g, -10, -h / 2, w, h, 26); g.fillStyle = cor || '#FFD23F'; g.fill(); g.fillStyle = '#111'; ls.forEach((l, q) => g.fillText(l, 15, -h / 2 + 46 + q * 58)); g.restore();
    }
    function esquema(cn, t) {
      const e = cn.esquema; if (!e || typeof e !== 'object') return false;
      const local = t - cn.ini, D = cn.fim - cn.ini;
      const ent = U.saida(U.clamp(local / 0.25, 0, 1)), sai = U.clamp((local - (D - 0.2)) / 0.2, 0, 1);
      c.save(); c.globalAlpha = ent * (1 - sai * 0.0); c.drawImage(FUNDO_ESQ, 0, 0); c.restore();
      if (ent < 0.98) return true;
      const itens = (Array.isArray(e.itens) ? e.itens : []).slice(0, 4);
      const tj = (j) => local - ESQ_T0 - j * ESQ_DT;
      const fonte = (px) => { c.font = px + 'px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; };
      if (e.tipo === 'corpo') {
        silhueta(c);
        const acesos = new Set(itens.filter((it, j) => tj(j) >= 0).map((it) => it.alvo));
        Object.keys(ORG).forEach((o) => { if (o !== 'pele' && o !== 'sangue') orgao(c, o, acesos.has(o), t); });
        ['sangue', 'pele'].forEach((o) => { if (acesos.has(o)) orgao(c, o, true, t); });
        itens.forEach((it, j) => { const q = tj(j); if (q < 0) return;
          const [ox, oy] = ORG[it.alvo] || ORG.estomago, x = CX_C + ox, y = Y_C + oy, s = U.mola(q, 10);
          if (it.fluxo === 'entra') particulas(c, [x + 260, y - 160], [CX_C, Y_C + 125], local, it.icone === 'sal' ? 'sal' : 'gota', 7);
          if (it.fluxo === 'entra' && it.icone !== 'sal') particulas(c, [x + 300, y - 120], [CX_C, Y_C + 125], local + 0.5, 'sal', 4);
          if (it.fluxo === 'sai') particulas(c, [x, y + 20], [x - 60, Y_C + 1020], local, 'gota', 8);
          if (it.alvo === 'estomago' || it.alvo === 'sangue') particulas(c, [CX_C, Y_C + 160], [x, y], local, 'sal', 5);
          etiqueta(c, it.texto, W - 400, Y_C + 60 + j * 230, x + (ox > 0 ? 60 : 30), y, s, it.fluxo === 'sai' ? '#7FD0FF' : '#FFD23F'); });
        if (e.balanco) { const q = tj(itens.length); if (q > 0) { const s = U.saida(U.clamp(q / 0.6, 0, 1)), r2 = Number(e.balanco.razao) || 1.3, L = 360;
          c.save(); c.translate(W - 410, 1210); fonte(40); c.textAlign = 'left';
          [[e.balanco.entra || 'ENTRA', 1 / r2, '#3DDC84'], [e.balanco.sai || 'SAI', 1, '#FF5A3C']].forEach(([txt, f, cor], k) => {
            c.fillStyle = '#FFF'; c.fillText(String(txt).toUpperCase(), 0, k * 80 - 22); U.rr(c, 0, k * 80, L, 30, 15); c.fillStyle = 'rgba(255,255,255,0.15)'; c.fill();
            U.rr(c, 0, k * 80, Math.max(10, L * f * s), 30, 15); c.fillStyle = cor; c.fill(); }); c.restore(); } }
      } else if (e.tipo === 'barras' && itens.length) {
        const vmax = Math.max(...itens.map((it) => Math.abs(Number(it.valor) || 0)), 1e-9), L = W - 200;
        itens.forEach((it, j) => { const q = U.saida(U.clamp(tj(j) / 0.7, 0, 1)); if (q <= 0) return; const y = 560 + j * 230, x0 = 100;
          fonte(64); c.textAlign = 'left'; c.fillStyle = '#FFF'; c.fillText(String(it.texto || '').toUpperCase().slice(0, 26), x0, y - 50, L);
          U.rr(c, x0, y, L, 80, 40); c.fillStyle = 'rgba(255,255,255,0.12)'; c.fill(); U.rr(c, x0, y, Math.max(20, L * (Math.abs(Number(it.valor) || 0) / vmax) * q), 80, 40); c.fillStyle = j === 0 ? '#FF5A3C' : '#4FA8FF'; c.fill();
          if (!e.sem_valor) { const v = (Number(it.valor) || 0) * q; fonte(60); c.textAlign = 'right'; c.fillStyle = '#FFF'; c.fillText((Math.abs(v) >= 10 ? Math.round(v) : v.toFixed(1)).toString().replace('.', ',') + (e.unidade ? ' ' + e.unidade : ''), x0 + L, y - 50); } });
      } else if (e.tipo === 'medidor') {
        const q = U.saida(U.clamp(tj(0) / 1.0, 0, 1)), vmax = Number(e.max) || 100, v = U.clamp((Number(e.valor) || 0) / vmax, 0, 1) * q, cx = W / 2, cy = 900, R = 300;
        fonte(72); c.fillStyle = '#FFF'; c.fillText(String(e.texto || '').toUpperCase().slice(0, 26), cx, 480, W - 100);
        c.lineWidth = 80; c.lineCap = 'round'; c.beginPath(); c.arc(cx, cy, R, Math.PI, 2 * Math.PI); c.strokeStyle = 'rgba(255,255,255,0.12)'; c.stroke();
        const gr = c.createLinearGradient(cx - R, 0, cx + R, 0); gr.addColorStop(0, '#3DDC84'); gr.addColorStop(0.5, '#FFD23F'); gr.addColorStop(1, '#FF5A3C');
        c.beginPath(); c.arc(cx, cy, R, Math.PI, Math.PI + Math.PI * Math.max(0.001, v)); c.strokeStyle = gr; c.stroke();
        const a = Math.PI + Math.PI * v; c.lineWidth = 16; c.strokeStyle = '#FFF'; c.beginPath(); c.moveTo(cx, cy); c.lineTo(cx + Math.cos(a) * (R - 30), cy + Math.sin(a) * (R - 30)); c.stroke();
        c.beginPath(); c.arc(cx, cy, 30, 0, Math.PI * 2); c.fillStyle = '#FFF'; c.fill();
        fonte(120); c.fillStyle = '#FFD23F'; c.fillText(Math.round((Number(e.valor) || 0) * q) + (e.unidade ? ' ' + e.unidade : '%'), cx, cy + 130);
      } else if (itens.length) {   // passos: linhas grandes com icone, texto e seta para baixo
        const n = itens.length, passo = Math.min(300, 880 / n), y0 = 640 - (n - 1) * passo / 2 + 150;
        itens.forEach((it, j) => { const q = tj(j); if (q < 0) return; const s = U.mola(q, 10), y = y0 + j * passo;
          if (j > 0) { const k = U.saida(U.clamp(q / 0.25, 0, 1)); c.save(); c.globalAlpha = k; c.fillStyle = '#FFFFFF'; c.beginPath(); const ya = y - passo / 2 + 10 * k;
            c.moveTo(250 - 28, ya - 22); c.lineTo(250 + 28, ya - 22); c.lineTo(250, ya + 18); c.closePath(); c.fill(); c.restore(); }
          c.save(); c.translate(250, y); c.scale(s, s); c.beginPath(); c.arc(0, 0, 105, 0, Math.PI * 2); c.fillStyle = 'rgba(255,255,255,0.1)'; c.fill(); c.lineWidth = 8; c.strokeStyle = COR_ICONE[it.icone] || '#FFF'; c.stroke();
          c.save(); c.scale(70, 70); c.fillStyle = c.strokeStyle = COR_ICONE[it.icone] || '#FFF'; c.lineWidth = 0.15; (ICONES_ESQ[it.icone] || ICONES_ESQ.alerta)(c); c.restore(); c.restore();
          c.save(); c.globalAlpha = U.clamp(q / 0.25, 0, 1); c.font = '70px "Lilita One", sans-serif'; c.textAlign = 'left'; c.textBaseline = 'middle'; c.fillStyle = '#FFF';
          const ls = U.linhas(c, String(it.texto || '').toUpperCase(), 560).slice(0, 2); ls.forEach((l, k) => c.fillText(l, 400, y + (k - (ls.length - 1) / 2) * 76)); c.restore(); });
      }
      return true;
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
      const ctaOn = t > (Number(spec.dur_s) || 0) - 2.8;
      if (!ctaOn) perigo(i, t, local);
      seloTempo(cn, t);
      if (!esquema(cn, t)) cartaoNumero(cn, t);   // com esquema, o numero ja esta nele
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 170, fundo: '#FFD23F', borda: '#1B1B1B', cor: '#1B1B1B', altura_linha: 100, dur: 3.0 });
      U.ctaFinal(c, spec, t);
      U.legenda(c, spec, t, { fonte: '104px "Lilita One", sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#FFD23F', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro, dispose: () => { cenas.forEach(o => U3.liberarCena(o.sc)); R.dispose(); R.forceContextLoss(); } };
  }
  MOTORES.lowpoly = { criar };
})();
