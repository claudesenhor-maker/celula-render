#!/usr/bin/env python3
"""
palito_v5 — VOZ PRIMEIRO, CENA DEPOIS.

Implementa a estratégia central do vídeo de referência (Elton Machado,
"o ritmo que prende"): o áudio é gerado ANTES de qualquer imagem, e a
duração REAL de cada fala define a timeline. Nada de estimar tempo por
contagem de palavras.

Isso inverte o que o sistema fazia: 'Processar Roteiro' calculava
2,6 pal/s x 1,15 + 0,35s de respiro (§5.2) e a imagem tinha que caber
num tempo inventado. Quando a estimativa errava, a fala atropelava o corte.

Além disso, o lipsync passa a vir da ENVOLTÓRIA REAL do áudio, não de
um seno falso: a boca abre quando há som, fecha quando não há.

Modos:
  --real   usa edge-tts (precisa de rede). É o modo de produção.
  --demo   sintetiza um áudio com formantes e marcas de palavra
           determinísticas. Serve para validar a lógica sem rede.

Uso:
    python3 palito_v5.py --demo  -o saida.mp4
    python3 palito_v5.py --real  -o saida.mp4
    from palito_v5 import render_spec
"""
import argparse, asyncio, json, math, os, subprocess, sys, tempfile, wave
import struct, random
import cairosvg

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from palito_v4 import (W, H, OUT_W, OUT_H, FPS, REST, POSES, EXPRESSOES, merge, blend,
                       frame_svg, BG, TINTA)

SR = 24000


# =====================================================================
# 1. VOZ  — a etapa que define a timeline
# =====================================================================
async def _edge(texto, cfg, out_mp3):
    import edge_tts
    c = edge_tts.Communicate(texto, cfg.get("voice", "pt-BR-AntonioNeural"),
                             rate=cfg.get("rate", "+0%"), pitch=cfg.get("pitch", "+0Hz"))
    marcas, dur = [], 0.0
    with open(out_mp3, "wb") as f:
        async for ch in c.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                ini = ch["offset"] / 1e7
                fim = ini + ch["duration"] / 1e7
                marcas.append({"palavra": ch["text"], "inicio_s": ini, "fim_s": fim})
                dur = max(dur, fim)
    return marcas, dur


def _demo(texto, cfg, out_wav):
    """Voz sintética determinística: dois formantes + envelope por sílaba.
    Não substitui TTS — existe para validar a timeline e o lipsync sem rede."""
    palavras = [p for p in texto.replace(",", " ").split() if p]
    rnd = random.Random(hash(texto) & 0xFFFF)
    base = 118 if cfg.get("pitch", "").startswith("-") else 155
    amostras, marcas, t = [], [], 0.30
    for p in palavras:
        sil = max(1, sum(1 for c in p.lower() if c in "aeiouáéíóúâêôãõ"))
        dur = sil * 0.155 + 0.06
        marcas.append({"palavra": p, "inicio_s": t, "fim_s": t + dur})
        n = int(dur * SR)
        f0 = base * rnd.uniform(0.9, 1.12)
        for i in range(n):
            x = i / SR
            env = math.sin(math.pi * (i / n)) ** 0.6
            s = (0.55 * math.sin(2 * math.pi * f0 * x)
                 + 0.28 * math.sin(2 * math.pi * f0 * 2.4 * x)
                 + 0.12 * math.sin(2 * math.pi * f0 * 3.9 * x))
            amostras.append(s * env * 0.42)
        for _ in range(int(0.075 * SR)):          # pausa entre palavras
            amostras.append(0.0)
        t += dur + 0.075

    with wave.open(out_wav, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, s)) * 32000))
                               for s in amostras))
    return marcas, t


def sintetizar(texto, cfg, destino, modo):
    if modo == "real":
        mp3 = destino + ".mp3"
        marcas, dur = asyncio.run(_edge(texto, cfg, mp3))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3,
                        "-ar", str(SR), "-ac", "1", destino], check=True)
        return marcas, dur
    return _demo(texto, cfg, destino)


