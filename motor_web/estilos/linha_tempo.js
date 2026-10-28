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

    function quadro(t) {
      const { i, k, local } = U.cenaEm(spec, t), cn = cenas[i];
      // a camera desce do marco anterior ao atual no primeiro terco da cena
      const q = U.suave(U.clamp(local / Math.min(1.1, (spec.cenas[i].fim - spec.cenas[i].ini) * 0.4), 0, 1));
      const yCam = i ? U.lerp(Y[i - 1], Y[i], q) : 0, zoom = cn.acao === 'zoom' ? 1 + 0.12 * U.suave(k) : 1;
      const anoAgora = i ? U.lerp(cenas[i - 1].ano, cn.ano, cn.acao === 'salto' ? U.saida(q) : q) : cn.ano;
      fundo(t, cenas.length > 1 ? (anoAgora - cenas[0].ano) / Math.max(1, cenas[cenas.length - 1].ano - cenas[0].ano) : 0);
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
        const atual = j === i, ent = atual ? U.mola(local - 0.1, 10) : 1, y = Y[j];
        // o que ja passou apaga enquanto sobe (nao briga com o contador do ano)
        const yTela = (y - yCam) * zoom + Y0, alfa = atual ? 1 : U.clamp((yTela - 420) / 320, 0, 0.4);
        if (alfa <= 0.01) return;
        c.save(); c.globalAlpha = alfa;
        c.beginPath(); c.arc(X, y, atual ? 38 + 4 * Math.sin(t * 5) : 26, 0, U.TAU); c.fillStyle = m.cor; c.fill(); c.lineWidth = 8; c.strokeStyle = '#FFFFFF'; c.stroke();
        if (ent > 0) {
          const bx = X + 80, bw = W - bx - 150, bh = 300;
          c.translate(bx + (1 - Math.min(1, ent)) * 300, y - bh / 2);
          U.rr(c, 0, 0, bw, bh, 30); c.fillStyle = 'rgba(255,255,255,0.96)'; c.fill(); c.fillStyle = m.cor; U.rr(c, 0, 0, 22, bh, 11); c.fill();
          c.save(); c.translate(105, bh / 2); c.scale(62, 62); c.fillStyle = m.cor; c.strokeStyle = m.cor; ICONES[m.icone](c); c.restore();
          c.fillStyle = '#16202C'; c.textAlign = 'left'; c.textBaseline = 'top'; c.font = '86px "Lilita One", sans-serif'; { const lw = c.measureText(anoTxt(m.ano)).width; if (lw > bw - 220) c.font = Math.floor(86 * (bw - 220) / lw) + 'px "Lilita One", sans-serif'; } c.fillText(anoTxt(m.ano), 190, 34);
          c.font = '46px "Lilita One", sans-serif'; U.linhas(c, m.evento.toUpperCase(), bw - 220).slice(0, 2).forEach((l, n) => c.fillText(l, 190, 140 + n * 54));
        }
        c.restore();
      });
      c.restore();
      // o contador do ano no topo (corre entre os marcos)
      { const txt = anoTxt(anoAgora), s = 1 + 0.06 * Math.sin(Math.min(1, q) * Math.PI);
        const yA = U.lerp(560, 330, U.suave(U.clamp((t - 3.0) / 0.5, 0, 1)));
        c.save(); c.translate(W / 2, yA); c.scale(s, s); c.font = '150px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        { const lw = c.measureText(txt).width; if (lw > W * 0.9) c.font = Math.floor(150 * (W * 0.9) / lw) + 'px "Lilita One", sans-serif'; }   // 23/10: "450,000,000 BC" saia cortado
        c.lineWidth = 18; c.strokeStyle = '#000000'; c.strokeText(txt, 0, 0); c.fillStyle = '#FFD166'; c.fillText(txt, 0, 0); c.restore(); }
      if (cn.hud && typeof cn.hud !== 'object' && local > 0.2) { const s = U.mola(local - 0.2, 10); c.save(); c.translate(W / 2, H * 0.6); c.scale(s, s);
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
