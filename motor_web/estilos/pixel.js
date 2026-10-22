// PIXEL -- a vida adulta como RPG de 8 bits, sem voz (13/10, HISTORICO §109).
//
// O canal transforma o cotidiano adulto em jogo: o boleto e' um chefe de fase,
// o salario cai como ouro e some na loja, segunda-feira tira HP. Sem voz: o
// texto vem na CAIXA DE DIALOGO com maquina de escrever (o "blip" de cada
// letra e' o som do genero) e na interface (HP, ENERGIA, OURO, NIVEL), que
// conta a piada sozinha quando o numero despenca.
//
// A tela tem 180x320 pixels de verdade, ampliada 6x sem suavizar; o texto e a
// interface sao desenhados por cima, na resolucao final, em Press Start 2P.
(function () {
  'use strict';
  const PAL = { ceu: '#5FA8D3', noite: '#1D2B53', parede: '#C2C3C7', parede2: '#83769C', chao: '#5F574F', chao2: '#7E7058', madeira: '#AB5236', madeira2: '#7E2553',
    pele: '#FFCCAA', cabelo: '#4A2E1F', azul: '#29ADFF', azul2: '#1D2B53', verde: '#00E436', verde2: '#008751', amarelo: '#FFEC27', laranja: '#FFA300', vermelho: '#FF004D',
    branco: '#FFF1E8', preto: '#000000', cinza: '#5F574F', rosa: '#FF77A8' };

  // sprites 12x20: '.' vazio; letras = cor. Dois quadros de caminhada.
  const S = {
    heroi: [
      '....cccc....', '...cccccc...', '...cppppc...', '...pkppkp...', '...pppppp...', '....pppp....', '...aaaaaa...', '..aaaaaaaa..', '..paaaaaap..', '..paaaaaap..',
      '...aaaaaa...', '...dddddd...', '...dd..dd...', '...dd..dd...', '...dd..dd...', '...ss..ss...'],
    chefe: [
      '....pppp....', '...pppppp...', '...pkppkp...', '...pppppp...', '...pmmmmp...', '....pppp....', '..ggwrrwgg..', '.gggwrrwggg.', '.pggwrrwggp.', '.pggggggggp.',
      '..gggggggg..', '..gggggggg..', '...gg..gg...', '...gg..gg...', '...gg..gg...', '...ss..ss...'],
    mae: [
      '....cccc....', '...cccccc...', '..ccppppcc..', '...pkppkp...', '...pppppp...', '....pppp....', '...rrrrrr...', '..rwwwwwwr..', '..pwwwwwwp..', '..pwwwwwwp..',
      '...wwwwww...', '...rrrrrr...', '...rr..rr...', '....p..p....', '....p..p....', '...ss..ss...'],
    gato: ['............', '............', '............', '............', '............', '............', '............', '............', '.o..o.......', '.oooo.......',
      '.okok....o..', '.oooooooo...', '..oooooooo..', '..oooooooo..', '..o.o..o.o..', '..o.o..o.o..'],
    npc: [
      '....yyyy....', '...yyyyyy...', '...ypppp y..', '...pkppkp...', '...pppppp...', '....pppp....', '...vvvvvv...', '..vvvvvvvv..', '..pvvvvvvp..', '..pvvvvvvp..',
      '...vvvvvv...', '...dddddd...', '...dd..dd...', '...dd..dd...', '...dd..dd...', '...ss..ss...']
  };
  const COR = { c: PAL.cabelo, p: PAL.pele, k: PAL.preto, a: PAL.azul, d: PAL.azul2, s: PAL.preto, g: '#3B3B4F', w: PAL.branco, r: PAL.vermelho, m: '#B5603E', o: PAL.laranja, y: PAL.amarelo, v: PAL.verde2 };

  function criar(tela, spec, U) {
    const c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const PW = 180, PH = 320, K = W / PW;
    const buf = document.createElement('canvas'); buf.width = PW; buf.height = PH; const b = buf.getContext('2d');
    const px = (x, y, w, h, cor) => { b.fillStyle = cor; b.fillRect(Math.round(x), Math.round(y), w, h); };
    function sprite(nome, x, y, quadro, dir, esc) {
      const sp = S[nome] || S.heroi, e = esc || 3;
      sp.forEach((lin, j) => {
        let l = lin;
        if (quadro && j >= 12 && nome !== 'gato') l = j % 2 ? lin.replace('dd..dd', 'd...dd').replace('gg..gg', 'g...gg') : lin.replace('dd..dd', 'dd...d').replace('gg..gg', 'gg...g');
        for (let i = 0; i < 12; i++) { const ch = l[dir < 0 ? 11 - i : i]; if (ch && ch !== '.' && ch !== ' ' && COR[ch]) px(x + i * e, y + j * e, e, e, COR[ch]); }
      });
    }
    function objeto(nome, x, y) {
      if (nome === 'cafe') { px(x, y, 6, 6, PAL.branco); px(x + 6, y + 1, 2, 3, PAL.branco); px(x + 1, y + 1, 4, 2, PAL.madeira); }
      else if (nome === 'boleto') { px(x, y, 8, 10, PAL.branco); for (let i = 0; i < 4; i++) px(x + 1, y + 2 + i * 2, 6, 1, PAL.cinza); px(x + 5, y + 8, 3, 1, PAL.vermelho); }
      else if (nome === 'celular') { px(x, y, 5, 9, PAL.preto); px(x + 1, y + 1, 3, 6, PAL.azul); }
      else if (nome === 'pizza') { for (let i = 0; i < 8; i++) px(x + i / 2, y + i, 8 - i, 1, i < 1 ? PAL.madeira : PAL.amarelo); px(x + 2, y + 2, 1, 1, PAL.vermelho); px(x + 4, y + 3, 1, 1, PAL.vermelho); }
      else if (nome === 'moeda') { px(x + 1, y, 4, 6, PAL.amarelo); px(x, y + 1, 6, 4, PAL.amarelo); px(x + 2, y + 1, 1, 4, PAL.laranja); }
      else if (nome === 'alarme') { px(x, y + 2, 8, 7, PAL.vermelho); px(x + 2, y + 3, 4, 4, PAL.branco); px(x - 1, y, 3, 2, PAL.amarelo); px(x + 6, y, 3, 2, PAL.amarelo); }
      else if (nome === 'email') { px(x, y, 10, 7, PAL.branco); for (let i = 0; i < 5; i++) px(x + i, y + i * 0.6, 1, 1, PAL.cinza); for (let i = 0; i < 5; i++) px(x + 9 - i, y + i * 0.6, 1, 1, PAL.cinza); }
    }
    function cenario(nome, t) {
      const f = Math.floor(t * 4);
      if (nome === 'rua' || nome === 'onibus') {
        px(0, 0, PW, 200, PAL.ceu); for (let i = 0; i < 6; i++) { const x = ((i * 40 - (nome === 'onibus' ? t * 60 : 0)) % 240 + 240) % 240 - 40, h = 70 + (i * 37) % 60; px(x, 200 - h, 34, h, i % 2 ? PAL.parede2 : '#7E7058'); for (let r = 0; r < h / 14 - 1; r++) for (let q = 0; q < 3; q++) px(x + 4 + q * 10, 205 - h + r * 14, 5, 7, (r + q + i) % 3 ? PAL.amarelo : PAL.azul2); }
        px(0, 200, PW, 120, PAL.chao); px(0, 200, PW, 4, PAL.chao2);
        if (nome === 'onibus') { px(0, 120, PW, 200, '#FFA30044'); px(0, 110, PW, 12, PAL.laranja); px(0, 196, PW, 124, PAL.laranja); for (let i = 0; i < 4; i++) { px(8 + i * 44, 210, 30, 30, PAL.azul2); px(8 + i * 44, 240, 30, 6, PAL.preto); } for (let i = 0; i < 3; i++) px(10 + i * 60, 120, 4, 76, PAL.laranja); }
        return;
      }
      const paredes = { quarto: [PAL.parede2, '#6B5D88'], escritorio: [PAL.parede, '#A8A9AD'], cozinha: ['#F2D3AB', '#E0B98D'], mercado: [PAL.branco, '#E6D9CC'], academia: ['#3B3B4F', '#2C2C3B'], chefe_arena: [PAL.noite, '#121A36'] }[nome] || [PAL.parede, '#A8A9AD'];
      px(0, 0, PW, 210, paredes[0]); for (let y = 0; y < 210; y += 16) px(0, y, PW, 1, paredes[1]);
      px(0, 210, PW, 110, nome === 'chefe_arena' ? '#3B1F2B' : PAL.madeira); for (let x = 0; x < PW; x += 20) px(x, 210, 1, 110, PAL.madeira2);
      if (nome === 'quarto') { px(14, 40, 40, 30, PAL.ceu); px(33, 40, 2, 30, PAL.branco); px(14, 54, 40, 2, PAL.branco); px(110, 150, 62, 30, PAL.branco); px(110, 140, 16, 12, PAL.branco); px(110, 176, 62, 34, PAL.madeira); px(70, 60, 24, 32, PAL.rosa); }
      if (nome === 'escritorio') { px(20, 150, 90, 8, PAL.madeira); px(24, 158, 6, 52, PAL.madeira2); px(100, 158, 6, 52, PAL.madeira2); px(40, 118, 44, 30, PAL.preto); px(43, 121, 38, 24, (f % 2) ? PAL.azul : '#29ADFFCC'); px(58, 148, 8, 3, PAL.cinza);
        px(140, 30, 24, 24, PAL.branco); px(151, 34, 2, 10, PAL.preto); px(151, 42, 8, 2, PAL.preto); px(150, 170, 14, 40, PAL.verde2); px(146, 150, 22, 24, PAL.verde); }
      if (nome === 'cozinha') { px(130, 100, 40, 110, PAL.branco); px(132, 150, 36, 1, PAL.cinza); px(164, 120, 2, 20, PAL.cinza); px(10, 150, 70, 60, PAL.cinza); px(16, 146, 14, 4, PAL.preto); px(46, 146, 14, 4, PAL.preto); }
      if (nome === 'mercado') { for (let r = 0; r < 3; r++) { px(10, 60 + r * 50, 160, 4, PAL.madeira); for (let i = 0; i < 12; i++) px(14 + i * 13, 44 + r * 50, 9, 16, [PAL.vermelho, PAL.amarelo, PAL.verde, PAL.azul][(i + r) % 4]); } }
      if (nome === 'academia') { for (let i = 0; i < 3; i++) { px(20 + i * 55, 170, 30, 4, PAL.cinza); px(18 + i * 55, 164, 6, 16, PAL.preto); px(46 + i * 55, 164, 6, 16, PAL.preto); } px(0, 20, PW, 30, PAL.vermelho); }
      if (nome === 'chefe_arena') { for (let i = 0; i < 40; i++) { const r = U.rng(i); px(r() * PW, r() * 200, 1, 1, PAL.branco); } px(0, 200, PW, 2, PAL.vermelho); }
    }

    // ---------- interface (resolucao final) ----------
    const F = (n) => n + 'px "Press Start 2P", monospace';
    function caixa(x, y, w, h) { c.fillStyle = '#1D2B53'; c.fillRect(x, y, w, h); c.lineWidth = 8; c.strokeStyle = PAL.branco; c.strokeRect(x + 8, y + 8, w - 16, h - 16); }
    function barra(x, y, w, rot, v, cor) { c.font = F(26); c.fillStyle = PAL.branco; c.textAlign = 'left'; c.textBaseline = 'middle'; c.fillText(rot, x, y + 16); c.fillStyle = PAL.preto; c.fillRect(x + 150, y, w, 32); c.fillStyle = cor; c.fillRect(x + 154, y + 4, Math.max(0, (w - 8) * U.clamp(v / 100, 0, 1)), 24); }
    function hudEm(t) {
      // o HUD de cada cena vale do comeco dela; anda ate o da cena seguinte no 1o terco
      const { c: cn, i, k } = U.cenaEm(spec, t);
      const atual = Object.assign({ hp: 80, energia: 60, ouro: 120, nivel: 27 }, spec.hud_inicial || {});
      for (let j = 0; j < i; j++) Object.assign(atual, spec.cenas[j].hud || {});
      const alvo = Object.assign({}, atual, cn.hud || {}), q = U.saida(U.clamp(k * 3, 0, 1));
      const out = {}; for (const key in alvo) out[key] = U.lerp(atual[key], alvo[key], q);
      out.caiu = (cn.hud && cn.hud.hp != null && cn.hud.hp < atual.hp && k < 0.4) || (cn.hud && cn.hud.ouro != null && cn.hud.ouro < atual.ouro && k < 0.4);
      return out;
    }
    // ZONA SEGURA DO SHORTS (22/10, ordem do dono: "as legendas e falas ficam
    // tampadas com as informacoes do YouTube"). O app cobre o rodape (titulo,
    // canal, descricao: ~480 px de baixo), a coluna da direita (curtir,
    // comentar, compartilhar: ~170 px) e a barra do topo (~140 px). A caixa de
    // dialogo morava em H-520..H-80 -- inteira debaixo da descricao -- e o HUD
    // comecava em y=30, sob a barra. Tudo que se le fica dentro de ZS.
    const ZS = { topo: 150, base: H - 500, esq: 30, dir: W - 175 };
    const DLG = { x: ZS.esq, y: ZS.base - 360, w: ZS.dir - ZS.esq, h: 360 };
    // o MUNDO sobe 150 px (25 pixels do buffer, multiplo de K: continua nitido)
    // para o chao ficar acima da caixa; o rodape repete o chao (o app cobre ali).
    const MUNDO_DY = 150;
    function hud(t) {
      const h = hudEm(t), tremor = h.caiu ? Math.sin(t * 80) * 6 : 0;
      c.save(); c.translate(tremor, 0); caixa(ZS.esq, ZS.topo, ZS.dir - ZS.esq, 130);
      barra(70, ZS.topo + 24, 400, 'HP', h.hp, h.hp < 30 ? PAL.vermelho : PAL.verde); barra(70, ZS.topo + 72, 400, 'NRG', h.energia, PAL.amarelo);
      c.font = F(30); c.textAlign = 'right'; c.textBaseline = 'middle'; c.fillStyle = PAL.amarelo; c.fillText('G ' + Math.round(h.ouro), ZS.dir - 40, ZS.topo + 42); c.fillStyle = PAL.branco; c.fillText('LV ' + Math.round(h.nivel), ZS.dir - 40, ZS.topo + 90); c.restore();
    }
    function dialogo(texto, local, quem) {
      if (!texto) return;
      // a caixa ja' mostra quem fala: "MOM: MOM: ..." era o roteiro repetindo
      if (quem && texto.toUpperCase().startsWith(String(quem).toUpperCase() + ':')) texto = texto.slice(String(quem).length + 1).trim();
      const n = Math.floor(local * 32), vis = texto.slice(0, n);
      caixa(DLG.x, DLG.y, DLG.w, DLG.h);
      c.font = F(36); c.fillStyle = PAL.branco; c.textAlign = 'left'; c.textBaseline = 'top';
      if (quem) { c.fillStyle = PAL.amarelo; c.fillText(String(quem).toUpperCase(), DLG.x + 50, DLG.y + 45); }
      c.fillStyle = PAL.branco; U.linhas(c, vis, DLG.w - 100).forEach((l, i) => c.fillText(l, DLG.x + 50, DLG.y + (quem ? 110 : 60) + i * 60));
      const sx = DLG.x + DLG.w - 70, sy = DLG.y + DLG.h - 60;
      if (n >= texto.length && Math.floor(local * 3) % 2) { c.beginPath(); c.moveTo(sx - 20, sy); c.lineTo(sx + 20, sy); c.lineTo(sx, sy + 26); c.closePath(); c.fill(); }
    }
    function banner(txt, local, cor) {
      const p = U.mola(local, 10); c.save(); c.translate(W / 2, 760); c.scale(p, p); c.fillStyle = cor || PAL.vermelho; c.fillRect(-470, -90, 940, 180); c.lineWidth = 10; c.strokeStyle = PAL.branco; c.strokeRect(-450, -70, 900, 140);
      c.font = F(54); c.fillStyle = PAL.branco; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(txt, 0, 4); c.restore();
    }

    // ---------- acoes (no buffer de pixels) ----------
    function quadro(t) {
      const { c: cn, k, local } = U.cenaEm(spec, t);
      const passo = Math.floor(t * 6) % 2, at = cn.atores && cn.atores.length ? cn.atores : ['heroi'];
      const cen = cn.acao === 'batalha' ? 'chefe_arena' : (cn.cenario || 'quarto');
      b.save(); cenario(cen, t);
      const yb = 162;
      let extraUI = null;
      switch (cn.acao) {
        case 'acorda': { const ant = k < 0.5; sprite(at[0], ant ? 112 : 70, ant ? 112 : yb, 0, 1); if (ant) px(106, 150, 66, 18, PAL.branco); objeto('alarme', 40, 140 + (Math.floor(t * 12) % 2)); break; }
        case 'anda': sprite(at[0], U.lerp(-36, 150, k), yb, passo, 1); if (at[1]) sprite(at[1], 128, yb, 0, -1); break;
        case 'digita': sprite(at[0], 54, 150, passo, 1); if (Math.floor(t * 3) % 2) px(80, 132, 3, 5, PAL.azul); objeto('cafe', 92, 142); break;
        case 'come': sprite(at[0], 70, yb, 0, 1); objeto(cn.objeto || 'pizza', 88, 200 - Math.floor(k * 3) * 2); break;
        case 'dorme': sprite(at[0], 112, 112, 0, 1); px(106, 150, 66, 18, PAL.branco); break;
        case 'compra': case 'recebe': { sprite(at[0], 70, yb, 0, 1); for (let i = 0; i < 6; i++) { const q = (local * 1.5 + i / 6) % 1; objeto('moeda', 80 + Math.sin(i * 2) * 20, cn.acao === 'recebe' ? 40 + q * 150 : 180 - q * 150); } if (cn.objeto && cn.objeto !== 'moeda') objeto(cn.objeto, 98, yb + 30); break; }
        case 'batalha': sprite(at[0], 14, 162, passo, 1, 3); sprite(at[1] || 'chefe', 96, 76, 0, -1, 6); if (k > 0.45 && k < 0.6) px(0, 0, PW, PH, '#FFFFFF66'); extraUI = 'batalha'; break;
        case 'level_up': sprite(at[0], 84, yb, 0, 1); for (let i = 0; i < 10; i++) { const q = (local * 2 + i / 10) % 1; px(80 + (i % 5) * 6, yb + 20 - q * 120, 2, 2, i % 2 ? PAL.amarelo : PAL.branco); } extraUI = 'level'; break;
        case 'game_over': sprite(at[0], 84, yb + 10, 0, 1); extraUI = 'over'; break;
        case 'missao': sprite(at[0], 84, yb, 0, 1); extraUI = 'missao'; break;
        default: sprite(at[0], 30, yb, Math.floor(t * 2) % 2, 1); if (at[1]) sprite(at[1], 116, yb, 0, -1);
      }
      if (cn.objeto && ['acorda', 'come', 'compra', 'recebe'].indexOf(cn.acao) < 0) objeto(cn.objeto, cn.acao === 'anda' ? U.lerp(-36, 150, k) + 28 : 82, cn.acao === 'anda' ? yb + 30 : 160 + Math.sin(t * 4) * 2);
      b.restore();
      c.imageSmoothingEnabled = false; c.drawImage(buf, 0, 0, W, H); c.drawImage(buf, 0, -MUNDO_DY, W, H);
      if (extraUI === 'over') { c.fillStyle = 'rgba(0,0,0,' + (0.75 * U.clamp(k * 2, 0, 1)).toFixed(2) + ')'; c.fillRect(0, 0, W, H); c.font = F(86); c.fillStyle = PAL.vermelho; c.textAlign = 'center'; c.fillText('GAME OVER', W / 2, 820); if (k > 0.5) { c.font = F(36); c.fillStyle = PAL.branco; c.fillText('CONTINUE? ' + (9 - Math.floor((k - 0.5) * 18)), W / 2, 960); } }
      hud(t);
      if (extraUI === 'level') banner('LEVEL UP!', local, PAL.verde2);
      if (extraUI === 'missao') banner('NEW QUEST', local, PAL.azul2);
      if (extraUI === 'batalha') { if (!cn.texto) { caixa(DLG.x, DLG.y, DLG.w, DLG.h); c.font = F(46); c.textAlign = 'left'; c.textBaseline = 'middle'; ['FIGHT', 'ITEM', 'RUN', 'CRY'].forEach((o, i) => { c.fillStyle = PAL.branco; c.fillText(o, DLG.x + 130 + (i % 2) * 380, DLG.y + 140 + Math.floor(i / 2) * 120); });
        const sel = Math.min(3, Math.floor(k * 4)); c.fillStyle = PAL.amarelo; { const ax = DLG.x + 70 + (sel % 2) * 380, ay = DLG.y + 140 + Math.floor(sel / 2) * 120; c.beginPath(); c.moveTo(ax, ay - 20); c.lineTo(ax + 32, ay); c.lineTo(ax, ay + 20); c.closePath(); c.fill(); } }
        if (k > 0.45 && k < 0.8) { c.font = F(70); c.fillStyle = PAL.vermelho; c.textAlign = 'center'; c.fillText('-' + (cn.dano || 40), W * 0.3, 1100 - MUNDO_DY - (k - 0.45) * 400); } }
      if (cn.texto) dialogo(cn.texto, local, cn.quem);
      if (cn.texto && cn.acao === 'missao') { c.font = F(40); c.fillStyle = PAL.branco; c.textAlign = 'center'; }
      U.cartaz(c, spec, t, { fonte: F(48), y: ZS.topo + 165, fundo: PAL.vermelho, borda: PAL.branco, cor: PAL.branco, altura_linha: 70, raio: 0, dur: 2.6, caixa: true });
      // linhas de varredura de tela de tubo
      c.fillStyle = 'rgba(0,0,0,.08)'; for (let y = 0; y < H; y += 6) c.fillRect(0, y, W, 2);
    }
    return { quadro };
  }
  MOTORES.pixel = { criar };
})();


