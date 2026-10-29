// QUIZ -- "ache o diferente" (22/10; v2 23/10, ordem do dono: "nao so' com
// letras, tambem com outras coisas"). Uma grade de itens iguais com UM
// diferente; cronometro; no fim do tempo, o diferente e' circulado. Cada cena
// e' um nivel, cada vez mais dificil. O espectador comenta em que nivel parou.
//
// cena: { texto (rotulo: "LEVEL 1", "ONLY 1% SEE IT"), tipo, base, diferente,
//         colunas: 4..12, linhas: 5..16, dur_s, cor?, dificuldade: 1..5 }
//   tipo "letras"  base/diferente = 1 a 3 caracteres parecidos (O/Q, 8/B, rn/m)
//   tipo "formas"  base = uma de FORMAS; diferente = girado|espelhado|maior|menor|sem_pedaco|cor
//   tipo "icones"  base = um de ICONES;  diferente = idem (relogio: "hora" muda o ponteiro)
//   tipo "cores"   base = forma ou icone; o diferente e' um tom mais claro/escuro
//   `dificuldade` decide o QUANTO o diferente difere (5 = quase igual).
// A posicao do diferente vem da semente (deterministica). Sem estado entre quadros.
(function () {
  'use strict';
  const TAU = Math.PI * 2;
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
      c.save(); c.globalCompositeOperation = 'destination-out'; c.beginPath(); c.arc(-0.45, 0, 0.15, 0, TAU); c.fill(); c.restore(); },
    peixe: (c) => { c.beginPath(); c.ellipse(-0.1, 0, 0.62, 0.38, 0, 0, TAU); c.fill(); c.beginPath(); c.moveTo(0.4, 0); c.lineTo(0.9, -0.38); c.lineTo(0.9, 0.38); c.closePath(); c.fill();
      c.save(); c.globalCompositeOperation = 'destination-out'; c.beginPath(); c.arc(-0.42, -0.08, 0.08, 0, TAU); c.fill(); c.restore(); },
    maca: (c) => { c.beginPath(); c.arc(-0.28, 0.12, 0.5, 0, TAU); c.arc(0.28, 0.12, 0.5, 0, TAU); c.fill(); c.fillRect(-0.05, -0.75, 0.1, 0.35); c.beginPath(); c.ellipse(0.25, -0.6, 0.22, 0.1, -0.5, 0, TAU); c.fill(); },
    casa: (c) => { c.beginPath(); c.moveTo(0, -0.9); c.lineTo(0.9, -0.05); c.lineTo(-0.9, -0.05); c.closePath(); c.fill(); c.fillRect(-0.62, -0.05, 1.24, 0.9);
      c.save(); c.globalCompositeOperation = 'destination-out'; c.fillRect(-0.15, 0.35, 0.3, 0.5); c.restore(); },
    guarda_chuva: (c) => { c.beginPath(); c.arc(0, 0, 0.88, Math.PI, 0); c.closePath(); c.fill(); c.fillRect(-0.05, 0, 0.1, 0.7); c.lineWidth = 0.1; c.beginPath(); c.arc(-0.15, 0.7, 0.15, 0, Math.PI); c.stroke(); },
    relogio: (c, v) => { c.lineWidth = 0.14; c.beginPath(); c.arc(0, 0, 0.8, 0, TAU); c.stroke(); const h = (v && v.hora != null ? v.hora : 3);
      c.lineWidth = 0.12; c.lineCap = 'round'; c.beginPath(); c.moveTo(0, 0); c.lineTo(Math.cos((h / 12) * TAU - Math.PI / 2) * 0.42, Math.sin((h / 12) * TAU - Math.PI / 2) * 0.42); c.stroke();
      c.beginPath(); c.moveTo(0, 0); c.lineTo(0, -0.62); c.stroke(); },
    olho: (c) => { c.beginPath(); c.moveTo(-0.95, 0); c.quadraticCurveTo(0, -0.85, 0.95, 0); c.quadraticCurveTo(0, 0.85, -0.95, 0); c.fill();
      c.save(); c.globalCompositeOperation = 'destination-out'; c.beginPath(); c.arc(0, 0, 0.34, 0, TAU); c.fill(); c.restore(); c.beginPath(); c.arc(0.06, 0, 0.17, 0, TAU); c.fill(); },
    lampada: (c) => { c.beginPath(); c.arc(0, -0.25, 0.6, Math.PI * 0.8, Math.PI * 2.2); c.lineTo(0.25, 0.55); c.lineTo(-0.25, 0.55); c.closePath(); c.fill(); c.fillRect(-0.25, 0.62, 0.5, 0.14); c.fillRect(-0.18, 0.82, 0.36, 0.12); },
    foguete: (c) => { c.beginPath(); c.moveTo(0, -1); c.quadraticCurveTo(0.5, -0.4, 0.35, 0.5); c.lineTo(-0.35, 0.5); c.quadraticCurveTo(-0.5, -0.4, 0, -1); c.fill();
      c.beginPath(); c.moveTo(-0.35, 0.2); c.lineTo(-0.7, 0.75); c.lineTo(-0.3, 0.55); c.moveTo(0.35, 0.2); c.lineTo(0.7, 0.75); c.lineTo(0.3, 0.55); c.fill(); },
    nota_musical: (c) => { c.beginPath(); c.ellipse(-0.3, 0.55, 0.32, 0.24, -0.4, 0, TAU); c.fill(); c.fillRect(-0.02, -0.85, 0.12, 1.4); c.beginPath(); c.moveTo(0.1, -0.85); c.quadraticCurveTo(0.7, -0.6, 0.55, -0.1); c.quadraticCurveTo(0.5, -0.45, 0.1, -0.5); c.fill(); },
    gato: (c) => { c.beginPath(); c.arc(0, 0.15, 0.68, 0, TAU); c.fill(); c.beginPath(); c.moveTo(-0.62, -0.1); c.lineTo(-0.5, -0.9); c.lineTo(-0.12, -0.5); c.moveTo(0.62, -0.1); c.lineTo(0.5, -0.9); c.lineTo(0.12, -0.5); c.fill();
      c.save(); c.globalCompositeOperation = 'destination-out'; c.beginPath(); c.ellipse(-0.25, 0.05, 0.1, 0.16, 0, 0, TAU); c.ellipse(0.25, 0.05, 0.1, 0.16, 0, 0, TAU); c.fill(); c.restore(); },
  };

  function clarear(hex, f) {   // f>0 clareia, f<0 escurece
    let h = String(hex).replace('#', ''); if (h.length === 3) h = h.split('').map((x) => x + x).join('');
    const n = parseInt(h, 16), ch = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((v) => Math.round(f > 0 ? v + (255 - v) * f : v * (1 + f)));
    return 'rgb(' + ch.join(',') + ')';
  }

  function criar(tela, spec, U) {
    let c = tela.getContext('2d');const W = spec.w, H = spec.h;
    let gradeCache=null,gradeIndice=-1;
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const FUNDOS = ['#FFD23F', '#3EC1F3', '#7CFF8A', '#FF8FB1', '#B07CFF', '#FF9F45'];
    const TINTAS = ['#1B1B2F', '#C0392B', '#1F6FEB', '#11823B', '#7B2CBF', '#B35C00'];
    const REVELA = 1.3;   // segundos finais de cada nivel: a resposta
    // MAIS DIFICIL (23/10, pedido do dono): a grade e a sutileza tem um PISO que
    // sobe a cada nivel, seja o que for que o roteiro pedir -- nivel 1 ja' em 6x9,
    // o ultimo ate 10x16; a diferenca nunca e' "facil" depois do nivel 2.
    // SIMETRIA: girar um circulo, girar 90 graus um quadrado ou espelhar um
    // coracao nao muda nada -- o nivel ficava impossivel. Essas trocam de modo.
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
      return { col, lin, tipo, base: String(cn.base || 'O').slice(0, 14), dif: modo,
        desenho, nivelDif: dif, alvo: Math.floor(r() * col * lin), fundo: corOk(cn.cor, FUNDOS[i % FUNDOS.length]), tinta: TINTAS[i % TINTAS.length],
        rotulo: String(cn.texto || 'LEVEL ' + (i + 1)).toUpperCase().slice(0, 24) };
    });
    // o item de uma celula: igual a todos, ou o diferente (com a variacao pedida)
    function item(nv, k, cx, cy, tam) {
      if (nv.tipo === 'letras') { c.fillText(k === nv.alvo ? nv.dif : nv.base, cx, cy); return; }
      const e = tam / 2.1, d = nv.nivelDif, odd = k === nv.alvo;
      c.save(); c.translate(cx, cy); c.fillStyle = nv._tom || nv.tinta; c.strokeStyle = nv._tom || nv.tinta;
      let v = null;
      if (odd) {
        const m = nv.tipo === 'cores' ? 'cor' : nv.dif;
        if (m === 'girado') c.rotate(((6 + 34 * (5 - d) / 4) * Math.PI) / 180);   // 40 graus facil, 6 graus dificil
        else if (m === 'espelhado') c.scale(-1, 1);
        else if (m === 'maior') c.scale(1 + 0.26 / d, 1 + 0.26 / d);
        else if (m === 'menor') c.scale(1 - 0.24 / d, 1 - 0.24 / d);
        else if (m === 'cor') c.fillStyle = c.strokeStyle = clarear(nv.tinta, 0.36 / d);
        else if (m === 'hora') v = { hora: 3 + Math.max(1, 6 - d) };
      }
      c.scale(e, e);
      nv.desenho(c, v);
      if (odd && nv.dif === 'sem_pedaco' && nv.tipo !== 'cores') {   // um corte em cunha no item
        c.save(); c.globalCompositeOperation = 'destination-out'; c.beginPath(); c.moveTo(0, 0); c.arc(0, 0, 1.2, -0.25 * (6 - d) / 5 - 0.12, 0.25 * (6 - d) / 5 + 0.12); c.closePath(); c.fill(); c.restore();
      }
      c.restore();
    }
    function quadro(t) {
      const { c: cn, i, local } = U.cenaEm(spec, t), nv = niveis[i], dur = Math.max(2, cn.fim - cn.ini), resta = dur - REVELA - local;
      c.fillStyle = nv.fundo; c.fillRect(0, 0, W, H);
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
      const entra = U.saida(U.clamp((local + 0.25) / 0.35, 0, 1));   // 23/10: a grade ja' aparece no 1o quadro
      // CAMUFLAGEM (23/10): do nivel de dificuldade 3 em diante todos os itens
      // tremem um pouco de lugar -- o diferente deixa de "saltar" da grade
      const rj = U.rng((spec.semente || 'quiz') + ':j' + i), tremor = nv.nivelDif >= 3 ? (nv.nivelDif - 2) * 0.05 : 0;
      const desenharGrade=()=>{
      c.save(); c.font = tam + 'px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillStyle = '#111';
      // cartao branco atras da grade nas formas/icones (contraste com qualquer fundo)
      if (nv.tipo !== 'letras') { U.rr(c, x0 - 16, y0 - 16, x1 - x0 + 32, y1 - y0 + 32, 28); c.fillStyle = 'rgba(255,255,255,0.88)'; c.fill(); c.fillStyle = '#111'; }
      for (let k = 0; k < nv.col * nv.lin; k++) {
        const jx = (rj() - 0.5) * 2 * tremor * cw, jy = (rj() - 0.5) * 2 * tremor * ch, jc = rj();
        const cx = x0 + (k % nv.col + 0.5) * cw + jx, cy = y0 + (Math.floor(k / nv.col) + 0.5) * ch + jy;
        c.globalAlpha = entra;
        if (nv.tipo === 'cores' && nv.nivelDif >= 4 && k !== nv.alvo) { c.save(); nv._tom = clarear(nv.tinta, (jc - 0.5) * 0.05); }
        item(nv, k, cx, cy + (1 - entra) * 30, tam);
        if (nv._tom) { c.restore(); nv._tom = null; }
      }
      c.restore();
      };
      if(entra>=1){
        if(gradeIndice!==i){const principal=c;
          gradeCache=U.camada(W,H,g=>{c=g;try{desenharGrade();}finally{c=principal;}});gradeIndice=i;}
        c.drawImage(gradeCache,0,0);
      } else desenharGrade();
      if (resta <= 0) {
        const k = nv.alvo, rj2 = U.rng((spec.semente || 'quiz') + ':j' + i); let jx = 0, jy = 0;
        for (let n = 0; n <= k; n++) { const a = rj2(), b = rj2(); rj2(); if (n === k) { jx = (a - 0.5) * 2 * tremor * cw; jy = (b - 0.5) * 2 * tremor * ch; } }
        const cx = x0 + (k % nv.col + 0.5) * cw + jx, cy = y0 + (Math.floor(k / nv.col) + 0.5) * ch + jy, q = U.mola(-resta, 10);
        c.save(); c.lineWidth = 12; c.strokeStyle = '#E2373C'; c.beginPath(); c.arc(cx, cy, Math.max(cw, ch) * 0.62 * q, 0, Math.PI * 2); c.stroke();
        c.font = '84px "Lilita One", sans-serif'; c.textAlign = 'center'; c.fillStyle = '#111'; c.fillText('FOUND IT?', W / 2, 430); c.restore();
      }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 100, altura_max: 240, fundo: '#111', borda: '#FFF', cor: '#FFF', altura_linha: 100, dur: 2.2 });
    }
    return { quadro };
  }
  MOTORES.quiz = { criar };
  window.QUIZ_ITENS = { formas: Object.keys(FORMAS), icones: Object.keys(ICONES) };
})();
