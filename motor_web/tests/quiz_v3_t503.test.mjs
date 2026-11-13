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

test('v3: as frases entre aspas da premissa viram as legendas do roteiro', () => {
  const log = []; const { U, MOTORES, tela } = carregar(log);
  const sp = spec({ metadados: { premissa: "Abre com 'If you blink, your streak ends', depois 'But now, smaller' e fecha com 'How many did you catch?'." } });
  const m = MOTORES.quiz.criar(tela(), sp, U);
  for (let t = 0; t < sp.dur_s; t += 1 / 6) m.quadro(t);
  const txt = log.join(' ');
  assert.ok(txt.includes('IF YOU BLINK, YOUR STREAK ENDS'), 'abertura passa para o nivel 2 quando o nivel 1 e curto');
  assert.ok(txt.includes('BUT NOW, SMALLER'));
  assert.ok(txt.includes('HOW MANY DID YOU CATCH? _/4'));
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
