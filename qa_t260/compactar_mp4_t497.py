"""Adequa MP4 aprovado ao limite do Storage sem aumentar a cota (T497)."""
from pathlib import Path
import shutil
import subprocess


def compactar_se_grande(arquivo, qa, sonda, limite=100 * 1024 * 1024):
    arquivo = Path(arquivo)
    if not qa.get('aprovado') or arquivo.stat().st_size <= limite:
        return qa
    backup = arquivo.with_suffix('.antes-t497.mp4')
    candidato = arquivo.with_suffix('.compacto-t497.mp4')
    if backup.exists() or candidato.exists():
        raise RuntimeError('T497: evidência anterior existente; compactação recusada')
    tamanho = arquivo.stat().st_size
    try:
        subprocess.run([
            'ffmpeg', '-nostdin', '-v', 'error', '-threads', '1', '-i', str(arquivo),
            '-map', '0:v:0', '-map', '0:a:0', '-c:v', 'libx264', '-threads', '1',
            '-crf', '20', '-preset', 'medium', '-maxrate', '10M', '-bufsize', '20M',
            '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', str(candidato),
        ], check=True, capture_output=True, timeout=900)
        if not candidato.is_file() or not 0 < candidato.stat().st_size <= limite:
            raise RuntimeError('T497: MP4 compactado ainda excede limite ou está vazio')
        novo = sonda(candidato)
        if not novo.get('aprovado'):
            raise RuntimeError('T497: sonda completa reprovou MP4 compactado')
        antes = float(qa['runner']['duracao_s'])
        depois = float(novo['runner']['duracao_s'])
        if abs(antes - depois) > .05:
            raise RuntimeError('T497: compactação alterou duração')
        # Não sobrescrever o original antes da validação completa do candidato.
        shutil.copy2(arquivo, backup)
        candidato.replace(arquivo)
        novo['compactacao_t497'] = {
            'bytes_antes': tamanho, 'bytes_depois': arquivo.stat().st_size,
            'limite_bytes': limite, 'original': str(backup), 'audio': 'copy',
        }
        return novo
    finally:
        candidato.unlink(missing_ok=True)
