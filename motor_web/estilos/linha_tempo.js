// LINHA DO TEMPO -- "de 1900 a hoje em 40 s" (23/10, TIMELINE DROP; um nicho
// e um motor por canal). A camera DESCE por uma linha do tempo vertical; cada
// cena e' um marco: o ano corre ate ele, o cartao entra com o icone e os
// marcos que ja passaram ficam acima, apagados. A distancia entre os marcos e'
// proporcional ao tempo (com piso), entao "3 anos" e "300 anos" se veem.
//
//   cena: { texto, acao: "marco|salto|zoom", ano: 1969 (pode ser negativo = a.C.),
//           evento: str curto, icone: um de ICONES, cor: "#hex", hud }
//   salto = o contador corre rapido (seculos); zoom = a camera aproxima do cartao
//
// CONTRATO (comum.js): `quadro(t)` sem estado entre quadros.
(function () {
  'use strict';
  // icones de vetor (sem emoji: a fonte do render nao tem). Cada um desenha num
  // quadrado de -1..1 com a cor atual.
  const ICONES = {
    foguete(c) { c.beginPath(); c.moveTo(0, -1); c.quadraticCurveTo(0.5, -0.4, 0.35, 0.5); c.lineTo(-0.35, 0.5); c.quadraticCurveTo(-0.5, -0.4, 0, -1); c.fill();
      c.beginPath(); c.moveTo(-0.35, 0.2); c.lineTo(-0.7, 0.75); c.lineTo(-0.3, 0.55); c.moveTo(0.35, 0.2); c.lineTo(0.7, 0.75); c.lineTo(0.3, 0.55); c.fill();
      c.fillStyle = '#FF8A3D'; c.beginPath(); c.moveTo(-0.2, 0.55); c.lineTo(0, 1); c.lineTo(0.2, 0.55); c.fill(); },
    lampada(c) { c.beginPath(); c.arc(0, -0.25, 0.6, Math.PI * 0.8, Math.PI * 2.2); c.lineTo(0.25, 0.55); c.lineTo(-0.25, 0.55); c.closePath(); c.fill(); c.fillRect(-0.25, 0.62, 0.5, 0.14); c.fillRect(-0.18, 0.82, 0.36, 0.12); },
    carro(c) { c.beginPath(); c.moveTo(-0.95, 0.35); c.lineTo(-0.95, 0); c.lineTo(-0.55, -0.05); c.lineTo(-0.3, -0.4); c.lineTo(0.35, -0.4); c.lineTo(0.6, -0.05); c.lineTo(0.95, 0.05); c.lineTo(0.95, 0.35); c.closePath(); c.fill();
      c.fillStyle = '#1B1B1B'; [-0.55, 0.55].forEach((x) => { c.beginPath(); c.arc(x, 0.38, 0.22, 0, Math.PI * 2); c.fill(); }); },
    aviao(c) { c.beginPath(); c.moveTo(0, -1); c.lineTo(0.12, -0.2); c.lineTo(0.95, 0.2); c.lineTo(0.95, 0.35); c.lineTo(0.12, 0.15); c.lineTo(0.1, 0.65); c.lineTo(0.35, 0.85); c.lineTo(0.35, 0.95);
      c.lineTo(0, 0.85); c.lineTo(-0.35, 0.95); c.lineTo(-0.35, 0.85); c.lineTo(-0.1, 0.65); c.lineTo(-0.12, 0.15); c.lineTo(-0.95, 0.35); c.lineTo(-0.95, 0.2); c.lineTo(-0.12, -0.2); c.closePath(); c.fill(); },
    computador(c) { c.fillRect(-0.9, -0.75, 1.8, 1.15); c.fillStyle = '#1B2A3A'; c.fillRect(-0.75, -0.62, 1.5, 0.9); c.fillStyle = c.strokeStyle; c.fillRect(-0.15, 0.4, 0.3, 0.3); c.fillRect(-0.55, 0.7, 1.1, 0.14); },
    telefone(c) { c.beginPath(); if (c.roundRect) c.roundRect(-0.45, -0.95, 0.9, 1.9, 0.18); else c.rect(-0.45, -0.95, 0.9, 1.9); c.fill(); c.fillStyle = '#1B2A3A'; c.fillRect(-0.36, -0.75, 0.72, 1.35); c.fillStyle = c.strokeStyle; c.beginPath(); c.arc(0, 0.78, 0.09, 0, Math.PI * 2); c.fill(); },
    globo(c) { c.beginPath(); c.arc(0, 0, 0.9, 0, Math.PI * 2); c.fill(); c.strokeStyle = '#1B2A3A'; c.lineWidth = 0.09; c.beginPath(); c.ellipse(0, 0, 0.4, 0.9, 0, 0, Math.PI * 2); c.moveTo(-0.9, 0); c.lineTo(0.9, 0); c.moveTo(-0.78, -0.45); c.lineTo(0.78, -0.45); c.moveTo(-0.78, 0.45); c.lineTo(0.78, 0.45); c.stroke(); },
    coroa(c) { c.beginPath(); c.moveTo(-0.9, 0.6); c.lineTo(-0.9, -0.5); c.lineTo(-0.45, 0); c.lineTo(0, -0.75); c.lineTo(0.45, 0); c.lineTo(0.9, -0.5); c.lineTo(0.9, 0.6); c.closePath(); c.fill(); c.fillRect(-0.9, 0.68, 1.8, 0.22); },
    espada(c) { c.beginPath(); c.moveTo(0, -1); c.lineTo(0.14, -0.8); c.lineTo(0.14, 0.35); c.lineTo(-0.14, 0.35); c.lineTo(-0.14, -0.8); c.closePath(); c.fill(); c.fillRect(-0.5, 0.35, 1, 0.14); c.fillRect(-0.09, 0.49, 0.18, 0.38); c.beginPath(); c.arc(0, 0.92, 0.12, 0, Math.PI * 2); c.fill(); },
    livro(c) { c.beginPath(); c.moveTo(0, -0.6); c.quadraticCurveTo(-0.5, -0.85, -0.95, -0.6); c.lineTo(-0.95, 0.75); c.quadraticCurveTo(-0.5, 0.5, 0, 0.75); c.quadraticCurveTo(0.5, 0.5, 0.95, 0.75); c.lineTo(0.95, -0.6); c.quadraticCurveTo(0.5, -0.85, 0, -0.6); c.fill();
      c.strokeStyle = '#1B2A3A'; c.lineWidth = 0.07; c.beginPath(); c.moveTo(0, -0.6); c.lineTo(0, 0.75); c.stroke(); },
    bandeira(c) { c.fillRect(-0.75, -0.95, 0.12, 1.9); c.beginPath(); c.moveTo(-0.63, -0.9); c.quadraticCurveTo(0, -1.1, 0.3, -0.8); c.quadraticCurveTo(0.6, -0.55, 0.9, -0.75); c.lineTo(0.9, 0.05); c.quadraticCurveTo(0.6, 0.25, 0.3, 0); c.quadraticCurveTo(0, -0.25, -0.63, -0.1); c.closePath(); c.fill(); },
    atomo(c) { c.lineWidth = 0.1; [0, 1, 2].forEach((i) => { c.beginPath(); c.ellipse(0, 0, 0.95, 0.35, (i * Math.PI) / 3, 0, Math.PI * 2); c.stroke(); }); c.beginPath(); c.arc(0, 0, 0.2, 0, Math.PI * 2); c.fill(); },
    dinheiro(c) { c.beginPath(); c.arc(0, 0, 0.9, 0, Math.PI * 2); c.fill(); c.fillStyle = '#1B2A3A'; c.font = 'bold 1.3px sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('$', 0, 0.08); },
    predio(c) { c.fillRect(-0.55, -0.95, 1.1, 1.9); c.fillStyle = '#1B2A3A'; for (let y = -0.8; y < 0.75; y += 0.3) for (let x = -0.4; x < 0.45; x += 0.3) c.fillRect(x, y, 0.16, 0.16); },
    navio(c) { c.beginPath(); c.moveTo(-1, 0.25); c.lineTo(1, 0.25); c.lineTo(0.7, 0.75); c.lineTo(-0.7, 0.75); c.closePath(); c.fill(); c.fillRect(-0.05, -0.95, 0.1, 1.2); c.beginPath(); c.moveTo(0.05, -0.9); c.lineTo(0.75, 0.15); c.lineTo(0.05, 0.15); c.fill(); },
    coracao(c) { c.beginPath(); c.moveTo(0, 0.85); c.bezierCurveTo(-1.2, 0, -0.75, -1, 0, -0.4); c.bezierCurveTo(0.75, -1, 1.2, 0, 0, 0.85); c.fill(); },
    explosao(c) { c.beginPath(); for (let i = 0; i < 16; i++) { const a = (i / 16) * Math.PI * 2, r = i % 2 ? 0.45 : 1; c.lineTo(Math.cos(a) * r, Math.sin(a) * r); } c.closePath(); c.fill(); },
    tela(c) { c.fillRect(-0.95, -0.6, 1.9, 1.15); c.fillStyle = '#1B2A3A'; c.fillRect(-0.82, -0.48, 1.64, 0.9); c.fillStyle = c.strokeStyle; c.beginPath(); c.moveTo(-0.2, -0.25); c.lineTo(0.3, -0.03); c.lineTo(-0.2, 0.2); c.fill(); c.fillRect(-0.35, 0.6, 0.7, 0.12); },
  };

  function criar(tela, spec, U) {
    const c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const PAL = ['#FF6B6B', '#FFD166', '#06D6A0', '#4CC9F0', '#B388EB', '#F78C6B'];
    const cenas = spec.cenas.map((cn, i) => ({ ano: Number.isFinite(Number(cn.ano)) ? Number(cn.ano) : (i ? null : 1900), evento: String(cn.evento || '').slice(0, 34),
      icone: ICONES[cn.icone] ? cn.icone : 'globo', cor: corOk(cn.cor, PAL[i % PAL.length]), acao: cn.acao || 'marco', hud: cn.hud }));
    cenas.forEach((cn, i) => { if (cn.ano == null) cn.ano = cenas[i - 1].ano + 1; });
    // posicao de cada marco na trilha: proporcional ao tempo (raiz, para seculos
    // nao virarem quilometros), com piso para dois marcos nunca se encostarem
    const Y = [0];
    for (let i = 1; i < cenas.length; i++) Y.push(Y[i - 1] + Math.max(640, Math.sqrt(Math.abs(cenas[i].ano - cenas[i - 1].ano)) * 140));
    const anoTxt = (a) => (a < 0 ? Math.round(-a).toLocaleString('en-US') + ' BC' : String(Math.round(a)));
    const X = 210;   // a trilha mora a esquerda; cartoes a direita (botoes do app ficam na borda direita)

    function fundo(t, prog) {
      // a cor do ceu muda com a epoca: sepia nos antigos, azul nos recentes
      const k = U.clamp(prog, 0, 1), cor = (a, b) => Math.round(U.lerp(a, b, k));
      const g = c.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, `rgb(${cor(52, 14)},${cor(36, 22)},${cor(24, 48)})`); g.addColorStop(1, `rgb(${cor(24, 6)},${cor(16, 10)},${cor(10, 24)})`);
      c.fillStyle = g; c.fillRect(0, 0, W, H);
      const r = U.rng(3); c.fillStyle = 'rgba(255,255,255,0.05)';
      for (let i = 0; i < 70; i++) { const x = r() * W, y = ((r() * H * 3 - t * 40 * (0.5 + r())) % H + H) % H; c.fillRect(x, y, 3, 3); }
    }

    // HORIZONTE DA ÉPOCA (v2 05/11): a cidade ao fundo muda com o ano que corre --
    // vila/castelo, casas com chaminé, fábricas, prédios, torres de vidro. O olho
    // VÊ o tempo passar em vez de ler só o número.
    const ERAS = [[-1e9, 'antigo'], [1500, 'vila'], [1800, 'chamine'], [1900, 'fabrica'], [1950, 'predio'], [1995, 'torre']];
    function eraDe(a) { let e = ERAS[0][1]; for (const [d, n] of ERAS) if (a >= d) e = n; return e; }
    const skylines = {};
    function skyline(era) {
      if (skylines[era]) return skylines[era];
      return (skylines[era] = U.camada(W + 400, 700, (g) => {
        const r = U.rng('sky' + era); g.fillStyle = '#000';
        const base = 700;
        for (let x = 0; x < W + 400;) {
          let w, h;
          if (era === 'antigo') { w = 160 + r() * 120; h = 80 + r() * 60; g.fillRect(x, base - h, w, h); if (r() > .6) { g.fillRect(x + w * .3, base - h - 160, 50, 160); g.beginPath(); g.moveTo(x + w * .3 - 10, base - h - 160); g.lineTo(x + w * .3 + 25, base - h - 220); g.lineTo(x + w * .3 + 60, base - h - 160); g.fill(); } }
          else if (era === 'vila') { w = 120 + r() * 80; h = 110 + r() * 80; g.fillRect(x, base - h, w, h); g.beginPath(); g.moveTo(x - 10, base - h); g.lineTo(x + w / 2, base - h - 70); g.lineTo(x + w + 10, base - h); g.fill(); if (r() > .8) g.fillRect(x + w / 2 - 12, base - h - 180, 24, 120); }
          else if (era === 'chamine') { w = 130 + r() * 90; h = 140 + r() * 90; g.fillRect(x, base - h, w, h); g.beginPath(); g.moveTo(x - 6, base - h); g.lineTo(x + w / 2, base - h - 50); g.lineTo(x + w + 6, base - h); g.fill(); g.fillRect(x + w * .7, base - h - 80, 22, 60); }
          else if (era === 'fabrica') { w = 200 + r() * 120; h = 160 + r() * 80; g.fillRect(x, base - h, w, h); for (let k = 0; k < 4; k++) { g.beginPath(); g.moveTo(x + k * w / 4, base - h); g.lineTo(x + k * w / 4 + w / 4, base - h - 50); g.lineTo(x + k * w / 4 + w / 4, base - h); g.fill(); } if (r() > .4) g.fillRect(x + w * .8, base - h - 260, 30, 260); }
          else if (era === 'predio') { w = 110 + r() * 90; h = 240 + r() * 200; g.fillRect(x, base - h, w, h); }
          else { w = 90 + r() * 80; h = 320 + r() * 330; g.fillRect(x, base - h, w, h); if (r() > .6) { g.fillRect(x + w / 2 - 4, base - h - 90, 8, 90); } }
          // janelas acesas
          g.save(); g.fillStyle = 'rgba(255,214,120,.55)';
          for (let yy = base - h + 24; yy < base - 20; yy += 34) for (let xx = x + 14; xx < x + w - 20; xx += 30) if (r() > .55) g.fillRect(xx, yy, 12, 16);
          g.restore(); g.fillStyle = '#000';
          x += w + 8 + r() * 30;
        }
      }));
    }
    function cidade(anoAgora, yCam, prog) {
      const era = eraDe(anoAgora), img = skyline(era), ox = (yCam * 0.08) % 400;
      // silhueta CLARA sobre o céu escuro (preto sobre escuro sumia), tingida pela época
      const tinta = { antigo: '#6b4a2e', vila: '#6b4a2e', chamine: '#5a4636', fabrica: '#4a4652', predio: '#34466a', torre: '#2c4a7a' }[era];
      if (!skylines['t' + era]) skylines['t' + era] = U.camada(W + 400, 700, (g) => { g.drawImage(img, 0, 0); g.globalCompositeOperation = 'source-atop'; g.fillStyle = tinta; g.fillRect(0, 0, W + 400, 700); g.globalCompositeOperation = 'source-over';
        g.globalCompositeOperation = 'source-atop'; const r = U.rng('jan' + era); g.fillStyle = 'rgba(255,214,120,.8)'; for (let i = 0; i < 260; i++) g.fillRect(r() * (W + 400), 260 + r() * 420, 10, 14); g.globalCompositeOperation = 'source-over'; });
      c.save(); c.globalAlpha = 0.9; c.drawImage(skylines['t' + era], -ox, H - 700 - 420); c.restore();
      const g = c.createLinearGradient(0, H - 700, 0, H); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.75)'); c.fillStyle = g; c.fillRect(0, H - 700, W, 700);
    }
    const ANOS = /^pt/i.test(spec.idioma || '') ? 'ANOS' : (/^es/i.test(spec.idioma || '') ? 'AÑOS' : 'YEARS');
    function quadro(t) {
      const { i, k, local } = U.cenaEm(spec, t), cn = cenas[i];
      // a camera desce do marco anterior ao atual no primeiro terco da cena
      const q = U.suave(U.clamp(local / Math.min(1.1, (spec.cenas[i].fim - spec.cenas[i].ini) * 0.4), 0, 1));
      const yCam = i ? U.lerp(Y[i - 1], Y[i], q) : 0, zoom = cn.acao === 'zoom' ? 1 + 0.12 * U.suave(k) : 1;
      const anoAgora = i ? U.lerp(cenas[i - 1].ano, cn.ano, cn.acao === 'salto' ? U.saida(q) : q) : cn.ano;
      fundo(t, cenas.length > 1 ? (anoAgora - cenas[0].ano) / Math.max(1, cenas[cenas.length - 1].ano - cenas[0].ano) : 0);
      cidade(anoAgora, yCam);
      const Y0 = H * 0.45;   // onde o marco atual fica na tela
      c.save(); c.translate(W / 2, Y0); c.scale(zoom, zoom); c.translate(-W / 2, -yCam);   // o marco em yCam cai em Y0
      // a trilha e as marcas de ano entre os marcos
      c.lineCap = 'round'; c.strokeStyle = 'rgba(255,255,255,0.18)'; c.lineWidth = 16; c.beginPath(); c.moveTo(X, -2000); c.lineTo(X, Y[Y.length - 1] + 3000); c.stroke();
      const feito = yCam; c.strokeStyle = '#FFD166'; c.lineWidth = 16; c.beginPath(); c.moveTo(X, -2000); c.lineTo(X, feito); c.stroke();
      for (let j = 0; j + 1 < cenas.length; j++) {
        const a0 = cenas[j].ano, a1 = cenas[j + 1].ano, passo = [1, 5, 10, 25, 50, 100, 500, 1000].find((p) => Math.abs(a1 - a0) / p <= 8) || 1000;
        for (let a = Math.ceil(a0 / passo) * passo; a < a1; a += passo) { if (a === a0) continue; const y = U.lerp(Y[j], Y[j + 1], (a - a0) / (a1 - a0));
          c.fillStyle = 'rgba(255,255,255,0.35)'; c.fillRect(X - 26, y - 3, 52, 6); c.font = '34px "Oswald", sans-serif'; c.textAlign = 'right'; c.textBaseline = 'middle'; c.fillText(anoTxt(a), X - 40, y); }
      }
      // os marcos: os que ja passaram apagados, o atual aceso e entrando
      cenas.forEach((m, j) => {
        if (j > i) return;
        const chega = i ? Math.min(1.1, (spec.cenas[i].fim - spec.cenas[i].ini) * 0.4) * 0.75 : 0;
        const atual = j === i, ent = atual ? U.mola(local - 0.1 - chega, 10) : 1, y = Y[j];
        // o que ja passou apaga enquanto sobe (nao briga com o contador do ano)
        const yTela = (y - yCam) * zoom + Y0, alfa = atual ? 1 : U.clamp((yTela - 420) / 320, 0, 0.4);
        if (alfa <= 0.01) return;
        c.save(); c.globalAlpha = alfa;
        c.beginPath(); c.arc(X, y, atual ? 38 + 4 * Math.sin(t * 5) : 26, 0, U.TAU); c.fillStyle = m.cor; c.fill(); c.lineWidth = 8; c.strokeStyle = '#FFFFFF'; c.stroke();
        if (ent > 0) {
          const bx = X + 70, bw = W - bx - 120, bh = 380;
          c.translate(bx + (1 - Math.min(1, ent)) * 300, y - bh / 2);
          U.rr(c, 0, 0, bw, bh, 30); c.fillStyle = 'rgba(255,255,255,0.96)'; c.fill(); c.fillStyle = m.cor; U.rr(c, 0, 0, 22, bh, 11); c.fill();
          c.beginPath(); c.arc(140, bh / 2, 104, 0, U.TAU); c.fillStyle = m.cor; c.fill();
          c.save(); c.translate(140, bh / 2 + (atual ? Math.sin(t * 3) * 4 : 0)); c.scale(70, 70); c.fillStyle = '#FFFFFF'; c.strokeStyle = '#FFFFFF'; ICONES[m.icone](c); c.restore();
          c.fillStyle = '#16202C'; c.textAlign = 'left'; c.textBaseline = 'top'; c.font = '104px "Lilita One", sans-serif'; { const lw = c.measureText(anoTxt(m.ano)).width; if (lw > bw - 290) c.font = Math.floor(104 * (bw - 290) / lw) + 'px "Lilita One", sans-serif'; } c.fillText(anoTxt(m.ano), 270, 40);
          c.font = '54px "Lilita One", sans-serif';
          const texto = U.textoAjustado(c, String(spec.cenas[j].evento || m.evento).toUpperCase(), bw - 300, 190, 30);
          texto.linhas.forEach((l, n) => c.fillText(l, 270, 168 + n * texto.lh));
        }
        c.restore();
      });
      // "+83 ANOS": o intervalo entre o marco anterior e este, no meio da trilha
      if (i > 0) { const gap = Math.round(Math.abs(cn.ano - cenas[i - 1].ano)), yG = (Y[i - 1] + Y[i]) / 2, s = U.clamp(U.mola(local - 0.05, 9), 0, 1.3) * (1 - U.clamp((local - 1.6) / .3, 0, 1));
        if (gap > 0 && s > 0.01) { c.save(); c.translate(X + 40, yG); c.scale(s, s); c.font = '78px "Lilita One", sans-serif'; c.textAlign = 'left'; c.textBaseline = 'middle';
          const tx = '+' + gap.toLocaleString('en-US') + ' ' + (gap === 1 ? ANOS.replace(/S$/, '').replace('AÑO', 'AÑO') : ANOS), w = c.measureText(tx).width + 70; U.rr(c, 0, -62, w, 124, 62); c.fillStyle = '#FF6B6B'; c.fill(); c.lineWidth = 8; c.strokeStyle = '#FFFFFF'; c.stroke(); c.fillStyle = '#FFFFFF'; c.fillText(tx, 35, 6); c.restore(); } }
      c.restore();
      // o contador do ano no topo (corre entre os marcos)
      { const txt = anoTxt(anoAgora), s = 1 + 0.06 * Math.sin(Math.min(1, q) * Math.PI);
        const yA = U.lerp(560, 330, U.suave(U.clamp((t - 3.0) / 0.5, 0, 1)));
        c.save(); c.translate(W / 2, yA); c.scale(s, s); c.font = '150px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        { const lw = c.measureText(txt).width; if (lw > W * 0.9) c.font = Math.floor(150 * (W * 0.9) / lw) + 'px "Lilita One", sans-serif'; }   // 23/10: "450,000,000 BC" saia cortado
        c.lineWidth = 18; c.strokeStyle = '#000000'; c.strokeText(txt, 0, 0); c.fillStyle = '#FFD166'; c.fillText(txt, 0, 0); c.restore(); }
      const fimDesce = i ? Math.min(1.1, (spec.cenas[i].fim - spec.cenas[i].ini) * 0.4) : 0;
      if (cn.hud && typeof cn.hud !== 'object' && local > fimDesce + 0.1) { const s = U.mola(local - fimDesce - 0.1, 10); c.save(); c.translate(W / 2, H * 0.62); c.scale(s, s);
        c.font = '100px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; const tx = U.hud(c, cn.hud, c.canvas.width * 0.84 - 70, 22), w = c.measureText(tx).width + 70;
        U.rr(c, -w / 2, -66, w, 132, 30); c.fillStyle = '#FFD166'; c.fill(); c.fillStyle = '#16202C'; c.fillText(tx, 0, 6); c.restore(); }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 150, fundo: '#FFD166', borda: '#16202C', cor: '#16202C', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '100px "Lilita One", sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#FFD166', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro };
  }
  MOTORES.linha_tempo = { criar };
  window.ICONES_LINHA_TEMPO = Object.keys(ICONES);
})();
