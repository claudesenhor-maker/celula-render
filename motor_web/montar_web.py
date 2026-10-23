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
                "encolhe": [("pop", 0.3, 0.8)], "impacto": [("whoosh", 0.25, 1.0), ("explosao", 0.6, 1.2), ("tremido", 0.62, 0.8)],
                "explode": [("explosao", 0.55, 1.2), ("tremido", 0.57, 0.7)], "erupcao": [("tremido", 0.1, 1.0), ("explosao", 0.3, 0.6)],
                "vento": [("whoosh", 0.05, 0.8), ("whoosh", 0.5, 0.7)], "congela": [("plim", 0.55, 0.8)],
                "seca": [("whoosh", 0.1, 0.5)], "brota": [("pop", 0.25, 0.6), ("pop", 0.45, 0.6), ("pop", 0.65, 0.6)],
                "gravidade_zero": [("whoosh", 0.1, 0.6)], "aurora": [("plim", 0.3, 0.6)], "amanhece": [("plim", 0.4, 0.6)],
                "derrete": [("gole", 0.5, 0.5)], "compara": [("pop", 0.3, 0.7)], "mostra": [("pop", 0.08, 0.5)]},
    # 22/10: "como funciona" (estilos/mecanismo.js)
    "mecanismo": {"explode": [("whoosh", 0.05, 0.8), ("tecido", 0.1, 0.5)], "monta": [("metal", 0.4, 0.7), ("clique", 0.55, 0.8)],
                  "corte": [("whoosh", 0.05, 0.6)], "destaque": [("plim", 0.15, 0.6)], "gira": [("motor", 0.05, 0.45)],
                  "move": [("metal", 0.3, 0.7), ("clique", 0.8, 0.8)], "fluxo": [("whoosh", 0.1, 0.5)]},
    # 22/10: comparacao de escala (estilos/escala.js): a camera recua a cada cena
    "escala": {"compara": [("whoosh", 0.02, 0.7), ("plim", 0.4, 0.5)]},
    # 22/10: quiz "ache o diferente" (estilos/quiz.js); o tique por segundo vem
    # de `eventos_sonoros`, a resposta (1,3 s antes do fim do nivel) aqui
    "quiz": {},
    # 23/10: historia em mapa (estilos/mapa.js): a camera viaja, paises acendem,
    # rotas e setas andam, alfinetes caem, o ano conta
    "mapa": {"mostra": [("whoosh", 0.02, 0.5)], "destaca": [("pop", 0.18, 0.6), ("pop", 0.32, 0.5)],
             "rota": [("whoosh", 0.12, 0.6), ("clique", 0.82, 0.6)], "avanca": [("whoosh", 0.08, 0.9), ("thud", 0.62, 0.7)],
             "marca": [("pop", 0.22, 0.7), ("pop", 0.5, 0.6)], "ano": [("clique", 0.02, 0.8), ("plim", 0.9, 0.5)]},
    # 23/10: ficha de animal (estilos/animal.js) e linha do tempo (estilos/linha_tempo.js)
    "animal": {"mostra": [("whoosh", 0.03, 0.4)], "stat": [("pop", 0.08, 0.6), ("plim", 0.62, 0.6)], "compara": [("pop", 0.2, 0.6)],
               "corre": [("whoosh", 0.05, 0.9), ("whoosh", 0.45, 0.7)], "ataca": [("whoosh", 0.2, 0.9), ("thud", 0.42, 1.2), ("tremido", 0.44, 0.7)]},
    "linha_tempo": {"marco": [("whoosh", 0.05, 0.5), ("pop", 0.36, 0.7)], "salto": [("whoosh", 0.02, 0.9), ("pop", 0.36, 0.7)],
                    "zoom": [("whoosh", 0.05, 0.5), ("plim", 0.4, 0.8)]},
    # 23/10: Sistema Solar com dados reais (estilos/orbita.js, ORBIT DAILY)
    "orbita": {"sistema": [("whoosh", 0.03, 0.5)], "foco": [("whoosh", 0.03, 0.5), ("plim", 0.2, 0.6)], "dia": [("whoosh", 0.03, 0.4), ("plim", 0.92, 0.7)],
               "compara": [("pop", 0.12, 0.6), ("thud", 0.42, 0.6)], "orbita": [("whoosh", 0.05, 0.6), ("plim", 0.95, 0.6)],
               "viagem": [("whoosh", 0.06, 0.9), ("whoosh", 0.4, 0.7), ("pop", 0.58, 0.7)]},
}
# O PERFIL DE EFEITOS de cada estilo (sfx.PERFIL, 22/10): o acervo gravado
# que o canal usa. Pixel soa 8-bit; quiz, relogio; o resto, o mundo real.
PERFIL_SFX = {"pixel": "pixel", "quiz": "quiz"}


