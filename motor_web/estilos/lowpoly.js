// LOWPOLY -- "E se...?" narrado em 3D de poucas faces (13/10, HISTORICO §109).
//
// O canal responde perguntas hipoteticas ("E se a Terra parasse de girar?")
// com narracao e um mundo de brinquedo: poucas faces, sombreado em degraus
// (toon), cores chapadas. O 3D da a camera e a luz de graca; o que precisa de
// codigo e' o EVENTO de cada cena (parar, congelar, inundar, meteoros...).
//
// Cada cena do spec ganha uma THREE.Scene propria, montada uma vez em
// `criar`; `quadro(t)` so' posiciona a camera e o evento pelo tempo. O WebGL
// desenha num canvas a parte (o palco e' 2D), que e' copiado para o palco
// antes da legenda e do cartaz.
(function () {
  'use strict';
  function criar(tela, spec, U) {
    const T = window.THREE;
    const c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const gl = document.createElement('canvas'); gl.width = W; gl.height = H;
    const R = new T.WebGLRenderer({ canvas: gl, antialias: true, preserveDrawingBuffer: true });
    R.setSize(W, H, false);
    const grad = new Uint8Array([55, 120, 185, 225]); const gm = new T.DataTexture(grad, 4, 1, T.LuminanceFormat); gm.minFilter = gm.magFilter = T.NearestFilter; gm.needsUpdate = true;
    const M = (cor, emis) => new T.MeshToonMaterial({ color: cor, gradientMap: gm, emissive: emis || '#000000' });

    function pessoa(cor) {
      const g = new T.Group();
      const corpo = new T.Mesh(new T.CylinderGeometry(0.42, 0.55, 1.2, 6), M(cor || '#E46A86')); corpo.position.y = 1.25; g.add(corpo);
      const cab = new T.Mesh(new T.IcosahedronGeometry(0.48, 0), M('#F2C9A5')); cab.position.y = 2.2; g.add(cab);
      const cabelo = new T.Mesh(new T.IcosahedronGeometry(0.5, 0), M('#3A2A22')); cabelo.scale.set(1, 0.5, 1); cabelo.position.y = 2.42; g.add(cabelo);
      const olho = new T.MeshBasicMaterial({ color: '#111' }); [-0.17, 0.17].forEach((x) => { const o = new T.Mesh(new T.SphereGeometry(0.07, 6, 6), olho); o.position.set(x, 2.22, 0.42); g.add(o); });
      const membros = [];
      [[-0.6, 1.7, 0.2], [0.6, 1.7, 0.2], [-0.22, 0.65, 0.26], [0.22, 0.65, 0.26]].forEach(([x, y, l], i) => {
        const piv = new T.Group(); piv.position.set(x, y, 0); const m = new T.Mesh(new T.BoxGeometry(l, 0.7, l), M(i < 2 ? (cor || '#E46A86') : '#3B4A63')); m.position.y = -0.35; piv.add(m); g.add(piv); membros.push(piv);
      });
      g.userData = { membros, cab };
      return g;
    }
    function arvore(x, z, s) { const g = new T.Group(); const tr = new T.Mesh(new T.CylinderGeometry(0.12, 0.16, 0.8, 5), M('#7A5232')); tr.position.y = 0.4; g.add(tr); const co = new T.Mesh(new T.ConeGeometry(0.7, 1.6, 6), M('#4E9A5C')); co.position.y = 1.5; g.add(co); g.position.set(x, 0, z); g.scale.setScalar(s || 1); return g; }

    function montar(cn, idx) {
      const sc = new T.Scene(), cen = cn.cenario || 'cidade', r = U.rng((spec.semente || 'lp') + idx);
      const ceu = { espaco: '#0B0F24', planeta: '#0B0F24', polo: '#CFE6F2', vulcao: '#3B2430', deserto: '#F5C98A', oceano: '#8FD3E8' }[cen] || '#A8D5E2';
      sc.background = new T.Color(ceu);
      sc.add(new T.HemisphereLight('#ffffff', '#55607a', 0.5)); const sol = new T.DirectionalLight('#ffffff', 0.75); sol.position.set(6, 10, 7); sc.add(sol);
      const obj = { sc, cen, extras: [], gente: [], agua: null, globo: null, meteoros: [] };
      if (cen === 'espaco' || cen === 'planeta') {
        const pts = new T.BufferGeometry(), v = []; for (let i = 0; i < 900; i++) { const a = r() * Math.PI * 2, b = Math.acos(2 * r() - 1), d = 60; v.push(d * Math.sin(b) * Math.cos(a), d * Math.cos(b), d * Math.sin(b) * Math.sin(a)); }
        pts.setAttribute('position', new T.Float32BufferAttribute(v, 3)); sc.add(new T.Points(pts, new T.PointsMaterial({ color: '#ffffff', size: 0.25 })));
        const geo = new T.IcosahedronGeometry(3, 2), cores = [], pos = geo.attributes.position;
        for (let i = 0; i < pos.count; i += 3) { const terra = Math.sin(pos.getX(i) * 1.3) + Math.cos(pos.getZ(i) * 1.1 + pos.getY(i)) > 0.6; const col = new T.Color(terra ? (Math.abs(pos.getY(i)) > 2.5 ? '#F4F7FA' : '#5DAA5A') : '#2F7FD1'); for (let k = 0; k < 3; k++) cores.push(col.r, col.g, col.b); }
        geo.setAttribute('color', new T.Float32BufferAttribute(cores, 3));
        const globo = new T.Mesh(geo, new T.MeshToonMaterial({ vertexColors: true, gradientMap: gm })); obj.globo = globo; sc.add(globo);
        const atm = new T.Mesh(new T.IcosahedronGeometry(3.25, 2), new T.MeshBasicMaterial({ color: '#8FC7FF', transparent: true, opacity: 0.18 })); globo.add(atm);
        if (cen === 'espaco') { const lua = new T.Mesh(new T.IcosahedronGeometry(0.8, 1), M('#B9B4AA')); lua.position.set(-6, 2, -4); sc.add(lua); obj.extras.push(lua); }
      } else {
        const chaoCor = { deserto: '#E8B86A', polo: '#F4F7FA', vulcao: '#5A4048', floresta: '#7FB77E', oceano: '#E8D9A8' }[cen] || '#9CB48A';
        const chao = new T.Mesh(new T.CylinderGeometry(9, 9.5, 0.6, 12), M(chaoCor)); chao.position.y = -0.3; sc.add(chao);
        if (cen === 'cidade') { for (let i = 0; i < 26; i++) { const x = (r() - 0.5) * 14, z = (r() - 0.5) * 10 - 2; if (Math.abs(x) < 1.8 && z > -1) continue; const h = 1 + r() * 5; const pr = new T.Mesh(new T.BoxGeometry(1.2, h, 1.2), M(['#E4E1D6', '#C9B79C', '#A8B8C8', '#D9A28B'][i % 4])); pr.position.set(x, h / 2, z); sc.add(pr); }
          for (let i = 0; i < 4; i++) { const car = new T.Mesh(new T.BoxGeometry(0.8, 0.4, 0.4), M(['#E2574C', '#F2B705', '#3E7CB1'][i % 3])); car.position.set(-8 + i * 4, 0.2, 2.5); sc.add(car); obj.extras.push(car); } }
        if (cen === 'floresta' || cen === 'polo') { for (let i = 0; i < 30; i++) { const x = (r() - 0.5) * 15, z = (r() - 0.5) * 12 - 2; if (Math.abs(x) < 1.6 && z > -1) continue; const a = arvore(x, z, 0.8 + r() * 0.8); if (cen === 'polo') a.children[1].material = M('#E8F2F6'); sc.add(a); } }
        if (cen === 'deserto') { for (let i = 0; i < 5; i++) { const d = new T.Mesh(new T.SphereGeometry(2.5 + r() * 2, 7, 5), M('#E0A85C')); d.scale.y = 0.35; d.position.set((r() - 0.5) * 16, 0, -4 - r() * 4); sc.add(d); } const p = new T.Mesh(new T.ConeGeometry(2.5, 3, 4), M('#D9B26F')); p.position.set(4, 1.5, -5); sc.add(p); }
        if (cen === 'vulcao') { const v = new T.Mesh(new T.ConeGeometry(4, 5, 8, 1, true), M('#4A3038')); v.position.set(0, 2.5, -5); sc.add(v); const lava = new T.Mesh(new T.CylinderGeometry(0.9, 0.9, 0.3, 8), M('#FF6A2A', '#FF4A00')); lava.position.set(0, 5, -5); sc.add(lava); obj.extras.push(lava); }
        if (cen === 'oceano' || cn.acao === 'inunda') { const ag = new T.Mesh(new T.PlaneGeometry(40, 40, 30, 30), new T.MeshToonMaterial({ color: '#3C9BD6', gradientMap: gm, transparent: true, opacity: 0.88 })); ag.rotation.x = -Math.PI / 2; ag.position.y = cen === 'oceano' ? 0.05 : -0.2; obj.agua = ag; obj.aguaBase = ag.geometry.attributes.position.array.slice(); sc.add(ag); }
        const n = cn.acao === 'multidao' ? 14 : (cn.atores || ['pessoa']).length;
        for (let i = 0; i < Math.min(14, n); i++) { const p = pessoa(['#E46A86', '#3E7CB1', '#F2B705', '#5DAA5A'][i % 4]); p.position.set(i === 0 ? 0 : (r() - 0.5) * 8, 0, i === 0 ? 1.5 : (r() - 0.5) * 4); p.rotation.y = i === 0 ? 0 : (r() - 0.5) * 2; p.userData.xInicial = p.position.x; sc.add(p); obj.gente.push(p); }
      }
      if (cn.acao === 'chuva_meteoros') { for (let i = 0; i < 14; i++) { const m = new T.Mesh(new T.IcosahedronGeometry(0.3 + r() * 0.3, 0), M('#8A6A55', '#FF5A1F')); m.userData = { x: (r() - 0.5) * 16, z: (r() - 0.5) * 10 - 2, fase: r() }; sc.add(m); obj.meteoros.push(m); } }
      if (cn.acao === 'gravidade_zero') { for (let i = 0; i < 18; i++) { const m = new T.Mesh(new T.BoxGeometry(0.5, 0.5, 0.5), M(['#E2574C', '#F2B705', '#3E7CB1', '#5DAA5A'][i % 4])); m.userData = { x: (r() - 0.5) * 10, z: (r() - 0.5) * 8, fase: r() }; sc.add(m); obj.meteoros.push(m); } }
      return obj;
    }
    const cenas = spec.cenas.map(montar);
    const cam = new T.PerspectiveCamera(40, W / H, 0.1, 200);

    function animarPessoa(p, t, modo) {
      const m = p.userData.membros, a = t * (modo === 'corre' ? 11 : 5);
      const amp = modo === 'parado' ? 0.08 : (modo === 'corre' ? 1.1 : 0.6);
      m[0].rotation.x = Math.sin(a) * amp; m[1].rotation.x = -Math.sin(a) * amp; m[2].rotation.x = -Math.sin(a) * amp; m[3].rotation.x = Math.sin(a) * amp;
      if (modo === 'surpreso') { m[0].rotation.z = 2.6; m[1].rotation.z = -2.6; }
      p.position.y = modo === 'parado' ? 0 : Math.abs(Math.sin(a)) * 0.15;
      p.userData.cab.rotation.z = Math.sin(t * 1.3) * 0.1;
    }

    function quadro(t) {
      const { c: cn, i, k, local } = U.cenaEm(spec, t);
      const o = cenas[i], acao = cn.acao || 'orbita';
      // camera: orbita lenta como base; `zoom_in`/`zoom_out`/`sobrevoo` mudam o caminho
      const ang = 0.35 * Math.sin(t * 0.25) + (acao === 'orbita' ? k * 1.4 : 0);
      let dist = o.globo ? 17 : 17, alt = o.globo ? 1.5 : 7.5;
      if (cn.camera === 'zoom_in') dist *= U.lerp(1.25, 0.7, U.suave(k));
      if (cn.camera === 'zoom_out') dist *= U.lerp(0.7, 1.3, U.suave(k));
      if (cn.camera === 'sobrevoo') { alt = 12; dist = 7; }
      cam.position.set(Math.sin(ang) * dist, alt, Math.cos(ang) * dist); cam.lookAt(0, o.globo ? 0 : 1.6, 0);
      if (acao === 'tremor' || (acao === 'para_de_girar' && k > 0.3 && k < 0.6)) { const r = U.rng(Math.floor(t * 30)); cam.position.x += (r() - 0.5) * 0.4; cam.position.y += (r() - 0.5) * 0.3; }
      // o evento
      if (o.globo) {
        // o angulo e' a INTEGRAL da velocidade (frear multiplicando o angulo
        // faria o globo girar para tras)
        const D = Math.max(0.01, cn.fim - cn.ini), vel = (s) => (acao === 'para_de_girar' ? 1 - U.saida(U.clamp((s / D) * 1.6, 0, 1)) : 1);
        let ang = 0; const n = 48; for (let j = 0; j < n; j++) ang += vel(((j + 0.5) / n) * local) * (local / n);
        o.globo.rotation.y = cn.ini * 0.5 + ang * 0.5;
      }
      o.extras.forEach((e, j) => { if (e.geometry && e.geometry.type === 'BoxGeometry') e.position.x = ((t * 2.2 + j * 4) % 18) - 9; });
      o.gente.forEach((p, j) => {
        const modo = acao === 'corre' || acao === 'chuva_meteoros' ? 'corre' : (acao === 'para_de_girar' || acao === 'tremor' ? 'surpreso' : (j === 0 && acao === 'anda' ? 'anda' : 'parado'));
        animarPessoa(p, t + j * 0.3, modo);
        if (j === 0 && acao === 'cresce') p.scale.setScalar(U.lerp(1, 3.2, U.saida(k)));
        if (j === 0 && acao === 'encolhe') p.scale.setScalar(U.lerp(1, 0.25, U.saida(k)));
        if (acao === 'gravidade_zero') { p.position.y = U.saida(k) * (2 + j * 0.4); p.rotation.x = k * (j % 2 ? 1 : -1); }
        if (acao === 'para_de_girar') { p.position.x = p.userData.xInicial + Math.max(0, k - 0.3) * 0.2; p.rotation.z = -0.5 * U.saida(U.clamp((k - 0.3) / 0.7, 0, 1)); }
      });
      if (o.agua) { const a = o.agua.geometry.attributes.position, base = o.aguaBase; for (let j = 0; j < a.count; j++) a.setZ(j, base[j * 3 + 2] + Math.sin(base[j * 3] * 0.8 + t * 2) * 0.12 + Math.cos(base[j * 3 + 1] * 0.7 + t * 1.6) * 0.1); a.needsUpdate = true;
        if (acao === 'inunda') o.agua.position.y = U.lerp(-0.2, 2.2, U.suave(k)); }
      o.meteoros.forEach((m) => { const d = m.userData;
        if (acao === 'chuva_meteoros') { const q = (local * 0.6 + d.fase) % 1; m.position.set(d.x + 6 * (1 - q), 14 * (1 - q), d.z); m.rotation.x = q * 6; }
        else { m.position.set(d.x, U.saida(k) * (1 + d.fase * 4) + 0.3, d.z); m.rotation.set(t * d.fase, t * (1 - d.fase), 0); } });
      // tinta do evento por cima do mundo
      R.render(o.sc, cam);
      c.drawImage(gl, 0, 0, W, H);
      const tinta = { congela: 'rgba(150,210,255,', esquenta: 'rgba(255,120,40,', noite_eterna: 'rgba(5,10,40,' }[acao];
      if (tinta) { c.fillStyle = tinta + (0.45 * U.suave(k)).toFixed(3) + ')'; c.fillRect(0, 0, W, H); }
      if (acao === 'congela' && k > 0.4) { c.strokeStyle = 'rgba(255,255,255,.6)'; c.lineWidth = 6; const r = U.rng(5); for (let j = 0; j < 12; j++) { const x = r() * W, y = r() * H, l = 80 + r() * 120; c.beginPath(); c.moveTo(x, y); c.lineTo(x + l, y + l * 0.4); c.stroke(); } }
      // passagem: corte com flash curto de 0,1 s
      if (i > 0 && t - cn.ini < 0.1) { c.fillStyle = 'rgba(255,255,255,' + (0.6 * (1 - (t - cn.ini) / 0.1)).toFixed(2) + ')'; c.fillRect(0, 0, W, H); }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 170, fundo: '#FFD23F', borda: '#1B1B1B', cor: '#1B1B1B', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '104px "Lilita One", sans-serif', y: H * 0.80, cor: '#FFFFFF', cor_ativa: '#FFD23F', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro };
  }
  MOTORES.lowpoly = { criar };
})();

