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
# cairosvg e importado DENTRO de render_spec, nao aqui: ele exige libcairo
# do sistema, e palito_cutout importa deste modulo `sintetizar` e `envelope`
# -- duas funcoes de audio que nao tem nada com SVG. Com o import no topo,
# rodar o motor cut-out numa maquina sem libcairo era impossivel, e conferir
# frames antes de gastar 13 minutos de Action tambem.

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from palito_v4 import (W, H, OUT_W, OUT_H, FPS, REST, POSES, EXPRESSOES, merge, blend,
                       frame_svg, BG, TINTA)

SR = 24000


# =====================================================================
# 1. VOZ  — a etapa que define a timeline
# =====================================================================
_VOZES = None          # cache do catalogo real, buscado uma vez por processo


async def _catalogo_vozes():
    """Vozes que o servico REALMENTE oferece hoje.

    A Microsoft corta vozes do Edge sem aviso. Pedir uma que nao existe nao
    devolve erro: devolve um stream vazio, e o edge-tts levanta
    NoAudioReceived("verifique seus parametros") - mensagem que nao ajuda em
    nada. Foi assim que o primeiro render no GitHub morreu, pedindo
    pt-BR-FabioNeural."""
    global _VOZES
    if _VOZES is None:
        import edge_tts
        _VOZES = {v["ShortName"] for v in await edge_tts.list_voices()}
    return _VOZES


async def _resolver_voz(desejada):
    disp = await _catalogo_vozes()
    if desejada in disp:
        return desejada
    # A RESERVA E' DO MESMO LOCALE DA VOZ PEDIDA (12/09, segundo canal em
    # ingles): uma voz en-US que sumir do catalogo cai em outra en-US, nunca
    # em pt-BR -- video em ingles com voz de portugues e' pior que sem voz.
    locale = "-".join(str(desejada).split("-")[:2]) or "pt-BR"
    preferidas = {"pt-BR": ("pt-BR-AntonioNeural", "pt-BR-FranciscaNeural"),
                  "en-US": ("en-US-GuyNeural", "en-US-JennyNeural")}.get(locale, ())
    for alt in preferidas:
        if alt in disp:
            print(f"[voz] {desejada} indisponivel -> usando {alt}")
            return alt
    mesmo = sorted(v for v in disp if v.startswith(locale))
    if mesmo:
        print(f"[voz] {desejada} indisponivel -> usando {mesmo[0]}")
        return mesmo[0]
    raise RuntimeError(f"nenhuma voz {locale} disponivel no servico")


def _falar(edge_tts, texto, voz, cfg):
    """Communicate pedindo marca por PALAVRA.

    O edge-tts 7.x passou a mandar `sentenceBoundaryEnabled` por padrao: sem
    este kwarg o servico devolve UM SentenceBoundary por frase e nenhum
    WordBoundary, e o tempo de cada palavra -- que a legenda usa -- some.
    Conferido em 27/08 contra o servico real: 29 chunks de audio e um unico
    SentenceBoundary. Ninguem tinha percebido porque as marcas eram
    descartadas de qualquer jeito.

    O kwarg nao existe no edge-tts 6.x, e o requirements aceita >=6.1;
    entao se ele nao for aceito, segue sem -- a legenda cai no reparto
    proporcional em vez de o job inteiro morrer."""
    try:
        return edge_tts.Communicate(texto, voz, rate=cfg.get("rate", "+0%"),
                                    pitch=cfg.get("pitch", "+0Hz"),
                                    boundary="WordBoundary")
    except TypeError:
        print("[voz] edge-tts sem o parametro 'boundary'; sem marca de palavra")
        return edge_tts.Communicate(texto, voz, rate=cfg.get("rate", "+0%"),
                                    pitch=cfg.get("pitch", "+0Hz"))


async def _edge(texto, cfg, out_mp3, tentativas=3):
    import edge_tts
    voz = await _resolver_voz(cfg.get("voice", "pt-BR-AntonioNeural"))
    ultimo = None
    for n in range(tentativas):
        marcas, dur, bytes_audio = [], 0.0, 0
        try:
            c = _falar(edge_tts, texto, voz, cfg)
            with open(out_mp3, "wb") as f:
                async for ch in c.stream():
                    if ch["type"] == "audio":
                        f.write(ch["data"]); bytes_audio += len(ch["data"])
                    elif ch["type"] == "WordBoundary":
                        i0 = ch["offset"] / 1e7
                        i1 = i0 + ch["duration"] / 1e7
                        marcas.append({"palavra": ch["text"], "inicio_s": i0, "fim_s": i1})
                        dur = max(dur, i1)
            if bytes_audio > 0:
                return marcas, dur
            ultimo = "stream vazio"
        except Exception as e:
            ultimo = str(e)
        # o servico tambem falha por instabilidade; esperar e tentar de novo
        # resolve boa parte dos casos e custa segundos, nao um job inteiro
        print(f"[voz] tentativa {n+1}/{tentativas} falhou ({ultimo})")
        await asyncio.sleep(2 * (n + 1))
    raise RuntimeError(f"TTS falhou em {tentativas} tentativas com {voz}: {ultimo}")


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