def camas_de_ambiente(spec):
    """[(ini, fim, tipo)]: o som do LUGAR de cada cena (sfx.ambiente).

    So' os estilos com lugar: o low-poly (pela acao e pelo cenario), a
    silhueta (clima, hora e lugar) e os estudios 3D (um tom de sala, para nao
    haver silencio digital entre as falas). Pixel, quiz, fisica e mangueira
    tem som proprio e ficam sem cama."""
    est, out = spec.get("estilo"), []
    for c in spec["cenas"]:
        a, cen, obj, hora = c.get("acao_desenhada") or c.get("acao"), c.get("cenario"), c.get("objeto"), c.get("hora")
        tipo = None
        if est == "lowpoly":
            tipo = ({"chove": "chuva", "vento": "vento", "incendio": "fogo", "erupcao": "fogo", "inunda": "mar", "seca": "vento",
                     "noite_eterna": "grilos", "aurora": "grilos", "derrete": "mar", "estiagem": "vento", "sem_ar": "vento"}.get(a)
                    or {"oceano": "mar", "praia": "mar", "cidade": "cidade", "espaco": "espaco", "planeta": "espaco", "polo": "vento",
                        "deserto": "vento", "montanha": "vento", "vulcao": "fogo", "floresta": "vento", "campo": "vento"}.get(cen))
            if hora == "noite" and tipo not in ("chuva", "fogo", "espaco"):
                tipo = "grilos"
        elif est == "silhueta":
            tipo = ({"chuva": "chuva", "raio": "chuva", "neve": "vento", "fogueira": "fogo", "vagalumes": "grilos", "nevoa": "vento"}.get(obj)
                    or ("grilos" if hora == "noite" else None)
                    or {"mar": "mar", "farol": "mar", "cidade": "cidade", "vila": "cidade", "estrada": "vento"}.get(cen) or "vento")
        elif est in ("mecanismo",):
            tipo = "sala"
        elif est == "escala":
            tipo = "vento"
        if tipo and c.get("fim") is not None:
            out.append((c["ini"], c["fim"] + 0.4, tipo))
    return out


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


def _aparar_inicio(wav, marcas, folga=0.03):
    """Corta o silencio que a voz traz ANTES da 1a palavra (23/10, retencao: o
    TTS abre com 0,2-0,5 s de nada, e na cena 1 isso e' o gancho mudo enquanto
    o feed decide). Usa a marca da 1a palavra; sem marcas, nao mexe."""
    if not marcas:
        return marcas, None
    ini = float(marcas[0].get("inicio_s", 0))
    if ini <= folga + 0.06:
        return marcas, None
    corte = ini - folga
    with wave.open(wav) as w:
        p, sr, n = w.getparams(), w.getframerate(), w.getnframes()
        w.setpos(min(n, int(corte * sr)))
        resto = w.readframes(n)
    with wave.open(wav, "wb") as o:
        o.setparams(p)
        o.writeframes(resto)
    novas = [dict(m, inicio_s=max(0.0, float(m["inicio_s"]) - corte), fim_s=max(0.0, float(m["fim_s"]) - corte)) for m in marcas]
    with wave.open(wav) as w:
        return novas, w.getnframes() / float(w.getframerate())


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
                try:
                    if wav.endswith(".wav") and os.path.exists(wav):
                        marcas, d2 = _aparar_inicio(wav, marcas)
                        if d2:
                            print(f"[voz] cena {i}: {dur - d2:.2f} s de silencio cortados antes da 1a palavra")
                            dur = d2
                except Exception as e:                       # noqa: BLE001 -- aparar e' bonus, nunca derruba
                    print(f"[voz] cena {i}: nao aparei o inicio ({e})")
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


