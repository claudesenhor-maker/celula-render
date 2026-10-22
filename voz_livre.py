#!/usr/bin/env python3
"""
voz_livre -- vozes de CODIGO ABERTO, gratis, geradas no proprio runner (22/10).

POR QUE ISTO EXISTE
    22/10, ordem do dono: "em todos os canais nosso maior ponto fraco e' a
    trilha sonora e a voz de IA". Oito dos dez canais saem com o Edge (a voz
    que o dono ja mandou corrigir duas vezes por soar robotica) e o PAPERCUT
    cai nele quando o credito da ElevenLabs acaba. Este modulo poe no meio da
    cadeia dois motores abertos, de repositorios conhecidos, que rodam na CPU
    do Action sem chave nem conta:

      chatterbox  Resemble AI, licenca MIT (uso comercial livre). Clona a voz
                  de um trecho de referencia de ~10 s (zero-shot), tem controle
                  de EMOCAO (`exaggeration`) e fala 23 linguas, portugues
                  incluso. Nos testes cegos da Resemble ele foi preferido a
                  ElevenLabs. E' o motor padrao daqui.
      kokoro      hexgrad/Kokoro-82M, licenca Apache 2.0. 82 M de parametros:
                  roda varias vezes mais rapido que o tempo real numa CPU, voz
                  limpa de narrador (ingles muito bom; portugues razoavel). E'
                  o degrau rapido e tambem o FABRICANTE DA REFERENCIA do
                  chatterbox quando o canal nao tem uma (ver `_referencia`).

    Motores que NAO entram, e por que (licenca de pesos nao-comercial; os
    canais sao monetizados): F5-TTS (CC-BY-NC), XTTS-v2 (CPML), Fish-Speech
    (CC-BY-NC-SA), MusicGen. Nada aqui imita a voz de uma pessoa real: a
    referencia padrao e' uma voz SINTETICA do Kokoro; `ref_url` no perfil
    troca por uma gravacao propria (do dono ou de alguem que autorizou).

AS TRES EXIGENCIAS DA CADEIA DE VOZ (memoria do projeto, 10/09)
    1. marca por palavra -- a legenda e o bipe de palavrao dependem dela. O
       Kokoro devolve o tempo de cada palavra em ingles; o resto passa pelo
       alinhamento do faster-whisper (MIT) contra o texto que se pediu (as
       palavras da legenda sao SEMPRE as do roteiro, o whisper so' da o tempo).
    2. portugues do Brasil -- chatterbox (language_id "pt") e kokoro ("p").
    3. custo que faz sentido em volume baixo -- zero: roda no runner.

COMO SE USA
    O perfil de voz escolhe: {"motor": "chatterbox"} ou {"motor": "kokoro"}.
    Campos opcionais do perfil:
        ref_url        trecho WAV/MP3 de 6-15 s com a voz a clonar
        kokoro_voice   voz do Kokoro (af_heart, am_michael, pf_dora, pm_alex...)
        exaggeration   0.25 (contido) .. 0.5 (padrao) .. 0.9 (exagerado)
        cfg_weight     0.5 padrao; 0.3 para quem fala rapido
        velocidade     so' kokoro, 1.0 padrao
    Sem `kokoro_voice`, a voz do Edge do perfil (`voice`) diz o genero e a
    lingua (`VOZ_DO_EDGE`), entao cada personagem continua com uma voz propria.

    `palito_v5.sintetizar` chama `sintetizar_livre`; qualquer falha aqui
    levanta excecao e a cadeia segue para o degrau seguinte (Azure -> Edge).

    Teste local (precisa de rede na primeira vez):
        python voz_livre.py --motor kokoro --texto "What if the Moon vanished?" -o t.wav
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import wave

SR = 24000
MOTORES = ("chatterbox", "kokoro")

# AS DUAS CHAVES DA TROCA (lidas por `palito_v5.sintetizar`; o ambiente
# VOZ_EDGE_VIRA / VOZ_RESERVA_LIVRE sobrepoe):
#   EDGE_VIRA          perfil com motor "edge" (8 dos 10 canais) passa a usar
#                      este motor; o Edge vira so' a rede de seguranca.
#   RESERVA_DO_ELEVEN  quando a ElevenLabs recusa (credito), este motor entra
#                      ANTES do Azure (que tem as mesmas vozes do Edge).
# Vazias = desligadas. Ligar e' trocar aqui depois de ouvir o ensaio.
EDGE_VIRA = ""
RESERVA_DO_ELEVEN = ""

# Versoes travadas: um motor que muda sozinho no meio da producao e' o tipo de
# surpresa de domingo que o resto da cadeia de voz foi escrito para evitar.
_TORCH = ["torch==2.6.0", "torchaudio==2.6.0"]
_PACOTES = {
    "chatterbox": ["chatterbox-tts>=0.1.4,<0.2"],
    "kokoro": ["kokoro==0.9.4", "soundfile"],
    "whisper": ["faster-whisper==1.1.1"],
}
_PRONTO = set()

# A voz do Edge que o perfil ja tem -> a voz do Kokoro com o mesmo papel.
# Genero e lingua iguais; vozes diferentes ficam diferentes.
VOZ_DO_EDGE = {
    "en-US-GuyNeural": "am_michael", "en-US-ChristopherNeural": "am_fenrir", "en-US-EricNeural": "am_eric",
    "en-US-AndrewNeural": "am_adam", "en-US-BrianNeural": "am_puck", "en-US-RogerNeural": "am_onyx",
    "en-US-SteffanNeural": "am_liam", "en-US-DavisNeural": "am_echo",
    "en-US-JennyNeural": "af_heart", "en-US-AriaNeural": "af_bella", "en-US-AvaNeural": "af_nicole",
    "en-US-EmmaNeural": "af_sarah", "en-US-MichelleNeural": "af_nova", "en-US-AnaNeural": "af_sky",
    "en-GB-RyanNeural": "bm_george", "en-GB-ThomasNeural": "bm_lewis", "en-GB-SoniaNeural": "bf_emma",
    "en-GB-LibbyNeural": "bf_isabella",
    "pt-BR-AntonioNeural": "pm_alex", "pt-BR-FranciscaNeural": "pf_dora", "pt-BR-ThalitaNeural": "pf_dora",
}
_KOKORO_PADRAO = {"en": ("am_michael", "af_heart"), "pt": ("pm_alex", "pf_dora"), "es": ("em_alex", "ef_dora")}
_FEMININOS = ("jenny", "aria", "ava", "emma", "michelle", "ana", "sonia", "libby", "francisca", "thalita",
              "maria", "female", "mulher")

# A frase que vira a REFERENCIA quando o canal nao tem gravacao: ~10 s, ritmo
# de narrador, sem nome proprio (o chatterbox copia a cadencia junto com o timbre).
_FRASE_REF = {
    "en": "Here is something most people never think about. It sounds simple at first, but the more you "
          "look at it, the stranger it gets. So let's take it one step at a time.",
    "pt": "Tem uma coisa que quase ninguem para pra pensar. Parece simples no comeco, mas quanto mais "
          "voce olha, mais estranho fica. Entao vamos por partes, com calma.",
    "es": "Hay algo en lo que casi nadie se detiene a pensar. Parece simple al principio, pero cuanto mas "
          "lo miras, mas extrano se vuelve. Asi que vamos paso a paso.",
}


# =====================================================================
# dependencias: instaladas na primeira chamada (o render dos outros
# canais nao paga os ~2 min do torch)
# =====================================================================
# ISOLADO (22/10, run 39815253969): instalar o chatterbox DENTRO do processo do
# render trocou o numpy que ja' estava carregado ("numpy.dtype size changed"),
# a voz caiu no Edge como devia -- e logo depois a MIXAGEM quebrou, derrubando
# o video. Agora as dependencias moram num venv proprio e a sintese roda num
# processo TRABALHADOR desse venv (`--servidor`), que carrega os modelos uma
# vez e atende todas as falas do video. O processo do render nunca importa
# torch nem troca numpy.
VENV = os.environ.get("VOZ_LIVRE_VENV") or os.path.join(tempfile.gettempdir(), "voz_livre_venv")


def _py_venv():
    return os.path.join(VENV, "bin", "python")


def _garantir_venv():
    marca = os.path.join(VENV, ".pronto")
    if os.path.exists(marca):
        return
    print(f"[voz-livre] montando o ambiente isolado em {VENV} (~3 min, uma vez por render)", flush=True)
    subprocess.run([sys.executable, "-m", "venv", VENV], check=True)
    pip = [_py_venv(), "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
    subprocess.run(pip + ["--upgrade", "pip"], check=False)
    # torch de CPU: o wheel padrao traz CUDA (~2,5 GB) que o runner nao usa
    subprocess.run(pip + _TORCH + ["--index-url", "https://download.pytorch.org/whl/cpu"], check=True)
    # o indice de CPU como extra: o torch==2.6.0 exigido ja' esta satisfeito pelo
    # 2.6.0+cpu e o pip nao baixa o de CUDA
    subprocess.run(pip + _PACOTES["chatterbox"] + _PACOTES["kokoro"] + _PACOTES["whisper"]
                   + ["--extra-index-url", "https://download.pytorch.org/whl/cpu"], check=True)
    # o G2P do portugues (e o reserva do ingles) do kokoro e' o espeak-ng do sistema
    if not _tem("espeak-ng"):
        subprocess.run(["sudo", "apt-get", "install", "-y", "-qq", "espeak-ng"], check=False)
    open(marca, "w").write("ok")


def _instalar(qual):
    """No trabalhador as dependencias ja' vem do venv; fora dele, nada se instala."""
    return


