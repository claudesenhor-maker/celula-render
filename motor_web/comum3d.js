// BASE 3D comum (23/10, pedido do dono: motores 3D "mais detalhistas e com fundo").
//
// Usada pelos estilos que desenham em three.js (mecanismo, escala). Tres coisas:
//   U3.estudio(R, sc, ...)  luz realista: reflexo de ambiente (RoomEnvironment),
//                           tom de cinema (ACES) e sombra macia no chao.
//   U3.formas(T)            biblioteca de pecas lisas e detalhadas (caixa de
//                           canto arredondado, parafuso com rosca, capsula...).
//   U3.ambiente(...)        o LUGAR onde o objeto esta (oficina, cozinha,
//                           banheiro, garagem, escritorio, laboratorio, externo,
//                           prancheta): parede e piso desenhados por codigo, com
//                           nevoa para o fundo nao brigar com o objeto.
// Tudo e' dado + codigo nosso; nenhuma imagem de fora.
(function (G) {
  'use strict';
  const U3 = {};

  // ------------------------------------------------------------------ luz
  U3.estudio = function (R, sc, T, opc) {
    opc = Object.assign({}, window.U3_TESTE || {}, opc || {});
    R.outputEncoding = T.sRGBEncoding;
    R.toneMapping = T.ACESFilmicToneMapping;
    R.toneMappingExposure = opc.exposicao || 1.05;
    R.shadowMap.enabled = opc.sombra !== false;
    R.shadowMap.type = T.PCFShadowMap;
    // o reflexo NAO vai em sc.environment: no Chrome sem GPU (Actions) ele custava
    // +1,25 s por quadro em TODO pixel. Fica so' nos materiais que refletem de
    // verdade (metal, vidro, ceramica) -- `U3.material` pega daqui.
    U3._env = null;
    if (T.RoomEnvironment && opc.reflexo !== false) {
      const pm = new T.PMREMGenerator(R);
      U3._env = pm.fromScene(new T.RoomEnvironment(), 0.04).texture;
      pm.dispose();
    }
  };
  // luz principal com sombra, enquadrada no tamanho do objeto
  U3.luzComSombra = function (T, sc, tam, cor, intens, pos) {
    const l = new T.DirectionalLight(cor || '#ffffff', intens == null ? 1.6 : intens);
    l.position.set(...(pos || [tam * 0.9, tam * 1.6, tam * 1.1]));
    l.castShadow = true; l.shadow.mapSize.set(1024, 1024); l.shadow.bias = -0.0006; l.shadow.radius = 3;
    const s = l.shadow.camera; s.left = s.bottom = -tam * 1.6; s.right = s.top = tam * 1.6; s.near = 0.01; s.far = tam * 8;
    sc.add(l); sc.add(l.target); return l;
  };

  // ------------------------------------------------------------------ formas
  // `liso`: curvas com segmentos de sobra (o flatShading facetado lia como "jogo
  // de 2005"); `caixa` com canto arredondado pequeno (canto vivo perfeito e' o
  // que mais denuncia computacao grafica barata).
  U3.formas = function (T) {
    const caixaArred = () => {
      const r = 0.06, s = new T.Shape(), w = 0.5 - r, h = 0.5 - r;
      s.moveTo(-w, -0.5); s.lineTo(w, -0.5); s.quadraticCurveTo(0.5, -0.5, 0.5, -h); s.lineTo(0.5, h); s.quadraticCurveTo(0.5, 0.5, w, 0.5);
      s.lineTo(-w, 0.5); s.quadraticCurveTo(-0.5, 0.5, -0.5, h); s.lineTo(-0.5, -h); s.quadraticCurveTo(-0.5, -0.5, -w, -0.5);
      const g = new T.ExtrudeGeometry(s, { depth: 1 - 2 * r, bevelEnabled: true, bevelThickness: r, bevelSize: 0, bevelSegments: 3, curveSegments: 4 });
      g.translate(0, 0, -(1 - 2 * r) / 2); g.computeVertexNormals(); return g;
    };
    const engrenagem = (dentes) => {
      const s = new T.Shape(), n = dentes || 14, r1 = 0.5, r2 = 0.41;
      for (let i = 0; i < n; i++) {
        const a0 = (i / n) * Math.PI * 2, d = (Math.PI * 2) / n;
        const p = [[r2, a0], [r1, a0 + d * 0.18], [r1, a0 + d * 0.45], [r2, a0 + d * 0.63]];
        p.forEach(([r, a], j) => { const x = Math.cos(a) * r, y = Math.sin(a) * r; if (i === 0 && j === 0) s.moveTo(x, y); else s.lineTo(x, y); });
      }
      const furo = new T.Path(); furo.absarc(0, 0, 0.1, 0, Math.PI * 2, true); s.holes.push(furo);
      for (let k = 0; k < 4; k++) { const a = k * Math.PI / 2 + 0.4, h = new T.Path(); h.absarc(Math.cos(a) * 0.25, Math.sin(a) * 0.25, 0.06, 0, Math.PI * 2, true); s.holes.push(h); }
      const g = new T.ExtrudeGeometry(s, { depth: 0.16, bevelEnabled: true, bevelThickness: 0.02, bevelSize: 0.012, bevelSegments: 2, curveSegments: 10 });
      g.translate(0, 0, -0.08); g.rotateX(Math.PI / 2); return g;
    };
    const mola = () => {
      const pts = []; for (let i = 0; i <= 200; i++) { const a = i * 0.42; pts.push(new T.Vector3(Math.cos(a) * 0.4, -0.5 + i / 200, Math.sin(a) * 0.4)); }
      return new T.TubeGeometry(new T.CatmullRomCurve3(pts), 320, 0.045, 10, false);
    };
    // parafuso: haste + rosca helicoidal + cabeca sextavada com fenda
    const parafuso = () => {
      const gs = [];
      const haste = new T.CylinderGeometry(0.16, 0.16, 0.8, 24); haste.translate(0, -0.1, 0); gs.push(haste);
      const pts = []; for (let i = 0; i <= 180; i++) { const a = i * 0.55; pts.push(new T.Vector3(Math.cos(a) * 0.17, -0.48 + i * 0.0042, Math.sin(a) * 0.17)); }
      gs.push(new T.TubeGeometry(new T.CatmullRomCurve3(pts), 260, 0.03, 6, false));
      const cab = new T.CylinderGeometry(0.32, 0.32, 0.2, 6); cab.translate(0, 0.4, 0); gs.push(cab);
      return juntar(gs);
    };
    // capsula: cilindro com duas meias-esferas (torno)
    const capsula = () => {
      const p = []; for (let i = 0; i <= 10; i++) { const a = -Math.PI / 2 + (i / 10) * (Math.PI / 2); p.push(new T.Vector2(Math.cos(a) * 0.3, -0.2 + Math.sin(a) * 0.3)); }
      for (let i = 0; i <= 10; i++) { const a = (i / 10) * (Math.PI / 2); p.push(new T.Vector2(Math.cos(a) * 0.3, 0.2 + Math.sin(a) * 0.3)); }
      return new T.LatheGeometry(p, 28);
    };
    const helice = () => {
      const gs = [new T.CylinderGeometry(0.1, 0.1, 0.16, 20)];
      for (let k = 0; k < 3; k++) { const b = new T.SphereGeometry(0.5, 16, 8); b.scale(0.2, 0.03, 0.95); b.translate(0, 0, 0.5); b.rotateZ(0.35); b.rotateY((k * Math.PI * 2) / 3); gs.push(b); }
      return juntar(gs);
    };
    const meiaEsfera = () => new T.SphereGeometry(0.5, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2);
    const seta = () => { const g = new T.ConeGeometry(0.3, 0.5, 20); g.translate(0, 0.25, 0); return g; };
    // junta geometrias nao indexadas (r128 nao traz o BufferGeometryUtils global)
    function juntar(gs) {
      const ns = gs.map((g) => (g.index ? g.toNonIndexed() : g));
      let n = 0; ns.forEach((g) => { n += g.attributes.position.count; });
      const pos = new Float32Array(n * 3), nor = new Float32Array(n * 3); let o = 0;
      ns.forEach((g) => { pos.set(g.attributes.position.array, o * 3); nor.set(g.attributes.normal.array, o * 3); o += g.attributes.position.count; });
      const out = new T.BufferGeometry(); out.setAttribute('position', new T.BufferAttribute(pos, 3)); out.setAttribute('normal', new T.BufferAttribute(nor, 3)); return out;
    }
    return {
      caixa: caixaArred, cubo: caixaArred, caixa_viva: () => new T.BoxGeometry(1, 1, 1),
      esfera: () => new T.SphereGeometry(0.5, 40, 24), meia_esfera: meiaEsfera,
      cone: () => new T.ConeGeometry(0.5, 1, 40), cilindro: () => new T.CylinderGeometry(0.5, 0.5, 1, 40),
      tubo: () => new T.CylinderGeometry(0.5, 0.5, 1, 40, 1, true), disco: () => new T.CylinderGeometry(0.5, 0.5, 0.08, 48),
      lamina: () => { const g = caixaArred(); g.scale(1, 0.06, 1); return g; },
      anel: () => new T.TorusGeometry(0.42, 0.06, 16, 48), toro: () => new T.TorusGeometry(0.4, 0.12, 20, 48),
      icosa: () => new T.IcosahedronGeometry(0.5, 0), piramide: () => new T.ConeGeometry(0.6, 1, 4),
      engrenagem: () => engrenagem(14), engrenagem_pequena: () => engrenagem(9), mola, seta, parafuso, capsula, helice,
    };
  };
  // curvas lisas (as outras ficam com a normal da propria forma)
  U3.FORMAS_LISAS = ['esfera', 'meia_esfera', 'cone', 'cilindro', 'tubo', 'disco', 'anel', 'toro', 'mola', 'capsula', 'helice', 'seta'];

  // ------------------------------------------------------------------ materiais
  const MATERIAIS = {
    metal: { roughness: 0.28, metalness: 0.9 }, aco: { roughness: 0.32, metalness: 0.95 }, cromado: { roughness: 0.08, metalness: 1 },
    latao: { roughness: 0.3, metalness: 0.9 }, plastico: { roughness: 0.42, metalness: 0 }, borracha: { roughness: 0.92, metalness: 0 },
    madeira: { roughness: 0.75, metalness: 0 }, vidro: { roughness: 0.05, metalness: 0, opacity: 0.32 }, ceramica: { roughness: 0.22, metalness: 0 },
    tecido: { roughness: 1, metalness: 0 }, pedra: { roughness: 0.9, metalness: 0 },
  };
  U3.material = function (T, cor, tipo, metalAntigo) {
    const m = MATERIAIS[String(tipo || '').toLowerCase()] || (metalAntigo ? MATERIAIS.metal : MATERIAIS.plastico);
    const reflete = m.metalness > 0.5 || m.opacity || m.roughness < 0.25;
    const mat = new T.MeshStandardMaterial({ color: cor, roughness: m.roughness, metalness: m.metalness, transparent: true, opacity: m.opacity || 1,
      envMap: reflete ? U3._env : null, envMapIntensity: 1 });
    // a saida e' sRGB (U3.estudio): a cor em hex precisa ir para o espaco linear,
    // senao tudo sai lavado, cor de pastel
    mat.color.convertSRGBToLinear();
    mat.userData.opacidadeBase = m.opacity || 1;
    return mat;
  };

  // ------------------------------------------------------------------ texturas
  function tela(w, h) { const cv = document.createElement('canvas'); cv.width = w; cv.height = h; return [cv, cv.getContext('2d')]; }
  function rng(s) { let x = s >>> 0 || 1; return () => { x ^= x << 13; x >>>= 0; x ^= x >>> 17; x ^= x << 5; x >>>= 0; return (x % 100000) / 100000; }; }
  function tex(T, cv, rx, ry) { const t = new T.CanvasTexture(cv); t.encoding = T.sRGBEncoding; t.wrapS = t.wrapT = T.RepeatWrapping; t.repeat.set(rx || 1, ry || 1); t.anisotropy = 2; return t; }
  const PINTA = {
    madeira(g, w, h, r, base) {
      g.fillStyle = base || '#9A6B43'; g.fillRect(0, 0, w, h);
      const tab = 6; for (let i = 0; i < tab; i++) { const y0 = (i * h) / tab; g.fillStyle = `rgba(${60 + r() * 40},${35 + r() * 25},${15},${0.12 + r() * 0.12})`; g.fillRect(0, y0, w, h / tab);
        for (let k = 0; k < 26; k++) { g.strokeStyle = `rgba(60,35,15,${0.06 + r() * 0.12})`; g.lineWidth = 1 + r() * 2; g.beginPath(); const yy = y0 + r() * h / tab; g.moveTo(0, yy); for (let x = 0; x <= w; x += 32) g.lineTo(x, yy + Math.sin(x * 0.01 + k) * 3); g.stroke(); }
        g.fillStyle = 'rgba(30,18,8,0.55)'; g.fillRect(0, y0, w, 3); }
    },
    azulejo(g, w, h, r, cor, rejunte, n) {
      g.fillStyle = rejunte; g.fillRect(0, 0, w, h); const cx = n || 8, cy = Math.round((n || 8) * h / w), lw = w / cx, lh = h / cy;
      for (let i = 0; i < cx; i++) for (let j = 0; j < cy; j++) { const v = 0.94 + r() * 0.08; g.fillStyle = cor; g.globalAlpha = v; g.fillRect(i * lw + 3, j * lh + 3, lw - 6, lh - 6); g.globalAlpha = 1;
        const gr = g.createLinearGradient(i * lw, j * lh, i * lw + lw, j * lh + lh); gr.addColorStop(0, 'rgba(255,255,255,0.18)'); gr.addColorStop(1, 'rgba(0,0,0,0.05)'); g.fillStyle = gr; g.fillRect(i * lw + 3, j * lh + 3, lw - 6, lh - 6); }
    },
    metro(g, w, h, r) { // azulejo de metro (cozinha)
      g.fillStyle = '#C9CCCF'; g.fillRect(0, 0, w, h); const lw = w / 6, lh = lw / 2;
      for (let j = 0; j * lh < h; j++) for (let i = -1; i < 7; i++) { const x = i * lw + (j % 2 ? lw / 2 : 0); g.fillStyle = `hsl(200,10%,${93 + r() * 4}%)`; g.fillRect(x + 3, j * lh + 3, lw - 6, lh - 6); }
    },
    concreto(g, w, h, r, base) {
      g.fillStyle = base || '#8D9196'; g.fillRect(0, 0, w, h);
      for (let k = 0; k < 2600; k++) { const v = r(); g.fillStyle = v > 0.5 ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.06)'; const s = 2 + r() * 10; g.fillRect(r() * w, r() * h, s, s); }
      for (let k = 0; k < 6; k++) { const gr = g.createRadialGradient(r() * w, r() * h, 0, r() * w, r() * h, 80 + r() * 160); gr.addColorStop(0, 'rgba(0,0,0,0.10)'); gr.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gr; g.fillRect(0, 0, w, h); }
    },
    furos(g, w, h, r) { // painel perfurado de oficina
      g.fillStyle = '#C8A77A'; g.fillRect(0, 0, w, h); g.fillStyle = 'rgba(60,40,20,0.55)';
      for (let x = 16; x < w; x += 32) for (let y = 16; y < h; y += 32) { g.beginPath(); g.arc(x, y, 4, 0, Math.PI * 2); g.fill(); }
      g.strokeStyle = 'rgba(40,40,45,0.85)'; g.lineWidth = 10; g.lineCap = 'round';
      for (let k = 0; k < 7; k++) { const x = 60 + r() * (w - 120), y = 80 + r() * (h * 0.5); g.beginPath(); g.moveTo(x, y); g.lineTo(x + (r() - 0.5) * 30, y + 70 + r() * 90); g.stroke(); g.beginPath(); g.arc(x, y, 14, 0, Math.PI * 2); g.stroke(); }
    },
    pintura(g, w, h, r, cor) {
      g.fillStyle = cor; g.fillRect(0, 0, w, h);
      for (let k = 0; k < 1200; k++) { g.fillStyle = r() > 0.5 ? 'rgba(255,255,255,0.025)' : 'rgba(0,0,0,0.03)'; g.fillRect(r() * w, r() * h, 3, 3); }
      g.fillStyle = 'rgba(0,0,0,0.12)'; g.fillRect(0, h * 0.86, w, 6); g.fillStyle = 'rgba(255,255,255,0.5)'; g.fillRect(0, h * 0.86 + 6, w, h * 0.14);
    },
    prancheta(g, w, h) {
      const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#0E2340'); gr.addColorStop(1, '#2A6299'); g.fillStyle = gr; g.fillRect(0, 0, w, h);
      g.strokeStyle = 'rgba(160,200,255,0.18)'; g.lineWidth = 1; for (let x = 0; x < w; x += 32) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h); g.stroke(); } for (let y = 0; y < h; y += 32) { g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke(); }
      g.strokeStyle = 'rgba(160,200,255,0.32)'; g.lineWidth = 2; for (let x = 0; x < w; x += 160) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, h); g.stroke(); }
    },
    ceu(g, w, h, r) {
      const gr = g.createLinearGradient(0, 0, 0, h); gr.addColorStop(0, '#3E7FD1'); gr.addColorStop(0.62, '#A9D6FF'); gr.addColorStop(0.8, '#E3F3FF'); gr.addColorStop(0.8, '#8FB07A'); gr.addColorStop(1, '#6E8F5E'); g.fillStyle = gr; g.fillRect(0, 0, w, h);
      for (let k = 0; k < 9; k++) { const x = r() * w, y = h * (0.12 + r() * 0.35), s = 40 + r() * 70; g.fillStyle = 'rgba(255,255,255,0.85)'; for (let j = 0; j < 5; j++) { g.beginPath(); g.ellipse(x + j * s * 0.45, y + Math.sin(j) * 8, s * 0.6, s * 0.35, 0, 0, Math.PI * 2); g.fill(); } }
      g.fillStyle = '#7F9A8B'; g.beginPath(); g.moveTo(0, h * 0.8); for (let x = 0; x <= w; x += 40) g.lineTo(x, h * (0.72 + 0.06 * Math.sin(x * 0.012) + 0.03 * Math.sin(x * 0.05))); g.lineTo(w, h * 0.8); g.fill();
    },
    grama(g, w, h, r) {
      g.fillStyle = '#7FA65F'; g.fillRect(0, 0, w, h);
      for (let k = 0; k < 9000; k++) { g.fillStyle = `hsla(${88 + r() * 30},${40 + r() * 20}%,${30 + r() * 25}%,0.5)`; g.fillRect(r() * w, r() * h, 2, 5); }
    },
  };
  // [parede, piso, cor da nevoa, intensidade do sol]
  const AMBIENTES = {
    oficina: { parede: (g, w, h, r) => PINTA.furos(g, w, h, r), piso: (g, w, h, r) => PINTA.madeira(g, w, h, r), nevoa: '#3A2E24', luz: '#FFE2B8' },
    cozinha: { parede: (g, w, h, r) => PINTA.metro(g, w, h, r), piso: (g, w, h, r) => PINTA.concreto(g, w, h, r, '#5E5A57'), nevoa: '#B9B4AC', luz: '#FFF4E2' },
    banheiro: { parede: (g, w, h, r) => PINTA.azulejo(g, w, h, r, '#BFE3F2', '#E8F1F4', 6), piso: (g, w, h, r) => PINTA.azulejo(g, w, h, r, '#F2F4F5', '#B9C3C8', 5), nevoa: '#BCD7E2', luz: '#F2FAFF' },
    garagem: { parede: (g, w, h, r) => { PINTA.concreto(g, w, h, r, '#6F747A'); for (let x = -h; x < w; x += 60) { g.fillStyle = (Math.floor(x / 60) % 2) ? '#F2C230' : '#222'; g.beginPath(); g.moveTo(x, h * 0.78); g.lineTo(x + 60, h * 0.78); g.lineTo(x + 90, h * 0.86); g.lineTo(x + 30, h * 0.86); g.fill(); } },
      piso: (g, w, h, r) => PINTA.concreto(g, w, h, r, '#7D8186'), nevoa: '#3D4248', luz: '#FFFFFF' },
    escritorio: { parede: (g, w, h, r) => PINTA.pintura(g, w, h, r, '#5E7D8C'), piso: (g, w, h, r) => PINTA.madeira(g, w, h, r, '#7B5638'), nevoa: '#3F525C', luz: '#FFF1DD' },
    laboratorio: { parede: (g, w, h, r) => PINTA.azulejo(g, w, h, r, '#F4F6F8', '#D5DADF', 4), piso: (g, w, h, r) => PINTA.concreto(g, w, h, r, '#6F7A84'), nevoa: '#DDE3E8', luz: '#F4FAFF' },
    externo: { parede: (g, w, h, r) => PINTA.ceu(g, w, h, r), piso: (g, w, h, r) => PINTA.grama(g, w, h, r), nevoa: '#CFE6F7', luz: '#FFF6E8' },
    prancheta: { parede: (g, w, h) => PINTA.prancheta(g, w, h), piso: (g, w, h) => PINTA.prancheta(g, w, h), nevoa: '#1D4A7A', luz: '#FFFFFF' },
  };
  U3.AMBIENTES = Object.keys(AMBIENTES);
  // ceu de fundo (escala): gradiente + nuvens, preso na tela (a camera do escala
  // olha de frente, quase ao rés do chao). O chao se funde nele pela nevoa.
  U3.ceu = function (T, semente) {
    const r = rng(semente || 3), [cv, g] = tela(512, 1024);
    const gr = g.createLinearGradient(0, 0, 0, 1024); gr.addColorStop(0, '#2F6FC4'); gr.addColorStop(0.55, '#8CC4F2'); gr.addColorStop(1, '#DDEFFF'); g.fillStyle = gr; g.fillRect(0, 0, 512, 1024);
    for (let k = 0; k < 7; k++) { const x = r() * 512, y = 120 + r() * 420, s = 26 + r() * 40, a = 0.55 + r() * 0.35;
      for (let j = 0; j < 6; j++) { g.fillStyle = `rgba(255,255,255,${a})`; g.beginPath(); g.ellipse(x + (j - 2.5) * s * 0.5, y + Math.sin(j * 1.7) * s * 0.18, s * 0.62, s * 0.36, 0, 0, Math.PI * 2); g.fill(); }
      g.fillStyle = 'rgba(160,190,220,0.25)'; g.beginPath(); g.ellipse(x, y + s * 0.25, s * 1.6, s * 0.18, 0, 0, Math.PI * 2); g.fill(); }
    const t = new T.CanvasTexture(cv); t.encoding = T.sRGBEncoding; return t;
  };
  U3.textura = function (T, tipo, semente, rep) {
    const r = rng(semente || 5), [cv, g] = tela(512, 512); (PINTA[tipo] || PINTA.grama)(g, 512, 512, r); return tex(T, cv, rep || 1, rep || 1);
  };
  // a sala: cilindro aberto por dentro (a camera orbita e sempre ve parede) + piso
  U3.ambiente = function (T, sc, tipo, tam, semente) {
    const A = AMBIENTES[tipo] || AMBIENTES.prancheta, r = rng(semente || 7);
    if ((window.U3_TESTE || {}).sala === false) { sc.background = new T.Color(A.nevoa); return { raio: 10, luz: A.luz }; }
    const raio = Math.max(8, tam * 3.4), alto = raio * 1.5;
    const [cvP, gP] = tela(1024, 768); A.parede(gP, 1024, 768, r);
    // parede e piso BARATOS (23/10): sem GPU no Actions, iluminar pixel a pixel
    // a sala inteira custava 1,1 s por quadro. A parede nao recebe luz (o
    // sombreado ja vem pintado); o piso usa Lambert, que ainda recebe a sombra.
    const parede = new T.Mesh(new T.CylinderGeometry(raio, raio, alto, 48, 1, true), new T.MeshBasicMaterial({ map: tex(T, cvP, 4, 1), side: T.BackSide, color: '#d8d8d8' }));
    parede.position.y = alto * 0.42; parede.receiveShadow = false; sc.add(parede);
    const [cvC, gC] = tela(1024, 1024); A.piso(gC, 1024, 1024, r);
    const piso = new T.Mesh(new T.CircleGeometry(raio, 48), new T.MeshLambertMaterial({ map: tex(T, cvC, raio / 4, raio / 4) }));
    piso.rotation.x = -Math.PI / 2; piso.receiveShadow = true; sc.add(piso);
    // so' a parede do fundo entra na nevoa: o objeto fica a ~0,7 raio da camera
    sc.fog = new T.Fog(A.nevoa, raio * 1.1, raio * 2.6);
    sc.background = new T.Color(A.nevoa);
    sc.add(new T.HemisphereLight('#ffffff', A.nevoa, 0.35));
    return { raio, luz: A.luz, piso, parede };
  };

  G.U3 = U3;
})(window);
