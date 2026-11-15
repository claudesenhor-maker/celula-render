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
def rampa_de_tom(x, sr, ini_s, fim_s, st_final):
    import subprocess
    a, b = max(0, int(ini_s * sr)), min(len(x), int(fim_s * sr))
    if b - a < int(0.08 * sr) or abs(st_final) < 0.3: return x
    rb = 'rubberband' in subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, text=True).stdout
    if not rb: return x
    fat = int(0.04 * sr); cruz = int(0.012 * sr); n = max(2, (b - a) // fat); y = x.copy(); acc = np.zeros(b - a, dtype='float32'); peso = np.zeros(b - a, dtype='float32')
    for k in range(n):
        s0 = a + k * (b - a) // n; s1 = a + (k + 1) * (b - a) // n if k < n - 1 else b
        e0, e1 = max(a, s0 - cruz), min(b, s1 + cruz); st = st_final * ((k + 1) / n) ** (1.0 if st_final > 0 else 1.3)
        r = subprocess.run(['ffmpeg', '-v', 'error', '-f', 's16le', '-ar', str(sr), '-ac', '1', '-i', '-', '-af', f'rubberband=pitch={2 ** (st / 12):.5f}:formant=preserved:pitchq=quality',
                            '-f', 's16le', '-ar', str(sr), '-ac', '1', '-'], input=(np.clip(x[e0:e1], -1, 1) * 32767).astype('<i2').tobytes(), capture_output=True, check=True)
        p = np.frombuffer(r.stdout, dtype='<i2').astype('float32') / 32768; L = e1 - e0
        p = np.pad(p, (0, max(0, L - len(p))))[:L]
        w = np.ones(L, dtype='float32'); c0 = s0 - e0; c1 = e1 - s1
        if c0 > 0: w[:2 * c0] = np.linspace(0, 1, 2 * c0)[:len(w[:2 * c0])]
        if c1 > 0: w[-2 * c1:] = np.linspace(1, 0, 2 * c1)[-len(w[-2 * c1:]):]
        acc[e0 - a:e1 - a] += p * w; peso[e0 - a:e1 - a] += w
    y[a:b] = acc / np.maximum(peso, 1e-3)
    return y


def corrigir(x, sr, marcas, fins_de_fala=(), max_st=4.0):
    """rampa de tom no fim das frases que continuam erradas. `fins_de_fala`: índices de palavra que fecham uma fala do roteiro
    (só nesses a afirmação é forçada a descer; no meio do trecho uma frase pode ficar suspensa). Devolve (áudio, lista do que mudou)."""
    feitos = []; res = medir(x, sr, marcas); k = 0; fins = set(fins_de_fala)
    for fr, r in zip(frases(marcas), res):
        ult = k + len(fr) - 1; k += len(fr)
        if r['fim_st'] is None: continue
        alvo = None
        if r['tipo'] == 'pergunta_sim_nao' and r['fim_st'] < 1.5: alvo = min(max_st + 2.5, 3.5 - r['fim_st'])
        elif r['tipo'] == 'afirmacao' and ult in fins and r['fim_st'] > -0.6: alvo = -min(max_st, 2.2 + r['fim_st'])
        if alvo is None: continue
        w = fr[-1]; ini = max(w['inicio_s'], w['fim_s'] - 0.45)
        x = rampa_de_tom(x, sr, ini, w['fim_s'] + 0.03, alvo); feitos.append({'texto': r['texto'][-40:], 'tipo': r['tipo'], 'era_st': r['fim_st'], 'rampa_st': round(alvo, 1)})
    return x, feitos