def _notas(eventos, dur_s, destino, sr=SFX.SR):
    """As batidas da simulacao (estilos/fisica.js) viram MUSICA: uma nota de
    timbre de marimba/sino por batida, na altura que a simulacao mandou (a
    melodia do spec, em ciclo). E' a trilha desses videos -- o nicho vive disso."""
    import numpy as np
    n = int((dur_s + 1.0) * sr)
    x = np.zeros(n, dtype=np.float32)
    tt = np.arange(int(0.9 * sr)) / sr
    for e in eventos:
        i = int(float(e.get("t", 0)) * sr)
        if i >= n:
            continue
        f0 = 440.0 * 2 ** ((float(e.get("nota", 72)) - 69) / 12.0)
        env = np.exp(-tt * (5.5 if not e.get("forte") else 2.5))
        tom = (np.sin(2 * np.pi * f0 * tt) + 0.35 * np.sin(2 * np.pi * f0 * 2.01 * tt) + 0.12 * np.sin(2 * np.pi * f0 * 3.98 * tt)) * env
        g = 0.32 if e.get("forte") else 0.22
        m = min(len(tom), n - i)
        x[i:i + m] += (tom[:m] * g).astype(np.float32)
    pico = float(np.max(np.abs(x))) if len(x) else 0.0
    if pico > 0.95:
        x = np.tanh(x * 1.2) / np.tanh(1.2) * 0.95
    with wave.open(destino, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32000).astype("<i2").tobytes())
    return destino


def eventos_sonoros(spec):
    ev = []
    por_acao = EFEITO_DA_ACAO.get(spec.get("estilo"), {})
    for c in spec["cenas"]:
        d = c["fim"] - c["ini"]
        for nome, frac, ganho in por_acao.get(c.get("acao_desenhada") or c.get("acao"), []):
            ev.append({"nome": nome, "t": c["ini"] + frac * d, "ganho": ganho})
        for nome in (c.get("sfx") or []):
            ev.append({"nome": nome, "t": c["ini"] + 0.05, "ganho": 0.9})
        # quiz: um tique por segundo do cronometro e o "plim" da resposta
        if spec.get("estilo") == "quiz":
            fim_relogio = c["fim"] - 1.3
            tt = c["ini"] + 0.35
            while tt < fim_relogio:
                ev.append({"nome": "clique", "t": tt, "ganho": 0.6, "cadencia": True})
                tt += 1.0
            ev.append({"nome": "plim", "t": fim_relogio + 0.05, "ganho": 1.0})
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
    # a simulacao fisica entrega as batidas: elas sao a "voz" (o som principal)
    try:
        som = json.load(open(mudo + ".som.json", encoding="utf-8"))
        if som:
            voz = _notas(som, spec["dur_s"], os.path.join(tmp, "notas.wav"))
            print(f"[web] {len(som)} batidas viraram notas")
    except (OSError, ValueError):
        pass
    trilha = dict(fmt.get("trilha") or {})
    musica = dict(spec.get("musica") or {})
    for k, v in trilha.items():
        musica.setdefault(k, v)
    musica.setdefault("semente", spec.get("fila_id") or spec.get("semente") or "web")
    # CANAL SERIO (23/10): a trava de `sfx.genero_permitido` existe para a
    # comedia (trilha dramatica embaixo de piada). Canal de historia, animal ou
    # linha do tempo declara `trilha.registro: "serio"` no estilo e toca o
    # epico/suspense que pediu, sem fingir ironia.
    if str(musica.pop("registro", "") or "").lower() == "serio":
        musica["ironia"] = True
    if not spec["narrado"]:
        musica.setdefault("ganho_db", -9)   # sem voz, a trilha e' a protagonista do som
    if fmt.get("sem_trilha"):
        musica = None                       # fisica: as notas das batidas SAO a trilha
    SFX.PERFIL = PERFIL_SFX.get(est, "padrao")
    mix = SFX.mixar(voz, eventos_sonoros(spec), os.path.join(tmp, "mix.wav"), musica=musica, dur_s=spec["dur_s"],
                    camas=camas_de_ambiente(spec))
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
