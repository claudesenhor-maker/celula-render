// FISICA -- simulacao "satisfatoria" (22/10; v2 23/10, ordem do dono: "a fisica
// das bolas esta ruim, elas nao saem da argola; crie varios semelhantes").
// Cada batida toca uma nota (a melodia de `spec.melodia`, em ciclo): o som do
// video SAO as colisoes.
//
// O DEFEITO DA v1: a bola entrava na abertura, a abertura girava para longe
// antes de ela terminar de passar, e a parede a "teletransportava" de volta
// para dentro. Agora a bola que comecou a atravessar termina de atravessar, e
// depois do horario de abertura a fenda ALARGA ate alguem passar: o video
// sempre anda.
//
// MODOS (`spec.fisica.modo`):
//   aneis     aneis concentricos girando, cada um com uma fenda; quem escapa
//             quebra o anel (o classico, corrigido)
//   espiral   aneis alternando o sentido do giro, cada um com 2 fendas
//   poligono  bolas dentro de um poligono que gira (3 a 8 lados), com uma fenda
//             num dos lados; o poligono de fora e' maior
//   plinko    corrida: N bolinhas coloridas caem por uma piramide de pinos ate
//             as cacapas; a primeira a chegar ganha (o quiz "qual cor vence?")
//
// DETERMINISTICO: a simulacao inteira roda UMA vez em `criar`, com passo fixo;
// `quadro(t)` so' le. Mesmo spec = mesmo video.
//
// spec.fisica: { modo, aneis: 1..6, lados: 3..8, abertura_graus: 15..90, giro_graus_s: -180..180,
//   bolas: 1..8 (plinko: 2..8), raio_bola: 0.02..0.08, gravidade: 0..2, quique: 0.8..1.05,
//   velocidade: 1.5..5, regra: "cresce|divide|acelera|nenhuma", cores: ["#hex"], fundo: "#hex",
//   nomes: ["RED", ...] (plinko: o nome de cada bola) }
(function () {
  'use strict';
  const TAU = Math.PI * 2;
  const ang = (a) => ((a % TAU) + TAU * 1.5) % TAU - Math.PI;   // -PI..PI

  function criar(tela, spec, U) {
    const c = tela.getContext('2d'), W = spec.w, H = spec.h, FPS = spec.fps || 30;
    const f = spec.fisica || {};
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const MODO = ['aneis', 'espiral', 'poligono', 'plinko'].includes(f.modo) ? f.modo : 'aneis';
    const PAL = ['#FF4D6D', '#FFD23F', '#3EC1F3', '#7CFF8A', '#B07CFF', '#FF9F43', '#00E5C3', '#F368E0'];
    const CORES = (Array.isArray(f.cores) && f.cores.length ? f.cores : PAL).map((x, i) => corOk(x, PAL[i % PAL.length]));
    const FUNDO = corOk(f.fundo, '#0B0B14');
    const dur = spec.dur_s || 30, SUB = 10, dt = 1 / (FPS * SUB), nTotal = Math.ceil(dur * FPS);
    const G = num(f.gravidade, 0, 2, 1) * 1.6, Q = num(f.quique, 0.8, 1.05, 0.98), REGRA = String(f.regra || 'nenhuma');
    const VMIN = num(f.velocidade, 1.5, 5, 2.6), VMAX = VMIN * 1.9;
    const MEL = Array.isArray(spec.melodia) && spec.melodia.length ? spec.melodia.map((n) => num(n, 36, 96, 72)) : [72, 74, 76, 77, 79, 77, 76, 74];
    const rng = U.rng(spec.semente || 'fis');
    const CX = W / 2, CY = H * 0.42, ESC = W * 0.46;          // mundo: 1 = meia largura
    // `impactos` (23/10): ONDE e QUANDO cada batida foi -- a imagem acende no
    // mesmo instante em que a nota toca (o "satisfatorio" e' som e luz juntos)
    const eventos = [], quadros = [], impactos = [];
    const impacto = (t, x, y, cor, k, forte) => { if (impactos.length < 4000 && (!impactos.length || t - impactos[impactos.length - 1].t > 0.02 || forte)) impactos.push({ t, x, y, cor, k, forte: !!forte }); };
    let notaI = 0, batidas = 0;
    const nota = (t, forte) => { if (!eventos.length || t - eventos[eventos.length - 1].t > 0.045 || forte) eventos.push({ t, nota: MEL[notaI++ % MEL.length] + (forte ? 12 : 0), forte: forte ? 1 : 0 }); };
    const limitaV = (b) => { const v = Math.hypot(b.vx, b.vy) || 1e-6; if (v < VMIN) { b.vx *= VMIN / v; b.vy *= VMIN / v; } else if (v > VMAX) { b.vx *= VMAX / v; b.vy *= VMAX / v; } };
    const R0 = num(f.raio_bola, 0.02, 0.08, 0.035) / 0.46;

    // ===================================================================== PAREDES QUE GIRAM
    // aneis/espiral/poligono: N paredes fechadas concentricas; cada uma com
    // fendas que giram. `abre[k]`: a partir de quando a fenda deixa passar.
    let paredes = [];
    if (MODO !== 'plinko') {
      const N = Math.round(num(f.aneis, 1, 6, MODO === 'poligono' ? 3 : 4)), AB0 = (num(f.abertura_graus, 15, 90, 38) * Math.PI) / 180;
      const GIRO = (num(f.giro_graus_s, -180, 180, 60) * Math.PI) / 180, LADOS = Math.round(num(f.lados, 3, 8, 6));
      for (let k = 0; k < N; k++) {
        const R = 0.3 + (0.68 * (k + 1)) / N;
        const omega = MODO === 'espiral' ? (k % 2 ? -1 : 1) * GIRO * (1 + k * 0.15) : GIRO * (1 + k * 0.12);
        paredes.push({ R, omega, fase: rng() * TAU, fendas: MODO === 'espiral' ? 2 : 1, ab: AB0, abre: (dur * (k + 0.8)) / (N + 1.2), viva: true, quebra: null, lados: MODO === 'poligono' ? LADOS : 0 });
      }
    }
    // raio da parede poligonal na direcao `a` (no referencial que gira)
    const raioPoli = (p, a) => { const n = p.lados, setor = TAU / n, x = ((a % setor) + setor) % setor - setor / 2; return (p.R * Math.cos(Math.PI / n)) / Math.cos(x); };
    const raioEm = (p, a) => (p.lados ? raioPoli(p, a) : p.R);
    // a abertura (com alargamento depois do horario): a bola no angulo `a` (mundo) cabe nela?
    function naFenda(p, a, t, r, R) {
      if (t < p.abre) return false;
      const extra = Math.min(Math.PI * 0.7, Math.max(0, t - p.abre - 1.2) * 0.18);   // alarga 10 graus/s depois de 1,2 s
      const meia = (p.ab + extra) / 2 - Math.asin(Math.min(0.9, r / R));
      for (let j = 0; j < p.fendas; j++) { if (Math.abs(ang(a - (p.fase + p.omega * t + (j * TAU) / p.fendas))) < meia) return true; }
      return false;
    }

    let bolas = [];
    if (MODO !== 'plinko') {
      bolas = Array.from({ length: Math.round(num(f.bolas, 1, 8, 1)) }, (_, i) => ({ x: (rng() - 0.5) * 0.2, y: -0.05 + (rng() - 0.5) * 0.1, vx: (rng() < 0.5 ? -1 : 1) * (1.4 + rng()), vy: -1.2 - rng(), r: R0, cor: CORES[i % CORES.length], k: 0, cruzando: false, fora: false, flash: 0 }));
    }

    // ===================================================================== PLINKO
    // PLINKO EM RODADAS: um campeonato (cada rodada ~8 s; 1o lugar 3 pontos, 2o 2, 3o 1) e o campeao no fim
    let pinos = [], cacapas = [], nomes = [], rodadas = [], pontos = [];
    const TOPO = -0.82;
    if (MODO === 'plinko') {
      const nb = Math.round(num(f.bolas, 2, 8, 4)), linhas = 13;
      nomes = Array.from({ length: nb }, (_, i) => String((Array.isArray(f.nomes) && f.nomes[i]) || ['RED', 'YELLOW', 'BLUE', 'GREEN', 'PURPLE', 'ORANGE', 'TEAL', 'PINK'][i]).toUpperCase().slice(0, 10));
      for (let l = 0; l < linhas; l++) {
        const y = -0.6 + (l * 1.38) / (linhas - 1), passo = 0.15, desl = l % 2 ? passo / 2 : 0;
        for (let x = -0.9 + desl; x <= 0.9 + 1e-6; x += passo) pinos.push({ x, y, r: 0.02, brilho: -9 });
      }
      const nc = 7; for (let j = 0; j < nc; j++) cacapas.push({ x0: -0.95 + (j * 1.9) / nc, x1: -0.95 + ((j + 1) * 1.9) / nc });
      const NR = Math.max(1, Math.min(5, Math.floor(dur / 8)));
      for (let r = 0; r < NR; r++) rodadas.push({ ini: (r * dur) / NR, chegada: [] });
      pontos = nomes.map(() => 0);
      bolas = nomes.map((n, i) => ({ x: 0, y: TOPO, vx: 0, vy: 0, r: 0.038, cor: CORES[i % CORES.length], nome: n, i, fora: false, chegou: null }));
    }
    let rodadaAtual = -1;
    const largar = (r) => { rodadaAtual = r; const rr = U.rng((spec.semente || 'fis') + ':r' + r);
      bolas.forEach((b, i) => { b.x = (i - (bolas.length - 1) / 2) * 0.075 + (rr() - 0.5) * 0.03; b.y = TOPO - rr() * 0.06; b.vx = (rr() - 0.5) * 0.4; b.vy = 0; b.chegou = null; }); };

    // ===================================================================== SIMULACAO
    for (let q = 0; q < nTotal; q++) {
      for (let s = 0; s < SUB; s++) {
        const t = (q * SUB + s) * dt;
        if (MODO === 'plinko') {
          if (rodadaAtual + 1 < rodadas.length && t >= rodadas[rodadaAtual + 1].ini) largar(rodadaAtual + 1);
          const rod = rodadas[rodadaAtual];
          for (const b of bolas) {
            if (b.chegou != null) continue;
            b.vy += G * 1.0 * dt; b.x += b.vx * dt; b.y += b.vy * dt;
            for (const p of pinos) {
              const dx = b.x - p.x, dy = b.y - p.y, d = Math.hypot(dx, dy), m = b.r + p.r;
              if (d < m && d > 1e-6) { const nx = dx / d, ny = dy / d, vn = b.vx * nx + b.vy * ny;
                if (vn < 0) { b.vx -= (1 + 0.45) * vn * nx; b.vy -= (1 + 0.45) * vn * ny; b.vx += (rng() - 0.5) * 0.25; p.brilho = t; batidas++; nota(t); impacto(t, p.x, p.y, b.cor, -1); }
                b.x = p.x + nx * m; b.y = p.y + ny * m; }
            }
            // bolas batem entre si (a corrida tem empurra-empurra)
            for (const o of bolas) { if (o === b || o.chegou != null) continue; const dx = b.x - o.x, dy = b.y - o.y, d = Math.hypot(dx, dy), m = b.r + o.r;
              if (d < m && d > 1e-6) { const nx = dx / d, ny = dy / d, rel = (b.vx - o.vx) * nx + (b.vy - o.vy) * ny; if (rel < 0) { b.vx -= rel * nx; b.vy -= rel * ny; o.vx += rel * nx; o.vy += rel * ny; } b.x += nx * (m - d) / 2; b.y += ny * (m - d) / 2; } }
            if (Math.abs(b.x) > 0.95 - b.r) { b.x = Math.sign(b.x) * (0.95 - b.r); b.vx *= -0.6; }
            b.vx *= 0.9995;
            const vmax = 2.2, v = Math.hypot(b.vx, b.vy); if (v > vmax) { b.vx *= vmax / v; b.vy *= vmax / v; }
            if (b.y > 0.94) { b.chegou = t; b.y = 0.94; rod.chegada.push({ i: b.i, t }); const pos = rod.chegada.length; pontos[b.i] += pos === 1 ? 3 : pos === 2 ? 2 : pos === 3 ? 1 : 0; nota(t, pos === 1); }
          }
          continue;
        }
        for (const b of bolas) {
          b.vy += G * dt; b.x += b.vx * dt; b.y += b.vy * dt;
          if (b.fora) continue;
          let k = b.k; while (k < paredes.length && !paredes[k].viva) k++;
          b.k = k; if (k >= paredes.length) { b.fora = true; continue; }
          const p = paredes[k], d = Math.hypot(b.x, b.y), a = Math.atan2(b.y, b.x), R = raioEm(p, a - p.omega * t - p.fase);
          if (b.cruzando) {
            // comecou a atravessar: termina, a fenda girando nao a puxa de volta
            if (d > R + b.r * 1.2) { b.cruzando = false; p.viva = false; p.quebra = t; b.k = k + 1; b.flash = t; nota(t, true); impacto(t, b.x, b.y, b.cor, k, true); }
            else if (d < R - b.r * 2.5) b.cruzando = false;          // voltou para dentro por conta propria
            continue;
          }
          if (d + b.r >= R) {
            if (naFenda(p, a, t, b.r, R)) { b.cruzando = true; continue; }
            // reflete na parede: no circulo a normal e' radial; no poligono, a do lado
            let nx = b.x / d, ny = b.y / d;
            if (p.lados) { const n = p.lados, setor = TAU / n, rel = a - p.omega * t - p.fase, meio = Math.floor((((rel % TAU) + TAU) % TAU) / setor) * setor + setor / 2 + p.omega * t + p.fase; nx = Math.cos(meio); ny = Math.sin(meio); }
            const vn = b.vx * nx + b.vy * ny;
            if (vn > 0) {
              b.vx -= (1 + Q) * vn * nx; b.vy -= (1 + Q) * vn * ny;
              b.vx += -ny * p.omega * p.R * 0.06; b.vy += nx * p.omega * p.R * 0.06;     // a parede que gira empurra
              batidas++; nota(t); impacto(t, b.x + nx * b.r, b.y + ny * b.r, b.cor, k);
              if (REGRA === 'cresce') b.r = Math.min(p.R * 0.4, b.r * 1.03);
              if (REGRA === 'acelera') { b.vx *= 1.02; b.vy *= 1.02; }
              if (REGRA === 'divide' && bolas.length < 40) bolas.push({ x: b.x * 0.92, y: b.y * 0.92, vx: -b.vx * 0.8, vy: b.vy * 0.8, r: b.r, cor: CORES[bolas.length % CORES.length], k: b.k, cruzando: false, fora: false, flash: 0 });
              limitaV(b);
            }
            const fator = (R - b.r) / d; b.x *= fator; b.y *= fator;
          }
        }
      }
      quadros.push({ b: bolas.map((b) => [b.x, b.y, b.r, b.cor, b.fora ? 1 : 0, b.chegou != null ? 1 : 0]), vivas: paredes.map((p) => p.viva), batidas, pontos: pontos.slice(), rodada: rodadaAtual });
    }
    window.EVENTOS_SOM = eventos.map((e) => ({ t: +e.t.toFixed(3), nota: e.nota, forte: e.forte || 0 }));
    console.log('[fisica] modo ' + MODO + ': ' + bolas.length + ' bolas, ' + eventos.length + ' batidas com som, '
      + (MODO === 'plinko' ? rodadas.length + ' rodadas, pontos ' + JSON.stringify(nomes.map((n, i) => n + ':' + pontos[i])) + ', chegadas por rodada ' + rodadas.map((r) => r.chegada.length).join('/') : 'paredes abertas ' + paredes.filter((p) => !p.viva).length + '/' + paredes.length));

    // ===================================================================== DESENHO
    function desenhaParede(p, t) {
      const rot = p.fase + p.omega * t, extra = t > p.abre ? Math.min(Math.PI * 0.7, Math.max(0, t - p.abre - 1.2) * 0.18) : 0, meia = (p.ab + extra) / 2;
      const cor = CORES[(paredes.indexOf(p) + 2) % CORES.length], kp = paredes.indexOf(p);
      const bateu = (desenhaParede.vivos || []).reduce((m, e) => (e.k === kp ? Math.max(m, 1 - (t - e.t) / 0.25) : m), 0);
      c.save(); c.lineWidth = 14 + 8 * bateu; c.lineCap = 'round'; c.lineJoin = 'round'; c.strokeStyle = bateu > 0.5 ? '#FFFFFF' : cor; c.shadowColor = cor; c.shadowBlur = 26 + 40 * bateu;
      // contorno inteiro em passos de 1 grau, pulando as fendas
      c.beginPath(); let caneta = false;
      for (let i = 0; i <= 360; i++) {
        const a = rot + (i * TAU) / 360; let fenda = false;
        for (let j = 0; j < p.fendas; j++) if (Math.abs(ang(a - (rot + (j * TAU) / p.fendas))) < meia) fenda = true;
        if (fenda) { caneta = false; continue; }
        const R = raioEm(p, a - rot), x = CX + Math.cos(a) * R * ESC, y = CY + Math.sin(a) * R * ESC;
        if (caneta) c.lineTo(x, y); else { c.moveTo(x, y); caneta = true; }
      }
      c.stroke();
      // a barreira do portao (tracejada) enquanto a fenda ainda nao deixa passar
      const fecha = 1 - U.clamp((t - p.abre) / 0.4, 0, 1);
      if (fecha > 0) { c.globalAlpha = 0.4 * fecha; c.shadowBlur = 0; c.lineWidth = 6; c.strokeStyle = '#FFFFFF'; c.setLineDash([10, 12]);
        for (let j = 0; j < p.fendas; j++) { const m = rot + (j * TAU) / p.fendas; c.beginPath(); c.arc(CX, CY, p.R * ESC * (p.lados ? Math.cos(Math.PI / p.lados) : 1), m - meia, m + meia); c.stroke(); } c.setLineDash([]); }
      c.restore();
    }
    function estilhaco(p, t) {   // a parede que quebrou vira faiscas por 0,8 s
      const k = (t - p.quebra) / 0.8; if (k < 0 || k > 1) return;
      const r = U.rng(paredes.indexOf(p) + 7), cor = CORES[(paredes.indexOf(p) + 2) % CORES.length];
      c.save(); c.globalAlpha = 1 - k; c.fillStyle = cor;
      for (let i = 0; i < 60; i++) { const a = r() * TAU, d = p.R * (1 + k * (0.3 + r() * 0.5)); c.beginPath(); c.arc(CX + Math.cos(a) * d * ESC, CY + Math.sin(a) * d * ESC + k * k * 200, 6 * (1 - k) + 2, 0, TAU); c.fill(); }
      c.restore();
    }

    const fundoFixo=U.camada(W,H,g=>{const gr=g.createRadialGradient(CX,CY,50,CX,CY,H*.8);gr.addColorStop(0,'#1A1A2E');gr.addColorStop(1,FUNDO);g.fillStyle=gr;g.fillRect(0,0,W,H);});
    function quadro(t) {
      const qi = Math.min(quadros.length - 1, Math.max(0, Math.floor(t * FPS))), Q_ = quadros[qi];
      // as batidas da janela [t-0,45 s, t] (busca binaria: a lista e' em ordem de tempo)
      let lo = 0, hi = impactos.length; while (lo < hi) { const m = (lo + hi) >> 1; if (impactos[m].t < t - 0.45) lo = m + 1; else hi = m; }
      const vivos = []; for (let j = lo; j < impactos.length && impactos[j].t <= t; j++) vivos.push(impactos[j]);
      const ult = vivos[vivos.length - 1], pulso = ult ? Math.max(0, 1 - (t - ult.t) / (ult.forte ? 0.5 : 0.16)) * (ult.forte ? 0.5 : 0.18) : 0;
      c.drawImage(fundoFixo,0,0);
      if (pulso > 0) { const g2 = c.createRadialGradient(CX, CY, 0, CX, CY, H * 0.6); g2.addColorStop(0, ult.cor); g2.addColorStop(1, 'rgba(0,0,0,0)'); c.save(); c.globalAlpha = pulso; c.fillStyle = g2; c.fillRect(0, 0, W, H); c.restore(); }
      if (MODO === 'plinko') {
        pinos.forEach((p) => { const acende = U.clamp(1 - (t - p.brilho) / 0.16, 0, 1); c.save(); c.fillStyle = acende > 0 ? '#FFFFFF' : '#5A6B8C'; if (acende > 0) { c.shadowColor = '#FFFFFF'; c.shadowBlur = 30 * acende; }
          c.beginPath(); c.arc(CX + p.x * ESC, CY + p.y * ESC, p.r * ESC * (1 + 0.5 * acende), 0, TAU); c.fill(); c.restore(); });
        c.save(); c.strokeStyle = '#5A6B8C'; c.lineWidth = 6; cacapas.forEach((k) => { c.beginPath(); c.moveTo(CX + k.x0 * ESC, CY + 0.84 * ESC); c.lineTo(CX + k.x0 * ESC, CY + 1.0 * ESC); c.stroke(); });
        c.beginPath(); c.moveTo(CX - 0.95 * ESC, CY + 1.0 * ESC); c.lineTo(CX + 0.95 * ESC, CY + 1.0 * ESC); c.stroke(); c.restore();
      } else {
        desenhaParede.vivos = vivos;
        paredes.forEach((p, k) => { if (Q_.vivas[k]) desenhaParede(p, t); else estilhaco(p, t); });
      }
      // RASTRO DE LUZ (23/10): uma faixa continua pelos ultimos 12 quadros, que
      // afina e apaga -- antes eram 6 bolinhas soltas quase invisiveis
      const NR = 12, nb = Q_.b.length;
      c.save(); c.lineCap = 'round';
      for (let bi = 0; bi < nb && bi < 40; bi++) {
        for (let j = NR; j >= 1; j--) {
          const a1 = quadros[qi - j], a2 = quadros[qi - j + 1]; if (!a1 || !a2 || !a1.b[bi] || !a2.b[bi]) continue;
          const [x1, y1, r1, cor] = a1.b[bi], [x2, y2] = a2.b[bi]; if (Math.hypot(x2 - x1, y2 - y1) > 0.4) continue;
          const k = 1 - j / (NR + 1); c.globalAlpha = 0.55 * k * k; c.strokeStyle = cor; c.lineWidth = r1 * ESC * 2 * (0.25 + 0.75 * k);
          c.beginPath(); c.moveTo(CX + x1 * ESC, CY + y1 * ESC); c.lineTo(CX + x2 * ESC, CY + y2 * ESC); c.stroke();
        }
      }
      c.restore();
      Q_.b.forEach(([x, y, r, cor]) => { c.save(); c.fillStyle = cor; c.shadowColor = cor; c.shadowBlur = 30; c.beginPath(); c.arc(CX + x * ESC, CY + y * ESC, r * ESC, 0, TAU); c.fill();
        c.shadowBlur = 0; c.globalAlpha = 0.85; c.fillStyle = '#FFFFFF'; c.beginPath(); c.arc(CX + (x - r * 0.3) * ESC, CY + (y - r * 0.3) * ESC, r * ESC * 0.38, 0, TAU); c.fill(); c.restore(); });
      // ONDA DE CHOQUE + FAISCAS em cada batida (0,45 s), na cor da bola
      vivos.forEach((e, n) => {
        const k = (t - e.t) / (e.forte ? 0.45 : 0.32); if (k < 0 || k > 1) return;
        const px = CX + e.x * ESC, py = CY + e.y * ESC, rr = U.rng(Math.floor(e.t * 1000) + n);
        c.save(); c.globalAlpha = (1 - k) * 0.9; c.strokeStyle = e.cor; c.lineWidth = (e.forte ? 10 : 6) * (1 - k) + 1; c.shadowColor = e.cor; c.shadowBlur = 20;
        c.beginPath(); c.arc(px, py, (e.forte ? 160 : 70) * U.saida(k) + 6, 0, TAU); c.stroke();
        c.fillStyle = '#FFFFFF'; const nf = e.forte ? 18 : 7;
        for (let j = 0; j < nf; j++) { const a = rr() * TAU, d = (e.forte ? 220 : 90) * U.saida(k) * (0.5 + rr() * 0.5); c.beginPath(); c.arc(px + Math.cos(a) * d, py + Math.sin(a) * d + k * k * 40, (e.forte ? 6 : 4) * (1 - k) + 1, 0, TAU); c.fill(); }
        c.restore();
      });
      c.globalAlpha = 1;
      c.save(); c.font = '64px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillStyle = '#FFFFFF';
      if (MODO === 'plinko') {
        // placar da rodada e do campeonato
        const ri = Q_.rodada, rod = rodadas[Math.max(0, ri)], ultimo = ri === rodadas.length - 1;
        c.font = '58px "Lilita One", sans-serif'; c.fillText('ROUND ' + (ri + 1) + ' / ' + rodadas.length, W / 2, CY - ESC * 1.02);
        const ord = nomes.map((n, i) => ({ n, i, p: Q_.pontos[i] })).sort((a, b) => b.p - a.p || a.i - b.i);
        c.font = '50px "Lilita One", sans-serif'; ord.forEach((o, j) => { const x = W / 2 + (j - (ord.length - 1) / 2) * (W * 0.86 / ord.length);
          c.fillStyle = CORES[o.i % CORES.length]; c.fillText(o.n, x, H * 0.80 - 210); c.fillStyle = '#FFFFFF'; c.fillText(String(o.p), x, H * 0.80 - 150); });
        const prim = rod && rod.chegada.find((ch) => ch.t <= t);
        if (prim && t - prim.t < 2.2 && !(ultimo && t - prim.t > 1.5)) { const s = U.mola(t - prim.t, 9); c.save(); c.translate(W / 2, CY); c.scale(s, s);
          c.font = '120px "Lilita One", sans-serif'; c.lineWidth = 16; c.strokeStyle = '#111'; const tx = nomes[prim.i] + ' +3'; c.strokeText(tx, 0, 0); c.fillStyle = CORES[prim.i % CORES.length]; c.fillText(tx, 0, 0); c.restore(); }
        const fim = ultimo && rod.chegada.length && t > rod.chegada[0].t + 1.5;
        if (fim) { const campeao = ord[0], s = U.mola(t - rod.chegada[0].t - 1.5, 9); c.save(); c.translate(W / 2, CY); c.scale(s, s); c.font = '130px "Lilita One", sans-serif';
          c.lineWidth = 18; c.strokeStyle = '#111'; c.strokeText(campeao.n, 0, -70); c.fillStyle = CORES[campeao.i % CORES.length]; c.fillText(campeao.n, 0, -70);
          c.font = '96px "Lilita One", sans-serif'; c.strokeText('CHAMPION!', 0, 60); c.fillStyle = '#FFD23F'; c.fillText('CHAMPION!', 0, 60); c.restore(); }
      } else {
        const pula = ult ? 1 + 0.18 * Math.max(0, 1 - (t - ult.t) / 0.12) : 1;
        c.save(); c.translate(W / 2, H * 0.80 - 230); c.scale(pula, pula); c.fillText('BOUNCES: ' + Q_.batidas, 0, 0); c.restore();
        const abertas = Q_.vivas.filter((v) => !v).length; c.fillStyle = '#FFD23F'; c.fillText((MODO === 'poligono' ? 'WALLS: ' : 'RINGS: ') + (paredes.length - abertas) + ' / ' + paredes.length, W / 2, H * 0.80 - 150);
        if (abertas === paredes.length && paredes.length) { const tq = Math.max(...paredes.map((p) => p.quebra || 0)), s = U.mola(t - tq, 9);
          c.translate(W / 2, CY); c.scale(s, s); c.font = '150px "Lilita One", sans-serif'; c.lineWidth = 16; c.strokeStyle = '#111'; c.strokeText('ESCAPED!', 0, 0); c.fillStyle = '#FFD23F'; c.fillText('ESCAPED!', 0, 0); }
      }
      c.restore();
      const { c: cn, i: ci, local: local0 } = U.cenaEm(spec, t);
      // 23/10: na 1a cena o texto esperava nada e saia por baixo do cartaz do titulo
      const local = local0 - (ci === 0 && spec.titulo ? 3.4 : 0);
      if (cn.texto && local >= 0 && local < 3) { c.save(); c.globalAlpha = U.clamp(Math.min(local * 4, (3 - local) * 3), 0, 1); c.font = '72px "Lilita One", sans-serif'; c.textAlign = 'center'; c.fillStyle = '#FFFFFF';
        // 24/10: no plinko o placar da rodada mora em ~y 300; a frase sobe para o topo (o cartaz do titulo ja saiu)
        const y0 = MODO === 'plinko' ? 170 : 330, dy = MODO === 'plinko' ? 64 : 86;
        if (MODO === 'plinko') c.font = '62px "Lilita One", sans-serif';
        U.linhas(c, String(cn.texto), W * 0.8).slice(0, MODO === 'plinko' ? 2 : 9).forEach((l, i) => c.fillText(l, W / 2, y0 + i * dy)); c.restore(); }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 150, fundo: '#FFD23F', borda: '#111', cor: '#111', altura_linha: 100, dur: 3.0 });
    }
    return { quadro };
  }
  MOTORES.fisica = { criar };
})();