def _tem(prog):
    from shutil import which
    return which(prog) is not None


# =====================================================================
# lingua e voz
# =====================================================================
def _lingua(cfg):
    v = str(cfg.get("lingua") or cfg.get("idioma") or cfg.get("voice") or "").lower()
    if v.startswith("pt"):
        return "pt"
    if v.startswith("es"):
        return "es"
    return "en"


def _voz_kokoro(cfg):
    if cfg.get("kokoro_voice"):
        return str(cfg["kokoro_voice"])
    edge = str(cfg.get("voice") or "")
    if edge in VOZ_DO_EDGE:
        return VOZ_DO_EDGE[edge]
    m, f = _KOKORO_PADRAO[_lingua(cfg)]
    return f if any(x in edge.lower() for x in _FEMININOS) else m


def _kokoro_lang(voz):
    # a primeira letra da voz e' a lingua no Kokoro: a/b ingles, p portugues, e espanhol
    return {"a": "a", "b": "b", "p": "p", "e": "e"}.get(voz[:1], "a")


# =====================================================================
# kokoro
# =====================================================================
_KPIPE = {}


def _kokoro(texto, cfg, destino):
    """Devolve (marcas ou None, duracao). Marca so' vem no ingles."""
    _instalar("kokoro")
    import numpy as np
    from kokoro import KPipeline
    voz = _voz_kokoro(cfg)
    lang = _kokoro_lang(voz)
    if lang not in _KPIPE:
        _KPIPE[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
    pipe = _KPIPE[lang]
    partes, marcas, t0 = [], [], 0.0
    for res in pipe(texto, voice=voz, speed=float(cfg.get("velocidade") or 1.0)):
        audio = res.audio
        if audio is None:
            continue
        a = audio.detach().cpu().numpy() if hasattr(audio, "detach") else np.asarray(audio)
        for tk in (getattr(res, "tokens", None) or []):
            ini, fim = getattr(tk, "start_ts", None), getattr(tk, "end_ts", None)
            txt = str(getattr(tk, "text", "") or "").strip()
            if ini is None or fim is None or not re.search(r"\w", txt):
                continue
            marcas.append({"palavra": txt, "inicio_s": t0 + float(ini), "fim_s": t0 + float(fim)})
        partes.append(a.astype("float32"))
        t0 += len(a) / 24000.0
    if not partes:
        raise RuntimeError("kokoro nao devolveu audio")
    _gravar(destino, np.concatenate(partes), 24000)
    return (marcas if lang in ("a", "b") and marcas else None), t0


# =====================================================================
# chatterbox
# =====================================================================
_CB = {}


def _referencia(cfg, tmp):
    """O trecho cuja voz o chatterbox clona.

    1. `ref_url` do perfil (gravacao propria) -- baixada uma vez por processo;
    2. senao, uma voz SINTETICA do Kokoro lendo `_FRASE_REF`: cada personagem
       ganha um timbre estavel (o mesmo `kokoro_voice` = a mesma voz em todo
       video) sem copiar a voz de ninguem;
    3. se ate isso falhar, None = a voz embutida do chatterbox."""
    url = cfg.get("ref_url")
    if url:
        dest = os.path.join(tmp, "ref_" + re.sub(r"\W", "_", url)[-40:] + ".wav")
        if not os.path.exists(dest):
            import urllib.request
            bruto = dest + ".bruto"
            urllib.request.urlretrieve(url, bruto)
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", bruto, "-ac", "1", "-ar", "24000", "-t", "15", dest], check=True)
        return dest
    voz = _voz_kokoro(cfg)
    dest = os.path.join(tmp, f"ref_kokoro_{voz}.wav")
    if not os.path.exists(dest):
        try:
            frase = _FRASE_REF.get(_lingua(cfg), _FRASE_REF["en"])
            _kokoro(frase, dict(cfg, kokoro_voice=voz, velocidade=1.0), dest)
        except Exception as e:                                   # noqa: BLE001
            print(f"[voz-livre] referencia kokoro falhou ({e}); voz embutida do chatterbox")
            return None
    return dest


def _cb_modelo(lingua):
    import torch
    torch.set_num_threads(max(1, os.cpu_count() or 2))
    chave = "mtl" if lingua != "en" else "en"
    if chave in _CB:
        return _CB[chave]
    if chave == "en":
        from chatterbox.tts import ChatterboxTTS
        m = ChatterboxTTS.from_pretrained(device="cpu")
    else:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        m = ChatterboxMultilingualTTS.from_pretrained(device="cpu")
    _CB[chave] = m
    return m


def _frases(texto, max_chars=240):
    """O chatterbox perde o fio em texto longo; corta em frases e junta."""
    if len(texto) <= max_chars:
        return [texto]
    out, atual = [], ""
    for f in re.split(r"(?<=[.!?…])\s+", texto):
        if atual and len(atual) + len(f) + 1 > max_chars:
            out.append(atual)
            atual = f
        else:
            atual = (atual + " " + f).strip()
    if atual:
        out.append(atual)
    return out


def _chatterbox(texto, cfg, destino, tmp):
    _instalar("chatterbox")
    import numpy as np
    lingua = _lingua(cfg)
    ref = _referencia(cfg, tmp)
    m = _cb_modelo(lingua)
    kw = {"exaggeration": float(cfg.get("exaggeration", 0.5)), "cfg_weight": float(cfg.get("cfg_weight", 0.5)),
          "temperature": float(cfg.get("temperature", 0.8))}
    if ref:
        kw["audio_prompt_path"] = ref
    pedacos = []
    for frase in _frases(texto):
        if lingua != "en":
            wav = m.generate(frase, language_id=lingua, **kw)
        else:
            wav = m.generate(frase, **kw)
        a = wav.squeeze().detach().cpu().numpy().astype("float32")
        pedacos.append(a)
        pedacos.append(np.zeros(int(0.12 * m.sr), dtype="float32"))
    x = np.concatenate(pedacos[:-1]) if len(pedacos) > 1 else pedacos[0]
    _gravar(destino, x, m.sr)
    return None, len(x) / float(m.sr)


# =====================================================================
# marca por palavra: faster-whisper alinhado ao TEXTO PEDIDO
# =====================================================================
_WH = {}


def _norm(p):
    return re.sub(r"[^\w]", "", p.lower())


def alinhar(wav, texto, lingua="en"):
    """[{palavra, inicio_s, fim_s}] com as palavras DO TEXTO e o tempo do audio.

    O whisper transcreve com o tempo de cada palavra; o casamento com o texto
    (difflib) passa o tempo para as palavras do roteiro. Palavra que o whisper
    ouviu diferente ("11" x "eleven") fica entre as vizinhas casadas, no
    reparto pelo tamanho -- a legenda nunca mostra o que o whisper ACHOU."""
    _instalar("whisper")
    from difflib import SequenceMatcher
    from faster_whisper import WhisperModel
    nome = "base.en" if lingua == "en" else "small"
    if nome not in _WH:
        _WH[nome] = WhisperModel(nome, device="cpu", compute_type="int8")
    segs, _ = _WH[nome].transcribe(wav, language=lingua, word_timestamps=True, beam_size=1,
                                   vad_filter=False, condition_on_previous_text=False)
    ouvidas = [w for s in segs for w in (s.words or [])]
    pedidas = texto.split()
    dur = _duracao(wav)
    if not ouvidas:
        return _reparto(pedidas, 0.0, dur)
    a = [_norm(p) for p in pedidas]
    b = [_norm(w.word) for w in ouvidas]
    tempos = [None] * len(pedidas)
    for blk in SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            w = ouvidas[blk.b + k]
            tempos[blk.a + k] = (float(w.start), float(w.end))
    # buracos: reparto entre as ancoras vizinhas
    i = 0
    while i < len(pedidas):
        if tempos[i] is not None:
            i += 1
            continue
        j = i
        while j < len(pedidas) and tempos[j] is None:
            j += 1
        ini = tempos[i - 1][1] if i > 0 else (float(ouvidas[0].start) if ouvidas else 0.0)
        fim = tempos[j][0] if j < len(pedidas) else max(ini + 0.2, min(dur, float(ouvidas[-1].end) + 0.3))
        for k, m in enumerate(_reparto(pedidas[i:j], ini, max(ini + 0.05 * (j - i), fim))):
            tempos[i + k] = (m["inicio_s"], m["fim_s"])
        i = j
    return [{"palavra": p, "inicio_s": round(t[0], 3), "fim_s": round(max(t[1], t[0] + 0.04), 3)}
            for p, t in zip(pedidas, tempos)]


def _reparto(palavras, ini, fim):
    peso = [max(1, len(_norm(p))) for p in palavras]
    tot, t, out = float(sum(peso) or 1), ini, []
    for p, w in zip(palavras, peso):
        d = (fim - ini) * w / tot
        out.append({"palavra": p, "inicio_s": t, "fim_s": t + d})
        t += d
    return out


# =====================================================================
# audio
# =====================================================================
def _gravar(destino, x, sr):
    import numpy as np
    x = np.asarray(x, dtype="float32")
    with wave.open(destino, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(sr))
        w.writeframes((np.clip(x, -1, 1) * 32000).astype("<i2").tobytes())


def _duracao(caminho):
    with wave.open(caminho) as w:
        return w.getnframes() / float(w.getframerate())


def _acabamento(entrada, destino, sr=SR):
    """Corta o silencio das pontas (o respiro entre falas e' do motor, nao do
    TTS), tira o grave abaixo de 70 Hz e iguala o volume ao do Edge/Eleven."""
    filtro = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,"
              "areverse,silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse,"
              "highpass=f=70,loudnorm=I=-16:LRA=11:TP=-1.5")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", entrada, "-af", filtro, "-ar", str(sr), "-ac", "1", destino],
                   check=True)


