import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from qualidade_render import codificacao
from qualidade_render import conferir_quadros
import json
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
from PIL import Image

class QualidadeRender(unittest.TestCase):
    def test_qualidade_respeita_orcamento_e_preserva_override(self):
        p = codificacao({}, 60)
        self.assertEqual(p['crf'], '20')
        self.assertLessEqual(float(p['maxrate'][:-1])*1_000_000*60/8,45*1024*1024)
        self.assertEqual(codificacao({'crf': 18}, 30)['crf'], '18')
        self.assertLess(float(codificacao({},600)['maxrate'][:-1]),float(p['maxrate'][:-1]))
    def test_configuracoes_invalidas_nao_chegam_ao_encoder(self):
        for crf in [True,-1,50,'20',float('nan')]:
            with self.assertRaises(ValueError):codificacao({'crf':crf},30)
        with self.assertRaises(ValueError):codificacao({},0)

    def quadros(self, pasta):
        for i in range(3):
            Image.new('RGB', (120, 200), (i * 50, 90, 120)).save(Path(pasta) / f'{i:05d}.png')

    def test_previa_legada_registra_tempo_e_nao_finge_revisao_de_ia(self):
        with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, {}, clear=True):
            self.quadros(pasta)
            saida = str(Path(pasta) / 'ensaio.mp4')
            relatorio = conferir_quadros({}, pasta, 3, 2, saida)
            rodada = relatorio['historico'][0]
            self.assertEqual(rodada['modo'], 'tecnico-local')
            self.assertNotIn('revisao', rodada)
            self.assertEqual(rodada['quadros'][-1]['t'], 1)
            self.assertTrue(Path(saida + '.direcao.json').exists())
            self.assertEqual(len(list(Path(saida + '.previas').glob('*.jpg'))), 3)

    def test_visao_legada_preserva_credenciais_e_reprovacao_interrompe(self):
        recebidos = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                dados = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                recebidos.append(dados)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'aprovado': len(recebidos) == 1,
                                            'problemas': [], 'correcoes': []}).encode())

            def log_message(self, *args):
                pass

        servidor = HTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=servidor.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as pasta, patch.dict(os.environ, {'VIDEO_REVISOR_URL': f'http://127.0.0.1:{servidor.server_port}'}, clear=True):
                self.quadros(pasta)
                spec = {'voz': {'token': 'NAO_ENVIAR'}, 'trechos': [{'texto': 'Olá', 'acao': 'aponta'}]}
                saida = str(Path(pasta) / 'ensaio.mp4')
                self.assertTrue(conferir_quadros(spec, pasta, 3, 2, saida)['historico'][0]['revisao']['aprovado'])
                self.assertNotIn('NAO_ENVIAR', json.dumps(recebidos))
                self.assertTrue(recebidos[0]['quadros'][0]['imagem'].startswith('data:image/jpeg;base64,'))
                with self.assertRaisesRegex(ValueError, 'não aprovada'):
                    conferir_quadros(spec, pasta, 3, 2, saida)
                self.assertIn('erro', json.loads(Path(saida + '.direcao.json').read_text())['historico'][0])
        finally:
            servidor.shutdown()
            servidor.server_close()
            thread.join(timeout=2)
