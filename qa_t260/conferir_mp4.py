"""Verificação estrutural sem ffmpeg + sonda completa opcional no runner.

O parser estrutural não prova decodificação: aprovação exige o relatório do
runner vinculado por SHA-256 e a inspeção visual separada no recibo do canal.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
from .juiz_qualidade import comandos_audio, ler_audio, checar_audio


def caixas(dados):
    p = 0
    while p < len(dados):
        if len(dados) - p < 8:
            raise ValueError("caixa truncada")
        n, tipo = struct.unpack_from(">I4s", dados, p)
        header = 8
        if n == 1:
            if len(dados) - p < 16:
                raise ValueError("caixa estendida truncada")
            n = struct.unpack_from(">Q", dados, p + 8)[0]
            header = 16
        elif n == 0:
            n = len(dados) - p
        if n < header or p + n > len(dados):
            raise ValueError("tamanho invalido da caixa")
        yield tipo, dados[p + header:p + n]
        p += n


def unico(dados, tipo):
    encontrados = [d for t, d in caixas(dados) if t == tipo]
    if len(encontrados) != 1:
        raise ValueError("caixa ausente ou repetida: " + tipo.decode())
    return encontrados[0]


def estrutura(dados):
    unico(dados, b"ftyp")
    if not any(t == b"mdat" and len(d) for t, d in caixas(dados)):
        raise ValueError("mdat vazio")
    moov = unico(dados, b"moov")
    mvhd = unico(moov, b"mvhd")
    versao = mvhd[0]
    if versao not in (0, 1):
        raise ValueError("versao mvhd desconhecida")
    escala = struct.unpack_from(">I", mvhd, 20 if versao else 12)[0]
    dur = struct.unpack_from(">Q" if versao else ">I", mvhd, 24 if versao else 16)[0]
    if not escala or not dur:
        raise ValueError("duracao zero")
    trilhas = []
    for tipo, trak in caixas(moov):
        if tipo != b"trak":
            continue
        tk = unico(trak, b"tkhd")
        w, h = struct.unpack_from(">II", tk, len(tk) - 8)
        mdia = unico(trak, b"mdia")
        handler = unico(mdia, b"hdlr")[8:12]
        stsd = unico(unico(unico(mdia, b"minf"), b"stbl"), b"stsd")
        codecs = [t.decode("ascii") for t, _ in caixas(stsd[8:])]
        trilhas.append({"tipo": handler.decode("ascii"), "w": w / 65536, "h": h / 65536, "codecs": codecs})
    videos = [t for t in trilhas if t["tipo"] == "vide"]
    audios = [t for t in trilhas if t["tipo"] == "soun"]
    if len(videos) != 1 or len(audios) != 1:
        raise ValueError("exige uma trilha video e uma audio")
    v = videos[0]
    if (v["w"], v["h"]) != (1080, 1920) or "avc1" not in v["codecs"] or "mp4a" not in audios[0]["codecs"]:
        raise ValueError("exige h264/aac 1080x1920")
    return {"duracao_s": dur / escala, "trilhas": trilhas}


def conferir(dados, relatorio, dur_min=1, dur_max=180):
    erros = []
    e = {}
    try:
        e = estrutura(dados)
        if not dur_min <= e["duracao_s"] <= min(dur_max, 180):
            erros.append("duracao fora da faixa")
    except (ValueError, IndexError, struct.error, UnicodeError) as exc:
        erros.append(str(exc))
    r = relatorio or {}
    if r.get("sha256") != hashlib.sha256(dados).hexdigest():
        erros.append("relatorio nao corresponde ao MP4")
    if r.get("decode_ok") is not True:
        erros.append("decodificacao integral ausente ou falhou")
    if (r.get("video_codec"), r.get("audio_codec"), r.get("w"), r.get("h")) != ("h264", "aac", 1080, 1920):
        erros.append("ffprobe nao confirmou codecs/resolucao")
    for k, limite in (("preto_max_s", 1), ("congelado_max_s", 2)):
        n = r.get(k)
        if not isinstance(n, (float, int)) or not math.isfinite(n) or n < 0 or n > limite:
            erros.append(k + " ausente ou fora do limite")
    dur = r.get("duracao_s", 0)
    if not isinstance(dur, (float, int)) or not math.isfinite(dur) or not dur_min <= dur <= min(dur_max, 180):
        erros.append("duracao ffprobe invalida")
    elif e and abs(dur - e["duracao_s"]) > 0.2:
        erros.append("duracao estrutural diverge do ffprobe")
    a = r.get("audio") or {}
    if any(not isinstance(a.get(k), (int, float)) or not math.isfinite(a[k]) for k in ("lufs", "pico", "silencio_max")):
        erros.append("audio sem medicao completa")
    else:
        _, motivos = checar_audio(a)
        erros.extend(motivos)
    return {"aprovado": not erros, "erros": erros, "estrutura": e, "runner": r}


def sonda_runner(mp4, pasta, dur_min, dur_max):
    """Executada com ffmpeg/ffprobe no Actions; falhas não viram aprovação."""
    def rodar(cmd):
        return subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=900)
    d = Path(mp4).read_bytes()
    probe = json.loads(rodar(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(mp4)]).stdout)
    v = next(s for s in probe["streams"] if s["codec_type"] == "video")
    a = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    dec = rodar(["ffmpeg", "-v", "error", "-xerror", "-i", str(mp4), "-f", "null", "-"])
    eb, sil = comandos_audio(str(mp4))
    som = ler_audio(rodar(eb).stderr, rodar(sil).stderr)
    dur = float(probe["format"]["duration"])
    det = rodar(["ffmpeg", "-nostats", "-i", str(mp4), "-an", "-vf",
                 "blackdetect=d=0.1:pix_th=0.10,freezedetect=n=-60dB:d=0.1", "-f", "null", "-"]).stderr
    pretos = [float(x) for x in re.findall(r"black_duration:([0-9.]+)", det)]
    freezes = [float(x) for x in re.findall(r"freeze_duration: ([0-9.]+)", det)]
    # Detectores só imprimem duration quando o intervalo termina; cobrir cauda.
    for nome, lista in (("freeze", freezes), ("black", pretos)):
        starts = re.findall(nome + r"_start:\s*([0-9.]+)", det)
        ends = re.findall(nome + r"_end:\s*([0-9.]+)", det)
        if len(starts) > len(ends):
            lista.append(dur - float(starts[-1]))
    r = {"sha256": hashlib.sha256(d).hexdigest(), "decode_ok": not dec.stderr.strip(),
         "video_codec": v["codec_name"], "audio_codec": a["codec_name"], "w": v["width"], "h": v["height"],
         "duracao_s": dur, "audio": som, "preto_max_s": max(pretos, default=0),
         "congelado_max_s": max(freezes, default=0)}
    pasta = Path(pasta); pasta.mkdir(parents=True, exist_ok=True)
    quadros = []
    for n, frac in enumerate((0, .5, .9)):
        q = pasta / f"quadro{n}.jpg"
        rodar(["ffmpeg", "-y", "-v", "error", "-ss", str(dur * frac), "-i", str(mp4), "-frames:v", "1", str(q)])
        if not q.is_file() or not q.stat().st_size:
            raise ValueError("quadro nao extraido")
        quadros.append(str(q))
    resultado = conferir(d, r, dur_min, dur_max)
    resultado["quadros"] = quadros
    (pasta / "sonda.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2))
    return resultado
