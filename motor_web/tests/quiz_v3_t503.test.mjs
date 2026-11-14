// Quiz v3 (T503, 13/11): redesenho do motor do ODD ONE OUT. Roda o motor num canvas falso
// (sem navegador) e confere os erros que a v3 corrigiu.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const raiz = path.join(path.dirname(fileURLToPath(import.meta.url)), '..');
const fonte = fs.readFileSync(path.join(raiz, 'estilos/quiz.js'), 'utf8');

function contexto(log) {
  const alvo = { measureText: (t) => ({ width: String(t).length * 30 }), createRadialGradient: () => ({ addColorStop() {} }),
    fillText: (t) => log.push(String(t)), strokeText() {} };
  return new Proxy(alvo, { get: (o, k) => (k in o ? o[k] : () => {}), set: (o, k, v) => { o[k] = v; return true; } });
}
function carregar(log) {
  const tela = () => ({ width: 0, height: 0, getContext: () => contexto(log) });
  const janela = { MOTORES: {} };
  const sb = { window: janela, MOTORES: janela.MOTORES, document: { createElement: tela }, Math, console };
  vm.createContext(sb);
  vm.runInContext(fs.readFileSync(path.join(raiz, 'comum.js'), 'utf8'), sb);
  vm.runInContext(fonte, sb);
  return { U: janela.U, MOTORES: janela.MOTORES, tela };
}
function spec(extra) {
  const cenas = [
    { tipo: 'formas', base: 'seta', diferente: 'sem_pedaco', colunas: 6, linhas: 9, dificuldade: 2, texto: 'Rookie', dur_s: 4 },
    { tipo: 'letras', base: '8', diferente: 'B', colunas: 8, linhas: 11, dificuldade: 3, texto: 'Look closer', dur_s: 5 },
    { tipo: 'icones', base: 'chave', diferente: 'menor', colunas: 9, linhas: 14, dificuldade: 4, texto: 'Expert', dur_s: 6 },
    { tipo: 'cores', base: 'olho', colunas: 12, linhas: 16, dificuldade: 5, texto: 'Only 0.1% see it', dur_s: 7 },
  ];
  let t = 0; for (const c of cenas) { c.ini = t; c.fim = t + c.dur_s; t += c.dur_s; }
  return { w: 1080, h: 1920, fps: 30, dur_s: t, estilo: 'quiz', idioma: 'en-US', semente: 'teste-v3', titulo: 'Spot It Fast', cenas, ...extra };
}

test('v3: nenhum furo atravessa o cartao (destination-out mostrava o fundo e entregava a resposta)', () => {
  assert.ok(!/globalCompositeOperation\s*=\s*'destination-out'/.test(fonte));
});

test('v3: a revelacao continua com 1,3 s (o "plim" do montar_web.py cai em fim-1,3)', () => {
  assert.match(fonte, /const REVELA = 1\.3;/);
});

test('v3: todos os quadros desenham sem erro e mostram placar, legenda e pedido de placar no fim', () => {
  const log = []; const { U, MOTORES, tela } = carregar(log);
  const sp = spec();
  const m = MOTORES.quiz.criar(tela(), sp, U);
  for (let t = 0; t < sp.dur_s; t += 1 / 6) m.quadro(t);
  const txt = log.join(' ');
  assert.ok(txt.includes('1/4') && txt.includes('4/4'), 'placar de progresso');
  assert.ok(!txt.includes('FIND THE ODD ONE OUT'), 'nivel 1 de 4 s: o cartaz do titulo ocupa o alto, a abertura nao pisca');
  assert.ok(txt.includes('FOUND IT?'), 'legenda da revelacao');
  assert.ok(txt.includes('HOW MANY DID YOU GET? _/4'), 'fim pede o placar');
  assert.ok(!txt.includes('NOW LOOK CLOSER'), 'legenda nao repete o rotulo "LOOK CLOSER"');
});

test('14/11: a premissa (nota interna, as vezes em portugues) NUNCA vira legenda; spec.legendas sim', () => {
  const log = []; const { U, MOTORES, tela } = carregar(log);
  const sp = spec({ metadados: { premissa: "Abre com 'que um furo dessa grade esta', depois 'dito em uma frase:' e fecha." } });
  const m = MOTORES.quiz.criar(tela(), sp, U);
  for (let t = 0; t < sp.dur_s; t += 1 / 6) m.quadro(t);
  const txt = log.join(' ');
  assert.ok(!txt.includes('QUE UM FURO DESSA GRADE ESTA') && !txt.includes('DITO EM UMA FRASE'), 'premissa em PT nao aparece no canal em ingles');
  const log2 = []; const c2 = carregar(log2);
  const sp2 = spec({ legendas: ['If you blink, your streak ends', 'But now, smaller', 'How many did you catch?'] });
  const m2 = c2.MOTORES.quiz.criar(c2.tela(), sp2, c2.U);
  for (let t = 0; t < sp2.dur_s; t += 1 / 6) m2.quadro(t);
  assert.ok(log2.join(' ').includes('BUT NOW, SMALLER'), 'spec.legendas continua valendo');
});

test('v3: legendas em espanhol e portugues', () => {
  for (const [idioma, frase] of [['es-MX', 'ENCUENTRA EL DIFERENTE'], ['pt-BR', 'ACHE O DIFERENTE']]) {
    const log = []; const { U, MOTORES, tela } = carregar(log);
    const sp = spec({ idioma, titulo: '' });
    const m = MOTORES.quiz.criar(tela(), sp, U);
    m.quadro(1);
    assert.ok(log.join('|').includes(frase), idioma);
  }
});

test('encerramento (cta_s): placar nos comentarios, like e inscrever no fim; o jogo do ultimo nivel acaba antes', () => {
  const log = []; const { U, MOTORES, tela } = carregar(log);
  const sp = spec(); sp.cta_s = 2.6; sp.cenas.at(-1).fim += 2.6; sp.dur_s += 2.6;
  const m = MOTORES.quiz.criar(tela(), sp, U);
  const fimJogo = sp.dur_s - 2.6;
  log.length = 0; m.quadro(fimJogo - 0.2);
  assert.ok(!log.join(' ').includes('COMMENT YOUR SCORE'), 'revelacao ainda sem encerramento');
  log.length = 0; m.quadro(fimJogo + 0.9);
  let txt = log.join(' ');
  assert.ok(txt.includes('COMMENT YOUR SCORE') && txt.includes('LIKE IF YOU GOT 4/4') && txt.includes('SUBSCRIBE'), txt);
  log.length = 0; m.quadro(sp.dur_s - 0.05);
  assert.ok(log.join(' ').includes('SUBSCRIBED'), 'o botao e apertado');
  // sem cta_s (spec antigo) o fim nao muda
  const log2 = []; const k = carregar(log2); const sp2 = spec(); const m2 = k.MOTORES.quiz.criar(k.tela(), sp2, k.U);
  m2.quadro(sp2.dur_s - 0.05); assert.ok(!log2.join(' ').includes('SUBSCRIBE'));
});
