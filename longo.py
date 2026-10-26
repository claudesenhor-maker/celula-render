"""Montagem do vídeo longo B05 (T210): Shorts escolhidos + contextos novos em 16:9 1920×1080.

Só biblioteca padrão. O mesmo arquivo é copiado como `longo.py` no repo celula-render, onde o
`job.py` o chama quando `spec.tipo == "longo"`. Rede, ffmpeg e voz entram por parâmetro, então
os testes rodam sem nada disso.
"""

import json
import re
import subprocess
from pathlib import Path

LARGURA, ALTURA = 1920, 1080
DURACAO_MIN_S, DURACAO_MAX_S = 480, 900
FRACAO_CONTEXTO_MIN = 0.5
LUFS_ALVO = -14
FPS = 30
VOZ_PADRAO = {"pt-BR": {"motor": "edge", "voice": "pt-BR-AntonioNeural"},
              "en-US": {"motor": "edge", "voice": "en-US-GuyNeural"}}


class ErroLongo(ValueError):
    """Spec ou montagem do longo recusada."""


def validar_spec(spec):
    if not isinstance(spec, dict) or spec.get("tipo") != "longo":
        raise ErroLongo("spec.tipo deve ser 'longo'")
    shorts, contextos = spec.get("shorts"), spec.get("contextos")
    if not shorts or not isinstance(shorts, list):
        raise ErroLongo("spec sem shorts")
    if not isinstance(contextos, list) or len(contextos) != len(shorts):
        raise ErroLongo("é preciso um contexto novo por Short")
    for i, s in enumerate(shorts, 1):
        if not str(s.get("video_url") or "").startswith("http"):
            raise ErroLongo(f"short {i} sem video_url")
        try:
            ok = float(s.get("duracao_s")) > 0
        except (TypeError, ValueError):
            ok = False
        if not ok:
            raise ErroLongo(f"short {i} sem duração positiva")
    for i, c in enumerate(contextos, 1):
        if not str(c.get("texto") or "").strip():
            raise ErroLongo(f"contexto {i} sem texto")
    return spec


def planejar_tempos(duracoes_short, duracoes_contexto):
    """Alterna Short e contexto; recusa fora de 480–900 s ou com menos de 50% de contexto."""
    segmentos = []
    for i, (s, c) in enumerate(zip(duracoes_short, duracoes_contexto)):
        segmentos.append({"tipo": "short", "indice": i, "dur": float(s)})
        segmentos.append({"tipo": "contexto", "indice": i, "dur": float(c)})
    total = sum(s["dur"] for s in segmentos)
    if not DURACAO_MIN_S <= total <= DURACAO_MAX_S:
        raise ErroLongo(f"duração {total:.0f} s fora de {DURACAO_MIN_S}-{DURACAO_MAX_S} s")
    if fracao_contexto(segmentos) < FRACAO_CONTEXTO_MIN:
        raise ErroLongo(f"contexto novo é {fracao_contexto(segmentos):.0%} do tempo (mínimo 50%)")
    return segmentos


def fracao_contexto(segmentos):
    total = sum(s["dur"] for s in segmentos)
    return sum(s["dur"] for s in segmentos if s["tipo"] == "contexto") / total if total else 0.0


