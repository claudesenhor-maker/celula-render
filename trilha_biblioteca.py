#!/usr/bin/env python3
"""
trilha_biblioteca -- trilha de VERDADE no lugar da sintetizada (22/10).

POR QUE
    22/10, ordem do dono: "em todos os canais nosso maior ponto fraco e' a
    trilha sonora". A trilha padrao e' `sfx.trilha`: osciladores de numpy a
    24 kHz (sem nada acima de 12 kHz), timbres de seno com envelope. Funciona
    como chao, mas o ouvido reconhece na hora que nao e' instrumento -- e o
    conjunto soa "feito por IA" mesmo com a voz boa.

    Aqui a trilha passa a ser uma FAIXA gravada/gerada de verdade, escolhida
    pelo genero que o roteiro ja pede (`musica.genero`), com a mesma semente
    por video (dois videos do mesmo genero nao saem com a mesma faixa no
    mesmo trecho). Sem faixa para o genero, `sfx.mixar` cai na sintetizada de
    sempre: a biblioteca so' acrescenta.

ONDE AS FAIXAS MORAM (a primeira que tiver o genero vence)
    1. `trilhas/<genero>/*.mp3|ogg|wav|flac` no proprio repo do render (vem no
       checkout; nada a baixar);
    2. `toonzueira/trilhas/<genero>/` no Storage do Supabase (listado com a
       chave de servico que o Action ja tem).

    Licenca: so' entra faixa que pode ir para canal MONETIZADO sem Content ID
    -- gerada por modelo aberto de licenca comercial (ACE-Step, Apache 2.0) ou
    de dominio publico/CC0. O nome do arquivo nao importa; `LICENCAS.md` na
    pasta registra a origem de cada lote.

O QUE ESTE MODULO FAZ COM A FAIXA
    - escolhe pela semente; comeca num ponto que varia por video (sem pegar a
      introducao vazia de toda faixa) e da' a volta (loop com cruzamento);
    - normaliza pelo RMS (faixas de lotes diferentes entram no mesmo nivel);
    - `cavar_voz`: tira ~4 dB da faixa entre 1 e 4 kHz, onde mora a
      inteligibilidade da fala -- a trilha pode ficar mais alta sem brigar com
      a voz (o mesmo que um mixador faz com EQ, aqui estatico).
"""
import hashlib
import json
import os
import subprocess
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.join(AQUI, "trilhas")
EXT = (".mp3", ".ogg", ".wav", ".flac", ".m4a")
SR_FAIXA = 48000
RMS_ALVO_DB = -14.0

# genero do roteiro sem pasta propria -> o mais proximo que tiver
PARENTES = {
    "comedia_leve": ["leve", "circo", "lofi"], "leve": ["comedia_leve", "lofi"], "espera": ["lofi", "comedia_leve"],
    "lofi": ["leve", "comedia_leve"], "circo": ["comedia_leve", "ragtime"], "samba": ["funk", "comedia_leve"],
    "funk": ["trap", "samba"], "suspense": ["misterio", "terror"], "misterio": ["suspense"], "terror": ["suspense"],
    "epico": ["aventura", "suspense"], "aventura": ["epico"], "novela": ["suspense", "epico"], "rock": ["epico", "funk"],
    "trap": ["funk"], "ragtime": ["circo", "comedia_leve"], "chiptune": ["leve"],
}


def _sem(s):
    return int(hashlib.sha1(str(s).encode("utf-8")).hexdigest()[:8], 16)


def _locais(genero):
    d = os.path.join(PASTA, genero)
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(EXT))


def _remotas(genero):
    sb, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_SERVICE_KEY")
    bucket = os.environ.get("SUPABASE_BUCKET", "toonzueira")
    if not sb or not key:
        return []
    corpo = json.dumps({"prefix": f"trilhas/{genero}", "limit": 200, "offset": 0,
                        "sortBy": {"column": "name", "order": "asc"}}).encode()
    req = urllib.request.Request(f"{sb}/storage/v1/object/list/{bucket}", data=corpo, method="POST",
                                 headers={"Authorization": f"Bearer {key}", "apikey": key,
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            itens = json.loads(r.read().decode())
    except Exception as e:                                       # noqa: BLE001
        print(f"[trilha] listagem do bucket falhou ({e})")
        return []
    return [f"{sb}/storage/v1/object/public/{bucket}/trilhas/{genero}/{i['name']}"
            for i in itens if str(i.get("name", "")).lower().endswith(EXT)]


def candidatas(genero):
    """As faixas do genero (ou do parente mais proximo que tiver alguma)."""
    for g in [genero] + PARENTES.get(genero, []):
        if not g:
            continue
        fs = _locais(g) or _remotas(g)
        if fs:
            return g, fs
    return None, []


def faixa_para(genero, semente, dur_s, destino, sr=SR_FAIXA):
    """Grava em `destino` (WAV mono `sr`) uma faixa do genero cobrindo `dur_s`.

    Devolve (caminho, rotulo) ou (None, motivo). Nunca levanta: trilha real e'
    melhoria; sem ela o mixador usa a sintetizada."""
    try:
        g, fs = candidatas(str(genero or "").strip().lower())
        if not fs:
            return None, f"sem faixa para '{genero}'"
        h = _sem(semente)
        esc = fs[h % len(fs)]
        origem = esc
        if esc.startswith("http"):
            bruto = destino + ".baixado"
            urllib.request.urlretrieve(esc, bruto)
            origem = bruto
        # ponto de entrada: 0 a 25% da faixa, pela semente (sem a mesma
        # introducao em todo video); `-stream_loop -1` da' a volta se faltar
        total = _duracao(origem)
        ini = 0.0 if total < dur_s * 1.4 else ((h >> 8) % 1000) / 1000.0 * min(total * 0.25, max(0.0, total - dur_s))
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-ss", f"{ini:.2f}", "-i", origem,
                        "-t", f"{dur_s + 0.5:.2f}", "-ac", "1", "-ar", str(sr), "-af", "afade=t=in:d=0.25",
                        destino], check=True)
        return destino, f"{g}/{os.path.basename(esc.split('?')[0])} a partir de {ini:.1f}s"
    except Exception as e:                                       # noqa: BLE001
        return None, f"falhou ({type(e).__name__}: {e})"


def _duracao(caminho):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                            "default=nw=1:nk=1", caminho], capture_output=True, text=True, check=True)
        return float(r.stdout.strip() or 0)
    except Exception:                                            # noqa: BLE001
        return 0.0


def normalizar(x):
    """Mesmo nivel para toda faixa: RMS em RMS_ALVO_DB (picos limitados depois)."""
    import numpy as np
    rms = float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0
    if rms < 1e-5:
        return x
    return (x * (10 ** (RMS_ALVO_DB / 20.0) / rms)).astype(np.float32)


def cavar_voz(x, sr, ganho_db=-4.0, f1=1000.0, f2=4000.0):
    """Abre na faixa o espaco da fala: `ganho_db` entre f1 e f2 (bordas suaves)."""
    import numpy as np
    n = len(x)
    if n < 2048:
        return x
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1.0 / sr)
    lo, hi = np.log2(f1), np.log2(f2)
    lf = np.log2(np.maximum(f, 1.0))
    # meia oitava de rampa de cada lado
    peso = np.clip(np.minimum((lf - (lo - 0.5)) / 0.5, ((hi + 0.5) - lf) / 0.5), 0.0, 1.0)
    X *= 10 ** (ganho_db * peso / 20.0)
    return np.fft.irfft(X, n).astype(np.float32)