# =====================================================================
# entrada
# =====================================================================
class _Trabalhador:
    """O processo do venv isolado: uma linha JSON por pedido, uma por resposta.
    Os logs dele vao para o stderr (aparecem no log do Action); o stdout e' so'
    do protocolo."""
    _p = None

    @classmethod
    def pedir(cls, pedido):
        if cls._p is None or cls._p.poll() is not None:
            _garantir_venv()
            cls._p = subprocess.Popen([_py_venv(), os.path.abspath(__file__), "--servidor"],
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        cls._p.stdin.write(json.dumps(pedido, ensure_ascii=False) + "\n")
        cls._p.stdin.flush()
        linha = cls._p.stdout.readline()
        if not linha:
            raise RuntimeError("o trabalhador da voz livre morreu (ver o log acima)")
        r = json.loads(linha)
        if not r.get("ok"):
            raise RuntimeError(r.get("erro") or "falha sem mensagem")
        return r["marcas"]


def sintetizar_livre(texto, cfg, destino, motor=None):
    """Texto -> WAV mono 24 kHz em `destino`; devolve as marcas por palavra.

    Roda no trabalhador isolado. Levanta excecao em qualquer falha: quem chama
    (`palito_v5.sintetizar`) segue para o degrau seguinte da cadeia."""
    return _Trabalhador.pedir({"texto": texto, "cfg": cfg, "destino": os.path.abspath(destino), "motor": motor})


def _sintetizar_local(texto, cfg, destino, motor=None):
    motor = (motor or cfg.get("motor") or "chatterbox").lower()
    if motor not in MOTORES:
        raise ValueError(f"motor livre desconhecido: {motor}")
    texto = re.sub(r"\[[^\]\[]{1,40}\]", " ", str(texto)).strip()   # tags de direcao do eleven_v4
    texto = re.sub(r"\s+", " ", texto)
    if not texto:
        raise ValueError("texto vazio")
    tmp = os.environ.get("VOZ_LIVRE_TMP") or os.path.join(tempfile.gettempdir(), "voz_livre")
    os.makedirs(tmp, exist_ok=True)
    cru = destino + ".cru.wav"
    if motor == "kokoro":
        _kokoro(texto, cfg, cru)
    else:
        _chatterbox(texto, cfg, cru, tmp)
    _acabamento(cru, destino)
    # o acabamento corta as pontas e as marcas do kokoro deslocariam: o
    # alinhamento e' sempre feito no arquivo FINAL
    marcas = alinhar(destino, texto, _lingua(cfg))
    try:
        os.remove(cru)
    except OSError:
        pass
    return marcas


def _servidor():
    import traceback
    sys.stdout, saida = sys.stderr, sys.stdout      # print dos motores vai para o log, nao para o protocolo
    for linha in sys.stdin:
        try:
            q = json.loads(linha)
            m = _sintetizar_local(q["texto"], q.get("cfg") or {}, q["destino"], q.get("motor"))
            r = {"ok": True, "marcas": m}
        except Exception as e:                                  # noqa: BLE001
            traceback.print_exc()
            r = {"ok": False, "erro": f"{type(e).__name__}: {e}"[:500]}
        saida.write(json.dumps(r, ensure_ascii=False) + "\n")
        saida.flush()


if __name__ == "__main__" and "--servidor" in sys.argv:
    _servidor()
    sys.exit(0)

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--motor", default="chatterbox", choices=MOTORES)
    ap.add_argument("--texto", required=True)
    ap.add_argument("--voz", default="en-US-GuyNeural", help="voz do Edge do perfil (diz genero e lingua)")
    ap.add_argument("--kokoro-voice")
    ap.add_argument("--exaggeration", type=float, default=0.5)
    ap.add_argument("-o", "--saida", default="voz_livre.wav")
    a = ap.parse_args()
    perfil = {"motor": a.motor, "voice": a.voz, "exaggeration": a.exaggeration}
    if a.kokoro_voice:
        perfil["kokoro_voice"] = a.kokoro_voice
    m = sintetizar_livre(a.texto, perfil, a.saida)
    print(json.dumps({"saida": a.saida, "dur_s": round(_duracao(a.saida), 2), "marcas": m}, ensure_ascii=False)[:2000])
