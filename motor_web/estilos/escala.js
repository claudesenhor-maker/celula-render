// ESCALA -- comparacao de tamanhos em 3D (22/10, ordem do dono: um nicho e um
// motor por canal). "Qual o tamanho de...", "e se X fosse do tamanho de Y".
//
// `spec.itens`: os objetos do video em ordem, cada um com a ALTURA REAL em
// metros. Eles ficam lado a lado no mesmo chao, na mesma escala, e cada cena
// enquadra ate' o item `alvo` -- a camera recua (ou avanca) o quanto precisa, de
// 1 cm a milhares de km. O objeto vem de uma peca pronta (`modelo`) ou e'
// DESCRITO pela IA em formas (`partes`, o mesmo formato do motor mecanismo);
// nada e' executado como codigo.
//   item: { nome, tamanho_m (a MAIOR dimensao; altura_m tambem vale), cor, modelo?: "pessoa|arvore|predio|torre|montanha|esfera|cubo|cilindro|cone",
//           partes?: [{forma, cor, pos, tam, giro}] (unidade: a altura do item = 1) }
//   cena: { texto, alvo: indice|nome, hud? }
//
// CONTRATO (comum.js): `quadro(t)` sem estado entre quadros.
(function () {
  'use strict';
  function criar(tela, spec, U) {
    const T = window.THREE, c = tela.getContext('2d'), W = spec.w, H = spec.h;
    const gl = document.createElement('canvas'); gl.width = W; gl.height = H;
    const R = new T.WebGLRenderer({ canvas: gl, antialias: true, preserveDrawingBuffer: true, logarithmicDepthBuffer: true }); R.setSize(W, H, false);
    const cam = new T.PerspectiveCamera(36, W / H, 0.001, 1e8);
    const sc = new T.Scene();
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const vet = (v, a, b, p) => [0, 1, 2].map((i) => num(Array.isArray(v) ? v[i] : undefined, a, b, p[i]));
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    const M = (cor) => new T.MeshStandardMaterial({ color: cor, roughness: 0.75, metalness: 0.05, flatShading: true });
    const F = {
      caixa: () => new T.BoxGeometry(1, 1, 1), esfera: () => new T.IcosahedronGeometry(0.5, 2), cone: () => new T.ConeGeometry(0.5, 1, 9),
      cilindro: () => new T.CylinderGeometry(0.5, 0.5, 1, 14), icosa: () => new T.IcosahedronGeometry(0.5, 0), toro: () => new T.TorusGeometry(0.4, 0.12, 8, 20),
      piramide: () => new T.ConeGeometry(0.6, 1, 4),
    };
    // ceu e chao
    { const cv = document.createElement('canvas'); cv.width = 4; cv.height = 256; const g = cv.getContext('2d'); const gr = g.createLinearGradient(0, 0, 0, 256);
      gr.addColorStop(0, '#3E7FD1'); gr.addColorStop(0.75, '#BFE3FF'); gr.addColorStop(1, '#E8F6FF'); g.fillStyle = gr; g.fillRect(0, 0, 4, 256); sc.background = new T.CanvasTexture(cv); }
    sc.add(new T.HemisphereLight('#ffffff', '#6b7a5a', 0.75));
    const sol = new T.DirectionalLight('#ffffff', 0.8); sol.position.set(0.5, 1, 0.8); sc.add(sol);

    function pecaPronta(nome, cor) {
      const g = new T.Group(), add = (geo, c2, p, s) => { const m = new T.Mesh(geo, M(c2)); m.position.set(...p); m.scale.set(...s); g.add(m); };
      switch (nome) {
        case 'pessoa': add(F.cilindro(), cor || '#E46A86', [0, 0.47, 0], [0.26, 0.5, 0.2]); add(F.esfera(), '#F2C9A5', [0, 0.84, 0], [0.18, 0.18, 0.18]);
          add(F.caixa(), '#3B4A63', [-0.06, 0.12, 0], [0.09, 0.25, 0.1]); add(F.caixa(), '#3B4A63', [0.06, 0.12, 0], [0.09, 0.25, 0.1]); break;
        case 'arvore': add(F.cilindro(), '#7A5232', [0, 0.2, 0], [0.08, 0.4, 0.08]); add(F.cone(), cor || '#4E9A5C', [0, 0.65, 0], [0.45, 0.7, 0.45]); break;
        case 'predio': add(F.caixa(), cor || '#A8B8C8', [0, 0.5, 0], [0.35, 1, 0.35]); for (let i = 0; i < 6; i++) add(F.caixa(), '#FFE9A8', [0, 0.12 + i * 0.15, 0.176], [0.25, 0.04, 0.005]); break;
        case 'torre': add(F.piramide(), cor || '#8A6A55', [0, 0.5, 0], [0.35, 1, 0.35]); break;
        case 'montanha': add(F.cone(), cor || '#7C8A6E', [0, 0.5, 0], [2.4, 1, 2.4]); add(F.cone(), '#F4F7FA', [0, 0.88, 0], [0.55, 0.24, 0.55]); break;
        case 'esfera': add(F.esfera(), cor || '#5DAA5A', [0, 0.5, 0], [1, 1, 1]); break;
        case 'cubo': add(F.caixa(), cor || '#E2574C', [0, 0.5, 0], [1, 1, 1]); break;
        case 'cone': add(F.cone(), cor || '#F2B705', [0, 0.5, 0], [0.8, 1, 0.8]); break;
        default: add(F.cilindro(), cor || '#B8C4D0', [0, 0.5, 0], [0.4, 1, 0.4]);
      }
      return g;
    }
    const itens = (Array.isArray(spec.itens) ? spec.itens.slice(0, 12) : []).map((it, i) => {
      const tam = num(it.tamanho_m != null ? it.tamanho_m : it.altura_m, 0.001, 2e7, 1), cor = corOk(it.cor, null);
      let g;
      if (Array.isArray(it.partes) && it.partes.length) {
        g = new T.Group();
        it.partes.slice(0, 20).forEach((p) => { const m = new T.Mesh((F[p.forma] || F.caixa)(), M(corOk(p.cor, cor || '#B8C4D0')));
          m.position.set(...vet(p.pos, -5, 5, [0, 0.5, 0])); m.scale.set(...vet(p.tam, 0.001, 5, [1, 1, 1])); m.rotation.set(...vet(p.giro, -360, 360, [0, 0, 0]).map((a) => (a * Math.PI) / 180)); g.add(m); });
      } else g = pecaPronta(String(it.modelo || 'cilindro'), cor);
      // normaliza: a MAIOR dimensao vira `tamanho_m` (a baleia mede 30 m de
      // comprimento, nao de altura; a torre, 330 m de altura)
      const b = new T.Box3().setFromObject(g), maior = Math.max(1e-6, b.max.y - b.min.y, b.max.x - b.min.x);
      g.scale.multiplyScalar(tam / maior); g.position.y = -b.min.y * (tam / maior);
      const b2 = new T.Box3().setFromObject(g), alt = Math.max(1e-6, b2.max.y - b2.min.y), larg = Math.max(alt * 0.2, b2.max.x - b2.min.x);
      sc.add(g);
      return { nome: String(it.nome || 'item ' + (i + 1)).slice(0, 26), tam, alt, larg, g };
    });
    // lado a lado, do menor para a direita, com um respiro proporcional
    let x = 0; itens.forEach((it, i) => { if (i) x += (itens[i - 1].larg + it.larg) * 0.5 + Math.max(itens[i - 1].larg, it.larg) * 0.25; it.x = x; it.g.position.x = x; });
    const chaoTam = Math.max(10, x * 4 + (itens.length ? itens[itens.length - 1].alt * 20 : 10));
    const chao = new T.Mesh(new T.CircleGeometry(chaoTam, 64), new T.MeshStandardMaterial({ color: '#8DB36B', roughness: 1 })); chao.rotation.x = -Math.PI / 2; chao.position.x = x / 2; sc.add(chao);

    const idxAlvo = (cn, i) => {
      if (typeof cn.alvo === 'number') return U.clamp(Math.round(cn.alvo), 0, Math.max(0, itens.length - 1));
      const k = itens.findIndex((it) => it.nome.toLowerCase() === String(cn.alvo || '').toLowerCase());
      return k >= 0 ? k : Math.min(i, itens.length - 1);
    };
    // o enquadramento que mostra os itens 0..a inteiros: centro e distancia
    function quadroDe(a) {
      if (!itens.length) return { cx: 0, cy: 1, d: 6 };
      const it = itens[a], x0 = Math.max(itens[0].x - itens[0].larg, it.x - Math.max(it.alt * 1.2, it.larg * 0.65)), x1 = it.x + it.larg * 0.65;
      const hfov = 2 * Math.atan(Math.tan((cam.fov * Math.PI) / 360) * cam.aspect), vfov = (cam.fov * Math.PI) / 180;
      const h = it.alt * 1.6, w = x1 - x0, d = Math.max((w / 2) / Math.tan(hfov / 2) * 1.1, (h / 2) / Math.tan(vfov / 2) * 1.15);
      return { cx: (x0 + x1) / 2, cy: it.alt * 0.5, d };
    }
    // interpola em LOG (a distancia muda por ordens de grandeza)
    const lerpLog = (a, b, k) => Math.exp(U.lerp(Math.log(a), Math.log(b), k));

    function quadro(t) {
      const { c: cn, i, k, local } = U.cenaEm(spec, t), a = idxAlvo(cn, i), ant = i > 0 ? idxAlvo(spec.cenas[i - 1], i - 1) : a;
      const A = quadroDe(ant), B = quadroDe(a), q = U.suave(U.clamp(k * 2.4, 0, 1));
      const d = lerpLog(A.d, B.d, q), cx = U.lerp(A.cx, B.cx, q), cy = lerpLog(Math.max(1e-3, A.cy), Math.max(1e-3, B.cy), q);
      // camera quase ao rés do chao, de frente: o ceu domina e o chao fica numa
      // faixa embaixo; mirar abaixo do centro do objeto o SOBE no quadro (a
      // legenda mora em 70% da altura)
      const ang = Math.sin(t * 0.2) * 0.07;
      cam.position.set(cx + Math.sin(ang) * d, cy * 0.55, Math.cos(ang) * d); cam.near = d / 5000; cam.far = d * 400; cam.updateProjectionMatrix();
      cam.lookAt(cx, cy * 0.62, 0);
      R.render(sc, cam); c.drawImage(gl, 0, 0, W, H);
      // etiquetas: nome e altura de cada item visivel, ancoradas no topo dele.
      // 23/10: o destaque e' posto primeiro; etiqueta secundaria que bateria
      // numa ja posta some (antes "1 BARCO" cobria "KHALIFA"); nunca sai pela
      // borda (conta a largura real) nem sobe para baixo do selo do alto.
      const comHud = !!(cn.hud && typeof cn.hud !== 'object');
      const yMin = comHud ? 540 : 330, postas = [];
      const ordem = itens.map((it, j) => j).filter((j) => j <= a).sort((x, y) => (y === a) - (x === a));
      ordem.forEach((j) => {
        const it = itens[j];
        const p = new T.Vector3(it.x, it.alt, 0).project(cam); if (p.z > 1) return;
        const px = (p.x * 0.5 + 0.5) * W, py = (-p.y * 0.5 + 0.5) * H; if (px < -50 || px > W + 50 || py < 0) return;
        const tamPx = Math.abs(py - (-new T.Vector3(it.x, 0, 0).project(cam).y * 0.5 + 0.5) * H); if (tamPx < 26 && j !== a) return;
        const v = it.tam, real = v >= 1000 ? (v / 1000).toLocaleString('en-US', { maximumFractionDigits: 1 }) + ' km' : v >= 1 ? v.toLocaleString('en-US', { maximumFractionDigits: 1 }) + ' m' : (v * 100).toLocaleString('en-US', { maximumFractionDigits: 1 }) + ' cm';
        const destaque = j === a, ent = destaque ? U.mola(local - 0.15, 10) : 1;
        c.save();
        c.font = (destaque ? '64px' : '42px') + ' "Lilita One", sans-serif';
        const l1 = it.nome.toUpperCase(), w1 = Math.min(W - 40, Math.max(c.measureText(l1).width, c.measureText(real).width) + 40), hh = destaque ? 150 : 104;
        const bx = U.clamp(px, w1 / 2 + 20, W - w1 / 2 - 20), by = Math.max(yMin, py - 40);
        const caixa = [bx - w1 / 2, by - hh, bx + w1 / 2, by];
        if (!destaque && postas.some((r) => caixa[0] < r[2] + 12 && caixa[2] > r[0] - 12 && caixa[1] < r[3] + 12 && caixa[3] > r[1] - 12)) { c.restore(); return; }
        postas.push(caixa);
        c.translate(bx, by); c.scale(ent, ent);
        c.textAlign = 'center'; c.textBaseline = 'bottom';
        U.rr(c, -w1 / 2, -hh, w1, hh, 22); c.fillStyle = destaque ? '#FFD23F' : 'rgba(255,255,255,0.85)'; c.fill();
        c.fillStyle = '#1B1B1B'; c.fillText(l1, 0, -hh / 2 + 4, w1 - 30); c.font = (destaque ? '54px' : '36px') + ' "Lilita One", sans-serif'; c.fillText(real, 0, -12, w1 - 30);
        c.restore();
      });
      if (cn.hud && typeof cn.hud !== 'object' && local > 0.3) { const s = U.mola(local - 0.3, 10); c.save(); c.translate(W / 2, 300); c.scale(s, s); c.font = '120px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        const txt = U.hud(c, cn.hud, c.canvas.width * 0.84 - 70, 22), w = c.measureText(txt).width + 70; U.rr(c, -w / 2, -78, w, 156, 34); c.fillStyle = '#1B1B1B'; c.fill(); c.fillStyle = '#FFD23F'; c.fillText(txt, 0, 6); c.restore(); }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 170, fundo: '#FFD23F', borda: '#1B1B1B', cor: '#1B1B1B', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '100px "Lilita One", sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#FFD23F', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro };
  }
  MOTORES.escala = { criar };
})();
