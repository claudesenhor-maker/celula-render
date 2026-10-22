// MECANISMO -- "Como funciona" em 3D (22/10, ordem do dono: um nicho e um motor
// por canal; "como funciona" e' o nicho em alta que ele pediu).
//
// O canal explica como uma coisa funciona por dentro (fechadura, descarga,
// motor a combustao, ziper, caneta, freio). Nao existe catalogo de objetos: o
// roteirista (IA) DESCREVE o objeto do video em `spec.modelo`, peca por peca,
// com nome, forma, cor, posicao, e como cada peca se comporta (`casca` some no
// corte; `explode` e' para onde ela vai na vista explodida; `eixo` e' em torno
// de que ela gira). Nada e' executado como codigo: e' dado, e numero fora da
// faixa e' cortado.
//
// Cada cena diz o que se ve enquanto a frase e' dita:
//   mostra   o objeto inteiro girando no estudio
//   explode  as pecas se afastam (vista explodida)       | monta: o contrario
//   corte    a casca fica transparente e o miolo aparece
//   destaque `alvo` (nomes de pecas) brilha, o resto apaga
//   gira     as pecas de `alvo` giram no proprio `eixo` (engrenagens, rotor)
//   move     as pecas de `alvo` deslizam ate `mover` e voltam (pistao, trava)
//   fluxo    particulas correm pelos pontos de `fluxo.caminho` (agua, ar, corrente)
// `rotulos`: [{parte, texto}] -- etiqueta com linha ate a peca, sempre legivel.
//
// CONTRATO (comum.js): `quadro(t)` sem estado entre quadros.
(function () {
  'use strict';
  const FORMAS = (T) => ({
    caixa: () => new T.BoxGeometry(1, 1, 1), esfera: () => new T.IcosahedronGeometry(0.5, 1), cone: () => new T.ConeGeometry(0.5, 1, 10),
    cilindro: () => new T.CylinderGeometry(0.5, 0.5, 1, 14), tubo: () => new T.CylinderGeometry(0.5, 0.5, 1, 14, 1, true),
    icosa: () => new T.IcosahedronGeometry(0.5, 0), toro: () => new T.TorusGeometry(0.4, 0.12, 8, 20), piramide: () => new T.ConeGeometry(0.6, 1, 4),
    engrenagem: () => engrenagem(T), mola: () => mola(T), seta: () => seta(T),
  });
  function engrenagem(T) {
    const s = new T.Shape(), n = 12, r1 = 0.5, r2 = 0.4;
    for (let i = 0; i < n * 2; i++) { const a = (i / (n * 2)) * Math.PI * 2, r = i % 2 ? r2 : r1; const a2 = a + Math.PI / (n * 2);
      if (i === 0) s.moveTo(Math.cos(a) * r, Math.sin(a) * r); else s.lineTo(Math.cos(a) * r, Math.sin(a) * r); s.lineTo(Math.cos(a2) * r, Math.sin(a2) * r); }
    const furo = new T.Path(); furo.absarc(0, 0, 0.12, 0, Math.PI * 2, true); s.holes.push(furo);
    const g = new T.ExtrudeGeometry(s, { depth: 0.2, bevelEnabled: false }); g.translate(0, 0, -0.1); g.rotateX(Math.PI / 2); return g;
  }
  function mola(T) {
    const pts = []; for (let i = 0; i <= 120; i++) { const a = i * 0.42; pts.push(new T.Vector3(Math.cos(a) * 0.4, -0.5 + i / 120, Math.sin(a) * 0.4)); }
    return new T.TubeGeometry(new T.CatmullRomCurve3(pts), 160, 0.05, 6, false);
  }
  function seta(T) { const g = new T.ConeGeometry(0.3, 0.5, 8); g.translate(0, 0.25, 0); return g; }

  function criar(tela, spec, U) {
    const T = window.THREE, c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const gl = document.createElement('canvas'); gl.width = W; gl.height = H;
    const R = new T.WebGLRenderer({ canvas: gl, antialias: true, preserveDrawingBuffer: true }); R.setSize(W, H, false);
    const cam = new T.PerspectiveCamera(34, W / H, 0.1, 300);
    const sc = new T.Scene();
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const vet = (v, a, b, p) => [0, 1, 2].map((i) => num(Array.isArray(v) ? v[i] : undefined, a, b, p[i]));
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);

    // ---- estudio: fundo azul de prancheta, chao com grade, luz de tres pontos
    { const cv = document.createElement('canvas'); cv.width = 4; cv.height = 256; const g = cv.getContext('2d'); const gr = g.createLinearGradient(0, 0, 0, 256);
      gr.addColorStop(0, '#0E2340'); gr.addColorStop(0.7, '#1D4A7A'); gr.addColorStop(1, '#2A6299'); g.fillStyle = gr; g.fillRect(0, 0, 4, 256); sc.background = new T.CanvasTexture(cv); }
    sc.add(new T.HemisphereLight('#dfefff', '#1a2a40', 0.65));
    const key = new T.DirectionalLight('#ffffff', 0.85); key.position.set(6, 10, 8); sc.add(key);
    const rim = new T.DirectionalLight('#9fd0ff', 0.45); rim.position.set(-8, 4, -6); sc.add(rim);
    const grade = new T.GridHelper(30, 30, '#5f8fc4', '#355d8a'); grade.position.y = -0.001; grade.material.transparent = true; grade.material.opacity = 0.35; sc.add(grade);
    { const cv = document.createElement('canvas'); cv.width = cv.height = 64; const g = cv.getContext('2d'); const gr = g.createRadialGradient(32, 32, 0, 32, 32, 32);
      gr.addColorStop(0, 'rgba(0,0,0,0.45)'); gr.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gr; g.fillRect(0, 0, 64, 64);
      const s0 = new T.Mesh(new T.PlaneGeometry(1, 1), new T.MeshBasicMaterial({ map: new T.CanvasTexture(cv), transparent: true, depthWrite: false })); s0.rotation.x = -Math.PI / 2; s0.position.y = 0.01; sc.add(s0); sc.userData.sombra = s0; }

    // ---- o objeto, peca por peca
    const F = FORMAS(T), mod = spec.modelo || {}, raiz = new T.Group(); sc.add(raiz);
    const pecas = {}, lista = [];
    (Array.isArray(mod.partes) ? mod.partes.slice(0, 40) : []).forEach((p, i) => {
      const nome = String(p.nome || 'peca' + i).slice(0, 40), cor = corOk(p.cor, '#B8C4D0');
      const mat = new T.MeshStandardMaterial({ color: cor, roughness: p.metal ? 0.35 : 0.7, metalness: p.metal ? 0.6 : 0.05, flatShading: true, transparent: true, opacity: 1,
        emissive: '#000000', side: (p.forma === 'tubo' ? T.DoubleSide : T.FrontSide) });
      const m = new T.Mesh((F[p.forma] || F.caixa)(), mat);
      const pos = vet(p.pos, -20, 20, [0, 0.5, 0]), tam = vet(p.tam, 0.01, 20, [1, 1, 1]), giro = vet(p.giro, -360, 360, [0, 0, 0]).map((a) => (a * Math.PI) / 180);
      m.position.set(...pos); m.scale.set(...tam); m.rotation.set(...giro);
      m.userData = { nome, pos, giro, casca: !!p.casca, explode: vet(p.explode, -20, 20, [0, 0, 0]), eixo: vet(p.eixo, -1, 1, [0, 1, 0]), cor: new T.Color(cor) };
      raiz.add(m); pecas[nome.toLowerCase()] = m; lista.push(m);
    });
    // enquadra: o objeto cabe na tela inteira, sobre o chao
    const caixa = new T.Box3().setFromObject(raiz), tamObj = new T.Vector3(), centro = new T.Vector3(); caixa.getSize(tamObj); caixa.getCenter(centro);
    const esc = num(mod.escala, 0.1, 10, 1) * (lista.length ? 4.2 / Math.max(0.3, tamObj.x, tamObj.y * 0.75, tamObj.z) : 1);
    raiz.scale.setScalar(esc); raiz.position.set(-centro.x * esc, -caixa.min.y * esc, -centro.z * esc);
    const altura = tamObj.y * esc;
    // ENQUADRAMENTO: a esfera que contem o objeto MONTADO e a que contem o
    // EXPLODIDO; a camera recua o que precisa para a da vez caber na largura
    // (9:16 -- a largura e' o lado curto).
    function esfera(ex) {
      lista.forEach((m) => { const u = m.userData; m.position.set(u.pos[0] + u.explode[0] * ex, u.pos[1] + u.explode[1] * ex, u.pos[2] + u.explode[2] * ex); });
      const b = new T.Box3().setFromObject(raiz), cs = new T.Vector3(); b.getCenter(cs);
      return { c: cs, r: Math.max(0.5, b.getSize(new T.Vector3()).length() / 2) };
    }
    const E0 = lista.length ? esfera(0) : { c: new T.Vector3(0, 1, 0), r: 2 }, E1 = lista.length ? esfera(1) : E0;
    const hfov = 2 * Math.atan(Math.tan((cam.fov * Math.PI) / 360) * cam.aspect);
    const distPara = (r) => (r / Math.sin(hfov / 2)) * 1.02;
    sc.userData.sombra.scale.set(tamObj.x * esc * 1.6 + 1, tamObj.z * esc * 1.6 + 1, 1);
    if (!lista.length) console.log('[mecanismo] spec sem modelo.partes: estudio vazio');

    // particulas do fluxo (pontos ao longo do caminho)
    const NP = 90, fluxoGeo = new T.BufferGeometry(); fluxoGeo.setAttribute('position', new T.Float32BufferAttribute(new Float32Array(NP * 3), 3));
    const fluxoMat = new T.PointsMaterial({ color: '#7CE0FF', size: 0.22, transparent: true, opacity: 0.95, depthTest: false });
    const fluxo = new T.Points(fluxoGeo, fluxoMat); fluxo.frustumCulled = false; fluxo.renderOrder = 5; raiz.add(fluxo);

    const alvos = (cn) => (Array.isArray(cn.alvo) ? cn.alvo : cn.alvo ? [cn.alvo] : []).map((n) => pecas[String(n).toLowerCase()]).filter(Boolean);
    const cenas = spec.cenas;
    // estado de cada peca no instante t: o que as cenas ANTERIORES deixaram
    // (explodido continua explodido ate um "monta"), mais a cena atual
    function explodeEm(i, k) {
      let e = 0;
      // explodido continua explodido nas cenas de `destaque` seguintes (apontar
      // as pecas soltas); qualquer outra acao remonta no comeco da cena
      for (let j = 0; j < i; j++) { const a = cenas[j].acao; if (a === 'explode') e = 1; else if (a !== 'destaque') e = 0; }
      const a = cenas[i].acao;
      if (a === 'explode') return U.lerp(e, 1, U.suave(k * 1.6));
      if (a === 'destaque') return e;
      return U.lerp(e, 0, U.suave(k * (a === 'monta' ? 1.6 : 3.5)));
    }
    function corteEm(i, k) {
      let v = 0; for (let j = 0; j < i; j++) { if (cenas[j].acao === 'corte') v = 1; if (cenas[j].acao === 'monta' || cenas[j].acao === 'mostra') v = 0; }
      if (cenas[i].acao === 'corte') v = U.lerp(v, 1, U.suave(k * 2)); if (cenas[i].acao === 'monta' || cenas[i].acao === 'mostra') v = U.lerp(v, 0, U.suave(k * 2));
      return v;
    }

    function pose(t) {
      const { c: cn, i, k, local } = U.cenaEm(spec, t), acao = cn.acao || 'mostra', al = alvos(cn);
      const ex = explodeEm(i, k), co = corteEm(i, k);
      lista.forEach((m) => {
        const u = m.userData;
        m.position.set(u.pos[0] + u.explode[0] * ex, u.pos[1] + u.explode[1] * ex, u.pos[2] + u.explode[2] * ex);
        m.rotation.set(...u.giro);
        m.material.opacity = u.casca ? U.lerp(1, 0.14, co) : 1; m.material.depthWrite = m.material.opacity > 0.5;
        m.material.emissive.setRGB(0, 0, 0); m.material.color.copy(u.cor);
        if (acao === 'destaque' && al.length && al.indexOf(m) < 0) { m.material.color.copy(u.cor).multiplyScalar(U.lerp(1, 0.35, U.suave(k * 3))); }
      });
      al.forEach((m) => {
        const u = m.userData;
        if (acao === 'destaque') { const p = 0.35 + 0.25 * Math.sin(t * 6); m.material.emissive.copy(u.cor).multiplyScalar(p * U.suave(k * 3)); }
        if (acao === 'gira') { const ang = local * Math.PI * 2 * num(cn.voltas_por_s, 0.05, 4, 0.6); const e = new T.Vector3(...u.eixo).normalize(); m.rotateOnAxis(e, ang); }
        if (acao === 'move') { const mv = vet(cn.mover, -20, 20, [0, 0.5, 0]), q = 0.5 - 0.5 * Math.cos(Math.min(1, k * 1.15) * Math.PI * 2 * num(cn.ciclos, 0.5, 6, 1)); m.position.x += mv[0] * q; m.position.y += mv[1] * q; m.position.z += mv[2] * q; }
      });
      // fluxo: pontos correndo pelo caminho (coordenadas do modelo)
      const cam_ = cn.fluxo && Array.isArray(cn.fluxo.caminho) ? cn.fluxo.caminho.slice(0, 12).map((p) => new T.Vector3(...vet(p, -20, 20, [0, 0, 0]))) : null;
      fluxo.visible = acao === 'fluxo' && cam_ && cam_.length >= 2;
      if (fluxo.visible) {
        fluxoMat.color.set(corOk(cn.fluxo.cor, '#7CE0FF'));
        const curva = new T.CatmullRomCurve3(cam_), a = fluxoGeo.attributes.position, r = U.rng(31);
        for (let j = 0; j < NP; j++) { const q = (j / NP + local * 0.35) % 1, p = curva.getPointAt(q); a.setXYZ(j, p.x + (r() - 0.5) * 0.08, p.y + (r() - 0.5) * 0.08, p.z + (r() - 0.5) * 0.08); }
        a.needsUpdate = true; fluxoMat.opacity = 0.95 * U.suave(k * 4);
      }
      // camera: gira devagar em volta; perto/frente/cima mudam o caminho
      const r = U.lerp(E0.r, E1.r, ex), foco = E0.c.clone().lerp(E1.c, ex), D = distPara(r);
      let ang = 0.6 + t * 0.12 + Math.sin(t * 0.21) * 0.15, dist = D, y = foco.y + D * 0.3;
      const camN = cn.camera || 'orbita';
      if (camN === 'perto' && al.length) { const wp = new T.Vector3(); al[0].getWorldPosition(wp); const q = U.suave(k * 2); foco.lerp(wp, q * 0.7); dist = D * U.lerp(1, 0.7, q); y = foco.y + dist * 0.25; }
      if (camN === 'frente') { ang = 0.15 * Math.sin(t * 0.3); y = foco.y + D * 0.12; }
      if (camN === 'cima') { y = foco.y + D * 0.85; dist = D * 0.55; }
      dist *= 1 - 0.08 * (1 - U.saida(U.clamp(local / 0.5, 0, 1)));   // empurrao de entrada
      const hz = Math.sqrt(Math.max(0.01, dist * dist - (y - foco.y) * (y - foco.y)));
      cam.position.set(foco.x + Math.sin(ang) * hz, y, foco.z + Math.cos(ang) * hz); cam.lookAt(foco);
      return { cn, i, k, local };
    }

    // ---- 2D: rotulos com linha ate a peca, numero da frase, legenda
    function rotulos(cn, k, local) {
      const lst = Array.isArray(cn.rotulos) ? cn.rotulos.slice(0, 4) : [];
      lst.forEach((r, j) => {
        const m = pecas[String(r.parte || '').toLowerCase()]; if (!m || !r.texto) return;
        const q = U.saida(U.clamp((local - 0.25 - j * 0.35) / 0.4, 0, 1)); if (q <= 0) return;
        const wp = new T.Vector3(); m.getWorldPosition(wp); wp.project(cam);
        const px = (wp.x * 0.5 + 0.5) * W, py = (-wp.y * 0.5 + 0.5) * H;
        // coluna fixa a esquerda (a direita da tela tem os botoes do app): uma
        // etiqueta por linha, nunca uma sobre a outra
        c.save(); c.font = '56px "Lilita One", sans-serif';
        const txt = String(r.texto).toUpperCase().slice(0, 20), w = c.measureText(txt).width + 44, bx = 40, ey = 470 + j * 112;
        const lx = bx + w, ly = ey;
        c.globalAlpha = q; c.strokeStyle = '#FFD23F'; c.lineWidth = 5; c.beginPath(); c.moveTo(lx, ly); c.lineTo(lx + (px - lx) * q, ly + (py - ly) * q); c.stroke();
        if (q > 0.95) { c.fillStyle = '#FFD23F'; c.beginPath(); c.arc(px, py, 11, 0, Math.PI * 2); c.fill(); }
        U.rr(c, bx, ey - 42, w, 84, 20); c.fillStyle = '#FFD23F'; c.fill();
        c.fillStyle = '#10243F'; c.textAlign = 'left'; c.textBaseline = 'middle'; c.fillText(txt, bx + 22, ey + 3); c.restore();
      });
    }
    function numero(cn, local) {
      const txt = cn.hud != null && typeof cn.hud !== 'object' ? String(cn.hud).toUpperCase().slice(0, 16) : ''; if (!txt || local < 0.2) return;
      const s = U.mola(local - 0.2, 10); c.save(); c.translate(W / 2, cn.ini < 3.2 ? 540 : 330); c.scale(s, s);
      c.font = '130px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; const w = c.measureText(txt).width + 80;
      U.rr(c, -w / 2, -85, w, 170, 36); c.fillStyle = '#FFFFFF'; c.fill(); c.fillStyle = '#10243F'; c.fillText(txt, 0, 6); c.restore();
    }

    function quadro(t) {
      const { cn, i, k, local } = pose(t);
      R.render(sc, cam); c.drawImage(gl, 0, 0, W, H);
      if (i > 0 && local < 0.12) { c.fillStyle = 'rgba(255,255,255,' + (0.35 * (1 - local / 0.12)).toFixed(2) + ')'; c.fillRect(0, 0, W, H); }
      rotulos(cn, k, local); numero(cn, local);
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 170, fundo: '#FFFFFF', borda: '#10243F', cor: '#10243F', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '100px "Lilita One", sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#FFD23F', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro };
  }
  MOTORES.mecanismo = { criar };
})();
