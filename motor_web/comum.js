// MOTOR WEB -- a base comum dos quatro estilos (13/10, HISTORICO §109).
//
// POR QUE NO NAVEGADOR
//   Os quatro canais novos (mangueira, silhueta, pixel, lowpoly) sao desenho
//   por CODIGO, sem arte de personagem. Canvas 2D e three.js desenham isso
//   melhor e mais rapido que o Pillow do motor do recorte, e o MESMO codigo
//   roda na previa (artifact) e na producao (Chrome headless no Action,
//   `render_web.mjs`). O que a previa mostra e' o que vai ao ar.
//
// O CONTRATO DE UM ESTILO
//   MOTORES[estilo] = { criar(canvas, spec, U) -> { quadro(t) } }
//   `quadro(t)` desenha o instante `t` (segundos) do video inteiro e NAO guarda
//   estado entre chamadas: o quadro 137 e' sempre o mesmo quadro 137 (lei do
//   motor antigo, `efeitos.py`). Tudo o que anda vem de `t` e da semente.
//
// O SPEC (montado por `montar_web.py`, ver `docs/motor.md` §5.3)
//   { estilo, w, h, fps, dur_s, titulo, idioma, semente,
//     cenas: [{ ini, fim, cenario, acao, atores, objeto, camera, texto, hora }],
//     palavras: [{ palavra, ini, fim }]   -- so' nos narrados }
(function (G) {
  'use strict';
  const TAU = Math.PI * 2;
  const U = {
    TAU,
    clamp: (v, a, b) => Math.max(a, Math.min(b, v)),
    lerp: (a, b, k) => a + (b - a) * k,
    // suavizacoes: o movimento acelera e freia (principio 6 da Disney)
    suave: (k) => { k = Math.max(0, Math.min(1, k)); return k * k * (3 - 2 * k); },
    saida: (k) => 1 - Math.pow(1 - Math.max(0, Math.min(1, k)), 3),
    entrada: (k) => Math.pow(Math.max(0, Math.min(1, k)), 3),
    // mola: passa do ponto e volta (o "pop" de quem entra)
    mola: (x, f) => (x <= 0 ? 0 : 1 - Math.exp(-6.5 * x) * Math.cos((f || 12) * x)),
    onda: (p) => Math.sin(TAU * p),
    // gerador deterministico (xorshift); mesma semente, mesmo video
    rng(seed) {
      let s = (typeof seed === 'string' ? [...seed].reduce((a, c) => (a * 31 + c.charCodeAt(0)) >>> 0, 7) : seed >>> 0) || 1;
      return () => { s ^= s << 13; s >>>= 0; s ^= s >>> 17; s ^= s << 5; s >>>= 0; return (s % 100000) / 100000; };
    },
    rr(c, x, y, w, h, r) {
      r = Math.min(r, w / 2, h / 2);
      c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r);
      c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath();
    },
    // a cena do instante t, o indice e o progresso dentro dela (0..1)
    cenaEm(spec, t) {
      const cs = spec.cenas;
      let i = cs.findIndex((c) => t >= c.ini && t < c.fim);
      if (i < 0) i = t < cs[0].ini ? 0 : cs.length - 1;
      const c = cs[i];
      return { c, i, k: U.clamp((t - c.ini) / Math.max(0.001, c.fim - c.ini), 0, 1), local: t - c.ini };
    },
    // quebra o texto em linhas que cabem em `max` px
    linhas(c, texto, max) {
      const out = []; let lin = '';
      String(texto || '').split(/\s+/).filter(Boolean).forEach((w) => {
        const tenta = lin ? lin + ' ' + w : w;
        if (c.measureText(tenta).width > max && lin) { out.push(lin); lin = w; } else lin = tenta;
      });
      if (lin) out.push(lin);
      return out;
    },
    // O SELO DO ALTO (hud): antes cada estilo cortava em 14 caracteres e saia
    // "1.5 M AT THE S" (23/10). Agora corta so' entre palavras (ate `maxCar`)
    // e diminui a fonte ja posta em `c.font` ate caber em `maxW` px.
    hud(c, texto, maxW, maxCar) {
      let s = String(texto == null ? '' : texto).toUpperCase().replace(/\s+/g, ' ').trim();
      const lim = maxCar || 22;
      if (s.length > lim) { const corte = s.slice(0, lim + 1).lastIndexOf(' '); s = s.slice(0, corte > 4 ? corte : lim).trim(); }
      const m = /(\d+(?:\.\d+)?)px/.exec(c.font); let px = m ? Number(m[1]) : 100;
      while (px > 40 && c.measureText(s).width > maxW) { px -= 4; c.font = c.font.replace(/\d+(?:\.\d+)?px/, px + 'px'); }
      return s;
    },
    // A LEGENDA DOS NARRADOS: 3 palavras por vez, a da voz destacada. Short se
    // assiste no mudo (mesma regra do motor do recorte, `legendas.py`).
    legenda(c, spec, t, est) {
      const pw = spec.palavras || [];
      if (!pw.length) return;
      let i = pw.findIndex((p) => t >= p.ini && t < p.fim + 0.25);
      if (i < 0) return;
      const n = est.por_vez || 3, g0 = Math.floor(i / n) * n, grupo = pw.slice(g0, g0 + n);
      if (t > grupo[grupo.length - 1].fim + 0.35) return;
      c.save();
      c.font = est.fonte; c.textAlign = 'left'; c.textBaseline = 'middle';
      const esp = c.measureText(' ').width;
      const larg = grupo.reduce((s, p) => s + c.measureText(est.caixa ? p.palavra.toUpperCase() : p.palavra).width, 0) + esp * (grupo.length - 1);
      let x = spec.w / 2 - larg / 2; const y = est.y;
      const pop = U.mola(t - pw[g0].ini, 14);
      // palavra longa ("23-DEGREE") nunca sai pela borda: o grupo encolhe
      const cabe = Math.min(1, (spec.w * 0.9) / Math.max(1, larg));
      c.translate(spec.w / 2, y); c.scale(cabe * (0.85 + 0.15 * pop), cabe * (0.85 + 0.15 * pop)); c.translate(-spec.w / 2, -y);
      grupo.forEach((p, k) => {
        const w = est.caixa ? p.palavra.toUpperCase() : p.palavra;
        const ativa = g0 + k === i;
        c.lineJoin = 'round'; c.lineWidth = est.contorno || 14; c.strokeStyle = est.cor_contorno || '#000';
        c.strokeText(w, x, y);
        c.fillStyle = ativa ? est.cor_ativa : est.cor;
        c.fillText(w, x, y);
        x += c.measureText(w).width + esp;
      });
      c.restore();
    },
    // O CARTAZ DO 1o SEGUNDO (o mesmo papel do `legendas.Titulo` do recorte):
    // a promessa do video escrita enquanto o feed decide. Sai em ~3 s.
    cartaz(c, spec, t, est) {
      if (!spec.titulo) return;
      const dur = est.dur || 3.2;
      if (t > dur + 0.4) return;
      // 23/10 (retencao): o cartaz ja' esta' NO QUADRO 0 -- e' o quadro que o feed
      // mostra enquanto a pessoa decide; antes ele nascia do zero e so' aparecia ~0,2 s depois
      const ent = U.mola(t + 0.35, 11), sai = U.clamp((t - dur) / 0.4, 0, 1);
      c.save();
      c.font = est.fonte; c.textAlign = 'center'; c.textBaseline = 'middle';
      const ls = U.linhas(c, est.caixa ? spec.titulo.toUpperCase() : spec.titulo, spec.w * 0.8);
      const lh = est.altura_linha || 96, h = ls.length * lh + 60, w = Math.min(spec.w * 0.9, Math.max(...ls.map((l) => c.measureText(l).width)) + 90);
      c.translate(spec.w / 2, est.y + h / 2); c.scale(ent * (1 - sai * 0.3), ent * (1 - sai * 0.3)); c.globalAlpha = 1 - sai;
      if (est.fundo) { U.rr(c, -w / 2, -h / 2, w, h, est.raio || 28); c.fillStyle = est.fundo; c.fill(); if (est.borda) { c.lineWidth = 8; c.strokeStyle = est.borda; c.stroke(); } }
      ls.forEach((l, k) => {
        const y = -h / 2 + 30 + lh / 2 + k * lh;
        if (est.contorno) { c.lineWidth = est.contorno; c.strokeStyle = est.cor_contorno || '#000'; c.lineJoin = 'round'; c.strokeText(l, 0, y); }
        c.fillStyle = est.cor; c.fillText(l, 0, y);
      });
      c.restore();
    }
  };
// T272: função pura; grupos de três palavras + cortes de segurança até 6 s.
function ritmoInicio(spec, t) {
  const marcos = [0];
  const palavras = Array.isArray(spec.palavras) ? spec.palavras : [];
  const pedidos = palavras.filter((_, i) => i % 3 === 0)
    .map(p => Number(p.ini)).filter(x => Number.isFinite(x) && x > 0 && x < 6)
    .concat((spec.cenas || []).map(c => Number(c.ini)).filter(x => Number.isFinite(x) && x > 0 && x < 6));
  for (const alvo of [...new Set(pedidos)].sort((a,b) => a-b).concat([6])) {
    while (alvo-marcos[marcos.length-1] > 1.5) marcos.push(marcos[marcos.length-1]+1.5);
    if (alvo < 6 && alvo > marcos[marcos.length-1]) marcos.push(alvo);
  }
  const indice = marcos.filter(x => x <= t).length-1;
  return {zoom: t >= 0 && t < 6 && indice % 2 === 0 ? 1.08 : 1, indice, marcos};
}

// A cópia raster funciona para Canvas 2D e WebGL e não altera MOTOR.quadro(t).
// `saida` é só o destino: seu conteúdo é sobrescrito integralmente a cada chamada.
function quadroComRitmo(tela, spec, t, saida) {
  const z = ritmoInicio(spec, t).zoom, w = tela.width, h = tela.height;
  const ctx = saida.getContext('2d');
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, w, h);
  ctx.drawImage(tela, (w-w/z)/2, (h-h/z)/2, w/z, h/z, 0, 0, w, h);
  return saida;
}

  U.ritmoInicio = ritmoInicio;
  U.quadroComRitmo = quadroComRitmo;
  G.U = U;
  G.MOTORES = G.MOTORES || {};
})(window);
