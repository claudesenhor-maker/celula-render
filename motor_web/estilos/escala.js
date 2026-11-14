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
          // v4 (14/11, dono: "personagens 3D desfigurados e de baixa qualidade"): era cilindro + caixa de sapato + bola de
          // cabeca com 2 pontinhos. Agora proporcao de boneco simpatico (cabeca ~1/5), maos, sapato arredondado, olho com
          // branco e pupila, sorriso, cabelo com franja, manga e cinto. Unidade: altura = 1.
          const pele = '#E8B996', roupa = '#3E7CB1', calca = '#2F3C55', cab = '#3A2618';
          for (const l of [-1, 1]) {
            add('capsula', calca, [l * 0.05, 0.25, 0], [0.085, 0.42, 0.09], null, 'tecido');
            add('esfera', '#1E1E22', [l * 0.05, 0.03, 0.025], [0.085, 0.06, 0.15], null, 'borracha');
            add('capsula', roupa, [l * 0.15, 0.6, 0], [0.075, 0.2, 0.075], [0, 0, l * 8], 'tecido');
            add('capsula', pele, [l * 0.168, 0.47, 0.005], [0.058, 0.18, 0.058], [0, 0, l * 5]);
            add('esfera', pele, [l * 0.175, 0.385, 0.01], [0.06, 0.068, 0.05]);
          }
          add('capsula', roupa, [0, 0.6, 0], [0.27, 0.34, 0.19], null, 'tecido');
          add('cilindro', '#22283A', [0, 0.45, 0], [0.25, 0.03, 0.18], null, 'borracha');
          add('cilindro', pele, [0, 0.765, 0], [0.06, 0.05, 0.06]);
          add('esfera', pele, [0, 0.88, 0], [0.2, 0.21, 0.19]);
          for (const l of [-1, 1]) {
            add('esfera', pele, [l * 0.098, 0.875, 0], [0.03, 0.045, 0.03]);
            add('esfera', '#FFFFFF', [l * 0.04, 0.9, 0.085], [0.032, 0.038, 0.016], null, 'ceramica');
            add('esfera', '#1A1410', [l * 0.04, 0.898, 0.093], [0.018, 0.022, 0.01]);
            add('capsula', cab, [l * 0.042, 0.94, 0.086], [0.012, 0.03, 0.01], [0, 0, 90 + l * 10]);
          }
          add('esfera', '#D9A07E', [0, 0.873, 0.097], [0.022, 0.02, 0.018]);
          add('capsula', '#8A2E2E', [0, 0.848, 0.09], [0.011, 0.045, 0.01], [0, 0, 90]);
          add('meia_esfera', cab, [0, 0.905, -0.012], [0.205, 0.16, 0.2], [-22, 0, 0], 'tecido');
          add('capsula', cab, [0.015, 0.968, 0.07], [0.03, 0.13, 0.03], [0, 0, 80], 'tecido');
          break; }
        case 'roda_gigante': {
          // v4 (14/11): a IA descrevia a London Eye como um anel DEITADO num tripe. Modelo pronto: aro em pe, raios,
          // 16 cabines, cubo, cavalete em A e base. Unidade: altura = 1.
          const aco = '#E9EEF3', R0 = 0.44, cy = 0.53;
          const aro = new T.Mesh(new T.TorusGeometry(R0, 0.012, 8, 72), M(aco, 'metal')); aro.position.y = cy; g.add(aro);
          const aro2 = new T.Mesh(new T.TorusGeometry(R0 * 0.97, 0.006, 6, 72), M(aco, 'metal')); aro2.position.set(0, cy, 0.03); g.add(aro2);
          for (let k = 0; k < 16; k++) { const an = (k / 16) * Math.PI * 2;
            const r = new T.Mesh(new T.CylinderGeometry(0.0035, 0.0035, R0, 4), M(aco, 'metal')); r.position.set(Math.cos(an) * R0 / 2, cy + Math.sin(an) * R0 / 2, 0.015); r.rotation.z = an - Math.PI / 2; g.add(r);
            const cab = new T.Mesh(new T.SphereGeometry(0.028, 12, 8), M(k % 4 ? '#BFE3F2' : (cor || '#E8473C'), 'vidro')); cab.scale.set(1, 0.75, 1.3); cab.position.set(Math.cos(an) * (R0 + 0.02), cy + Math.sin(an) * (R0 + 0.02), 0.02); g.add(cab); }
          const cubo = new T.Mesh(new T.CylinderGeometry(0.035, 0.035, 0.08, 16), M('#9AA5B1', 'metal')); cubo.rotation.x = Math.PI / 2; cubo.position.set(0, cy, 0.02); g.add(cubo);
          for (const l of [-1, 1]) for (const zz of [-0.09, 0.12]) { const p = new T.Mesh(new T.CylinderGeometry(0.008, 0.012, cy * 1.08, 8), M('#C9D2DB', 'metal')); p.position.set(l * 0.13, cy / 2, zz); p.rotation.z = l * 0.24; g.add(p); }
          const base = new T.Mesh(new T.BoxGeometry(0.42, 0.02, 0.32), M('#8E8E8E', 'concreto')); base.position.y = 0.01; g.add(base);
          break; }
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
        case 'onibus': {   // v3 (13/11): era uma caixa amarela com 2 rodas; agora janelas, porta, para-brisa, faixa, 6 rodas
          const cb = cor || '#F2B705';
          add('caixa', cb, [0, 0.19, 0], [1, 0.27, 0.22], null, 'metal'); add('caixa', '#FFFFFF', [0, 0.335, 0], [0.98, 0.02, 0.21], null, 'metal');
          for (let k = 0; k < 7; k++) add('caixa', '#2C3A48', [-0.36 + k * 0.105, 0.24, 0.111], [0.085, 0.085, 0.004], null, 'vidro');
          add('caixa', '#2C3A48', [0.497, 0.22, 0], [0.006, 0.13, 0.19], null, 'vidro');
          add('caixa', '#2C3A48', [0.42, 0.17, 0.111], [0.06, 0.17, 0.004], null, 'vidro');
          add('caixa', '#1B1B1E', [0, 0.11, 0.111], [1, 0.012, 0.003], null, 'metal');
          add('caixa', '#FFE9A8', [0.5, 0.1, 0.07], [0.006, 0.025, 0.04], null, 'vidro'); add('caixa', '#FFE9A8', [0.5, 0.1, -0.07], [0.006, 0.025, 0.04], null, 'vidro');
          [-0.38, -0.26, 0.34].forEach((x) => [0.112, -0.112].forEach((z) => { add('cilindro', '#1B1B1E', [x, 0.05, z], [0.1, 0.035, 0.1], [90, 0, 0], 'borracha'); add('cilindro', '#B9C0C7', [x, 0.05, z * 1.06], [0.05, 0.01, 0.05], [90, 0, 0], 'cromado'); }));
          break; }
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
        case 'disco': {   // v3: espelho de telescopio, prato, moeda, roda -- disco EM PE de frente para a camera
          add('cilindro', '#DCE6F0', [0, 0.5, 0], [1, 0.05, 1], [90, 0, 0], 'cromado');
          add('toro', '#AAB4BF', [0, 0.5, 0.0], [1.22, 1.22, 0.25], null, 'aco');
          add('cilindro', '#59616B', [0, 0.5, 0.03], [0.1, 0.06, 0.1], [90, 0, 0], 'metal');
          add('caixa', '#3A4250', [0, 0.02, 0], [0.5, 0.04, 0.2], null, 'metal'); break; }
        case 'esfera': add('esfera', cor || '#5DAA5A', [0, 0.5, 0], [1, 1, 1], null, 'pedra'); break;
        case 'cubo': add('caixa', cor || '#E2574C', [0, 0.5, 0], [1, 1, 1]); break;
        case 'cone': add('cone', cor || '#F2B705', [0, 0.5, 0], [0.8, 1, 0.8]); break;
        default: add('cilindro', cor || '#B8C4D0', [0, 0.5, 0], [0.4, 1, 0.4]);
      }
      return g;
    }
    // v3 (13/11): o roteiro descreve o onibus em 2 caixas e o motor tem um modelo pronto bem melhor -- o NOME decide.
    const PELO_NOME = [[/autob[uú]s|\bbus(es)?\b|[oô]nibus/i, 'onibus'], [/\bpersona|\bperson\b|pessoa|humano|human\b/i, 'pessoa'],
      [/\bcoche|\bcarro|\bcar\b|\bauto\b/i, 'carro'], [/avi[oó]n|avi[aã]o|airplane|\bplane\b|jet\b/i, 'aviao'], [/\bbarco|navio|\bship\b|buque|crucero/i, 'navio'],
      [/cohete|foguete|rocket/i, 'foguete'], [/espejo|espelho|mirror|\bdisco\b|\bdisc\b|\bplato\b|\bprato\b|moneda|moeda|\bcoin\b/i, 'disco'], [/edificio|pr[eé]dio|building|rascacielos|skyscraper/i, 'predio'], [/noria|ferris|roda[- ]gigante|london eye|high roller|ain d[uú]b[aá]i|ain dubai|observation wheel|\brueda\b/i, 'roda_gigante'], [/[aá]rbol|[aá]rvore|\btree\b/i, 'arvore'], [/\bcasa\b|\bhouse\b/i, 'casa']];
    const modeloPeloNome = (n) => { for (const [re, m] of PELO_NOME) if (re.test(String(n || ''))) return m; return null; };
    const itens = (Array.isArray(spec.itens) ? spec.itens.slice(0, 12) : []).map((it, i) => {
      const tam = num(it.tamanho_m != null ? it.tamanho_m : it.altura_m, 0.001, 2e7, 1), cor = corOk(it.cor, null);
      let g;
      const pronto = it.modelo ? null : modeloPeloNome(it.nome);
      if (pronto) g = pecaPronta(pronto, cor);
      else if (Array.isArray(it.partes) && it.partes.length) {
        g = new T.Group();
        it.partes.slice(0, 24).forEach((p) => { const m = new T.Mesh((F[p.forma] || F.caixa)(), M(corOk(p.cor, cor || '#B8C4D0'), p.material));
          m.position.set(...vet(p.pos, -5, 5, [0, 0.5, 0])); m.scale.set(...vet(p.tam, 0.001, 5, [1, 1, 1])); m.rotation.set(...vet(p.giro, -360, 360, [0, 0, 0]).map((a) => (a * Math.PI) / 180)); g.add(m); });
      } else g = pecaPronta(String(it.modelo || 'cilindro'), cor);
      // normaliza: a MAIOR dimensao vira `tamanho_m` (a baleia mede 30 m de
      // comprimento, nao de altura; a torre, 330 m de altura)
      // v3 (13/11): item CHATO (folha, espelho, pista, pegada) deitado no chao vira uma linha invisivel -- a comparacao
      // do titulo some. Ele fica EM PE, inclinado para a camera, como uma placa: a area aparece.
      const b0 = new T.Box3().setFromObject(g), dx0 = b0.max.x - b0.min.x, dy0 = b0.max.y - b0.min.y, dz0 = b0.max.z - b0.min.z;
      if (dy0 < 0.2 * Math.max(dx0, dz0) && dz0 > 0.3 * dx0) { const pe = new T.Group(); pe.add(g); g.rotation.x = Math.PI / 2 * 0.88; g = pe; g.userData.emPe = true; }
      const b = new T.Box3().setFromObject(g), maior = Math.max(1e-6, b.max.y - b.min.y, b.max.x - b.min.x);
      g.scale.multiplyScalar(tam / maior); g.position.y = -b.min.y * (tam / maior);
      const b2 = new T.Box3().setFromObject(g), alt = Math.max(1e-6, b2.max.y - b2.min.y), larg = Math.max(alt * 0.2, b2.max.x - b2.min.x);
      g.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
      sc.add(g);
      return { nome: String(it.nome || 'item ' + (i + 1)).slice(0, 26), tam, alt, larg, g, s0: g.scale.clone(), y0: g.position.y };
    });
    // lado a lado, do menor para a direita, com um respiro proporcional
    let x = 0; itens.forEach((it, i) => { if (i) x += (itens[i - 1].larg + it.larg) * 0.5 + Math.max(itens[i - 1].larg, it.larg) * 0.25; it.x = x; it.g.position.x = x; });
    const chaoTam = Math.max(10, x * 4 + (itens.length ? itens[itens.length - 1].alt * 20 : 10));
    // CHAO QUE ACOMPANHA O ZOOM (23/10): o disco tem 60x a distancia da camera
    // e a grama repete na mesma proporcao -- de perto parece grama, de longe campo
    // v3: a grama texturizada virava um borrao verde em metade do quadro; chao liso + GRADE DE MEDIDA (a grade
    // acompanha o zoom: as linhas mantem o espacamento na tela e dao a escala ao olho)
    // v4: o renderer usa tom ACES + saida sRGB; cor 'Basic' em hex passava pelo tom e saia LAVADA (o chao claro do v3).
    // Cor convertida para linear e fora do tone mapping = a cor que se pediu.
    const corPura = (hex, extra) => Object.assign({ color: new T.Color(hex).convertSRGBToLinear(), fog: false, toneMapped: false }, extra || {});
    const chao = new T.Mesh(new T.CircleGeometry(1, 64), new T.MeshBasicMaterial(corPura('#79B256')));
    chao.rotation.x = -Math.PI / 2; chao.position.x = x / 2; chao.scale.setScalar(chaoTam); chao.receiveShadow = true; sc.add(chao);
    const grade = new T.GridHelper(1, 40, new T.Color('#4F8A35').convertSRGBToLinear(), new T.Color('#5E9741').convertSRGBToLinear()); grade.material.toneMapped = false; grade.position.y = 0.0005; grade.material.transparent = true; grade.material.opacity = 0.9; sc.add(grade);

    // v4 (14/11, dono: "na comparacao de tamanhos tente ser mais criativo, algo que prenda, mais dinamico, mais movimento
    // e mais detalhes"): HORIZONTE com morros e nuvens em unidade "distancia da camera" -- em qualquer zoom (1 cm ou
    // 1000 km) o fundo tem detalhe e paralaxe, em vez de ceu liso + chao liso.
    const horizonte = new T.Group(); sc.add(horizonte);
    { const rh = U.rng('horizonte'), mMorro = [new T.MeshBasicMaterial(corPura('#8FB8C8')), new T.MeshBasicMaterial(corPura('#A9C9D8'))];   // azulados: longe
      for (let k = 0; k < 34; k++) { const a = (k / 34) * Math.PI * 2 + rh() * 0.1, r0 = 150 + (k % 2) * 25, h = 1.2 + rh() * 2.6;
        const m = new T.Mesh(new T.SphereGeometry(10 + rh() * 12, 14, 8, 0, Math.PI * 2, 0, Math.PI / 2), mMorro[k % 2]); m.position.set(Math.cos(a) * r0, -0.3, Math.sin(a) * r0); m.scale.y = h / 6; horizonte.add(m); }
      const mNuv = new T.MeshBasicMaterial(corPura('#FFFFFF', { transparent: true, opacity: 0.95 }));
      for (let k = 0; k < 14; k++) { const n = new T.Group(), a = rh() * Math.PI * 2, r0 = 38 + rh() * 30, y = 9 + rh() * 9;
        for (let j = 0; j < 4; j++) { const b = new T.Mesh(new T.SphereGeometry(1, 12, 8), mNuv); b.position.set((j - 1.5) * 1.6, (j % 2) * 0.5, 0); b.scale.set(1.6 + rh(), 1 + rh() * 0.5, 1); n.add(b); }
        n.position.set(Math.cos(a) * r0, y, Math.sin(a) * r0); n.lookAt(0, y, 0); n.scale.setScalar(1.4 + rh() * 1.2); n.userData.v = 0.4 + rh() * 0.6; horizonte.add(n); } }
    // chao com vida: tufos de grama e flores em unidade de distancia (acompanham o zoom como a grade)
    const tufos = new T.Group(); sc.add(tufos);
    { const rt = U.rng('tufos'), mT = [new T.MeshBasicMaterial(corPura('#5E9A3E')), new T.MeshBasicMaterial(corPura('#4C8A33'))], mF = ['#FFFFFF', '#FFD23F', '#F27DA3'].map((h) => new T.MeshBasicMaterial(corPura(h)));
      for (let k = 0; k < 160; k++) { const a = rt() * Math.PI * 2, r0 = 0.9 + Math.pow(rt(), 0.7) * 30, x = Math.cos(a) * r0, z = Math.sin(a) * r0 * 0.9 + 0.3;
        if (Math.abs(z) < 0.5 && Math.abs(x) < 1.5) continue;
        const tf = new T.Group(); tf.position.set(x, 0, z);
        for (let j = 0; j < 3; j++) { const f = new T.Mesh(new T.ConeGeometry(0.035, 0.16 + rt() * 0.1, 4), mT[j % 2]); f.position.set((j - 1) * 0.04, 0.08, 0); f.rotation.z = (j - 1) * 0.35; tf.add(f); }
        if (rt() < 0.3) { const fl = new T.Mesh(new T.SphereGeometry(0.035, 8, 6), mF[k % 3]); fl.position.y = 0.2; tf.add(fl); }
        tufos.add(tf); } }
    const poeira = new T.Mesh(new T.RingGeometry(0.62, 1, 48), new T.MeshBasicMaterial({ color: '#E9DFC8', transparent: true, opacity: 0, depthWrite: false, side: T.DoubleSide }));
    poeira.rotation.x = -Math.PI / 2; sc.add(poeira);
    const idxAlvo = (cn, i) => {
      if (typeof cn.alvo === 'number') return U.clamp(Math.round(cn.alvo), 0, Math.max(0, itens.length - 1));
      const k = itens.findIndex((it) => it.nome.toLowerCase() === String(cn.alvo || '').toLowerCase());
      return k >= 0 ? k : Math.min(i, itens.length - 1);
    };
    // o enquadramento que mostra os itens 0..a inteiros: centro e distancia
    function quadroDe(a) {
      if (!itens.length) return { cx: 0, cy: 1, d: 6 };
      const it = itens[a]; let x0 = Math.max(itens[0].x - itens[0].larg, it.x - Math.max(it.alt * 1.2, it.larg * 0.65)); const x1 = it.x + it.larg * 0.65;
      // v3: a comparacao do titulo precisa dos DOIS no quadro -- o item anterior entra sempre
      if (a > 0) x0 = Math.min(x0, itens[a - 1].x - itens[a - 1].larg * 0.95);
      const hfov = 2 * Math.atan(Math.tan((cam.fov * Math.PI) / 360) * cam.aspect), vfov = (cam.fov * Math.PI) / 180;
      // v2 05/11: margens mais justas -- o item da vez ocupa o quadro (antes ~25% da altura)
      // v3: o item ocupa ~55% da altura util (antes 1,3x de folga + metade de baixo do quadro vazia)
      const h = it.alt * 1.15, w = x1 - x0, d = Math.max((w / 2) / Math.tan(hfov / 2) * 0.95, (h / 2) / Math.tan(vfov / 2) * 0.98);
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
      let miraY = cy * 0.82;   // v3: mira mais perto do centro do item -- ele desce para o meio do quadro
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
      // v4: na TROCA a camera voa em arco (gira para um lado e sobe) e assenta; parada, gira devagar em volta
      const lado = i % 2 ? -1 : 1, salto = Math.abs(Math.log(B.d / Math.max(1e-9, A.d)));
      const voo = a !== ant ? Math.sin(Math.PI * q) : 0;
      let ang = lado * (0.42 * voo + 0.16 * Math.sin(local * 0.9)) + Math.sin(t * 0.35) * 0.05;
      // entrada do item da vez: cai do alto e quica (mola); os outros ficam no tamanho normal
      const entra = a !== ant || i === 0 ? U.clamp((local - 0.12) / 0.55, 0, 1) : 1;
      itens.forEach((it, j) => { const sEnt = j === a && entra < 1 ? Math.max(0.001, U.mola(entra * 1.4, 9)) : 1;
        it.g.scale.copy(it.s0).multiplyScalar(sEnt); it.g.position.y = it.y0 * sEnt + (j === a && entra < 1 ? it.alt * 1.6 * Math.pow(1 - U.clamp(entra * 2.2, 0, 1), 2) : 0); });
      const pouso = U.clamp((entra - 0.45) / 0.4, 0, 1), treme = a !== ant && pouso > 0 && pouso < 1 ? (1 - pouso) * 0.012 : 0;
      // v2 05/11: item chato e largo (avião, pista, zona) visto do chão vira uma linha;
      // a câmera sobe em ângulo proporcional a largura/altura e mostra a ÁREA.
      const elevDe = (j) => { const it = itens[j]; if (!it) return 0; const r = it.larg / Math.max(1e-6, it.alt); return U.clamp((Math.log(r) - 1.2) / 2.4, 0, 0.75); };
      const elev = U.clamp(0.17 + U.lerp(elevDe(ant), elevDe(a), q) + 0.32 * voo * U.clamp(salto / 1.5, 0.35, 1), 0, 0.9);
      if (elev > 0.01) { miraY = U.lerp(miraY, 0, U.clamp(elev / 0.4, 0, 1)); }
      cam.position.set(cx + Math.sin(ang) * d * Math.cos(elev) + Math.sin(t * 61) * treme * d, cy * 0.55 + d * Math.sin(elev) + Math.cos(t * 53) * treme * d, Math.cos(ang) * d * Math.cos(elev));
      horizonte.position.set(cam.position.x, 0, cam.position.z); horizonte.scale.setScalar(d);
      horizonte.children.forEach((n) => { if (n.userData.v) n.rotation.z = 0; });
      horizonte.rotation.y = t * 0.012; tufos.position.set(cx, 0, 0); tufos.scale.setScalar(d * 0.5);
      if (itens[a]) { const it = itens[a], qp = U.clamp((entra - 0.5) / 0.5, 0, 1);
        poeira.visible = a !== ant && qp > 0 && qp < 1; poeira.position.set(it.x, Math.max(1e-4, d * 0.0006), 0);
        poeira.scale.setScalar(Math.max(it.larg * 0.6, it.alt * 0.3) * (0.55 + qp * 0.8)); poeira.material.opacity = 0.45 * (1 - qp) * (1 - qp); } cam.near = d / 5000; cam.far = d * 2000; cam.updateProjectionMatrix();
      if (T3) {
        chao.position.set(cx, 0, 0); chao.scale.setScalar(d * 600);   // v4: com o voo em arco a borda do disco (60x) aparecia como cupula
        grade.position.set(cx, d * 0.0004, 0); grade.scale.setScalar(d * 6);
        nevoa.near=d*25;nevoa.far=d*160;   // v3: a nevoa a 6x lavava o chao de branco
        sol.position.set(cx + d * 0.7, d * 1.4, d * 1.1); sol.target.position.set(cx, 0, 0);
        const sh = sol.shadow.camera; sh.left = sh.bottom = -d * 1.2; sh.right = sh.top = d * 1.2; sh.near = d * 0.05; sh.far = d * 5; sh.updateProjectionMatrix();
      }
      cam.lookAt(cx, miraY, 0);
      U3.render(R, sc, cam, spec, t); c.drawImage(gl, 0, 0, W, H);
      // v4: LINHAS DE VELOCIDADE quando o salto de tamanho e' grande (a camera recua por ordens de grandeza)
      if (a !== ant && salto > 0.7 && voo > 0.05) {
        const rv = U.rng('vel' + i), forca = voo * U.clamp(salto / 3, 0.3, 1);
        c.save(); c.translate(W / 2, H * 0.48); c.strokeStyle = 'rgba(255,255,255,' + (0.55 * forca).toFixed(3) + ')'; c.lineCap = 'round';
        for (let k = 0; k < 46; k++) { const an = rv() * Math.PI * 2, r0 = 300 + rv() * 260 + ((t * 2400 + rv() * 900) % 700), len = 90 + rv() * 220 * forca;
          c.lineWidth = 3 + rv() * 6; c.beginPath(); c.moveTo(Math.cos(an) * r0, Math.sin(an) * r0); c.lineTo(Math.cos(an) * (r0 + len), Math.sin(an) * (r0 + len)); c.stroke(); }
        c.restore();
      }
      // etiquetas: nome e altura de cada item visivel, ancoradas no topo dele.
      // 23/10: o destaque e' posto primeiro; etiqueta secundaria que bateria
      // numa ja posta some (antes "1 BARCO" cobria "KHALIFA"); nunca sai pela
      // borda (conta a largura real) nem sobe para baixo do selo do alto.
      const comHud = !!(cn.hud && typeof cn.hud !== 'object');
      const yMin = spec.titulo && t < 3.4 ? 620 : comHud ? 540 : 330, postas = [];   // v4: o titulo vem antes do HUD
      const ordem = itens.map((it, j) => j).filter((j) => j <= a).sort((x, y) => (y === a) - (x === a));
      ordem.forEach((j) => {
        const it = itens[j];
        const p = new T.Vector3(it.x, it.alt, 0).project(cam); if (p.z > 1) return;
        const px = (p.x * 0.5 + 0.5) * W, py = (-p.y * 0.5 + 0.5) * H; if (px < -50 || px > W + 50 || py < 0) return;
        const tamPx = Math.abs(py - (-new T.Vector3(it.x, 0, 0).project(cam).y * 0.5 + 0.5) * H); if (tamPx < 26 && j !== a) return;
        const conta = j === a && (a !== ant || i === 0) ? U.saida(U.clamp((local - 0.2) / 0.7, 0, 1)) : 1;   // v4: o numero CONTA ate' a medida
        const v = it.tam * conta, real = v >= 1000 ? (v / 1000).toLocaleString('en-US', { maximumFractionDigits: 1 }) + ' km' : v >= 1 ? v.toLocaleString('en-US', { maximumFractionDigits: 1 }) + ' m' : (v * 100).toLocaleString('en-US', { maximumFractionDigits: 1 }) + ' cm';
        const destaque = j === a, ent = destaque ? U.mola(local - 0.15, 10) : 1;
        c.save();
        c.font = (destaque ? '64px' : '42px') + ' "Lilita One", sans-serif';
        // v3: "AUTOBÚS DE 12 METROS / 12 m" repetia a medida -- se o nome ja traz numero, fica so o nome
        const l1 = it.nome.toUpperCase(), soNome = /\d/.test(it.nome), w1 = Math.min(W - 40, Math.max(c.measureText(l1).width, soNome ? 0 : c.measureText(real).width) + 40), hh = soNome ? (destaque ? 92 : 66) : destaque ? 150 : 104;
        const bx = U.clamp(px, w1 * 0.58 + 20, W - w1 * 0.58 - 20), by = Math.max(yMin, py - 40);
        const caixa = [bx - w1 / 2, by - hh, bx + w1 / 2, by];
        if (!destaque && postas.some((r) => caixa[0] < r[2] + 12 && caixa[2] > r[0] - 12 && caixa[1] < r[3] + 12 && caixa[3] > r[1] - 12)) { c.restore(); return; }
        postas.push(caixa);
        c.translate(bx, by); c.scale(ent, ent);
        c.textAlign = 'center'; c.textBaseline = 'bottom';
        U.rr(c, -w1 / 2, -hh, w1, hh, 22); c.fillStyle = destaque ? '#FFD23F' : 'rgba(255,255,255,0.85)'; c.fill();
        c.fillStyle = '#1B1B1B';
        if (soNome) c.fillText(l1, 0, -hh * 0.18, w1 - 30);
        else { c.fillText(l1, 0, -hh / 2 + 4, w1 - 30); c.font = (destaque ? '54px' : '36px') + ' "Lilita One", sans-serif'; c.fillText(real, 0, -12, w1 - 30); }
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
      // v4: SELO "xN" -- quantas vezes o item da vez e' maior (ou menor) que o anterior; gira e assenta com mola
      if (a > 0 && itens[a] && itens[a - 1] && local > 0.55 && !(spec.titulo && t < 3.3)) {
        const rz = itens[a].tam / itens[a - 1].tam, maior = rz >= 1, x = maior ? rz : 1 / rz;
        if (x >= 1.5) {
          const fmt = x >= 1e6 ? (x / 1e6).toLocaleString('en-US', { maximumFractionDigits: 1 }) + 'M' : x >= 1e4 ? Math.round(x / 1e3) + 'K' : x >= 10 ? Math.round(x).toLocaleString('en-US') : x.toFixed(1).replace(/\.0$/, '');
          const lg = /^es/i.test(spec.idioma || '') ? (maior ? 'MÁS GRANDE' : 'MÁS PEQUEÑO') : /^pt/i.test(spec.idioma || '') ? (maior ? 'MAIOR' : 'MENOR') : (maior ? 'BIGGER' : 'SMALLER');
          const sp = U.mola(local - 0.55, 9), gira = (1 - U.clamp((local - 0.55) / 0.35, 0, 1)) * -0.5;
          c.save(); c.translate(W / 2, H * 0.785); c.rotate(gira); c.scale(sp * 0.8, sp * 0.8); c.textAlign = 'center'; c.textBaseline = 'middle';   // faixa livre abaixo da legenda
          c.font = '118px "Lilita One", sans-serif'; const t1 = '×' + fmt; const w1 = c.measureText(t1).width; c.font = '50px "Lilita One", sans-serif'; const w2 = c.measureText(lg).width;
          const ww = Math.max(w1, w2) + 80; U.rr(c, -ww / 2, -100, ww, 200, 40); c.fillStyle = '#E8473C'; c.fill(); c.lineWidth = 8; c.strokeStyle = '#1B1B1B'; c.stroke();
          c.fillStyle = '#FFFFFF'; c.font = '118px "Lilita One", sans-serif'; c.fillText(t1, 0, -18); c.font = '50px "Lilita One", sans-serif'; c.fillText(lg, 0, 58); c.restore();
        }
      }
      // v3: o HUD aparecia atras do cartaz do titulo -- so' entra depois dele
      if (cn.hud && typeof cn.hud !== 'object' && local > 0.3 && !(spec.titulo && t < 3.3)) { const s = U.mola(local - 0.3, 10); c.save(); c.translate(W / 2, 300); c.scale(s, s); c.font = '120px "Lilita One", sans-serif'; c.textAlign = 'center'; c.textBaseline = 'middle';
        const txt = U.hud(c, cn.hud, c.canvas.width * 0.84 - 70, 22), w = c.measureText(txt).width + 70; U.rr(c, -w / 2, -78, w, 156, 34); c.fillStyle = '#1B1B1B'; c.fill(); c.fillStyle = '#FFD23F'; c.fillText(txt, 0, 6); c.restore(); }
      U.cartaz(c, spec, t, { fonte: '84px "Lilita One", sans-serif', y: 170, fundo: '#FFD23F', borda: '#1B1B1B', cor: '#1B1B1B', altura_linha: 100, dur: 3.0 });
      U.legenda(c, spec, t, { fonte: '100px "Lilita One", sans-serif', y: H * 0.70, cor: '#FFFFFF', cor_ativa: '#FFD23F', contorno: 18, caixa: true, por_vez: 3 });
    }
    return { quadro, dispose: () => U3.liberar(R, sc) };
  }
  MOTORES.escala = { criar };
})();
