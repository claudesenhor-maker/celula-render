"""Juiz de qualidade antes da Publicação (T203, Q1): ninguém publica sem nota.

Duas portas no mesmo ponto: (1) juiz = agente da VM, com 6-8 quadros-chave do MP4 e o
roteiro, nota 1-10 em cinco critérios; (2) checagem de áudio (ebur128 + silencedetect).
Média < 7 ou áudio reprovado -> refazer (no máximo 2 vezes), depois descarta com motivo.
Sem nota válida nunca publica.
"""

from __future__ import annotations

import json
import re

CRITERIOS = ("gancho", "clareza", "desfecho", "imagem", "variacao")
MEDIA_MINIMA = 7.0
MAX_REFEITURAS = 2
LUFS_MIN, LUFS_MAX = -16.0, -12.0
SILENCIO_MAX_S = 1.5
PICO_MAX_DBTP = -1.0


def comandos_audio(mp4: str) -> tuple[list[str], list[str]]:
    """(ebur128 com true peak, silencedetect); a saída de ambos vem no stderr do ffmpeg."""
    base = ["ffmpeg", "-nostats", "-i", mp4, "-vn", "-af"]
    return (base + ["ebur128=peak=true", "-f", "null", "-"],
            base + [f"silencedetect=noise=-40dB:d={SILENCIO_MAX_S}", "-f", "null", "-"])


def ler_audio(saida_ebur128: str, saida_silencio: str) -> dict:
    """Extrai lufs, pico (dBTP) e maior silêncio (s); campo ausente fica fora do dict."""
    m = {}
    resumo = (saida_ebur128 or "").split("Summary:")[-1]
    achou = re.search(r"\bI:\s*(-?\d+(?:\.\d+)?)\s*LUFS", resumo)
    if achou:
        m["lufs"] = float(achou.group(1))
    achou = re.search(r"\bPeak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", resumo)
    if achou:
        m["pico"] = float(achou.group(1))
    if m:
        duracoes = [float(x) for x in re.findall(r"silence_duration:\s*(\d+(?:\.\d+)?)", saida_silencio or "")]
        m["silencio_max"] = max(duracoes, default=0.0)
    return m


def checar_audio(m: dict) -> tuple[bool, list[str]]:
    """Reprova loudness fora de -16..-12 LUFS, silêncio > 1,5 s ou pico > -1 dBTP."""
    if not m or "lufs" not in m or "pico" not in m:
        return False, ["áudio sem medição"]
    motivos = []
    if not LUFS_MIN <= m["lufs"] <= LUFS_MAX:
        motivos.append(f"loudness {m['lufs']} LUFS fora de {LUFS_MIN:g}..{LUFS_MAX:g}")
    if m.get("silencio_max", 0) > SILENCIO_MAX_S:
        motivos.append(f"silêncio de {m['silencio_max']} s > {SILENCIO_MAX_S} s")
    if m["pico"] > PICO_MAX_DBTP:
        motivos.append(f"pico {m['pico']} dBTP > {PICO_MAX_DBTP:g}")
    return not motivos, motivos


def instantes_quadros(duracao: float, n: int = 7) -> list[float]:
    """n (6-8) instantes em segundos; o primeiro é 0 (o gancho do 1º segundo)."""
    n = max(6, min(8, n))
    passo = duracao / n
    return [round(i * passo, 2) for i in range(n)]


def montar_prompt(titulo: str, frases: list[str], recentes: list[str]) -> str:
    roteiro = "\n".join(f"{i + 1}. {f}" for i, f in enumerate(frases))
    ultimos = "\n".join(f"- {t}" for t in recentes) or "- (nenhum)"
    return (
        "Você é o juiz de qualidade de um Short. Vê 6 a 8 quadros-chave do vídeo (em ordem; "
        "o primeiro é o 1º segundo) e o roteiro. Dê nota inteira de 1 a 10 em: "
        "gancho (o 1º segundo prende?), clareza, desfecho (há payoff?), "
        "imagem (combina com a frase?), variacao (difere dos últimos 20 do canal?).\n"
        f"Título: {titulo}\nRoteiro:\n{roteiro}\nÚltimos do canal:\n{ultimos}\n"
        'Responda só JSON: {"gancho":n,"clareza":n,"desfecho":n,"imagem":n,"variacao":n,"motivo":"uma frase"}'
    )


def ler_nota(texto: str) -> dict:
    """Valida a resposta do juiz: cinco notas inteiras 1-10; devolve notas, média e motivo."""
    corpo = re.sub(r"^```(?:json)?|```$", "", (texto or "").strip(), flags=re.M).strip()
    dados = json.loads(corpo)
    if not isinstance(dados, dict):
        raise ValueError("resposta do juiz não é objeto")
    nota = {}
    for c in CRITERIOS:
        v = dados.get(c)
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 10:
            raise ValueError(f"nota inválida em {c}: {v!r}")
        nota[c] = v
    nota["media"] = round(sum(nota[c] for c in CRITERIOS) / len(CRITERIOS), 2)
    nota["motivo"] = str(dados.get("motivo") or "")[:500]
    return nota


def decidir(media, audio_ok: bool, motivos_audio: list[str], refeituras: int) -> dict:
    """acao = publicar | refazer | descartar; `refeituras` = quantas vezes já voltou."""
    motivos = []
    if media is None:
        motivos.append("sem nota do juiz")
    elif media < MEDIA_MINIMA:
        motivos.append(f"média {media} < {MEDIA_MINIMA:g}")
    if not audio_ok:
        motivos.extend(motivos_audio or ["áudio reprovado"])
    if not motivos:
        return {"acao": "publicar", "motivo": f"média {media}, áudio ok"}
    if refeituras >= MAX_REFEITURAS:
        return {"acao": "descartar", "motivo": f"descartado após {MAX_REFEITURAS} refeituras: " + "; ".join(motivos)}
    return {"acao": "refazer", "motivo": "; ".join(motivos)}


def linha_notas_video(fila_id, cell_id, motor, nota: dict, audio: dict, decisao: dict, refeituras: int) -> dict:
    return {
        "fila_id": fila_id, "cell_id": cell_id, "motor": motor,
        "notas": {c: nota[c] for c in CRITERIOS}, "media": nota["media"],
        "audio": audio, "acao": decisao["acao"],
        "motivo": decisao["motivo"] if decisao["acao"] != "publicar" else (nota.get("motivo") or decisao["motivo"]),
        "tentativa": refeituras + 1,
    }
