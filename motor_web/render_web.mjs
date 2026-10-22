// render_web.mjs -- spec do motor web -> MP4 sem som (13/10, HISTORICO §109).
//
// USO
//   node render_web.mjs --spec spec_render.json --saida video_mudo.mp4 [--quadros 0,12,48 --folha folha.png]
//
// Abre `palco.html` no Chrome headless (puppeteer-core; o Chrome vem do
// sistema: `CHROME` no ambiente, o do runner `ubuntu-latest`, ou o do Windows),
// desenha quadro a quadro e entrega cada JPEG ao ffmpeg por um pipe. Nao ha
// relogio: o quadro f e' desenhado em t = f / fps, entao a velocidade da
// maquina nunca muda o video. `--quadros` desenha so' alguns e monta uma folha
// de contato (conferir em segundos antes de gastar o render inteiro).
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';
import puppeteer from 'puppeteer-core';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };

function acharChrome() {
  const cands = [process.env.CHROME, '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium-browser', '/usr/bin/chromium',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'];
  for (const c of cands) if (c && fs.existsSync(c)) return c;
  throw new Error('[render_web] nenhum Chrome encontrado; defina CHROME=<caminho>');
}

async function main() {
  const spec = JSON.parse(fs.readFileSync(arg('spec'), 'utf8').replace(/^﻿/, ''));
  const saida = arg('saida', 'video_mudo.mp4');
  const fps = spec.fps || 30, n = Math.ceil(spec.dur_s * fps);
  const browser = await puppeteer.launch({ executablePath: acharChrome(), headless: true,
    args: ['--no-sandbox', '--allow-file-access-from-files', '--enable-webgl', '--ignore-gpu-blocklist', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage();
  page.on('console', (m) => console.log('[palco] ' + m.text()));
  page.on('pageerror', (e) => console.log('[palco] ERRO ' + e.message));
  await page.setViewport({ width: Math.min(spec.w, 1080), height: Math.min(spec.h, 1920), deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(path.join(AQUI, 'palco.html')).href, { waitUntil: 'networkidle0', timeout: 60000 });
  const prep = await page.evaluate((s) => window.preparar(s), spec);
  console.log('[render_web] ' + spec.estilo + ': ' + n + ' quadros a ' + fps + ' fps, fontes ' + JSON.stringify(prep.fontes));
  if (prep.acoes && prep.acoes.some(Boolean)) fs.writeFileSync(saida + '.acoes.json', JSON.stringify(prep.acoes));
  if (prep.som && prep.som.length) fs.writeFileSync(saida + '.som.json', JSON.stringify(prep.som));

  const so = arg('quadros');
  if (so) {
    const pasta = path.dirname(path.resolve(arg('folha', 'folha.png')));
    const lista = so.split(',').map(Number);
    const arqs = [];
    for (const f of lista) {
      const url = await page.evaluate((t) => window.quadro(t, 'image/png'), f / fps);
      const a = path.join(pasta, '_q' + f + '.png'); fs.writeFileSync(a, Buffer.from(url.split(',')[1], 'base64')); arqs.push(a);
    }
    await browser.close();
    await rodar('ffmpeg', ['-y', '-loglevel', 'error', ...arqs.flatMap((a) => ['-i', a]), '-filter_complex',
      arqs.map((_, i) => '[' + i + ':v]scale=270:-1[v' + i + ']').join(';') + ';' + arqs.map((_, i) => '[v' + i + ']').join('') + 'hstack=inputs=' + arqs.length, arg('folha', 'folha.png')]);
    arqs.forEach((a) => fs.unlinkSync(a));
    console.log('[render_web] folha: ' + arg('folha', 'folha.png'));
    return;
  }

  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    // crf 21 (13/10): a 19 o grao de pelicula da mangueira dava 57 MB em 21 s
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'medium', '-crf', String(spec.crf || 21), '-maxrate', '8M', '-bufsize', '16M', '-r', String(fps), saida], { stdio: ['pipe', 'inherit', 'inherit'] });
  const t0 = Date.now();
  for (let f = 0; f < n; f++) {
    const url = await page.evaluate((t) => window.quadro(t, 'image/jpeg', 0.93), f / fps);
    const buf = Buffer.from(url.split(',')[1], 'base64');
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (f % (fps * 5) === 0) console.log('[render_web] quadro ' + f + '/' + n + ' (' + ((Date.now() - t0) / 1000).toFixed(0) + ' s)');
  }
  ff.stdin.end();
  await new Promise((r, j) => ff.on('close', (c) => (c === 0 ? r() : j(new Error('ffmpeg saiu com ' + c)))));
  await browser.close();
  console.log('[render_web] ok ' + saida + ' (' + n + ' quadros em ' + ((Date.now() - t0) / 1000).toFixed(0) + ' s)');
}

function rodar(cmd, args) {
  return new Promise((r, j) => { const p = spawn(cmd, args, { stdio: 'inherit' }); p.on('close', (c) => (c === 0 ? r() : j(new Error(cmd + ' saiu com ' + c)))); });
}

main().catch((e) => { console.error('[render_web] FALHOU: ' + (e.stack || e)); process.exit(1); });
