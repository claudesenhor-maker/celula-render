// MANGUEIRA -- desenho animado dos anos 30, sem fala (13/10, HISTORICO §109).
//
// O canal e' de comedia fisica MUDA: a piada e' o corpo (escorregar, levar a
// bigorna na cabeca, fugir com as pernas em roda). Sem voz nao ha lingua, e o
// video serve ao mundo inteiro; o texto que existe e' a CARTELA de cinema mudo
// (`acao: "cartela"`), curta, e o cartaz do 1o segundo.
//
// O QUE FAZ PARECER 1930: preto e branco sobre papel, grao de filme que muda a
// cada quadro, vinheta, cintilacao de projetor, risco de pelicula, a tremida do
// quadro na janela do projetor, ABERTURA E FECHAMENTO EM IRIS, e todo mundo
// quicando no compasso da trilha (`spec.bpm`) -- inclusive parado.
//
// PERSONAGEM: braco e perna sao CURVAS sem cotovelo (a "mangueira"), luva
// branca, sapato grande, olho de torta. Toda pose sai de `pose()`, um objeto
// plano; as acoes so' escrevem nele. Desenho em `desenharAtor`.
(function () {
  'use strict';
  const PAPEL = '#ECE5D3', TINTA = '#141210', CINZA = '#8E877A', CINZA2 = '#C9C1AE', BRANCO = '#FBF8EF';

  const ELENCO = {
    hank: { chapeu: 'coco', corpo: 1.0, cara: BRANCO },
    dottie: { chapeu: 'laco', corpo: 0.92, cara: BRANCO, saia: true, cilios: true },
    bruto: { chapeu: 'bone', corpo: 1.22, cara: BRANCO, bigode: true },
    pip: { chapeu: 'helice', corpo: 0.78, cara: BRANCO }
  };

  function pose(x, k) {
    return { x, y: 0, rot: 0, sq: 1, esc: k || 1, dir: 1,
      bE: { x: -150, y: 260 }, bD: { x: 150, y: 260 }, pE: { x: -70, y: 300 }, pD: { x: 70, y: 300 },
      olhos: 'normal', boca: 'sorriso', olhar: 0, chapeu: { dy: 0, rot: 0 }, extras: [] };
  }

  function criar(tela, spec, U) {
    const c = tela.getContext('2d'), W = spec.w, H = spec.h, CHAO = H * 0.80;
    const bpm = spec.bpm || 150, batida = (t) => (t * bpm) / 60;
    const rnd = U.rng(spec.semente || spec.fila_id || 'mangueira');
    // grao: 6 texturas sorteadas uma vez; o quadro escolhe uma por indice
    const graos = [];
    for (let g = 0; g < 6; g++) {
      const cv = document.createElement('canvas'); cv.width = 270; cv.height = 480;
      const gx = cv.getContext('2d'), im = gx.createImageData(270, 480);
      for (let i = 0; i < im.data.length; i += 4) { const v = rnd() * 255; im.data[i] = im.data[i + 1] = im.data[i + 2] = v; im.data[i + 3] = 22; }
      gx.putImageData(im, 0, 0); graos.push(cv);
    }

    // ---------- desenho do ator ----------
    function mangueira(x0, y0, x1, y1, curva, larg) {
      const mx = (x0 + x1) / 2, my = (y0 + y1) / 2, dx = x1 - x0, dy = y1 - y0, L = Math.hypot(dx, dy) || 1;
      c.beginPath(); c.moveTo(x0, y0); c.quadraticCurveTo(mx - (dy / L) * curva, my + (dx / L) * curva, x1, y1);
      c.lineWidth = larg; c.strokeStyle = TINTA; c.lineCap = 'round'; c.stroke();
    }
    function luva(x, y, r, ang) {
      c.save(); c.translate(x, y); c.rotate(ang || 0);
      c.beginPath(); c.arc(0, 0, r, 0, U.TAU); c.fillStyle = BRANCO; c.fill(); c.lineWidth = 7; c.strokeStyle = TINTA; c.stroke();
      c.lineWidth = 5; [-0.35, 0, 0.35].forEach((a) => { c.beginPath(); c.moveTo(Math.cos(a) * r * 0.2, Math.sin(a) * r * 0.2); c.lineTo(Math.cos(a) * r * 0.75, Math.sin(a) * r * 0.75); c.stroke(); });
      c.beginPath(); c.ellipse(-r * 0.95, 0, r * 0.32, r * 0.5, 0, 0, U.TAU); c.fillStyle = BRANCO; c.fill(); c.stroke();
      c.restore();
    }
    function sapato(x, y, s) {
      c.beginPath(); c.ellipse(x + 26 * s, y - 20, 74, 40, 0, 0, U.TAU); c.fillStyle = TINTA; c.fill();
      c.beginPath(); c.ellipse(x + 46 * s, y - 34, 22, 10, -0.3 * s, 0, U.TAU); c.fillStyle = CINZA; c.fill();
    }
    function olho(x, y, tipo, olhar, t) {
      c.save(); c.translate(x, y);
      if (tipo === 'fechado') { c.beginPath(); c.arc(0, 8, 26, Math.PI * 1.1, Math.PI * 1.9); c.lineWidth = 9; c.strokeStyle = TINTA; c.stroke(); c.restore(); return; }
      if (tipo === 'feliz') { c.beginPath(); c.arc(0, 14, 26, Math.PI * 1.15, Math.PI * 1.85); c.lineWidth = 10; c.strokeStyle = TINTA; c.stroke(); c.restore(); return; }
      if (tipo === 'xis') { c.lineWidth = 10; c.strokeStyle = TINTA; c.beginPath(); c.moveTo(-20, -20); c.lineTo(20, 20); c.moveTo(20, -20); c.lineTo(-20, 20); c.stroke(); c.restore(); return; }
      const big = tipo === 'arregalado' ? 1.45 : 1;
      c.beginPath(); c.ellipse(0, 0, 30 * big, 46 * big, 0, 0, U.TAU); c.fillStyle = BRANCO; c.fill(); c.lineWidth = 7; c.strokeStyle = TINTA; c.stroke();
      // o olho de TORTA: pupila preta com a fatia cortada
      const px = olhar * 10, py = 8;
      c.beginPath(); c.moveTo(px, py); c.ellipse(px, py, 18 * big, 30 * big, 0, -0.35 * Math.PI, 1.45 * Math.PI); c.closePath(); c.fillStyle = TINTA; c.fill();
      if (tipo === 'chorando') { c.beginPath(); c.ellipse(0, 52, 30, 10, 0, 0, U.TAU); c.fillStyle = '#9DB7C9'; c.fill(); }
      c.restore();
    }
    function desenharAtor(nome, P, t) {
      const E = ELENCO[nome] || ELENCO.hank;
      const s = P.esc * E.corpo * 1.05;
      const sy = P.sq, sx = 1 / Math.sqrt(Math.max(0.2, P.sq));
      c.save();
      c.translate(P.x, CHAO - P.y);
      c.scale(s * P.dir, s);
      // sombra no chao (fica no chao quando ele pula)
      c.save(); c.scale(1 / P.dir, 1); c.beginPath(); c.ellipse(0, 6 + P.y / s, 150 * Math.max(0.4, 1 - P.y / 900), 22, 0, 0, U.TAU); c.fillStyle = 'rgba(20,18,16,.18)'; c.fill(); c.restore();
      c.rotate(P.rot);
      const HIP = -300, OMB = -540;
      // pernas
      mangueira(-36, HIP, P.pE.x, HIP + P.pE.y, -40, 34); mangueira(36, HIP, P.pD.x, HIP + P.pD.y, 40, 34);
      sapato(P.pE.x, HIP + P.pE.y + 10, -1); sapato(P.pD.x, HIP + P.pD.y + 10, 1);
      // corpo (feijao) com o achatar/esticar no quadril
      c.save(); c.translate(0, HIP); c.scale(sx, sy);
      c.beginPath(); c.ellipse(0, -130, 118, 175, 0, 0, U.TAU); c.fillStyle = TINTA; c.fill();
      if (E.saia) { c.beginPath(); c.moveTo(-130, -40); c.lineTo(130, -40); c.lineTo(175, 70); c.lineTo(-175, 70); c.closePath(); c.fillStyle = TINTA; c.fill();
        c.fillStyle = BRANCO; for (let i = -3; i <= 3; i++) { c.beginPath(); c.arc(i * 46, 30, 11, 0, U.TAU); c.fill(); } }
      c.beginPath(); c.ellipse(0, -70, 68, 92, 0, 0, U.TAU); c.fillStyle = CINZA2; c.fill();
      [-18, 18].forEach((bx) => { c.beginPath(); c.arc(bx, -130, 10, 0, U.TAU); c.fillStyle = BRANCO; c.fill(); });
      c.restore();
      // bracos
      const oy = HIP + (OMB - HIP) * sy;
      mangueira(-92 * sx, oy, P.bE.x * 0.9, oy + P.bE.y * 0.9, -55, 30); mangueira(92 * sx, oy, P.bD.x * 0.9, oy + P.bD.y * 0.9, 55, 30);
      luva(P.bE.x * 0.9, oy + P.bE.y * 0.9, 46, -0.4); luva(P.bD.x * 0.9, oy + P.bD.y * 0.9, 46, Math.PI + 0.4);
      // cabeca
      const hy = oy - 150;
      c.save(); c.translate(0, hy); c.rotate(-P.rot * 0.4 + 0.06 * Math.sin(U.TAU * batida(t) * 0.5));
      if (nome !== 'dottie') { [-1, 1].forEach((k) => { c.beginPath(); c.ellipse(k * 128, -60, 46, 58, k * 0.3, 0, U.TAU); c.fillStyle = TINTA; c.fill(); }); }
      c.beginPath(); c.arc(0, 0, 165, 0, U.TAU); c.fillStyle = TINTA; c.fill();
      // mascara clara do rosto (o recorte classico em "pera")
      c.beginPath(); c.moveTo(-130, 40); c.bezierCurveTo(-150, -70, -40, -60, 0, -20); c.bezierCurveTo(40, -60, 150, -70, 130, 40);
      c.bezierCurveTo(110, 150, -110, 150, -130, 40); c.fillStyle = E.cara; c.fill();
      olho(-48, -10, P.olhos, P.olhar, t); olho(48, -10, P.olhos, P.olhar, t);
      if (E.cilios && P.olhos !== 'fechado') { c.lineWidth = 7; c.strokeStyle = TINTA; [-48, 48].forEach((ex) => { for (let k = -1; k <= 1; k++) { c.beginPath(); c.moveTo(ex + k * 14, -58); c.lineTo(ex + k * 22, -80); c.stroke(); } }); }
      // nariz e boca
      c.beginPath(); c.ellipse(0, 42, 26, 18, 0, 0, U.TAU); c.fillStyle = TINTA; c.fill();
      if (E.bigode) { c.beginPath(); c.ellipse(-34, 66, 40, 14, 0.25, 0, U.TAU); c.ellipse(34, 66, 40, 14, -0.25, 0, U.TAU); c.fill(); }
      c.lineWidth = 9; c.strokeStyle = TINTA; c.fillStyle = TINTA;
      const b = P.boca;
      if (b === 'sorriso') { c.beginPath(); c.arc(0, 60, 58, 0.15 * Math.PI, 0.85 * Math.PI); c.stroke(); }
      else if (b === 'risada') { c.beginPath(); c.moveTo(-62, 70); c.quadraticCurveTo(0, 170 + 20 * Math.sin(t * 30), 62, 70); c.closePath(); c.fill(); c.beginPath(); c.ellipse(0, 112, 28, 16, 0, 0, U.TAU); c.fillStyle = '#B85C5C'; c.fill(); }
      else if (b === 'o') { c.beginPath(); c.ellipse(0, 96, 26, 36, 0, 0, U.TAU); c.fill(); }
      else if (b === 'triste') { c.beginPath(); c.arc(0, 128, 52, 1.2 * Math.PI, 1.8 * Math.PI); c.stroke(); }
      else if (b === 'dentes') { c.beginPath(); U.rr(c, -66, 72, 132, 46, 18); c.fillStyle = BRANCO; c.fill(); c.stroke(); c.beginPath(); c.moveTo(-66, 95); c.lineTo(66, 95); c.stroke(); }
      else if (b === 'mastiga') { const a = Math.abs(Math.sin(t * 22)); c.beginPath(); c.ellipse(0, 92, 40, 8 + 22 * a, 0, 0, U.TAU); c.fill(); }
      else { c.beginPath(); c.moveTo(-40, 92); c.lineTo(40, 92); c.stroke(); }
      // chapeu
      c.save(); c.translate(0, -150 - P.chapeu.dy); c.rotate(P.chapeu.rot);
      if (E.chapeu === 'coco') { c.beginPath(); c.ellipse(0, 0, 150, 26, 0, 0, U.TAU); c.fillStyle = TINTA; c.fill(); c.beginPath(); c.arc(0, -10, 98, Math.PI, U.TAU); c.fill(); c.fillStyle = CINZA; c.fillRect(-98, -22, 196, 14); }
      else if (E.chapeu === 'laco') { c.fillStyle = TINTA; c.beginPath(); c.moveTo(0, 0); c.lineTo(-110, -70); c.lineTo(-110, 60); c.closePath(); c.moveTo(0, 0); c.lineTo(110, -70); c.lineTo(110, 60); c.closePath(); c.fill(); c.beginPath(); c.arc(0, 0, 30, 0, U.TAU); c.fillStyle = CINZA; c.fill(); }
      else if (E.chapeu === 'bone') { c.beginPath(); c.ellipse(-10, 0, 150, 60, -0.1, Math.PI, U.TAU); c.fillStyle = TINTA; c.fill(); c.beginPath(); c.ellipse(120, 4, 90, 18, 0.1, 0, U.TAU); c.fill(); }
      else if (E.chapeu === 'helice') { c.beginPath(); c.arc(0, 0, 90, Math.PI, U.TAU); c.fillStyle = TINTA; c.fill(); c.fillRect(-6, -150, 12, 60); const a = t * 18; c.fillStyle = CINZA; c.beginPath(); c.ellipse(0, -150, 110 * Math.abs(Math.cos(a)), 16, 0, 0, U.TAU); c.fill(); }
      c.restore();
      c.restore();
      // extras (no espaco do ator)
      P.extras.forEach((e) => extra(e, hy, t));
      c.restore();
    }
    function extra(e, hy, t) {
      c.save(); c.lineWidth = 9; c.strokeStyle = TINTA; c.fillStyle = TINTA;
      if (e === 'estrelas') { for (let i = 0; i < 5; i++) { const a = t * 5 + (i * U.TAU) / 5; estrela(Math.cos(a) * 210, hy - 190 + Math.sin(a) * 50, 30); } }
      else if (e === 'suor') { for (let i = 0; i < 3; i++) { const k = ((t * 1.6 + i / 3) % 1); c.globalAlpha = 1 - k; gota(170 + i * 30, hy - 120 + k * 160, 22); } }
      else if (e === 'lagrimas') { c.strokeStyle = '#7E9DB3'; c.lineWidth = 16; [-1, 1].forEach((s) => { for (let i = 0; i < 6; i++) { const k = ((t * 2.2 + i / 6) % 1); c.beginPath(); c.arc(s * (70 + k * 330), hy + 20 - 260 * k + 520 * k * k, 10, 0, U.TAU); c.fillStyle = '#9DB7C9'; c.fill(); } }); }
      else if (e === 'lampada') { const p = U.mola(t % 100, 10); c.save(); c.translate(0, hy - 380); c.scale(p, p);
        c.beginPath(); c.arc(0, 0, 70, 0, U.TAU); c.fillStyle = BRANCO; c.fill(); c.stroke(); c.fillStyle = TINTA; c.fillRect(-34, 62, 68, 40);
        for (let i = 0; i < 8; i++) { const a = (i * U.TAU) / 8; c.beginPath(); c.moveTo(Math.cos(a) * 95, Math.sin(a) * 95); c.lineTo(Math.cos(a) * 140, Math.sin(a) * 140); c.stroke(); } c.restore(); }
      else if (e === 'zzz') { c.font = '90px Rye, serif'; for (let i = 0; i < 3; i++) { const k = ((t * 0.6 + i / 3) % 1); c.globalAlpha = 1 - k; c.fillText('Z', 150 + k * 140, hy - 200 - k * 300); } }
      else if (e === 'notas') { c.font = '110px serif'; for (let i = 0; i < 3; i++) { const k = ((t * 0.8 + i / 3) % 1); c.globalAlpha = 1 - k; c.fillText(i % 2 ? '♪' : '♫', 120 + Math.sin(k * 9) * 40, hy - 100 - k * 360); } }
      else if (e === 'velocidade') { c.lineWidth = 12; for (let i = 0; i < 5; i++) { c.beginPath(); c.moveTo(-260 - i * 30, -600 + i * 120); c.lineTo(-520 - i * 50, -600 + i * 120); c.stroke(); } }
      else if (e === 'poeira') { for (let i = 0; i < 6; i++) { const k = ((t * 3 + i / 6) % 1); c.globalAlpha = 1 - k; c.beginPath(); c.arc(-160 - k * 300, -40 - k * 80, 40 + k * 60, 0, U.TAU); c.fillStyle = CINZA2; c.fill(); c.stroke(); } }
      else if (e === 'confete') { const r = U.rng(9); for (let i = 0; i < 26; i++) { const x = (r() - 0.5) * 900, v = 0.4 + r(), y = -1300 + ((t * 420 * v + r() * 1400) % 1500); c.save(); c.translate(x, y); c.rotate(t * 6 * v + i); c.fillStyle = i % 2 ? TINTA : CINZA; c.fillRect(-14, -8, 28, 16); c.restore(); } }
      c.restore();
    }
    function estrela(x, y, r) { c.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, rr = i % 2 ? r * 0.45 : r; c.lineTo(x + Math.cos(a) * rr, y + Math.sin(a) * rr); } c.closePath(); c.fillStyle = BRANCO; c.fill(); c.lineWidth = 6; c.strokeStyle = TINTA; c.stroke(); }
    function gota(x, y, r) { c.beginPath(); c.moveTo(x, y - r * 1.6); c.quadraticCurveTo(x + r, y, x, y + r); c.quadraticCurveTo(x - r, y, x, y - r * 1.6); c.fillStyle = BRANCO; c.fill(); c.lineWidth = 6; c.stroke(); }

    // ---------- objetos ----------
    function objeto(nome, x, y, rot, esc) {
      c.save(); c.translate(x, y); c.rotate(rot || 0); c.scale(esc || 1, esc || 1); c.lineWidth = 8; c.strokeStyle = TINTA; c.fillStyle = TINTA;
      if (nome === 'banana') { c.beginPath(); c.moveTo(-90, 0); c.quadraticCurveTo(0, 60, 90, 0); c.quadraticCurveTo(0, 25, -90, 0); c.fillStyle = CINZA2; c.fill(); c.stroke(); }
      else if (nome === 'bigorna') { c.beginPath(); c.moveTo(-130, -60); c.lineTo(150, -60); c.lineTo(90, 0); c.lineTo(60, 0); c.lineTo(80, 70); c.lineTo(-80, 70); c.lineTo(-60, 0); c.lineTo(-90, -10); c.closePath(); c.fill(); c.fillStyle = CINZA; c.fillRect(-120, -56, 220, 12); }
      else if (nome === 'balde') { c.beginPath(); c.moveTo(-80, -70); c.lineTo(80, -70); c.lineTo(60, 70); c.lineTo(-60, 70); c.closePath(); c.fillStyle = CINZA; c.fill(); c.stroke(); c.beginPath(); c.arc(0, -70, 80, Math.PI, U.TAU); c.stroke(); }
      else if (nome === 'bolo') { c.fillStyle = BRANCO; c.beginPath(); U.rr(c, -110, -60, 220, 110, 16); c.fill(); c.stroke(); c.fillStyle = CINZA2; c.fillRect(-110, -10, 220, 18); c.fillStyle = TINTA; c.fillRect(-6, -110, 12, 50); c.beginPath(); c.ellipse(0, -120, 10, 18, 0, 0, U.TAU); c.fillStyle = BRANCO; c.fill(); c.stroke(); }
      else if (nome === 'telefone') { c.beginPath(); U.rr(c, -90, -40, 180, 90, 20); c.fill(); c.fillStyle = BRANCO; c.beginPath(); c.arc(0, 4, 30, 0, U.TAU); c.fill(); c.lineWidth = 14; c.beginPath(); c.arc(0, -40, 90, Math.PI * 1.1, Math.PI * 1.9); c.stroke(); }
      else if (nome === 'guarda_chuva') { c.beginPath(); c.arc(0, 0, 150, Math.PI, U.TAU); c.closePath(); c.fill(); c.lineWidth = 12; c.beginPath(); c.moveTo(0, 0); c.lineTo(0, 200); c.arc(-25, 200, 25, 0, Math.PI); c.stroke(); }
      else if (nome === 'sanduiche') { c.fillStyle = CINZA2; c.beginPath(); U.rr(c, -120, -50, 240, 40, 18); c.fill(); c.stroke(); c.fillStyle = TINTA; c.fillRect(-125, -10, 250, 16); c.fillStyle = CINZA2; c.beginPath(); U.rr(c, -120, 6, 240, 40, 18); c.fill(); c.stroke(); }
      else if (nome === 'presente') { c.fillStyle = BRANCO; c.fillRect(-90, -80, 180, 160); c.strokeRect(-90, -80, 180, 160); c.fillStyle = TINTA; c.fillRect(-14, -80, 28, 160); c.fillRect(-90, -14, 180, 28); c.beginPath(); c.ellipse(-40, -100, 40, 22, 0.4, 0, U.TAU); c.ellipse(40, -100, 40, 22, -0.4, 0, U.TAU); c.fill(); }
      else if (nome === 'relogio') { c.fillStyle = BRANCO; c.beginPath(); c.arc(0, 0, 90, 0, U.TAU); c.fill(); c.stroke(); c.beginPath(); c.moveTo(0, 0); c.lineTo(0, -60); c.moveTo(0, 0); c.lineTo(45, 10); c.stroke(); }
      else if (nome === 'dinheiro') { c.fillStyle = CINZA2; c.beginPath(); U.rr(c, -110, -55, 220, 110, 10); c.fill(); c.stroke(); c.fillStyle = TINTA; c.font = '90px Rye, serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('$', 0, 6); }
      else if (nome === 'coracao') { c.beginPath(); c.moveTo(0, 60); c.bezierCurveTo(-140, -30, -60, -120, 0, -50); c.bezierCurveTo(60, -120, 140, -30, 0, 60); c.fill(); }
      else if (nome === 'interrogacao' || nome === 'exclamacao') { c.font = '200px Rye, serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(nome === 'interrogacao' ? '?' : '!', 0, 10); }
      c.restore();
    }
    function balao(x, y, icone, k) {
      const p = U.mola(k * 3, 12);
      c.save(); c.translate(x, y); c.scale(p, p);
      c.beginPath(); c.ellipse(0, 0, 170, 130, 0, 0, U.TAU); c.fillStyle = BRANCO; c.fill(); c.lineWidth = 9; c.strokeStyle = TINTA; c.stroke();
      c.beginPath(); c.moveTo(-40, 120); c.lineTo(-100, 220); c.lineTo(10, 126); c.fillStyle = BRANCO; c.fill(); c.stroke();
      objeto(icone || 'interrogacao', 0, 0, 0, 0.75);
      c.restore();
    }

    // ---------- cenarios (traco de tinta sobre papel) ----------
    function cenario(nome, t, cam) {
      c.fillStyle = PAPEL; c.fillRect(0, 0, W, H);
      c.save(); c.lineWidth = 9; c.strokeStyle = TINTA; c.fillStyle = CINZA2;
      const par = (k) => c.translate(-cam.px * k, 0);
      c.save(); par(0.3);
      if (nome === 'rua' || nome === 'parque' || nome === 'praia') {
        // sol com cara, que balanca no compasso -- assinatura da epoca
        c.save(); c.translate(820, 330); c.rotate(0.12 * Math.sin(U.TAU * batida(t) * 0.5));
        c.beginPath(); c.arc(0, 0, 110, 0, U.TAU); c.fillStyle = BRANCO; c.fill(); c.stroke();
        for (let i = 0; i < 12; i++) { const a = (i * U.TAU) / 12; c.beginPath(); c.moveTo(Math.cos(a) * 130, Math.sin(a) * 130); c.lineTo(Math.cos(a) * 175, Math.sin(a) * 175); c.stroke(); }
        c.fillStyle = TINTA; c.beginPath(); c.arc(-36, -10, 12, 0, U.TAU); c.arc(36, -10, 12, 0, U.TAU); c.fill(); c.beginPath(); c.arc(0, 20, 50, 0.2 * Math.PI, 0.8 * Math.PI); c.stroke(); c.restore();
      }
      if (nome === 'rua') { for (let i = 0; i < 4; i++) { const x = i * 300 - 60, h = 520 + (i % 2) * 180; c.fillStyle = i % 2 ? CINZA2 : BRANCO; c.fillRect(x, CHAO - h, 260, h); c.strokeRect(x, CHAO - h, 260, h);
          c.fillStyle = TINTA; for (let r = 0; r < 4; r++) for (let q = 0; q < 2; q++) c.fillRect(x + 50 + q * 110, CHAO - h + 60 + r * 120, 60, 70); } }
      if (nome === 'parque') { [140, 520, 930].forEach((x, i) => { c.fillStyle = TINTA; c.fillRect(x - 18, CHAO - 520, 36, 520); c.beginPath(); c.arc(x, CHAO - 620, 190 - i * 20, 0, U.TAU); c.fillStyle = i % 2 ? CINZA : CINZA2; c.fill(); c.stroke(); }); }
      if (nome === 'praia') { c.fillStyle = CINZA2; c.fillRect(0, CHAO - 260, W, 260); c.lineWidth = 8; for (let r = 0; r < 4; r++) { c.beginPath(); for (let x = -40; x < W + 40; x += 80) c.arc(x + ((t * 60) % 80), CHAO - 230 + r * 60, 40, Math.PI, U.TAU); c.stroke(); } }
      c.restore();
      c.save(); par(0.6);
      if (nome === 'cozinha') { c.fillStyle = BRANCO; c.fillRect(80, CHAO - 900, 360, 300); c.strokeRect(80, CHAO - 900, 360, 300); c.beginPath(); c.moveTo(260, CHAO - 900); c.lineTo(260, CHAO - 600); c.moveTo(80, CHAO - 750); c.lineTo(440, CHAO - 750); c.stroke();
        c.fillStyle = CINZA2; c.fillRect(640, CHAO - 520, 340, 520); c.strokeRect(640, CHAO - 520, 340, 520); c.fillStyle = TINTA; [700, 900].forEach((x) => { c.beginPath(); c.arc(x, CHAO - 470, 40, 0, U.TAU); c.fill(); }); c.strokeRect(680, CHAO - 380, 260, 300); }
      if (nome === 'sala') { c.fillStyle = BRANCO; c.fillRect(380, CHAO - 1050, 320, 240); c.strokeRect(380, CHAO - 1050, 320, 240); c.beginPath(); c.arc(540, CHAO - 930, 60, 0, U.TAU); c.stroke();
        c.fillStyle = CINZA; U.rr(c, 60, CHAO - 380, 520, 260, 60); c.fill(); c.stroke(); c.fillStyle = TINTA; c.fillRect(860, CHAO - 700, 16, 700); c.beginPath(); c.moveTo(780, CHAO - 700); c.lineTo(960, CHAO - 700); c.lineTo(910, CHAO - 860); c.lineTo(830, CHAO - 860); c.closePath(); c.fillStyle = BRANCO; c.fill(); c.stroke(); }
      if (nome === 'escritorio') { c.fillStyle = BRANCO; c.beginPath(); c.arc(820, CHAO - 980, 110, 0, U.TAU); c.fill(); c.stroke(); c.beginPath(); c.moveTo(820, CHAO - 980); c.lineTo(820, CHAO - 1060); c.moveTo(820, CHAO - 980); c.lineTo(820 + 60 * Math.cos(t), CHAO - 980 + 60 * Math.sin(t)); c.stroke();
        c.fillStyle = CINZA2; c.fillRect(60, CHAO - 420, 560, 40); c.strokeRect(60, CHAO - 420, 560, 40); c.fillRect(90, CHAO - 380, 40, 380); c.fillRect(550, CHAO - 380, 40, 380); c.fillStyle = CINZA; c.fillRect(780, CHAO - 640, 220, 640); c.strokeRect(780, CHAO - 640, 220, 640); for (let r = 0; r < 3; r++) c.strokeRect(810, CHAO - 610 + r * 200, 160, 170); }
      c.restore();
      // chao: linhas de tabuas / calcada
      c.fillStyle = CINZA2; c.fillRect(0, CHAO, W, H - CHAO); c.beginPath(); c.moveTo(0, CHAO); c.lineTo(W, CHAO); c.stroke();
      c.lineWidth = 5; for (let i = 0; i < 6; i++) { const y = CHAO + 30 + i * i * 14; c.beginPath(); c.moveTo(0, y); c.lineTo(W, y); c.stroke(); }
      c.restore();
    }

    // ---------- acoes: escrevem nas poses; `k` e' 0..1 da cena, `l` segundos ----------
    const XH = 330, XO = 760;
    function andar(P, p, passo, bob) {
      const a = U.TAU * p;
      P.pE = { x: -40 + passo * Math.sin(a), y: 300 - Math.max(0, Math.cos(a)) * 90 };
      P.pD = { x: 40 - passo * Math.sin(a), y: 300 - Math.max(0, -Math.cos(a)) * 90 };
      P.bE = { x: -170 - 60 * Math.sin(a), y: 250 }; P.bD = { x: 170 + 60 * Math.sin(a), y: 250 };
      P.y = Math.abs(Math.sin(a)) * (bob || 30); P.sq = 1 + 0.06 * Math.cos(2 * a);
    }
    function quicar(P, t, forca) { const b = batida(t); P.sq = 1 + (forca || 0.05) * Math.sin(U.TAU * b); P.y += Math.max(0, Math.sin(U.TAU * b)) * 12; }
    const ACOES = {
      parado(h, o, k, l, t) { quicar(h, t); if (o) quicar(o, t + 0.2); },
      entra_andando(h, o, k, l, t) { h.x = U.lerp(-260, XH, U.saida(Math.min(1, k * 1.25))); if (k < 0.8) andar(h, l * 2.2, 90); else quicar(h, t); h.extras.push('notas'); if (o) quicar(o, t); },
      anda_assobiando(h, o, k, l, t) { andar(h, l * 2.2, 90); h.extras.push('notas'); h.boca = 'o'; if (o) quicar(o, t); },
      escorrega(h, o, k, l, t, cena) {
        const pisa = 0.32, voa = 0.62;
        if (k < pisa) { h.x = U.lerp(140, 520, k / pisa); andar(h, l * 2.4, 90); }
        else if (k < voa) { const q = (k - pisa) / (voa - pisa); h.x = 520 + q * 120; h.y = Math.sin(q * Math.PI) * 420; h.rot = -U.saida(q) * 1.45; h.pE = { x: 160, y: -60 }; h.pD = { x: 220, y: -20 }; h.bE = { x: -260, y: -80 }; h.bD = { x: 240, y: -120 }; h.olhos = 'arregalado'; h.boca = 'o'; h.chapeu = { dy: 260 * q, rot: q * 3 }; }
        else { const q = (k - voa) / (1 - voa); h.x = 640; h.rot = -1.5; h.y = 40; h.sq = 1 - 0.25 * Math.exp(-q * 10); h.pE = { x: 200, y: 120 }; h.pD = { x: 260, y: 160 }; h.olhos = 'xis'; h.boca = 'triste'; h.extras.push('estrelas'); }
        objeto('banana', 600 + (k > pisa ? (k - pisa) * 900 : 0), CHAO - 20 - (k > pisa && k < voa ? Math.sin((k - pisa) / (voa - pisa) * Math.PI) * 300 : 0), k * 9, 1);
        if (o) { o.x = XO + 60; quicar(o, t); if (k > voa) { o.boca = 'risada'; o.olhos = 'feliz'; o.sq = 1 + 0.08 * Math.sin(t * 28); } }
      },
      tropeca(h, o, k, l, t) {
        if (k < 0.35) { h.x = U.lerp(160, 460, k / 0.35); andar(h, l * 2.4, 90); }
        else { const q = U.saida((k - 0.35) / 0.4); h.x = 460 + q * 160; h.rot = q * 1.4; h.y = Math.sin(Math.min(1, q) * Math.PI) * 120; h.bE = { x: -200 + 120 * Math.sin(t * 30), y: -140 }; h.bD = { x: 200 - 120 * Math.sin(t * 30), y: -140 }; h.olhos = 'arregalado'; h.boca = 'o'; if (k > 0.75) { h.olhos = 'xis'; h.extras.push('estrelas'); } }
        if (o) quicar(o, t);
      },
      pula_de_susto(h, o, k, l, t) {
        const q = U.clamp((k - 0.15) / 0.5, 0, 1), ar = Math.sin(q * Math.PI);
        h.x = XH; if (k < 0.15) { h.sq = 1 - 0.25 * (k / 0.15); quicar(h, t, 0.02); } // antecipacao: agacha antes
        else { h.y = ar * 620; h.sq = 1 + 0.45 * ar; h.bE = { x: -230, y: -260 }; h.bD = { x: 230, y: -260 }; h.pE = { x: -40, y: 360 }; h.pD = { x: 40, y: 360 }; h.olhos = 'arregalado'; h.boca = 'o'; h.chapeu = { dy: ar * 420, rot: q * 6 }; }
        h.extras.push('suor');
        if (o) { o.x = XO; o.bD = { x: 260, y: -60 }; o.boca = 'dentes'; quicar(o, t); }
      },
      foge(h, o, k, l, t) {
        h.x = U.lerp(XH, 1500, U.entrada(k)); h.rot = 0.35; h.olhos = 'arregalado'; h.boca = 'o';
        // as pernas viram RODA (o borrão classico)
        const a = t * 40; h.pE = { x: Math.cos(a) * 120, y: 220 + Math.sin(a) * 70 }; h.pD = { x: Math.cos(a + Math.PI) * 120, y: 220 + Math.sin(a + Math.PI) * 70 };
        h.bE = { x: -260, y: 60 }; h.bD = { x: 260, y: -40 }; h.y = 20 + Math.abs(Math.sin(a)) * 30; h.extras.push('poeira', 'velocidade', 'suor');
        if (o) { o.x = XO; o.olhos = 'arregalado'; o.boca = 'o'; quicar(o, t); }
      },
      estica_braco(h, o, k, l, t, cena) {
        const ob = cena.objeto || 'bolo', ida = U.clamp(k / 0.45, 0, 1), volta = U.clamp((k - 0.55) / 0.35, 0, 1);
        const alc = 620 * U.saida(ida) * (1 - U.suave(volta));
        h.x = XH - 80; h.bD = { x: 170 + alc, y: 120 - 40 * ida }; h.olhar = 1; h.boca = ida > 0.9 ? 'dentes' : 'sorriso'; quicar(h, t, 0.03);
        const ox = volta > 0 ? (XH - 80 + (170 + alc) * 1.05) : 900, oy = volta > 0 ? CHAO - 300 - 130 : CHAO - 120;
        objeto(ob, ox, oy, 0, 0.9);
        if (o) { o.x = 980; o.esc = 0.8; o.olhos = volta > 0 ? 'arregalado' : 'normal'; quicar(o, t); }
      },
      objeto_cai_na_cabeca(h, o, k, l, t, cena) {
        const ob = cena.objeto || 'bigorna', bate = 0.45; h.x = XH + 120;
        if (k < bate) { quicar(h, t); h.boca = 'sorriso'; h.extras.push('notas'); objeto(ob, h.x, U.lerp(-200, CHAO - 980, U.entrada(k / bate)), 0, 1.1); }
        else { const q = (k - bate) / (1 - bate); h.sq = 0.45 + 0.55 * (1 - Math.exp(-q * 2.2)) * (q > 0.6 ? 1 : 0.2) + (q < 0.6 ? 0 : 0); h.olhos = 'xis'; h.boca = 'triste'; h.extras.push('estrelas');
          objeto(ob, h.x, CHAO - 980 * (0.45 + (q > 0.6 ? 0.55 : 0.1)) + 60, 0.05 * Math.sin(q * 40) * (1 - q), 1.1); }
        if (o) { o.x = XO + 80; if (k > bate) { o.boca = 'risada'; o.olhos = 'feliz'; o.sq = 1 + 0.08 * Math.sin(t * 28); o.bD = { x: -80, y: 120 }; } else quicar(o, t); }
      },
      ri_apontando(h, o, k, l, t) {
        // O primeiro de atores executa a acao; o segundo recebe a provocacao.
        h.x = XH; h.boca = 'risada'; h.olhos = 'feliz'; h.sq = 1 + 0.1 * Math.sin(t * 26); h.y = Math.abs(Math.sin(t * 13)) * 30; h.bE = { x: -120, y: 160 }; h.bD = { x: 330, y: 30 }; h.extras.push('lagrimas');
        if (o) { o.x = XO; o.boca = 'triste'; o.olhos = 'normal'; o.olhar = 1; o.dir = -1; o.sq = 0.92 + 0.02 * Math.sin(t * 4); }
      },
      chora_cachoeira(h, o, k, l, t) { h.x = 540; h.olhos = 'chorando'; h.boca = 'triste'; h.sq = 1 + 0.05 * Math.sin(t * 18); h.bE = { x: -60, y: -60 }; h.bD = { x: 60, y: -60 }; h.extras.push('lagrimas'); if (o) { o.x = 900; o.esc = 0.85; o.olhos = 'arregalado'; quicar(o, t); } },
      come_rapido(h, o, k, l, t, cena) {
        const ob = cena.objeto || 'bolo', resta = 1 - U.clamp(k / 0.8, 0, 1); h.x = XH + 100; h.boca = resta > 0 ? 'mastiga' : 'sorriso'; h.bE = { x: 120, y: 30 }; h.bD = { x: 240, y: 30 };
        if (resta > 0) objeto(ob, h.x + 230 * h.esc, CHAO - 640, 0, 0.4 + 0.6 * resta); h.sq = 1 + (1 - resta) * 0.25; if (resta === 0) h.extras.push('estrelas'); if (o) { o.x = 920; o.esc = 0.85; o.olhos = 'arregalado'; o.boca = 'o'; quicar(o, t); }
      },
      dorme_ronca(h, o, k, l, t) { h.x = 540; h.olhos = 'fechado'; h.boca = 'o'; h.sq = 1 + 0.08 * Math.sin(t * 2.4); h.rot = 0.08; h.extras.push('zzz'); if (o) quicar(o, t); },
      briga_nuvem(h, o, k, l, t) {
        const r = U.rng(Math.floor(t * 12)); c.save(); c.translate(540 + (r() - 0.5) * 30, CHAO - 520 + (r() - 0.5) * 30);
        for (let i = 0; i < 9; i++) { const a = (i * U.TAU) / 9; c.beginPath(); c.arc(Math.cos(a) * 250, Math.sin(a) * 170, 150, 0, U.TAU); c.fillStyle = CINZA2; c.fill(); c.lineWidth = 9; c.strokeStyle = TINTA; c.stroke(); }
        c.beginPath(); c.ellipse(0, 0, 330, 230, 0, 0, U.TAU); c.fillStyle = CINZA2; c.fill();
        for (let i = 0; i < 4; i++) { const a = r() * U.TAU; luva(Math.cos(a) * 330, Math.sin(a) * 220, 46, a); }
        for (let i = 0; i < 3; i++) estrela((r() - 0.5) * 600, (r() - 0.5) * 400, 34);
        c.restore(); h.oculto = true; if (o) o.oculto = true;
      },
      pensa_ideia(h, o, k, l, t) { h.x = 540; h.bD = { x: 60, y: -170 }; h.olhar = -0.6; h.olhos = k > 0.55 ? 'arregalado' : 'normal'; h.boca = k > 0.55 ? 'dentes' : 'reta'; if (k > 0.55) h.extras.push('lampada'); quicar(h, t, 0.03); if (o) quicar(o, t); },
      comemora(h, o, k, l, t) { const b = batida(t); h.x = XH; h.y = Math.max(0, Math.sin(U.TAU * b)) * 220; h.sq = 1 + 0.2 * Math.sin(U.TAU * b); h.bE = { x: -170, y: -300 }; h.bD = { x: 170, y: -300 }; h.boca = 'risada'; h.olhos = 'feliz'; h.extras.push('confete'); if (o) { o.x = XO; o.y = Math.max(0, Math.sin(U.TAU * b + 1)) * 200; o.bE = { x: -170, y: -300 }; o.bD = { x: 170, y: -300 }; o.boca = 'risada'; o.olhos = 'feliz'; } },
      danca(h, o, k, l, t) { const b = batida(t), s = Math.sin(U.TAU * b * 0.5); h.x = XH + s * 60; h.rot = s * 0.25; h.pE = { x: -110 + s * 60, y: 280 }; h.pD = { x: 110 + s * 60, y: 280 - Math.max(0, s) * 120 }; h.bE = { x: -200, y: -180 * s }; h.bD = { x: 200, y: 180 * s }; h.boca = 'sorriso'; h.extras.push('notas'); if (o) { o.x = XO - s * 60; o.rot = -s * 0.25; o.bE = { x: -200, y: 180 * s }; o.bD = { x: 200, y: -180 * s }; } },
      conversa(h, o, k, l, t, cena) { h.x = XH; quicar(h, t); h.olhar = 1; h.bD = { x: 230, y: 40 + 60 * Math.sin(t * 8) }; balao(XH + 40, CHAO - 1300, cena.objeto || 'interrogacao', k);
        if (o) { o.x = XO; o.dir = -1; o.olhar = 1; quicar(o, t + 0.25); if (k > 0.5) { o.olhos = 'arregalado'; o.boca = 'o'; } } },
      espera(h, o, k, l, t) { h.x = 540; h.pD = { x: 90, y: 300 - Math.max(0, Math.sin(U.TAU * batida(t))) * 50 }; h.bE = { x: -120, y: -40 }; h.olhos = 'normal'; h.boca = 'reta'; h.olhar = -1 + 2 * (Math.floor(t * 0.8) % 2); objeto('relogio', 540 - 130, CHAO - 900, 0, 0.6); if (o) quicar(o, t); }
    };

    // ---------- cartela de cinema mudo ----------
    function cartela(texto, k) {
      c.fillStyle = '#0D0C0B'; c.fillRect(0, 0, W, H);
      c.strokeStyle = '#D8CFB8'; c.lineWidth = 8; c.strokeRect(70, 520, W - 140, H - 1040); c.lineWidth = 3; c.strokeRect(96, 546, W - 192, H - 1092);
      [[70, 520], [W - 70, 520], [70, H - 520], [W - 70, H - 520]].forEach(([x, y]) => { c.beginPath(); c.arc(x, y, 22, 0, U.TAU); c.fillStyle = '#D8CFB8'; c.fill(); });
      c.font = '78px Rye, serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillStyle = '#E9E1CB';
      const ls = U.linhas(c, texto, W - 300), lh = 104;
      ls.forEach((l, i) => c.fillText(l, W / 2, H / 2 - ((ls.length - 1) * lh) / 2 + i * lh));
    }

    // ---------- o quadro ----------
    function quadro(t) {
      const { c: cena, k, local } = U.cenaEm(spec, t);
      const f = Math.round(t * (spec.fps || 30));
      c.save();
      // a janela do projetor treme (gate weave)
      const r = U.rng(f + 17); c.translate((r() - 0.5) * 4, (r() - 0.5) * 4);
      if (cena.acao === 'cartela') cartela(cena.texto || '', k);
      else {
        const cam = { px: 0, z: 1 };
        if (cena.camera === 'perto') cam.z = U.lerp(1, 1.35, U.suave(k * 3));
        if (cena.camera === 'zoom_in') cam.z = U.lerp(1, 1.45, U.suave(k));
        c.save(); c.translate(W / 2, H * 0.55); c.scale(cam.z, cam.z); c.translate(-W / 2, -H * 0.55);
        if (cena.camera === 'tremor' || (cena.acao === 'objeto_cai_na_cabeca' && k > 0.45 && k < 0.6)) c.translate((r() - 0.5) * 40, (r() - 0.5) * 30);
        cenario(cena.cenario || 'rua', t, cam);
        const at = cena.atores && cena.atores.length ? cena.atores : ['hank'];
        const h = pose(XH), o = at[1] ? pose(XO) : null; if (o) o.dir = -1;
        (ACOES[cena.acao] || ACOES.parado)(h, o, k, local, t, cena);
        if (o && !o.oculto) desenharAtor(at[1], o, t);
        if (!h.oculto) desenharAtor(at[0], h, t);
        c.restore();
      }
      U.cartaz(c, spec, t, { fonte: '74px Rye, serif', y: 150, fundo: '#0D0C0B', borda: '#E9E1CB', cor: '#E9E1CB', altura_linha: 92, dur: 2.8 });
      // pelicula: grao, risco, cintilacao, vinheta
      c.globalAlpha = 0.9; c.drawImage(graos[f % graos.length], 0, 0, W, H); c.globalAlpha = 1;
      if (r() < 0.18) { c.strokeStyle = 'rgba(20,18,16,.35)'; c.lineWidth = 3; const x = r() * W; c.beginPath(); c.moveTo(x, 0); c.lineTo(x + (r() - 0.5) * 40, H); c.stroke(); }
      c.fillStyle = 'rgba(255,250,235,' + (0.04 * r()).toFixed(3) + ')'; c.fillRect(0, 0, W, H);
      const v = c.createRadialGradient(W / 2, H / 2, H * 0.3, W / 2, H / 2, H * 0.75); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.55)'); c.fillStyle = v; c.fillRect(0, 0, W, H);
      c.restore();
      // IRIS: abre no comeco, fecha no fim (e o loop recomeca da iris)
      const ab = U.clamp(t / 0.6, 0, 1), fe = U.clamp((spec.dur_s - t) / 0.6, 0, 1), raio = Math.hypot(W, H) * 0.6 * U.suave(Math.min(ab, fe));
      if (raio < Math.hypot(W, H) * 0.6) { c.save(); c.beginPath(); c.rect(0, 0, W, H); c.arc(W / 2, H * 0.45, Math.max(1, raio), 0, U.TAU, true); c.fillStyle = '#000'; c.fill('evenodd'); c.restore(); }
    }
    return { quadro };
  }
  MOTORES.mangueira = { criar, vocabulario: () => ({}) };
})();
