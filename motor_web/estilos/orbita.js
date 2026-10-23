// ORBITA -- o Sistema Solar com dados REAIS (23/10, canal ORBIT DAILY; um nicho
// e um motor por canal). A IA escolhe os corpos e o que mostrar; os NUMEROS
// vem da tabela abaixo (NASA Planetary Fact Sheet), nunca do roteiro -- o video
// nao inventa o tamanho de Jupiter nem quanto dura um dia em Venus.
//
//   cena: { texto, acao, alvo, alvo2?, dado?, veiculo?, hud? }
//     acao "sistema"  -- o Sistema Solar visto de cima, acelerado, com as posicoes
//                        de HOJE (longitude media J2000); `alvo` destacado
//     acao "foco"     -- o corpo grande girando no proprio eixo; com `dado`, o
//                        cartao do numero contra a Terra
//     acao "dia"      -- uma volta no eixo em relacao ao Sol e o relogio contando
//                        quanto dura esse dia
//     acao "compara"  -- `alvo` e `alvo2` lado a lado na escala real (e quantos cabem)
//     acao "orbita"   -- `alvo` dando uma volta no corpo que ele orbita (Lua e ISS
//                        na escala real da distancia) e o tempo contando
//     acao "viagem"   -- de `alvo2` (padrao: Terra) ate `alvo`; a distancia e quanto
//                        tempo levaria de `veiculo` (luz|foguete|aviao|carro)
//   dado: dia | ano | gravidade | temperatura | distancia | tamanho | inclinacao
//
// CONTRATO (comum.js): `quadro(t)` sem estado entre quadros.
(function () {
  'use strict';
  // raio km, distancia ao pai km, periodo orbital (dias), dia solar (h), rotacao
  // sideral (h, negativo = retrograda), gravidade m/s2, temperatura media C,
  // inclinacao do eixo (graus); L0 = longitude media em J2000 (graus)
  const CORPOS = {
    sun: { nome: 'Sun', raio: 696000, pai: null, a: 0, ano: 0, dia: 609.1, rot: 609.1, g: 274, temp: 5500, incl: 7.25, tipo: 'estrela', cor: '#FDB813' },
    mercury: { nome: 'Mercury', raio: 2439.7, pai: 'sun', a: 57.9e6, ano: 88.0, dia: 4222.6, rot: 1407.6, g: 3.7, temp: 167, incl: 0.03, L0: 252.25, tipo: 'rocha', cor: '#9C9590' },
    venus: { nome: 'Venus', raio: 6051.8, pai: 'sun', a: 108.2e6, ano: 224.7, dia: 2802.0, rot: -5832.5, g: 8.9, temp: 464, incl: 177.4, L0: 181.98, tipo: 'nuvem', cor: '#E3C27A' },
    earth: { nome: 'Earth', raio: 6371, pai: 'sun', a: 149.6e6, ano: 365.2, dia: 24.0, rot: 23.9, g: 9.8, temp: 15, incl: 23.4, L0: 100.46, tipo: 'terra', cor: '#2F6DB5' },
    moon: { nome: 'Moon', raio: 1737.5, pai: 'earth', a: 384400, ano: 27.3, dia: 708.7, rot: 655.7, g: 1.6, temp: -20, incl: 6.7, tipo: 'rocha', cor: '#B8B5AE' },
    mars: { nome: 'Mars', raio: 3389.5, pai: 'sun', a: 228.0e6, ano: 687.0, dia: 24.7, rot: 24.6, g: 3.7, temp: -65, incl: 25.2, L0: 355.45, tipo: 'marte', cor: '#C1502E' },
    jupiter: { nome: 'Jupiter', raio: 69911, pai: 'sun', a: 778.5e6, ano: 4331, dia: 9.9, rot: 9.9, g: 23.1, temp: -110, incl: 3.1, L0: 34.40, tipo: 'gas', cor: '#C99A6B', faixas: ['#E8D3B0', '#B9875A', '#F0E2C8', '#A8714A', '#D9BC92'] },
    saturn: { nome: 'Saturn', raio: 58232, pai: 'sun', a: 1432.0e6, ano: 10747, dia: 10.7, rot: 10.7, g: 9.0, temp: -140, incl: 26.7, L0: 49.94, tipo: 'gas', cor: '#E2C98E', faixas: ['#EADBB0', '#D2B77C', '#F2E6C4', '#C8A86A'], aneis: true },
    uranus: { nome: 'Uranus', raio: 25362, pai: 'sun', a: 2867.0e6, ano: 30589, dia: 17.2, rot: -17.2, g: 8.7, temp: -195, incl: 97.8, L0: 313.23, tipo: 'gas', cor: '#9FD8DF', faixas: ['#A9DEE4', '#98D2DA', '#B4E4E9'] },
    neptune: { nome: 'Neptune', raio: 24622, pai: 'sun', a: 4515.0e6, ano: 59800, dia: 16.1, rot: 16.1, g: 11.0, temp: -200, incl: 28.3, L0: 304.88, tipo: 'gas', cor: '#3F64D6', faixas: ['#4A6FDC', '#3557C2', '#5C82E6'] },
    pluto: { nome: 'Pluto', raio: 1188.3, pai: 'sun', a: 5906.4e6, ano: 90560, dia: 153.3, rot: -153.3, g: 0.6, temp: -225, incl: 122.5, L0: 238.9, tipo: 'rocha', cor: '#C9B39A' },
    iss: { nome: 'ISS', raio: 0.055, pai: 'earth', a: 6371 + 420, ano: 92.9 / 1440, dia: 0, rot: 0, g: 0, temp: 0, incl: 0, tipo: 'nave', cor: '#D8DDE3' },
  };
  const PLANETAS = ['mercury', 'venus', 'earth', 'mars', 'jupiter', 'saturn', 'uranus', 'neptune'];
  const VEICULOS = { luz: ['LIGHT', 299792.458 * 3600], foguete: ['FASTEST ROCKET', 58536], aviao: ['JET (550 MPH)', 885], carro: ['CAR (60 MPH)', 96.56] };
  const KM_MI = 0.621371;

  function criar(tela, spec, U) {
    const T = window.THREE, c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const gl = document.createElement('canvas'); gl.width = W; gl.height = H;
    const R = new T.WebGLRenderer({ canvas: gl, antialias: true, preserveDrawingBuffer: true, logarithmicDepthBuffer: true }); R.setSize(W, H, false);
    const cam = new T.PerspectiveCamera(40, W / H, 0.001, 1e6);
    const sc = new T.Scene(); sc.background = new T.Color('#03040B');
    const chave = (k, p) => (CORPOS[String(k || '').toLowerCase()] ? String(k).toLowerCase() : p);

    // ---- ceu: estrelas fixas numa casca grande (da semente)
    { const r = U.rng(spec.semente || 'orbita'), n = 2600, pos = new Float32Array(n * 3), cor = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) { const u = r() * 2 - 1, a = r() * U.TAU, s = Math.sqrt(1 - u * u), d = 4000;
        pos.set([Math.cos(a) * s * d, u * d, Math.sin(a) * s * d], i * 3); const b = 0.45 + r() * 0.55, q = r(); cor.set([b * (q < 0.15 ? 1 : 0.85), b * 0.9, b * (q > 0.85 ? 1 : 0.88)], i * 3); }
      const g = new T.BufferGeometry(); g.setAttribute('position', new T.BufferAttribute(pos, 3)); g.setAttribute('color', new T.BufferAttribute(cor, 3));
      const ceu = new T.Points(g, new T.PointsMaterial({ size: 2.2, sizeAttenuation: false, vertexColors: true })); sc.add(ceu); }
    const amb = new T.AmbientLight('#ffffff', 0.08); sc.add(amb);
    const luzSol = new T.PointLight('#FFF4E0', 2.2, 0, 0); sc.add(luzSol);
    const luzDir = new T.DirectionalLight('#FFF4E0', 1.6); sc.add(luzDir); sc.add(luzDir.target);

    // ---- texturas desenhadas (equiretangulares 512x256), da semente do corpo
    function textura(k) {
      const b = CORPOS[k], cv = document.createElement('canvas'); cv.width = 512; cv.height = 256; const g = cv.getContext('2d'), r = U.rng('tex-' + k);
      g.fillStyle = b.cor; g.fillRect(0, 0, 512, 256);
      const mancha = (x, y, rx, ry, cor) => { g.fillStyle = cor; g.beginPath(); g.ellipse(x, y, rx, ry, r() * 3, 0, U.TAU); g.fill(); };
      if (b.tipo === 'gas' || b.tipo === 'nuvem' || b.tipo === 'estrela') {
        const fx = b.faixas || [b.cor];
        for (let y = 0; y < 256; y += 4 + Math.floor(r() * 10)) { g.fillStyle = fx[Math.floor(r() * fx.length)]; g.globalAlpha = b.tipo === 'gas' ? 0.75 : 0.25; g.fillRect(0, y, 512, 3 + r() * 12); }
        g.globalAlpha = 1;
        if (k === 'jupiter') mancha(330, 165, 34, 18, '#B5532F');
        if (b.tipo === 'estrela') for (let i = 0; i < 260; i++) mancha(r() * 512, r() * 256, 3 + r() * 9, 2 + r() * 6, r() < 0.5 ? 'rgba(255,170,40,0.5)' : 'rgba(255,240,170,0.45)');
        if (b.tipo === 'nuvem') for (let i = 0; i < 70; i++) mancha(r() * 512, r() * 256, 20 + r() * 50, 5 + r() * 10, 'rgba(250,235,190,0.35)');
      } else if (b.tipo === 'terra') {
        for (let i = 0; i < 46; i++) { const x = r() * 512, y = 40 + r() * 176; mancha(x, y, 10 + r() * 38, 6 + r() * 24, r() < 0.7 ? '#4E8C3A' : '#B79A62'); }
        g.fillStyle = '#F4F8FB'; g.fillRect(0, 0, 512, 16); g.fillRect(0, 240, 512, 16);
        for (let i = 0; i < 60; i++) mancha(r() * 512, r() * 256, 14 + r() * 40, 3 + r() * 6, 'rgba(255,255,255,0.55)');
      } else if (b.tipo === 'marte') {
        for (let i = 0; i < 50; i++) mancha(r() * 512, 30 + r() * 196, 8 + r() * 40, 4 + r() * 18, r() < 0.5 ? 'rgba(110,40,20,0.45)' : 'rgba(220,120,70,0.4)');
        g.fillStyle = '#F2EEE8'; g.fillRect(0, 0, 512, 10); g.fillRect(0, 248, 512, 8);
      } else {
        for (let i = 0; i < 140; i++) { const x = r() * 512, y = r() * 256, rr = 2 + r() * 12; g.fillStyle = 'rgba(0,0,0,0.18)'; g.beginPath(); g.arc(x, y, rr, 0, U.TAU); g.fill();
          g.strokeStyle = 'rgba(255,255,255,0.18)'; g.lineWidth = 1.5; g.beginPath(); g.arc(x - 1, y - 1, rr, Math.PI, Math.PI * 1.6); g.stroke(); }
        if (k === 'pluto') mancha(300, 150, 60, 40, 'rgba(245,230,210,0.7)');
      }
      const t = new T.CanvasTexture(cv); t.anisotropy = 4; return t;
    }
    const brilho = (() => { const cv = document.createElement('canvas'); cv.width = cv.height = 256; const g = cv.getContext('2d'), gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
      gr.addColorStop(0, 'rgba(255,230,150,0.95)'); gr.addColorStop(0.25, 'rgba(255,190,80,0.45)'); gr.addColorStop(1, 'rgba(255,150,40,0)'); g.fillStyle = gr; g.fillRect(0, 0, 256, 256); return new T.CanvasTexture(cv); })();

    // ---- um objeto 3D por corpo (raio 1; cada palco escala e posiciona)
    const OBJ = {};
    function obj(k) {
      if (OBJ[k]) return OBJ[k];
      const b = CORPOS[k], grupo = new T.Group(), eixo = new T.Group(); grupo.add(eixo);
      let corpo;
      if (b.tipo === 'nave') {
        corpo = new T.Group(); const M = (cor) => new T.MeshStandardMaterial({ color: cor, roughness: 0.5, metalness: 0.4, flatShading: true });
        const tr = new T.Mesh(new T.BoxGeometry(2, 0.12, 0.12), M('#D8DDE3')); corpo.add(tr);
        [-0.8, -0.45, 0.45, 0.8].forEach((x) => { const p = new T.Mesh(new T.BoxGeometry(0.28, 0.02, 0.9), M('#C9A24A')); p.position.set(x, 0, 0); corpo.add(p); });
        const mod = new T.Mesh(new T.CylinderGeometry(0.12, 0.12, 0.7, 12), M('#EEF1F4')); mod.rotation.x = Math.PI / 2; corpo.add(mod);
      } else {
        const mat = b.tipo === 'estrela' ? new T.MeshBasicMaterial({ map: textura(k) }) : new T.MeshStandardMaterial({ map: textura(k), roughness: 0.95, metalness: 0 });
        corpo = new T.Mesh(new T.SphereGeometry(1, 64, 32), mat);
        if (b.tipo === 'estrela') { const s = new T.Sprite(new T.SpriteMaterial({ map: brilho, blending: T.AdditiveBlending, depthWrite: false, transparent: true })); s.scale.set(3.4, 3.4, 1); grupo.add(s); }
        if (b.aneis || k === 'uranus') {
          const cv = document.createElement('canvas'); cv.width = 256; cv.height = 4; const g = cv.getContext('2d'), r = U.rng('anel-' + k);
          for (let x = 0; x < 256; x++) { const a = k === 'uranus' ? (x % 40 < 3 ? 0.5 : 0.04) : (x < 30 ? 0.15 : x > 150 && x < 165 ? 0.05 : 0.45 + r() * 0.45); g.fillStyle = 'rgba(226,206,160,' + a.toFixed(2) + ')'; g.fillRect(x, 0, 1, 4); }
          const tx = new T.CanvasTexture(cv), geo = new T.RingGeometry(1.25, 2.3, 96), pos = geo.attributes.position, uv = geo.attributes.uv, v = new T.Vector3();
          for (let i = 0; i < pos.count; i++) { v.fromBufferAttribute(pos, i); uv.setXY(i, (v.length() - 1.25) / 1.05, 0.5); }
          const anel = new T.Mesh(geo, new T.MeshStandardMaterial({ map: tx, transparent: true, side: T.DoubleSide, depthWrite: false })); anel.rotation.x = Math.PI / 2; eixo.add(anel);
        }
      }
      eixo.add(corpo); eixo.rotation.z = -((b.incl || 0) * Math.PI) / 180;
      sc.add(grupo); grupo.visible = false;
      return (OBJ[k] = { k, b, grupo, eixo, corpo });
    }

    // ---- posicoes de HOJE: longitude media de J2000 + movimento medio
    const diasJ2000 = (Date.now() - Date.UTC(2000, 0, 1, 12)) / 864e5;
    const lonHoje = (k) => { const b = CORPOS[k]; return ((b.L0 || 0) + (360 * diasJ2000) / Math.max(1e-6, b.ano)) * Math.PI / 180; };
    const rSis = (k) => 2.6 + 3.2 * Math.log2(1 + CORPOS[k].a / 149.6e6);
    const tamSis = (k) => (k === 'sun' ? 0.9 : 0.16 + 0.3 * Math.log10(1 + CORPOS[k].raio / 1000));
    let orbitas = null;
    function linhasDeOrbita() {
      if (orbitas) return orbitas; orbitas = {};
      PLANETAS.concat(['pluto']).forEach((k) => { const pts = []; for (let i = 0; i <= 160; i++) { const a = (i / 160) * U.TAU; pts.push(new T.Vector3(Math.cos(a) * rSis(k), 0, -Math.sin(a) * rSis(k))); }
        const l = new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: '#6B7690', transparent: true, opacity: 0.55 })); sc.add(l); l.visible = false; orbitas[k] = l; });
      return orbitas;
    }
    const trilha = new T.Line(new T.BufferGeometry().setFromPoints([new T.Vector3(), new T.Vector3()]), new T.LineBasicMaterial({ color: '#FFD23F' })); sc.add(trilha); trilha.visible = false;
    const anelOrb = new T.Line(new T.BufferGeometry(), new T.LineBasicMaterial({ color: '#8A93A8', transparent: true, opacity: 0.6 })); sc.add(anelOrb); anelOrb.visible = false;

    // ---- formatos (canal americano: milhas e Fahrenheit primeiro)
    const n0 = (v, d) => Number(v).toLocaleString('en-US', { maximumFractionDigits: d == null ? (Math.abs(v) < 10 ? 1 : 0) : d });
    const tempoH = (h) => (Math.abs(h) < 48 ? n0(Math.abs(h)) + ' HOURS' : Math.abs(h) < 24 * 730 ? n0(Math.abs(h) / 24) + ' EARTH DAYS' : n0(Math.abs(h) / 8766) + ' EARTH YEARS');
    const tempoD = (d) => (d < 2 ? n0(d * 24) + ' HOURS' : d < 730 ? n0(d) + ' DAYS' : n0(d / 365.25) + ' YEARS');
    const dist = (km) => (km * KM_MI >= 1e6 ? n0((km * KM_MI) / 1e6) + ' MILLION MI' : n0(km * KM_MI) + ' MI');
    const DADOS = {
      dia: { rotulo: 'ONE DAY', val: (b) => b.dia, txt: (b) => tempoH(b.dia), rel: true },
      ano: { rotulo: 'ONE YEAR', val: (b) => b.ano, txt: (b) => tempoD(b.ano), rel: true },
      gravidade: { rotulo: 'GRAVITY', val: (b) => b.g, txt: (b) => n0((b.g / 9.8) * 100, 0) + '% OF EARTH', rel: true },
      temperatura: { rotulo: 'AVG TEMPERATURE', val: (b) => b.temp, txt: (b) => n0(b.temp * 1.8 + 32, 0) + '°F (' + n0(b.temp, 0) + '°C)', rel: false },
      distancia: { rotulo: 'FROM THE ' + 'SUN', val: (b) => b.a, txt: (b) => dist(b.a), rel: true },
      tamanho: { rotulo: 'DIAMETER', val: (b) => b.raio, txt: (b) => n0(b.raio * 2 * KM_MI, 0) + ' MI', rel: true },
      inclinacao: { rotulo: 'AXIS TILT', val: (b) => b.incl, txt: (b) => n0(b.incl) + '°', rel: true },
    };

    function esconder() { Object.values(OBJ).forEach((o) => { o.grupo.visible = false; }); if (orbitas) Object.values(orbitas).forEach((l) => { l.visible = false; }); trilha.visible = false; anelOrb.visible = false; }
    const giro = (o, t, periodoVis) => { o.corpo.rotation.y = (t / periodoVis) * U.TAU * (o.b.rot < 0 ? -1 : 1); };
    const proj = (v) => { const p = v.clone().project(cam); return { x: (p.x * 0.5 + 0.5) * W, y: (-p.y * 0.5 + 0.5) * H, atras: p.z > 1 }; };

    // ======================= PALCOS =======================
    function palcoSistema(cn, t, local) {
      linhasDeOrbita();
      const alvo = chave(cn.alvo, 'earth'), longe = ['jupiter', 'saturn', 'uranus', 'neptune', 'pluto'].indexOf(alvo) >= 0 || cn.zoom === 'completo';
      const lista = longe ? PLANETAS.concat(['pluto']) : ['mercury', 'venus', 'earth', 'mars'];
      const dps = Number(cn.dias_por_s) > 0 ? U.clamp(Number(cn.dias_por_s), 1, 20000) : longe ? 900 : 30;
      const sol = obj('sun'); sol.grupo.visible = true; sol.grupo.position.set(0, 0, 0); sol.grupo.scale.setScalar(tamSis('sun')); giro(sol, t, 30);
      luzSol.position.set(0, 0, 0); luzSol.intensity = 2.4; luzDir.intensity = 0; amb.intensity = 0.12;
      const marcas = [];
      lista.forEach((k) => { const o = obj(k), a = lonHoje(k) + (U.TAU * local * dps) / CORPOS[k].ano, r = rSis(k);
        o.grupo.visible = true; o.grupo.scale.setScalar(tamSis(k)); o.grupo.position.set(Math.cos(a) * r, 0, -Math.sin(a) * r); giro(o, t, 3);
        orbitas[k].visible = true; orbitas[k].material.color.set(k === alvo ? '#FFD23F' : '#6B7690'); orbitas[k].material.opacity = k === alvo ? 0.95 : 0.45;
        marcas.push([k, o.grupo.position.clone(), tamSis(k)]); });
      // o sistema inteiro cabe na LARGURA (a tela e' em pe), visto de cima e um pouco de lado
      const raio = rSis(lista[lista.length - 1]) * 1.08, hf = Math.tan((cam.fov * Math.PI) / 360) * cam.aspect, d = raio / hf;
      const ang = 1.05 + Math.sin(t * 0.15) * 0.05, giroCam = t * 0.04;
      cam.position.set(Math.sin(giroCam) * d * Math.cos(ang), d * Math.sin(ang), Math.cos(giroCam) * d * Math.cos(ang));
      cam.near = 0.05; cam.far = 1e5; cam.updateProjectionMatrix(); cam.lookAt(0, 0, 0);
      // e desce o sistema na tela: o alto fica para o cartaz, o contador mora embaixo
      cam.position.y += raio * 0.25;
      return { marcas, alvo, dias: local * dps };
    }
    function palcoFoco(cn, t, k, local, umDia) {
      const alvo = chave(cn.alvo, 'earth'), o = obj(alvo); o.grupo.visible = true; o.grupo.position.set(0, 0, 0); o.grupo.scale.setScalar(1);
      // `dia`: uma volta no eixo durante a cena, com o Sol parado a esquerda (o terminador fica)
      if (umDia) o.corpo.rotation.y = U.suave(k) * U.TAU * (o.b.rot < 0 ? -1 : 1); else giro(o, t, 14);
      luzSol.intensity = 0; luzDir.intensity = o.b.tipo === 'estrela' ? 0 : 2.2; luzDir.position.set(-6, 1.5, 3); luzDir.target.position.set(0, 0, 0); amb.intensity = 0.07;
      const temAnel = !!o.b.aneis, d = (temAnel ? 2.4 : 1.12) / Math.tan((cam.fov * Math.PI) / 360) / Math.min(1, cam.aspect) * 1.32;
      const a = Math.sin(t * 0.18) * 0.25 + 0.15 * U.saida(U.clamp(local / 2, 0, 1));
      cam.position.set(Math.sin(a) * d, d * (temAnel ? 0.18 : 0.08), Math.cos(a) * d); cam.near = 0.01; cam.far = 1e5; cam.updateProjectionMatrix();
      // mirar abaixo do centro SOBE o planeta: o meio da tela fica para o cartao e a legenda
      cam.lookAt(0, -(temAnel ? 1.25 : 0.82), 0);
      return { alvo, o };
    }
    function palcoCompara(cn, t) {
      const A = chave(cn.alvo, 'jupiter'), B = chave(cn.alvo2, A === 'earth' ? 'moon' : 'earth');
      const [g, p] = CORPOS[A].raio >= CORPOS[B].raio ? [A, B] : [B, A];
      const oG = obj(g), oP = obj(p), rg = 1, rp = Math.max(CORPOS[p].raio / CORPOS[g].raio, 0.004);
      luzSol.intensity = 0; luzDir.intensity = 2.0; luzDir.position.set(-5, 2, 4); amb.intensity = 0.1;
      oG.grupo.visible = oP.grupo.visible = true; oG.grupo.scale.setScalar(rg); oP.grupo.scale.setScalar(rp);
      const pq = rp < 0.12; // o pequeno vira um ponto: fica na frente do grande, no alto, com etiqueta
      oG.grupo.position.set(pq ? 0 : rg + 0.15, 0, 0); oP.grupo.position.set(pq ? -0.55 : -(rp + 0.15), pq ? 0.45 : 0, pq ? 1.05 : 0);
      giro(oG, t, 16); giro(oP, t, 16);
      const larg = pq ? 2.3 : 2 * rg + 2 * rp + 0.5, hf = Math.tan((cam.fov * Math.PI) / 360), d = Math.max((larg / 2) / (hf * cam.aspect), (rg * 1.25) / hf) * 1.12;
      cam.position.set(Math.sin(t * 0.1) * 0.4, 0.15, d); cam.near = 0.001; cam.far = 1e5; cam.updateProjectionMatrix(); cam.lookAt(pq ? 0 : (oG.grupo.position.x + oP.grupo.position.x) / 2, -rg * 0.55, 0);
      return { g, p, oG, oP };
    }
    function palcoOrbita(cn, t, k) {
      const alvo = chave(cn.alvo, 'moon') === 'sun' ? 'earth' : chave(cn.alvo, 'moon'), pai = CORPOS[alvo].pai || 'sun', oPai = obj(pai), oA = obj(alvo);
      const razao = CORPOS[alvo].a / CORPOS[pai].raio, escalaReal = razao <= 80;
      const rOrb = escalaReal ? razao : 3 + 2.2 * Math.log10(razao), rA = escalaReal ? Math.max(CORPOS[alvo].raio / CORPOS[pai].raio, alvo === 'iss' ? 0.035 : rOrb * 0.012) : 0.32;
      oPai.grupo.visible = oA.grupo.visible = true; oPai.grupo.position.set(0, 0, 0); oPai.grupo.scale.setScalar(1); oA.grupo.scale.setScalar(rA);
      const ang = U.TAU * U.suave(k) + 0.6, pos = new T.Vector3(Math.cos(ang) * rOrb, 0, -Math.sin(ang) * rOrb); oA.grupo.position.copy(pos);
      oA.grupo.rotation.y = ang; giro(oPai, t, 10);
      if (pai === 'sun') { luzSol.position.set(0, 0, 0); luzSol.intensity = 2.6; luzDir.intensity = 0; } else { luzSol.intensity = 0; luzDir.intensity = 2.0; luzDir.position.set(-8, 2, 5); }
      amb.intensity = 0.14;
      { const pts = []; for (let i = 0; i <= 200; i++) { const a = (i / 200) * U.TAU; pts.push(new T.Vector3(Math.cos(a) * rOrb, 0, -Math.sin(a) * rOrb)); } anelOrb.geometry.setFromPoints(pts); anelOrb.visible = true; }
      { const pts = [], n = 80; for (let i = 0; i <= n; i++) { const a = 0.6 + ((ang - 0.6) * i) / n; pts.push(new T.Vector3(Math.cos(a) * rOrb, 0, -Math.sin(a) * rOrb)); } trilha.geometry.setFromPoints(pts); trilha.visible = true; }
      const hf = Math.tan((cam.fov * Math.PI) / 360), d = (rOrb * (razao < 3 ? 1.9 : 1.15)) / (hf * cam.aspect), el = 0.75;
      cam.position.set(Math.sin(t * 0.05) * d * Math.cos(el) * 0.4, d * Math.sin(el), d * Math.cos(el)); cam.near = d / 2000; cam.far = d * 200; cam.updateProjectionMatrix(); cam.lookAt(0, -rOrb * (razao < 3 ? 0.55 : 0.32), 0);
      return { alvo, pai, oA, oPai, escalaReal };
    }
    function palcoViagem(cn, t, k) {
      const B = chave(cn.alvo, 'mars'), A0 = chave(cn.alvo2, 'earth'), A = A0 === B ? (B === 'earth' ? 'moon' : 'earth') : A0;
      const oA = obj(A), oB = obj(B), L = 60, rB = U.clamp(CORPOS[B].raio / CORPOS[A].raio, 0.15, 6);
      oA.grupo.visible = oB.grupo.visible = true; oA.grupo.scale.setScalar(1); oA.grupo.position.set(0, 0, 0); oB.grupo.scale.setScalar(rB); oB.grupo.position.set(0, 0, -L);
      giro(oA, t, 14); giro(oB, t, 14);
      luzSol.intensity = 0; luzDir.intensity = 2.0; luzDir.position.set(-5, 3, 2); amb.intensity = 0.12;
      // o corpo de partida fica a ESQUERDA do caminho: a camera passa por ele (que some pela
      // borda) e segue reto ate o destino, que para no alto da tela com folga
      oA.grupo.position.set(-1.7, 0, 0);
      const q = U.suave(U.clamp((k - 0.08) / 0.84, 0, 1)), z0 = 4.6, z1 = -L + 6.2 * rB;
      cam.position.set(0.3, 0.2, U.lerp(z0, z1, q)); cam.near = 0.01; cam.far = 1e5; cam.updateProjectionMatrix();
      cam.lookAt(0, -0.32 * (q > 0.5 ? rB : 1), cam.position.z - 10);
      // distancia: Lua a partir da Terra; planetas pela diferenca das orbitas (o mais perto que chegam)
      const km = A === 'earth' && B === 'moon' || A === 'moon' && B === 'earth' ? 384400 : CORPOS[A].pai === CORPOS[B].pai && CORPOS[A].pai === 'sun' ? Math.abs(CORPOS[A].a - CORPOS[B].a)
        : B === 'sun' ? CORPOS[A].a : A === 'sun' ? CORPOS[B].a : Math.abs((CORPOS[A].pai === 'sun' ? CORPOS[A].a : CORPOS.earth.a) - (CORPOS[B].pai === 'sun' ? CORPOS[B].a : CORPOS.earth.a));
      return { A, B, km, q };
    }

    // ======================= 2D por cima =======================
    function etiqueta(txt, sub, x, y, destaque, ent) {
      c.save(); c.translate(U.clamp(x, 150, W - 150), y); c.scale(ent, ent); c.textAlign = 'center'; c.textBaseline = 'middle';
      c.font = (destaque ? '58px' : '40px') + ' "Lilita One", sans-serif'; const w = Math.max(c.measureText(txt).width, sub ? c.measureText(sub).width * 0.7 : 0) + 44, h = destaque ? (sub ? 126 : 80) : 62;
      U.rr(c, -w / 2, -h / 2, w, h, 20); c.fillStyle = destaque ? '#FFD23F' : 'rgba(255,255,255,0.88)'; c.fill(); c.fillStyle = '#10131C';
      c.fillText(txt, 0, sub && destaque ? -20 : 2); if (sub && destaque) { c.font = '38px "Lilita One", sans-serif'; c.fillText(sub, 0, 30); }
      c.restore();
    }
    function cartao(rotulo, valorTxt, barras, local) {
      const ent = U.mola(local - 0.15, 10); if (ent <= 0) return;
      const x0 = 70, w = W - 140, y0 = H * 0.47, h = barras ? 330 : 200;
      c.save(); c.translate(W / 2, y0 + h / 2); c.scale(ent, ent); c.translate(-W / 2, -(y0 + h / 2));
      U.rr(c, x0, y0, w, h, 34); c.fillStyle = 'rgba(8,10,22,0.88)'; c.fill(); c.lineWidth = 6; c.strokeStyle = '#FFD23F'; c.stroke();
      c.textBaseline = 'middle'; c.textAlign = 'left'; c.font = '46px "Lilita One", sans-serif'; c.fillStyle = '#FFD23F'; c.fillText(rotulo, x0 + 40, y0 + 52);
      c.textAlign = 'center'; c.font = '86px "Lilita One", sans-serif'; c.fillStyle = '#FFFFFF';
      const s = Math.min(1, (w - 60) / Math.max(1, c.measureText(valorTxt).width)); c.save(); c.translate(W / 2, y0 + 128); c.scale(s, s); c.fillText(valorTxt, 0, 0); c.restore();
      if (barras) { const q = U.suave(U.clamp((local - 0.4) / 1.0, 0, 1)), mx = Math.max(...barras.map((b) => Math.abs(b[1])), 1e-9), bw = w - 280, by = y0 + 196;
        barras.forEach(([n, v, cor], j) => { const yy = by + j * 66; c.textAlign = 'left'; c.font = '36px "Lilita One", sans-serif'; c.fillStyle = cor; c.fillText(n, x0 + 40, yy + 22);
          U.rr(c, x0 + 240, yy, bw, 44, 12); c.fillStyle = 'rgba(255,255,255,0.12)'; c.fill(); U.rr(c, x0 + 240, yy, Math.max(12, bw * (Math.abs(v) / mx) * q), 44, 12); c.fillStyle = cor; c.fill(); }); }
      c.restore();
    }
    function selo(txt, sub, y, local) {
      const s = U.mola(local, 11); if (s <= 0) return;
      c.save(); c.translate(W / 2, y); c.rotate(-0.04); c.scale(s, s); c.textAlign = 'center'; c.textBaseline = 'middle'; c.font = '96px "Lilita One", sans-serif';
      const w = Math.max(c.measureText(txt).width, sub ? c.measureText(sub).width * 0.45 : 0) + 70, h = sub ? 190 : 140;
      U.rr(c, -w / 2, -h / 2, w, h, 30); c.fillStyle = '#E4572E'; c.fill(); c.fillStyle = '#FFFFFF'; c.fillText(txt, 0, sub ? -24 : 4);
      if (sub) { c.font = '44px "Lilita One", sans-serif'; c.fillText(sub, 0, 54); } c.restore();
    }
    function contador(rotulo, txt, y) {
      c.save(); c.textAlign = 'center'; c.textBaseline = 'middle'; c.font = '44px "Lilita One", sans-serif'; c.fillStyle = '#9FB0D0'; c.fillText(rotulo, W / 2, y - 64);
      c.font = '104px "Lilita One", sans-serif'; c.lineWidth = 14; c.strokeStyle = '#05060D'; c.lineJoin = 'round'; c.strokeText(txt, W / 2, y); c.fillStyle = '#FFFFFF'; c.fillText(txt, W / 2, y); c.restore();
    }

    function quadro(t) {
      const { c: cn, i, k, local } = U.cenaEm(spec, t), acao = cn.acao || 'foco';
      esconder();
      let info = {};
      if (acao === 'sistema') info = palcoSistema(cn, t, local);
      else if (acao === 'compara') info = palcoCompara(cn, t);
      else if (acao === 'orbita') info = palcoOrbita(cn, t, k);
      else if (acao === 'viagem') info = palcoViagem(cn, t, k);
      else info = palcoFoco(cn, t, k, local, acao === 'dia');
      R.render(sc, cam); c.drawImage(gl, 0, 0, W, H);
      if (i > 0 && local < 0.12) { c.fillStyle = 'rgba(255,255,255,' + (0.35 * (1 - local / 0.12)).toFixed(2) + ')'; c.fillRect(0, 0, W, H); }
      const dur = cn.fim - cn.ini;

      if (acao === 'sistema') {
        info.marcas.forEach(([kk, p, tam]) => { const q = proj(p.clone().add(new T.Vector3(0, tam * 1.6, 0))); if (q.atras) return;
          if (kk === info.alvo) etiqueta(CORPOS[kk].nome.toUpperCase(), null, q.x, q.y - 40, true, U.mola(local - 0.2, 10)); });
        contador('TIME LAPSE', '+' + tempoD(Math.max(0, info.dias)), H * 0.87);
        c.save(); c.font = '30px "Lilita One", sans-serif'; c.fillStyle = 'rgba(200,210,230,0.6)'; c.textAlign = 'center'; c.fillText('POSITIONS: TODAY · DISTANCES NOT TO SCALE', W / 2, H * 0.965); c.restore();
      } else if (acao === 'foco' || acao === 'dia') {
        const b = CORPOS[info.alvo];
        if (acao === 'dia' && b.dia) { contador('ONE DAY ON ' + b.nome.toUpperCase(), tempoH(b.dia * U.suave(k)), H * 0.6); }
        else if (cn.dado && DADOS[cn.dado] && info.alvo !== 'iss') {
          const D = DADOS[cn.dado], v = D.val(b);
          const barras = D.rel && info.alvo !== 'earth' && cn.dado !== 'distancia' || (cn.dado === 'distancia' && b.pai === 'sun' && info.alvo !== 'earth')
            ? [[b.nome.toUpperCase().slice(0, 8), v, '#FFD23F'], ['EARTH', D.val(CORPOS.earth), '#6FA8FF']] : null;
          const rot = cn.dado === 'distancia' && b.pai !== 'sun' ? 'FROM ' + CORPOS[b.pai || 'sun'].nome.toUpperCase() : D.rotulo;
          cartao(rot, D.txt(b), barras, local);
        } else etiqueta(b.nome.toUpperCase(), n0(b.raio * 2 * KM_MI, 0) + ' MI WIDE', W / 2, H * 0.56, true, U.mola(local - 0.3, 10));
      } else if (acao === 'compara') {
        const G = CORPOS[info.g], P = CORPOS[info.p], ent = U.mola(local - 0.3, 10);
        [[info.oG, G], [info.oP, P]].forEach(([o, b], j) => { const top = proj(o.grupo.position.clone().add(new T.Vector3(0, o.grupo.scale.x * 1.05, 0)));
          etiqueta(b.nome.toUpperCase(), n0(b.raio * 2 * KM_MI, 0) + ' MI', top.x, Math.max(330, top.y - 60 - j * 10), true, ent); });
        const vezes = G.raio / P.raio, cabem = Math.pow(vezes, 3);
        if (local > 1.0 && vezes >= 1.3) selo(n0(vezes, vezes < 10 ? 1 : 0) + 'x WIDER', cabem >= 2 ? '≈ ' + n0(cabem, 0) + ' ' + P.nome.toUpperCase() + 'S FIT INSIDE' : null, H * 0.6, local - 1.0);
      } else if (acao === 'orbita') {
        const b = CORPOS[info.alvo], q = proj(info.oA.grupo.position.clone().add(new T.Vector3(0, Math.max(info.oA.grupo.scale.x, 0.3) * 1.5, 0)));
        if (!q.atras) etiqueta(b.nome.toUpperCase(), null, q.x, Math.min(q.y - 30, H * 0.5), true, U.mola(local - 0.2, 10));
        const qp = proj(new T.Vector3(0, 1.3, 0)); if (!qp.atras) etiqueta(CORPOS[info.pai].nome.toUpperCase(), null, qp.x, qp.y - 34, false, U.mola(local - 0.1, 10));
        contador('ONE ORBIT AROUND ' + CORPOS[info.pai].nome.toUpperCase(), b.ano < 1 ? n0(b.ano * 1440 * U.suave(k), 0) + ' MIN' : tempoD(b.ano * U.suave(k)), H * 0.64);
        if (info.escalaReal) { c.save(); c.font = '34px "Lilita One", sans-serif'; c.fillStyle = 'rgba(200,210,230,0.7)'; c.textAlign = 'center'; c.fillText('DISTANCE TO SCALE', W / 2, H * 0.965); c.restore(); }
      } else if (acao === 'viagem') {
        const v = VEICULOS[cn.veiculo] || VEICULOS.luz, horas = info.km / v[1];
        contador(CORPOS[info.A].nome.toUpperCase() + ' → ' + CORPOS[info.B].nome.toUpperCase(), dist(info.km * info.q), H * 0.6);
        if (k > 0.55) selo(tempoH(horas).replace(' EARTH', ''), 'BY ' + v[0], H * 0.49, (k - 0.55) * dur);
        if (info.q > 0.1 && info.q < 0.9) { const r2 = U.rng(17); c.save(); c.strokeStyle = 'rgba(255,255,255,0.5)'; c.lineWidth = 4;
          for (let j = 0; j < 30; j++) { const a = r2() * U.TAU, r0 = 120 + ((r2() * 900 + local * 1600) % 900); c.beginPath(); c.moveTo(W / 2 + Math.cos(a) * r0, H * 0.4 + Math.sin(a) * r0); c.lineTo(W / 2 + Math.cos(a) * (r0 + 90), H * 0.4 + Math.sin(a) * (r0 + 90)); c.stroke(); }
          c.restore(); }
      }
      if (cn.hud && typeof cn.hud !== 'object' && local > 0.3 && acao !== 'viagem') { const s = U.mola(local - 0.3, 10); c.save(); c.translate(W / 2, 330); c.scale(s, s); c.font = '110px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        const txt = U.hud(c, cn.hud, c.canvas.width * 0.84 - 70, 22), w = c.measureText(txt).width + 70; U.rr(c, -w / 2, -74, w, 148, 34); c.fillStyle = '#FFD23F'; c.fill(); c.fillStyle = '#10131C'; c.fillText(txt, 0, 6); c.restore(); }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 150, fundo: '#FFD23F', borda: '#10131C', cor: '#10131C', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '96px "Lilita One", sans-serif', y: H * 0.74, cor: '#FFFFFF', cor_ativa: '#FFD23F', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro };
  }
  MOTORES.orbita = { criar, CORPOS };
})();
