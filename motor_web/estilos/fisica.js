// FISICA -- simulacao "satisfatoria" (22/10, ordem do dono: um nicho e um motor
// por canal). Bolinhas quicando dentro de aneis que giram, cada anel com uma
// abertura; quem escapa cai para o anel de fora. Cada batida toca uma nota (a
// melodia de `spec.melodia`, em ciclo): o som do video SAO as colisoes.
//
// DETERMINISTICO: a simulacao inteira roda UMA vez em `criar`, com passo fixo,
// e guarda a posicao de cada bola em cada quadro e cada batida com o tempo.
// `quadro(t)` so' le. Mesmo spec = mesmo video.
//
// spec.fisica (o que a IA escolhe; tudo cortado na faixa):
//   { aneis: 1..6, abertura_graus: 15..90, giro_graus_s: -180..180, bolas: 1..8,
//     raio_bola: 0.02..0.08 (fracao da tela), gravidade: 0..2, quique: 0.8..1.08,
//     regra: "cresce" (a bola cresce a cada batida) | "divide" (cada batida no anel
//            de fora vira mais uma bola, ate 40) | "acelera" | "nenhuma",
//     cores: ["#hex", ...], fundo: "#hex" }
// cenas: [{ texto (cartela curta, opcional), dur_s }]  -- so' o tempo e o texto
// eventos sonoros: `window.EVENTOS_SOM` [{t, nota}] lido pelo render_web.
(function () {
  'use strict';
  function criar(tela, spec, U) {
    const c = tela.getContext('2d'), W = spec.w, H = spec.h, FPS = spec.fps || 30;
    const f = spec.fisica || {};
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const N_ANEIS = Math.round(num(f.aneis, 1, 6, 3)), AB = (num(f.abertura_graus, 15, 90, 40) * Math.PI) / 180;
    const GIRO = (num(f.giro_graus_s, -180, 180, 45) * Math.PI) / 180, G = num(f.gravidade, 0, 2, 1) * 1.6;
    const Q = num(f.quique, 0.8, 1.08, 1.0), REGRA = String(f.regra || 'nenhuma');
    const CORES = (Array.isArray(f.cores) && f.cores.length ? f.cores : ['#FF4D6D', '#FFD23F', '#3EC1F3', '#7CFF8A', '#B07CFF']).map((x, i) => corOk(x, ['#FF4D6D', '#FFD23F', '#3EC1F3'][i % 3]));
    const FUNDO = corOk(f.fundo, '#0B0B14');
    // mundo em unidades de "raio da tela" (1 = metade da largura); centro na tela
    const CX = W / 2, CY = H * 0.42, ESC = W * 0.46;
    const raios = Array.from({ length: N_ANEIS }, (_, i) => 0.32 + (0.68 * (i + 1)) / N_ANEIS);
    const R0 = num(f.raio_bola, 0.02, 0.08, 0.035) / 0.46;
    const MAX_B = 40, dur = spec.dur_s || 30, dt = 1 / (FPS * 8), sub = 8;
    // O PORTAO: a abertura do anel k so' deixa passar depois de ABRE[k] -- os
    // aneis caem espalhados pelo video (o ultimo perto do fim), seja qual for o
    // numero que a IA escolheu. Antes disso a abertura tem uma barreira fraca.
    const ABRE = raios.map((_, k) => (dur * (k + 1)) / (N_ANEIS + 1.15));
    // estado inicial deterministico
    const rng = U.rng(spec.semente || 'fis');
    let bolas = Array.from({ length: Math.round(num(f.bolas, 1, 8, 1)) }, (_, i) => ({ x: (rng() - 0.5) * 0.2, y: -0.1 + (rng() - 0.5) * 0.1, vx: (rng() < 0.5 ? -1 : 1) * (1.4 + rng()), vy: -1.2 - rng(), r: R0, cor: CORES[i % CORES.length], anel: 0, fora: false }));
    const quadros = [], eventos = [], vivo = raios.map(() => true);
    let notaI = 0, batidas = 0;
    const MEL = Array.isArray(spec.melodia) && spec.melodia.length ? spec.melodia.map((n) => num(n, 36, 96, 72)) : [72, 74, 76, 77, 79, 77, 76, 74];
    const nTotal = Math.ceil(dur * FPS);
    for (let q = 0; q < nTotal; q++) {
      for (let s = 0; s < sub; s++) {
        const t = (q * sub + s) * dt, giro = GIRO * t;
        for (const b of bolas) {
          if (b.fora) { b.vy += G * dt; b.x += b.vx * dt; b.y += b.vy * dt; continue; }
          b.vy += G * dt; b.x += b.vx * dt; b.y += b.vy * dt;
          // o anel vivo mais interno que contem a bola
          let k = b.anel; while (k < N_ANEIS && !vivo[k]) k++;
          if (k >= N_ANEIS) { b.fora = true; continue; }
          b.anel = k;
          const R = raios[k], d = Math.hypot(b.x, b.y);
          if (d + b.r >= R) {
            // passa pela abertura? (o angulo da bola contra o da abertura, que gira)
            let a = Math.atan2(b.y, b.x) - giro - k * 0.9; a = ((a % (Math.PI * 2)) + Math.PI * 3) % (Math.PI * 2) - Math.PI;
            if (Math.abs(a) < AB / 2 && t >= ABRE[k]) { if (d > R + b.r) { vivo[k] = false; b.anel = k + 1; eventos.push({ t, nota: MEL[notaI++ % MEL.length] + 12, forte: 1 }); } continue; }
            // reflete na parede (normal = radial) e recoloca dentro
            const nx = b.x / d, ny = b.y / d, vn = b.vx * nx + b.vy * ny;
            if (vn > 0) {
              b.vx -= (1 + Q) * vn * nx; b.vy -= (1 + Q) * vn * ny;
              // um empurrao tangencial pelo giro do anel: o movimento nunca morre
              b.vx += -ny * GIRO * R * 0.05; b.vy += nx * GIRO * R * 0.05;
              b.x = nx * (R - b.r); b.y = ny * (R - b.r);
              batidas++;
              if (!eventos.length || t - eventos[eventos.length - 1].t > 0.045) eventos.push({ t, nota: MEL[notaI++ % MEL.length] });
              if (REGRA === 'cresce') b.r = Math.min(R * 0.45, b.r * 1.03);
              if (REGRA === 'acelera') { b.vx *= 1.02; b.vy *= 1.02; }
              if (REGRA === 'divide' && bolas.length < MAX_B && k === b.anel) bolas = bolas.concat([{ x: b.x * 0.9, y: b.y * 0.9, vx: -b.vx * 0.8, vy: b.vy * 0.8, r: b.r, cor: CORES[bolas.length % CORES.length], anel: b.anel, fora: false }]);
              // faixa de velocidade: abaixo de VMIN o video "morre" (o nicho vive
              // de 3-6 batidas por segundo); acima de VMAX vira borrao
              const v = Math.hypot(b.vx, b.vy), VMIN = num(f.velocidade, 1.5, 5, 2.6), VMAX = VMIN * 1.9;
              if (v < VMIN) { b.vx *= VMIN / v; b.vy *= VMIN / v; } else if (v > VMAX) { b.vx *= VMAX / v; b.vy *= VMAX / v; }
            }
          }
        }
      }
      quadros.push({ b: bolas.map((b) => [b.x, b.y, b.r, b.cor, b.fora ? 1 : 0]), vivo: vivo.slice(), batidas });
    }
    window.EVENTOS_SOM = eventos.map((e) => ({ t: +e.t.toFixed(3), nota: e.nota, forte: e.forte || 0 }));
    console.log('[fisica] ' + N_ANEIS + ' aneis, ' + bolas.length + ' bolas no fim, ' + eventos.length + ' batidas com som, aneis abertos ' + vivo.filter((v) => !v).length);

    function quadro(t) {
      const qi = Math.min(quadros.length - 1, Math.max(0, Math.floor(t * FPS))), Q_ = quadros[qi], giro = GIRO * t;
      c.fillStyle = FUNDO; c.fillRect(0, 0, W, H);
      // aneis (os quebrados somem num flash)
      raios.forEach((R, k) => {
        if (!Q_.vivo[k]) return;
        const a0 = giro + k * 0.9 + AB / 2, a1 = giro + k * 0.9 + Math.PI * 2 - AB / 2;
        c.save(); c.lineWidth = 14; c.lineCap = 'round'; c.strokeStyle = CORES[(k + 2) % CORES.length]; c.shadowColor = c.strokeStyle; c.shadowBlur = 24;
        c.beginPath(); c.arc(CX, CY, R * ESC, a0, a1); c.stroke();
        // a barreira do portao: some quando o anel pode ser vencido
        const fecha = 1 - U.clamp((t - ABRE[k]) / 0.4, 0, 1);
        if (fecha > 0) { c.globalAlpha = 0.35 * fecha; c.lineWidth = 6; c.shadowBlur = 0; c.strokeStyle = '#FFFFFF'; c.setLineDash([10, 14]); c.beginPath(); c.arc(CX, CY, R * ESC, a1, a0 + Math.PI * 2); c.stroke(); c.setLineDash([]); }
        c.restore();
      });
      // rastro: as ultimas posicoes de cada bola
      for (let j = 6; j >= 0; j--) {
        const qq = quadros[Math.max(0, qi - j * 2)]; if (!qq) continue;
        qq.b.forEach(([x, y, r, cor]) => { c.globalAlpha = j ? 0.12 * (1 - j / 7) : 1; c.fillStyle = cor; c.beginPath(); c.arc(CX + x * ESC, CY + y * ESC, r * ESC, 0, Math.PI * 2); c.fill(); });
      }
      c.globalAlpha = 1;
      // contadores
      c.save(); c.font = '64px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillStyle = '#FFFFFF';
      c.fillText('BOUNCES: ' + Q_.batidas, W / 2, H * 0.80 - 230);
      const abertos = Q_.vivo.filter((v) => !v).length; c.fillStyle = '#FFD23F'; c.fillText('RINGS: ' + (raios.length - abertos) + ' / ' + raios.length, W / 2, H * 0.80 - 150); c.restore();
      // cartela da cena (opcional)
      const { c: cn, local } = U.cenaEm(spec, t);
      if (cn.texto && local < 3) { c.save(); c.globalAlpha = U.clamp(Math.min(local * 4, (3 - local) * 3), 0, 1); c.font = '72px "Lilita One", sans-serif'; c.textAlign = 'center'; c.fillStyle = '#FFFFFF';
        U.linhas(c, String(cn.texto), W * 0.8).forEach((l, i) => c.fillText(l, W / 2, 330 + i * 86)); c.restore(); }
      if (abertos === raios.length) { const qq = quadros.findIndex((x) => x.vivo.every((v) => !v)), s = U.mola(t - qq / FPS, 9);
        c.save(); c.translate(W / 2, CY); c.scale(s, s); c.font = '150px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        c.lineWidth = 16; c.strokeStyle = '#111'; c.strokeText('ESCAPED!', 0, 0); c.fillStyle = '#FFD23F'; c.fillText('ESCAPED!', 0, 0); c.restore(); }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 150, fundo: '#FFD23F', borda: '#111', cor: '#111', altura_linha: 100, dur: 3.0 });
    }
    return { quadro };
  }
  MOTORES.fisica = { criar };
})();
