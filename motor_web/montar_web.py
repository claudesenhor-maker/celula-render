# -*- coding: utf-8 -*-
"""montar_web.py -- spec do motor web -> MP4 com som (13/10, HISTORICO §109).

A ORDEM E' A DO MOTOR DO RECORTE (lei do ritmo: VOZ PRIMEIRO, CENA DEPOIS)
    1. narrado: cada cena tem `texto`, que vira voz (`palito_v5.sintetizar`,
       a mesma escada ElevenLabs -> Azure -> Edge) e a DURACAO REAL do audio
       vira a duracao da cena; as marcas de palavra viram a legenda.
       mudo: a duracao vem de `dur_s` da cena, com piso pelo texto que a cena
       mostra (cartela, caixa de dialogo) -- ninguem le mais rapido que 14
       caracteres por segundo.
    2. `render_web.mjs` desenha os quadros (Chrome headless) -> video mudo.
    3. efeitos: os pedidos pela cena (`sfx`) e os que a ACAO implica
       (`EFEITO_DA_ACAO`, por estilo) -> `sfx.mixar` com a trilha do genero
       do estilo (`config.json > formatos.<estilo>.trilha`).
    4. ffmpeg junta video e som.

USO
    python work/motor_web/montar_web.py --spec spec_web.json --saida video.mp4 [--modo-tts demo]

`--modo-tts demo` (ou PRODUCAO != 1) nunca usa voz paga: ensaio e teste usam a
voz sintetica local ou o Edge (`palito_v5`).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import wave

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))          # work/

import sfx as SFX                                   # noqa: E402

# O som que a acao implica, por estilo: (efeito do sfx.py, fracao da cena, ganho)
EFEITO_DA_ACAO = {
    "mangueira": {
        "escorrega": [("boing", 0.34, 1.0), ("thud", 0.64, 1.0)],
        "tropeca": [("whoosh", 0.36, 0.8), ("thud", 0.72, 1.0)],
        "pula_de_susto": [("susto", 0.14, 1.0), ("boing", 0.2, 0.9)],
        "foge": [("whoosh", 0.05, 1.0)],
        "estica_braco": [("whoosh", 0.05, 0.7), ("pop", 0.45, 0.8)],
        "objeto_cai_na_cabeca": [("whoosh", 0.1, 0.7), ("thud", 0.45, 1.2), ("plim", 0.55, 0.8)],
        "ri_apontando": [("rimshot", 0.6, 0.8)],
        "pensa_ideia": [("plim", 0.55, 1.0)],
        "come_rapido": [("pop", 0.2, 0.6), ("pop", 0.45, 0.6), ("pop", 0.7, 0.6)],
        "briga_nuvem": [("thud", 0.1, 0.8), ("thud", 0.35, 0.8), ("thud", 0.6, 0.8)],
        "conversa": [("pop", 0.05, 0.6)],
    },
    "pixel": {
        "acorda": [("notificacao", 0.0, 1.0), ("notificacao", 0.2, 1.0)],
        "batalha": [("susto", 0.0, 0.8), ("thud", 0.46, 1.1), ("erro", 0.5, 0.9)],
        "level_up": [("plim", 0.05, 1.0), ("plim", 0.15, 1.0)],
        "game_over": [("erro", 0.05, 1.0)],
        "compra": [("caixa", 0.2, 1.0)],
        "recebe": [("caixa", 0.2, 1.0)],
        "missao": [("plim", 0.05, 1.0)],
    },
    "silhueta": {"cai": [("thud", 0.6, 0.7)]},
    # 22/10: os eventos da v2 do lowpoly (estilos/lowpoly.js). O tempo casa com
    # o desenho: impacto e explosao batem em 0,6 da cena, quando o clarao sobe.
    "lowpoly": {"chuva_meteoros": [("whoosh", 0.1, 0.8), ("thud", 0.5, 0.8)], "tremor": [("tremido", 0.05, 1.0)],
                "para_de_girar": [("tremido", 0.35, 1.0)], "inunda": [("whoosh", 0.1, 0.6)], "cresce": [("boing", 0.2, 0.8)],
                "encolhe": [("pop", 0.3, 0.8)], "impacto": [("whoosh", 0.25, 1.0), ("thud", 0.6, 1.3), ("tremido", 0.62, 1.0)],
                "explode": [("thud", 0.55, 1.3), ("tremido", 0.57, 0.9)], "erupcao": [("tremido", 0.1, 1.0), ("thud", 0.3, 0.9)],
                "vento": [("whoosh", 0.05, 0.8), ("whoosh", 0.5, 0.7)], "congela": [("plim", 0.55, 0.8)],
                "seca": [("whoosh", 0.1, 0.5)], "brota": [("pop", 0.25, 0.6), ("pop", 0.45, 0.6), ("pop", 0.65, 0.6)],
                "gravidade_zero": [("whoosh", 0.1, 0.6)], "aurora": [("plim", 0.3, 0.6)], "amanhece": [("plim", 0.4, 0.6)],
                "derrete": [("gole", 0.5, 0.5)], "compara": [("pop", 0.3, 0.7)], "mostra": [("pop", 0.08, 0.5)]},
}
CPS_LEITURA = 14.0      # caracteres por segundo que alguem le no celular
PAUSA_NARRADO = 0.22    # respiro entre cenas narradas (a voz nao emenda)


def _formato(estilo):
    """A regra do estilo (`config.json > motor_web.estilos.<estilo>`)."""
    try:
        from config_gerado import MOTOR_WEB
        return dict((MOTOR_WEB.get("estilos") or {}).get(estilo) or {})
    except Exception as e:                           # noqa: BLE001
        print(f"[web] config_gerado sem motor_web ({e}); padroes do codigo")
        return {}


def _silencio(caminho, dur, sr=SFX.SR):
    with wave.open(caminho, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(dur * sr))
    return caminho


def linha_do_tempo(spec, tmp, modo_tts):
    """Duracao de cada cena e, nos narrados, a voz e as palavras."""
    cenas, t, palavras, faixas, respiros = spec["cenas"], 0.0, [], [], []
    narrado = bool(spec.get("narrado"))
    if narrado:
        from palito_v5 import sintetizar, juntar_com_respiro
        voz_cfg = dict(spec.get("voz") or {})
        for i, c in enumerate(cenas):
            texto = str(c.get("texto") or "").strip()
            wav = os.path.join(tmp, f"n{i}.wav")
            if texto:
                marcas, dur = sintetizar(texto, voz_cfg, wav, modo_tts)
            else:
                marcas, dur = [], float(c.get("dur_s") or 1.5)
                _silencio(wav, dur)
            for m in marcas or []:
                palavras.append({"palavra": m.get("palavra", ""), "ini": round(t + float(m["inicio_s"]), 3), "fim": round(t + float(m["fim_s"]), 3)})
            c["ini"], c["fim"] = round(t, 3), round(t + dur + PAUSA_NARRADO, 3)
            t = c["fim"]; faixas.append(wav); respiros.append(PAUSA_NARRADO)
        voz = juntar_com_respiro(faixas, respiros, os.path.join(tmp, "voz.wav"), tmp)
    else:
        for c in cenas:
            dur = float(c.get("dur_s") or 2.5)
            texto = str(c.get("texto") or "")
            if texto and (c.get("acao") == "cartela" or spec.get("estilo") == "pixel"):
                dur = max(dur, len(texto) / CPS_LEITURA + 1.0)
            c["ini"], c["fim"] = round(t, 3), round(t + dur, 3)
            t = c["fim"]
        voz = _silencio(os.path.join(tmp, "voz.wav"), t)
    spec["dur_s"] = round(t, 3)
    spec["palavras"] = palavras
    return voz


def eventos_sonoros(spec):
    ev = []
    por_acao = EFEITO_DA_ACAO.get(spec.get("estilo"), {})
    for c in spec["cenas"]:
        d = c["fim"] - c["ini"]
        for nome, frac, ganho in por_acao.get(c.get("acao_desenhada") or c.get("acao"), []):
            ev.append({"nome": nome, "t": c["ini"] + frac * d, "ganho": ganho})
        for nome in (c.get("sfx") or []):
            ev.append({"nome": nome, "t": c["ini"] + 0.05, "ganho": 0.9})
        # o "blip" de maquina de escrever do pixel: 1 a cada 3 letras
        if spec.get("estilo") == "pixel" and c.get("texto") and c.get("acao") != "batalha":
            for j in range(0, len(c["texto"]), 3):
                tt = c["ini"] + j / 32.0
                if tt < c["fim"]:
                    ev.append({"nome": "clique", "t": tt, "ganho": 0.35, "cadencia": True})
    return ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--modo-tts", default=os.environ.get("MODO_TTS", "real"))
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8-sig"))
    est = spec.get("estilo")
    fmt = _formato(est)
    spec.setdefault("w", 1080); spec.setdefault("h", 1920); spec.setdefault("fps", int(fmt.get("fps") or 30))
    spec.setdefault("narrado", bool(fmt.get("narrado")))
    tmp = tempfile.mkdtemp(prefix="web_")
    voz = linha_do_tempo(spec, tmp, a.modo_tts)
    print(f"[web] {est}: {len(spec['cenas'])} cenas, {spec['dur_s']:.1f} s, {'narrado' if spec['narrado'] else 'mudo'}")
    spec_render = os.path.join(tmp, "spec_render.json")
    json.dump(spec, open(spec_render, "w", encoding="utf-8"), ensure_ascii=False)
    mudo = os.path.join(tmp, "mudo.mp4")
    subprocess.run(["node", os.path.join(AQUI, "render_web.mjs"), "--spec", spec_render, "--saida", mudo], check=True)
    try:
        for c, a_ in zip(spec["cenas"], json.load(open(mudo + ".acoes.json", encoding="utf-8"))):
            if a_:
                c["acao_desenhada"] = a_
    except (OSError, ValueError):
        pass
    trilha = dict(fmt.get("trilha") or {})
    musica = dict(spec.get("musica") or {})
    for k, v in trilha.items():
        musica.setdefault(k, v)
    musica.setdefault("semente", spec.get("fila_id") or spec.get("semente") or "web")
    if not spec["narrado"]:
        musica.setdefault("ganho_db", -9)   # sem voz, a trilha e' a protagonista do som
    mix = SFX.mixar(voz, eventos_sonoros(spec), os.path.join(tmp, "mix.wav"), musica=musica, dur_s=spec["dur_s"])
    # LOUDNORM (22/10): o motor web saia sem normalizacao nenhuma -- cada video
    # num volume. -14 LUFS e' o alvo do YouTube (ele abaixa o que passa disso).
    # 48 kHz/192k: a cama de faixa real (`trilha_biblioteca`) tem brilho acima
    # de 12 kHz que a saida a 24 kHz cortava.
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", mudo, "-i", mix, "-c:v", "copy",
                    "-af", fmt.get("loudnorm") or "loudnorm=I=-14:LRA=11:TP=-1.5", "-ar", "48000",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", a.saida], check=True)
    json.dump(spec, open(os.path.splitext(a.saida)[0] + "_spec_render.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[web] ok {a.saida} ({spec['dur_s']:.1f} s)")


if __name__ == "__main__":
    main()
