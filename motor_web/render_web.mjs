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
import {prepararSpec} from './diretor_visual.mjs';
import {revisarAntesDoRender} from './preflight.mjs';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };

function acharChrome() {
  const cands = [process.env.CHROME, '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable', '/usr/bin/chromium-browser', '/usr/bin/chromium',
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'];
  for (const c of cands) if (c && fs.existsSync(c)) return c;
  throw new Error('[render_web] nenhum Chrome encontrado; defina CHROME=<caminho>');
}

async function main() {
  let spec = prepararSpec(JSON.parse(fs.readFileSync(arg('spec'), 'utf8').replace(/^﻿/, '')));
  const saida = arg('saida', 'video_mudo.mp4');
  const fps = spec.fps || 30, n = Math.ceil(spec.dur_s * fps);
  const browser = await puppeteer.launch({ executablePath: acharChrome(), headless: true,
    args: ['--no-sandbox', '--allow-file-access-from-files', '--enable-webgl', '--ignore-gpu-blocklist', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  let ff;
  try {
  const page = await browser.newPage();
  const errosPagina=[];
  page.on('console', (m) => console.log('[palco] ' + m.text()));
  page.on('pageerror', (e) => {errosPagina.push(e.message);console.log('[palco] ERRO ' + e.message);});
  await page.setViewport({ width: Math.min(spec.w, 1080), height: Math.min(spec.h, 1920), deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(path.join(AQUI, 'palco.html')).href, { waitUntil: 'networkidle0', timeout: 60000 });
  if(errosPagina.length)throw Error(errosPagina.join('; '));
  let prep = await page.evaluate((s) => window.preparar(s), spec);
  if(!arg('quadros')) {
    spec = await revisarAntesDoRender(page,spec,saida);
    // As ações e os sons pertencem à última preparação, que pode ter sido corrigida.
    prep = {...prep,...await page.evaluate(()=>({acoes:SPEC_INICIO_T272.cenas.map(c=>c.acaoV2||null),som:window.EVENTOS_SOM||[]}))};
  }
  fs.writeFileSync(saida+'.spec.json',JSON.stringify(spec,null,2));
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

  const jpeg=spec.qualidade==='rapido';
  ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', jpeg ? 'mjpeg' : 'png', '-i', '-',
    // PNG intermediário preserva contornos; o perfil rápido usa JPEG. O grão é controlado no estilo.
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-preset', 'medium', '-crf', String(spec.crf ?? (spec.estilo==='pixel'?18:20)), '-maxrate', '16M', '-bufsize', '32M', '-r', String(fps),
    '-vf', 'scale=out_color_matrix=bt709:out_range=tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv', '-movflags', '+faststart', saida], { stdio: ['pipe', 'inherit', 'inherit'] });
  const encerrado=new Promise((r,j)=>{ff.once('error',j);ff.once('close',c=>c===0?r():j(Error('ffmpeg saiu com '+c)));});
  encerrado.catch(()=>{});
  ff.stdin.on('error',()=>{});
  const t0 = Date.now();
  for (let f = 0; f < n; f++) {
    const url = await page.evaluate(({t,jpeg}) => window.quadro(t, jpeg ? 'image/jpeg' : 'image/png', 0.95), {t:f / fps,jpeg});
    const buf = Buffer.from(url.split(',')[1], 'base64');
    if (!ff.stdin.write(buf)) await Promise.race([new Promise((r) => ff.stdin.once('drain', r)),encerrado.then(()=>{throw Error('ffmpeg encerrou antes do último quadro');})]);
    if (f % (fps * 5) === 0) console.log('[render_web] quadro ' + f + '/' + n + ' (' + ((Date.now() - t0) / 1000).toFixed(0) + ' s)');
  }
  ff.stdin.end();
  await encerrado;
  await browser.close();
  console.log('[render_web] ok ' + saida + ' (' + n + ' quadros em ' + ((Date.now() - t0) / 1000).toFixed(0) + ' s)');
  } finally {if(ff && ff.exitCode===null)ff.kill('SIGTERM');await browser.close();}
}

function rodar(cmd, args) {
  return new Promise((r, j) => { const p = spawn(cmd, args, { stdio: 'inherit' }); p.on('close', (c) => (c === 0 ? r() : j(new Error(cmd + ' saiu com ' + c)))); });
}

main().catch((e) => { console.error('[render_web] FALHOU: ' + (e.stack || e)); process.exit(1); });
