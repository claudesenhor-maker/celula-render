"""MARCAÇÃO DE EMOÇÃO NA FALA (14/11/2026, pedido do dono): o roteiro escreve  emocao(trecho)  e a voz muda naquele trecho.

    Ele apostou tudo. triste(E perdeu.) pausa(0.6) ironico(Parabéns, viu.) Mas enfase(ninguém) viu.

Vale em QUALQUER idioma: o nome da emoção aceita português, espanhol e inglês (triste/sad, ironico/sarcastic, susurro/whisper...).
Três camadas, da mais forte para a que sempre existe:
  1. referência do banco de vozes gravada NAQUELA emoção (quando a voz tem: <idioma>/<voz>/<emocao>.mp3) -- o clone copia a entonação;
  2. parâmetros do clonador por emoção (exaggeration, cfg_weight, temperature);
  3. PROSÓDIA por processamento de áudio no trecho: tom (semitons), ritmo e volume. Esta não depende do modelo nem do idioma --
     é ela que garante a troca de registro entre frases que o clonador sozinho achata (medido: 2 st contra ~4 st do original).
Comandos: pausa(segundos) e enfase(palavras) (a palavra sai mais lenta, mais alta e um pouco mais aguda).
Nome que não é emoção (ex.: f(x), João(o primo)) fica como texto normal. Sem dependências além do ffmpeg."""
import re, subprocess, unicodedata

#            ref (humor do banco, em ordem de preferência)   exag  cfg   temp  semitons ritmo  ganho dB
EMOCOES = {
    'neutro':   dict(ref=['causo'],                 exag=.60, cfg=.30, temp=.80, st=0.0,  tempo=1.00, db=0.0),
    'causo':    dict(ref=['causo'],                 exag=.62, cfg=.30, temp=.80, st=0.0,  tempo=1.00, db=0.0),
    'triste':   dict(ref=['triste', 'seco', 'tenso'], exag=.55, cfg=.35, temp=.75, st=-1.7, tempo=0.91, db=-2.0),
    'alegre':   dict(ref=['alegre', 'espanto', 'causo'], exag=.85, cfg=.28, temp=.85, st=1.3, tempo=1.04, db=1.0),
    'animado':  dict(ref=['alegre', 'espanto', 'causo'], exag=.95, cfg=.25, temp=.90, st=1.7, tempo=1.06, db=1.5),
    'ironico':  dict(ref=['ironico', 'causo'],      exag=.78, cfg=.30, temp=.85, st=0.7,  tempo=0.96, db=0.0),
    'tenso':    dict(ref=['tenso', 'seco'],         exag=.68, cfg=.32, temp=.80, st=-1.2, tempo=0.93, db=-1.5),
    'espanto':  dict(ref=['espanto', 'alegre'],     exag=.92, cfg=.25, temp=.90, st=2.1,  tempo=1.03, db=1.5),
    'seco':     dict(ref=['seco', 'tenso'],         exag=.50, cfg=.35, temp=.75, st=-2.0, tempo=0.95, db=-0.5),
    'raiva':    dict(ref=['raiva', 'espanto'],      exag=1.0, cfg=.25, temp=.90, st=0.9,  tempo=1.05, db=2.5),
    'sussurro': dict(ref=['tenso', 'seco'],         exag=.45, cfg=.38, temp=.75, st=-0.6, tempo=0.90, db=-5.0),
}
APELIDOS = {
    'neutro': 'neutral normal', 'causo': 'narrador contador storyteller narrator cuento',
    'triste': 'sad tristeza melancolico melancolia',
    'alegre': 'feliz happy contento contente joy alegria', 'animado': 'empolgado excited emocionado entusiasmado euforico',
    'ironico': 'sarcastico sarcastic ironic deboche debochado ironia', 'tenso': 'suspense tense medo fear miedo nervoso nervioso tension',
    'espanto': 'surpresa surpreso surprised surprise sorpresa choque shock asombro', 'seco': 'serio serious dry flat frio',
    'raiva': 'bravo angry anger enojado furioso furia ira', 'sussurro': 'whisper susurro baixinho cochicho sussurrando',
}
ENFASE = dict(st=1.2, tempo=0.85, db=2.5)


def _n(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s.lower()) if unicodedata.category(c) != 'Mn')


_MAPA = {_n(k): k for k in EMOCOES}
for _k, _v in APELIDOS.items():
    for _a in _v.split():
        _MAPA[_n(_a)] = _k
_CMD = {'pausa': 'pausa', 'pause': 'pausa', 'enfase': 'enfase', 'emphasis': 'enfase', 'destaque': 'enfase', 'enfasis': 'enfase'}
_ABRE = re.compile(r'([A-Za-zÀ-ÿ_]+)\(')


def _fecha(s, i):
    """índice do ')' que fecha o '(' aberto antes de i (aceita parênteses internos)."""
    d = 1
    while i < len(s):
        if s[i] == '(': d += 1
        elif s[i] == ')':
            d -= 1
            if d == 0: return i
        i += 1
    return -1


