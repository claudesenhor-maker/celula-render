// MICRO -- a pele por dentro, em corte 3D (24/10, canal SKIN DECODED; um nicho
// e um motor por canal). "O que esse ingrediente faz na sua pele": um bloco de
// pele cortado mostra as tres camadas (camada cornea em tijolos, epiderme em
// celulas, derme com colageno, vaso, pelo e glandula de oleo); as moleculas do
// ativo caem na superficie, entram ate' a camada certa e o efeito aparece.
// Linguagem do TINY WHAT IF (formas lisas, cores de produto), nada realista.
//
//   spec.ativo: { nome, cor: "#hex", forma: "cadeia|anel|esfera|cristal|gota", grande?: bool }
//     `grande`: molecula grande demais para entrar (fica na superficie como filme)
//   cena: { texto, acao, alvo?, efeito?, dado?, hud? }
//     acao "corte"    -- o bloco girando devagar; as camadas ganham nome uma a uma
//     acao "aplica"   -- uma gota do produto cai, espalha, e as moleculas aparecem
//     acao "entra"    -- as moleculas descem ate' `alvo`: superficie|epiderme|derme
//     acao "molecula" -- a molecula do ativo de perto, girando, com o nome
//     acao "efeito"   -- `efeito`: hidrata|barreira|manchas|colageno|oleo|protege|esfolia|acalma
//     acao "dado"     -- o cartao de um numero: dado = { rotulo, valor }
//
// O roteiro nunca promete cura: o efeito desenhado e' o mecanismo ("ajuda a
// segurar agua"), e o texto da cena e' quem fala (regra do canal).
// CONTRATO (comum.js): `quadro(t)` sem estado entre quadros.
(function () {
  'use strict';
  const PROF = { superficie: -0.08, epiderme: -0.72, derme: -1.85 };
  const EFEITOS = ['hidrata', 'barreira', 'manchas', 'colageno', 'oleo', 'protege', 'esfolia', 'acalma'];
  function criar(tela, spec, U) {
    const T = window.THREE, c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const gl = document.createElement('canvas'); gl.width = W; gl.height = H;
    const R = new T.WebGLRenderer({ canvas: gl, antialias: true, preserveDrawingBuffer: true }); R.setSize(W, H, false);
    const cam = new T.PerspectiveCamera(34, W / H, 0.05, 200);
    const sc = new T.Scene();
    const T3 = !!window.U3;
    if (T3) U3.estudio(R, sc, T, { exposicao: 1.05, reflexo: false });
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const M = (cor, tipo, op) => {
      const m = T3 ? U3.material(T, cor, tipo || 'plastico') : new T.MeshStandardMaterial({ color: cor, roughness: 0.6 });
      if (op != null) { m.transparent = true; m.opacity = op; m.userData.opacidadeBase = op; }
      return m;
    };
    const rnd = U.rng(String(spec.semente || spec.fila_id || 'micro'));
    const ativo = Object.assign({ nome: 'Active', cor: '#5BC0EB', forma: 'cadeia' }, spec.ativo || {});
    ativo.cor = corOk(ativo.cor, '#5BC0EB'); ativo.nome = String(ativo.nome || 'Active').slice(0, 28);

    // fundo: gradiente de "laboratorio de cosmetico" (lilas -> menta), preso na tela
    { const cv = document.createElement('canvas'); cv.width = 16; cv.height = 512; const g = cv.getContext('2d');
      const gr = g.createLinearGradient(0, 0, 0, 512); gr.addColorStop(0, '#F6E3EE'); gr.addColorStop(0.55, '#E7DDF6'); gr.addColorStop(1, '#D6EFE8');
      g.fillStyle = gr; g.fillRect(0, 0, 16, 512); const tx = new T.CanvasTexture(cv); if (T3) tx.encoding = T.sRGBEncoding; sc.background = tx; }
    sc.add(new T.HemisphereLight('#FFFFFF', '#E9C9C0', 0.75));
    const sol = new T.DirectionalLight('#FFF4EC', 1.45); sol.position.set(2.5, 5, 4); sc.add(sol); sc.add(sol.target);
    const contra = new T.DirectionalLight('#CFE6FF', 0.45); contra.position.set(-4, 2, -3); sc.add(contra);

    // ======================= O BLOCO DE PELE =======================
    // x: -2,2..2,2 (largura), z: -1,2..1,2 (fundo), y: 0 = superficie
    const LX = 2.2, LZ = 1.2, Y_CORNEA = -0.24, Y_DERME = -1.2, Y_FUNDO = -3.0;
    const pele = new T.Group(); sc.add(pele);
    const F = T3 ? U3.formas(T) : null;
    const geoCaixa = F ? F.caixa() : new T.BoxGeometry(1, 1, 1);
    // bloco solido por tras (o corte mostra as celulas na frente)
    const solido = (y0, y1, cor, op) => { const m = new T.Mesh(new T.BoxGeometry(LX * 2, y0 - y1, LZ * 2 - 0.5), M(cor, 'tecido', op));
      m.position.set(0, (y0 + y1) / 2, -0.25); pele.add(m); return m; };
    solido(Y_CORNEA, Y_DERME, '#E9A994'); const dermeSolida = solido(Y_DERME, Y_FUNDO, '#F1BDB1');
    // camada cornea: tijolos (corneocitos) com a "argamassa" de lipideos entre eles
    // a argamassa fica um pouco para dentro: a fila de cima e a da frente dos tijolos aparecem
    const argamassa = new T.Mesh(new T.BoxGeometry(LX * 2 - 0.04, -Y_CORNEA - 0.07, LZ * 2 - 0.34), M('#F6E08E', 'ceramica', 0.55));
    argamassa.position.set(0, (Y_CORNEA - 0.05) / 2, -0.17); pele.add(argamassa);
    // material unico (um draw state so'); so' o esfolia, que solta tijolo por tijolo, precisa de um por tijolo
    const soltaTijolo = (spec.cenas || []).some((q) => q.acao === 'efeito' && q.efeito === 'esfolia'), matTij = M('#F7DCCB', 'tecido');
    const tijolos = [];
    for (let fila = 0; fila < 3; fila++) for (let x = -LX + 0.22 - (fila % 2) * 0.2; x < LX - 0.1; x += 0.44) for (let z = -LZ + 0.2; z < LZ; z += 0.4) {
      const m = new T.Mesh(geoCaixa, soltaTijolo ? M('#F7DCCB', 'tecido') : matTij); const y = -0.04 - fila * 0.075;
      m.scale.set(0.4, 0.055, 0.36); m.position.set(x, y, z); pele.add(m);
      tijolos.push({ m, x, y, z, fila, r: rnd() });
    }
    // epiderme: celulas (instanciadas: centenas de esferas a custo de uma)
    const geoCel = new T.SphereGeometry(0.5, 20, 14);
    const celulas = []; for (let y = Y_CORNEA - 0.12; y > Y_DERME + 0.08; y -= 0.17) for (let x = -LX + 0.12; x < LX; x += 0.2) for (let z = 0.15; z < LZ; z += 0.25)
      celulas.push({ x: x + (rnd() - 0.5) * 0.05, y: y + (rnd() - 0.5) * 0.04, z, s: 0.17 + rnd() * 0.03, basal: y < Y_DERME + 0.25 });
    const celInst = new T.InstancedMesh(geoCel, M('#F0B3A0', 'tecido'), celulas.length); pele.add(celInst);
    // melanina: pontinhos escuros na camada basal (o que faz a mancha)
    const melanina = celulas.filter((q) => q.basal && rnd() < 0.55).map((q) => ({ x: q.x + 0.05, y: q.y + 0.05, z: q.z + 0.09, s: 0.05 + rnd() * 0.03 }));
    const melInst = new T.InstancedMesh(geoCel, M('#5B3A29', 'tecido'), Math.max(1, melanina.length)); melInst.count = melanina.length; pele.add(melInst);
    // derme: fibras de colageno (tubos ondulados), um vaso, o pelo e a glandula de oleo
    const fibras = [];
    for (let k = 0; k < 9; k++) {
      const y0 = Y_DERME - 0.3 - k * 0.17, z0 = 0.6 + (k % 3) * 0.2, fase = rnd() * 6, pts = [];
      for (let i = 0; i <= 24; i++) { const x = -LX + (i / 24) * LX * 2; pts.push(new T.Vector3(x, y0 + Math.sin(x * 2.2 + fase) * 0.07, z0 + Math.cos(x * 1.7 + fase) * 0.05)); }
      const m = new T.Mesh(new T.TubeGeometry(new T.CatmullRomCurve3(pts), 60, 0.035, 8, false), M('#FBEBDD', 'tecido')); pele.add(m); fibras.push(m);
    }
    const vasoPts = []; for (let i = 0; i <= 30; i++) { const x = -LX + (i / 30) * LX * 2; vasoPts.push(new T.Vector3(x, Y_FUNDO + 0.45 + Math.sin(x * 1.3) * 0.12, 0.95)); }
    const vaso = new T.Mesh(new T.TubeGeometry(new T.CatmullRomCurve3(vasoPts), 60, 0.09, 12, false), M('#D2414B', 'plastico')); pele.add(vaso);
    const XF = 1.15;
    const foliculo = new T.Mesh(new T.CylinderGeometry(0.13, 0.17, 2.3, 20, 1, true), M('#D99482', 'tecido')); foliculo.position.set(XF, -1.15, 0.95); pele.add(foliculo);
    const pelo = new T.Mesh(new T.CylinderGeometry(0.035, 0.045, 3.4, 10), M('#3A2618', 'tecido')); pelo.position.set(XF, -0.35, 0.95); pelo.rotation.z = -0.08; pele.add(pelo);
    const glandula = new T.Mesh(new T.SphereGeometry(0.5, 24, 16), M('#F2D06B', 'ceramica', 0.92)); glandula.position.set(XF - 0.3, -1.45, 0.95); pele.add(glandula);
    const sebo = new T.Mesh(new T.SphereGeometry(0.5, 20, 12), M('#F5DA7A', 'ceramica', 0.85)); sebo.position.set(XF, 0.02, 0.95); pele.add(sebo);
    // filtro solar (efeito protege): uma pelicula sobre a pele
    const filme = new T.Mesh(new T.BoxGeometry(LX * 2.02, 0.05, LZ * 2.02), M(ativo.cor, 'vidro', 0)); filme.position.y = 0.06; pele.add(filme);
    // raios UV (efeito protege)
    const raios = []; for (let k = 0; k < 7; k++) {
      const g = new T.Group(), haste = new T.Mesh(new T.CylinderGeometry(0.03, 0.03, 0.8, 8), M('#8E5BE8', 'plastico')), ponta = new T.Mesh(new T.ConeGeometry(0.08, 0.2, 12), M('#8E5BE8', 'plastico'));
      ponta.position.y = -0.5; ponta.rotation.x = Math.PI; g.add(haste); g.add(ponta); sc.add(g); raios.push({ g, x: -1.8 + k * 0.6, z: 0.3 + (k % 2) * 0.4 });
    }
    // agua (efeito hidrata)
    const geoGota = new T.SphereGeometry(0.5, 16, 12);
    const gotas = []; for (let k = 0; k < 40; k++) gotas.push({ x: (rnd() * 2 - 1) * LX * 0.95, y: Y_CORNEA - 0.1 - rnd() * 0.85, z: 0.35 + rnd() * 0.8, s: 0.05 + rnd() * 0.04, d: rnd() });
    const gotaInst = new T.InstancedMesh(geoGota, M('#7FC8F8', 'vidro', 0.75), gotas.length); pele.add(gotaInst);

    // ======================= A MOLECULA DO ATIVO =======================
    function molecula() {
      const g = new T.Group(), atomo = (p, cor, s) => { const m = new T.Mesh(geoCel, M(cor, 'ceramica')); m.position.set(...p); m.scale.setScalar(s); g.add(m); };
      const liga = (a, b) => { const va = new T.Vector3(...a), vb = new T.Vector3(...b), m = new T.Mesh(new T.CylinderGeometry(0.06, 0.06, 1, 10), M('#FFFFFF', 'ceramica'));
        m.position.copy(va).add(vb).multiplyScalar(0.5); m.scale.y = va.distanceTo(vb); m.quaternion.setFromUnitVectors(new T.Vector3(0, 1, 0), vb.clone().sub(va).normalize()); g.add(m); };
      const cor = ativo.cor, cor2 = '#FFFFFF', cor3 = '#F26B6B';
      const forma = String(ativo.forma || 'cadeia');
      let pts = [];
      if (forma === 'anel') { for (let i = 0; i < 6; i++) pts.push([Math.cos((i / 6) * U.TAU) * 0.6, Math.sin((i / 6) * U.TAU) * 0.6, 0]); pts.forEach((p, i) => liga(p, pts[(i + 1) % 6])); pts.push([1.15, 0, 0]); liga(pts[0], pts[6]); }
      else if (forma === 'esfera') { pts = [[0, 0, 0], [0.55, 0.3, 0], [-0.5, 0.35, 0.2], [0.05, -0.6, -0.2]]; pts.slice(1).forEach((p) => liga(pts[0], p)); }
      else if (forma === 'cristal') { [-0.4, 0.4].forEach((x) => [-0.4, 0.4].forEach((y) => [-0.4, 0.4].forEach((z) => pts.push([x, y, z])))); pts.forEach((p, i) => pts.forEach((q, j) => { if (j > i && Math.abs(p[0] - q[0]) + Math.abs(p[1] - q[1]) + Math.abs(p[2] - q[2]) < 0.9) liga(p, q); })); }
      else if (forma === 'gota') { pts = [[0, 0, 0], [0.55, -0.4, 0], [-0.55, -0.4, 0]]; liga(pts[0], pts[1]); liga(pts[0], pts[2]); }
      else { const n = ativo.grande ? 9 : 5; for (let i = 0; i < n; i++) pts.push([-((n - 1) * 0.28) + i * 0.56, (i % 2 ? 0.28 : -0.28), 0]); pts.forEach((p, i) => { if (i) liga(pts[i - 1], p); }); }
      pts.forEach((p, i) => atomo(p, i % 3 === 2 ? cor3 : i % 3 === 1 ? cor2 : cor, i === 0 ? 0.42 : 0.34));
      g.traverse((o) => { if (o.isMesh) o.castShadow = false; });
      return g;
    }
    const grande = molecula(); sc.add(grande);
    // as pequenas que entram na pele: copias da mesma (a geometria e' compartilhada)
    const NM = 16, mols = [];
    for (let k = 0; k < NM; k++) { const g = grande.clone(); g.scale.setScalar(0.17); sc.add(g); mols.push({ g, x: (rnd() * 2 - 1) * LX * 0.8, z: 0.45 + rnd() * 0.65, atraso: rnd() * 0.35, fase: rnd() * 6, ondula: 0.08 + rnd() * 0.12 }); }
    // a gota do produto (acao aplica)
    const pingo = new T.Mesh(new T.SphereGeometry(0.5, 32, 20), M(ativo.cor, 'vidro', 0.8)); sc.add(pingo);

    // ======================= ESTADO DE CADA CENA (sem guardar nada) =======================
    const cenas = spec.cenas || [];
    // onde as moleculas estao no comeco da cena i: na ultima profundidade a que chegaram antes
    function profAntes(i) {
      let p = null; for (let j = 0; j < i; j++) { const a = cenas[j].acao; if (a === 'aplica') p = p == null ? 0.12 : p; if (a === 'entra') p = alvoDe(cenas[j]); }
      return p;
    }
    const alvoDe = (cn) => (ativo.grande ? PROF.superficie : PROF[cn.alvo] != null ? PROF[cn.alvo] : PROF.epiderme);
    // o efeito vale dali para frente (a pele hidratada continua hidratada)
    function efeitoEm(i, k) {
      const out = {}; for (let j = 0; j <= i; j++) { const cn = cenas[j]; if (cn.acao === 'efeito' && EFEITOS.indexOf(cn.efeito) >= 0) out[cn.efeito] = j < i ? 1 : U.suave(U.clamp((k - 0.12) / 0.6, 0, 1)); }
      return out;
    }

    const m4 = new T.Matrix4(), q0 = new T.Quaternion(), v1 = new T.Vector3(), cor = new T.Color();
    const corCel0 = new T.Color('#F0B3A0'), corCelH = new T.Color('#F6C6B4'), corCelR = new T.Color('#F08C86');
    function desenharPele(t, ef) {
      const hid = ef.hidrata || 0, bar = ef.barreira || 0, man = ef.manchas || 0, col = ef.colageno || 0, ole = ef.oleo || 0, aca = ef.acalma || 0, esf = ef.esfolia || 0;
      celulas.forEach((q, n) => {
        const s = q.s * (1 + 0.13 * hid) * (1 + 0.012 * Math.sin(t * 2 + n));
        m4.compose(v1.set(q.x, q.y, q.z), q0, new T.Vector3(s, s * 0.92, s)); celInst.setMatrixAt(n, m4);
        cor.copy(corCel0).lerp(corCelR, (1 - aca) * (ef.acalma != null ? 0.55 : 0)).lerp(corCelH, hid * 0.8); celInst.setColorAt(n, cor);
      });
      celInst.instanceMatrix.needsUpdate = true; if (celInst.instanceColor) celInst.instanceColor.needsUpdate = true;
      melanina.forEach((q, n) => { const s = q.s * (1 - 0.75 * man); m4.compose(v1.set(q.x, q.y, q.z), q0, new T.Vector3(s, s, s)); melInst.setMatrixAt(n, m4); });
      melInst.instanceMatrix.needsUpdate = true;
      // barreira: antes ha' frestas (tijolos tortos e a argamassa rala); depois tudo alinha
      const fresta = ef.barreira != null ? 1 - bar : 0;
      tijolos.forEach((b) => {
        const solta = ef.esfolia != null && b.fila === 0 && b.r < 0.55 ? U.suave(U.clamp(esf * 1.3 - b.r * 0.6, 0, 1)) : 0;
        b.m.position.set(b.x + (b.r - 0.5) * 0.06 * fresta, b.y + solta * (0.9 + b.r * 1.4), b.z);
        b.m.rotation.set((b.r - 0.5) * 0.25 * fresta + solta * b.r * 2, 0, (b.r - 0.5) * 0.3 * fresta + solta * (b.r - 0.5) * 3);
        if (soltaTijolo) { b.m.material.opacity = 1 - solta; b.m.material.transparent = solta > 0; } b.m.visible = solta < 0.99;
      });
      argamassa.material.opacity = ef.barreira != null ? 0.25 + 0.7 * bar : 0.55;
      argamassa.material.emissive = argamassa.material.emissive || new T.Color(); argamassa.material.emissive.set('#FFC93C').multiplyScalar(0.45 * bar * (0.6 + 0.4 * Math.sin(t * 5)));
      gotas.forEach((g, n) => { const s = g.s * U.clamp(hid * 1.4 - g.d * 0.4, 0, 1); m4.compose(v1.set(g.x, g.y + Math.sin(t * 1.5 + n) * 0.015, g.z), q0, new T.Vector3(s, s, s)); gotaInst.setMatrixAt(n, m4); });
      gotaInst.instanceMatrix.needsUpdate = true;
      fibras.forEach((f, n) => { const s = 1 + col * (0.55 + 0.1 * Math.sin(n)); f.scale.set(1, s, s); f.position.y = (1 - s) * (Y_DERME - 0.3 - n * 0.17); });
      dermeSolida.material.color.set(ef.colageno != null ? '#F1BDB1' : '#F1BDB1').convertSRGBToLinear();
      const gs = 0.46 * (1.25 - 0.45 * ole); glandula.scale.set(gs, gs * 0.75, gs);
      sebo.scale.setScalar(0.24 * (1 - 0.85 * ole)); sebo.visible = sebo.scale.x > 0.02;
      vaso.material.color.set('#D2414B').convertSRGBToLinear(); vaso.material.emissive = vaso.material.emissive || new T.Color();
      vaso.material.emissive.set('#FF3B3B').multiplyScalar(ef.acalma != null ? 0.5 * (1 - aca) * (0.6 + 0.4 * Math.sin(t * 6)) : 0);
    }

    // ======================= 2D por cima =======================
    let topoLivre = 0;
    const proj = (x, y, z) => { const p = new T.Vector3(x, y, z).project(cam); return { x: (p.x * 0.5 + 0.5) * W, y: (-p.y * 0.5 + 0.5) * H, atras: p.z > 1 }; };
    function etiqueta(txt, x, y, destaque, ent, ladoX) {
      if (ent <= 0.01) return;
      const yy = Math.max(y, topoLivre);
      c.save(); c.font = (destaque ? '54px' : '40px') + ' "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
      const w = c.measureText(txt).width + 44, h = destaque ? 78 : 60, bx = U.clamp(ladoX != null ? ladoX : x, w / 2 + 24, W - w / 2 - 24);
      // a linha liga a etiqueta ao ponto da pele
      c.globalAlpha = U.clamp(ent, 0, 1); c.strokeStyle = 'rgba(40,30,60,0.75)'; c.lineWidth = 4; c.beginPath(); c.moveTo(bx, yy); c.lineTo(x, y); c.stroke();
      c.fillStyle = '#2A1E3C'; c.beginPath(); c.arc(x, y, 8, 0, U.TAU); c.fill();
      c.translate(bx, yy); c.scale(ent, ent); U.rr(c, -w / 2, -h / 2, w, h, 20); c.fillStyle = destaque ? '#FFD23F' : 'rgba(255,255,255,0.92)'; c.fill();
      c.fillStyle = '#2A1E3C'; c.fillText(txt, 0, 2); c.restore();
    }
    const CAMADAS = [['TOP LAYER', -0.12], ['EPIDERMIS', -0.72], ['DERMIS', -2.0]];
    function cartao(rotulo, valor, local) {
      const ent = U.mola(local - 0.25, 10); if (ent <= 0) return;
      c.save(); c.translate(W / 2, H * 0.55); c.scale(ent, ent); c.textAlign = 'center'; c.textBaseline = 'middle';
      c.font = '120px "Lilita One", sans-serif'; const v = String(valor == null ? '' : valor).toUpperCase().slice(0, 18);
      c.font = '44px "Lilita One", sans-serif'; const r = String(rotulo || '').toUpperCase().slice(0, 30);
      c.font = '120px "Lilita One", sans-serif'; const w = Math.min(W - 80, Math.max(c.measureText(v).width, 520) + 120);
      U.rr(c, -w / 2, -150, w, 300, 40); c.fillStyle = 'rgba(42,30,60,0.92)'; c.fill();
      c.fillStyle = '#FFD23F'; c.font = '44px "Lilita One", sans-serif'; c.fillText(r, 0, -78);
      c.fillStyle = '#FFFFFF'; c.font = '120px "Lilita One", sans-serif'; c.fillText(U.hud(c, v, w - 80, 18), 0, 40);
      c.restore();
    }

    // ======================= O QUADRO =======================
    function quadro(t) {
      const { c: cn, i, k, local } = U.cenaEm(spec, t), acao = cn.acao || 'corte', ef = efeitoEm(i, k);
      const close = acao === 'molecula';
      pele.visible = !close; desenharPele(t, ef);
      // camera: o bloco visto de frente e um pouco de cima, girando devagar
      const giro = Math.sin(t * 0.22) * 0.32 + (acao === 'corte' ? (k - 0.5) * 0.5 : 0);
      let dist = 13.5, alvoY = -1.2, alt = 2.4;
      if (acao === 'entra' || acao === 'aplica') { const p = acao === 'entra' ? alvoDe(cn) : 0; alvoY = U.lerp(-0.9, Math.max(-1.9, p * 0.8 - 0.5), U.suave(k)); dist = 10.5; }
      if (acao === 'efeito') {
        const e = cn.efeito; dist = 8.5;
        alvoY = e === 'colageno' || e === 'acalma' ? -2.0 : e === 'manchas' ? -1.05 : e === 'oleo' ? -0.9 : e === 'barreira' || e === 'esfolia' || e === 'protege' ? -0.25 : -0.7;
        if (e === 'barreira' || e === 'esfolia') dist = 6.2;
      }
      // GANCHO DO 1o SEGUNDO: a 1a cena nasce colada na pele (as celulas enchem a tela) e recua
      if (i === 0) { const w = 1 - U.suave(U.clamp((local - 0.35) / 1.2, 0, 1)); dist = U.lerp(dist, 3.2, w); alvoY = U.lerp(alvoY, -0.55, w); }
      cam.position.set(Math.sin(giro) * dist, alvoY + alt * (dist / 13.5) + 0.6, Math.cos(giro) * dist);
      cam.lookAt(0, alvoY - 0.35, 0);
      // molecula grande (acao molecula) no centro, girando
      grande.visible = close;
      if (close) { cam.position.set(0, 0.4, 6); cam.lookAt(0, -0.8, 0); grande.position.set(0, 0.2, 0); const s = U.mola(local, 8) * 1.25; grande.scale.setScalar(s); grande.rotation.set(t * 0.5, t * 0.8, 0.2); }
      // as moleculas pequenas
      const p0 = profAntes(i);
      mols.forEach((m, n) => {
        let y = null, vis = true;
        if (close) vis = false;
        else if (acao === 'aplica') { const kk = U.clamp((k - 0.35 - m.atraso * 0.5) / 0.4, 0, 1); y = kk > 0 ? 0.12 : null; m.g.scale.setScalar(0.17 * U.mola(kk, 10)); }
        else if (acao === 'entra') {
          const de = p0 == null ? 0.12 : p0, ate = alvoDe(cn), kk = U.suave(U.clamp((k - m.atraso) / 0.6, 0, 1));
          y = U.lerp(de, ate - (n % 4) * 0.08, kk); m.g.scale.setScalar(0.17);
        } else if (p0 != null) { y = p0 - (n % 4) * 0.08; m.g.scale.setScalar(0.17); }
        if (y == null) vis = false;
        m.g.visible = vis;
        if (vis) { m.g.position.set(m.x + Math.sin(t * 1.3 + m.fase) * m.ondula * 0.3, y, m.z); m.g.rotation.set(t * 0.9 + m.fase, t * 1.2, 0); }
      });
      // a gota do produto
      pingo.visible = acao === 'aplica';
      if (pingo.visible) {
        const cai = U.clamp(k / 0.35, 0, 1), y = U.lerp(2.6, 0.12, cai * cai), esp = U.saida(U.clamp((k - 0.35) / 0.4, 0, 1));
        pingo.position.set(0, y + (cai >= 1 ? 0 : 0.15), 0.5); pingo.scale.set(0.45 + esp * 2.6, 0.55 * (1 - esp * 0.9) + 0.02, 0.45 + esp * 1.4);
        pingo.material.opacity = 0.8 * (1 - esp * 0.6);
      }
      // protetor: a pelicula e os raios que batem e voltam
      const pr = ef.protege || 0;
      filme.material.opacity = ef.protege != null ? 0.45 * pr : 0;
      raios.forEach((r, n) => {
        const vis = acao === 'efeito' && cn.efeito === 'protege'; r.g.visible = vis; if (!vis) return;
        const ciclo = ((local * 0.8 + n * 0.17) % 1), desce = ciclo < 0.5, kk = desce ? ciclo / 0.5 : (ciclo - 0.5) / 0.5;
        const bate = pr > 0.5 ? 0.14 : -0.6, y = desce ? U.lerp(2.6, bate, kk) : U.lerp(bate, 2.6, kk);
        const vol = !desce && pr > 0.5;
        r.g.position.set(r.x + (vol ? kk * 0.8 : 0), vol || desce ? y : -5, r.z); r.g.rotation.set(0, 0, vol ? Math.PI - 0.45 : -0.15);
        if (!desce && pr <= 0.5) r.g.visible = false;
      });
      sol.position.set(cam.position.x * 0.4 + 2.5, 5, 4);
      R.render(sc, cam); c.drawImage(gl, 0, 0, W, H);

      topoLivre = t < 3.4 || (cn.hud && typeof cn.hud !== 'object' && local > 0.3) ? 480 : 0;
      // etiquetas
      if (acao === 'corte') CAMADAS.forEach(([nome, y], j) => { const q = proj(-LX * 0.55, y, LZ); if (!q.atras) etiqueta(nome, q.x, q.y, j === CAMADAS.length - 1 || k > 0.8, U.mola(local - 0.4 - j * 0.55, 10), W * 0.73); });
      else if (acao === 'entra') { const nome = ({ superficie: 'TOP LAYER', epiderme: 'EPIDERMIS', derme: 'DERMIS' })[ativo.grande ? 'superficie' : cn.alvo] || 'EPIDERMIS';
        const q = proj(-LX * 0.55, alvoDe(cn), LZ); if (!q.atras) etiqueta(nome, q.x, q.y, true, U.mola(local - 0.6, 10), W * 0.72); }
      else if (acao === 'aplica' || close) { const q = close ? { x: W / 2, y: H * 0.36 } : proj(0, 0.5, 0.5); etiqueta(ativo.nome.toUpperCase(), q.x, q.y + (close ? 0 : -60), true, U.mola(local - (close ? 0.3 : 0.8), 10)); }
      else if (acao === 'efeito') {
        const ponto = { hidrata: [0.4, -0.6], barreira: [-0.6, -0.12], manchas: [0.2, -1.1], colageno: [-0.4, -2.0], oleo: [XF - 0.3, -1.45], protege: [-0.8, 0.08], esfolia: [0.6, -0.04], acalma: [-0.5, Y_FUNDO + 0.45] }[cn.efeito];
        const nome = { hidrata: 'WATER HELD IN', barreira: 'BARRIER SEALED', manchas: 'LESS PIGMENT', colageno: 'COLLAGEN', oleo: 'LESS OIL', protege: 'UV BLOCKED', esfolia: 'OLD CELLS OFF', acalma: 'LESS REDNESS' }[cn.efeito];
        if (ponto) { const q = proj(ponto[0], ponto[1], LZ * 0.9); if (!q.atras) etiqueta(nome, q.x, q.y, true, U.mola(local - 0.9, 10), W * 0.5); }
      } else if (acao === 'dado' && cn.dado && typeof cn.dado === 'object') cartao(cn.dado.rotulo, cn.dado.valor, local);
      if (i > 0 && local < 0.12) { c.fillStyle = 'rgba(255,255,255,' + (0.3 * (1 - local / 0.12)).toFixed(2) + ')'; c.fillRect(0, 0, W, H); }
      if (cn.hud && typeof cn.hud !== 'object' && local > 0.3) { const s = U.mola(local - 0.3, 10); c.save(); c.translate(W / 2, 330); c.scale(s, s); c.font = '104px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        const txt = U.hud(c, cn.hud, W * 0.84 - 70, 22), w = c.measureText(txt).width + 70; U.rr(c, -w / 2, -72, w, 144, 34); c.fillStyle = '#2A1E3C'; c.fill(); c.fillStyle = '#FFD23F'; c.fillText(txt, 0, 6); c.restore(); }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 150, fundo: '#FFD23F', borda: '#2A1E3C', cor: '#2A1E3C', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '96px "Lilita One", sans-serif', y: H * 0.76, cor: '#FFFFFF', cor_ativa: '#FFD23F', contorno: 18, cor_contorno: '#2A1E3C', caixa: true, por_vez: 3 });
    }
    return { quadro };
  }
  MOTORES.micro = { criar };
})();
