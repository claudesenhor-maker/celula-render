import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

def _rodar(args):
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=180)


def _medir(arquivo):
    r = _rodar(['ffmpeg', '-hide_banner', '-threads', '1', '-i', str(arquivo),
                '-vn', '-af', 'loudnorm=I=-14:TP=-2:LRA=7:print_format=json',
                '-f', 'null', '-'])
    m = re.search(r'\{\s*"input_i".*?\}', r.stderr, re.S)
    if not m:
        raise ValueError('Medição de áudio ausente')
    dados = json.loads(m.group())
    if not all(math.isfinite(float(dados[k])) for k in
               ('input_i', 'input_tp', 'input_lra', 'input_thresh', 'target_offset')):
        raise ValueError('Medição de áudio não finita')
    return dados


def _video_hash(arquivo):
    return _rodar(['ffmpeg', '-v', 'error', '-i', str(arquivo), '-map', '0:v:0',
                   '-c', 'copy', '-f', 'hash', '-hash', 'sha256', '-']).stdout.strip()


def normalizar(origem, destino, min_duracao=10):
    origem, destino = Path(origem), Path(destino)
    if origem.resolve() == destino.resolve() or destino.exists():
        raise ValueError('Preservar original e destino existente')
    probe = json.loads(_rodar(['ffprobe', '-v', 'error', '-show_format',
                              '-show_streams', '-of', 'json', str(origem)]).stdout)
    dur = float(probe['format']['duration'])
    visual = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    if not min_duracao <= dur <= 90 or visual['height'] <= visual['width']:
        raise ValueError('Formato/duração fora da faixa de Shorts')
    antes = _medir(origem)
    if not -35 < float(antes['input_i']) < -16 or float(antes['input_tp']) > 0:
        raise ValueError('Reparo restrito a áudio baixo, finito e sem clipping')
    filtro = 'loudnorm=I=-14:TP=-2:LRA=7:linear=true:' + ':'.join(
        k+'='+antes[v] for k, v in [('measured_I', 'input_i'),
            ('measured_TP', 'input_tp'), ('measured_LRA', 'input_lra'),
            ('measured_thresh', 'input_thresh'), ('offset', 'target_offset')])
    _rodar(['ffmpeg', '-v', 'error', '-threads', '1', '-i', str(origem),
            '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'copy', '-af', filtro,
             '-ar', '48000', '-t', str(dur), '-c:a', 'aac', '-b:a', '160k',
             '-movflags', '+faststart', '-n', str(destino)])
    depois = _medir(destino)
    if not (-16 <= float(depois['input_i']) <= -12 and float(depois['input_tp']) <= -1):
        raise ValueError('Áudio reparado reprovou nova medição')
    check = _rodar(['ffmpeg', '-v', 'error', '-xerror', '-i', str(destino),
                    '-f', 'null', '-'])
    if check.stderr.strip():
        raise ValueError('Aviso na decodificação completa')
    final_probe = json.loads(_rodar(['ffprobe', '-v', 'error', '-show_format',
                                    '-of', 'json', str(destino)]).stdout)
    if abs(float(final_probe['format']['duration']) - dur) > .1:
        raise ValueError('Duração mudou durante reparo')
    original_hash, final_hash = _video_hash(origem), _video_hash(destino)
    if original_hash != final_hash:
        raise ValueError('Fluxo de vídeo mudou durante reparo')
    return {'antes': {'lufs': float(antes['input_i']), 'pico': float(antes['input_tp'])},
            'depois': {'lufs': float(depois['input_i']), 'pico': float(depois['input_tp'])},
            'duracao': dur, 'largura': visual['width'], 'altura': visual['height'],
            'video_antes_sha256': original_hash, 'video_depois_sha256': final_hash,
            'mp4_sha256': hashlib.sha256(destino.read_bytes()).hexdigest(),
            'decodificacao_completa': True}


def reparar_se_baixo(arquivo, qa, sonda):
    erros = qa.get('erros') or []
    medidas = [re.fullmatch(r'loudness (-?\d+(?:\.\d+)?) LUFS fora de -16\.\.-12', e)
               for e in erros]
    if (qa.get('aprovado') or not medidas
            or not all(m and -35 < float(m[1]) < -16 for m in medidas)):
        return qa
    arquivo = Path(arquivo)
    corrigido = Path(str(arquivo)+'.audio-t460.mp4')
    backup = Path(str(arquivo)+'.audio-original')
    if backup.exists():
        raise ValueError('Preservar backup de áudio existente')
    reparo = normalizar(arquivo, corrigido)
    final = sonda(corrigido)
    if not final.get('aprovado'):
        raise ValueError('Reparo de áudio reprovado pela sonda completa: '+str(final.get('erros')))
    arquivo.rename(backup)
    try:
        corrigido.rename(arquivo)
    except OSError:
        backup.rename(arquivo)
        raise
    return dict(final, reparo_audio_t460=reparo)
