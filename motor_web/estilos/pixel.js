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
    const legado = spec.qualidade === 'legado';
    const PW = 180, PH = 320, K = W / PW;
    const buf = document.createElement('canvas'); buf.width = PW; buf.height = PH; let b = buf.getContext('2d');
    const px = (x, y, w, h, cor) => { b.fillStyle = cor; b.fillRect(Math.round(x), Math.round(y), Math.max(1,Math.round(w)), Math.max(1,Math.round(h))); };
    const fundos = new Map(), sprites = new Map();
    function sprite(nome, x, y, quadro, dir, esc, pose) {
      const sp = S[nome] || S.heroi, e = esc || 3;
      if(legado){sp.forEach((lin,j)=>{let l=lin;if(quadro && j>=12 && nome!=='gato')l=j%2?lin.replace('dd..dd','d...dd').replace('gg..gg','g...gg'):lin.replace('dd..dd','dd...d').replace('gg..gg','gg...g');for(let i=0;i<12;i++){const ch=l[dir<0?11-i:i];if(ch&&ch!=='.'&&ch!==' '&&COR[ch])px(x+i*e,y+j*e,e,e,COR[ch]);}});return;}
      // Contato e volume desenhados na grade, nunca blur em resolução final.
      px(x+e,y+16*e-1,10*e,2,'#00000044');
      const key = [nome,quadro,dir,e,pose].join(':');
      if(sprites.has(key)){b.drawImage(sprites.get(key),Math.round(x),Math.round(y));return;}
      const cv=document.createElement('canvas');cv.width=12*e;cv.height=16*e;const g=cv.getContext('2d');
      sp.forEach((lin, j) => {
        let l = lin;
        if (quadro && j >= 12 && nome !== 'gato') l = j % 2 ? lin.replace('dd..dd', 'd...dd').replace('gg..gg', 'g...gg') : lin.replace('dd..dd', 'dd...d').replace('gg..gg', 'gg...g');
        for (let i = 0; i < 12; i++) { const ch = l[dir < 0 ? 11 - i : i]; if(pose === 'consome' && j >= 8 && j <= 9 && i > 6 && ch === 'p') continue; if (ch && ch !== '.' && ch !== ' ' && COR[ch]) {
          g.fillStyle=COR[ch];g.fillRect(i*e,j*e,e,e);
          if(i>6 && ['a','g','v','r','d'].includes(ch)){g.fillStyle='#00000024';g.fillRect(i*e,j*e,e,e);}
        } }
      });
      sprites.set(key,cv);b.drawImage(cv,Math.round(x),Math.round(y));
    }
    function objeto(nome, x, y) {
      if (!legado) return objeto2(nome, x, y);
      if (nome === 'cafe') { px(x, y, 6, 6, PAL.branco); px(x + 6, y + 1, 2, 3, PAL.branco); px(x + 1, y + 1, 4, 2, PAL.madeira); }
      // T337: casquinha e bola de sorvete no mesmo estilo de pixels.
      else if (nome === 'sorvete') { px(x + 2, y + 5, 4, 2, PAL.laranja); px(x + 3, y + 7, 2, 2, PAL.laranja); px(x + 1, y + 1, 6, 4, PAL.rosa); px(x + 2, y, 4, 1, PAL.rosa); }
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
      if(!legado){px(0,204,PW,6,paredes[1]);px(0,210,PW,2,'#00000044');
      for(let row=0;row<6;row++)for(let col=0;col<10;col++){const x=col*20+(row%2?10:0),y=212+row*18;px(x,y,1,18,'#00000033');px(x+4,y+7,7,1,'#FFFFFF10');}}
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
      out.ouroAntes = atual.ouro;
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
    function dialogoLegado(texto, local, quem) {
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
    function dialogo(texto, local, quem) {
      if(legado)return dialogoLegado(texto,local,quem);
      if (!texto) return;
      // a caixa ja' mostra quem fala: "MOM: MOM: ..." era o roteiro repetindo
      if (quem && texto.toUpperCase().startsWith(String(quem).toUpperCase() + ':')) texto = texto.slice(String(quem).length + 1).trim();
      // Páginas calculadas com o texto completo: uma linha não salta ao digitar.
      // 05/11: 32 px era ilegivel no celular (3% da largura); 42 px com 3-4 linhas cabe na caixa de 360 px.
      c.font = F(42);
      const completas = U.linhas(c, texto, DLG.w - 100), porPagina = quem ? 3 : 4;
      const paginas=[];for(let i=0;i<completas.length;i+=porPagina)paginas.push(completas.slice(i,i+porPagina));
      const cps=32, tempos=paginas.map(ls=>ls.join(' ').length/cps+0.8);
      let pagina=0, inicio=0;while(pagina<tempos.length-1 && local>=inicio+tempos[pagina])inicio+=tempos[pagina++];
      const n=Math.floor(Math.max(0,local-inicio)*cps), vis=paginas[pagina] || [], textoPagina=vis.join(' ');
      caixa(DLG.x, DLG.y, DLG.w, DLG.h);
      c.font = F(42); c.fillStyle = PAL.branco; c.textAlign = 'left'; c.textBaseline = 'top';
      if (quem) { c.fillStyle = PAL.amarelo; c.fillText(String(quem).toUpperCase(), DLG.x + 50, DLG.y + 40); }
      let escrito=0;c.fillStyle = PAL.branco; vis.forEach((l,i)=>{const trecho=l.slice(0,Math.max(0,n-escrito));escrito+=l.length+1;c.fillText(trecho,DLG.x+50,DLG.y+(quem?105:50)+i*66);});
      const sx = DLG.x + DLG.w - 70, sy = DLG.y + DLG.h - 60;
      if (n >= textoPagina.length && Math.floor(local * 3) % 2) { c.beginPath(); c.moveTo(sx - 20, sy); c.lineTo(sx + 20, sy); c.lineTo(sx, sy + 26); c.closePath(); c.fill(); }
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
      b.save();
      const estatico = !legado && !['onibus','escritorio'].includes(cen);
      if(estatico && fundos.has(cen))b.drawImage(fundos.get(cen),0,0);
      else {cenario(cen,t);if(estatico){const cv=document.createElement('canvas');cv.width=PW;cv.height=PH;cv.getContext('2d').drawImage(buf,0,0);fundos.set(cen,cv);}}
      const yb = 162;
      let extraUI = null;
      switch (cn.acao) {
        case 'acorda': { const ant = k < 0.5; sprite(at[0], ant ? 112 : 70, ant ? 112 : yb, 0, 1); if (ant) px(106, 150, 66, 18, PAL.branco); if (cn.objeto && cn.objeto !== 'alarme') objeto(cn.objeto, ant ? 140 : 98, ant ? 142 : 192); else objeto('alarme', 40, 140 + (Math.floor(t * 12) % 2)); break; }
        case 'anda': sprite(at[0], U.lerp(-36, 150, k), yb, passo, 1); if (at[1]) sprite(at[1], 128, yb, 0, -1); break;
        case 'digita': {
          if(legado){sprite(at[0],54,150,passo,1);if(Math.floor(t*3)%2)px(80,132,3,5,PAL.azul);objeto(cn.objeto||'cafe',cn.objeto?82:92,cn.objeto?180:142);break;}
          px(18,151,17,39,PAL.azul2);sprite(at[0],22,130,0,1);
          px(28,166,20,6,PAL.azul2);px(43,170,5,18,PAL.azul2);px(42,187,10,3,PAL.preto);
          px(44,151,14,4,PAL.azul);px(56,150+(passo?0:1),7,3,PAL.pele);
          px(60,152,21,2,PAL.cinza);for(let j=0;j<7;j++)px(61+j*3,152,1,1,PAL.branco);
          objeto(cn.objeto || 'cafe', cn.objeto ? 82 : 92, cn.objeto ? 180 : 142);
          if(!cn.objeto || cn.objeto === 'cafe')for(let j=0;j<3;j++)px(94+j*2,138-((Math.floor(t*5)+j*2)%8),1,2,'#FFFFFF88');break;
        }
        case 'come': {
          // T324: evento literal, nunca uma palavra solta, hipótese ou pergunta.
          const texto = typeof cn.texto === 'string' ? cn.texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').trim().replace(/\s+/g, ' ').toLowerCase() : '';
          const cafeLiteral = /^(?:you used coffee|usaste cafe(?: frio)?|voce usou cafe(?: frio)?)[.!](?:\s|$)/.test(texto);
          // T337: só consumo afirmativo completo; objeto explícito distinto vence.
          const sorveteLiteral = /^(?:you ate ice cream|comiste helado|voce comeu sorvete)[.!](?:\s|$)/.test(texto);
          const item = (!cn.objeto || cn.objeto === 'pizza') && sorveteLiteral ? 'sorvete' : (cafeLiteral && (!cn.objeto || cn.objeto === 'pizza') ? 'cafe' : (cn.objeto || 'pizza'));
          if(legado || !['cafe','pizza','sorvete'].includes(item) || at[0] === 'gato') {
            sprite(at[0], 70, yb, 0, 1); objeto(item, 98, 184 - Math.floor(k * 3) * 2); break;
          }
          // Uma ação completa, presa à mão: repouso -> boca -> repouso.
          // A fase depende só do instante da cena, inclusive em busca aleatória.
          const levantar = U.suave(U.clamp((k - .12) / .28, 0, 1));
          const baixar = U.suave(U.clamp((k - .72) / .23, 0, 1));
          const gesto = levantar * (1 - baixar), ox = Math.round(U.lerp(98, 88, gesto)), oy = Math.round(U.lerp(184, 173, gesto));
          sprite(at[0], 70, yb, 0, 1, 3, 'consome');
          const manga = {chefe:'#3B3B4F',mae:PAL.branco,npc:PAL.verde2}[at[0]] || PAL.azul;
          const segmento = (x0,y0,x1,y1,cor) => {const n=Math.max(Math.abs(x1-x0),Math.abs(y1-y0),1);for(let j=0;j<=n;j++)px(U.lerp(x0,x1,j/n),U.lerp(y0,y1,j/n),3,3,cor);};
          segmento(96,183,103,181-gesto*3,manga);
          segmento(103,181-gesto*3,ox+6,oy+5,PAL.pele);
          objeto(item,ox,oy);px(ox+6,oy+4,3,3,PAL.pele);
          if(item==='cafe')for(let j=0;j<2;j++)px(ox+1+j*3,oy-3-((Math.floor(local*5)+j*2)%5),1,2,'#FFF1E899');
          break;
        }
        case 'dorme': sprite(at[0], 112, 112, 0, 1); px(106, 150, 66, 18, PAL.branco); break;
        case 'compra': case 'recebe': { sprite(at[0], 70, yb, 0, 1); const h = hudEm(t); if (cn.acao === 'compra' || !Number.isFinite(cn.hud?.ouro) || !Number.isFinite(h.ouroAntes) || cn.hud.ouro > h.ouroAntes) for (let i = 0; i < 6; i++) { const q = (local * 1.5 + i / 6) % 1; objeto('moeda', 80 + Math.sin(i * 2) * 20, cn.acao === 'recebe' ? 40 + q * 150 : 180 - q * 150); } if (cn.objeto && cn.objeto !== 'moeda') objeto(cn.objeto, 98, yb + 30); break; }
        case 'batalha': sprite(at[0], 14, 162, passo, 1, 3); sprite(at[1] || 'chefe', 96, 76, 0, -1, 6); if (k > 0.45 && k < 0.6) px(0, 0, PW, PH, '#FFFFFF66'); extraUI = 'batalha'; break;
        case 'level_up': sprite(at[0], 84, yb, 0, 1); for (let i = 0; i < 10; i++) { const q = (local * 2 + i / 10) % 1; px(80 + (i % 5) * 6, yb + 20 - q * 120, 2, 2, i % 2 ? PAL.amarelo : PAL.branco); } extraUI = 'level'; break;
        case 'game_over': {
          // T359: abertura viva continua a história; finais e fim explícito preservados.
          const aberturaViva = cn === spec.cenas[0] && spec.cenas.length > 1 &&
            Number.isFinite(cn.hud?.hp) && cn.hud.hp > 0 &&
            !/\b(?:game\s+over|fin\s+del\s+juego|fim\s+de\s+jogo)\b/i.test(cn.texto || '');
          sprite(at[0], 84, yb + 10, 0, 1); extraUI = aberturaViva ? null : 'over'; break;
        }
        case 'missao': sprite(at[0], 84, yb, 0, 1); extraUI = 'missao'; break;
        default: sprite(at[0], 30, yb, Math.floor(t * 2) % 2, 1); if (at[1]) sprite(at[1], 116, yb, 0, -1);
      }
      if (cn.objeto && ['acorda', 'digita', 'come', 'compra', 'recebe'].indexOf(cn.acao) < 0) objeto(cn.objeto, cn.acao === 'anda' ? U.lerp(-36, 150, k) + 28 : 82, cn.acao === 'anda' ? yb + 30 : 160 + Math.sin(t * 4) * 2);
      b.restore();
      c.imageSmoothingEnabled = false; c.drawImage(buf, 0, 0, W, H); c.drawImage(buf, 0, -MUNDO_DY, W, H);
      if (extraUI === 'over') { c.fillStyle = 'rgba(0,0,0,' + (0.75 * U.clamp(k * 2, 0, 1)).toFixed(2) + ')'; c.fillRect(0, 0, W, H); c.font = F(86); c.fillStyle = PAL.vermelho; c.textAlign = 'center'; c.fillText('GAME OVER', W / 2, 820); if (k > 0.5) { c.font = F(36); c.fillStyle = PAL.branco; c.fillText('CONTINUE? ' + (9 - Math.floor((k - 0.5) * 18)), W / 2, 960); } }
      hud(t);
      if (extraUI === 'level') banner('LEVEL UP!', local, PAL.verde2);
      if (extraUI === 'missao') banner('NEW QUEST', local, PAL.azul2);
      if (extraUI === 'batalha') { if (!cn.texto) { caixa(DLG.x, DLG.y, DLG.w, DLG.h); c.font = F(46); c.textAlign = 'left'; c.textBaseline = 'middle'; ['FIGHT', 'ITEM', 'RUN', 'CRY'].forEach((o, i) => { c.fillStyle = PAL.branco; c.fillText(o, DLG.x + 130 + (i % 2) * 380, DLG.y + 140 + Math.floor(i / 2) * 120); });
        const sel = Math.min(3, Math.floor(k * 4)); c.fillStyle = PAL.amarelo; { const ax = DLG.x + 70 + (sel % 2) * 380, ay = DLG.y + 140 + Math.floor(sel / 2) * 120; c.beginPath(); c.moveTo(ax, ay - 20); c.lineTo(ax + 32, ay); c.lineTo(ax, ay + 20); c.closePath(); c.fill(); } }
        if (k > 0.45 && k < 0.8 && Number.isFinite(cn.dano) && cn.dano > 0) { c.font = F(70); c.fillStyle = PAL.vermelho; c.textAlign = 'center'; c.fillText('-' + cn.dano, W * 0.3, 1100 - MUNDO_DY - (k - 0.45) * 400); } }
      if (cn.texto) dialogo(cn.texto, local, cn.quem);
      if (cn.texto && cn.acao === 'missao') { c.font = F(40); c.fillStyle = PAL.branco; c.textAlign = 'center'; }
      U.cartaz(c, spec, t, { fonte: F(48), y: ZS.topo + 165, fundo: PAL.vermelho, borda: PAL.branco, cor: PAL.branco, altura_linha: 70, raio: 0, dur: 2.6, caixa: true });
      // linhas de varredura de tela de tubo
      if(legado || spec.crt === true){c.fillStyle = legado ? 'rgba(0,0,0,.08)' : 'rgba(0,0,0,.045)'; for (let y = 0; y < H; y += 6) c.fillRect(0, y, W, legado ? 2 : 1);}
    }
    // =====================================================================
    // PIXEL v2 (05/11/2026, pedido do dono: salto de qualidade por motor).
    // O que mudou contra o v1 (folha de bancada 05/11):
    //  - herói 16x24 com contorno, sombra e EXPRESSÃO (era 12x16 sem rosto legível,
    //    36x48 px de buffer = 20% da largura, pés escondidos atrás da caixa);
    //  - o chão subiu para fora da caixa de diálogo: o personagem inteiro aparece;
    //  - cenários cheios (janela com céu, objetos com volume, luz, primeiro plano);
    //  - câmera: closes 2x nos momentos de emoção, tremor no dano, transição em
    //    mosaico entre cenas;
    //  - batalha de RPG de verdade: chefe grande com nome e barra de vida própria;
    //  - balão de emoção sobre a cabeça; narração (se houver) revela o diálogo
    //    no ritmo das palavras faladas.
    // O contrato (ações, cenários, objetos, hud, dano, quem) é o mesmo do v1 e as
    // regras semânticas (T294..T392) valem igual: um objeto() por item pedido.
    // =====================================================================
    const C2 = { o: '#1a1423', h: PAL.cabelo, H: '#6e4630', s: PAL.pele, S: '#e8a07a', e: '#fff1e8', k: '#1a1423', m: '#8a3a3a',
      a: '#2a9d8f', A: '#1f7368', d: '#33406b', D: '#252f52', b: '#3b2a20', r: PAL.vermelho, w: PAL.branco, g: '#5a5a6e', G: '#44445a', y: PAL.amarelo, Y: '#d9a400', v: '#3aa35b', V: '#2b7a44', p: '#ff77a8', P: '#c85a85' };
    const METADE = [
      '......oo', '....oohh', '...ohhHh', '..ohhhhh', '..ohhsss', '..ohssss', '..osseks', '..osssss',
      '...ossss', '...osssm', '....osss', '.....oss', '...ooaaa', '..oaaaaa', '..oaoaaa', '..oaoaAa',
      '..oaoaAa', '..osoaaa', '...oDddd', '...odddd', '...oddoo', '...oddo.', '...obbo.', '..obbbo.'];
    const espelhar = (l) => l + [...l].reverse().join('');
    const BASE = METADE.map(espelhar);
    // Cada personagem troca cores/linhas do mesmo esqueleto (mesmo tamanho, mesma leitura).
    const ELENCO = {
      heroi: { troca: {} },
      chefe: { troca: { h: '#d9b38c', H: '#e8c9a8', a: '#3b3b4f', A: '#2c2c3b', d: '#2c2c3b', D: '#1f1f2b' }, gravata: true, careca: true },
      mae: { troca: { h: '#8a3324', H: '#b5503a', a: '#e85d75', A: '#b8475b' }, avental: true },
      npc: { troca: { h: '#e0c341', H: '#f5dd6a', a: '#3aa35b', A: '#2b7a44' } },
      gato: { gato: true }
    };
    const GATO = ['................', '................', '................', '................', '................', '................',
      '................', '................', '................', '................', '................', '................',
      '..o.o...........', '.oyoyo..........', '.oyyyo.......oo.', '.okyko......oyo.', '.oyyyoooooooyo..', '..oyyyyyyyyyyo..',
      '..oyyyyyyyyyyo..', '..oyyyyyyyyyyo..', '..oyoyoooyoyo...', '..oyoyo..oyoyo..', '..oo.oo..oo.oo..', '................'];
    const sprites2 = new Map();
    function boneco(nome, quadro, dir, expr) {
      const key = [nome, quadro, dir, expr].join(':');
      if (sprites2.has(key)) return sprites2.get(key);
      const def = ELENCO[nome] || ELENCO.heroi;
      let linhas = def.gato ? GATO.slice() : BASE.slice();
      if (!def.gato) {
        if (def.careca) { linhas[1] = '....oossssoo....'; linhas[2] = '...ossssssssso..'.slice(0, 16); linhas[3] = '..osssssssssso..'; }
        if (def.gravata) { for (let j = 12; j <= 16; j++) linhas[j] = linhas[j].slice(0, 7) + (j === 12 ? 'ww' : 'rr') + linhas[j].slice(9); }
        if (def.avental) { for (let j = 14; j <= 19; j++) linhas[j] = linhas[j].slice(0, 5) + 'wwwwww' + linhas[j].slice(11); }
        // expressão: olhos (linha 6) e boca (linha 9)
        if (expr === 'feliz') { linhas[6] = linhas[6].replace('seks', 'skss').replace('skes', 'sskS'.replace('S', 's')); linhas[9] = '...ossmssmsso...'; linhas[10] = '....ossmmsso....'; }
        if (expr === 'triste') { linhas[6] = '..ossokssksso..'.padEnd(16, '.'); linhas[9] = '...osssmmssso...'; linhas[10] = '....osmssmso....'; }
        if (expr === 'susto') { linhas[5] = '..ohsekssekso...'.slice(0, 16); linhas[9] = '...osssmmssso...'; linhas[10] = '....ossmmsso....'; }
        if (expr === 'raiva') { linhas[5] = '..ohokssssko...'.padEnd(16, '.'); linhas[9] = '...osmmmmmmso...'; }
        if (expr === 'dorme') { linhas[6] = '..ossoossooss...'.slice(0, 16); }
        if (quadro) { // passo: pernas alternadas
          linhas[20] = '...oddoo..oddo..'; linhas[21] = '..oddo....oddo..'; linhas[22] = '..obbo....obbo..'; linhas[23] = '.obbbo.....obbbo';
        }
      }
      const cores = Object.assign({}, C2, def.troca || {});
      const cv = document.createElement('canvas'); cv.width = 16; cv.height = 24; const g = cv.getContext('2d');
      linhas.forEach((lin, j) => { for (let i = 0; i < 16; i++) { const ch = lin[dir < 0 ? 15 - i : i]; if (ch && ch !== '.' && cores[ch]) { g.fillStyle = cores[ch]; g.fillRect(i, j, 1, 1); } } });
      sprites2.set(key, cv); return cv;
    }
    // desenha o boneco com os pés em (x, chao), escala inteira e = 3 (48x72 no buffer)
    function ator(nome, x, chao, opts) {
      const o = opts || {}, e = o.e || 3, cv = boneco(nome, o.quadro || 0, o.dir || 1, o.expr || 'neutro');
      b.fillStyle = '#00000040'; b.fillRect(Math.round(x + 2 * e), Math.round(chao - 2), 12 * e, 3);
      const pulo = o.pulo || 0;
      if (b.drawImage) b.drawImage(cv, Math.round(x), Math.round(chao - 24 * e - pulo), 16 * e, 24 * e);
    }
    // balão de emoção em pixel: '!', '?', '♥', '$', 'z', '#'
    function emote(tipo, x, y, local) {
      const p = U.clamp(local * 4, 0, 1); if (p <= 0) return;
      const yy = y - Math.round(4 * U.mola(local, 14));
      px(x, yy, 15, 13, '#1a1423'); px(x + 1, yy + 1, 13, 11, PAL.branco); px(x + 5, yy + 13, 4, 2, '#1a1423'); px(x + 6, yy + 12, 2, 2, PAL.branco);
      const cor = { '!': PAL.vermelho, '?': '#29adff', '♥': PAL.rosa, '$': '#d9a400', 'z': '#83769c', '#': PAL.vermelho }[tipo] || '#1a1423';
      const G = { '!': ['..x..', '..x..', '..x..', '.....', '..x..'], '?': ['.xxx.', '...x.', '..x..', '.....', '..x..'], '♥': ['.x.x.', 'xxxxx', 'xxxxx', '.xxx.', '..x..'],
        '$': ['.xxx.', 'x.x..', '.xxx.', '..x.x', '.xxx.'], 'z': ['xxxx.', '..x..', '.x...', 'xxxx.', '.....'], '#': ['x.x.x', '.xxx.', 'xx.xx', '.xxx.', 'x.x.x'] }[tipo] || [];
      G.forEach((l, j) => { for (let i = 0; i < 5; i++) if (l[i] === 'x') px(x + 3 + i * 2 - 1, yy + 2 + j * 2 - 1, 2, 2, cor); });
    }
    const CHAO = 170;
    // ---------------- cenários v2 (fundos cacheados) ----------------
    function sombra(x, y, w, h) { px(x, y, w, h, '#00000030'); }
    function caixa3d(x, y, w, h, cor, escura) { px(x, y, w, h, '#1a1423'); px(x + 1, y + 1, w - 2, h - 2, cor); px(x + 1, y + h - 4, w - 2, 3, escura); }
    function janela(x, y, w, h, noite) {
      px(x - 2, y - 2, w + 4, h + 4, '#1a1423'); px(x, y, w, h, noite ? '#1d2b53' : '#8fd3ff');
      if (!noite) { px(x, y + h * .6, w, h * .4, '#bfe9ff'); px(x + 4, y + 6, 10, 4, PAL.branco); px(x + 8, y + 4, 8, 3, PAL.branco); px(x + w - 22, y + h - 14, 22, 14, '#7e7058'); px(x + w - 18, y + h - 22, 10, 8, '#83769c'); }
      else { for (let i = 0; i < 8; i++) { const r = U.rng(i + x)(); px(x + r * w, y + ((i * 7) % h), 1, 1, PAL.branco); } px(x + w - 12, y + 5, 6, 6, '#fff1a8'); }
      px(x + w / 2 - 1, y, 2, h, '#e8e0d0'); px(x, y + h / 2 - 1, w, 2, '#e8e0d0'); px(x - 4, y + h + 2, w + 8, 4, '#c8b89a'); px(x - 4, y + h + 5, w + 8, 1, '#1a1423');
    }
    function parede(cor, faixa, padrao) {
      px(0, 0, PW, CHAO, cor);
      for (let y = 6; y < CHAO; y += 12) for (let x = (y / 12) % 2 ? 0 : 6; x < PW; x += 12) px(x, y, padrao ? 2 : 1, padrao ? 2 : 1, faixa);
      px(0, CHAO - 10, PW, 10, '#e8e0d0'); px(0, CHAO - 10, PW, 1, '#1a1423'); px(0, CHAO - 1, PW, 1, '#1a1423');
    }
    function piso(cor, linha) {
      px(0, CHAO, PW, PH - CHAO, cor);
      for (let r = 0; r < 12; r++) { const y = CHAO + 3 + r * (6 + r * 2); for (let x = (r % 2) * 12; x < PW; x += 24) px(x, y, 1, 4 + r, linha); px(0, y, PW, 1, linha); }
      px(0, CHAO, PW, 2, '#00000040');
    }
    function fundo2(nome) {
      if (fundos.has('v2:' + nome)) return fundos.get('v2:' + nome);
      const cv = document.createElement('canvas'); cv.width = PW; cv.height = PH;
      const antigo = b; const g = cv.getContext('2d'); b = g;
      try {
        if (nome === 'onibus_int') {
          // interior do ônibus: janelas vazadas (a cidade passa por trás, desenhada a cada quadro)
          px(0, 0, PW, CHAO, '#e88a2a'); px(0, 0, PW, 22, '#c96a1a'); px(0, 22, PW, 2, '#1a1423');
          if (g.clearRect) for (let i = 0; i < 3; i++) g.clearRect(8 + i * 58, 34, 50, 56);
          for (let i = 0; i < 3; i++) { px(6 + i * 58, 32, 54, 2, '#1a1423'); px(6 + i * 58, 90, 54, 3, '#1a1423'); px(6 + i * 58, 32, 2, 60, '#1a1423'); px(58 + i * 58, 32, 2, 60, '#1a1423'); }
          for (let i = 0; i < 4; i++) { px(4 + i * 50, 22, 3, CHAO - 22, '#ffd36a'); px(4 + i * 50, 22, 1, CHAO - 22, '#1a1423'); px(0 + i * 50, 28, 11, 6, '#ffd36a'); }
          for (let i = 0; i < 3; i++) { caixa3d(14 + i * 58, 118, 40, 30, '#29adff', '#1d6fa3'); caixa3d(14 + i * 58, 104, 10, 44, '#29adff', '#1d6fa3'); }
          px(0, CHAO, PW, PH - CHAO, '#3b3b4f'); for (let x = 0; x < PW; x += 6) px(x, CHAO, 3, PH - CHAO, '#33334a'); px(0, CHAO, PW, 2, '#1a1423');
        } else if (nome === 'rua' || nome === 'onibus') {
          for (let y = 0; y < CHAO; y++) px(0, y, PW, 1, y < 60 ? '#8fd3ff' : y < 110 ? '#a8e0ff' : '#c9eeff');
          px(18, 18, 26, 8, PAL.branco); px(24, 13, 16, 6, PAL.branco); px(120, 30, 30, 7, PAL.branco);
          for (let i = 0; i < 6; i++) { const x = i * 32 - 6, h = 60 + (i * 37) % 50; caixa3d(x, CHAO - 20 - h, 30, h, ['#c97b63', '#83769c', '#7e7058', '#5f8fa8'][i % 4], '#00000030');
            for (let r = 0; r < Math.floor(h / 14) - 1; r++) for (let q = 0; q < 2; q++) px(x + 5 + q * 12, CHAO - 14 - h + r * 14, 7, 8, (r + q + i) % 3 ? '#ffe28a' : '#33406b'); }
          px(0, CHAO - 20, PW, 20, '#9a9aa8'); px(0, CHAO - 20, PW, 1, '#1a1423'); for (let x = 0; x < PW; x += 30) px(x, CHAO - 20, 1, 20, '#7a7a88');
          px(0, CHAO, PW, PH - CHAO, '#4a4a58'); for (let x = 4; x < PW; x += 28) px(x, CHAO + 40, 14, 3, PAL.branco);
          px(150, CHAO - 68, 3, 48, '#1a1423'); px(144, CHAO - 72, 15, 6, '#1a1423'); px(146, CHAO - 70, 11, 2, '#ffe28a');
        } else if (nome === 'chefe_arena') {
          for (let y = 0; y < PH; y++) px(0, y, PW, 1, y < 120 ? '#1d1433' : y < CHAO ? '#2a1a4a' : '#160f26');
          for (let i = 0; i < 50; i++) { const r = U.rng(i * 7 + 3); px(r() * PW, r() * 150, 1, 1, i % 5 ? '#c2c3c7' : PAL.amarelo); }
          for (let i = 0; i < 9; i++) { const x = i * 22 - 4, h = 18 + (i * 13) % 26; px(x, CHAO - h, 20, h, '#120b22'); }
          px(0, CHAO, PW, 2, PAL.vermelho); for (let r = 0; r < 8; r++) px(0, CHAO + 8 + r * r * 3, PW, 1, '#ff004d55');
        } else {
          const tema = { quarto: ['#83769c', '#9a8db5', '#c08a5a', '#8a5a3a'], escritorio: ['#bfc6cf', '#d3d9e0', '#8a8f99', '#6b707a'],
            cozinha: ['#f2d3ab', '#f8e2c4', '#d9d9d9', '#b5b5b5'], mercado: ['#f0ece4', '#e2dccf', '#c9c2b4', '#a8a090'],
            academia: ['#3b3b4f', '#48485e', '#2c2c3b', '#22222f'] }[nome] || ['#bfc6cf', '#d3d9e0', '#8a8f99', '#6b707a'];
          parede(tema[0], tema[1], nome === 'quarto' || nome === 'cozinha'); piso(tema[2], tema[3]);
          if (nome === 'quarto') {
            janela(14, 36, 46, 40, false);
            caixa3d(104, 112, 70, 26, PAL.branco, '#c2c3c7'); caixa3d(104, 104, 20, 12, PAL.branco, '#d6d6dc'); caixa3d(100, 136, 78, 34, '#ab5236', '#7e2553');
            px(118, 118, 50, 10, '#29adff'); px(118, 126, 50, 2, '#1d6fa3');
            caixa3d(70, 52, 22, 28, '#ff77a8', '#c85a85'); px(74, 58, 14, 2, PAL.branco); px(74, 64, 10, 2, PAL.branco);
            caixa3d(66, 140, 22, 30, '#7e5a3a', '#5a3e28'); px(70, 134, 14, 7, '#ffd36a'); px(76, 128, 2, 7, '#1a1423'); px(72, 126, 10, 3, '#ffd36a');
          } else if (nome === 'escritorio') {
            janela(120, 30, 44, 36, false);
            caixa3d(14, 120, 100, 8, '#ab5236', '#7e2553'); px(20, 128, 5, 42, '#5a3e28'); px(104, 128, 5, 42, '#5a3e28');
            caixa3d(36, 88, 50, 32, '#1a1423', '#000'); px(39, 91, 44, 24, '#29adff'); for (let i = 0; i < 4; i++) px(43, 95 + i * 5, 20 + (i * 7) % 18, 2, PAL.branco); px(57, 120, 8, 4, '#5f574f');
            caixa3d(140, 120, 26, 50, '#c2c3c7', '#9a9aa8'); for (let i = 0; i < 3; i++) px(144, 126 + i * 15, 18, 1, '#1a1423');
            px(16, 60, 22, 28, '#e8e0d0'); px(18, 62, 18, 14, '#ff77a8'); px(20, 80, 14, 2, '#5f574f');
            caixa3d(92, 106, 14, 14, '#3aa35b', '#2b7a44'); px(96, 98, 6, 8, '#3aa35b');
          } else if (nome === 'cozinha') {
            janela(70, 34, 40, 34, false);
            caixa3d(130, 70, 44, 100, PAL.branco, '#d6d6dc'); px(132, 112, 40, 1, '#1a1423'); px(166, 90, 3, 16, '#8a8f99'); px(166, 120, 3, 20, '#8a8f99');
            caixa3d(8, 120, 110, 50, '#e8e0d0', '#c9c2b4'); px(8, 118, 110, 4, '#8a8f99'); px(18, 130, 30, 30, '#d3d9e0'); px(60, 130, 30, 30, '#d3d9e0');
            px(20, 110, 16, 8, '#1a1423'); px(22, 108, 12, 3, '#5f574f');
            for (let i = 0; i < 4; i++) caixa3d(10 + i * 14, 60, 12, 16, ['#ff004d', '#ffa300', '#3aa35b', '#29adff'][i], '#00000030');
          } else if (nome === 'mercado') {
            for (let r = 0; r < 3; r++) { caixa3d(6, 62 + r * 36, 168, 5, '#ab5236', '#7e2553');
              for (let i = 0; i < 13; i++) caixa3d(9 + i * 12.6, 44 + r * 36, 10, 18, ['#ff004d', '#ffec27', '#3aa35b', '#29adff', '#ffa300'][(i + r) % 5], '#00000030'); }
            px(0, 8, PW, 18, '#ff004d'); for (let i = 0; i < 9; i++) px(6 + i * 20, 14, 10, 6, PAL.branco);
            caixa3d(120, 140, 50, 30, '#c2c3c7', '#9a9aa8'); px(124, 132, 42, 8, '#5f574f');
          } else if (nome === 'academia') {
            px(0, 20, PW, 26, PAL.vermelho); for (let i = 0; i < 6; i++) px(8 + i * 30, 28, 18, 10, PAL.branco);
            for (let i = 0; i < 3; i++) { px(18 + i * 55, 146, 36, 4, '#8a8f99'); caixa3d(14 + i * 55, 138, 8, 20, '#1a1423', '#000'); caixa3d(48 + i * 55, 138, 8, 20, '#1a1423', '#000'); }
            caixa3d(120, 80, 50, 60, '#5f574f', '#3b3b4f'); px(126, 86, 38, 30, '#83c5ff');
          }
        }
      } finally { b = antigo; }
      fundos.set('v2:' + nome, cv); return cv;
    }
    function objeto2(nome, x, y) {
      // Itens em 2x do v1 (mesmos nomes, contorno escuro): leem no celular.
      const q = (dx, dy, w, h, cor) => px(x + dx * 2, y + dy * 2, w * 2, h * 2, cor);
      const contorno = (w, h) => px(x - 1, y - 1, w * 2 + 2, h * 2 + 2, '#1a1423');
      if (nome === 'cafe') { contorno(7, 7); q(0, 0, 6, 7, PAL.branco); q(6, 1, 1, 4, PAL.branco); q(1, 1, 4, 2, PAL.madeira); }
      else if (nome === 'sorvete') { q(2, 5, 4, 3, PAL.laranja); q(3, 8, 2, 2, PAL.laranja); q(1, 1, 6, 4, PAL.rosa); q(2, 0, 4, 1, PAL.rosa); q(2, 1, 1, 1, PAL.branco); }
      else if (nome === 'boleto') { contorno(8, 10); q(0, 0, 8, 10, PAL.branco); for (let i = 0; i < 4; i++) q(1, 2 + i * 2, 6, 1, PAL.cinza); q(4, 8, 4, 1, PAL.vermelho); }
      else if (nome === 'celular') { contorno(5, 9); q(0, 0, 5, 9, PAL.preto); q(1, 1, 3, 6, PAL.azul); q(2, 8, 1, 1, '#5f574f'); }
      else if (nome === 'pizza') { for (let i = 0; i < 8; i++) q(i / 2, i, 8 - i, 1, i < 1 ? PAL.madeira : PAL.amarelo); q(2, 2, 1, 1, PAL.vermelho); q(4, 3, 1, 1, PAL.vermelho); }
      else if (nome === 'moeda') { px(x + 1, y, 4, 6, '#1a1423'); px(x, y + 1, 6, 4, '#1a1423'); px(x + 1, y + 1, 4, 4, PAL.amarelo); px(x + 2, y + 2, 1, 2, '#fff1a8'); }
      else if (nome === 'alarme') { contorno(8, 9); q(0, 2, 8, 7, PAL.vermelho); q(2, 3, 4, 4, PAL.branco); q(3, 4, 1, 2, '#1a1423'); q(-1, 0, 3, 2, PAL.amarelo); q(6, 0, 3, 2, PAL.amarelo); }
      else if (nome === 'email') { contorno(10, 7); q(0, 0, 10, 7, PAL.branco); for (let i = 0; i < 5; i++) { q(i, i * .6, 1, 1, PAL.cinza); q(9 - i, i * .6, 1, 1, PAL.cinza); } }
      else { contorno(6, 6); q(0, 0, 6, 6, PAL.amarelo); }
    }
    // câmera: (zoom inteiro, centro) por cena; tremor quando o HUD cai
    function camera(cn, k, t) {
      const fechado = { come: 1, game_over: 1, level_up: 1, acorda: 1, dorme: 1 }[cn.acao] || /\bclose\b/.test(String(cn.camera || ''));
      return fechado ? { z: 2, cx: 64, cy: CHAO - 46 } : { z: 1, cx: PW / 2, cy: PH / 2 };
    }
    function revelado(cn, local, texto) {
      // narrado: revela na proporção das palavras já faladas nesta cena
      const pw = spec.palavras;
      if (Array.isArray(pw) && pw.length) {
        const t = cn.ini + local, da = pw.filter((p) => p.ini >= cn.ini - .05 && p.ini < cn.fim);
        if (da.length) { const ditas = da.filter((p) => p.ini <= t).length; return Math.round(texto.length * ditas / da.length); }
      }
      return null;
    }
    function quadro2(t) {
      const { c: cn, i: idx, k, local } = U.cenaEm(spec, t);
      const passo = Math.floor(t * 6) % 2, at = cn.atores && cn.atores.length ? cn.atores : ['heroi'];
      const cen = cn.acao === 'batalha' ? 'chefe_arena' : (cn.cenario || 'quarto');
      const h = hudEm(t);
      if (cen === 'onibus') {
        // cidade correndo atrás das janelas (paralaxe), depois o interior vazado por cima
        px(0, 30, PW, 64, '#8fd3ff');
        for (let i = 0; i < 9; i++) { const x = ((i * 34 - t * 48) % 306 + 306) % 306 - 40, hh = 26 + (i * 17) % 30;
          px(x, 92 - hh, 28, hh, ['#c97b63', '#83769c', '#7e7058', '#5f8fa8'][i % 4]); for (let r = 0; r < hh / 9 - 1; r++) px(x + 4, 96 - hh + r * 9, 20, 4, '#ffe28a'); }
        b.drawImage(fundo2('onibus_int'), 0, 0);
      } else b.drawImage(fundo2(cen), 0, 0);
      let extraUI = null, emo = null, ex = 64, ey = CHAO - 84;
      const HX = 40, NX = 104;
      switch (cn.acao) {
        case 'acorda': {
          const deitado = k < 0.45;
          if (deitado) { ator(at[0], 116, 136, { expr: 'dorme' }); px(104, 118, 70, 16, PAL.branco); px(104, 118, 70, 1, '#1a1423'); emo = 'z'; ex = 140; ey = 92; }
          else { ator(at[0], HX, CHAO, { expr: 'susto', pulo: Math.round(6 * Math.max(0, Math.sin((k - .45) * 12))) }); emo = '!'; ex = HX + 16; }
          if (cn.objeto && cn.objeto !== 'alarme') objeto(cn.objeto, deitado ? 92 : HX + 50, deitado ? 150 : CHAO - 40);
          else objeto('alarme', 84, 146 + (Math.floor(t * 12) % 2));
          break;
        }
        case 'anda': ator(at[0], U.lerp(-20, 120, k), CHAO, { quadro: passo, expr: 'neutro' }); if (at[1]) ator(at[1], 120, CHAO, { dir: -1 }); break;
        case 'digita': {
          // herói sentado de costas para a mesa do escritório, mãos no teclado
          ator(at[0], 20, CHAO, { expr: k > .6 ? 'raiva' : 'neutro' });
          px(66, 112 + (passo ? 0 : 1), 10, 4, PAL.pele);
          objeto(cn.objeto || 'cafe', cn.objeto ? 80 : 94, cn.objeto ? 102 : 104);
          emo = k > .6 ? '#' : null; ex = 34;
          break;
        }
        case 'come': {
          const texto = typeof cn.texto === 'string' ? cn.texto.normalize('NFD').replace(/[̀-ͯ]/g, '').trim().replace(/\s+/g, ' ').toLowerCase() : '';
          const cafeLiteral = /^(?:you used coffee|usaste cafe(?: frio)?|voce usou cafe(?: frio)?)[.!](?:\s|$)/.test(texto);
          const sorveteLiteral = /^(?:you ate ice cream|comiste helado|voce comeu sorvete)[.!](?:\s|$)/.test(texto);
          const item = (!cn.objeto || cn.objeto === 'pizza') && sorveteLiteral ? 'sorvete' : (cafeLiteral && (!cn.objeto || cn.objeto === 'pizza') ? 'cafe' : (cn.objeto || 'pizza'));
          const levantar = U.suave(U.clamp((k - .12) / .28, 0, 1)), baixar = U.suave(U.clamp((k - .72) / .23, 0, 1)), gesto = levantar * (1 - baixar);
          ator(at[0], HX, CHAO, { expr: gesto > .5 ? 'feliz' : 'neutro' });
          objeto(item, Math.round(U.lerp(HX + 40, HX + 26, gesto)), Math.round(U.lerp(CHAO - 34, CHAO - 50, gesto)));
          emo = gesto > .6 ? '♥' : null; ex = HX + 20;
          break;
        }
        case 'dorme': ator(at[0], 116, 136, { expr: 'dorme' }); px(104, 118, 70, 16, PAL.branco); px(104, 118, 70, 1, '#1a1423'); emo = 'z'; ex = 140; ey = 92; break;
        case 'compra': case 'recebe': {
          const sobe = Number.isFinite(cn.hud?.ouro) && Number.isFinite(h.ouroAntes) && cn.hud.ouro > h.ouroAntes;
          ator(at[0], HX, CHAO, { expr: cn.acao === 'recebe' && sobe ? 'feliz' : (cn.acao === 'compra' ? 'triste' : 'neutro') });
          if (cn.acao === 'compra' || !Number.isFinite(cn.hud?.ouro) || !Number.isFinite(h.ouroAntes) || cn.hud.ouro > h.ouroAntes)
            for (let i = 0; i < 8; i++) { const q = (local * 1.4 + i / 8) % 1; objeto('moeda', HX + 18 + Math.sin(i * 2.3) * 26, cn.acao === 'recebe' ? 70 + q * 90 : CHAO - 40 - q * 100); }
          if (cn.objeto && cn.objeto !== 'moeda') objeto(cn.objeto, HX + 54, CHAO - 44);
          emo = cn.acao === 'recebe' && sobe ? '$' : (cn.acao === 'compra' ? '!' : null); ex = HX + 16;
          break;
        }
        case 'batalha': {
          const golpe = k > 0.42 && k < 0.62, recuo = golpe ? Math.round(Math.sin((k - .42) * 60) * 3) : 0;
          ator(at[1] || 'chefe', 78 + recuo, CHAO - 10, { e: 5, dir: -1, expr: 'raiva' });
          ator(at[0], 8 + (k > .3 && k < .45 ? Math.round((k - .3) * 160) : 0), CHAO + 22, { expr: k > .5 ? 'susto' : 'raiva' });
          if (golpe) { for (let i = 0; i < 14; i++) px(70 + i * 3, 60 + i * 5, 4, 3, PAL.branco); px(0, 0, PW, PH, '#ffffff33'); }
          extraUI = 'batalha'; break;
        }
        case 'level_up': ator(at[0], HX, CHAO, { expr: 'feliz', pulo: Math.round(8 * Math.abs(Math.sin(local * 5))) }); for (let i = 0; i < 16; i++) { const q = (local * 1.6 + i / 16) % 1; px(HX + 4 + (i % 8) * 6, CHAO - q * 120, 2, 2, i % 2 ? PAL.amarelo : PAL.branco); } extraUI = 'level'; break;
        case 'game_over': {
          const aberturaViva = cn === spec.cenas[0] && spec.cenas.length > 1 && Number.isFinite(cn.hud?.hp) && cn.hud.hp > 0 &&
            !/\b(?:game\s+over|fin\s+del\s+juego|fim\s+de\s+jogo)\b/i.test(cn.texto || '');
          ator(at[0], HX, CHAO, { expr: 'triste' }); emo = aberturaViva ? '!' : null; ex = HX + 16; extraUI = aberturaViva ? null : 'over'; break;
        }
        case 'missao': ator(at[0], HX, CHAO, { expr: 'susto' }); emo = '!'; ex = HX + 16; extraUI = 'missao'; break;
        default: ator(at[0], HX, CHAO, { quadro: Math.floor(t * 2) % 2, expr: cn.quem && at[1] ? 'neutro' : 'neutro' }); if (at[1]) ator(at[1], NX, CHAO, { dir: -1, expr: 'neutro' });
      }
      if (cn.objeto && ['acorda', 'digita', 'come', 'compra', 'recebe'].indexOf(cn.acao) < 0)
        objeto(cn.objeto, cn.acao === 'anda' ? U.lerp(-20, 120, k) + 40 : HX + 52, cn.acao === 'anda' ? CHAO - 40 : CHAO - 44 + Math.round(Math.sin(t * 4) * 2));
      if (emo) emote(emo, ex, ey, local);
      // ---- composição na tela: câmera, tremor, transição em mosaico ----
      const cam = camera(cn, k, t), z = cam.z, vw = PW / z, vh = PH / z;
      let x0 = U.clamp(cam.cx - vw / 2, 0, PW - vw), y0 = U.clamp(cam.cy - vh * .42, 0, PH - vh);
      const tremor = h.caiu ? Math.round(Math.sin(t * 70) * 2) : 0;
      c.imageSmoothingEnabled = false;
      const entrada = idx > 0 ? U.clamp(local / .18, 0, 1) : 1;
      if (entrada < 1) {
        // mosaico: a cena nova nasce em blocos grandes que viram pixels
        const bloco = Math.max(1, Math.round(12 * (1 - entrada)));
        const mini = document.createElement('canvas'); mini.width = Math.ceil(vw / bloco); mini.height = Math.ceil(vh / bloco);
        const mg = mini.getContext('2d'); if (mg.drawImage) mg.drawImage(buf, x0, y0, vw, vh, 0, 0, mini.width, mini.height);
        if (mg.imageSmoothingEnabled !== undefined) mg.imageSmoothingEnabled = false;
        c.drawImage(mini, 0, 0, mini.width, mini.height, tremor * K, 0, W, H);
      } else c.drawImage(buf, x0, y0, vw, vh, tremor * K, 0, W, H);
      if (extraUI === 'over') { c.fillStyle = 'rgba(0,0,0,' + (0.72 * U.clamp(k * 2, 0, 1)).toFixed(2) + ')'; c.fillRect(0, 0, W, H); c.font = F(90); c.textAlign = 'center'; c.textBaseline = 'middle'; c.lineWidth = 14; c.strokeStyle = '#1a1423'; c.strokeText('GAME OVER', W / 2, 640); c.fillStyle = PAL.vermelho; c.fillText('GAME OVER', W / 2, 640); if (k > 0.5) { c.font = F(38); c.fillStyle = PAL.branco; c.fillText('CONTINUE? ' + (9 - Math.floor((k - 0.5) * 18)), W / 2, 760); } }
      hud(t);
      if (extraUI === 'level') banner('LEVEL UP!', local, PAL.verde2);
      if (extraUI === 'missao') banner('NEW QUEST', local, PAL.azul2);
      if (extraUI === 'batalha') {
        // barra do chefe: nome = quem fala (ou o objeto), vida cai no golpe
        const quemSis = !cn.quem || /^(sistema|system|narrador|narrator|game|juego|jogo)$/i.test(String(cn.quem).trim());
        const NOMES = { boleto: 'BILL', celular: 'PHONE', email: 'INBOX', alarme: 'ALARM', cafe: 'COFFEE', pizza: 'PIZZA', moeda: 'DEBT' };
        const nome = String(quemSis ? (NOMES[cn.objeto] || 'BOSS') : cn.quem).toUpperCase().slice(0, 14);
        const vida = Number.isFinite(cn.dano) && cn.dano > 0 ? U.lerp(1, .45, U.suave(U.clamp((k - .45) / .2, 0, 1))) : 1;
        const bx = ZS.esq + 20, by = ZS.topo + 150, bw = ZS.dir - ZS.esq - 40;
        caixa(bx, by, bw, 92); c.font = F(30); c.fillStyle = PAL.vermelho; c.textAlign = 'left'; c.textBaseline = 'middle'; c.fillText(nome, bx + 34, by + 46);
        c.fillStyle = PAL.preto; c.fillRect(bx + bw * .5, by + 30, bw * .45, 32); c.fillStyle = vida < .6 ? PAL.laranja : PAL.vermelho; c.fillRect(bx + bw * .5 + 4, by + 34, (bw * .45 - 8) * vida, 24);
        if (!cn.texto) { caixa(DLG.x, DLG.y, DLG.w, DLG.h); c.font = F(46); c.textAlign = 'left'; c.textBaseline = 'middle'; ['FIGHT', 'ITEM', 'RUN', 'CRY'].forEach((o, i) => { c.fillStyle = PAL.branco; c.fillText(o, DLG.x + 130 + (i % 2) * 380, DLG.y + 140 + Math.floor(i / 2) * 120); });
          const sel = Math.min(3, Math.floor(k * 4)); c.fillStyle = PAL.amarelo; const ax = DLG.x + 70 + (sel % 2) * 380, ay = DLG.y + 140 + Math.floor(sel / 2) * 120; c.beginPath(); c.moveTo(ax, ay - 20); c.lineTo(ax + 32, ay); c.lineTo(ax, ay + 20); c.closePath(); c.fill(); }
        if (k > 0.45 && k < 0.85 && Number.isFinite(cn.dano) && cn.dano > 0) { c.font = F(84); c.textAlign = 'center'; c.textBaseline = 'middle'; const yy = 560 - (k - 0.45) * 300; c.lineWidth = 14; c.strokeStyle = '#1a1423'; c.strokeText('-' + cn.dano, W * 0.62, yy); c.fillStyle = PAL.amarelo; c.fillText('-' + cn.dano, W * 0.62, yy); }
      }
      if (cn.texto) dialogo2(cn, local);
      U.cartaz(c, spec, t, { fonte: F(46), y: ZS.topo + 160, fundo: PAL.vermelho, borda: PAL.branco, cor: PAL.branco, altura_linha: 68, raio: 0, dur: 2.6, caixa: true });
      if (spec.crt === true) { c.fillStyle = 'rgba(0,0,0,.045)'; for (let y = 0; y < H; y += 6) c.fillRect(0, y, W, 1); }
    }
    function dialogo2(cn, local) {
      let texto = cn.texto; const quem = cn.quem;
      if (quem && texto.toUpperCase().startsWith(String(quem).toUpperCase() + ':')) texto = texto.slice(String(quem).length + 1).trim();
      // narrador/sistema não tem rosto: rótulo amarelo no alto, como no v1
      const sistema = !quem || /^(sistema|system|narrador|narrator|game|juego|jogo|tutorial)$/i.test(String(quem).trim());
      const comRetrato = !!quem && !sistema;
      const tx0 = comRetrato ? DLG.x + 210 : DLG.x + 50, larg0 = DLG.x + DLG.w - 60 - tx0;
      c.font = F(comRetrato ? 38 : 42);
      const completas = U.linhas(c, texto, larg0), porPagina = comRetrato ? 4 : (quem ? 3 : 4);
      const paginas = []; for (let i = 0; i < completas.length; i += porPagina) paginas.push(completas.slice(i, i + porPagina));
      const falado = revelado(cn, local, texto);
      let pagina = 0, n;
      if (falado != null) { let acum = 0; while (pagina < paginas.length - 1 && falado > acum + paginas[pagina].join(' ').length) acum += paginas[pagina++].join(' ').length + 1; n = falado - acum; }
      else { const cps = 32, tempos = paginas.map((ls) => ls.join(' ').length / cps + 0.8); let inicio = 0; while (pagina < tempos.length - 1 && local >= inicio + tempos[pagina]) inicio += tempos[pagina++]; n = Math.floor(Math.max(0, local - inicio) * cps); }
      const vis = paginas[pagina] || [], textoPagina = vis.join(' ');
      // caixa com retrato do falante (rosto 2x do mesmo sprite)
      caixa(DLG.x, DLG.y, DLG.w, DLG.h);
      let tx = DLG.x + 50;
      let topo = 48;
      if (comRetrato) {
        const ator0 = (cn.atores && cn.atores[0]) || 'heroi', retrato = boneco(/chefe|boss|jefe/i.test(quem) ? 'chefe' : /m[aã]e|mom|mam/i.test(quem) ? 'mae' : ator0, 0, 1, 'neutro');
        if (c.drawImage) { c.imageSmoothingEnabled = false; c.fillStyle = '#33406b'; c.fillRect(DLG.x + 36, DLG.y + 36, 150, 150); c.drawImage(retrato, 0, 0, 16, 16, DLG.x + 39, DLG.y + 39, 144, 144); }
        c.font = F(22); c.fillStyle = PAL.amarelo; c.textAlign = 'center'; c.textBaseline = 'top'; c.fillText(String(quem).toUpperCase().slice(0, 9), DLG.x + 111, DLG.y + 206);
      } else if (quem) {
        c.font = F(34); c.fillStyle = PAL.amarelo; c.textAlign = 'left'; c.textBaseline = 'top'; c.fillText(String(quem).toUpperCase(), DLG.x + 50, DLG.y + 40); topo = 100;
      }
      c.font = F(comRetrato ? 38 : 42); c.textAlign = 'left'; c.textBaseline = 'top'; c.fillStyle = PAL.branco;
      if (comRetrato) tx = DLG.x + 210;
      const linhas = vis;
      let escrito = 0; linhas.forEach((l, i) => { const trecho = l.slice(0, Math.max(0, n - escrito)); escrito += l.length + 1; c.fillText(trecho, tx, DLG.y + topo + i * 62); });
      const sx = DLG.x + DLG.w - 70, sy = DLG.y + DLG.h - 60;
      if (n >= textoPagina.length && Math.floor(local * 3) % 2) { c.fillStyle = PAL.branco; c.beginPath(); c.moveTo(sx - 20, sy); c.lineTo(sx + 20, sy); c.lineTo(sx, sy + 26); c.closePath(); c.fill(); }
    }

    if (!legado) return { quadro: quadro2 };
    return { quadro };
  }
  MOTORES.pixel = { criar };
})();


