"""RÉGUA DE ENTONAÇÃO (15/11/2026, dono: "parar de focar em sentimento e focar na entonação: fim de frase, interrogação, fluidez").
Mede, frase a frase, se a melodia combina com a pontuação -- em qualquer idioma (só usa a pontuação e o tom):
  afirmação (. !)            -> o tom DESCE no fim;
  pergunta de sim/não (?)    -> o tom SOBE no fim;
  pergunta com pronome (quem, por que, how, qué...) -> começa ALTO e desce;
  continuação (, : ...)      -> fica suspenso (não desce até o chão).
Usada para escolher, entre várias tentativas do mesmo trecho, a que tem a entonação certa. Só numpy."""
import re, unicodedata
import numpy as np

PRON = set('quem que qual quais quando onde como quanto quantos quanta quantas porque por cade cadê quién quien qué cuál cual cuándo cuando dónde donde cómo cuánto cuanto '
           'who what which when where why how whose pourquoi comment quand qui quoi où quel quelle wer was wann wo warum wie chi che cosa quando dove perché come quale'.split())


def _n(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')


_PRON = {_n(p) for p in PRON}


def tom(x, sr, hop_s=0.01):
    """f0 (Hz, 0 = sem voz) a cada 10 ms, por autocorrelação."""
    hop = int(sr * hop_s); win = int(sr * 0.05); n = max(0, (len(x) - win) // hop)
    f0 = np.zeros(n); lo, hi = sr // 380, sr // 65; w = np.hanning(win); nf = 1 << int(np.ceil(np.log2(win * 2)))
    for i in range(n):
        s = x[i * hop:i * hop + win]; s = (s - s.mean()) * w
        ac = np.fft.irfft(np.abs(np.fft.rfft(s, nf)) ** 2)[:hi + 1]
        if ac[0] <= 1e-9: continue
        ac = ac / ac[0]; k = lo + int(np.argmax(ac[lo:hi + 1]))
        if ac[k] > 0.6: f0[i] = sr / k
    return f0


def frases(marcas):
    """agrupa as palavras [{palavra,inicio_s,fim_s}] em frases pela pontuação final."""
    out, cur = [], []
    for m in marcas:
        cur.append(m); p = m['palavra'].rstrip('"\')»”')
        if p.endswith(('.', '?', '!', '…', ':', ';')) or p.endswith('...'):
            out.append(cur); cur = []
    if cur: out.append(cur)
    return out


def tipo(fr):
    fim = fr[-1]['palavra'].rstrip('"\')»”')
    if fim.endswith('?'):
        ini = [_n(re.sub(r'[^\w]', '', w['palavra'])) for w in fr[:3]]
        return 'pergunta_pronome' if any(w in _PRON for w in ini) else 'pergunta_sim_nao'
    if fim.endswith(('...', '…', ':', ';')): return 'continuacao'
    return 'afirmacao'


def medir(x, sr, marcas, f0=None):
    """por frase: {tipo, texto, fim_st (tom do fim menos o do meio), inicio_st, ok, nota 0..1}."""
    f0 = tom(x, sr) if f0 is None else f0
    v = f0[f0 > 0]
    if len(v) < 20: return []
    base = np.median(v); res = []
    for fr in frases(marcas):
        a, b = int(fr[0]['inicio_s'] * 100), int(fr[-1]['fim_s'] * 100) + 8
        s = f0[a:b]; idx = np.nonzero(s > 0)[0]; t = tipo(fr); texto = ' '.join(w['palavra'] for w in fr)
        if len(idx) < 8: res.append({'tipo': t, 'texto': texto, 'fim_st': None, 'inicio_st': None, 'ok': None, 'nota': 0.5}); continue
        st = 12 * np.log2(s[idx] / base); n = len(st); q = max(3, n // 5)
        fim = float(np.median(st[-q:]) - np.median(st[q:-q] if n > 3 * q else st)); ini = float(np.median(st[:q]) - np.median(st))
        chao = float(np.median(st[-q:]))
        if t == 'afirmacao': nota = np.clip((-fim + 0.3) / 2.3, 0, 1)                      # desce >= 2 st = nota 1
        elif t == 'pergunta_sim_nao': nota = np.clip((fim + 0.5) / 2.5, 0, 1)                # sobe >= 2 st = nota 1
        elif t == 'pergunta_pronome': nota = np.clip((ini + 0.5) / 2.5, 0, 1) * 0.6 + np.clip((-fim + 1) / 2, 0, 1) * 0.4
        else: nota = np.clip((chao + 3.5) / 3.0, 0, 1)                                       # suspenso: não vai ao chão
        res.append({'tipo': t, 'texto': texto, 'fim_st': round(fim, 2), 'inicio_st': round(ini, 2), 'ok': bool(nota >= 0.5), 'nota': round(float(nota), 2)})
    return res


def resumo(res):
    out = {}
    for t in ('afirmacao', 'pergunta_sim_nao', 'pergunta_pronome', 'continuacao'):
        r = [x for x in res if x['tipo'] == t and x['ok'] is not None]
        if r: out[t] = {'frases': len(r), 'certas_%': round(100 * sum(x['ok'] for x in r) / len(r)), 'fim_st_mediana': round(float(np.median([x['fim_st'] for x in r])), 1)}
    r = [x['nota'] for x in res]
    out['nota'] = round(float(np.mean(r)), 3) if r else 0.0
    return out


# ---------------------------------------------------------------------------------------------------------------------
# CORREÇÃO LOCAL: quando nenhuma tentativa acerta, a ÚLTIMA palavra da frase ganha uma rampa de tom (sobe na pergunta de
# sim/não, desce no ponto final). É curta (só o fim da frase), contínua (fatias de 40 ms cruzadas) e preserva o timbre.
_RB = None


def _rubberband():
    global _RB
    if _RB is None:
        import subprocess
        _RB = 'rubberband' in subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, text=True).stdout
    return _RB


def contorno_de_tom(x, sr, pontos):
    """muda o tom ao longo do tempo seguindo `pontos` = [(t_s, semitons), ...] (linear entre eles; antes do primeiro e depois
    do último vale 0). Uma passada só do rubberband com o tom comandado a cada 10 ms -- contínuo, sem fatias nem emendas no
    meio da palavra (a v7 transpunha fatias de 40 ms isoladas e o efeito quase sumia). Preserva formantes (timbre)."""
    import subprocess
    pontos = sorted(pontos)
    if len(pontos) < 2 or not _rubberband() or max(abs(p[1]) for p in pontos) < 0.3: return x
    marg = int(0.3 * sr); a = max(0, int(pontos[0][0] * sr)); b = min(len(x), int(pontos[-1][0] * sr))
    if b - a < int(0.06 * sr): return x
    e0, e1 = max(0, a - marg), min(len(x), b + marg); seg = x[e0:e1]; L = len(seg); AT = 0.06     # o filtro aplica o comando ~60 ms antes
    ts = [p[0] - e0 / sr for p in pontos]; vs = [p[1] for p in pontos]; cmds = []; ant = None
    for i in range(int(L / sr * 100) + 1):
        t = i * 0.01; st = float(np.interp(t - AT, ts, vs, left=0.0, right=0.0)); f = f'{2 ** (st / 12):.4f}'
        if f != ant: cmds.append(f'{t:.2f} rubberband pitch {f}'); ant = f
    af = "asetnsamples=n=240:p=0,asendcmd=c='" + ';'.join(cmds) + "',rubberband=pitch=1:formant=preserved:pitchq=quality"
    r = subprocess.run(['ffmpeg', '-v', 'error', '-f', 's16le', '-ar', str(sr), '-ac', '1', '-i', '-', '-af', af, '-f', 's16le', '-ar', str(sr), '-ac', '1', '-'],
                       input=(np.clip(seg, -1, 1) * 32767).astype('<i2').tobytes(), capture_output=True)
    if r.returncode != 0: return x
    p = np.frombuffer(r.stdout, dtype='<i2').astype('float32') / 32768
    if abs(len(p) - L) > sr // 20: return x
    p = np.pad(p, (0, max(0, L - len(p))))[:L]
    # volta ao original nas margens (onde o tom não mudou), com cruzamento de 30 ms
    w = np.zeros(L, dtype='float32'); c = int(0.03 * sr); i0 = max(0, a - e0 - int(0.1 * sr)); i1 = min(L, b - e0 + int(0.1 * sr))
    w[i0:i1] = 1
    if i0 >= c: w[i0 - c:i0] = np.linspace(0, 1, c)
    if L - i1 >= c: w[i1:i1 + c] = np.linspace(1, 0, c)
    y = x.copy(); y[e0:e1] = p * w + seg * (1 - w)
    return y


def rampa_de_tom(x, sr, ini_s, fim_s, st_final, solta_s=None):
    """rampa no fim da frase: de 0 até `st_final` entre ini_s e fim_s; segura até `solta_s` (silêncio depois da palavra) e solta."""
    if fim_s - ini_s < 0.08 or abs(st_final) < 0.3: return x
    n = 6; e = 1.0 if st_final > 0 else 1.3; solta_s = max(fim_s + 0.02, solta_s or fim_s + 0.12)
    return contorno_de_tom(x, sr, [(ini_s + (fim_s - ini_s) * i / n, st_final * (i / n) ** e) for i in range(n + 1)] + [(solta_s, st_final), (solta_s + 0.03, 0.0)])


def _pontos_ate_alvo(f0, fr, ini_s, fim_s, solta_s, delta_st, lim=(-7.0, 8.0)):
    """pontos de contorno que levam o fim da frase até (tom do meio da frase + delta_st), descontando o que a voz JÁ faz:
    uma pergunta que despenca uma oitava precisa de mais correção do que uma que só ficou reta."""
    a, b = int(fr[0]['inicio_s'] * 100), min(len(f0), int(fr[-1]['fim_s'] * 100) + 8); s = f0[a:b].astype('float64').copy()
    v = s[s > 0]
    if len(v) < 8: return None
    med = np.median(v); s[(s > med * 1.7) | (s < med * 0.55)] = 0; idx = np.nonzero(s > 0)[0]      # tira erro de oitava do medidor
    if len(idx) < 8: return None
    st = 12 * np.log2(s[idx] / med); n = len(st); q = max(3, n // 5); meio = float(np.median(st[q:-q] if n > 3 * q else st))
    cont = np.interp(np.arange(len(s)), idx, st)                                                     # contorno atual, sem buracos
    i0 = int(np.clip(int(ini_s * 100) - a, 0, len(s) - 1)); i1 = int(np.clip(int(fim_s * 100) - a, i0 + 1, len(s)))
    if i1 - i0 < 6: return None
    k = np.ones(5) / 5; atual = np.convolve(np.pad(cont[i0:i1], 2, mode='edge'), k, 'valid'); m = len(atual)
    caminho = atual[0] + (meio + delta_st - atual[0]) * (np.arange(m) / (m - 1)) ** (1.0 if delta_st > 0 else 1.2)
    d = np.clip(caminho - atual, lim[0], lim[1]); d[0] = 0.0
    if np.max(np.abs(d)) < 0.5: return None
    passo = max(1, m // 10); pts = [(ini_s + i / 100, float(d[i])) for i in range(0, m, passo)]
    if pts[-1][0] < ini_s + (m - 1) / 100 - 1e-6: pts.append((ini_s + (m - 1) / 100, float(d[-1])))
    fim_v = float(d[-1]); solta_s = max(pts[-1][0] + 0.02, solta_s)
    return pts + [(solta_s, fim_v), (solta_s + 0.03, 0.0)], round(float(d[-1]), 1)


def corrigir(x, sr, marcas, fins_de_fala=(), max_st=4.0):
    """acerta a melodia das frases que continuam erradas depois da escolha entre tentativas (devolve (áudio, lista do que mudou)):
      afirmação que não desce          -> desce na última palavra (em fim de fala do roteiro desce mais; no meio do trecho, menos);
      pergunta de sim/não que não sobe -> sobe na última palavra;
      pergunta com pronome que começa baixa -> a primeira palavra sobe e o tom escorre até o meio da frase; o fim desce;
      continuação (: ...) que cai no chão -> o fim fica suspenso.
    A correção desconta o que a voz já faz (contorno medido) e é contínua (contorno_de_tom)."""
    feitos = []; f0 = tom(x, sr); res = medir(x, sr, marcas, f0); k = 0; fins = set(fins_de_fala); todas = list(marcas)
    for fr, r in zip(frases(marcas), res):
        ult = k + len(fr) - 1; k += len(fr)
        if r['fim_st'] is None: continue
        w = fr[-1]; prox = todas[ult + 1]['inicio_s'] if ult + 1 < len(todas) else w['fim_s'] + 0.3
        solta = min(w['fim_s'] + 0.2, max(w['fim_s'] + 0.02, prox - 0.03)); ini = max(w['inicio_s'], w['fim_s'] - 0.45)
        if len(fr) > 1 and w['fim_s'] - w['inicio_s'] < 0.22: ini = max(fr[-2]['inicio_s'], w['fim_s'] - 0.45)   # palavra final curta: pega a anterior junto
        delta = None
        if r['tipo'] == 'pergunta_sim_nao' and r['fim_st'] < 1.5: delta = 3.0
        elif r['tipo'] == 'afirmacao' and r['fim_st'] > (-0.6 if ult in fins else 0.4): delta = -2.0 if ult in fins else -1.2
        elif r['tipo'] == 'continuacao' and r['nota'] < 0.5: delta = -0.6
        elif r['tipo'] == 'pergunta_pronome' and r['nota'] < 0.5:
            p0 = fr[0]; sobe = float(np.clip(2.0 - (r['inicio_st'] or 0), 1.0, 3.5)); meio = fr[min(len(fr) - 1, max(1, len(fr) // 2))]['inicio_s']
            x = contorno_de_tom(x, sr, [(p0['inicio_s'] - 0.02, 0.0), (p0['inicio_s'] + 0.01, sobe), (p0['fim_s'], sobe), (max(p0['fim_s'] + 0.1, meio), 0.0)])
            if len(fr) > 2 and r['fim_st'] > -0.5:
                pa = _pontos_ate_alvo(f0, fr, ini, w['fim_s'] + 0.03, solta, -1.6)
                if pa: x = contorno_de_tom(x, sr, pa[0])
            feitos.append({'texto': r['texto'][-40:], 'tipo': r['tipo'], 'era_st': r['inicio_st'], 'rampa_st': round(sobe, 1)}); continue
        if delta is None: continue
        pa = _pontos_ate_alvo(f0, fr, ini, w['fim_s'] + 0.03, solta, delta)
        if not pa: continue
        x = contorno_de_tom(x, sr, pa[0]); feitos.append({'texto': r['texto'][-40:], 'tipo': r['tipo'], 'era_st': r['fim_st'], 'rampa_st': pa[1]})
    return x, feitos
