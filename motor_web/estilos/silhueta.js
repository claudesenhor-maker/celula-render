// SILHUETA -- historia real narrada em sombra (13/10, HISTORICO §109).
//
// O canal conta MISTERIOS E HISTORIAS REAIS (sem violencia grafica): a voz
// carrega a historia e a imagem da o clima. Silhueta esconde detalhe, entao o
// que nao da para desenhar (rosto, arma, documento) nunca precisa aparecer --
// a pose e o horizonte bastam. O que faz o estilo: ceu em degrade pela HORA,
// tres planos de paisagem em paralaxe, um disco de sol/lua atras de tudo, a
// camera que nunca para (empurra devagar), e o clima (nevoa, chuva, raio).
(function () {
  'use strict';
  const CEUS = {
    aurora: ['#1B2A4A', '#6B4E7A', '#E58A6F', '#F6C37A'],
    entardecer: ['#241536', '#7A2E52', '#E2674B', '#F6B26B'],
    noite: ['#05070F', '#0B1430', '#1B2A55', '#2F3E6E'],
    tempestade: ['#0E1216', '#232B33', '#3A444D', '#58636B'],
    dia: ['#2D5C8A', '#6FA3C8', '#BFD9E6', '#F2E3C2']
  };
  const DISCO = { aurora: '#FFD9A0', entardecer: '#FFE2A8', noite: '#E8ECF5', tempestade: null, dia: '#FFF4D6' };

  function criar(tela, spec, U) {
    const c = tela.getContext('2d'), W = spec.w, H = spec.h, CHAO = H * 0.74;
    const camadas = {};   // por cenario: 3 perfis sorteados uma vez
    function perfil(cen, k) {
      const chave = cen + k;
      if (camadas[chave]) return camadas[chave];
      const r = U.rng((spec.semente || 'sil') + chave), pts = [];
      for (let i = 0; i < 40; i++) pts.push(r());
      return (camadas[chave] = { pts, r2: Array.from({ length: 60 }, () => r()) });
    }

    // ---------- a figura em sombra (v2 05/11) ----------
    // Anatomia de verdade em vez de tubos: membros afinam (coxa > canela), ombros
    // arredondados, pescoço, mãos e sapatos; cabelo/roupa dizem quem é (cartola
    // só no "velho"). A silhueta continua escondendo rosto e detalhe.
    function capsula(a, b, r1, r2) {
      const ang = Math.atan2(b[1] - a[1], b[0] - a[0]), n = ang + Math.PI / 2;
      c.beginPath();
      c.moveTo(a[0] + Math.cos(n) * r1, a[1] + Math.sin(n) * r1); c.lineTo(b[0] + Math.cos(n) * r2, b[1] + Math.sin(n) * r2);
      c.arc(b[0], b[1], r2, n, n + Math.PI, true); c.lineTo(a[0] - Math.cos(n) * r1, a[1] - Math.sin(n) * r1);
      c.arc(a[0], a[1], r1, n + Math.PI, n + 2 * Math.PI, true); c.closePath(); c.fill();
    }
    function figura(x, y, esc, tipo, pose, t) {
      c.save(); c.translate(x, y); c.scale(esc * (pose.dir || 1), esc); c.fillStyle = '#050407'; c.strokeStyle = '#050407'; c.lineCap = 'round'; c.lineJoin = 'round';
      const p = pose, alt = tipo === 'crianca' ? 0.68 : (tipo === 'mulher' ? 0.95 : 1);
      c.scale(alt, alt);
      const quadril = [0, -230 + (p.bob || 0)], ombro = [p.incl || 0, -430 + (p.bob || 0)];
      function membro(a, ang1, ang2, l1, l2, r0, r1, r2) {
        const j = [a[0] + Math.sin(ang1) * l1, a[1] + Math.cos(ang1) * l1], e = [j[0] + Math.sin(ang1 + ang2) * l2, j[1] + Math.cos(ang1 + ang2) * l2];
        capsula(a, j, r0, r1); capsula(j, e, r1, r2); return e;
      }
      const vento = Math.sin(t * 3) * 14 + (p.vento || 0);
      // pernas (a de trás um pouco mais fina dá profundidade)
      const pe1 = membro([quadril[0] - 16, quadril[1]], p.coxa1 || 0.05, p.canela1 || 0, 118, 114, 25, 17, 12);
      const pe2 = membro([quadril[0] + 16, quadril[1]], p.coxa2 || -0.05, p.canela2 || 0, 118, 114, 23, 16, 11);
      [pe1, pe2].forEach((pe) => { c.beginPath(); c.moveTo(pe[0] - 14, pe[1] - 8); c.quadraticCurveTo(pe[0] + 40, pe[1] - 14, pe[0] + 44, pe[1] + 6); c.lineTo(pe[0] - 16, pe[1] + 8); c.closePath(); c.fill(); });
      // tronco: ombros arredondados, cintura, quadril
      c.beginPath();
      c.moveTo(quadril[0] - 40, quadril[1] + 12);
      c.quadraticCurveTo(ombro[0] - 52, (ombro[1] + quadril[1]) / 2, ombro[0] - 58, ombro[1] + 22);
      c.quadraticCurveTo(ombro[0] - 56, ombro[1] - 6, ombro[0] - 24, ombro[1] - 10);
      c.lineTo(ombro[0] + 24, ombro[1] - 10);
      c.quadraticCurveTo(ombro[0] + 56, ombro[1] - 6, ombro[0] + 58, ombro[1] + 22);
      c.quadraticCurveTo(ombro[0] + 50, (ombro[1] + quadril[1]) / 2, quadril[0] + 40, quadril[1] + 12);
      c.closePath(); c.fill();
      if (tipo === 'homem' || tipo === 'velho') { // casaco longo que o vento abre
        c.beginPath(); c.moveTo(quadril[0] - 42, quadril[1] - 10); c.lineTo(quadril[0] + 42, quadril[1] - 10);
        c.quadraticCurveTo(quadril[0] + 50, quadril[1] + 60, quadril[0] + 34, quadril[1] + 120);
        c.lineTo(quadril[0] - 40 - vento * 1.2, quadril[1] + 118); c.closePath(); c.fill();
      }
      if (tipo === 'mulher') { c.beginPath(); c.moveTo(quadril[0] - 44, quadril[1] - 20); c.lineTo(quadril[0] + 44, quadril[1] - 20); c.quadraticCurveTo(quadril[0] + 80, quadril[1] + 70, quadril[0] + 92, quadril[1] + 150); c.lineTo(quadril[0] - 92 - vento, quadril[1] + 150); c.quadraticCurveTo(quadril[0] - 76, quadril[1] + 70, quadril[0] - 44, quadril[1] - 20); c.fill(); }
      // braços afinando até a mão
      const m1 = membro([ombro[0] - 46, ombro[1] + 14], p.braco1 || 0.15, p.ante1 || 0, 108, 100, 20, 14, 10);
      const m2 = membro([ombro[0] + 46, ombro[1] + 14], p.braco2 || -0.15, p.ante2 || 0, 108, 100, 20, 14, 10);
      [m1, m2].forEach((m) => { c.beginPath(); c.ellipse(m[0], m[1] + 8, 13, 18, 0, 0, U.TAU); c.fill(); });
      if (p.lanterna) { const g = c.createRadialGradient(m2[0], m2[1], 4, m2[0], m2[1], 560); g.addColorStop(0, 'rgba(255,214,140,.6)'); g.addColorStop(1, 'rgba(255,214,140,0)');
        c.save(); c.fillStyle = g; c.beginPath(); c.moveTo(m2[0], m2[1]); c.arc(m2[0], m2[1], 560, -0.32, 0.32); c.closePath(); c.fill(); c.restore(); c.fillRect(m2[0] - 12, m2[1] - 8, 24, 44); }
      if (p.carta) { c.save(); c.translate((m1[0] + m2[0]) / 2, (m1[1] + m2[1]) / 2 - 20); c.rotate(-0.1); c.fillRect(-55, -70, 110, 140); c.restore(); }
      if (p.pa) { c.lineWidth = 10; c.beginPath(); c.moveTo(m2[0], m2[1]); c.lineTo(m2[0] + 70, m2[1] + 170); c.stroke(); c.beginPath(); c.ellipse(m2[0] + 80, m2[1] + 190, 26, 40, -0.4, 0, U.TAU); c.fill(); }
      if (tipo === 'velho') { c.lineWidth = 10; c.beginPath(); c.moveTo(m1[0], m1[1]); c.lineTo(m1[0] - 10, 0); c.stroke(); }
      // pescoço e cabeça (perfil levemente virado: nariz e queixo)
      const cab = [ombro[0] + (p.cabeca || 0) * 30, ombro[1] - 74];
      capsula([ombro[0], ombro[1] - 4], [cab[0], cab[1] + 30], 17, 15);
      c.beginPath(); c.ellipse(cab[0], cab[1], 44, 52, 0, 0, U.TAU); c.fill();
      c.beginPath(); c.moveTo(cab[0] + 38, cab[1] - 8); c.lineTo(cab[0] + 54, cab[1] + 10); c.lineTo(cab[0] + 38, cab[1] + 18); c.fill();
      if (tipo === 'velho') { c.beginPath(); c.ellipse(cab[0], cab[1] - 30, 84, 13, -0.05, 0, U.TAU); c.fill(); c.beginPath(); c.moveTo(cab[0] - 46, cab[1] - 32); c.quadraticCurveTo(cab[0] - 44, cab[1] - 96, cab[0], cab[1] - 92); c.quadraticCurveTo(cab[0] + 44, cab[1] - 96, cab[0] + 46, cab[1] - 32); c.fill(); }
      else if (tipo === 'mulher') { c.beginPath(); c.moveTo(cab[0] - 46, cab[1] - 16); c.quadraticCurveTo(cab[0] - 66 - vento, cab[1] + 80, cab[0] - 44 - vento * 1.5, cab[1] + 150); c.lineTo(cab[0] + 6, cab[1] + 44); c.quadraticCurveTo(cab[0] + 50, cab[1] - 40, cab[0] + 10, cab[1] - 58); c.quadraticCurveTo(cab[0] - 40, cab[1] - 58, cab[0] - 46, cab[1] - 16); c.fill(); }
      else { c.beginPath(); c.ellipse(cab[0] - 6, cab[1] - 26, 48, 30, -0.2, Math.PI, U.TAU); c.fill(); }
      c.restore();
    }
    function poseDe(acao, t, k) {
      const a = U.TAU * t * 0.9, s = Math.sin(a);
      switch (acao) {
        case 'anda': return { coxa1: 0.45 * s, coxa2: -0.45 * s, canela1: -Math.max(0, -s) * 0.6, canela2: -Math.max(0, s) * 0.6, braco1: -0.4 * s, braco2: 0.4 * s, ante1: 0.3, ante2: 0.3, bob: -Math.abs(Math.cos(a)) * 8 };
        case 'corre': { const b = U.TAU * t * 1.8, q = Math.sin(b); return { coxa1: 0.9 * q, coxa2: -0.9 * q, canela1: -Math.max(0, -q) * 1.4, canela2: -Math.max(0, q) * 1.4, braco1: -0.9 * q, braco2: 0.9 * q, ante1: 1.2, ante2: 1.2, incl: 30, bob: -Math.abs(Math.cos(b)) * 18, vento: 30 }; }
        case 'olha': return { braco1: 0.1, braco2: -2.2, ante2: -0.9, cabeca: 0.3, bob: Math.sin(t * 2) * 2 };
        case 'aponta': return { braco2: -1.8 + 0.05 * Math.sin(t * 2), ante2: 0.1, braco1: 0.15, cabeca: 0.4 };
        case 'cava': { const q = Math.sin(U.TAU * t * 0.8); return { braco1: -0.6 + 0.5 * q, braco2: -0.9 + 0.6 * q, ante1: 0.8, ante2: 0.6, incl: 40 + 20 * q, coxa1: 0.3, coxa2: -0.2, canela1: -0.4, pa: true }; }
        case 'le_carta': return { braco1: -1.2, braco2: 1.2, ante1: 1.4, ante2: -1.4, cabeca: 0.1, carta: true, bob: Math.sin(t * 1.5) * 2 };
        case 'lanterna': return { braco2: -1.4, ante2: 0.1, braco1: 0.2, lanterna: true, coxa1: 0.2 * Math.sin(t * 2), coxa2: -0.2 * Math.sin(t * 2) };
        case 'ajoelha': return { coxa1: -1.5, canela1: 1.6, coxa2: 0.3, canela2: -1.4, braco1: -0.3, braco2: 0.3, bob: 80, incl: 20 };
        case 'cai': { const q = U.saida(k); return { incl: 120 * q, coxa1: 0.6, coxa2: -0.4, braco1: -2.4 * q, braco2: 2.0 * q, bob: 60 * q }; }
        default: return { braco1: 0.12, braco2: -0.12, bob: Math.sin(t * 1.6) * 3 };
      }
    }

    // ---------- paisagem ----------
    function horizonte(cen, k, base, amp, cor, t, desl) {
      const P = perfil(cen, k);
      c.fillStyle = cor; c.beginPath(); c.moveTo(-200, H);
      const passo = (W + 400) / (P.pts.length - 1);
      for (let i = 0; i < P.pts.length; i++) {
        const x = -200 + i * passo - desl, v = P.pts[i];
        let y = base;
        if (cen === 'montanha') y = base - amp * (0.4 + v) * (i % 4 === 0 ? 1.4 : 0.9);
        else if (cen === 'deserto' || cen === 'mar') y = base - amp * 0.3 * Math.sin(i * 0.5 + k) - amp * 0.1 * v;
        else if (cen === 'floresta') { c.lineTo(x - passo / 2, base - amp * 0.2); c.lineTo(x, base - amp * (0.8 + v * 0.8)); y = base - amp * 0.2; }
        else if (cen === 'cidade') { const h = amp * (0.5 + v * 1.4); c.lineTo(x, base - h); c.lineTo(x + passo * 0.85, base - h); if (v > 0.7) { c.lineTo(x + passo * 0.4, base - h); c.lineTo(x + passo * 0.42, base - h - 90); c.lineTo(x + passo * 0.44, base - h); } y = base - h; }
        else y = base - amp * (0.25 + 0.35 * v);
        c.lineTo(x, y);
      }
      c.lineTo(W + 400, H); c.closePath(); c.fill();
    }
    function marco(cen, x, base, t) {
      c.fillStyle = '#050407'; c.strokeStyle = '#050407';
      if (cen === 'castelo') { c.fillRect(x - 200, base - 320, 400, 320); [-200, -60, 80, 200].forEach((d, i) => { c.fillRect(x + d - 40, base - 420 - (i % 2) * 80, 80, 420); for (let m = 0; m < 3; m++) c.fillRect(x + d - 40 + m * 30, base - 450 - (i % 2) * 80, 20, 30); }); }
      if (cen === 'farol') { c.beginPath(); c.moveTo(x - 60, base); c.lineTo(x - 36, base - 520); c.lineTo(x + 36, base - 520); c.lineTo(x + 60, base); c.fill(); c.fillRect(x - 50, base - 600, 100, 80);
        const a = Math.sin(t * 1.2) * 1.2; const g = c.createLinearGradient(x, base - 560, x + Math.cos(a) * 900, base - 560 + Math.sin(a) * 100); g.addColorStop(0, 'rgba(255,240,190,.6)'); g.addColorStop(1, 'rgba(255,240,190,0)');
        c.save(); c.fillStyle = g; c.beginPath(); c.moveTo(x, base - 560); c.lineTo(x + Math.cos(a - 0.08) * 1000, base - 560 + Math.sin(a - 0.08) * 1000); c.lineTo(x + Math.cos(a + 0.08) * 1000, base - 560 + Math.sin(a + 0.08) * 1000); c.fill(); c.restore(); }
      if (cen === 'vila') { for (let i = 0; i < 4; i++) { const hx = x - 420 + i * 260, hh = 160 + (i % 2) * 60; c.fillRect(hx, base - hh, 200, hh); c.beginPath(); c.moveTo(hx - 20, base - hh); c.lineTo(hx + 100, base - hh - 110); c.lineTo(hx + 220, base - hh); c.fill(); c.fillRect(hx + 140, base - hh - 90, 26, 60);
          c.fillStyle = 'rgba(255,200,120,.75)'; c.fillRect(hx + 40, base - hh + 50, 36, 40); c.fillStyle = '#050407'; } }
      if (cen === 'deserto') { c.beginPath(); c.moveTo(x - 260, base); c.lineTo(x, base - 340); c.lineTo(x + 260, base); c.fill(); }
      if (cen === 'estrada') { for (let i = 0; i < 5; i++) { const px = ((x + i * 300 - t * 60) % 1500) - 200; c.fillRect(px, base - 420, 14, 420); c.fillRect(px - 40, base - 410, 94, 10); } c.lineWidth = 3; c.beginPath(); c.moveTo(-200, base - 400); for (let i = 0; i < 12; i++) c.quadraticCurveTo(i * 150 - 125, base - 360, i * 150 - 50, base - 400); c.stroke(); }
      if (cen === 'ceu_estrelado') { c.lineWidth = 26; c.beginPath(); c.moveTo(x, base); c.lineTo(x + 10, base - 300); c.stroke(); c.lineWidth = 12; [[-120, -420], [130, -460], [60, -380], [-60, -480]].forEach(([dx, dy]) => { c.beginPath(); c.moveTo(x + 10, base - 280); c.quadraticCurveTo(x + dx * 0.5, base + dy * 0.6, x + dx, base + dy); c.stroke(); }); }
    }
    function navio(x, y, t) { c.save(); c.translate(x, y + Math.sin(t * 1.4) * 10); c.rotate(Math.sin(t * 1.1) * 0.04); c.fillStyle = '#050407';
      c.beginPath(); c.moveTo(-260, 0); c.lineTo(260, 0); c.lineTo(200, 80); c.lineTo(-220, 80); c.fill(); c.fillRect(-10, -380, 14, 380);
      c.beginPath(); c.moveTo(4, -360); c.quadraticCurveTo(180, -200, 4, -40); c.fill(); c.beginPath(); c.moveTo(-10, -320); c.quadraticCurveTo(-170, -190, -10, -60); c.fill(); c.restore(); }
    function clima(nome, t, ceu) {
      const r = U.rng(7);
      if (nome === 'chuva' || nome === 'tempestade') { c.strokeStyle = 'rgba(200,215,230,.35)'; c.lineWidth = 3; for (let i = 0; i < 140; i++) { const x = r() * W, v = 1400 + r() * 600, y = ((r() * H + t * v) % (H + 100)) - 50; c.beginPath(); c.moveTo(x, y); c.lineTo(x - 18, y + 46); c.stroke(); } }
      if (nome === 'neve') { c.fillStyle = 'rgba(255,255,255,.8)'; for (let i = 0; i < 120; i++) { const x = (r() * W + Math.sin(t + i) * 30), y = ((r() * H + t * (60 + r() * 80)) % H); c.beginPath(); c.arc(x, y, 3 + r() * 4, 0, U.TAU); c.fill(); } }
      if (nome === 'nevoa') { for (let i = 0; i < 4; i++) { const g = c.createLinearGradient(0, CHAO - 300 + i * 90, 0, CHAO + 100 + i * 90); g.addColorStop(0, 'rgba(210,205,220,0)'); g.addColorStop(0.5, 'rgba(210,205,220,.22)'); g.addColorStop(1, 'rgba(210,205,220,0)'); c.fillStyle = g; c.fillRect(-100 + ((t * (20 + i * 9)) % 200) - 100, CHAO - 300 + i * 90, W + 400, 400); } }
      if (nome === 'passaros') { c.strokeStyle = '#050407'; c.lineWidth = 6; for (let i = 0; i < 7; i++) { const x = ((t * 90 + i * 140 + r() * 80) % (W + 300)) - 150, y = 520 + i * 30 + Math.sin(t * 2 + i) * 20, b = Math.sin(t * 9 + i) * 16; c.beginPath(); c.moveTo(x - 30, y - b); c.quadraticCurveTo(x - 12, y - 10, x, y); c.quadraticCurveTo(x + 12, y - 10, x + 30, y - b); c.stroke(); } }
      if (nome === 'vagalumes') { for (let i = 0; i < 30; i++) { const x = r() * W + Math.sin(t * 0.7 + i) * 40, y = CHAO - 400 + r() * 500 + Math.cos(t * 0.9 + i) * 30, a = 0.5 + 0.5 * Math.sin(t * 3 + i * 2); c.fillStyle = 'rgba(255,240,150,' + (a * 0.9).toFixed(2) + ')'; c.beginPath(); c.arc(x, y, 6, 0, U.TAU); c.fill(); } }
      if (nome === 'fogueira') { const x = W * 0.68, y = CHAO + 40; const g = c.createRadialGradient(x, y - 40, 10, x, y - 40, 600); g.addColorStop(0, 'rgba(255,170,80,.45)'); g.addColorStop(1, 'rgba(255,170,80,0)'); c.fillStyle = g; c.fillRect(0, 0, W, H);
        for (let i = 0; i < 5; i++) { const f = Math.sin(t * 9 + i) * 12; c.fillStyle = i % 2 ? '#FFB347' : '#FF7A3D'; c.beginPath(); c.moveTo(x - 60 + i * 30, y); c.quadraticCurveTo(x - 50 + i * 30 + f, y - 120 - i * 10, x - 40 + i * 25, y - 200 + f); c.quadraticCurveTo(x - 20 + i * 30 - f, y - 80, x - 10 + i * 30, y); c.fill(); } }
      if (nome === 'estrelas_cadentes') { const k = (t * 0.5) % 1; c.strokeStyle = 'rgba(255,255,255,' + (1 - k) + ')'; c.lineWidth = 4; c.beginPath(); c.moveTo(200 + k * 700, 200 + k * 300); c.lineTo(80 + k * 700, 140 + k * 300); c.stroke(); }
    }

    // raios de luz atrás das figuras (sol/lua/neblina): dão profundidade de cinema
    function raios(hora, t, desl) {
      if (!DISCO[hora]) return;
      const dx = W * 0.62 - desl * 0.1, dy = CHAO - 520;
      c.save(); c.globalCompositeOperation = 'lighter';
      for (let i = 0; i < 7; i++) {
        const a = Math.PI / 2 + (i - 3) * 0.22 + Math.sin(t * 0.25 + i) * 0.03, L = 1500;
        const g = c.createLinearGradient(dx, dy, dx + Math.cos(a) * L, dy + Math.sin(a) * L);
        g.addColorStop(0, DISCO[hora] + '22'); g.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = g;
        c.beginPath(); c.moveTo(dx, dy); c.lineTo(dx + Math.cos(a - 0.05) * L, dy + Math.sin(a - 0.05) * L); c.lineTo(dx + Math.cos(a + 0.05) * L, dy + Math.sin(a + 0.05) * L); c.closePath(); c.fill();
      }
      c.restore();
    }
    function mar(hora, cor, t, desl) {
      const y0 = CHAO - 300;
      const g = c.createLinearGradient(0, y0, 0, H); g.addColorStop(0, cor[2]); g.addColorStop(0.15, cor[1]); g.addColorStop(1, '#03040a');
      c.fillStyle = g; c.fillRect(-100, y0, W + 200, H);
      // trilha de luz do disco na água
      if (DISCO[hora]) { const dx = W * 0.62 - desl * 0.1; c.save(); c.globalCompositeOperation = 'lighter';
        for (let j = 0; j < 46; j++) { const yy = y0 + 8 + j * j * 0.55, w = 40 + j * 7 + Math.sin(t * 2 + j) * 20; c.fillStyle = DISCO[hora] + (j < 20 ? '55' : '22'); c.fillRect(dx - w / 2 + Math.sin(t * 1.6 + j * 1.3) * 18, yy, w, 3); }
        c.restore(); }
      c.strokeStyle = 'rgba(0,0,0,.35)'; c.lineWidth = 3;
      for (let j = 0; j < 14; j++) { const yy = y0 + 20 + j * j * 3; c.beginPath(); for (let x = -40; x < W + 40; x += 40) c.lineTo(x, yy + Math.sin(x * 0.02 + t * 1.5 + j) * (2 + j)); c.stroke(); }
    }
    function conves(t, desl) {
      // convés do barco em primeiro plano: amurada, cabos e o balanço do mar
      const rol = Math.sin(t * 1.1) * 0.018;
      c.save(); c.translate(W / 2, CHAO + 40); c.rotate(rol); c.translate(-W / 2, -(CHAO + 40));
      c.fillStyle = '#050407'; c.fillRect(-200, CHAO + 30, W + 400, H);
      c.fillRect(-200, CHAO - 120, W + 400, 16);
      for (let x = -160; x < W + 200; x += 130) c.fillRect(x - desl * 0.9, CHAO - 120, 14, 150);
      c.lineWidth = 6; c.strokeStyle = '#050407'; c.beginPath(); c.moveTo(-100, CHAO - 60); c.lineTo(W + 100, CHAO - 70); c.stroke();
      c.lineWidth = 8; c.beginPath(); c.moveTo(W * 0.9 - desl, CHAO + 30); c.lineTo(W * 0.96 - desl, -100); c.stroke();
      c.lineWidth = 3; c.beginPath(); c.moveTo(W * 0.96 - desl, -60); c.lineTo(W * 0.5, CHAO - 120); c.stroke();
      c.restore();
    }
    let padraoGrao = null;
    const grao = U.camada(256, 256, (g) => { const r = U.rng(99), im = g.createImageData(256, 256); for (let i = 0; i < im.data.length; i += 4) { const v = r() * 255; im.data[i] = im.data[i + 1] = im.data[i + 2] = v; im.data[i + 3] = 18; } g.putImageData(im, 0, 0); });
    // ---------- o quadro ----------
    function cena(cn, t, k, local) {
      const hora = cn.hora || (cn.objeto === 'raio' ? 'tempestade' : 'entardecer'), cor = CEUS[hora] || CEUS.entardecer;
      // camera: empurra devagar sempre; `zoom_out` abre, `paralaxe` desliza
      const z = cn.camera === 'zoom_out' ? U.lerp(1.25, 1, U.suave(k)) : U.lerp(1.04, 1.22, U.suave(k));
      const desl = (cn.camera === 'paralaxe' ? 160 : 60) * U.suave(k);
      c.save(); c.translate(W * 0.5, H * 0.5); c.scale(z, z); c.translate(-W * 0.5, -H * 0.5);
      const g = c.createLinearGradient(0, 0, 0, CHAO); cor.forEach((col, i) => g.addColorStop(i / (cor.length - 1), col)); c.fillStyle = g; c.fillRect(-100, -100, W + 200, H + 200);
      if (hora === 'noite' || cn.cenario === 'ceu_estrelado') { const r = U.rng(3); for (let i = 0; i < 160; i++) { const a = 0.4 + 0.6 * Math.abs(Math.sin(t * (0.5 + r()) + i)); c.fillStyle = 'rgba(255,255,255,' + (a * r()).toFixed(2) + ')'; c.fillRect(r() * W, r() * CHAO * 0.8, 3, 3); } }
      if (DISCO[hora]) { const dx = W * 0.62 - desl * 0.1, dy = CHAO - 520; const gl = c.createRadialGradient(dx, dy, 60, dx, dy, 520); gl.addColorStop(0, DISCO[hora]); gl.addColorStop(0.25, DISCO[hora] + '88'); gl.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = gl; c.fillRect(0, 0, W, H); c.beginPath(); c.arc(dx, dy, 170, 0, U.TAU); c.fillStyle = DISCO[hora]; c.fill(); }
      const cen = cn.cenario || 'montanha';
      raios(hora, t, desl);
      if (cen === 'mar') {
        mar(hora, cor, t, desl);
        navio(W * 0.78 - desl * 0.4, CHAO - 250, t);
        conves(t, desl);
      } else {
        horizonte(cen, 1, CHAO - 260, 420, 'rgba(10,8,16,.45)', t, desl * 0.25);
        horizonte(cen, 2, CHAO - 120, 300, 'rgba(8,6,12,.7)', t, desl * 0.5);
        marco(cen, W * 0.5 - desl * 0.7, CHAO - 40, t);
        horizonte(cen === 'cidade' ? 'cidade' : 'colina', 3, CHAO + 30, 90, '#050407', t, desl);
        c.fillStyle = '#050407'; c.fillRect(-100, CHAO + 20, W + 200, H);
      }
      if (cn.objeto && cn.objeto !== 'raio' && cn.objeto !== 'navio') clima(cn.objeto, t, cor);
      if (hora === 'tempestade' || cn.objeto === 'chuva') clima('chuva', t, cor);
      // gente
      const at = cn.atores && cn.atores.length ? cn.atores : ['homem'];
      if (at[0] === 'multidao') { for (let i = 0; i < 9; i++) figura(80 + i * 115 - desl * 0.8, CHAO + 30, 0.55 + (i % 3) * 0.06, i % 3 === 1 ? 'mulher' : 'homem', poseDe(cn.acao === 'anda' || cn.acao === 'corre' ? cn.acao : (i % 2 ? 'olha' : 'parado'), t + i, k), t); }
      else at.slice(0, 2).forEach((tipo, i) => {
        const acao = i === 0 ? cn.acao : (cn.acao === 'anda' || cn.acao === 'corre' ? cn.acao : 'parado');
        const x0 = i === 0 ? W * 0.36 : W * 0.68, mov = acao === 'anda' ? 180 * k : (acao === 'corre' ? 520 * k : 0);
        figura(x0 + mov - desl, CHAO + 30, 1.3, tipo, poseDe(acao, t + i * 0.37, k), t);
      });
      c.restore();
      if (cn.objeto === 'raio' || hora === 'tempestade') { const q = (t * 0.7) % 1; if (q < 0.06) { c.fillStyle = 'rgba(235,240,255,' + (0.7 * (1 - q / 0.06)) + ')'; c.fillRect(0, 0, W, H); } }
    }
    const vinheta = U.camada(W,H,g=>{const v=g.createRadialGradient(W/2,H/2,H*.35,W/2,H/2,H*.8);v.addColorStop(0,'rgba(0,0,0,0)');v.addColorStop(1,'rgba(0,0,0,.5)');g.fillStyle=v;g.fillRect(0,0,W,H);});
    function quadro(t) {
      const { c: cn, i, k, local } = U.cenaEm(spec, t);
      cena(cn, t, k, local);
      // passagem entre cenas: mergulho no preto de 0,3 s
      const borda = Math.min(t - cn.ini, cn.fim - t), dip = U.clamp(1 - borda / 0.18, 0, 1);
      if (i > 0 && t - cn.ini < 0.18 || i < spec.cenas.length - 1 && cn.fim - t < 0.18) { c.fillStyle = 'rgba(0,0,0,' + (dip*0.4).toFixed(3) + ')'; c.fillRect(0, 0, W, H); }
      // vinheta de cinema
      c.drawImage(vinheta,0,0);
      { const ox = Math.floor(t * 30 * 37) % 256, oy = Math.floor(t * 30 * 53) % 256; if (!padraoGrao && c.createPattern) padraoGrao = c.createPattern(grao, 'repeat'); if (padraoGrao) { c.save(); c.translate(-ox, -oy); c.fillStyle = padraoGrao; c.fillRect(0, 0, W + 256, H + 256); c.restore(); } }
      U.cartaz(c, spec, t, { fonte: '700 76px Cinzel, serif', y: 170, cor: '#F3E7D0', contorno: 14, cor_contorno: 'rgba(0,0,0,.85)', altura_linha: 96, dur: 3.2 });
      U.legenda(c, spec, t, { fonte: '600 92px Oswald, sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#FFC94A', contorno: 16, caixa: true, por_vez: 3 });
    }
    return { quadro };
  }
  MOTORES.silhueta = { criar };
})();