def _duracao_wav(caminho):
    with wave.open(caminho) as w:
        return w.getnframes() / float(w.getframerate())


def silencio(caminho, dur_s, sr=SR):
    """Grava um WAV de silencio no MESMO formato das faixas de voz.

    Mesmo sample rate, mono, 16 bits: o concat do ffmpeg (demuxer) exige
    formato identico entre as partes, senao emenda errado ou recusa."""
    n = max(0, int(round(dur_s * sr)))
    with wave.open(caminho, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(b"\x00\x00" * n)
    return caminho


def juntar_com_respiro(faixas, respiros, destino, tmp, sr=SR):
    """Concatena as falas INSERINDO o respiro como silencio de verdade.

    POR QUE ISTO EXISTE (bug achado em 26/08, no run #13)
        O respiro sempre entrou na timeline de VIDEO -- `tr["dur"] = dur +
        respiro_s` -- e nunca no AUDIO, que era a concatenacao crua dos
        WAVs. O ffmpeg fecha o arquivo com `-shortest`, entao o fluxo mais
        curto (o audio) mandava: 3 x 0,45s = 1,35s de animacao renderizada
        e jogada fora, com a CAUDA DO ULTIMO TRECHO DECEPADA -- no teste, o
        `acenar` final simplesmente sumiu. Pior, `render()` devolvia a
        duracao COM respiro (15,25s) enquanto o arquivo tinha 13,88s, entao
        a guarda de duracao do job.py validava um numero que nao existia.

        O respiro existe para dar uma batida depois de cada fala. Uma batida
        e silencio: ele tem que estar no som tambem, e ai video e audio
        voltam a concordar sozinhos."""
    partes = []
    for i, faixa in enumerate(faixas):
        partes.append(faixa)
        r = float(respiros[i] if i < len(respiros) else 0.0)
        if r > 0.001:
            partes.append(silencio(os.path.join(tmp, f"resp{i:02d}.wav"), r, sr))
    lista = os.path.join(tmp, "a.txt")
    with open(lista, "w") as f:
        for p in partes:
            # o caminho vai entre aspas simples: apostrofo em nome de pasta
            # quebraria o demuxer, e o tmp costuma vir de tempfile
            f.write("file '%s'\n" % p.replace("'", "'\\''"))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                    "-i", lista, "-ar", str(sr), "-ac", "1", destino], check=True)
    return destino


def _palavras_do_alinhamento(texto, chars, ini, fim):
    """Marcas por PALAVRA a partir do alinhamento por CARACTERE.

    O ElevenLabs devolve tempo de cada caractere; a legenda (legendas.py)
    trabalha por palavra, no mesmo formato que o edge-tts entrega. Agrupar
    caractere em palavra e ficar com o primeiro início e o último fim de
    cada grupo dá exatamente a mesma coisa -- com resolução melhor, porque
    o alinhamento vem do áudio sintetizado e não de uma estimativa.

    Sem isto, trocar de motor de voz custava a legenda palavra a palavra
    (a de §6.5, que foi trabalho de uma sessão inteira): `_eleven` devolvia
    lista vazia e a legenda caía no reparto proporcional."""
    marcas, atual, t0, t1 = [], [], None, None
    for c, a, b in zip(chars, ini, fim):
        if str(c).strip() == "":
            if atual:
                marcas.append({"palavra": "".join(atual), "inicio_s": t0, "fim_s": t1})
                atual, t0, t1 = [], None, None
            continue
        atual.append(c)
        t0 = a if t0 is None else t0
        t1 = b
    if atual:
        marcas.append({"palavra": "".join(atual), "inicio_s": t0, "fim_s": t1})
    return marcas


def _chaves_eleven():
    """As contas ElevenLabs, NA ORDEM EM QUE DEVEM SER GASTAS (07/09).

    Ordem definida pelo dono: primeiro a conta 1, depois a 2, e por ultimo o
    Edge (que nao e' conta -- e' a queda gratuita, ja implementada abaixo).

    POR QUE A ORDEM IMPORTA E NAO E' ARBITRARIA: os creditos da ElevenLabs
    nao acumulam de um mes para o outro. Gastar sempre a mesma conta primeiro
    esvazia uma enquanto a outra expira sem uso; gastar a 1 ate secar e so
    entao a 2 aproveita as duas dentro do mes. Por isso a lista e' ordenada, e
    nao um rodizio -- rodizio deixaria as duas pela metade.

    A conta 1 esta sem credito desde 04/09, entao na pratica a 2 e' quem
    trabalha hoje; a 1 continua primeiro na fila porque ela volta a ter
    credito na virada do ciclo de cobranca dela.
    """
    chaves = []
    for var in ("ELEVEN_API_KEY", "ELEVEN_API_KEY_2"):
        v = (os.environ.get(var) or "").strip()
        if v and v not in chaves:
            chaves.append(v)
    return chaves