def timestamp(segundos):
    s = int(round(segundos))
    h, resto = divmod(s, 3600)
    m, s = divmod(resto, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def capitulos(segmentos, titulos):
    """[(início em s, título)], um por Short+contexto; o primeiro começa em 0."""
    marcas, t = [], 0.0
    for seg in segmentos:
        if seg["tipo"] == "short":
            marcas.append((int(round(t)), titulos[seg["indice"]]))
        t += seg["dur"]
    return marcas


def formatar_capitulos(marcas):
    return "\n".join(f"{timestamp(t)} {titulo}" for t, titulo in marcas)


def _fundo_desfocado():
    return (f"[0:v]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
            f"crop={LARGURA}:{ALTURA},boxblur=40:5,setsar=1[bg]")


def cmd_short(entrada, saida, tem_audio=True):
    """Short vertical no centro (altura cheia) sobre o próprio vídeo desfocado."""
    grafo = (_fundo_desfocado() + f";[0:v]scale=-2:{ALTURA}:force_original_aspect_ratio=decrease,setsar=1[fg];"
             f"[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={FPS},format=yuv420p[v];"
              f"[{0 if tem_audio else 1}:a]aresample=48000,aformat=channel_layouts=stereo[a]")
    silencio = [] if tem_audio else ['-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo']
    return ["ffmpeg", "-y", "-v", "error", "-i", entrada, *silencio, "-filter_complex", grafo,
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
              "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", saida]


def _escapar_drawtext(caminho):
    return str(caminho).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def dividir_legenda(texto, duracao_s):
    """Frases com tempo proporcional às palavras: [(início, fim, frase)]."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?…])\s+", texto.strip()) if f.strip()]
    pedacos = []
    for f in frases:  # frase longa vira pedaços de até 12 palavras
        p = f.split()
        pedacos += [" ".join(p[i:i + 12]) for i in range(0, len(p), 12)]
    total = sum(len(p.split()) for p in pedacos) or 1
    saida, t = [], 0.0
    for i, p in enumerate(pedacos):
        fim = duracao_s if i == len(pedacos) - 1 else t + duracao_s * len(p.split()) / total
        saida.append((round(t, 3), round(fim, 3), p))
        t = fim
    return saida


def cmd_cartaz(arquivo_titulo, saida, fonte):
    """Cartaz de reserva (sem imagem): fundo liso + título."""
    desenho = (f"drawtext=fontfile='{_escapar_drawtext(fonte)}':textfile='{_escapar_drawtext(arquivo_titulo)}':"
               "fontcolor=white:fontsize=84:x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.4:boxborderw=30")
    return ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
            f"color=c=0x1d2b53:s={LARGURA}x{ALTURA}:d=1", "-vf", desenho, "-frames:v", "1", saida]


def cmd_contexto(imagem, audio, saida, duracao_s, legendas, fonte):
    """Imagem/cartaz em tela cheia sobre fundo desfocado, legenda por frase e a voz nova."""
    partes = [f"[0:v]split[a][b]", f"[a]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
              f"crop={LARGURA}:{ALTURA},boxblur=40:5[bg]",
              f"[b]scale={LARGURA}:{ALTURA - 220}:force_original_aspect_ratio=decrease[fg]",
              "[bg][fg]overlay=(W-w)/2:60[c0]"]
    atual = "c0"
    for i, (ini, fim, arq) in enumerate(legendas):
        prox = f"c{i + 1}"
        partes.append(
            f"[{atual}]drawtext=fontfile='{_escapar_drawtext(fonte)}':textfile='{_escapar_drawtext(arq)}':"
            "fontcolor=white:fontsize=46:x=(w-text_w)/2:y=h-150:box=1:boxcolor=black@0.6:boxborderw=14:"
            f"enable='between(t,{ini:.3f},{fim:.3f})'[{prox}]")
        atual = prox
    partes.append(f"[{atual}]fps={FPS},setsar=1,format=yuv420p[v]")
    return ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", imagem, "-i", audio,
            "-filter_complex", ";".join(partes), "-map", "[v]", "-map", "1:a",
            "-af", "aresample=48000,aformat=channel_layouts=stereo",
            "-t", f"{duracao_s:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", saida]


def filtro_loudnorm(medidas=None):
    base = f"loudnorm=I={LUFS_ALVO}:TP=-1.5:LRA=11"
    if not medidas:
        return base + ":print_format=json"
    return (base + f":measured_I={medidas['input_i']}:measured_TP={medidas['input_tp']}:"
            f"measured_LRA={medidas['input_lra']}:measured_thresh={medidas['input_thresh']}:"
            f"offset={medidas['target_offset']}:linear=true")


def parse_loudnorm(stderr):
    achado = re.search(r"\{[^{}]*\}", stderr or "", re.S)
    if not achado:
        raise ErroLongo("loudnorm não devolveu medidas")
    try:
        return json.loads(re.sub(r",\s*}", "}", achado.group(0)))
    except ValueError:
        raise ErroLongo("medidas do loudnorm ilegíveis") from None


def lista_concat(arquivos):
    return "".join("file '" + str(a).replace("'", "'\\''") + "'\n" for a in arquivos)


def validar_saida(info):
    if (info.get("largura"), info.get("altura")) != (LARGURA, ALTURA):
        raise ErroLongo(f"saída {info.get('largura')}x{info.get('altura')}, esperado {LARGURA}x{ALTURA}")
    if not DURACAO_MIN_S <= float(info.get("duracao_s") or 0) <= DURACAO_MAX_S:
        raise ErroLongo(f"duração final {info.get('duracao_s')} s fora de {DURACAO_MIN_S}-{DURACAO_MAX_S} s")
    return info


def sondar(caminho, run=subprocess.run):
    """ffprobe → {largura, altura, duracao_s}."""
    r = run(["ffprobe", "-v", "error", "-show_entries",
              "stream=codec_type,width,height,display_aspect_ratio:format=duration", "-of", "json", str(caminho)],
            capture_output=True, text=True, check=True)
    dados = json.loads(r.stdout)
    fluxo = next(s for s in dados['streams'] if s['codec_type'] == 'video')
    return {"largura": fluxo["width"], "altura": fluxo["height"], "duracao_s": float(dados["format"]["duration"]),
            "aspecto": fluxo.get('display_aspect_ratio'),
            "tem_audio": any(s['codec_type'] == 'audio' for s in dados['streams'])}


def executar(spec, pasta, run=subprocess.run, baixar=None, sintetizar=None, sondar=sondar,
             fonte="DejaVuSans.ttf", duracoes_short=None, medir_shorts=False):
    """Baixa os Shorts, sintetiza os contextos, monta e normaliza. Devolve o recibo.

    `sintetizar(texto, cfg_voz, destino_wav) -> duração em s`; `baixar(url, destino)`.
    `medir_shorts=True` usa a duração real (ffprobe) dos MP4 baixados em vez da do spec.
    """
    validar_spec(spec)
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    cfg_voz = spec.get("voz") or VOZ_PADRAO.get(spec.get("idioma"), VOZ_PADRAO["pt-BR"])
    shorts, contextos = spec["shorts"], spec["contextos"]
    brutos = []
    for i, s in enumerate(shorts):
        bruto = pasta / f"short{i}.mp4"
        baixar(s["video_url"], str(bruto))
        brutos.append(bruto)
    infos = [sondar(str(b)) for b in brutos] if medir_shorts else []
    if medir_shorts:  # a duração real do MP4 manda, não a do spec
        dur_short = [float(info["duracao_s"]) for info in infos]
    else:
        dur_short = list(duracoes_short or [float(s["duracao_s"]) for s in shorts])
    dur_ctx, wavs = [], []
    for i, c in enumerate(contextos):
        wav = pasta / f"ctx{i}.wav"
        dur_ctx.append(float(sintetizar(c["texto"].strip(), cfg_voz, str(wav))))
        wavs.append(wav)
    segmentos = planejar_tempos(dur_short, dur_ctx)

    partes = []
    for seg in segmentos:
        i = seg["indice"]
        saida = pasta / f"p{len(partes):02d}_{seg['tipo']}.mp4"
        if seg["tipo"] == "short":
            run(cmd_short(str(brutos[i]), str(saida), tem_audio=infos[i].get('tem_audio', True) if infos else True),
                check=True, capture_output=True, text=True)
        else:
            c = contextos[i]
            imagem = pasta / f"img{i}.png"
            if c.get("imagem_url"):
                baixar(c["imagem_url"], str(imagem))
            else:
                titulo = pasta / f"titulo{i}.txt"
                titulo.write_text(c.get("titulo") or shorts[i].get("titulo") or "", encoding="utf-8")
                run(cmd_cartaz(str(titulo), str(imagem), fonte), check=True, capture_output=True, text=True)
            legendas = []
            for k, (ini, fim, frase) in enumerate(dividir_legenda(c["texto"], seg["dur"])):
                arq = pasta / f"leg{i}_{k}.txt"
                arq.write_text(frase, encoding="utf-8")
                legendas.append((ini, fim, str(arq)))
            run(cmd_contexto(str(imagem), str(wavs[i]), str(saida), seg["dur"], legendas, fonte),
                check=True, capture_output=True, text=True)
        partes.append(saida)

    lista = pasta / "lista.txt"
    lista.write_text(lista_concat(partes), encoding="utf-8")
    juntado = pasta / "juntado.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", str(juntado)],
        check=True, capture_output=True, text=True)
    medida = run(["ffmpeg", "-y", "-hide_banner", "-i", str(juntado), "-af", filtro_loudnorm(),
                  "-vn", "-f", "null", "-"], check=True, capture_output=True, text=True)
    final = pasta / "longo.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(juntado), "-af", filtro_loudnorm(parse_loudnorm(medida.stderr)),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", str(final)],
        check=True, capture_output=True, text=True)
    info = validar_saida(sondar(str(final)))
    marcas = capitulos(segmentos, [s.get("titulo") or f"Caso {i + 1}" for i, s in enumerate(shorts)])
    return {"saida": str(final), "duracao_s": info["duracao_s"], "largura": info["largura"],
            "altura": info["altura"], "fracao_contexto": fracao_contexto(segmentos),
            "capitulos": marcas, "descricao": formatar_capitulos(marcas), "lufs_alvo": LUFS_ALVO}


def _achar_fonte(pasta_repo):
    for ext in ("*.ttf", "*.otf"):
        achadas = sorted(Path(pasta_repo, "fontes").glob(ext))
        if achadas:
            return str(achadas[0])
    return "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def conferir_piloto(spec, fila_id, job, pasta, sondar=sondar):
    """ffprobe do piloto existente no runner; só publica um recibo JSON no Storage."""
    prefixo = f'{job.SB}/storage/v1/object/public/{job.BUCKET}/longos/'
    url = spec.get('verificar_piloto_url') or ''
    if (spec.get('piloto') is not True or job.UUID_RE.match(str(fila_id))
        or not re.fullmatch(r'[\w-]{1,80}', str(fila_id)) or not url.startswith(prefixo)
        or not re.fullmatch(r'[\w-]+\.mp4', url[len(prefixo):])):
        raise ErroLongo('sonda exclusiva de piloto existente no Storage do projeto')
    r = job.requests.get(url, timeout=300)
    r.raise_for_status()
    entrada = Path(pasta) / 'piloto.mp4'
    entrada.write_bytes(r.content)
    info = validar_saida(sondar(str(entrada)))
    if not info.get('tem_audio') or info.get('aspecto') != '16:9':
        raise ErroLongo('piloto sem áudio ou aspecto diferente de 16:9')
    info = dict(info, piloto_url=url, origem='ffprobe', publicou=False)
    recibo = Path(pasta) / 'sonda.json'
    recibo.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding='utf-8')
    sonda_url = job.subir(str(recibo), f'longos/sonda-{fila_id}.json', 'application/json')
    job.avisar(dict(info, fila_id=fila_id, status='ok', sonda_url=sonda_url, piloto=True))
    return info


def rodar(spec, fila_id, t0, job, montar=None):
    """Caminho `spec.tipo == "longo"` do job.py (celula-render).

    `job` é o módulo job.py (subir, atualizar_fila, avisar, UUID_RE, requests). Item de produção
    (fila_id uuid, sem `piloto`) volta à fila como `pronto_para_publicar`; piloto só sobe o MP4
    em `longos/` e avisa — nunca toca na fila nem publica.
    """
    import os
    import tempfile
    import time
    eh_producao = bool(job.UUID_RE.match(str(fila_id))) and not spec.get("piloto")
    os.environ["PRODUCAO"] = "1" if eh_producao else "0"
    cfg = spec.get("voz")
    if isinstance(cfg, dict) and not eh_producao and str(cfg.get("motor", "")).lower() in ("eleven", "elevenlabs"):
        cfg["motor"] = "edge"   # voz paga é só do canal em produção

    def baixar(url, destino):
        r = job.requests.get(url, timeout=300)
        r.raise_for_status()
        Path(destino).write_bytes(r.content)

    def sintetizar(texto, cfg_voz, destino):
        import palito_v5
        return palito_v5.sintetizar(texto, cfg_voz, destino, os.environ.get("MODO_TTS", "real"))[1]

    pasta = tempfile.mkdtemp(prefix="longo_")
    if spec.get('verificar_piloto_url'):
        return conferir_piloto(spec, fila_id, job, pasta)
    if montar is None:
        repo = os.path.dirname(os.path.abspath(getattr(job, "__file__", ".")))
        recibo = executar(spec, pasta, baixar=baixar, sintetizar=sintetizar,
                          fonte=_achar_fonte(repo), medir_shorts=True)
    else:
        recibo = montar(spec, pasta)
    url = job.subir(recibo["saida"], f"longos/{fila_id}.mp4")
    print(f"[ok] longo {url}  {recibo['duracao_s']:.0f}s  render={time.time() - t0:.0f}s")
    if eh_producao:
        # O Dispatcher só pode ver pronto junto com os capítulos medidos pelo TTS.
        roteiro = {"tipo": "longo", "formato": "16:9", "titulo": spec.get('titulo', ''),
                   "playlist": spec.get('playlist', ''), "idioma": spec.get('idioma', 'pt-BR'),
                   "narracao": '\n'.join(c['texto'] for c in spec['contextos']),
                   "descricao": recibo['descricao'], "capitulos": recibo['capitulos'],
                   "duracao_s": recibo['duracao_s'], "fracao_contexto": recibo['fracao_contexto'],
                   "spec_longo": spec}
        job.atualizar_fila(fila_id, {"status": "pronto_para_publicar", "video_url": url,
                                   "roteiro_json": roteiro, "atualizado_em": "now()"})
    job.avisar({"fila_id": fila_id, "status": "ok", "tipo": "longo", "video_url": url,
                "duracao_s": recibo["duracao_s"], "largura": recibo["largura"], "altura": recibo["altura"],
                "fracao_contexto": recibo["fracao_contexto"], "lufs": recibo["lufs_alvo"],
                "capitulos": recibo["capitulos"], "descricao": recibo["descricao"],
                "piloto": bool(spec.get("piloto")), "render_s": round(time.time() - t0)})
    return recibo
