// ENEM -- "isso cai no ENEM" em 40 s (23/10, canal CAI NO ENEM; um nicho e um
// motor por canal). Uma LOUSA de giz: cada cena apaga a anterior com o
// apagador e escreve a nova a giz -- pergunta, fato com desenho, formula,
// esquema (cadeia ou ciclo), numero que conta, alternativas A-E com a certa
// circulada, e o carimbo "JA CAIU NO ENEM <ano>". A etiqueta da AREA da prova
// (natureza, humanas, matematica, linguagens) fica no canto da lousa.
//
//   cena: { texto (narracao), acao: "pergunta|fato|formula|esquema|numero|alternativas|carimbo",
//           area: "natureza|humanas|matematica|linguagens", lousa: str curto (o que se escreve),
//           icone: um de ICONES (fato), formula: str (formula),
//           itens: [str] 2-4 + esquema: "cadeia|ciclo" (esquema),
//           numero: num + unidade: str (numero), alternativas: [5 str] + correta: 0-4,
//           ano: 2009..2026 (carimbo), hud: str curto }
//
// CONTRATO (comum.js): `quadro(t)` sem estado entre quadros.
(function () {
  'use strict';
  const GIZ = '#F4F1E6', AMARELO = '#FFE066', ROSA = '#FF8FA3', AZUL = '#8FD3FF', VERDE = '#B8F5A0';
  const AREAS = {
    natureza: { nome: 'CIÊNCIAS DA NATUREZA', cor: '#5CD68A' },
    humanas: { nome: 'CIÊNCIAS HUMANAS', cor: '#FFB547' },
    matematica: { nome: 'MATEMÁTICA', cor: '#6EC1FF' },
    linguagens: { nome: 'LINGUAGENS', cor: '#FF7FA8' },
  };
  // desenhos a giz (so contorno), num quadrado de -1..1
  const ICONES = {
    folha(c) { c.beginPath(); c.moveTo(-0.8, 0.8); c.quadraticCurveTo(-0.9, -0.7, 0.8, -0.8); c.quadraticCurveTo(0.7, 0.9, -0.8, 0.8); c.moveTo(-0.8, 0.8); c.lineTo(0.5, -0.5); c.stroke(); },
    atomo(c) { [0, 1, 2].forEach((i) => { c.beginPath(); c.ellipse(0, 0, 0.95, 0.35, (i * Math.PI) / 3, 0, Math.PI * 2); c.stroke(); }); c.beginPath(); c.arc(0, 0, 0.14, 0, Math.PI * 2); c.fill(); },
    dna(c) { c.beginPath(); for (let y = -1; y <= 1.001; y += 0.05) c.lineTo(Math.sin(y * 4) * 0.5, y); c.stroke(); c.beginPath(); for (let y = -1; y <= 1.001; y += 0.05) c.lineTo(-Math.sin(y * 4) * 0.5, y); c.stroke();
      for (let y = -0.9; y < 1; y += 0.25) { c.beginPath(); c.moveTo(Math.sin(y * 4) * 0.5, y); c.lineTo(-Math.sin(y * 4) * 0.5, y); c.stroke(); } },
    globo(c) { c.beginPath(); c.arc(0, 0, 0.9, 0, Math.PI * 2); c.stroke(); c.beginPath(); c.ellipse(0, 0, 0.4, 0.9, 0, 0, Math.PI * 2); c.moveTo(-0.9, 0); c.lineTo(0.9, 0); c.moveTo(-0.78, -0.45); c.lineTo(0.78, -0.45); c.moveTo(-0.78, 0.45); c.lineTo(0.78, 0.45); c.stroke(); },
    livro(c) { c.beginPath(); c.moveTo(0, -0.6); c.quadraticCurveTo(-0.5, -0.85, -0.95, -0.6); c.lineTo(-0.95, 0.75); c.quadraticCurveTo(-0.5, 0.5, 0, 0.75); c.quadraticCurveTo(0.5, 0.5, 0.95, 0.75); c.lineTo(0.95, -0.6); c.quadraticCurveTo(0.5, -0.85, 0, -0.6); c.lineTo(0, 0.75); c.stroke(); },
    raio(c) { c.beginPath(); c.moveTo(0.2, -1); c.lineTo(-0.5, 0.1); c.lineTo(0, 0.1); c.lineTo(-0.2, 1); c.lineTo(0.55, -0.2); c.lineTo(0.05, -0.2); c.closePath(); c.stroke(); },
    gota(c) { c.beginPath(); c.moveTo(0, -1); c.bezierCurveTo(0.2, -0.5, 0.75, 0, 0.7, 0.35); c.arc(0, 0.35, 0.7, 0, Math.PI); c.bezierCurveTo(-0.75, 0, -0.2, -0.5, 0, -1); c.stroke(); },
    sol(c) { c.beginPath(); c.arc(0, 0, 0.45, 0, Math.PI * 2); c.stroke(); for (let i = 0; i < 10; i++) { const a = (i / 10) * Math.PI * 2; c.beginPath(); c.moveTo(Math.cos(a) * 0.62, Math.sin(a) * 0.62); c.lineTo(Math.cos(a) * 0.95, Math.sin(a) * 0.95); c.stroke(); } },
    balanca(c) { c.beginPath(); c.moveTo(0, -0.9); c.lineTo(0, 0.8); c.moveTo(-0.5, 0.8); c.lineTo(0.5, 0.8); c.moveTo(-0.85, -0.6); c.lineTo(0.85, -0.6); c.stroke();
      [-0.85, 0.85].forEach((x) => { c.beginPath(); c.moveTo(x, -0.6); c.lineTo(x - 0.3, 0.1); c.lineTo(x + 0.3, 0.1); c.closePath(); c.stroke(); }); },
    coroa(c) { c.beginPath(); c.moveTo(-0.9, 0.6); c.lineTo(-0.9, -0.5); c.lineTo(-0.45, 0); c.lineTo(0, -0.75); c.lineTo(0.45, 0); c.lineTo(0.9, -0.5); c.lineTo(0.9, 0.6); c.closePath(); c.stroke(); },
    celula(c) { c.beginPath(); c.ellipse(0, 0, 0.95, 0.75, 0.2, 0, Math.PI * 2); c.stroke(); c.beginPath(); c.arc(0.1, 0, 0.28, 0, Math.PI * 2); c.stroke(); c.beginPath(); c.arc(0.1, 0, 0.1, 0, Math.PI * 2); c.fill();
      c.beginPath(); c.ellipse(-0.5, 0.3, 0.2, 0.09, 0.5, 0, Math.PI * 2); c.stroke(); c.beginPath(); c.ellipse(0.55, -0.35, 0.18, 0.08, -0.4, 0, Math.PI * 2); c.stroke(); },
    engrenagem(c) { c.beginPath(); for (let i = 0; i < 24; i++) { const a = (i / 24) * Math.PI * 2, r = i % 3 === 0 ? 0.95 : 0.75; c.lineTo(Math.cos(a) * r, Math.sin(a) * r); } c.closePath(); c.stroke(); c.beginPath(); c.arc(0, 0, 0.3, 0, Math.PI * 2); c.stroke(); },
    lupa(c) { c.beginPath(); c.arc(-0.2, -0.2, 0.6, 0, Math.PI * 2); c.stroke(); c.beginPath(); c.moveTo(0.23, 0.23); c.lineTo(0.9, 0.9); c.stroke(); },
    grafico(c) { c.beginPath(); c.moveTo(-0.9, -0.9); c.lineTo(-0.9, 0.9); c.lineTo(0.9, 0.9); c.stroke(); c.beginPath(); c.moveTo(-0.7, 0.5); c.lineTo(-0.3, 0.1); c.lineTo(0.1, 0.3); c.lineTo(0.7, -0.6); c.stroke(); },
    fabrica(c) { c.beginPath(); c.moveTo(-0.95, 0.9); c.lineTo(-0.95, -0.1); c.lineTo(-0.45, 0.2); c.lineTo(-0.45, -0.1); c.lineTo(0.05, 0.2); c.lineTo(0.05, -0.8); c.lineTo(0.35, -0.8); c.lineTo(0.35, 0.2); c.lineTo(0.95, 0.2); c.lineTo(0.95, 0.9); c.closePath(); c.stroke(); },
  };

  function criar(tela, spec, U) {
    const c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const FONTE = '"Patrick Hand", "Lilita One", sans-serif';
    const BX = 70, BY = 330, BW = W - 140 - 60, BH = 1010;   // a lousa; 60 px a mais livres na direita (botoes do app)
    const IX = BX + 60, IW = BW - 120, IY = BY + 120, IH = BH - 220;   // area util dentro da lousa
    const lim = (s, n) => String(s == null ? '' : s).slice(0, n);
    const cenas = spec.cenas.map((cn, i) => {
      const area = AREAS[cn.area] ? cn.area : (i ? null : 'natureza');
      const alts = Array.isArray(cn.alternativas) ? cn.alternativas.slice(0, 5).map((a) => lim(a, 40)) : [];
      return { acao: cn.acao || 'fato', area, lousa: lim(cn.lousa || '', 90), icone: ICONES[cn.icone] ? cn.icone : null,
        formula: lim(cn.formula || '', 40), itens: (Array.isArray(cn.itens) ? cn.itens : []).slice(0, 4).map((x) => lim(x, 22)),
        esquema: cn.esquema === 'ciclo' ? 'ciclo' : 'cadeia', numero: Number(cn.numero), unidade: lim(cn.unidade || '', 24),
        alternativas: alts, correta: U.clamp(Math.round(Number(cn.correta) || 0), 0, Math.max(0, alts.length - 1)),
        ano: Number.isFinite(Number(cn.ano)) ? Math.round(Number(cn.ano)) : null, hud: cn.hud };
    });
    cenas.forEach((cn, i) => { if (!cn.area) cn.area = cenas[i - 1].area; });

    // ---------- giz ----------
    function giz(txt, x, y, px, cor, alinh) {
      c.font = `${px}px ${FONTE}`; c.textAlign = alinh || 'center'; c.textBaseline = 'middle';
      c.fillStyle = cor || GIZ; c.globalAlpha *= 0.35; c.fillText(txt, x + 2, y + 2); c.globalAlpha /= 0.35;
      c.fillText(txt, x, y);
    }
    // escreve da esquerda para a direita: k 0..1 revela o texto
    function escrever(linhas, cx, y0, px, lh, k, cor) {
      const total = linhas.reduce((s, l) => s + l.length, 0) || 1; let feito = 0;
      linhas.forEach((l, n) => {
        const frac = U.clamp((k * total - feito) / Math.max(1, l.length), 0, 1); feito += l.length;
        if (frac <= 0) return;
        c.font = `${px}px ${FONTE}`; const w = c.measureText(l).width, y = y0 + n * lh;
        c.save(); c.beginPath(); c.rect(cx - w / 2 - 10, y - lh, (w + 20) * frac, lh * 2); c.clip(); giz(l, cx, y, px, cor); c.restore();
        if (frac < 1) { c.save(); c.fillStyle = '#FFFFFF'; c.beginPath(); c.arc(cx - w / 2 + w * frac, y + px * 0.25, 7, 0, U.TAU); c.fill(); c.restore(); }
      });
    }
    function quebra(txt, px, max, n) { c.font = `${px}px ${FONTE}`; return U.linhas(c, txt, max).slice(0, n || 4); }
    function rabisco(x0, x1, y, k, cor) {   // sublinhado a giz que corre
      if (k <= 0) return; c.save(); c.strokeStyle = cor || AMARELO; c.lineWidth = 9; c.lineCap = 'round'; c.beginPath();
      const x = U.lerp(x0, x1, U.clamp(k, 0, 1)); for (let xx = x0; xx <= x; xx += 12) c.lineTo(xx, y + Math.sin(xx * 0.05) * 4); c.stroke(); c.restore();
    }
    function seta(x0, y0, x1, y1, k, cor) {
      if (k <= 0) return; const x = U.lerp(x0, x1, k), y = U.lerp(y0, y1, k), a = Math.atan2(y1 - y0, x1 - x0);
      c.save(); c.strokeStyle = cor || GIZ; c.lineWidth = 8; c.lineCap = 'round'; c.beginPath(); c.moveTo(x0, y0); c.lineTo(x, y); c.stroke();
      if (k > 0.85) { c.beginPath(); c.moveTo(x, y); c.lineTo(x - 34 * Math.cos(a - 0.5), y - 34 * Math.sin(a - 0.5)); c.moveTo(x, y); c.lineTo(x - 34 * Math.cos(a + 0.5), y - 34 * Math.sin(a + 0.5)); c.stroke(); }
      c.restore();
    }
    function caixaGiz(x, y, w, h, k, cor) {   // retangulo desenhado em volta (perimetro revelado)
      const per = 2 * (w + h), feito = per * U.clamp(k, 0, 1);
      c.save(); c.strokeStyle = cor || GIZ; c.lineWidth = 7; c.lineJoin = 'round'; c.beginPath(); c.moveTo(x, y);
      const lados = [[w, 0], [0, h], [-w, 0], [0, -h]]; let px = x, py = y, resta = feito;
      for (const [dx, dy] of lados) { const L = Math.abs(dx) + Math.abs(dy), f = Math.min(1, resta / L); px += dx * f; py += dy * f; c.lineTo(px, py); resta -= L; if (resta <= 0) break; }
      c.stroke(); c.restore();
    }

    // ---------- cenario fixo ----------
    function pintarFundo(c) {
      const g = c.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#1A2620'); g.addColorStop(1, '#0E1612'); c.fillStyle = g; c.fillRect(0, 0, W, H);
      // moldura de madeira e a lousa
      U.rr(c, BX - 26, BY - 26, BW + 52, BH + 52, 22); c.fillStyle = '#7A4E25'; c.fill();
      U.rr(c, BX - 26, BY - 26, BW + 52, BH + 52, 22); c.lineWidth = 6; c.strokeStyle = '#5A3818'; c.stroke();
      const lg = c.createRadialGradient(BX + BW * 0.4, BY + BH * 0.35, 80, BX + BW / 2, BY + BH / 2, BH * 0.9);
      lg.addColorStop(0, '#2F6A4E'); lg.addColorStop(1, '#1E4835'); c.fillStyle = lg; c.fillRect(BX, BY, BW, BH);
      // manchas de giz apagado (fixas: a lousa e' sempre a mesma)
      const r = U.rng(11); c.save(); c.beginPath(); c.rect(BX, BY, BW, BH); c.clip();
      for (let i = 0; i < 26; i++) { c.globalAlpha = 0.035 + r() * 0.04; c.fillStyle = '#FFFFFF'; c.beginPath(); c.ellipse(BX + r() * BW, BY + r() * BH, 60 + r() * 220, 20 + r() * 60, r() * 3, 0, U.TAU); c.fill(); }
      c.restore(); c.globalAlpha = 1;
      // o apoio do giz e o giz
      c.fillStyle = '#5A3818'; c.fillRect(BX + 40, BY + BH + 26, BW - 80, 22);
      c.fillStyle = '#F4F1E6'; c.fillRect(BX + 120, BY + BH + 14, 70, 16); c.fillStyle = AMARELO; c.fillRect(BX + 220, BY + BH + 14, 56, 16);
    }
    const fundoFixo = U.camada(W,H,pintarFundo);
    function fundo() { c.drawImage(fundoFixo,0,0); }
    function etiquetaArea(cn, local) {
      const a = AREAS[cn.area], s = U.clamp(U.mola(local, 9), 0, 1.2);
      c.save(); c.translate(BX + 30, BY + 30); c.scale(s, s);
      c.font = `46px ${FONTE}`; const w = c.measureText(a.nome).width + 50;
      U.rr(c, 0, 0, w, 66, 33); c.fillStyle = a.cor; c.fill(); c.fillStyle = '#10241A'; c.textAlign = 'left'; c.textBaseline = 'middle'; c.fillText(a.nome, 25, 36);
      c.restore();
    }
    function marca() {   // o selo do canal no pe da moldura
      c.save(); c.translate(BX + BW - 150, BY + BH + 4); c.rotate(-0.04);
      U.rr(c, -120, -34, 240, 68, 12); c.fillStyle = '#C8102E'; c.fill(); c.lineWidth = 4; c.strokeStyle = '#FFE066'; c.stroke();
      c.font = '40px "Lilita One", sans-serif'; c.fillStyle = '#FFFFFF'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('CAI NO ENEM', 0, 3); c.restore();
    }

    // ---------- as acoes ----------
    const DESENHA = {
      pergunta(cn, k, local) {
        const ls = quebra(cn.lousa || '?', 96, IW - 160, 4), lh = 112, y0 = IY + IH / 2 - ((ls.length - 1) * lh) / 2 - 40;
        escrever(ls, IX + IW / 2 - 50, y0, 96, lh, U.saida(k / 0.6));
        const s = U.mola(local - 0.5, 8); if (s > 0) { c.save(); c.translate(IX + IW - 60, IY + IH * 0.62); c.rotate(0.15 * Math.sin(local * 3)); c.scale(s, s); giz('?', 0, 0, 300, AMARELO); c.restore(); }
      },
      fato(cn, k) {
        let y = IY + 40;
        if (cn.icone) { const s = U.saida(k / 0.3); c.save(); c.translate(IX + IW / 2, IY + 170); c.scale(150 * s, 150 * s); c.strokeStyle = VERDE; c.fillStyle = VERDE; c.lineWidth = 0.06; c.lineCap = 'round'; c.lineJoin = 'round'; ICONES[cn.icone](c); c.restore(); y = IY + 400; }
        const ls = quebra(cn.lousa, 84, IW, cn.icone ? 4 : 5), lh = 98;
        if (!cn.icone) y = IY + IH / 2 - ((ls.length - 1) * lh) / 2;
        escrever(ls, IX + IW / 2, y, 84, lh, U.clamp((k - 0.15) / 0.55, 0, 1));
        c.font = `84px ${FONTE}`; const w = Math.max(...ls.map((l) => c.measureText(l).width), 10);
        rabisco(IX + IW / 2 - w / 2, IX + IW / 2 + w / 2, y + (ls.length - 1) * lh + 58, (k - 0.72) / 0.2);
      },
      formula(cn, k) {
        let px = 104; c.font = `${px}px ${FONTE}`; while (px > 54 && c.measureText(cn.formula).width > IW) { px -= 6; c.font = `${px}px ${FONTE}`; }
        const yF = IY + IH * 0.36; escrever([cn.formula || '?'], IX + IW / 2, yF, px, 120, U.clamp(k / 0.45, 0, 1), AZUL);
        const w = c.measureText(cn.formula).width;
        caixaGiz(IX + IW / 2 - w / 2 - 30, yF - px * 0.8, w + 60, px * 1.6, (k - 0.45) / 0.2, AMARELO);
        if (cn.lousa) { seta(IX + IW / 2, yF + px * 0.9, IX + IW / 2, yF + px * 0.9 + 120, (k - 0.6) / 0.12, AMARELO);
          escrever(quebra(cn.lousa, 70, IW, 3), IX + IW / 2, yF + px * 0.9 + 200, 70, 84, U.clamp((k - 0.68) / 0.3, 0, 1)); }
      },
      esquema(cn, k) {
        const it = cn.itens.length >= 2 ? cn.itens : [cn.lousa || '?', '?'], n = it.length;
        const pos = cn.esquema === 'ciclo'
          ? it.map((_, j) => { const a = -Math.PI / 2 + (j / n) * U.TAU; return [IX + IW / 2 + Math.cos(a) * IW * 0.3, IY + IH / 2 + Math.sin(a) * IH * 0.33]; })
          : it.map((_, j) => [IX + IW / 2, IY + 60 + (j + 0.5) * ((IH - 60) / n)]);
        const bw = cn.esquema === 'ciclo' ? 380 : 620, bh = 120;
        it.forEach((txt, j) => {
          const kk = U.clamp(k * n * 1.15 - j * 1.0, 0, 1); if (kk <= 0) return;
          const [x, y] = pos[j]; caixaGiz(x - bw / 2, y - bh / 2, bw, bh, kk * 1.6, AREAS[cn.area].cor);
          c.font = `${cn.esquema === 'ciclo' ? 54 : 62}px ${FONTE}`; let t2 = txt; while (c.measureText(t2).width > bw - 30 && t2.length > 4) t2 = t2.slice(0, -1);
          escrever([t2], x, y, cn.esquema === 'ciclo' ? 54 : 62, 70, U.clamp(kk * 1.5 - 0.4, 0, 1));
          const prox = cn.esquema === 'ciclo' ? (j + 1) % n : j + 1; if (prox >= n || (cn.esquema !== 'ciclo' && j === n - 1)) return;
          const [x2, y2] = pos[prox], ks = U.clamp(k * n * 1.15 - j * 1.0 - 0.9, 0, 1);
          const enc = (x1, y1, xa, ya, d) => { const L = Math.hypot(xa - x1, ya - y1) || 1; return [x1 + ((xa - x1) / L) * d, y1 + ((ya - y1) / L) * d]; };
          const d0 = cn.esquema === 'ciclo' ? 130 : bh / 2 + 10, [ax, ay] = enc(x, y, x2, y2, d0), [bx2, by2] = enc(x2, y2, x, y, d0);
          seta(ax, ay, bx2, by2, ks, GIZ);
        });
      },
      numero(cn, k) {
        if (cn.lousa) escrever(quebra(cn.lousa, 70, IW, 2), IX + IW / 2, IY + 70, 70, 84, U.clamp(k / 0.25, 0, 1));
        const alvo = Number.isFinite(cn.numero) ? cn.numero : 0, v = alvo * U.saida(U.clamp((k - 0.15) / 0.55, 0, 1));
        const dec = Math.abs(alvo) < 10 && alvo % 1 ? 1 : 0;
        const txt = v.toLocaleString('pt-BR', { minimumFractionDigits: dec, maximumFractionDigits: dec });
        let px = 240; c.font = `${px}px ${FONTE}`; while (px > 100 && c.measureText(txt).width > IW) { px -= 10; c.font = `${px}px ${FONTE}`; }
        const s = 1 + 0.08 * Math.sin(U.clamp((k - 0.7) / 0.15, 0, 1) * Math.PI);
        c.save(); c.translate(IX + IW / 2, IY + IH * 0.52); c.scale(s, s); giz(txt, 0, 0, px, AMARELO); c.restore();
        if (cn.unidade) escrever([cn.unidade], IX + IW / 2, IY + IH * 0.52 + px * 0.7, 78, 90, U.clamp((k - 0.6) / 0.2, 0, 1));
      },
      alternativas(cn, k) {
        const al = cn.alternativas.length ? cn.alternativas : ['?', '?', '?', '?', '?'], L = 'ABCDE', lh = Math.min(150, (IH - (cn.lousa ? 150 : 0)) / al.length);
        let y0 = IY + 40; if (cn.lousa) { escrever(quebra(cn.lousa, 64, IW, 2), IX + IW / 2, IY + 30, 64, 74, U.clamp(k / 0.2, 0, 1)); y0 = IY + 180; }
        const revela = U.clamp((k - 0.68) / 0.12, 0, 1);
        al.forEach((a, j) => {
          const kk = U.clamp((k - 0.12 - j * 0.09) / 0.12, 0, 1); if (kk <= 0) return;
          const y = y0 + j * lh + lh / 2, certa = j === cn.correta;
          c.save(); c.globalAlpha = revela > 0 && !certa ? 1 - 0.6 * revela : 1;
          c.font = `64px ${FONTE}`; let t2 = a; while (c.measureText(t2).width > IW - 160 && t2.length > 4) t2 = t2.slice(0, -1);
          giz(L[j] + ')', IX + 40, y, 70, certa && revela ? AMARELO : GIZ, 'left');
          c.save(); c.beginPath(); c.rect(IX + 120, y - 60, (IW - 120) * kk, 120); c.clip(); giz(t2, IX + 130, y, 64, certa && revela ? AMARELO : GIZ, 'left'); c.restore();
          c.restore();
          if (certa && revela > 0) { c.save(); c.strokeStyle = AMARELO; c.lineWidth = 9; c.beginPath(); c.ellipse(IX + 62, y, 62, 56, 0, -Math.PI / 2, -Math.PI / 2 + U.TAU * revela); c.stroke(); c.restore(); }
        });
      },
      carimbo(cn, k, local) {
        if (cn.lousa) escrever(quebra(cn.lousa, 80, IW, 3), IX + IW / 2, IY + 90, 80, 94, U.clamp(k / 0.35, 0, 1));
        const s = U.mola(local - 0.6, 9); if (s <= 0) return;
        c.save(); c.translate(IX + IW / 2, IY + IH * 0.62); c.rotate(-0.12); c.scale(2.2 - 1.2 * Math.min(1, s), 2.2 - 1.2 * Math.min(1, s)); c.globalAlpha = Math.min(1, s * 1.4);
        c.strokeStyle = ROSA; c.lineWidth = 14; U.rr(c, -330, -150, 660, 300, 26); c.stroke(); U.rr(c, -310, -130, 620, 260, 18); c.lineWidth = 5; c.stroke();
        c.fillStyle = ROSA; c.font = '96px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('JÁ CAIU', 0, -45);
        c.font = '84px "Lilita One", sans-serif'; c.fillText(cn.ano ? 'NO ENEM ' + cn.ano : 'NO ENEM', 0, 60); c.restore();
      },
    };

    function quadro(t) {
      const { i, k, local } = U.cenaEm(spec, t), cn = cenas[i];
      fundo(t);
      c.save(); c.beginPath(); c.rect(BX, BY, BW, BH); c.clip();
      // o apagador: nos primeiros 0,35 s a cena anterior some atras de uma faixa
      const ap = i > 0 ? U.clamp(local / 0.35, 0, 1) : 1;
      if (ap < 1) {
        (DESENHA[cenas[i - 1].acao] || DESENHA.fato)(cenas[i - 1], 1, 9);
        const xa = BX - 200 + (BW + 400) * ap;
        c.fillStyle = '#28593F'; c.fillRect(BX, BY, xa - BX, BH);
        c.save(); c.translate(xa, BY + BH * 0.45); c.rotate(-0.1); U.rr(c, -70, -230, 140, 460, 18); c.fillStyle = '#3B3B48'; c.fill(); c.fillStyle = '#C9A46A'; c.fillRect(-70, -230, 50, 460); c.restore();
      } else (DESENHA[cn.acao] || DESENHA.fato)(cn, k, local);
      c.restore();
      etiquetaArea(cn, i && cenas[i - 1].area === cn.area ? 9 : local);
      marca();
      if (cn.hud && typeof cn.hud !== 'object' && local > 0.4) { const s = U.mola(local - 0.4, 10); c.save(); c.translate(W / 2 - 30, BY + BH - 70); c.scale(s, s);
        c.font = '64px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; const tx = U.hud(c, cn.hud, BW - 200, 22), w = c.measureText(tx).width + 60;
        U.rr(c, -w / 2, -46, w, 92, 24); c.fillStyle = AMARELO; c.fill(); c.fillStyle = '#16202C'; c.fillText(tx, 0, 4); c.restore(); }
      U.cartaz(c, spec, t, { fonte: '80px "Lilita One", sans-serif', y: 110, fundo: '#FFE066', borda: '#16202C', cor: '#16202C', altura_linha: 96, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '96px "Lilita One", sans-serif', y: H * 0.79, cor: '#FFFFFF', cor_ativa: '#FFE066', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro };
  }
  MOTORES.enem = { criar };
  window.ICONES_ENEM = Object.keys(ICONES);
})();