class PlanoNaoPermiteVoz(RuntimeError):
    """A conta autentica e tem credito -- a VOZ e' que e' de plano pago.

    ISTO NAO E' FALTA DE CREDITO, E CONFUNDIR OS DOIS CUSTOU 10/09 INTEIRO.
    O dono trocou a chave, o video continuou saindo no Edge, e a mensagem que
    o log mostrava falava de cota. A resposta de verdade era:

        HTTP 402  code: paid_plan_required
        "Free users cannot use library voices via the API."

    As onze vozes deste elenco sao BRASILEIRAS e vieram da BIBLIOTECA da
    ElevenLabs (voz compartilhada por outra pessoa). Conta Free enxerga essas
    vozes na lista -- conferido: `/v1/voices` devolve as 22, com a `Jerri` do
    `pal` entre elas -- e recusa sintetizar com elas. So as 21 `premade`
    funcionam, e todas sao americanas, britanicas ou australianas.

    POR QUE ISSO MERECE UMA EXCECAO PROPRIA E NAO SO UM `except`: o conserto e
    outro. Cota estourada espera o mes virar ou troca de conta; plano
    insuficiente NAO passa sozinho e nenhuma chave nova da mesma conta
    resolve. Sao US$ 6 (Starter) ou trocar de voz.
    """


def _eleven(texto, cfg, out_mp3, chave, voz=None):
    """ElevenLabs, com a chave que o chamador escolheu da fila.

    Por que ele existe: o Edge-TTS e o servico de leitura do navegador Edge,
    nao uma API publica -- os termos da Microsoft nao autorizam este uso.
    Antes de monetizar, precisa sair. E a voz e o item da stack em que a
    diferenca de qualidade e mais audivel: entonacao, respiracao e enfase
    no fim da frase, que e onde a piada aterrissa.

    No volume de 90 videos/mes (~36 mil caracteres) o Multilingual v2 sai por
    ~US$ 3,50/mes. E o maior ganho de qualidade percebida por dolar de toda a
    stack, e com folga.

    ENDPOINT COM TIMESTAMPS (28/08). Antes esta funcao chamava
    /text-to-speech/{voz}, que devolve so o audio, e voltava com `[]` de
    marcas -- ou seja, ligar o ElevenLabs DESLIGAVA a legenda por palavra.
    O endpoint /with-timestamps devolve o mesmo audio (em base64) mais o
    alinhamento por caractere, e sai pelo mesmo preco."""
    import base64, urllib.request, urllib.error
    if not chave:
        raise RuntimeError("sem chave ElevenLabs")
    voz = voz or cfg.get("eleven_voice_id") or os.environ.get("ELEVEN_VOICE_ID")
    if not voz:
        raise RuntimeError("defina ELEVEN_VOICE_ID ou eleven_voice_id no perfil de voz")
    corpo = json.dumps({
        "text": texto,
        "model_id": cfg.get("eleven_model", os.environ.get(
            "ELEVEN_MODEL", "eleven_multilingual_v2")),
        "voice_settings": {
            "stability": cfg.get("stability", 0.45),
            "similarity_boost": cfg.get("similarity", 0.8),
            "style": cfg.get("style", 0.35),
            "use_speaker_boost": True,
        },
    }).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voz}/with-timestamps",
        data=corpo, method="POST",
        headers={"xi-api-key": chave, "Content-Type": "application/json",
                 "Accept": "application/json"})
    # O MOTIVO DE VERDADE, E NAO SO O CODIGO HTTP (04/09).
    #
    # Em 03/09 as nove falas do v001 cairam para o Edge com
    # `HTTP Error 401: Unauthorized`, e o diagnostico foi "a chave nao tem
    # permissao de text-to-speech". Estava errado. O corpo da resposta dizia
    # outra coisa:
    #
    #     "code": "quota_exceeded"
    #     "You have 0 credits remaining, while 6 credits are required"
    #
    # A chave funciona, o endpoint funciona e a permissao existe -- **a conta
    # esta sem credito**. A ElevenLabs devolve 401 para cota estourada, e nao
    # 429, entao o codigo HTTP sozinho aponta para o lugar errado.
    #
    # `urlopen` levanta HTTPError e o `except` de quem chama imprime so o
    # `str(e)`, que e a linha de status. O corpo -- onde esta a resposta --
    # ia para o lixo. Ler o corpo custa tres linhas e teria poupado a sessao
    # inteira que foi gasta atras de uma permissao que nunca esteve faltando.
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detalhe = ""
        codigo = ""
        try:
            corpo_erro = json.loads(e.read().decode("utf-8", "replace"))
            d = corpo_erro.get("detail") or corpo_erro
            if isinstance(d, dict):
                codigo = str(d.get("code") or "")
                detalhe = f"{d.get('status') or d.get('code')}: {d.get('message')}"
            else:
                detalhe = str(d)[:200]
        except Exception:                                  # noqa: BLE001
            pass
        # DUAS RECUSAS QUE PARECEM UMA SO (10/09). Ver `PlanoNaoPermiteVoz`:
        # cota estourada e plano insuficiente chegam as duas como recusa da
        # conta, e o conserto de cada uma e' diferente. Separar aqui e' o que
        # permite a quem chama tentar OUTRA VOZ na mesma chave, em vez de
        # desistir da conta inteira e cair no Edge.
        if codigo == "paid_plan_required" or "library voices" in detalhe:
            raise PlanoNaoPermiteVoz(
                f"a voz {voz} e' da BIBLIOTECA e esta conta e' Free "
                f"({detalhe}). A conta esta viva e tem credito -- o que falta "
                f"e' plano. Saidas: assinar o Starter (US$ 6) para as vozes "
                f"brasileiras do elenco, ou pôr um `eleven_voice_id_free` "
                f"(voz `premade`) no perfil deste personagem.")
        raise RuntimeError(f"HTTP {e.code} -- {detalhe or 'sem detalhe no corpo'}")
    audio = base64.b64decode(resp.get("audio_base64") or "")
    if not audio:
        raise RuntimeError("ElevenLabs devolveu audio vazio")
    with open(out_mp3, "wb") as f:
        f.write(audio)

    al = resp.get("alignment") or resp.get("normalized_alignment") or {}
    marcas = _palavras_do_alinhamento(
        texto, al.get("characters") or [],
        al.get("character_start_times_seconds") or [],
        al.get("character_end_times_seconds") or [])
    print(f"[voz] eleven: {len(audio)/1024:.0f} KB, {len(marcas)} palavras alinhadas")
    return marcas

