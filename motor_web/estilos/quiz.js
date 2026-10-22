// QUIZ -- "ache o diferente" (22/10, ordem do dono: um nicho e um motor por
// canal). Uma grade de caracteres iguais com UM diferente; cronometro; no fim
// do tempo, o diferente e' circulado. Cada cena e' um nivel, cada vez mais
// dificil (grade maior, par mais parecido, menos tempo). O espectador comenta
// em que nivel parou -- e' o que o formato vende.
//
// cena: { texto (rotulo do nivel: "LEVEL 1", "ONLY 1% SEE IT"), base: "O",
//         diferente: "Q", colunas: 5..12, linhas: 6..16, dur_s, cor? }
// A posicao do diferente vem da semente (deterministica). Sem estado entre quadros.
(function () {
  'use strict';
  function criar(tela, spec, U) {
    const c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const FUNDOS = ['#FFD23F', '#3EC1F3', '#7CFF8A', '#FF8FB1', '#B07CFF', '#FF9F45'];
    const REVELA = 1.3;   // segundos finais de cada nivel: a resposta
    const niveis = spec.cenas.map((cn, i) => {
      const r = U.rng((spec.semente || 'quiz') + ':' + i), col = Math.round(num(cn.colunas, 4, 12, 6)), lin = Math.round(num(cn.linhas, 5, 16, 9));
      return { col, lin, base: String(cn.base || 'O').slice(0, 3), dif: String(cn.diferente || 'Q').slice(0, 3), alvo: Math.floor(r() * col * lin),
        fundo: corOk(cn.cor, FUNDOS[i % FUNDOS.length]), rotulo: String(cn.texto || 'LEVEL ' + (i + 1)).toUpperCase().slice(0, 24) };
    });
    function quadro(t) {
      const { c: cn, i, local } = U.cenaEm(spec, t), nv = niveis[i], dur = Math.max(2, cn.fim - cn.ini), resta = dur - REVELA - local;
      c.fillStyle = nv.fundo; c.fillRect(0, 0, W, H);
      // rotulo do nivel + cronometro
      c.save(); c.textAlign = 'center'; c.textBaseline = 'middle'; c.font = '78px "Lilita One", sans-serif'; c.fillStyle = '#111';
      c.fillText(nv.rotulo, W / 2, 300);
      if (resta > 0) {
        const seg = Math.ceil(resta), pulso = 1 + 0.12 * Math.max(0, 1 - (resta % 1) * 4);
        c.translate(W / 2, 430); c.scale(pulso, pulso); c.beginPath(); c.arc(0, 0, 70, 0, Math.PI * 2); c.fillStyle = seg <= 2 ? '#E2373C' : '#111'; c.fill();
        c.font = '90px "Lilita One", sans-serif'; c.fillStyle = '#FFF'; c.fillText(String(seg), 0, 6);
      }
      c.restore();
      // a grade: dentro da zona segura (topo 520, rodape H-520, margem direita do app)
      const x0 = 50, x1 = W - 190, y0 = 540, y1 = H - 540, cw = (x1 - x0) / nv.col, ch = (y1 - y0) / nv.lin;
      const tam = Math.floor(Math.min(cw * 0.86, ch * 0.86));
      c.save(); c.font = tam + 'px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillStyle = '#111';
      const entra = U.saida(U.clamp(local / 0.35, 0, 1));
      for (let k = 0; k < nv.col * nv.lin; k++) {
        const cx = x0 + (k % nv.col + 0.5) * cw, cy = y0 + (Math.floor(k / nv.col) + 0.5) * ch;
        c.globalAlpha = entra; c.fillText(k === nv.alvo ? nv.dif : nv.base, cx, cy + (1 - entra) * 30);
      }
      c.restore();
      if (resta <= 0) {
        const k = nv.alvo, cx = x0 + (k % nv.col + 0.5) * cw, cy = y0 + (Math.floor(k / nv.col) + 0.5) * ch, q = U.mola(-resta, 10);
        c.save(); c.lineWidth = 12; c.strokeStyle = '#E2373C'; c.beginPath(); c.arc(cx, cy, Math.max(cw, ch) * 0.62 * q, 0, Math.PI * 2); c.stroke();
        c.font = '84px "Lilita One", sans-serif'; c.textAlign = 'center'; c.fillStyle = '#111'; c.fillText('FOUND IT?', W / 2, 430); c.restore();
      }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 150, fundo: '#111', borda: '#FFF', cor: '#FFF', altura_linha: 100, dur: 2.2 });
    }
    return { quadro };
  }
  MOTORES.quiz = { criar };
})();
