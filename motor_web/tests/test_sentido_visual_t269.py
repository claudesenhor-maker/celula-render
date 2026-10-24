"""Testes portáveis, também enviados a celula-render/motor_web/tests/."""
import copy
from pathlib import Path
import sys
import unittest

try:
    from videos_realistas.sentido_visual import corrigir
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from sentido_visual import corrigir


class SentidoRenderT269(unittest.TestCase):
    def test_nevoa_real_nao_vira_raio(self):
        c = {'texto':'For fourteen months, fog hid Kiska. Pilots bombed a coastline they could rarely see.',
             'objeto':'raio', 'acao':'olha', 'cenario':'ceu_estrelado', 'hora':'tempestade'}
        antes = copy.deepcopy(c)
        self.assertEqual(corrigir('silhueta', [c]),
                         [{'indice':0, 'campo':'objeto', 'antes':'raio', 'depois':'nevoa'}])
        self.assertEqual(c, dict(antes, objeto='nevoa'))

    def test_negacao_e_outros_estilos_preservados(self):
        for estilo, texto in [('silhueta','There was no fog.'), ('silhueta','What if it snowed?'),
                               ('silhueta','Fog and snow hid the coast.'), ('pixel','Fog hid Kiska.'),
                               ('mangueira','Fog hid Kiska.'), ('recorte','Fog hid Kiska.')]:
            c = [{'texto':texto, 'objeto':'raio'}]
            self.assertEqual(corrigir(estilo, c), [])
            self.assertEqual(c[0]['objeto'], 'raio')

    def test_correcao_idempotente(self):
        c = [{'texto':'La niebla cubrió el puerto.', 'objeto':'neve'}]
        self.assertEqual(len(corrigir('silhueta',c)), 1)
        self.assertEqual(c[0]['objeto'], 'nevoa')
        self.assertEqual(corrigir('silhueta',c), [])


if __name__ == '__main__':
    unittest.main()