def _azure(texto, cfg, out_mp3):
    """Azure AI Speech -- o degrau PAGO entre a ElevenLabs e o Edge (09/09).

    ORDEM DO DONO, na sessao de custos: *"para as vozes mantenha o elevenlabs,
    e use o outro caso acabe"*. Ate aqui a cadeia tinha dois degraus e um
    buraco entre eles: ElevenLabs -> Edge. Quando o credito acabava -- e ele
    acabou em 04/09 e continua acabando -- o video caia direto na voz que o
    dono ja mandou corrigir duas vezes.

    POR QUE O AZURE, E NAO OUTRO
        Ele e o unico do levantamento que atende as tres exigencias ao mesmo
        tempo: tem MARCA POR PALAVRA nativa (`WordBoundary`), cobra POR
        CARACTERE em vez de assinatura, e tem vozes pt-BR de verdade. O
        volume deste canal e ridiculo para uma API de caractere -- 424
        caracteres por video, 38.160/mes a 3 videos/dia --, e isso cabe
        inteiro no free tier de 500 mil/mes. No pago seria ~US$ 0,84.

    A ARMADILHA QUE ESTA FUNCAO EXISTE PARA NAO CAIR
        O Edge-TTS **ja e** o Azure: sao as mesmas vozes neurais, pela porta
        lateral do navegador. Apontar para o Azure com o MESMO nome de voz
        nao melhora nada -- paga-se pelo que ja se tinha. Por isso:

          · sem `azure_voice` no perfil, esta funcao usa `cfg["voice"]` (a voz
            do Edge) e o ganho e de LICENCA, nao de qualidade: os termos da
            Microsoft nao autorizam o uso do endpoint do navegador, e isso
            precisa sair antes de monetizar;
          · com `azure_voice` apontando para uma voz HD/Multilingual, o ganho
            e de qualidade tambem.

        Qual voz HD existe na conta E DECISAO DE QUEM TEM A CONTA, e este
        codigo nao supoe nenhuma (lei 12): sem `azure_voice` nem `voice` no
        perfil, ele recusa e a cadeia segue para o Edge.

    O SDK E OPCIONAL DE PROPOSITO
        A marca por palavra so vem pelo evento `WordBoundary` do SDK -- o
        endpoint REST devolve audio e mais nada, e um TTS sem marca DESLIGA a
        legenda palavra a palavra e as `janelas_censuradas` do bipe (lei 17).
        Como o SDK e uma dependencia a mais no runner, a falta dele nao pode
        derrubar render nenhum: sem o pacote, isto levanta e a cadeia cai para
        o Edge, com o motivo no log.
    """
    chave = (os.environ.get("AZURE_SPEECH_KEY") or "").strip()
    regiao = (os.environ.get("AZURE_SPEECH_REGION") or "").strip()
    if not chave or not regiao:
        raise RuntimeError("sem AZURE_SPEECH_KEY/AZURE_SPEECH_REGION")
    voz = cfg.get("azure_voice") or cfg.get("voice")
    if not voz:
        raise RuntimeError("sem azure_voice nem voice no perfil")
    try:
        import azure.cognitiveservices.speech as fala
    except ImportError as e:                                   # noqa: BLE001
        raise RuntimeError(
            f"azure-cognitiveservices-speech nao esta instalado ({e}); "
            f"sem o SDK nao ha marca por palavra") from e

    sc = fala.SpeechConfig(subscription=chave, region=regiao)
    sc.set_speech_synthesis_output_format(
        fala.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3)
    # `rate` e `pitch` ja existem no perfil por causa do Edge, e a sintaxe e a
    # mesma -- o Edge-TTS os repassa para este mesmo motor.
    rate = cfg.get("rate") or "+0%"
    pitch = cfg.get("pitch") or "+0Hz"
    estilo = cfg.get("azure_estilo")
    miolo = (f"<prosody rate='{rate}' pitch='{pitch}'>"
             f"{_escapar_ssml(texto)}</prosody>")
    if estilo:
        miolo = (f"<mstts:express-as style='{estilo}'>{miolo}"
                 f"</mstts:express-as>")
    # o `xml:lang` e' o locale da VOZ (12/09): "en-US-GuyNeural" -> en-US.
    # Era pt-BR fixo, e uma voz inglesa num documento pt-BR sai com prosodia
    # de portugues.
    lang = "-".join(str(voz).split("-")[:2]) or "pt-BR"
    ssml = (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
        f"xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='{lang}'>"
        f"<voice name='{voz}'>{miolo}</voice></speak>")

    marcas_cruas = []

    def _palavra(evt):
        # `audio_offset` vem em ticks de 100 ns. `duration` e timedelta nas
        # versoes novas do SDK e nao existe nas antigas -- por isso o fim e
        # opcional aqui e se fecha embaixo, com o inicio do vizinho.
        dur = None
        try:
            d = getattr(evt, "duration", None)
            dur = d.total_seconds() if hasattr(d, "total_seconds") else (
                float(d) / 1e7 if d else None)
        except Exception:                                      # noqa: BLE001
            dur = None
        marcas_cruas.append({"palavra": evt.text,
                             "inicio_s": evt.audio_offset / 1e7,
                             "dur_s": dur})

    saida = fala.audio.AudioOutputConfig(filename=out_mp3)
    sintetizador = fala.SpeechSynthesizer(speech_config=sc, audio_config=saida)
    sintetizador.synthesis_word_boundary.connect(_palavra)
    r = sintetizador.speak_ssml_async(ssml).get()

    if r.reason != fala.ResultReason.SynthesizingAudioCompleted:
        # O MOTIVO DE VERDADE, E NAO SO O ENUM -- a mesma licao que o `_eleven`
        # aprendeu com o 401 que queria dizer "sem credito" (04/09).
        detalhe = ""
        try:
            c = r.cancellation_details
            detalhe = f"{c.reason}: {c.error_details}"
        except Exception:                                      # noqa: BLE001
            pass
        raise RuntimeError(f"Azure recusou -- {detalhe or r.reason}")
    if not os.path.exists(out_mp3) or os.path.getsize(out_mp3) < 512:
        raise RuntimeError("Azure devolveu audio vazio")

    # O FIM DE CADA PALAVRA: a duracao do SDK quando ela existe, senao o inicio
    # da proxima. A ultima fecha com a propria duracao ou com o inicio + 0,3 s,
    # que e chute -- mas chute na ULTIMA palavra so desloca o fim da legenda
    # do trecho, e o respiro cobre isso.
    marcas = []
    for i, m in enumerate(marcas_cruas):
        if m["dur_s"]:
            fim = m["inicio_s"] + m["dur_s"]
        elif i + 1 < len(marcas_cruas):
            fim = marcas_cruas[i + 1]["inicio_s"]
        else:
            fim = m["inicio_s"] + 0.3
        marcas.append({"palavra": m["palavra"], "inicio_s": m["inicio_s"],
                       "fim_s": fim})
    kb = os.path.getsize(out_mp3) / 1024
    print(f"[voz] azure ({voz}): {kb:.0f} KB, {len(marcas)} palavras alinhadas")
    return marcas


