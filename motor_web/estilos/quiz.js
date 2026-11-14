// QUIZ -- "ache o diferente" (22/10; v2 23/10; v3 13/11 -- REDESENHO T503, ordem do dono:
// "pegue o nosso melhor canal (ODD ONE OUT) e redesenhe completamente o motor").
// Uma grade de itens iguais com UM diferente; cronometro; no fim do tempo o
// diferente e' revelado. Cada cena e' um nivel, cada vez mais dificil.
//
// cena: { texto (rotulo: "LEVEL 1", "ONLY 1% SEE IT"), tipo, base, diferente,
//         colunas: 4..12, linhas: 5..16, dur_s, cor?, dificuldade: 1..5,
//         legenda? (frase do alto durante o nivel) }
//   tipo "letras"  base/diferente = 1 a 3 caracteres parecidos (O/Q, 8/B, rn/m)
//   tipo "formas"  base = uma de FORMAS; diferente = girado|espelhado|maior|menor|sem_pedaco|cor
//   tipo "icones"  base = um de ICONES;  diferente = idem (relogio: "hora" muda o ponteiro)
//   tipo "cores"   base = forma ou icone; o diferente e' um tom mais claro/escuro
// spec.legendas? = [abertura, nivel 2, ..., final]  (opcional; sem ela o motor usa as frases
//   entre aspas simples da `metadados.premissa` -- o roteiro ja' as escreve -- ou frases padrao do idioma)
//
// O QUE A v3 MUDOU (folhas antes/depois em /var/lib/videos-auto/motores-plano/quiz/v3/):
//  E1 (ERRO) "sem_pedaco" e os furos dos icones (chave, peixe, casa, olho, gato) usavam
//     destination-out: o furo atravessava o cartao e mostrava o FUNDO colorido -- o diferente
//     ficava amarelo no meio da grade e o nivel nao tinha desafio. Agora o furo e' pintado
//     com a cor do cartao (opaco).
//  E2 (ERRO) as frases que o roteiro promete na premissa ("If you blink...", "But now, look
//     closer", "How many did you catch?") nunca apareciam: o motor nao tinha onde escreve-las.
//     Agora ha' uma LEGENDA no alto (faixa livre depois do cartaz do titulo).
//  E3 (ERRO) "FOUND IT?" encavalava no rotulo ("MYTHIC FOUND IT?"); virou legenda.
//  E4 (ERRO) a resposta era um circulo fino de ~40 px numa grade 12x16 -- invisivel no
//     celular. Agora: holofote (o resto do cartao escurece), anel que pulsa e o diferente
//     AMPLIADO 2,2x no lugar -- a recompensa do video e' ver o que nao se achou.
//  R1 retencao: placar de progresso "2/4" + barrinhas dos niveis (quem chegou ao 3 fica para o 4),
//     cronometro com anel que esvazia e treme nos 2 ultimos segundos, entrada de nivel com mola.
//  R2 fim: o ultimo nivel termina pedindo o placar nos comentarios ("How many did you get? _/4").
//  D1 detalhe: fundo com listras e vinheta, cartao com sombra, itens com sombra curta.
// O som (montar_web.py: um tique por segundo a partir de ini+0,35 e "plim" em fim-1,3) e o
// contrato do spec NAO mudaram: REVELA continua 1,3 s.
(function () {
  'use strict';
  const TAU = Math.PI * 2;
  // cor do cartao em uso: os "furos" dos desenhos sao pintados com ela (E1)
  let PAPEL = '#FFFFFF';
  const furo = (c, pintar) => { c.save(); c.shadowColor = 'transparent'; c.fillStyle = PAPEL; c.strokeStyle = PAPEL; pintar(); c.restore(); };
  // desenhos num quadrado -1..1, com a cor atual
  const FORMAS = {
    circulo: (c) => { c.beginPath(); c.arc(0, 0, 0.85, 0, TAU); c.fill(); },
    quadrado: (c) => { c.fillRect(-0.78, -0.78, 1.56, 1.56); },
    triangulo: (c) => { c.beginPath(); c.moveTo(0, -0.9); c.lineTo(0.85, 0.75); c.lineTo(-0.85, 0.75); c.closePath(); c.fill(); },
    estrela: (c) => { c.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + (i * Math.PI) / 5, r = i % 2 ? 0.4 : 0.92; c.lineTo(Math.cos(a) * r, Math.sin(a) * r); } c.closePath(); c.fill(); },
    coracao: (c) => { c.beginPath(); c.moveTo(0, 0.85); c.bezierCurveTo(-1.2, 0, -0.75, -1, 0, -0.4); c.bezierCurveTo(0.75, -1, 1.2, 0, 0, 0.85); c.fill(); },
    hexagono: (c) => { c.beginPath(); for (let i = 0; i < 6; i++) { const a = (i * TAU) / 6; c.lineTo(Math.cos(a) * 0.88, Math.sin(a) * 0.88); } c.closePath(); c.fill(); },
    lua: (c) => { c.beginPath(); c.arc(0, 0, 0.85, Math.PI * 0.3, Math.PI * 1.7); c.arc(0.35, 0, 0.62, Math.PI * 1.55, Math.PI * 0.45, true); c.closePath(); c.fill(); },
    gota: (c) => { c.beginPath(); c.moveTo(0, -0.95); c.bezierCurveTo(0.2, -0.5, 0.75, 0, 0.7, 0.3); c.arc(0, 0.3, 0.7, 0, Math.PI); c.bezierCurveTo(-0.75, 0, -0.2, -0.5, 0, -0.95); c.fill(); },
    seta: (c) => { c.beginPath(); c.moveTo(0.9, 0); c.lineTo(0.1, -0.75); c.lineTo(0.1, -0.3); c.lineTo(-0.85, -0.3); c.lineTo(-0.85, 0.3); c.lineTo(0.1, 0.3); c.lineTo(0.1, 0.75); c.closePath(); c.fill(); },
    raio: (c) => { c.beginPath(); c.moveTo(0.2, -0.95); c.lineTo(-0.55, 0.1); c.lineTo(-0.05, 0.1); c.lineTo(-0.25, 0.95); c.lineTo(0.6, -0.15); c.lineTo(0.08, -0.15); c.closePath(); c.fill(); },
    cruz: (c) => { c.fillRect(-0.28, -0.85, 0.56, 1.7); c.fillRect(-0.85, -0.28, 1.7, 0.56); },
  };
  const ICONES = {
    chave: (c) => { c.beginPath(); c.arc(-0.45, 0, 0.38, 0, TAU); c.fill(); c.fillRect(-0.1, -0.12, 0.95, 0.24); c.fillRect(0.55, 0.1, 0.14, 0.3); c.fillRect(0.3, 0.1, 0.14, 0.22);
      furo(c, () => { c.beginPath(); c.arc(-0.45, 0, 0.15, 0, TAU); c.fill(); }); },
    peixe: (c) => { c.beginPath(); c.ellipse(-0.1, 0, 0.62, 0.38, 0, 0, TAU); c.fill(); c.beginPath(); c.moveTo(0.4, 0); c.lineTo(0.9, -0.38); c.lineTo(0.9, 0.38); c.closePath(); c.fill();
      furo(c, () => { c.beginPath(); c.arc(-0.42, -0.08, 0.08, 0, TAU); c.fill(); }); },
    maca: (c) => { c.beginPath(); c.arc(-0.28, 0.12, 0.5, 0, TAU); c.arc(0.28, 0.12, 0.5, 0, TAU); c.fill(); c.fillRect(-0.05, -0.75, 0.1, 0.35); c.beginPath(); c.ellipse(0.25, -0.6, 0.22, 0.1, -0.5, 0, TAU); c.fill(); },
    casa: (c) => { c.beginPath(); c.moveTo(0, -0.9); c.lineTo(0.9, -0.05); c.lineTo(-0.9, -0.05); c.closePath(); c.fill(); c.fillRect(-0.62, -0.05, 1.24, 0.9);
      furo(c, () => c.fillRect(-0.15, 0.35, 0.3, 0.5)); },
    guarda_chuva: (c) => { c.beginPath(); c.arc(0, 0, 0.88, Math.PI, 0); c.closePath(); c.fill(); c.fillRect(-0.05, 0, 0.1, 0.7); c.lineWidth = 0.1; c.beginPath(); c.arc(-0.15, 0.7, 0.15, 0, Math.PI); c.stroke(); },
    relogio: (c, v) => { c.lineWidth = 0.14; c.beginPath(); c.arc(0, 0, 0.8, 0, TAU); c.stroke(); const h = (v && v.hora != null ? v.hora : 3);
      c.lineWidth = 0.12; c.lineCap = 'round'; c.beginPath(); c.moveTo(0, 0); c.lineTo(Math.cos((h / 12) * TAU - Math.PI / 2) * 0.42, Math.sin((h / 12) * TAU - Math.PI / 2) * 0.42); c.stroke();
      c.beginPath(); c.moveTo(0, 0); c.lineTo(0, -0.62); c.stroke(); },
    olho: (c) => { c.beginPath(); c.moveTo(-0.95, 0); c.quadraticCurveTo(0, -0.85, 0.95, 0); c.quadraticCurveTo(0, 0.85, -0.95, 0); c.fill();
      furo(c, () => { c.beginPath(); c.arc(0, 0, 0.34, 0, TAU); c.fill(); }); c.beginPath(); c.arc(0.06, 0, 0.17, 0, TAU); c.fill(); },
    lampada: (c) => { c.beginPath(); c.arc(0, -0.25, 0.6, Math.PI * 0.8, Math.PI * 2.2); c.lineTo(0.25, 0.55); c.lineTo(-0.25, 0.55); c.closePath(); c.fill(); c.fillRect(-0.25, 0.62, 0.5, 0.14); c.fillRect(-0.18, 0.82, 0.36, 0.12); },
    foguete: (c) => { c.beginPath(); c.moveTo(0, -1); c.quadraticCurveTo(0.5, -0.4, 0.35, 0.5); c.lineTo(-0.35, 0.5); c.quadraticCurveTo(-0.5, -0.4, 0, -1); c.fill();
      c.beginPath(); c.moveTo(-0.35, 0.2); c.lineTo(-0.7, 0.75); c.lineTo(-0.3, 0.55); c.moveTo(0.35, 0.2); c.lineTo(0.7, 0.75); c.lineTo(0.3, 0.55); c.fill(); },
    nota_musical: (c) => { c.beginPath(); c.ellipse(-0.3, 0.55, 0.32, 0.24, -0.4, 0, TAU); c.fill(); c.fillRect(-0.02, -0.85, 0.12, 1.4); c.beginPath(); c.moveTo(0.1, -0.85); c.quadraticCurveTo(0.7, -0.6, 0.55, -0.1); c.quadraticCurveTo(0.5, -0.45, 0.1, -0.5); c.fill(); },
    gato: (c) => { c.beginPath(); c.arc(0, 0.15, 0.68, 0, TAU); c.fill(); c.beginPath(); c.moveTo(-0.62, -0.1); c.lineTo(-0.5, -0.9); c.lineTo(-0.12, -0.5); c.moveTo(0.62, -0.1); c.lineTo(0.5, -0.9); c.lineTo(0.12, -0.5); c.fill();
      furo(c, () => { c.beginPath(); c.ellipse(-0.25, 0.05, 0.1, 0.16, 0, 0, TAU); c.ellipse(0.25, 0.05, 0.1, 0.16, 0, 0, TAU); c.fill(); }); },
  };

  function rgb(hex) {
    let h = String(hex).replace('#', ''); if (h.length === 3) h = h.split('').map((x) => x + x).join('');
    const n = parseInt(h, 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function clarear(hex, f) {   // f>0 clareia, f<0 escurece
    const ch = rgb(hex).map((v) => Math.round(f > 0 ? v + (255 - v) * f : v * (1 + f)));
    return 'rgb(' + ch.join(',') + ')';
  }
  function misturar(a, b, k) { const x = rgb(a), y = rgb(b); return 'rgb(' + x.map((v, i) => Math.round(v + (y[i] - v) * k)).join(',') + ')'; }

  // FRASES PADRAO da legenda (E2), por idioma: abertura, escalada entre niveis, revelacao, fim
  const FRASES = {
    en: { abre: 'Find the odd one out', sobe: ['Now look closer', 'It gets harder', "Don't blink", 'Most people quit here'], ultimo: 'Final level',
      achou: 'Found it?', fim: 'How many did you get? _/N',
      cta: { placar: 'Comment your score', like: 'Like if you got N/N', inscr: 'Subscribe', inscrito: 'Subscribed', sub: 'New levels every day' } },
    es: { abre: 'Encuentra el diferente', sobe: ['Ahora mira mejor', 'Se pone difícil', 'No parpadees', 'Casi todos fallan aquí'], ultimo: 'Último nivel',
      achou: '¿Lo viste?', fim: '¿Cuántos encontraste? _/N',
      cta: { placar: 'Comenta tu puntaje', like: 'Like si sacaste N/N', inscr: 'Suscríbete', inscrito: 'Suscrito', sub: 'Niveles nuevos cada día' } },
    pt: { abre: 'Ache o diferente', sobe: ['Agora olhe melhor', 'Fica mais difícil', 'Não pisque', 'Quase todos erram aqui'], ultimo: 'Último nível',
      achou: 'Achou?', fim: 'Quantos você achou? _/N',
      cta: { placar: 'Comente sua nota', like: 'Curta se fez N/N', inscr: 'Inscreva-se', inscrito: 'Inscrito', sub: 'Níveis novos todo dia' } },
  };

  function criar(tela, spec, U) {
    const c = tela.getContext('2d'); const W = spec.w, H = spec.h;
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const FUNDOS = ['#FFD23F', '#3EC1F3', '#7CFF8A', '#FF8FB1', '#B07CFF', '#FF9F45'];
    const TINTAS = ['#1B1B2F', '#C0392B', '#1F6FEB', '#11823B', '#7B2CBF', '#B35C00'];
    const REVELA = 1.3;   // segundos finais de cada nivel: a resposta (o "plim" do som cai aqui)
    const FONTE = '"Lilita One", sans-serif';
    const N = spec.cenas.length;
    // o cartao da grade: dentro da zona segura (botoes do app a direita, legenda do app embaixo de 1440)
    // 14/11 (dono: "legendas e imagens nao estao centralizadas"): o cartao ia de 50 a W-185 (centro em 43% da
    // largura, fugindo dos botoes do app). Agora e' simetrico; os botoes do app ficam sobre a borda do fundo.
    const GX0 = 64, GX1 = W - 64, GY0 = 500, GY1 = 1440, CX = (GX0 + GX1) / 2, PAD = 18;
    // MAIS DIFICIL (23/10, pedido do dono): a grade e a sutileza tem um PISO que sobe a cada nivel.
    // SIMETRIA: girar um circulo, girar 90 graus um quadrado ou espelhar um coracao nao muda nada.
    const GIRO_INVISIVEL = { circulo: 1 }, ESPELHO_INVISIVEL = { circulo: 1, quadrado: 1, cruz: 1, hexagono: 1, estrela: 1, coracao: 1, gota: 1, triangulo: 1,
      casa: 1, guarda_chuva: 1, lampada: 1, foguete: 1, maca: 0 };
    const niveis = spec.cenas.map((cn, i) => {
      const r = U.rng((spec.semente || 'quiz') + ':' + i);
      const col = Math.max(Math.round(num(cn.colunas, 4, 12, 6)), Math.min(10, 6 + i)), lin = Math.max(Math.round(num(cn.linhas, 5, 16, 9)), Math.min(16, 9 + 2 * i));
      let tipo = ['letras', 'formas', 'icones', 'cores'].includes(cn.tipo) ? cn.tipo : 'letras';
      const desenho = FORMAS[cn.base] || ICONES[cn.base];
      if (tipo !== 'letras' && !desenho) tipo = 'letras';
      const dif = Math.max(num(cn.dificuldade, 1, 5, 1 + Math.min(4, i)), Math.min(5, 2 + i));
      let modo = String(cn.diferente || (tipo === 'letras' ? 'Q' : 'girado')).slice(0, 14);
      if (tipo !== 'letras') {
        if (modo === 'girado' && GIRO_INVISIVEL[cn.base]) modo = 'sem_pedaco';
        if (modo === 'espelhado' && ESPELHO_INVISIVEL[cn.base]) modo = GIRO_INVISIVEL[cn.base] ? 'sem_pedaco' : 'girado';
        if (modo === 'hora' && cn.base !== 'relogio') modo = 'girado';
      }
      const fundo = corOk(cn.cor, FUNDOS[i % FUNDOS.length]);
      const nv = { col, lin, tipo, base: String(cn.base || 'O').slice(0, 14), dif: modo, desenho, nivelDif: dif,
        alvo: Math.floor(r() * col * lin), fundo, tinta: TINTAS[i % TINTAS.length], papel: misturar(fundo, '#FFFFFF', 0.9),
        rotulo: String(cn.texto || 'LEVEL ' + (i + 1)).toUpperCase().slice(0, 24) };
      // posicoes FIXAS de cada celula (a revelacao acha o diferente sem reproduzir o sorteio)
      const cw = (GX1 - GX0 - 2 * PAD) / col, ch = (GY1 - GY0 - 2 * PAD) / lin;
      // CAMUFLAGEM (23/10): da dificuldade 3 em diante os itens tremem de lugar; o diferente nao "salta"
      const rj = U.rng((spec.semente || 'quiz') + ':j' + i), tremor = dif >= 3 ? (dif - 2) * 0.05 : 0;
      nv.cw = cw; nv.ch = ch; nv.tam = Math.floor(Math.min(cw * 0.84, ch * 0.84));
      nv.pos = [];
      for (let k = 0; k < col * lin; k++) {
        const jx = (rj() - 0.5) * 2 * tremor * cw, jy = (rj() - 0.5) * 2 * tremor * ch, jc = rj();
        nv.pos.push({ x: GX0 + PAD + (k % col + 0.5) * cw + jx, y: GY0 + PAD + (Math.floor(k / col) + 0.5) * ch + jy, tom: jc });
      }
      return nv;
    });

    // ---- LEGENDA DO ALTO (E2): spec.legendas > frases entre aspas da premissa > padrao do idioma
    const lingua = /^es/i.test(spec.idioma || '') ? 'es' : /^pt/i.test(spec.idioma || '') ? 'pt' : 'en';
    const F = FRASES[lingua];
    let roteiro = Array.isArray(spec.legendas) ? spec.legendas.map(String) : null;
    // 14/11: a premissa e' nota interna (muitas vezes em portugues) -- legendas em PT apareciam no canal em ingles.
    // So' spec.legendas, cena.legenda ou o padrao do idioma.
    if (false) {
      const prem = String((spec.metadados && spec.metadados.premissa) || '');
      const aspas = [...prem.matchAll(/['‘’"“”]([^'‘’"“”]{4,42})['‘’"“”]/g)].map((m) => m[1].trim())
        .filter((s) => /[a-zA-ZÀ-ÿ]/.test(s) && !/[{}<>]/.test(s));
      if (aspas.length >= 2) roteiro = aspas;
    }
    const TITULO_ATE = 2.5;
    const curto0 = !!spec.titulo && (spec.cenas[0].fim - spec.cenas[0].ini) - REVELA - TITULO_ATE < 0.8;
    const legendaNivel = (i) => {
      const cn = spec.cenas[i];
      if (cn.legenda) return String(cn.legenda);
      if (roteiro) {
        // abertura no nivel 1; as frases do meio nos niveis seguintes; a ultima frase e' o fim.
        // Nivel 1 curto (o cartaz do titulo ocupa o alto ate' a revelacao): a abertura passa para o nivel 2.
        const lista = [roteiro[0]].concat(roteiro.slice(1, roteiro.length > 2 ? -1 : undefined));
        const k = curto0 ? i - 1 : i;
        if (k >= 0 && k < lista.length) return lista[k];
      }
      return padrao[i];
    };
    // padrao (E10): nunca repete o rotulo do nivel ("LOOK CLOSER" sob "NOW LOOK CLOSER", "FINAL LEVEL" sob
    // "FINAL ROUND") nem a frase de um nivel anterior
    const palavras = (x) => String(x).toUpperCase().split(/[^A-Z0-9À-Ý%]+/).filter((w) => w.length >= 4 || /%/.test(w));
    const usadas = new Set();
    const padrao = niveis.map((nv, i) => {
      const rot = new Set(palavras(nv.rotulo));
      const ok = (f) => !usadas.has(f) && !palavras(f).some((w) => rot.has(w));
      const fila = i === 0 ? [F.abre, ...F.sobe] : i === N - 1 && N > 2 ? [F.ultimo, ...F.sobe] : F.sobe.slice((i - 1) % F.sobe.length).concat(F.sobe);
      const f = fila.find(ok) || '';
      usadas.add(f); return f;
    });
    const legendaFim = () => {
      if (roteiro && roteiro.length >= 3 && /\?\s*$/.test(roteiro[roteiro.length - 1])) return roteiro[roteiro.length - 1] + ' _/' + N;
      return F.fim.replace('N', String(N));
    };

    // ---- camadas fixas por nivel: fundo (listras + vinheta) e cartao com a grade (D1)
    const camadas = new Map();
    function fundoDe(nv) {
      return U.camada(W, H, (g) => {
        g.fillStyle = nv.fundo; g.fillRect(0, 0, W, H);
        g.save(); g.globalAlpha = 0.10; g.fillStyle = '#FFFFFF'; g.translate(W / 2, H / 2); g.rotate(-0.42);
        for (let x = -H; x < H; x += 120) g.fillRect(x, -H, 52, 2 * H);
        g.restore();
        const v = g.createRadialGradient(W / 2, H * 0.48, H * 0.25, W / 2, H * 0.5, H * 0.75);
        v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,0.22)'); g.fillStyle = v; g.fillRect(0, 0, W, H);
      });
    }
    function desenharItem(g, nv, k, cx, cy, tam, forcarOdd) {
      const odd = forcarOdd || k === nv.alvo;
      if (nv.tipo === 'letras') { g.fillText(odd ? nv.dif : nv.base, cx, cy); return; }
      const e = tam / 2.1, d = nv.nivelDif;
      g.save(); g.translate(cx, cy);
      let cor = nv.tinta;
      if (nv.tipo === 'cores' && d >= 4 && !odd) cor = clarear(nv.tinta, (nv.pos[k].tom - 0.5) * 0.05);
      let v = null;
      if (odd) {
        const m = nv.tipo === 'cores' ? 'cor' : nv.dif;
        if (m === 'girado') g.rotate(((6 + 34 * (5 - d) / 4) * Math.PI) / 180);   // 40 graus facil, 6 graus dificil
        else if (m === 'espelhado') g.scale(-1, 1);
        else if (m === 'maior') g.scale(1 + 0.26 / d, 1 + 0.26 / d);
        else if (m === 'menor') g.scale(1 - 0.24 / d, 1 - 0.24 / d);
        else if (m === 'cor') cor = clarear(nv.tinta, 0.36 / d);
        else if (m === 'hora') v = { hora: 3 + Math.max(1, 6 - d) };
      }
      g.fillStyle = g.strokeStyle = cor;
      g.scale(e, e);
      nv.desenho(g, v);
      if (odd && nv.dif === 'sem_pedaco' && nv.tipo !== 'cores') {   // corte em cunha pintado com o papel (E1)
        furo(g, () => { g.beginPath(); g.moveTo(0, 0); g.arc(0, 0, 1.2, -0.25 * (6 - d) / 5 - 0.12, 0.25 * (6 - d) / 5 + 0.12); g.closePath(); g.fill(); });
      }
      g.restore();
    }
    function cartaoDe(nv) {
      return U.camada(W, H, (g) => {
        g.save(); g.shadowColor = 'rgba(0,0,0,0.28)'; g.shadowBlur = 36; g.shadowOffsetY = 14;
        U.rr(g, GX0, GY0, GX1 - GX0, GY1 - GY0, 34); g.fillStyle = nv.papel; g.fill(); g.restore();
        g.lineWidth = 5; g.strokeStyle = 'rgba(17,17,27,0.85)'; U.rr(g, GX0, GY0, GX1 - GX0, GY1 - GY0, 34); g.stroke();
        PAPEL = nv.papel;
        g.save(); g.font = nv.tam + 'px ' + FONTE; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = nv.tipo === 'letras' ? '#1B1B2F' : nv.tinta;
        // sombra curta nos itens: da' volume sem borrar a diferenca
        g.shadowColor = 'rgba(0,0,0,0.18)'; g.shadowBlur = Math.max(1, nv.tam * 0.05); g.shadowOffsetY = Math.max(1, nv.tam * 0.05);
        for (let k = 0; k < nv.col * nv.lin; k++) desenharItem(g, nv, k, nv.pos[k].x, nv.pos[k].y, nv.tam);
        g.restore();
      });
    }
    function camadasDe(i) {
      if (!camadas.has(i)) { if (camadas.size > 2) camadas.delete(camadas.keys().next().value); camadas.set(i, { fundo: fundoDe(niveis[i]), cartao: cartaoDe(niveis[i]) }); }
      return camadas.get(i);
    }

    // texto com contorno grosso (estilo do nicho: branco, borda preta)
    function contornado(txt, x, y, px, maxW, cor) {
      c.font = px + 'px ' + FONTE; c.letterSpacing = Math.round(px * 0.04) + 'px'; c.lineJoin = 'round'; c.lineWidth = Math.max(8, px * 0.2); c.strokeStyle = '#111';
      c.strokeText(txt, x, y, maxW); c.fillStyle = cor || '#FFF'; c.fillText(txt, x, y, maxW);
    }
    function legenda(txt, desde, t) {
      if (!txt) return;
      const pop = U.mola(t - desde, 12);
      if (pop <= 0) return;
      c.save(); c.textAlign = 'center'; c.textBaseline = 'middle'; c.font = '78px ' + FONTE;
      const lay = U.textoAjustado(c, txt.toUpperCase(), 860, 190, 46);
      const px = lay.px, lh = px * 1.12, y0 = 225 - ((lay.linhas.length - 1) * lh) / 2;
      c.translate(CX, 225); c.scale(0.8 + 0.2 * pop, 0.8 + 0.2 * pop); c.translate(-CX, -225); c.globalAlpha = U.clamp(pop * 1.5, 0, 1);
      lay.linhas.forEach((l, k) => contornado(l, CX, y0 + k * lh, px, 900));
      c.restore();
    }
    function placar(i, nv, t, local) {
      // badge "2/4" + rotulo do nivel; barrinhas de progresso embaixo (R1)
      c.save(); c.textBaseline = 'middle'; c.textAlign = 'left';
      const y = 405, bx = GX0;
      c.font = '50px ' + FONTE; const tb = (i + 1) + '/' + N, wb = c.measureText(tb).width + 40;
      U.rr(c, bx, y - 36, wb, 72, 36); c.fillStyle = '#111'; c.fill(); c.fillStyle = '#FFF'; c.fillText(tb, bx + 20, y + 3);
      c.font = '70px ' + FONTE; const maxR = GX1 - 190 - (bx + wb + 22);
      contornado(nv.rotulo, bx + wb + 22, y + 4, 70, maxR, '#FFF');
      // barrinhas: feitas = escuras com tique, atual = branca, futuras = vazadas
      const bw = (GX1 - GX0 - (N - 1) * 10) / N, by = y + 52;
      for (let k = 0; k < N; k++) {
        const x = GX0 + k * (bw + 10); U.rr(c, x, by, bw, 12, 6);
        if (k < i) { c.fillStyle = '#111'; c.fill(); }
        else if (k === i) { c.fillStyle = 'rgba(17,17,17,0.25)'; c.fill(); const dur = nv._dur; const p = U.clamp(local / Math.max(0.1, dur - REVELA), 0, 1);
          U.rr(c, x, by, Math.max(12, bw * p), 12, 6); c.fillStyle = '#111'; c.fill(); }
        else { c.fillStyle = 'rgba(255,255,255,0.55)'; c.fill(); }
      }
      c.restore();
    }
    function cronometro(resta, total) {
      // anel que esvazia + numero; vermelho e tremendo nos 2 ultimos segundos (R1)
      const seg = Math.ceil(resta), urg = seg <= 2, pulso = 1 + 0.12 * Math.max(0, 1 - (resta % 1) * 4);
      const tre = urg ? Math.sin(resta * 60) * 4 : 0;
      c.save(); c.translate(GX1 - 70 + tre, 405); c.scale(pulso, pulso);
      c.beginPath(); c.arc(0, 0, 64, 0, TAU); c.fillStyle = urg ? '#E2373C' : '#111'; c.fill();
      c.lineWidth = 10; c.lineCap = 'round'; c.strokeStyle = 'rgba(255,255,255,0.25)'; c.beginPath(); c.arc(0, 0, 50, 0, TAU); c.stroke();
      c.strokeStyle = '#FFF'; c.beginPath(); c.arc(0, 0, 50, -Math.PI / 2, -Math.PI / 2 + TAU * U.clamp(resta / Math.max(0.1, total), 0, 1)); c.stroke();
      c.font = '64px ' + FONTE; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillStyle = '#FFF'; c.fillText(String(seg), 0, 5);
      c.restore();
    }
    function revelar(nv, depois) {
      // holofote: o cartao escurece menos num circulo em volta do diferente; anel; o diferente ampliado (E4)
      const p = nv.pos[nv.alvo], q = U.mola(depois, 9), r0 = Math.max(nv.cw, nv.ch) * 0.75, amp = Math.max(2.2, 150 / nv.tam);
      const raio = Math.max(r0, (nv.tam * amp) / 2 + 26);
      const ent = U.saida(U.clamp(depois / 0.25, 0, 1));
      c.save();
      c.beginPath(); U.rr(c, GX0, GY0, GX1 - GX0, GY1 - GY0, 34); c.moveTo(p.x + raio * q, p.y); c.arc(p.x, p.y, Math.max(1, raio * q), 0, TAU, true);
      c.fillStyle = 'rgba(17,17,27,' + (0.62 * ent) + ')'; c.fill('evenodd');
      // o diferente grande, sobre um disco de papel (o que nao se achou, de perto)
      const s = 1 + (amp - 1) * U.clamp(q, 0, 1.15);
      c.beginPath(); c.arc(p.x, p.y, Math.max(1, (raio - 8) * q), 0, TAU); c.fillStyle = nv.papel; c.fill();
      PAPEL = nv.papel;
      c.font = Math.round(nv.tam * s) + 'px ' + FONTE; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillStyle = nv.tipo === 'letras' ? '#1B1B2F' : nv.tinta;
      if (nv.tipo === 'letras') c.fillText(nv.dif, p.x, p.y); else desenharItem(c, nv, nv.alvo, p.x, p.y, nv.tam * s, true);
      const pul = 1 + 0.05 * Math.sin(depois * 14);
      c.lineWidth = 14; c.strokeStyle = '#E2373C'; c.beginPath(); c.arc(p.x, p.y, Math.max(1, raio * q * pul), 0, TAU); c.stroke();
      c.lineWidth = 5; c.strokeStyle = '#FFF'; c.beginPath(); c.arc(p.x, p.y, Math.max(1, (raio * q * pul) + 10), 0, TAU); c.stroke();
      c.restore();
    }

    // ---- ENCERRAMENTO (T503, 13/11, ordem do dono): o canal tem a maior retencao da casa e poucos likes,
    // comentarios e inscritos. Os ultimos `spec.cta_s` segundos (montar_web.py: CTA_QUIZ_S) viram uma tela de
    // conversao: placar nos comentarios (botoes 0..N -- responder e' digitar um numero), like e inscrever
    // (o botao e' "apertado" e vira INSCRITO). Sem `cta_s` (spec antigo) nada muda.
    const CTA = num(spec.cta_s, 0, 6, 0);
    function coracao(x, y, r, cor) {
      c.save(); c.translate(x, y); c.scale(r, r); c.beginPath(); c.moveTo(0, 0.85); c.bezierCurveTo(-1.2, 0, -0.75, -1, 0, -0.4);
      c.bezierCurveTo(0.75, -1, 1.2, 0, 0, 0.85); c.fillStyle = cor; c.fill(); c.restore();
    }
    function sino(x, y, r) {
      c.save(); c.translate(x, y); c.scale(r, r); c.fillStyle = '#FFF'; c.beginPath(); c.moveTo(-0.7, 0.45); c.quadraticCurveTo(-0.6, 0.3, -0.6, -0.1);
      c.quadraticCurveTo(-0.6, -0.75, 0, -0.78); c.quadraticCurveTo(0.6, -0.75, 0.6, -0.1); c.quadraticCurveTo(0.6, 0.3, 0.7, 0.45); c.closePath(); c.fill();
      c.beginPath(); c.arc(0, 0.6, 0.18, 0, TAU); c.fill(); c.restore();
    }
    function botao(x, y, w, h, fundo, borda) {
      U.rr(c, x - w / 2, y - h / 2, w, h, h / 2); c.fillStyle = fundo; c.fill(); if (borda) { c.lineWidth = 6; c.strokeStyle = borda; c.stroke(); }
    }
    function encerramento(u, nv) {
      const T = F.cta;
      c.save(); c.globalAlpha = U.clamp(u / 0.25, 0, 1) * 0.72; c.fillStyle = '#11111B'; c.fillRect(0, 300, W, H - 300); c.restore();
      const pop = (k) => U.clamp(U.mola(u - 0.1 - 0.35 * k, 11), 0, 1.2);
      c.save(); c.textAlign = 'center'; c.textBaseline = 'middle';
      // 1) placar: titulo + botoes 0..N
      let p = pop(0);
      if (p > 0) {
        c.save(); c.translate(CX, 640); c.scale(p, p); c.translate(-CX, -640);
        contornado(T.placar.toUpperCase(), CX, 560, 74, 880, '#FFF');
        const n = N + 1, bw = Math.min(150, (GX1 - GX0 - 20 * (n - 1)) / n), x0 = CX - ((n - 1) * (bw + 20)) / 2;
        for (let k = 0; k < n; k++) {
          const x = x0 + k * (bw + 20), destaque = k === N, pulso = destaque ? 1 + 0.06 * Math.sin(u * 9) : 1;
          c.save(); c.translate(x, 700); c.scale(pulso, pulso);
          c.beginPath(); c.arc(0, 0, bw / 2, 0, TAU); c.fillStyle = destaque ? '#FFD23F' : '#FFF'; c.fill(); c.lineWidth = 6; c.strokeStyle = '#111'; c.stroke();
          c.font = Math.round(bw * 0.55) + 'px ' + FONTE; c.fillStyle = '#111'; c.fillText(String(k), 0, 4); c.restore();
        }
        // seta para baixo: "responde ai"
        const dy = 10 * Math.sin(u * 8);
        c.beginPath(); c.moveTo(CX - 34, 800 + dy); c.lineTo(CX + 34, 800 + dy); c.lineTo(CX, 850 + dy); c.closePath(); c.fillStyle = '#FFF'; c.fill();
        c.restore();
      }
      // 2) like
      p = pop(1);
      if (p > 0) {
        c.save(); c.translate(CX, 990); c.scale(p, p); c.translate(-CX, -990);
        botao(CX, 990, 760, 130, '#FFF', '#111');
        coracao(CX - 300, 994, 46 * (1 + 0.12 * Math.max(0, Math.sin(u * 7))), '#E2373C');
        c.font = '60px ' + FONTE; c.fillStyle = '#111'; c.textAlign = 'left'; c.fillText(T.like.replace(/N/g, String(N)).toUpperCase(), CX - 240, 996, 560);
        c.restore();
      }
      // 3) inscrever: o botao e' "apertado" 0,7 s depois de aparecer e vira INSCRITO
      p = pop(2);
      if (p > 0) {
        const aperto = u - 0.8 - 0.7, apertado = aperto > 0, s = apertado && aperto < 0.18 ? 0.92 : 1;
        c.save(); c.translate(CX, 1180); c.scale(p * s, p * s); c.translate(-CX, -1180);
        botao(CX, 1180, 760, 140, apertado ? '#3A3A44' : '#E2373C', '#111');
        sino(CX - 290, 1180, 44);
        c.font = '66px ' + FONTE; c.fillStyle = '#FFF'; c.textAlign = 'left';
        c.fillText((apertado ? T.inscrito : T.inscr).toUpperCase(), CX - 230, 1184, 540);
        c.restore();
        c.save(); c.textAlign = 'center'; contornado(T.sub.toUpperCase(), CX, 1310, 52, 860, '#FFF'); c.restore();
        // dedo que aperta (um circulo branco com sombra, como o toque na tela)
        if (u > 0.8 + 0.35 && u < 0.8 + 1.4) {
          const k = U.clamp((u - 1.15) / 0.35, 0, 1), x = CX + 260 + (1 - U.saida(k)) * 160, y = 1200 + (1 - U.saida(k)) * 180;
          c.save(); c.globalAlpha = 0.9; c.beginPath(); c.arc(x, y, apertado && aperto < 0.25 ? 30 : 38, 0, TAU); c.fillStyle = '#FFF'; c.fill();
          c.lineWidth = 6; c.strokeStyle = '#111'; c.stroke(); c.restore();
        }
      }
      c.restore();
    }

    function quadro(t) {
      const fase = U.cenaEm(spec, t), cn = fase.c, i = fase.i, local = fase.local, nv = niveis[i];
      const ultimoNivel = i === N - 1, cta = ultimoNivel ? CTA : 0;
      // o jogo do ultimo nivel acaba `cta` s antes da cena: o resto e' o encerramento
      const dur = Math.max(2, cn.fim - cn.ini - cta), resta = dur - REVELA - local;
      nv._dur = dur;
      const L = camadasDe(i);
      c.drawImage(L.fundo, 0, 0);
      // entrada do nivel: o 1o ja' esta' no quadro 0 (o feed decide nele); os outros sobem com mola (R1)
      const ent = i === 0 ? U.saida(U.clamp((local + 0.25) / 0.35, 0, 1)) : U.clamp(U.mola(local + 0.04, 11), 0, 1.2);
      c.save();
      if (ent < 0.999 || ent > 1.001) {
        const s = 0.9 + 0.1 * ent; c.translate(CX, (GY0 + GY1) / 2 + (1 - ent) * 120); c.scale(s, s); c.translate(-CX, -(GY0 + GY1) / 2);
        c.globalAlpha = U.clamp(ent, 0, 1);
      }
      c.drawImage(L.cartao, 0, 0);
      c.restore();
      if (resta <= 0) revelar(nv, -resta);
      placar(i, nv, t, local);
      if (resta > 0) cronometro(resta, dur - REVELA);
      // legenda do alto: depois do cartaz do titulo (2,2 s) no 1o nivel; desde o inicio nos outros
      const tituloAte = TITULO_ATE, ultimo = i === N - 1;
      if (resta <= 0) legenda(ultimo ? legendaFim() : F.achou, cn.ini + dur - REVELA, t);
      // (nivel 1 curto: se sobram < 0,8 s entre o cartaz e a revelacao, a frase de abertura nem pisca -- fica so' o cartaz)
      else if (!(i === 0 && spec.titulo && (t < tituloAte || curto0))) legenda(legendaNivel(i), i === 0 && spec.titulo ? tituloAte : cn.ini, t);
      // lampejo branco na troca de nivel (corte com batida)
      if (i > 0 && local < 0.14) { c.save(); c.globalAlpha = 0.45 * (1 - local / 0.14); c.fillStyle = '#FFF'; c.fillRect(0, 0, W, H); c.restore(); }
      if (cta && local >= dur) encerramento(local - dur, nv);
      U.cartaz(c, spec, t, { fonte: '84px ' + FONTE, y: 100, altura_max: 240, fundo: '#111', borda: '#FFF', cor: '#FFF', altura_linha: 100, dur: 2.2 });
    }
    return { quadro };
  }
  MOTORES.quiz = { criar };
  window.QUIZ_ITENS = { formas: Object.keys(FORMAS), icones: Object.keys(ICONES) };
})();
