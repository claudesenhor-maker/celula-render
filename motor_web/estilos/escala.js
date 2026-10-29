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
    const nevoa=new T.Fog('#DDEFFF',10,100);sc.fog=nevoa;
    const num = (v, a, b, p) => { const x = Number(v); return Number.isFinite(x) ? U.clamp(x, a, b) : p; };
    const vet = (v, a, b, p) => [0, 1, 2].map((i) => num(Array.isArray(v) ? v[i] : undefined, a, b, p[i]));
    const corOk = (x, p) => (/^#[0-9a-fA-F]{3,6}$/.test(String(x || '')) ? x : p);
    // 23/10 (pedido do dono: 3D "mais detalhista e com fundo"): luz realista,
    // formas lisas e materiais de comum3d.js; ceu com nuvens; modelos prontos
    // com o detalhe que faz cada coisa ser reconhecida de longe.
    const T3 = !!window.U3;
    if (T3) U3.estudio(R, sc, T, { exposicao: 1.1 });
    const FB = { caixa: () => new T.BoxGeometry(1, 1, 1), esfera: () => new T.IcosahedronGeometry(0.5, 2), cone: () => new T.ConeGeometry(0.5, 1, 9),
      cilindro: () => new T.CylinderGeometry(0.5, 0.5, 1, 14), icosa: () => new T.IcosahedronGeometry(0.5, 0), toro: () => new T.TorusGeometry(0.4, 0.12, 8, 20),
      piramide: () => new T.ConeGeometry(0.6, 1, 4) };
    const F = Object.assign(FB, T3 ? U3.formas(T) : {});
    const M = (cor, tipo) => (T3 ? U3.material(T, cor, tipo || 'plastico') : new T.MeshStandardMaterial({ color: cor, roughness: 0.75, metalness: 0.05, flatShading: true }));
    // ceu e chao
    sc.background = T3 ? U3.ceu(T, 11) : new T.Color('#9CCBF2');
    sc.add(new T.HemisphereLight('#ffffff', '#6b7a5a', T3 ? 0.55 : 0.75));
    const sol = new T.DirectionalLight('#FFF6E8', T3 ? 1.5 : 0.8); sol.position.set(0.5, 1, 0.8); sc.add(sol); sc.add(sol.target);
    if (T3) { sol.castShadow = true; sol.shadow.mapSize.set(1024, 1024); sol.shadow.bias = -0.0008; }
    // janelas acesas do predio (textura)
    function janelas(cor) {
      const cv = document.createElement('canvas'); cv.width = 64; cv.height = 256; const g = cv.getContext('2d'); const r = U.rng(9);
      g.fillStyle = cor; g.fillRect(0, 0, 64, 256);
      for (let y = 6; y < 250; y += 14) for (let x = 5; x < 60; x += 12) { g.fillStyle = r() > 0.35 ? '#FFE9A8' : '#3C5068'; g.fillRect(x, y, 8, 9); }
      const t = new T.CanvasTexture(cv); if (T3) t.encoding = T.sRGBEncoding; return t;
    }
    // MODELOS PRONTOS, na unidade "altura (ou comprimento) = 1"
    function pecaPronta(nome, cor) {
      const g = new T.Group();
      const add = (forma, c2, p, sz, giro, mat) => { const m = new T.Mesh((F[forma] || F.caixa)(), M(c2, mat)); m.position.set(...p); m.scale.set(...sz);
        if (giro) m.rotation.set(...giro.map((a) => (a * Math.PI) / 180)); g.add(m); return m; };
      switch (nome) {
        case 'pessoa': {
          // unidade: altura = 1 (capsula base: 0,6 de largura x 1 de altura)
          const pele = '#E8B996', roupa = cor || '#E46A86';
          add('cilindro', '#2F3C55', [-0.045, 0.24, 0], [0.075, 0.44, 0.075], null, 'tecido'); add('cilindro', '#2F3C55', [0.045, 0.24, 0], [0.075, 0.44, 0.075], null, 'tecido');
          add('caixa', '#1E1E22', [-0.045, 0.016, 0.02], [0.08, 0.032, 0.12], null, 'borracha'); add('caixa', '#1E1E22', [0.045, 0.016, 0.02], [0.08, 0.032, 0.12], null, 'borracha');
          add('capsula', roupa, [0, 0.64, 0], [0.42, 0.38, 0.32], null, 'tecido');
          add('capsula', roupa, [-0.135, 0.63, 0], [0.11, 0.36, 0.11], [0, 0, 6], 'tecido'); add('capsula', roupa, [0.135, 0.63, 0], [0.11, 0.36, 0.11], [0, 0, -6], 'tecido');
          add('esfera', pele, [-0.152, 0.445, 0], [0.055, 0.06, 0.055]); add('esfera', pele, [0.152, 0.445, 0], [0.055, 0.06, 0.055]);
          add('cilindro', pele, [0, 0.835, 0], [0.055, 0.04, 0.055]); add('esfera', pele, [0, 0.91, 0], [0.14, 0.16, 0.15]);
          for(const lado of [-1,1])add('esfera','#302523',[lado*.025,.92,.071],[.014,.016,.012]);
          add('meia_esfera', '#3A2618', [0, 0.925, -0.006], [0.148, 0.15, 0.158], null, 'tecido'); break; }
        case 'arvore':
          add('cilindro', '#6E4A2C', [0, 0.22, 0], [0.07, 0.44, 0.07], null, 'madeira');
          add('esfera', cor || '#4E9A5C', [0, 0.55, 0], [0.5, 0.4, 0.5]); add('esfera', cor || '#5DAA66', [-0.1, 0.72, 0.05], [0.4, 0.34, 0.4]);
          add('esfera', cor || '#6BBA70', [0.08, 0.86, -0.03], [0.3, 0.26, 0.3]); break;
        case 'predio': {
          const m = new T.Mesh(F.caixa_viva ? F.caixa_viva() : F.caixa(), T3 ? U3.material(T, '#ffffff', 'ceramica') : M('#A8B8C8'));
          const tx = janelas(cor || '#8FA3B8'); m.material.map = tx; m.material.needsUpdate = true; m.position.set(0, 0.5, 0); m.scale.set(0.3, 1, 0.3); g.add(m);
          add('caixa', '#6F7C8A', [0, 1.01, 0], [0.32, 0.02, 0.32], null, 'metal'); add('caixa', '#9AA7B4', [0.05, 1.04, 0.04], [0.08, 0.05, 0.08], null, 'metal');
          add('cilindro', '#C8CED4', [-0.06, 1.08, -0.05], [0.006, 0.14, 0.006], null, 'aco'); break; }
        case 'torre':
          // pernas que se juntam no alto (topo de cada uma inclina para o centro)
          [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([sx, sz]) => add('cilindro', cor || '#8A6A55', [sx * 0.105, 0.3, sz * 0.105], [0.028, 0.62, 0.028], [-sz * 9, 0, sx * 9], 'aco'));
          add('caixa', cor || '#8A6A55', [0, 0.32, 0], [0.2, 0.02, 0.2], null, 'aco'); add('caixa', cor || '#8A6A55', [0, 0.6, 0], [0.12, 0.02, 0.12], null, 'aco');
          add('piramide', cor || '#8A6A55', [0, 0.78, 0], [0.12, 0.36, 0.12], null, 'aco'); add('cilindro', '#C8CED4', [0, 0.98, 0], [0.008, 0.06, 0.008], null, 'aco'); break;
        case 'montanha':
          add('cone', cor || '#7C7466', [0, 0.5, 0], [2.4, 1, 2.4], null, 'pedra'); add('cone', '#8A8274', [0.9, 0.3, 0.3], [1.3, 0.6, 1.3], null, 'pedra');
          add('cone', '#F4F7FA', [0, 0.87, 0], [0.62, 0.27, 0.62], null, 'ceramica'); add('cone', '#6E8F5E', [-0.6, 0.12, 0.5], [1.6, 0.24, 1.6], null, 'pedra'); break;
        case 'casa':
          add('caixa', cor || '#E9D8B4', [0, 0.32, 0], [0.9, 0.64, 0.7], null, 'ceramica'); add('piramide', '#A2412F', [0, 0.82, 0], [0.88, 0.38, 0.72], [0, 45, 0], 'ceramica');
          add('caixa', '#6B4226', [0, 0.17, 0.355], [0.16, 0.34, 0.02], null, 'madeira');
          add('caixa', '#8FC2E6', [-0.28, 0.4, 0.355], [0.16, 0.14, 0.02], null, 'vidro'); add('caixa', '#8FC2E6', [0.28, 0.4, 0.355], [0.16, 0.14, 0.02], null, 'vidro'); break;
        case 'carro':
          add('caixa', cor || '#D23A3A', [0, 0.16, 0], [1, 0.18, 0.42], null, 'metal'); add('caixa', cor || '#D23A3A', [-0.05, 0.3, 0], [0.55, 0.16, 0.38], null, 'metal');
          add('caixa', '#24313E', [-0.05, 0.31, 0], [0.5, 0.12, 0.39], null, 'vidro');
          [[-0.32, 0.21], [0.32, 0.21], [-0.32, -0.21], [0.32, -0.21]].forEach(([x, z]) => { add('cilindro', '#1B1B1E', [x, 0.08, z], [0.16, 0.06, 0.16], [90, 0, 0], 'borracha'); add('cilindro', '#B9C0C7', [x, 0.08, z * 1.08], [0.08, 0.02, 0.08], [90, 0, 0], 'cromado'); }); break;
        case 'onibus':
          add('caixa', cor || '#F2B705', [0, 0.17, 0], [1, 0.26, 0.24], null, 'metal'); add('caixa', '#2C3A48', [0.02, 0.21, 0], [0.9, 0.08, 0.245], null, 'vidro');
          [-0.35, 0.33].forEach((x) => [0.12, -0.12].forEach((z) => add('cilindro', '#1B1B1E', [x, 0.045, z], [0.09, 0.04, 0.09], [90, 0, 0], 'borracha'))); break;
        case 'aviao':
          add('capsula', cor || '#F2F4F7', [0, 0.12, 0], [0.14, 1.6, 0.14], [0, 0, 90], 'metal'); add('lamina', cor || '#E1E5EA', [0.02, 0.1, 0], [0.18, 1, 1], null, 'metal');
          add('lamina', cor || '#E1E5EA', [0.44, 0.12, 0], [0.08, 0.5, 0.36], null, 'metal'); add('lamina', '#2F6FC4', [0.45, 0.2, 0], [0.14, 1, 0.18], [90, 0, 0], 'metal');
          add('cilindro', '#9AA3AD', [-0.05, 0.05, 0.2], [0.06, 0.12, 0.06], [0, 0, 90], 'metal'); add('cilindro', '#9AA3AD', [-0.05, 0.05, -0.2], [0.06, 0.12, 0.06], [0, 0, 90], 'metal'); break;
        case 'navio':
          add('caixa', cor || '#24313E', [0, 0.06, 0], [1, 0.12, 0.16], null, 'metal'); add('caixa', '#B33A2F', [0, 0.01, 0], [1, 0.02, 0.165], null, 'metal');
          add('caixa', '#F2F4F7', [0.3, 0.17, 0], [0.18, 0.1, 0.13], null, 'metal'); add('caixa', '#D88A3A', [-0.3, 0.16, 0], [0.4, 0.08, 0.12], null, 'metal');
          add('cilindro', '#2B2B2B', [0.34, 0.25, 0], [0.04, 0.08, 0.04], null, 'metal'); break;
        case 'foguete':
          add('cilindro', cor || '#F2F4F7', [0, 0.45, 0], [0.12, 0.7, 0.12], null, 'metal'); add('cone', cor || '#F2F4F7', [0, 0.88, 0], [0.12, 0.18, 0.12], null, 'metal');
          add('cilindro', '#2B2B2B', [0, 0.32, 0], [0.122, 0.02, 0.122], null, 'metal');
          [0, 120, 240].forEach((a) => add('lamina', '#B33A2F', [Math.sin((a * Math.PI) / 180) * 0.07, 0.12, Math.cos((a * Math.PI) / 180) * 0.07], [0.12, 0.18, 0.03], [0, a, 0], 'metal'));
          add('cone', '#5A5F66', [0, 0.06, 0], [0.09, 0.08, 0.09], [180, 0, 0], 'aco'); break;
        case 'esfera': add('esfera', cor || '#5DAA5A', [0, 0.5, 0], [1, 1, 1], null, 'pedra'); break;
        case 'cubo': add('caixa', cor || '#E2574C', [0, 0.5, 0], [1, 1, 1]); break;
        case 'cone': add('cone', cor || '#F2B705', [0, 0.5, 0], [0.8, 1, 0.8]); break;
        default: add('cilindro', cor || '#B8C4D0', [0, 0.5, 0], [0.4, 1, 0.4]);
      }
      return g;
    }
    const itens = (Array.isArray(spec.itens) ? spec.itens.slice(0, 12) : []).map((it, i) => {
      const tam = num(it.tamanho_m != null ? it.tamanho_m : it.altura_m, 0.001, 2e7, 1), cor = corOk(it.cor, null);
      let g;
      if (Array.isArray(it.partes) && it.partes.length) {
        g = new T.Group();
        it.partes.slice(0, 24).forEach((p) => { const m = new T.Mesh((F[p.forma] || F.caixa)(), M(corOk(p.cor, cor || '#B8C4D0'), p.material));
          m.position.set(...vet(p.pos, -5, 5, [0, 0.5, 0])); m.scale.set(...vet(p.tam, 0.001, 5, [1, 1, 1])); m.rotation.set(...vet(p.giro, -360, 360, [0, 0, 0]).map((a) => (a * Math.PI) / 180)); g.add(m); });
      } else g = pecaPronta(String(it.modelo || 'cilindro'), cor);
      // normaliza: a MAIOR dimensao vira `tamanho_m` (a baleia mede 30 m de
      // comprimento, nao de altura; a torre, 330 m de altura)
      const b = new T.Box3().setFromObject(g), maior = Math.max(1e-6, b.max.y - b.min.y, b.max.x - b.min.x);
      g.scale.multiplyScalar(tam / maior); g.position.y = -b.min.y * (tam / maior);
      const b2 = new T.Box3().setFromObject(g), alt = Math.max(1e-6, b2.max.y - b2.min.y), larg = Math.max(alt * 0.2, b2.max.x - b2.min.x);
      g.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
      sc.add(g);
      return { nome: String(it.nome || 'item ' + (i + 1)).slice(0, 26), tam, alt, larg, g };
    });
    // lado a lado, do menor para a direita, com um respiro proporcional
    let x = 0; itens.forEach((it, i) => { if (i) x += (itens[i - 1].larg + it.larg) * 0.5 + Math.max(itens[i - 1].larg, it.larg) * 0.25; it.x = x; it.g.position.x = x; });
    const chaoTam = Math.max(10, x * 4 + (itens.length ? itens[itens.length - 1].alt * 20 : 10));
    // CHAO QUE ACOMPANHA O ZOOM (23/10): o disco tem 60x a distancia da camera
    // e a grama repete na mesma proporcao -- de perto parece grama, de longe campo
    const chao = new T.Mesh(new T.CircleGeometry(1, 64), T3 ? new T.MeshLambertMaterial({ map: U3.textura(T, 'grama', 13, 120) }) : new T.MeshStandardMaterial({ color: '#8DB36B', roughness: 1 }));
    chao.rotation.x = -Math.PI / 2; chao.position.x = x / 2; chao.scale.setScalar(chaoTam); chao.receiveShadow = true; sc.add(chao);

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
      let d = lerpLog(A.d, B.d, q), cx = U.lerp(A.cx, B.cx, q), cy = lerpLog(Math.max(1e-3, A.cy), Math.max(1e-3, B.cy), q);
      // 24/10: enquanto o cartaz do titulo esta' no alto (y 170 a ~430), o item cabe
      // na faixa livre entre ele e a legenda -- antes o cartaz cobria a cabeca da
      // pessoa e a etiqueta "PERSON 1.7 m". Depois a camera volta ao normal.
      const wT = spec.titulo ? 1 - U.suave(U.clamp((t - 3.0) / 0.8, 0, 1)) : 0;
      let miraY = cy * 0.62;
      if (wT > 0 && itens[a]) {
        const vt = Math.tan((cam.fov * Math.PI) / 360), faixa = 640 / H;
        const dT = Math.max(d, itens[a].alt / (2 * vt * faixa));
        d = lerpLog(d, dT, wT);
        // a faixa livre (y 640 a 1280) tem o centro no meio da tela: mira no meio do item
        miraY = U.lerp(miraY, itens[a].alt * 0.5, wT);
      }
      // camera quase ao rés do chao, de frente: o ceu domina e o chao fica numa
      // faixa embaixo; mirar abaixo do centro do objeto o SOBE no quadro (a
      // legenda mora em 70% da altura)
      const ang = Math.sin(t * 0.2) * 0.07;
      cam.position.set(cx + Math.sin(ang) * d, cy * 0.55, Math.cos(ang) * d); cam.near = d / 5000; cam.far = d * 400; cam.updateProjectionMatrix();
      if (T3) {
        chao.position.set(cx, 0, 0); chao.scale.setScalar(d * 60);
        nevoa.near=d*6;nevoa.far=d*45;
        sol.position.set(cx + d * 0.7, d * 1.4, d * 1.1); sol.target.position.set(cx, 0, 0);
        const sh = sol.shadow.camera; sh.left = sh.bottom = -d * 1.2; sh.right = sh.top = d * 1.2; sh.near = d * 0.05; sh.far = d * 5; sh.updateProjectionMatrix();
      }
      cam.lookAt(cx, miraY, 0);
      U3.render(R, sc, cam, spec, t); c.drawImage(gl, 0, 0, W, H);
      // etiquetas: nome e altura de cada item visivel, ancoradas no topo dele.
      // 23/10: o destaque e' posto primeiro; etiqueta secundaria que bateria
      // numa ja posta some (antes "1 BARCO" cobria "KHALIFA"); nunca sai pela
      // borda (conta a largura real) nem sobe para baixo do selo do alto.
      const comHud = !!(cn.hud && typeof cn.hud !== 'object');
      const yMin = comHud ? 540 : t < 3.4 ? 590 : 330, postas = [];
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
      // A COTA (23/10, pedido do dono: o canal "dimensiona as coisas"): uma linha
      // de medida ao lado do item em destaque, que cresce do chao ate o topo com
      // setas nas pontas -- o olho le o tamanho antes de ler o numero.
      if (itens[a]) {
        const it = itens[a], xl = it.x + it.larg * 0.62;
        const p0 = new T.Vector3(xl, 0, 0).project(cam), p1 = new T.Vector3(xl, it.alt, 0).project(cam);
        const x0 = (p0.x * 0.5 + 0.5) * W, y0 = (-p0.y * 0.5 + 0.5) * H, y1 = (-p1.y * 0.5 + 0.5) * H, x1 = (p1.x * 0.5 + 0.5) * W;
        const cresce = U.saida(U.clamp((local - 0.35) / 0.7, 0, 1)), alto = y0 - y1;
        if (cresce > 0 && alto > 40 && x0 > 20 && x0 < W - 20 && p0.z < 1) {
          const yt = y0 - alto * cresce, xt = x0 + (x1 - x0) * cresce;
          c.save(); c.strokeStyle = '#FFFFFF'; c.fillStyle = '#FFFFFF'; c.lineWidth = 6; c.shadowColor = 'rgba(0,0,0,0.55)'; c.shadowBlur = 8;
          c.setLineDash([]); c.beginPath(); c.moveTo(x0, y0); c.lineTo(xt, yt); c.stroke();
          c.beginPath(); c.moveTo(x0 - 22, y0); c.lineTo(x0 + 22, y0); c.stroke();
          // marcas a cada 10% da altura
          for (let k = 1; k < 10; k++) { const yy = y0 - alto * k / 10; if (yy < yt) break; c.lineWidth = 3; c.beginPath(); c.moveTo(x0 - (k % 5 ? 8 : 16), yy); c.lineTo(x0 + (k % 5 ? 8 : 16), yy); c.stroke(); }
          if (cresce > 0.98) { c.lineWidth = 6; c.beginPath(); c.moveTo(x1 - 22, y1); c.lineTo(x1 + 22, y1); c.stroke();
            c.beginPath(); c.moveTo(x1, y1 - 2); c.lineTo(x1 - 14, y1 + 24); c.lineTo(x1 + 14, y1 + 24); c.closePath(); c.fill(); }
          c.restore();
        }
      }
      if (cn.hud && typeof cn.hud !== 'object' && local > 0.3) { const s = U.mola(local - 0.3, 10); c.save(); c.translate(W / 2, 300); c.scale(s, s); c.font = '120px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        const txt = U.hud(c, cn.hud, c.canvas.width * 0.84 - 70, 22), w = c.measureText(txt).width + 70; U.rr(c, -w / 2, -78, w, 156, 34); c.fillStyle = '#1B1B1B'; c.fill(); c.fillStyle = '#FFD23F'; c.fillText(txt, 0, 6); c.restore(); }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 170, fundo: '#FFD23F', borda: '#1B1B1B', cor: '#1B1B1B', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '100px "Lilita One", sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#FFD23F', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro, dispose: () => U3.liberar(R, sc) };
  }
  MOTORES.escala = { criar };
})();