def _escapar_ssml(t):
    """SSML e XML: `&`, `<` e `>` no texto quebram a sintese inteira.

    A esquete deste canal e falada e cheia de `&` nao -- mas ela tem aspas,
    reticencias e, depois da lei 17, o texto passa por corte de palavrao. Uma
    fala com `<` derrubaria a chamada com um erro de parse que nao diz que o
    problema e o texto.
    """
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# QUEM FALOU COM QUAL MOTOR, CONTADO (03/09, item 6 do dono do projeto:
# *"garanta que estamos usando as vozes do ElevenLabs na producao"*).
#
# A queda para o Edge sempre existiu e sempre avisou -- no log do Action, que
# ninguem le. Um video inteiro pode sair com a voz errada e o unico lugar que
# sabe disso e uma linha perdida em 2.000. Aqui a queda vira DADO: o motor de
# cada fala e' contado, `palito_cutout` imprime o placar depois da timeline, e
# `job.py` o carrega para o registro da volta.
#
# A queda continua sendo queda e nao erro fatal: perder 13 minutos de render
# por causa de uma fala e' pior que um video com uma voz trocada. O que muda e'
# que agora da para SABER.
USOU_MOTOR = {}


def placar_de_voz():
    """O que foi usado, e o que foi pedido. Zera o contador."""
    d = dict(USOU_MOTOR)
    USOU_MOTOR.clear()
    return d


