"""T503 (13/11): encerramento de conversao do quiz (ODD ONE OUT). A ultima cena ganha CTA_QUIZ_S segundos e o
cronometro/"plim" do ultimo nivel recuam o mesmo tanto (o som continua batendo com a imagem)."""
import importlib.util
import os
import sys
import tempfile
import types
import unittest

AQUI = os.path.dirname(os.path.abspath(__file__))


def carregar():
    if "sfx" not in sys.modules:                           # o teste nao mistura audio
        falso = types.ModuleType("sfx"); falso.SR = 48000; sys.modules["sfx"] = falso
    spec = importlib.util.spec_from_file_location("montar_web_t503", os.path.join(AQUI, "..", "montar_web.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class QuizCTA(unittest.TestCase):
    def setUp(self):
        self.m = carregar()
        self.m._silencio = lambda caminho, dur: caminho

    def spec(self, estilo="quiz"):
        return {"estilo": estilo, "narrado": False, "cenas": [{"dur_s": 4}, {"dur_s": 5}, {"dur_s": 6}]}

    def test_ultima_cena_ganha_o_encerramento(self):
        s = self.spec()
        self.m.linha_do_tempo(s, tempfile.mkdtemp(), "mudo")
        self.assertEqual(s["cta_s"], self.m.CTA_QUIZ_S)
        self.assertAlmostEqual(s["dur_s"], 15 + self.m.CTA_QUIZ_S, places=3)
        self.assertAlmostEqual(s["cenas"][-1]["fim"] - s["cenas"][-1]["ini"], 6 + self.m.CTA_QUIZ_S, places=3)

    def test_plim_do_ultimo_nivel_recua_e_ha_pops_no_encerramento(self):
        s = self.spec()
        self.m.linha_do_tempo(s, tempfile.mkdtemp(), "mudo")
        ev = self.m.eventos_sonoros(s)
        plims = sorted(e["t"] for e in ev if e["nome"] == "plim")
        ultima = s["cenas"][-1]
        self.assertAlmostEqual(plims[-1], ultima["fim"] - s["cta_s"] - 1.3 + 0.05, places=3)
        self.assertTrue(all(e["t"] < ultima["fim"] - s["cta_s"] - 1.3 for e in ev if e["nome"] == "clique" and e["t"] > ultima["ini"]))
        pops = [e for e in ev if e["nome"] == "pop" and e["t"] >= ultima["fim"] - s["cta_s"]]
        self.assertEqual(len(pops), 3)

    def test_outros_estilos_nao_mudam(self):
        s = self.spec("escala")
        self.m.linha_do_tempo(s, tempfile.mkdtemp(), "mudo")
        self.assertNotIn("cta_s", s)
        self.assertAlmostEqual(s["dur_s"], 15, places=3)


if __name__ == "__main__":
    unittest.main()
