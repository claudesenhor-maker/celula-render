// MAPA -- historia e geografia em mapa animado (23/10, MAP STORIES; um nicho e
// um motor por canal). Fronteiras que acendem, rotas que se desenham, setas de
// avanco, marcadores e o ANO na tela, com a camera indo de um lugar a outro.
//
// O mundo vem de `dados/mundo.js` (Natural Earth 110m, fronteiras ATUAIS).
// Imperio ou pais antigo = os paises de hoje que cobrem a area.
//
// CENA (todos os campos opcionais, menos `texto` nos narrados):
//   { texto, acao: "mostra|destaca|rota|avanca|marca|ano",
//     foco: {lon, lat, zoom} (zoom 1 = o mundo inteiro na largura),
//     paises: ["France" | {pais, cor, rotulo}],   -- acendem; sem `foco`, a camera enquadra eles
//     rota: {pontos: [[lon,lat], ...], cor, rotulo},  -- desenha-se ao longo da cena
//     setas: [{de: [lon,lat], para: [lon,lat], cor}], -- avanco de exercito, migracao
//     marcadores: [{lon, lat, rotulo}],
//     ano: "1914" | "476 AD",                     -- fica na tela ate outra cena trocar
//     hud: "x3" }                                  -- o numero da frase, grande
//
// CONTRATO (comum.js): `quadro(t)` sem estado entre quadros.
(function () {
  'use strict';
  const ALIAS = {
    usa: 'United States of America', us: 'United States of America', 'united states': 'United States of America', america: 'United States of America',
    uk: 'United Kingdom', britain: 'United Kingdom', 'great britain': 'United Kingdom', england: 'United Kingdom', scotland: 'United Kingdom', wales: 'United Kingdom',
    drc: 'Dem. Rep. Congo', 'democratic republic of the congo': 'Dem. Rep. Congo', 'congo kinshasa': 'Dem. Rep. Congo', 'republic of the congo': 'Congo',
    'czech republic': 'Czechia', 'ivory coast': "Côte d'Ivoire", 'cote divoire': "Côte d'Ivoire", 'south sudan': 'S. Sudan',
    'central african republic': 'Central African Rep.', 'dominican republic': 'Dominican Rep.', bosnia: 'Bosnia and Herz.',
    'bosnia and herzegovina': 'Bosnia and Herz.', 'north macedonia': 'Macedonia', swaziland: 'eSwatini', eswatini: 'eSwatini', burma: 'Myanmar',
    persia: 'Iran', 'western sahara': 'W. Sahara', falklands: 'Falkland Is.', 'falkland islands': 'Falkland Is.', 'solomon islands': 'Solomon Is.',
    'equatorial guinea': 'Eq. Guinea', 'east timor': 'Timor-Leste', 'northern cyprus': 'N. Cyprus', holland: 'Netherlands', 'the netherlands': 'Netherlands',
    'south korea': 'South Korea', korea: 'South Korea', 'north korea': 'North Korea', 'russian federation': 'Russia', ussr: 'Russia', 'soviet union': 'Russia',
    'turkiye': 'Turkey', 'vatican': 'Italy',
    // o roteiro em espanhol/portugues as vezes escreve o nome local
    'estados unidos': 'United States of America', brasil: 'Brazil', espana: 'Spain', espanha: 'Spain', alemania: 'Germany', alemanha: 'Germany',
    francia: 'France', 'franca': 'France', 'reino unido': 'United Kingdom', rusia: 'Russia', 'russia': 'Russia', japon: 'Japan', japao: 'Japan',
    mexico: 'Mexico', italia: 'Italy', egipto: 'Egypt', egito: 'Egypt', inglaterra: 'United Kingdom', china: 'China', turquia: 'Turkey', grecia: 'Greece',
  };
  const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z ]/g, ' ').replace(/\s+/g, ' ').trim();

  function criar(tela, spec, U) {
    const c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const MUNDO = window.MUNDO || [];
    const porNome = {};
    MUNDO.forEach((p, i) => { porNome[norm(p.n)] = i; });
    const acharPais = (nome) => {
      const k = norm(nome); if (!k) return -1;
      if (porNome[k] != null) return porNome[k];
      const a = ALIAS[k]; if (a && porNome[norm(a)] != null) return porNome[norm(a)];
      const quase = MUNDO.findIndex((p) => norm(p.n).startsWith(k) || k.startsWith(norm(p.n)));
      return quase;
    };
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const ponto = (v) => (Array.isArray(v) && v.length >= 2 ? [num(v[0], -180, 180, 0), num(v[1], -80, 84, 0)] : null);
    const PALETA = ['#E4572E', '#2E86AB', '#F2A541', '#7BAE37', '#9B5DE5', '#E83F6F', '#00A6A6'];

    // Mercator em "graus": X = lon, Y = y de Mercator convertido para graus
    const merc = (lat) => (Math.log(Math.tan(Math.PI / 4 + (U.clamp(lat, -82, 84) * Math.PI) / 360)) * 180) / Math.PI;

    // O QUE CADA CENA PEDE, ja resolvido (indices de pais, pontos validos)
    const cenas = spec.cenas.map((cn, i) => {
      const paises = (Array.isArray(cn.paises) ? cn.paises : []).slice(0, 24).map((x, j) => {
        const o = typeof x === 'string' ? { pais: x } : x || {};
        return { i: acharPais(o.pais), cor: corOk(o.cor, PALETA[(i + j) % PALETA.length]), rotulo: o.rotulo != null ? String(o.rotulo).slice(0, 22) : null };
      }).filter((p) => p.i >= 0);
      const rota = cn.rota && Array.isArray(cn.rota.pontos) ? { pts: cn.rota.pontos.map(ponto).filter(Boolean).slice(0, 40), cor: corOk(cn.rota.cor, '#E4572E'), rotulo: cn.rota.rotulo ? String(cn.rota.rotulo).slice(0, 22) : null } : null;
      const setas = (Array.isArray(cn.setas) ? cn.setas : []).slice(0, 8).map((s) => ({ de: ponto(s && s.de), para: ponto(s && s.para), cor: corOk(s && s.cor, '#C62828') })).filter((s) => s.de && s.para);
      const marcas = (Array.isArray(cn.marcadores) ? cn.marcadores : []).slice(0, 8).map((m) => ({ p: ponto([m && m.lon, m && m.lat]), rotulo: String((m && m.rotulo) || '').slice(0, 20) })).filter((m) => m.p);
      return { paises, rota: rota && rota.pts.length >= 2 ? rota : null, setas, marcas, ano: cn.ano != null && String(cn.ano).trim() ? String(cn.ano).trim().slice(0, 10) : null, foco: cn.foco || null, hud: cn.hud };
    });

    // A CAMERA de cada cena: o foco pedido, ou a caixa do que a cena mostra
    const AREA = { cx: W / 2, cy: H * 0.43, w: W * 0.86, h: H * 0.46 };
    function caixaDe(cn) {
      const xs = [], ys = [];
      // pela caixa do territorio PRINCIPAL: a Franca sem a Guiana, os EUA sem o Alasca
      cn.paises.forEach((p) => { const b = MUNDO[p.i].bm || MUNDO[p.i].b; xs.push(b[0], b[2]); ys.push(merc(b[1]), merc(b[3])); });
      if (cn.rota) cn.rota.pts.forEach((q) => { xs.push(q[0]); ys.push(merc(q[1])); });
      cn.setas.forEach((s) => { xs.push(s.de[0], s.para[0]); ys.push(merc(s.de[1]), merc(s.para[1])); });
      cn.marcas.forEach((m) => { xs.push(m.p[0]); ys.push(merc(m.p[1])); });
      if (!xs.length) return null;
      // pais com territorio do outro lado do mundo (Russia, EUA com Alasca) nao
      // pode virar uma caixa do planeta inteiro: limita a largura ao miolo
      return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
    }
    const cams = [];
    cenas.forEach((cn, i) => {
      let cam = null;
      if (cn.foco && typeof cn.foco === 'object') {
        cam = { x: num(cn.foco.lon, -180, 180, 0), y: merc(num(cn.foco.lat, -80, 84, 20)), z: num(cn.foco.zoom, 1, 40, 2) };
      } else {
        const b = caixaDe(cn);
        if (b) {
          const zw = (AREA.w / Math.max(4, (b.x1 - b.x0) * 1.25)) / (W / 360), zh = (AREA.h / Math.max(3, (b.y1 - b.y0) * 1.3)) / (W / 360);
          cam = { x: (b.x0 + b.x1) / 2, y: (b.y0 + b.y1) / 2, z: U.clamp(Math.min(zw, zh), 1, 30) };
        }
      }
      cams.push(cam || (i ? cams[i - 1] : { x: 10, y: merc(22), z: 1.15 }));
    });
    // o ano que vale em cada cena (fica ate alguem trocar)
    const anos = []; cenas.forEach((cn, i) => anos.push(cn.ano || (i ? anos[i - 1] : null)));

    const lerpLog = (a, b, k) => Math.exp(U.lerp(Math.log(a), Math.log(b), k));
    let VIEW = null;
    const proj = (lon, lat) => [AREA.cx + (lon - VIEW.x) * VIEW.s, AREA.cy - (merc(lat) - VIEW.y) * VIEW.s];
    const projM = (x, y) => [AREA.cx + (x - VIEW.x) * VIEW.s, AREA.cy - (y - VIEW.y) * VIEW.s];

    // o mundo desenhado 3 vezes (-360, 0, +360): a camera pode cruzar o Pacifico
    function caminhoPais(p, dx) {
      c.beginPath();
      p.a.forEach((r) => {
        for (let j = 0; j < r.length; j += 2) {
          const q = projM(r[j] + dx, merc(r[j + 1]));
          // trecho que pula mais de meio mundo e' a costura da linha de data:
          // ligar os dois lados riscaria a tela de ponta a ponta
          if (j && Math.abs(r[j] - r[j - 2]) < 180) c.lineTo(q[0], q[1]); else c.moveTo(q[0], q[1]);
        }
        c.closePath();
      });
    }
    function visivel(p, dx) {
      const a = projM(p.b[0] + dx, merc(p.b[3])), b = projM(p.b[2] + dx, merc(p.b[1]));
      return !(b[0] < -20 || a[0] > W + 20 || b[1] < -20 || a[1] > H + 20);
    }
    const copias = () => [-360, 0, 360].filter((dx) => { const l = projM(-180 + dx, 0)[0], r = projM(180 + dx, 0)[0]; return r > -50 && l < W + 50; });

    function fundo(t) {
      const g = c.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#0B2240'); g.addColorStop(0.5, '#123B66'); g.addColorStop(1, '#0B2240');
      c.fillStyle = g; c.fillRect(0, 0, W, H);
      // grade de meridianos e paralelos: 30 graus de longe, 10 de perto
      const passo = VIEW.s > 30 ? 5 : VIEW.s > 9 ? 10 : 30;
      c.save(); c.strokeStyle = 'rgba(255,255,255,0.07)'; c.lineWidth = 1.5;
      for (let lon = -540; lon <= 540; lon += passo) { const a = proj(lon, -80), b = proj(lon, 84); if (a[0] < -5 || a[0] > W + 5) continue; c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); }
      for (let lat = -60; lat <= 80; lat += passo) { const y = proj(0, lat)[1]; if (y < -5 || y > H + 5) continue; c.beginPath(); c.moveTo(0, y); c.lineTo(W, y); c.stroke(); }
      c.restore();
      // brilho que anda devagar na agua
      const bx = W * (0.3 + 0.4 * Math.sin(t * 0.07)), rg = c.createRadialGradient(bx, H * 0.35, 0, bx, H * 0.35, W);
      rg.addColorStop(0, 'rgba(120,180,255,0.10)'); rg.addColorStop(1, 'rgba(0,0,0,0)'); c.fillStyle = rg; c.fillRect(0, 0, W, H);
    }

    function terra(destaques) {
      const cp = copias();
      // sombra da terra (da relevo ao papel)
      c.save(); c.fillStyle = 'rgba(0,0,0,0.35)'; c.translate(0, 5);
      cp.forEach((dx) => MUNDO.forEach((p) => { if (visivel(p, dx)) { caminhoPais(p, dx); c.fill('evenodd'); } })); c.restore();
      c.lineJoin = 'round';
      cp.forEach((dx) => MUNDO.forEach((p, i) => {
        if (!visivel(p, dx)) return;
        caminhoPais(p, dx);
        c.fillStyle = p.n === 'Antarctica' ? '#E8EEF2' : '#EDE3CC'; c.fill('evenodd');
        const d = destaques[i];
        if (d && d.a > 0.01) { c.globalAlpha = d.a; c.fillStyle = d.cor; c.fill('evenodd'); c.globalAlpha = 1; }
        c.lineWidth = d && d.a > 0.3 ? 3 : 1.2; c.strokeStyle = d && d.a > 0.3 ? '#FFFFFF' : '#A8977A'; c.stroke();
      }));
    }

    function rotuloEm(x, y, txt, est) {
      c.save(); c.font = (est.fonte || '46px') + ' "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
      const w = c.measureText(txt).width + 36, h = est.h || 64, s = est.s == null ? 1 : est.s;
      c.translate(U.clamp(x, w / 2 + 12, W - w / 2 - 12), U.clamp(y, 260, H * 0.64)); c.scale(s, s);
      U.rr(c, -w / 2, -h / 2, w, h, 18); c.fillStyle = est.fundo || 'rgba(255,255,255,0.92)'; c.fill();
      c.fillStyle = est.cor || '#13233A'; c.fillText(txt, 0, 3); c.restore();
    }

    // trecho [0..p] de uma polilinha em tela
    function polilinha(pts, p) {
      const seg = []; let tot = 0;
      for (let j = 1; j < pts.length; j++) { const l = Math.hypot(pts[j][0] - pts[j - 1][0], pts[j][1] - pts[j - 1][1]); seg.push(l); tot += l; }
      let resta = tot * U.clamp(p, 0, 1); const out = [pts[0]];
      for (let j = 1; j < pts.length && resta > 0; j++) {
        if (resta >= seg[j - 1]) { out.push(pts[j]); resta -= seg[j - 1]; } else { const k = resta / seg[j - 1]; out.push([U.lerp(pts[j - 1][0], pts[j][0], k), U.lerp(pts[j - 1][1], pts[j][1], k)]); resta = 0; }
      }
      return out;
    }
    function cabeca(x, y, ang, cor, tam) {
      c.save(); c.translate(x, y); c.rotate(ang); c.beginPath(); c.moveTo(tam, 0); c.lineTo(-tam * 0.7, tam * 0.75); c.lineTo(-tam * 0.35, 0); c.lineTo(-tam * 0.7, -tam * 0.75); c.closePath();
      c.fillStyle = cor; c.fill(); c.lineWidth = 4; c.strokeStyle = '#FFFFFF'; c.stroke(); c.restore();
    }

    function desenharCena(cn, k, local, alfa) {
      if (alfa <= 0.01) return;
      c.save(); c.globalAlpha = alfa;
      // rota: linha tracejada que anda, com a ponta em seta
      if (cn.rota) {
        const p = U.suave(U.clamp((k - 0.12) / 0.7, 0, 1)), tela = cn.rota.pts.map((q) => proj(q[0], q[1])), feito = polilinha(tela, p);
        c.lineCap = 'round'; c.lineJoin = 'round';
        c.strokeStyle = 'rgba(0,0,0,0.35)'; c.lineWidth = 16; c.beginPath(); feito.forEach((q, j) => (j ? c.lineTo(q[0], q[1] + 4) : c.moveTo(q[0], q[1] + 4))); c.stroke();
        c.setLineDash([26, 16]); c.lineDashOffset = -local * 60; c.strokeStyle = cn.rota.cor; c.lineWidth = 11;
        c.beginPath(); feito.forEach((q, j) => (j ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]))); c.stroke(); c.setLineDash([]);
        const a = feito[feito.length - 1], b = feito[Math.max(0, feito.length - 2)];
        if (feito.length > 1 && p > 0.02) cabeca(a[0], a[1], Math.atan2(a[1] - b[1], a[0] - b[0]), cn.rota.cor, 30);
        const o = tela[0]; c.beginPath(); c.arc(o[0], o[1], 14, 0, U.TAU); c.fillStyle = '#FFFFFF'; c.fill(); c.lineWidth = 6; c.strokeStyle = cn.rota.cor; c.stroke();
        if (cn.rota.rotulo && p > 0.5) rotuloEm(a[0], a[1] - 70, cn.rota.rotulo.toUpperCase(), { fonte: '44px', s: U.mola((p - 0.5) * 3, 10) });
      }
      // setas: o avanco cresce em arco, uma depois da outra
      cn.setas.forEach((s, j) => {
        const p = U.saida(U.clamp((k - 0.08 - j * 0.08) / 0.55, 0, 1)); if (p <= 0) return;
        const a = proj(s.de[0], s.de[1]), b = proj(s.para[0], s.para[1]), dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1;
        const ctl = [a[0] + dx / 2 - (dy / L) * L * 0.22, a[1] + dy / 2 + (dx / L) * L * 0.22];
        const pts = []; for (let q = 0; q <= 24; q++) { const u = (q / 24) * p; pts.push([(1 - u) * (1 - u) * a[0] + 2 * (1 - u) * u * ctl[0] + u * u * b[0], (1 - u) * (1 - u) * a[1] + 2 * (1 - u) * u * ctl[1] + u * u * b[1]]); }
        c.lineCap = 'round'; c.strokeStyle = '#FFFFFF'; c.lineWidth = 30; c.beginPath(); pts.forEach((q, i2) => (i2 ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]))); c.stroke();
        c.strokeStyle = s.cor; c.lineWidth = 20; c.stroke();
        const e = pts[pts.length - 1], f = pts[pts.length - 2]; cabeca(e[0], e[1], Math.atan2(e[1] - f[1], e[0] - f[0]), s.cor, 46);
      });
      // marcadores: alfinete que cai e quica
      cn.marcas.forEach((m, j) => {
        const s = U.mola(local - 0.2 - j * 0.28, 11); if (s <= 0) return;
        const q = proj(m.p[0], m.p[1]);
        c.save(); c.translate(q[0], q[1] - (1 - Math.min(1, s)) * 60);
        c.beginPath(); c.moveTo(0, 0); c.bezierCurveTo(-34, -40, -30, -84, 0, -84); c.bezierCurveTo(30, -84, 34, -40, 0, 0); c.fillStyle = '#E4572E'; c.fill(); c.lineWidth = 5; c.strokeStyle = '#FFFFFF'; c.stroke();
        c.beginPath(); c.arc(0, -58, 11, 0, U.TAU); c.fillStyle = '#FFFFFF'; c.fill(); c.restore();
        if (m.rotulo) rotuloEm(q[0], q[1] - 130, m.rotulo.toUpperCase(), { fonte: '40px', h: 58, s: Math.min(1, s) });
      });
      c.restore();
    }

    function quadro(t) {
      const { i, k, local } = U.cenaEm(spec, t), cn = cenas[i], ant = i > 0 ? cenas[i - 1] : null;
      // camera: vai do foco anterior ao desta cena na primeira metade, depois
      // aproxima devagar (nunca fica parada)
      const A = i > 0 ? cams[i - 1] : { x: cams[0].x, y: cams[0].y, z: cams[0].z * 0.8 }, B = cams[i], q = U.suave(U.clamp(k * 2.2, 0, 1));
      let ax = A.x; if (B.x - ax > 180) ax += 360; if (ax - B.x > 180) ax -= 360;   // o caminho curto pelo Pacifico
      const z = lerpLog(A.z, B.z, q) * (1 + 0.06 * k);
      VIEW = { x: U.lerp(ax, B.x, q), y: U.lerp(A.y, B.y, q), s: (W / 360) * z };
      fundo(t);
      // destaques: os desta cena acendem; os da anterior apagam em 0,4 s
      const dest = {};
      if (ant) { const sai = 1 - U.clamp(local / 0.4, 0, 1); ant.paises.forEach((p) => { dest[p.i] = { cor: p.cor, a: 0.85 * sai }; }); }
      cn.paises.forEach((p, j) => { const ent = U.saida(U.clamp((local - 0.15 - j * 0.12) / 0.45, 0, 1)); const puls = 0.85 + 0.1 * Math.sin(t * 3 + j); dest[p.i] = { cor: p.cor, a: Math.max(dest[p.i] ? dest[p.i].a : 0, ent * puls) }; });
      terra(dest);
      // o que a cena anterior desenhou some junto com a troca de camera
      if (ant) desenharCena(ant, 1, 99, 1 - U.clamp(local / 0.35, 0, 1));
      desenharCena(cn, k, local, 1);
      // nome dos paises acesos (so' os que cabem na tela)
      cn.paises.forEach((p, j) => {
        const P = MUNDO[p.i], b0 = proj(P.b[0], P.b[3]), b1 = proj(P.b[2], P.b[1]); if (Math.abs(b1[0] - b0[0]) < 50 && cn.paises.length > 3) return;
        const s = U.mola(local - 0.35 - j * 0.12, 11); if (s <= 0) return;
        const ctr = proj(P.c[0], P.c[1]); rotuloEm(ctr[0], ctr[1], (p.rotulo || P.n).toUpperCase(), { fonte: '42px', h: 60, s: Math.min(1, s), fundo: 'rgba(19,35,58,0.88)', cor: '#FFFFFF' });
      });
      // vinheta
      const vg = c.createRadialGradient(W / 2, H * 0.45, H * 0.3, W / 2, H * 0.45, H * 0.75); vg.addColorStop(0, 'rgba(0,0,0,0)'); vg.addColorStop(1, 'rgba(0,0,0,0.45)'); c.fillStyle = vg; c.fillRect(0, 0, W, H);
      // o ANO: chip grande; quando muda e os dois sao numeros, conta ate o novo
      const ano = anos[i];
      if (ano) {
        const velho = i > 0 ? anos[i - 1] : null, nA = parseInt(velho, 10), nB = parseInt(ano, 10);
        let txt = ano;
        if (velho && velho !== ano && Number.isFinite(nA) && Number.isFinite(nB) && /^\d+$/.test(String(nA)) && local < 0.9) txt = String(Math.round(U.lerp(nA, nB, U.suave(local / 0.9)))) + String(ano).replace(/^\d+/, '');
        const s = velho === ano ? 1 : U.mola(local, 9);
        // enquanto o cartaz do 1o segundo esta na tela, o ano fica embaixo dele
        const yAno = U.lerp(560, 330, U.suave(U.clamp((t - 3.0) / 0.5, 0, 1)));
        c.save(); c.translate(W / 2, yAno); c.scale(0.8 + 0.2 * s, 0.8 + 0.2 * s); c.font = '110px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        const w = c.measureText(txt).width + 80; U.rr(c, -w / 2, -72, w, 144, 30); c.fillStyle = '#F2A541'; c.fill(); c.lineWidth = 8; c.strokeStyle = '#13233A'; c.stroke();
        c.fillStyle = '#13233A'; c.fillText(txt, 0, 8); c.restore();
      }
      if (cn.hud && typeof cn.hud !== 'object' && local > 0.3) {
        const s = U.mola(local - 0.3, 10); c.save(); c.translate(W / 2, H * 0.6); c.scale(s, s); c.font = '120px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        const txt = U.hud(c, cn.hud, c.canvas.width * 0.84 - 70, 22), w = c.measureText(txt).width + 70; U.rr(c, -w / 2, -78, w, 156, 34); c.fillStyle = '#13233A'; c.fill(); c.fillStyle = '#F2A541'; c.fillText(txt, 0, 6); c.restore();
      }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 150, fundo: '#F2A541', borda: '#13233A', cor: '#13233A', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '100px "Lilita One", sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#F2A541', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro };
  }
  MOTORES.mapa = { criar };
})();