def interpretar(texto, padrao='neutro'):
    """texto com marcação -> [{texto, emocao, pausa_s (depois do trecho), enfases: [índice de palavra no trecho]}]; o texto sai LIMPO."""
    padrao = _MAPA.get(_n(padrao or 'neutro'), 'neutro')
    saida = []

    def trecho(emo):
        if not saida or saida[-1]['emocao'] != emo or saida[-1]['pausa_s'] > 0:
            saida.append({'texto': '', 'emocao': emo, 'pausa_s': 0.0, 'enfases': []})
        return saida[-1]

    def por(txt, emo, enfase=False):
        txt = re.sub(r'\s+', ' ', txt)
        if not txt.strip(): return
        mp = re.match(r'^\s*([.,!?…;:]+)', txt)
        if mp and saida:                                         # pontuação logo depois de um ')' gruda no trecho anterior
            saida[-1]['texto'] = saida[-1]['texto'].rstrip() + mp.group(1); txt = txt[mp.end():]
            if not txt.strip(): return
        t = trecho(emo); n0 = len(t['texto'].split())
        t['texto'] = (t['texto'] + (' ' if t['texto'] and not t['texto'].endswith(' ') else '') + txt.lstrip()) if t['texto'] else txt.lstrip()
        if enfase: t['enfases'] += list(range(n0, n0 + len(txt.split())))

    def andar(s, emo, enfase=False):
        i = 0; p = 0
        while i < len(s):
            m = _ABRE.search(s, p)
            if not m: por(s[i:], emo, enfase); return
            nome = _n(m.group(1)); f = _fecha(s, m.end())
            alvo = _CMD.get(nome) or _MAPA.get(nome)
            if f < 0 or not alvo: p = m.end(); continue      # não é marcação: segue como texto
            por(s[i:m.start()], emo, enfase); dentro = s[m.end():f]
            if alvo == 'pausa':
                try: seg = max(0.0, min(1.5, float(dentro.replace(',', '.'))))
                except ValueError: seg = 0.4
                if saida: saida[-1]['pausa_s'] += seg
            elif alvo == 'enfase': andar(dentro, emo, True)
            else: andar(dentro, alvo, enfase)
            i = p = f + 1

    andar(str(texto or ''), padrao)
    for t in saida: t['texto'] = t['texto'].strip()
    return [t for t in saida if t['texto']]


def limpar(texto):
    """o texto sem a marcação (para legenda, título, contagem de palavras)."""
    return ' '.join(t['texto'] for t in interpretar(texto))


def referencia(emocao, refs):
    """a referência do banco para a emoção, na ordem de preferência; None = usa a referência base da voz."""
    for h in EMOCOES.get(emocao, EMOCOES['neutro'])['ref']:
        if h in (refs or {}): return h
    return None


_RB = None


def _rubberband():
    global _RB
    if _RB is None:
        _RB = 'rubberband' in subprocess.run(['ffmpeg', '-hide_banner', '-filters'], capture_output=True, text=True).stdout
    return _RB


def prosodia(x, sr, st=0.0, tempo=1.0, db=0.0):
    """muda tom (semitons), ritmo e volume de um vetor float32 mono; devolve o novo vetor. Preserva o timbre quando há rubberband."""
    import numpy as np
    if abs(st) < .05 and abs(tempo - 1) < .005 and abs(db) < .05 or len(x) < sr // 50: return x
    f = 2 ** (st / 12.0); fil = []
    if abs(st) >= .05 or abs(tempo - 1) >= .005:
        if _rubberband(): fil.append(f'rubberband=pitch={f:.5f}:tempo={tempo:.4f}:formant=preserved:pitchq=quality')
        else: fil += [f'asetrate={int(sr * f)}', f'aresample={sr}', f'atempo={max(0.5, min(2.0, tempo / f)):.4f}']
    if abs(db) >= .05: fil.append(f'volume={db:.2f}dB')
    r = subprocess.run(['ffmpeg', '-v', 'error', '-f', 's16le', '-ar', str(sr), '-ac', '1', '-i', '-', '-af', ','.join(fil), '-f', 's16le', '-ar', str(sr), '-ac', '1', '-'],
                       input=(np.clip(x, -1, 1) * 32767).astype('<i2').tobytes(), capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype='<i2').astype('float32') / 32768


def aplicar(x, sr, marcas, emocao, enfases=()):
    """aplica ênfase nas palavras e a prosódia da emoção no trecho; devolve (áudio, marcas com os tempos corrigidos).
    marcas: [{palavra, inicio_s, fim_s}] do trecho."""
    import numpy as np
    mm = [dict(m) for m in marcas]
    for k in sorted(set(enfases)):
        if not 0 <= k < len(mm): continue
        a = max(0, int((mm[k]['inicio_s'] - 0.012) * sr)); b = min(len(x), int((mm[k]['fim_s'] + 0.012) * sr))
        if b - a < sr // 25: continue
        p = prosodia(x[a:b], sr, **ENFASE); r = min(96, len(p) // 4)
        if r: p = p.copy(); p[:r] *= np.linspace(.35, 1, r); p[-r:] *= np.linspace(1, .35, r)
        d = (len(p) - (b - a)) / sr; x = np.concatenate([x[:a], p, x[b:]])
        mm[k]['fim_s'] += d
        for j in range(k + 1, len(mm)): mm[j]['inicio_s'] += d; mm[j]['fim_s'] += d
    e = EMOCOES.get(emocao, EMOCOES['neutro']); n0 = len(x)
    y = prosodia(x, sr, e['st'], e['tempo'], e['db'])
    if len(y) != n0 and n0:
        q = len(y) / n0
        for m in mm: m['inicio_s'] *= q; m['fim_s'] *= q
    return y, mm


if __name__ == '__main__':
    import json, sys
    print(json.dumps(interpretar(sys.argv[1] if len(sys.argv) > 1 else 'Ele apostou tudo. triste(E perdeu.) pausa(0.6) ironico(Parabéns, viu.) Mas enfase(ninguém) viu. f(x) fica.'), ensure_ascii=False, indent=1))