def sintetizar(texto, cfg, destino, modo):
    if modo == "real":
        mp3 = destino + ".mp3"
        # OPT-IN: so troca de motor se a chave existir. Sem ela, segue no
        # Edge-TTS -- que ja funciona. Ninguem quer descobrir num domingo que
        # a producao parou porque o motor de voz mudou sozinho.
        # ESCOLHA EXPLICITA DE MOTOR.
        #
        # Antes bastava a chave existir no ambiente para o ElevenLabs
        # assumir. Parecia razoavel e derrubou o render de 20/08: a chave
        # estava configurada, mas nenhum voice_id -- o _eleven levantou
        # excecao e o video saiu sem voz de verdade. "Ter a chave" nao e a
        # mesma coisa que "estar configurado para usar".
        #
        # Agora o motor e escolhido no perfil de voz (cfg["motor"]), o
        # padrao e o Edge (gratuito, vozes pt-BR reais, e ainda devolve
        # marcas de palavra que o lipsync usa), e faltar voice_id no meio
        # da producao faz cair para o Edge com aviso em vez de derrubar o
        # job inteiro.
        motor = (cfg.get("motor") or os.environ.get("MOTOR_TTS") or "edge").lower()
        marcas = None
        if motor in ("eleven", "elevenlabs"):
            tem_voz = cfg.get("eleven_voice_id") or os.environ.get("ELEVEN_VOICE_ID")
            chaves = _chaves_eleven()
            # A VOZ PAGA E' SO DE PRODUCAO (07/09, ordem do dono: "garanta que
            # nao sera usada para testes, apenas producao").
            #
            # `PRODUCAO` e' escrito pelo `job.py` a partir do fila_id: render
            # de teste tem id que nao e' uuid, e ali a voz cai no Edge. Sem
            # esta guarda, cada disparo de `disparar_render.py` -- que existe
            # para conferir movimento, junta e enquadramento, coisas que a voz
            # nao muda -- gastaria credito de uma conta que nao acumula mes a
            # mes. O teste continua saindo com voz; so nao com a voz cara.
            if os.environ.get("PRODUCAO") != "1":
                print("[voz] render de TESTE: a voz paga fica de fora, "
                      "usando o Edge (ver PRODUCAO no job.py)")
            elif not chaves:
                print("[voz] motor 'eleven' pedido mas nao ha ELEVEN_API_KEY "
                      "nem ELEVEN_API_KEY_2; usando o Edge")
            elif not tem_voz:
                print("[voz] motor 'eleven' pedido mas falta voice_id; usando o Edge")
            else:
                # A FILA DE CONTAS, NA ORDEM. Cada uma so e' abandonada depois
                # de responder erro -- e o motivo vai no log, porque "401" da
                # ElevenLabs quer dizer cota estourada e nao permissao (ver o
                # comentario dentro de `_eleven`).
                for i, ch in enumerate(chaves, 1):
                    try:
                        marcas = _eleven(texto, cfg, mp3, ch)
                        if i > 1:
                            print(f"[voz] conta ElevenLabs {i} atendeu "
                                  f"(a {i - 1} recusou)")
                        break
                    except PlanoNaoPermiteVoz as e:
                        # A CONTA SERVE, A VOZ E' QUE NAO (10/09). Desistir
                        # dela aqui seria jogar fora uma conta VIVA por causa
                        # de um voice_id -- e foi assim que 10/09 leu "Free
                        # users cannot use library voices" como falta de
                        # credito e caiu no Edge com credito na mao.
                        alt = cfg.get("eleven_voice_id_free")
                        if not alt:
                            print(f"[voz] conta ElevenLabs {i}: {e}")
                            print(f"[voz] sem `eleven_voice_id_free` no perfil "
                                  f"deste personagem; nao ha voz alternativa "
                                  f"para tentar nesta conta")
                        else:
                            try:
                                marcas = _eleven(texto, cfg, mp3, ch, voz=alt)
                                print(f"[voz] conta {i}: a voz do elenco e' de "
                                      f"plano pago; gravado com a voz "
                                      f"alternativa {alt}")
                                break
                            except Exception as e2:            # noqa: BLE001
                                print(f"[voz] conta {i}: a voz alternativa "
                                      f"{alt} tambem recusou ({e2})")
                        resta = len(chaves) - i
                        if resta:
                            print(f"[voz] tentando a conta {i + 1}")
                    except Exception as e:                     # noqa: BLE001
                        resta = len(chaves) - i
                        print(f"[voz] conta ElevenLabs {i} falhou ({e})"
                              + (f"; tentando a {i + 1}" if resta
                                 else "; caindo para o degrau seguinte"))

        # O DEGRAU DO MEIO: AZURE (09/09, ordem do dono -- *"para as vozes
        # mantenha o elevenlabs, e use o outro caso acabe"*).
        #
        # Ate aqui a cadeia era ElevenLabs -> Edge, e a queda ia direto da voz
        # cara para a voz que o dono ja mandou corrigir duas vezes. O Azure
        # entra ENTRE as duas: cobra por caractere (e os 38 mil/mes deste
        # canal cabem no free tier), tem marca por palavra nativa, e nao e
        # assinatura -- que e o que tornava a ElevenLabs cara neste volume.
        #
        # Ele nao substitui a ElevenLabs: ela continua sendo a primeira, por
        # ordem do dono e porque a voz dela e' o maior ganho de qualidade por
        # dolar da stack. O Azure existe para o dia em que o credito acaba, e
        # esse dia ja aconteceu.
        #
        # E' OPT-IN pelo mesmo motivo de todo o resto deste bloco: sem chave,
        # sem regiao ou sem SDK, ele levanta e a cadeia segue -- ninguem
        # descobre num domingo que a producao parou porque um degrau novo
        # apareceu.
        # QUEM ATENDEU SE GUARDA NUMA VARIAVEL, e nao se deduz de `marcas`.
        # Com dois motores dava para inferir ("tem marca? entao foi o caro");
        # com tres a inferencia deixa de existir, e placar errado e pior que
        # placar nenhum -- ele foi feito justamente para o dono saber com que
        # voz o video saiu (03/09).
        usou = "eleven" if marcas is not None else None

        if marcas is None and motor != "edge" and os.environ.get("AZURE_SPEECH_KEY"):
            if os.environ.get("PRODUCAO") != "1":
                print("[voz] render de TESTE: o Azure tambem fica de fora")
            else:
                try:
                    marcas = _azure(texto, cfg, mp3)
                    usou = "azure"
                    print("[voz] o Azure atendeu (a ElevenLabs nao)")
                except Exception as e:                         # noqa: BLE001
                    print(f"[voz] Azure falhou ({e}); caindo para o Edge")

        if marcas is None:
            usou = "edge"
            marcas, _ = asyncio.run(_edge(texto, cfg, mp3))
        USOU_MOTOR[f"pedido_{motor}"] = USOU_MOTOR.get(f"pedido_{motor}", 0) + 1
        USOU_MOTOR[f"usou_{usou}"] = USOU_MOTOR.get(f"usou_{usou}", 0) + 1
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3,
                        "-ar", str(SR), "-ac", "1", destino], check=True)
        # A duracao vem do ARQUIVO, nao das marcas de palavra.
        # As marcas sao opcionais: o edge-tts as vezes devolve audio sem
        # nenhum WordBoundary, e ai a timeline saia zerada -- foi o que
        # produziu um video de 1,7s no lugar de 20s. O arquivo nunca mente.
        dur = _duracao_wav(destino)
        if dur <= 0.05:
            raise RuntimeError(f"TTS devolveu audio vazio para: {texto[:40]!r}")
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
    faixas, respiros, total = [], [], 0.0
    for i, tr in enumerate(spec["trechos"]):
        wav = os.path.join(tmp, f"v{i:02d}.wav")
        cfg = vozes.get(tr.get("perfil_voz", "narrador"), {})
        marcas, dur = sintetizar(tr["fala"], cfg, wav, modo)
        respiro = float(tr.get("respiro_s", 0.45))
        dur += respiro
        tr["dur"] = dur                      # <<< SAÍDA do TTS, nunca entrada
        faixas.append(wav)
        respiros.append(respiro)
        total += dur
        print(f"  trecho {i}: {dur:5.2f}s  {len(marcas):2d} palavras  \"{tr['fala'][:44]}\"")
    print(f"[voz] timeline real: {total:.2f}s")

    # ---- 3.2 áudio concatenado + envoltória ---------------------------
    # com o respiro DENTRO do audio: sem ele, o -shortest do fim decepava a
    # cauda de cada trecho renderizado (ver juntar_com_respiro)
    voz = juntar_com_respiro(faixas, respiros, os.path.join(tmp, "voz.wav"), tmp)
    env = envelope(voz)

    # ---- 3.3 fundos gerados por IA (opcional) -------------------------
    # spec["fundos"] = {"sala": "https://.../sala.png", "mesa": "..."}
    # Baixados UMA vez por cenario e reutilizados em todos os frames: um
    # cenario e ativo permanente do canal, nao custo por video. Sem esta
    # chave, o rig desenha o fundo por codigo, como antes.
    import cairosvg              # so aqui: exige libcairo do sistema
    fundos = {}
    for nome, url in (spec.get("fundos") or {}).items():
        try:
            import urllib.request
            from PIL import Image
            tmp_bg = os.path.join(tmp, f"bg_{nome}.png")
            urllib.request.urlretrieve(url, tmp_bg)
            fundos[nome] = (Image.open(tmp_bg).convert("RGBA")
                            .resize((OUT_W, OUT_H), Image.LANCZOS))
            print(f"[fundo] {nome}: {url[:60]}")
        except Exception as e:
            # fundo e melhoria, nao requisito: falhar aqui nao pode custar o video
            print(f"[fundo] {nome} falhou ({e}); usando o cenario do rig")

    # ---- 3.3 frames, com a boca seguindo o áudio ----------------------
    n = 0
    for tr in spec["trechos"]:
        # .get com padrao, como em palito_cutout._rig_do_trecho: o spec novo
        # descreve movimento por `acoes` e nao traz mais `pose`/`expressao`.
        # Indexar direto fazia o rig vetorial -- que e a REDE DE SEGURANCA --
        # morrer de KeyError justamente quando era a ultima chance de sair
        # video. Sem pose declarada o boneco fica parado, que e o certo.
        _pose = tr.get("pose", "parado_falando")
        _expr = tr.get("expressao", "neutro")
        p1 = merge(REST, POSES.get(_pose, {}), EXPRESSOES.get(_expr, {}))
        p2 = merge(REST, POSES.get(tr.get("pose_saida", _pose), {}), EXPRESSOES.get(_expr, {}))
        dois = tr.get("quem") == "ab"
        if dois:
            p1, p2 = merge(p1, {"dx": -230}), merge(p2, {"dx": -230})
            sec = merge(REST, POSES.get(tr.get("pose_b", "parado_falando"), {}),
                        EXPRESSOES.get(tr.get("expressao_b", "neutro"), {}),
                        {"dx": 250, "cabeca_r": 112, "boca": 0.18})
        for f in range(max(1, int(tr["dur"] * FPS))):
            fh = (f // 2) * 2
            t = fh / max(1, int(tr["dur"] * FPS) - 1)
            rig = blend(p1, p2, t * t * (3 - 2 * t))
            rig["boca"] = 0.10 + 0.62 * (env[n] if n < len(env) else 0.0)   # <<< áudio real
            rig["quadril"] = [rig["quadril"][0], rig["quadril"][1] + math.sin(f * 0.13) * 6]
            rigs = [(rig, "#5A6B7A")] + ([(dict(sec), "#8C5F52")] if dois else [])
            cen = tr.get("cenario", "sala")
            bg = fundos.get(cen)
            destino = os.path.join(fd, f"{n:05d}.png")
            svg = frame_svg(rigs, fh // 2, cen, fundo_raster=bg is not None).encode()
            if bg is None:
                cairosvg.svg2png(bytestring=svg, write_to=destino,
                                 output_width=OUT_W, output_height=OUT_H)
            else:
                # SVG sai transparente e e colado SOBRE a imagem de fundo.
                # Compor no PIL em vez de embutir <image> no SVG: o cairosvg
                # degrada raster embutido (banding no ceu e em gradientes),
                # e aqui o fundo passa intacto.
                from io import BytesIO
                from PIL import Image
                png = cairosvg.svg2png(bytestring=svg, output_width=OUT_W,
                                       output_height=OUT_H)
                quadro = bg.copy()
                quadro.alpha_composite(Image.open(BytesIO(png)).convert("RGBA"))
                quadro.convert("RGB").save(destino)
            n += 1
    print(f"[rig] {n} frames ({n/FPS:.1f}s)")

    # ---- 3.4 trilha + loudnorm ---------------------------------------
    # A REDE DE SEGURANÇA TEM QUE SEGURAR (29/08). `musica` virou um DICT
    # em 28/08 (`{genero, ganho_db}`, sintetizada no próprio render) e este
    # caminho continuou esperando um CAMINHO DE ARQUIVO. Enquanto o cut-out
    # funcionou ninguém passou por aqui; no dia em que ele falhou, o job caiu
    # no rig vetorial e o vetorial quebrou com `TypeError: expected str...
    # not dict` -- ou seja, a queda para a rede de segurança custou o vídeo,
    # que é exatamente o que ela existe para evitar.
    #
    # Aqui o vetor não sintetiza trilha: ele toca uma se o spec der uma URL,
    # e segue sem música se não der. Vídeo sem trilha é pior que vídeo com
    # trilha; vídeo nenhum é pior que os dois.
    mus = spec.get("musica")
    if isinstance(mus, dict):
        mus = mus.get("url") or mus.get("arquivo")
        if not mus:
            print("[musica] o rig vetorial nao sintetiza trilha; seguindo sem ela")
    mix = voz
    if mus and isinstance(mus, str):
        mix = os.path.join(tmp, "mix.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", voz, "-i", mus,
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
