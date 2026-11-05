import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from qa_t260.reparar_audio import reparar_se_baixo

class AudioRenderT460Test(unittest.TestCase):

    def test_erros_mistos_altos_e_duracao_nao_disparam_reparo(self):
        for erros in [['duracao fora da faixa'], ['loudness -16.4 LUFS fora de -16..-12', 'preto demais'], ['loudness -11.2 LUFS fora de -16..-12'], ['pico -0.9 dBTP > -1'], []]:
            qa = {'aprovado': False, 'erros': erros}
            with patch('qa_t260.reparar_audio.normalizar') as norm:
                self.assertEqual(reparar_se_baixo('nao-existe.mp4', qa, None), qa)
                norm.assert_not_called()

    def test_sonda_reprovada_preserva_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'final.mp4'
            src.write_bytes(b'original')

            def normalizar(a, b):
                Path(b).write_bytes(b'corrigido')
                return {'mp4_sha256': 'hash'}
            qa = {'aprovado': False, 'erros': ['loudness -16.4 LUFS fora de -16..-12']}
            with patch('qa_t260.reparar_audio.normalizar', side_effect=normalizar):
                with self.assertRaisesRegex(ValueError, 'sonda'):
                    reparar_se_baixo(src, qa, lambda _: {'aprovado': False, 'erros': ['duracao']})
            self.assertEqual(src.read_bytes(), b'original')

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg ausente')
    def test_reparo_real_so_troca_apos_sonda_completa_e_guarda_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'final.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=blue:s=108x192:r=30:d=11', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=11', '-af', 'volume=0.4', '-c:v', 'libx264', '-c:a', 'aac', str(src)], check=True)
            original = src.read_bytes()
            qa = {'aprovado': False, 'erros': ['loudness -24.0 LUFS fora de -16..-12']}
            vistos = []

            def sonda(path):
                self.assertEqual(src.read_bytes(), original)
                vistos.append(Path(path).exists())
                return {'aprovado': True, 'erros': []}
            r = reparar_se_baixo(src, qa, sonda)
            self.assertEqual(vistos, [True])
            self.assertTrue(r['aprovado'])
            self.assertEqual(Path(str(src) + '.audio-original').read_bytes(), original)
            self.assertNotEqual(src.read_bytes(), original)
            probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(src)]))
            som = next((s for s in probe['streams'] if s['codec_type'] == 'audio'))
            self.assertEqual(som['sample_rate'], '48000')
            self.assertEqual(r['reparo_audio_t460']['video_antes_sha256'], r['reparo_audio_t460']['video_depois_sha256'])