# =====================================================================
# 2. LIPSYNC pela envoltória real do áudio
# =====================================================================
def envelope(wav_path, fps=FPS):
    """RMS por frame, normalizado 0..1. A boca segue o som de verdade."""
    with wave.open(wav_path) as w:
        n, sr = w.getnframes(), w.getframerate()
        raw = w.readframes(n)
    dados = struct.unpack(f"<{n}h", raw)
    por_frame = max(1, sr // fps)
    env = []
    for i in range(0, n, por_frame):
        bloco = dados[i:i + por_frame]
        if not bloco:
            break
        env.append(math.sqrt(sum(s * s for s in bloco) / len(bloco)) / 32768.0)
    m = max(env) or 1.0
    # raiz comprime: fala baixa ainda abre a boca um pouco
    return [min(1.0, (v / m) ** 0.55) for v in env]


# =====================================================================
# 3. RENDER
# =====================================================================
def render_spec(spec, saida, modo="demo", tmpdir=None):
    tmp = tmpdir or tempfile.mkdtemp()
    os.makedirs(tmp, exist_ok=True)
    fd = os.path.join(tmp, "frames"); os.makedirs(fd, exist_ok=True)
    vozes = spec.get("vozes", {})

    # ---- 3.1 VOZ PRIMEIRO: a duração real vira a timeline -------------
    faixas, total = [], 0.0
    for i, tr in enumerate(spec["trechos"]):
        wav = os.path.join(tmp, f"v{i:02d}.wav")
        cfg = vozes.get(tr.get("perfil_voz", "narrador"), {})
        marcas, dur = sintetizar(tr["fala"], cfg, wav, modo)
        dur += tr.get("respiro_s", 0.45)
        tr["dur"] = dur                      # <<< SAÍDA do TTS, nunca entrada
        faixas.append(wav)
        total += dur
        print(f"  trecho {i}: {dur:5.2f}s  {len(marcas):2d} palavras  \"{tr['fala'][:44]}\"")
    print(f"[voz] timeline real: {total:.2f}s")

    # ---- 3.2 áudio concatenado + envoltória ---------------------------
    lista = os.path.join(tmp, "a.txt")
    with open(lista, "w") as f:
        for a in faixas:
            f.write(f"file '{a}'\n")
    voz = os.path.join(tmp, "voz.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", lista, "-ar", str(SR), "-ac", "1", voz], check=True)
    env = envelope(voz)

    # ---- 3.3 frames, com a boca seguindo o áudio ----------------------
    n = 0
    for tr in spec["trechos"]:
        p1 = merge(REST, POSES[tr["pose"]], EXPRESSOES[tr["expressao"]])
        p2 = merge(REST, POSES[tr.get("pose_saida", tr["pose"])], EXPRESSOES[tr["expressao"]])
        dois = tr.get("quem") == "ab"
        if dois:
            p1, p2 = merge(p1, {"dx": -230}), merge(p2, {"dx": -230})
            sec = merge(REST, POSES[tr.get("pose_b", "parado_falando")],
                        EXPRESSOES[tr.get("expressao_b", "neutro")],
                        {"dx": 250, "cabeca_r": 112, "boca": 0.18})
        for f in range(max(1, int(tr["dur"] * FPS))):
            fh = (f // 2) * 2
            t = fh / max(1, int(tr["dur"] * FPS) - 1)
            rig = blend(p1, p2, t * t * (3 - 2 * t))
            rig["boca"] = 0.10 + 0.62 * (env[n] if n < len(env) else 0.0)   # <<< áudio real
            rig["quadril"] = [rig["quadril"][0], rig["quadril"][1] + math.sin(f * 0.13) * 6]
            rigs = [(rig, "#5A6B7A")] + ([(dict(sec), "#8C5F52")] if dois else [])
            cairosvg.svg2png(bytestring=frame_svg(rigs, fh // 2, tr.get("cenario", "sala")).encode(),
                             write_to=os.path.join(fd, f"{n:05d}.png"),
                             output_width=OUT_W, output_height=OUT_H)
            n += 1
    print(f"[rig] {n} frames ({n/FPS:.1f}s)")

    # ---- 3.4 trilha + loudnorm ---------------------------------------
    mix = voz
    if spec.get("musica"):
        mix = os.path.join(tmp, "mix.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", voz, "-i", spec["musica"],
                        "-filter_complex",
                        f"[1:a]volume={spec.get('musica_db',-24)}dB,aloop=loop=-1:size=2e9[m];"
                        "[0:a][m]amix=inputs=2:duration=first:dropout_transition=0[a]",
                        "-map", "[a]", mix], check=True)

    subprocess.run(["ffmpeg", "-y", "-v", "error",
                    "-framerate", str(FPS), "-i", os.path.join(fd, "%05d.png"),
                    "-i", mix,
                    "-vf", "noise=alls=4:allf=t,eq=saturation=0.94",
                    "-af", spec.get("loudnorm", "loudnorm=I=-9:LRA=8:TP=-1.5"),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "21",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", saida], check=True)
    return saida, round(n / FPS, 2)


# =====================================================================
SPEC_EXEMPLO = {
    "vozes": {
        "protagonista": {"voice": "pt-BR-FabioNeural", "rate": "+10%", "pitch": "+12Hz"},
        "secundario":   {"voice": "pt-BR-AntonioNeural", "rate": "+4%", "pitch": "-18Hz"},
    },
    "loudnorm": "loudnorm=I=-9:LRA=8:TP=-1.5",
    "trechos": [
        {"fala": "Falei pro meu chefe que hoje eu ia chegar cedo.",
         "perfil_voz": "protagonista", "pose": "parado_falando",
         "pose_saida": "bracos_abertos", "expressao": "neutro", "cenario": "sala"},
        {"fala": "Cheguei. Sete e cinquenta e nove da manhã.",
         "perfil_voz": "protagonista", "pose": "bracos_abertos",
         "pose_saida": "maos_na_cintura", "expressao": "sorrindo", "cenario": "sala"},
        {"fala": "Ele olhou pro relógio e falou: reunião foi ontem.",
         "perfil_voz": "secundario", "pose": "maos_na_cintura",
         "pose_saida": "pensando", "expressao": "duvida", "cenario": "mesa",
         "quem": "ab", "pose_b": "apontando", "expressao_b": "bravo"},
        {"fala": "Eu cheguei cedo. Vinte e quatro horas cedo.",
         "perfil_voz": "protagonista", "pose": "pensando",
         "pose_saida": "maos_na_cabeca", "expressao": "surpreso", "cenario": "mesa"},
    ],
}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["real", "demo"], default="demo")
    ap.add_argument("-o", "--saida", default="/tmp/poc5/palito_v5.mp4")
    ap.add_argument("--spec", help="spec.json; usa o exemplo se omitido")
    a = ap.parse_args()
    spec = json.load(open(a.spec)) if a.spec else SPEC_EXEMPLO
    os.makedirs(os.path.dirname(a.saida), exist_ok=True)
    print(f"modo: {a.modo}")
    out, dur = render_spec(spec, a.saida, a.modo, tmpdir="/tmp/poc5")
    print(f"[ok] {out}  {dur}s")
