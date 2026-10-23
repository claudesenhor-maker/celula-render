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
  function criar(tela, spec, U) {
    const T = window.THREE, c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const gl = document.createElement('canvas'); gl.width = W; gl.height = H;
    const R = new T.WebGLRenderer({ canvas: gl, antialias: true, preserveDrawingBuffer: true }); R.setSize(W, H, false);
    const cam = new T.PerspectiveCamera(36, W / H, 0.01, 5000);
    const sc = new T.Scene();
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const vet = (v, a, b, p) => [0, 1, 2].map((i) => num(Array.isArray(v) ? v[i] : undefined, a, b, p[i]));
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const M = (cor) => new T.MeshStandardMaterial({ color: cor, roughness: 0.8, metalness: 0.02, flatShading: true });
    const F = {
      caixa: () => new T.BoxGeometry(1, 1, 1), esfera: () => new T.IcosahedronGeometry(0.5, 1), cone: () => new T.ConeGeometry(0.5, 1, 9),
      cilindro: () => new T.CylinderGeometry(0.5, 0.5, 1, 12), icosa: () => new T.IcosahedronGeometry(0.5, 0), toro: () => new T.TorusGeometry(0.4, 0.12, 8, 18),
      piramide: () => new T.ConeGeometry(0.6, 1, 4), capsula: () => (T.CapsuleGeometry ? new T.CapsuleGeometry(0.3, 0.4, 4, 10) : new T.CylinderGeometry(0.5, 0.5, 1, 14)),
    };

    // ---- savana ao entardecer: ceu quente, chao de terra com faixas de capim
    { const cv = document.createElement('canvas'); cv.width = 4; cv.height = 256; const g = cv.getContext('2d'); const gr = g.createLinearGradient(0, 0, 0, 256);
      gr.addColorStop(0, '#2B5C8A'); gr.addColorStop(0.55, '#E8A86A'); gr.addColorStop(0.8, '#F6D29A'); gr.addColorStop(1, '#F6D29A'); g.fillStyle = gr; g.fillRect(0, 0, 4, 256); sc.background = new T.CanvasTexture(cv); }
    sc.fog = new T.Fog('#F0C890', 40, 260);
    sc.add(new T.HemisphereLight('#FFF4E0', '#6B5A3A', 0.7));
    const sol = new T.DirectionalLight('#FFE2B8', 0.95); sol.position.set(-6, 9, 7); sc.add(sol);
    const texChao = (() => { const cv = document.createElement('canvas'); cv.width = cv.height = 256; const g = cv.getContext('2d'); g.fillStyle = '#C9A46A'; g.fillRect(0, 0, 256, 256);
      const r = U.rng(5); for (let i = 0; i < 900; i++) { g.fillStyle = r() < 0.5 ? 'rgba(120,96,50,0.25)' : 'rgba(150,170,80,0.28)'; g.fillRect(r() * 256, r() * 256, 2 + r() * 6, 2 + r() * 3); }
      const t = new T.CanvasTexture(cv); t.wrapS = t.wrapT = T.RepeatWrapping; return t; })();
    const chao = new T.Mesh(new T.PlaneGeometry(2000, 2000), new T.MeshStandardMaterial({ map: texChao, roughness: 1 })); chao.rotation.x = -Math.PI / 2; sc.add(chao);
    // acacias e pedras ao longe (paisagem fixa, da semente)
    { const r = U.rng(spec.semente || 'savana');
      for (let i = 0; i < 26; i++) { const g = new T.Group(); const d = 30 + r() * 150, a = (r() - 0.5) * Math.PI * 1.6;
        const tr = new T.Mesh(F.cilindro(), M('#5B4128')); tr.scale.set(0.35, 3, 0.35); tr.position.y = 1.5; g.add(tr);
        const cp = new T.Mesh(F.esfera(), M('#5E7A3A')); cp.scale.set(5, 1.3, 4); cp.position.y = 3.3; g.add(cp);
        g.position.set(Math.sin(a) * d, 0, -Math.cos(a) * d); g.scale.setScalar(0.8 + r() * 1.4); sc.add(g); } }

    // ---- o animal (normalizado: o COMPRIMENTO vira `tamanho_m` metros)
    const an = spec.animal || {}, tamReal = num(an.tamanho_m, 0.01, 40, 2);
    const bicho = new T.Group(), corpo = new T.Group(); bicho.add(corpo); sc.add(bicho);
    const moveis = [];
    (Array.isArray(an.partes) ? an.partes.slice(0, 30) : []).forEach((p, i) => {
      const m = new T.Mesh((F[p.forma] || F.caixa)(), M(corOk(p.cor, '#9A7B55')));
      const pos = vet(p.pos, -10, 10, [0, 0.5, 0]), tam = vet(p.tam, 0.01, 10, [1, 1, 1]), giro = vet(p.giro, -360, 360, [0, 0, 0]).map((a) => (a * Math.PI) / 180);
      m.position.set(...pos); m.scale.set(...tam); m.rotation.set(...giro);
      const nome = String(p.nome || '').toLowerCase();
      const tipo = /leg|perna|pata|paw|foot|pe\b/.test(nome) ? 'perna' : /tail|cauda|rabo/.test(nome) ? 'cauda' : /wing|asa|fin|nadadeira/.test(nome) ? 'asa' : /jaw|mandibula|boca|mouth/.test(nome) ? 'boca' : null;
      m.userData = { giro, tipo, fase: i * 1.7 }; corpo.add(m); if (tipo) moveis.push(m);
    });
    if (!corpo.children.length) { const m = new T.Mesh(F.capsula(), M('#9A7B55')); m.rotation.z = Math.PI / 2; m.scale.set(1, 2, 1); m.position.y = 0.6; corpo.add(m); }
    { const b = new T.Box3().setFromObject(corpo), s = new T.Vector3(); b.getSize(s); const comp = Math.max(1e-3, s.x, s.z, s.y * 0.6);
      const k = tamReal / comp; corpo.scale.setScalar(k); corpo.position.y = -b.min.y * k; }
    const caixaB = new T.Box3().setFromObject(bicho), tamB = new T.Vector3(); caixaB.getSize(tamB);
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

    const hfov = 2 * Math.atan(Math.tan((cam.fov * Math.PI) / 360) * cam.aspect);
    function quadroDo3D(t) {
      const { c: cn, i, k, local } = U.cenaEm(spec, t), acao = cn.acao || 'mostra';
      const comp = acao === 'compara', corre = acao === 'corre', ataca = acao === 'ataca';
      // pernas, cauda, asas e boca
      moveis.forEach((m) => { const u = m.userData; m.rotation.set(...u.giro);
        const vel = corre ? 11 : 2.2, amp = corre ? 0.55 : 0.08;
        if (u.tipo === 'perna') m.rotation.z += Math.sin(t * vel + u.fase) * amp;
        if (u.tipo === 'cauda') m.rotation.y += Math.sin(t * 3 + u.fase) * 0.35;
        if (u.tipo === 'asa') m.rotation.x += Math.sin(t * (corre ? 14 : 4) + u.fase) * 0.5;
        if (u.tipo === 'boca') m.rotation.z += ataca ? -Math.max(0, Math.sin(Math.min(1, k * 1.6) * Math.PI)) * 0.6 : 0; });
      // respira; no `corre` quica; no `ataca` da o bote
      corpo.scale.y = corpo.scale.x * (1 + 0.015 * Math.sin(t * 2.4));
      let x = 0, y = 0;
      if (corre) y = Math.abs(Math.sin(t * 11)) * tamB.y * 0.05;
      if (ataca) x = Math.sin(U.clamp(k * 1.6, 0, 1) * Math.PI) * tamB.x * 0.35;
      bicho.position.set(x, y, 0);
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
      R.render(sc, cam); c.drawImage(gl, 0, 0, W, H);
      return { cn, i, k, local, acao };
    }

    const fmt = (v) => (Math.abs(v) >= 1e6 ? (v / 1e6).toLocaleString('en-US', { maximumFractionDigits: 1 }) + 'M' : Math.abs(v) >= 1e4 ? Math.round(v).toLocaleString('en-US')
      : v.toLocaleString('en-US', { maximumFractionDigits: Math.abs(v) < 10 ? 1 : 0 }));
    // CARTAO DO NUMERO: conta ate o valor e compara com o humano em barras
    function cartao(st, local) {
      if (!st) return;
      const ent = U.mola(local - 0.1, 10); if (ent <= 0) return;
      const q = U.suave(U.clamp((local - 0.25) / 1.1, 0, 1));
      const x0 = 70, w = W - 140, y0 = H * 0.42, h = 360;
      c.save(); c.translate(W / 2, y0 + h / 2); c.scale(ent, ent); c.translate(-W / 2, -(y0 + h / 2));
      U.rr(c, x0, y0, w, h, 34); c.fillStyle = 'rgba(24,20,14,0.86)'; c.fill(); c.lineWidth = 6; c.strokeStyle = '#F6C445'; c.stroke();
      c.textBaseline = 'middle'; c.textAlign = 'left'; c.font = '50px "Lilita One", sans-serif'; c.fillStyle = '#F6C445'; c.fillText(st.nome, x0 + 40, y0 + 58);
      c.textAlign = 'right'; c.font = '96px "Lilita One", sans-serif'; c.fillStyle = '#FFFFFF'; c.fillText(fmt(st.valor * q) + (st.unidade ? ' ' + st.unidade.toUpperCase() : ''), x0 + w - 40, y0 + 64);
      if (st.humano != null && st.valor > 0) {
        const mx = Math.max(st.valor, st.humano, 1e-9), bw = w - 260, by = y0 + 150;
        const nomeA = String((spec.animal || {}).nome || 'ANIMAL').toUpperCase().slice(0, 9);
        [[nomeA, st.valor, '#F6C445'], ['HUMAN', st.humano, '#9AA7B8']].forEach(([n, v, cor], j) => {
          const yy = by + j * 82; c.textAlign = 'left'; c.font = '40px "Lilita One", sans-serif'; c.fillStyle = cor; c.fillText(n, x0 + 40, yy + 26);
          U.rr(c, x0 + 220, yy, bw, 52, 14); c.fillStyle = 'rgba(255,255,255,0.12)'; c.fill();
          U.rr(c, x0 + 220, yy, Math.max(14, bw * (v / mx) * q), 52, 14); c.fillStyle = cor; c.fill();
        });
        const vezes = st.humano > 0 ? st.valor / st.humano : 0;
        if (vezes >= 1.5 && q > 0.9) { const s = U.mola(local - 1.35, 12); c.save(); c.translate(x0 + w - 120, y0 + h - 4); c.rotate(-0.08); c.scale(s, s);
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
      if (acao === 'stat') cartao(statDe(cn, i), local);
      if (acao === 'corre') velocimetro(statDe(cn, i), local);
      etiquetaAltura(acao, local);
      if (cn.hud && typeof cn.hud !== 'object' && acao !== 'stat' && local > 0.3) { const s = U.mola(local - 0.3, 10); c.save(); c.translate(W / 2, 330); c.scale(s, s);
        c.font = '120px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; const txt = String(cn.hud).toUpperCase().slice(0, 14), w = c.measureText(txt).width + 70;
        U.rr(c, -w / 2, -78, w, 156, 34); c.fillStyle = '#1B1B1B'; c.fill(); c.fillStyle = '#F6C445'; c.fillText(txt, 0, 6); c.restore(); }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 150, fundo: '#F6C445', borda: '#1B1B1B', cor: '#1B1B1B', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '100px "Lilita One", sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#F6C445', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro };
  }
  MOTORES.animal = { criar };
})();
