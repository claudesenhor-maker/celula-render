import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

const context = { window: {} };
vm.runInNewContext(fs.readFileSync(new URL('../comum.js', import.meta.url), 'utf8'), context);
const U = context.window.U;

test('preserva o quadro inicial e alterna enquadramento até seis segundos', () => {
  const spec = { cenas: [{ ini: 0 }], palavras: [] };
  assert.equal(U.ritmoInicio(spec, 0).zoom, 1);
  assert.equal(U.ritmoInicio(spec, 1.5).zoom, 1.08);
  assert.equal(U.ritmoInicio(spec, 3).zoom, 1);
  assert.equal(U.ritmoInicio(spec, 4.5).zoom, 1.08);
  assert.equal(U.ritmoInicio(spec, 6).zoom, 1);
});

test('preenche lacunas da fala e mantém resultado fora da ordem de render', () => {
  const spec = { cenas: [{ ini: 0 }, { ini: 4.9 }], palavras: [
    { ini: 0 }, { ini: .2 }, { ini: .4 }, { ini: .8 },
    { ini: 1 }, { ini: 1.2 }, { ini: 4.8 },
  ] };
  const before = JSON.stringify(spec);
  const first = JSON.stringify(U.ritmoInicio(spec, .9));
  U.ritmoInicio(spec, 5.5);
  assert.equal(JSON.stringify(U.ritmoInicio(spec, .9)), first);
  assert.equal(JSON.stringify(spec), before);
  const marks = [...U.ritmoInicio(spec, 0).marcos, 6];
  for (let i = 1; i < marks.length; i++) assert.ok(marks[i] - marks[i - 1] <= 1.5);
  for (let i = 1; i < marks.length - 1; i++) assert.ok(marks[i] - marks[i - 1] >= .35);
});

test('cópia do primeiro quadro não recorta as bordas do título', () => {
  const calls = [];
  const ctx = { setTransform() {}, clearRect() {}, drawImage(...args) { calls.push(args); } };
  const source = { width: 1080, height: 1920 };
  const output = { getContext() { return ctx; } };
  assert.equal(U.quadroComRitmo(source, { cenas: [] }, 0, output), output);
  assert.deepEqual(calls[0], [source, 0, 0, 1080, 1920, 0, 0, 1080, 1920]);
});
