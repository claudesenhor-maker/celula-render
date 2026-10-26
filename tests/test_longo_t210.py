import tempfile
import unittest
from pathlib import Path

import longo as ml


def spec_ok(n=4, short_s=40, ctx_palavras=120):
    return {
        "tipo": "longo", "fila_id": "piloto-t210", "cell_id": "11111111-1111-4111-8111-111111111111",
        "idioma": "pt-BR", "titulo": "Histórias do PAPERCUT",
        "shorts": [{"video_url": f"https://x/{i}.mp4", "titulo": f"Caso {i}", "duracao_s": short_s}
                   for i in range(1, n + 1)],
        "contextos": [{"texto": " ".join(["palavra"] * ctx_palavras), "titulo": f"Caso {i}",
                       "imagem_url": None} for i in range(1, n + 1)],
    }


class ValidarSpec(unittest.TestCase):
    def test_aceita_spec_valido(self):
        self.assertEqual(len(ml.validar_spec(spec_ok())["shorts"]), 4)

    def test_recusa_tipo_errado(self):
        s = spec_ok(); s["tipo"] = "short"
        with self.assertRaises(ml.ErroLongo):
            ml.validar_spec(s)

    def test_recusa_contextos_diferentes_dos_shorts(self):
        s = spec_ok(); s["contextos"].pop()
        with self.assertRaises(ml.ErroLongo):
            ml.validar_spec(s)

    def test_recusa_short_sem_url_ou_duracao(self):
        s = spec_ok(); s["shorts"][0]["video_url"] = ""
        with self.assertRaises(ml.ErroLongo):
            ml.validar_spec(s)
        s = spec_ok(); s["shorts"][1]["duracao_s"] = 0
        with self.assertRaises(ml.ErroLongo):
            ml.validar_spec(s)


class Tempos(unittest.TestCase):
    def test_contexto_minimo_50_por_cento(self):
        segs = ml.planejar_tempos([40] * 6, [50] * 6)
        self.assertAlmostEqual(sum(s["dur"] for s in segs), 540)
        self.assertGreaterEqual(ml.fracao_contexto(segs), 0.5)

    def test_recusa_contexto_abaixo_de_50(self):
        with self.assertRaises(ml.ErroLongo):
            ml.planejar_tempos([40] * 8, [20] * 8)

    def test_recusa_fora_de_480_900(self):
        with self.assertRaises(ml.ErroLongo):
            ml.planejar_tempos([30] * 3, [40] * 3)      # 210 s
        with self.assertRaises(ml.ErroLongo):
            ml.planejar_tempos([60] * 10, [60] * 10)    # 1200 s

    def test_alterna_short_e_contexto(self):
        segs = ml.planejar_tempos([40] * 6, [50] * 6)
        self.assertEqual([s["tipo"] for s in segs[:4]], ["short", "contexto", "short", "contexto"])


class Capitulos(unittest.TestCase):
    def test_marcas_e_formato_youtube(self):
        segs = ml.planejar_tempos([40] * 6, [50] * 6)
        titulos = [f"Caso {i}" for i in range(1, 7)]
        caps = ml.capitulos(segs, titulos)
        self.assertEqual(caps[0][0], 0)
        self.assertEqual(caps[1][0], 90)
        txt = ml.formatar_capitulos(caps)
        self.assertTrue(txt.splitlines()[0].startswith("0:00 "))
        self.assertIn("1:30 Caso 2", txt)

    def test_hora_acima_de_uma_hora(self):
        self.assertEqual(ml.timestamp(3725), "1:02:05")


class Comandos(unittest.TestCase):
    def test_short_mudo_recebe_silencio_sem_referenciar_audio_inexistente(self):
        cmd = ' '.join(ml.cmd_short('mudo.mp4', 'saida.mp4', tem_audio=False))
        self.assertIn('anullsrc', cmd)
        self.assertNotIn('[0:a]', cmd)
        self.assertIn('-shortest', cmd)

    def test_short_vertical_no_centro_com_fundo_desfocado(self):
        cmd = " ".join(ml.cmd_short("in.mp4", "out.mp4"))
        self.assertIn("boxblur", cmd)
        self.assertIn("1920:1080", cmd)
        self.assertIn("overlay=(W-w)/2:(H-h)/2", cmd)

    def test_contexto_usa_cartaz_legenda_e_audio(self):
        legendas = [(0.0, 2.0, "/tmp/l1.txt")]
        cmd = " ".join(ml.cmd_contexto("img.png", "voz.wav", "out.mp4", 10.0, legendas, fonte="f.ttf"))
        self.assertIn("-loop 1", cmd)
        self.assertIn("drawtext", cmd)
        self.assertIn("between(t,0.000,2.000)", cmd)
        self.assertIn("voz.wav", cmd)

    def test_cartaz_gerado_quando_sem_imagem(self):
        cmd = " ".join(ml.cmd_cartaz("t.txt", "cartaz.png", fonte="f.ttf"))
        self.assertIn("color=", cmd)
        self.assertIn("drawtext", cmd)

    def test_loudnorm_14(self):
        self.assertIn("I=-14", ml.filtro_loudnorm())
        medidas = {"input_i": "-20.1", "input_tp": "-3.0", "input_lra": "5.0",
                   "input_thresh": "-30.5", "target_offset": "0.4"}
        self.assertIn("measured_I=-20.1", ml.filtro_loudnorm(medidas))

    def test_parse_loudnorm(self):
        saida = 'ruido\n{\n\t"input_i" : "-20.10",\n\t"input_tp" : "-3.00",\n}\n'
        self.assertEqual(ml.parse_loudnorm(saida)["input_i"], "-20.10")
        with self.assertRaises(ml.ErroLongo):
            ml.parse_loudnorm("sem json")

    def test_concat_lista_escapa_aspas(self):
        txt = ml.lista_concat(["/tmp/a'b.mp4", "/tmp/c.mp4"])
        self.assertIn("file '/tmp/a'\\''b.mp4'", txt)


class Legendas(unittest.TestCase):
    def test_frases_cobrem_a_duracao_proporcional(self):
        trechos = ml.dividir_legenda("Um dois tres. Quatro cinco seis sete oito.", 9.0)
        self.assertAlmostEqual(trechos[0][0], 0.0)
        self.assertAlmostEqual(trechos[-1][1], 9.0)
        self.assertGreaterEqual(len(trechos), 2)
        for a, b, _ in trechos:
            self.assertLess(a, b)


class Saida(unittest.TestCase):
    def test_valida_16_9_e_duracao(self):
        ml.validar_saida({"largura": 1920, "altura": 1080, "duracao_s": 600})
        with self.assertRaises(ml.ErroLongo):
            ml.validar_saida({"largura": 1080, "altura": 1920, "duracao_s": 600})
        with self.assertRaises(ml.ErroLongo):
            ml.validar_saida({"largura": 1920, "altura": 1080, "duracao_s": 300})


class Orquestracao(unittest.TestCase):
    def test_executar_com_dependencias_injetadas(self):
        chamadas = []

        def run(cmd, **kw):
            chamadas.append(cmd)
            saida = cmd[-1]
            if saida.endswith((".mp4", ".png", ".wav")):
                Path(saida).write_bytes(b"x")
            class R:  # noqa: D401
                stderr = '{"input_i":"-20.0","input_tp":"-2.0","input_lra":"5","input_thresh":"-30","target_offset":"0"}'
                stdout = ""
                returncode = 0
            return R()

        def baixar(url, destino):
            Path(destino).write_bytes(b"v")

        def sintetizar(texto, cfg, destino):
            Path(destino).write_bytes(b"w")
            return 50.0

        def sondar(path):
            return {"largura": 1920, "altura": 1080, "duracao_s": 540.0}

        with tempfile.TemporaryDirectory() as d:
            r = ml.executar(spec_ok(6, 40), d, run=run, baixar=baixar, sintetizar=sintetizar, sondar=sondar,
                            fonte="f.ttf", duracoes_short=None)
        self.assertTrue(r["saida"].endswith("longo.mp4"))
        self.assertEqual(len(r["capitulos"]), 6)
        self.assertTrue(r["descricao"].startswith("0:00 "))
        self.assertGreaterEqual(r["fracao_contexto"], 0.5)
        self.assertTrue(any("loudnorm" in " ".join(c) for c in chamadas))


class RodarNoJob(unittest.TestCase):
    def test_sonda_piloto_existente_sem_render_ou_fila(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        job = SimpleNamespace(SB='https://sb', BUCKET='bucket',
            UUID_RE=__import__('re').compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-'),
            requests=SimpleNamespace(get=Mock(return_value=SimpleNamespace(
                content=b'mp4', raise_for_status=lambda: None))),
            subir=Mock(return_value='https://sb/sonda.json'), avisar=Mock(), atualizar_fila=Mock())
        s = {'tipo':'longo', 'piloto':True, 'verificar_piloto_url':
             'https://sb/storage/v1/object/public/bucket/longos/sem-id.mp4'}
        with tempfile.TemporaryDirectory() as d:
            r = ml.conferir_piloto(s, 'teste-sonda-t210', job, d,
                sondar=lambda _: {'largura':1920,'altura':1080,'duracao_s':513.9,
                                  'tem_audio':True,'aspecto':'16:9'})
        self.assertEqual(r['aspecto'], '16:9')
        job.atualizar_fila.assert_not_called()
        self.assertTrue(job.subir.call_args.args[1].endswith('.json'))
        job.avisar.assert_called_once()
        for mudanca in ({'piloto':False}, {'verificar_piloto_url':'https://outro/longos/a.mp4'}):
            with tempfile.TemporaryDirectory() as d, self.assertRaises(ml.ErroLongo):
                ml.conferir_piloto(dict(s,**mudanca), 'teste-sonda-t210', job, d)

    def test_rodar_sobe_atualiza_fila_e_avisa(self):
        eventos = []

        class FakeJob:
            UUID_RE = __import__("re").compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")

            @staticmethod
            def subir(local, remoto, mime="video/mp4"):
                eventos.append(("subir", remoto))
                return "https://sb/" + remoto

            @staticmethod
            def atualizar_fila(fila_id, campos):
                self.assertEqual(campos['roteiro_json']['descricao'], '0:00 A')
                self.assertEqual(campos['roteiro_json']['capitulos'], [(0, 'A')])
                self.assertEqual(campos['roteiro_json']['spec_longo']['tipo'], 'longo')
                eventos.append(("fila", fila_id, campos["status"], campos["video_url"]))

            @staticmethod
            def avisar(payload):
                eventos.append(("aviso", payload))

        recibo = {"saida": "/tmp/x.mp4", "duracao_s": 540.0, "largura": 1920, "altura": 1080,
                  "fracao_contexto": 0.55, "capitulos": [(0, "A")], "descricao": "0:00 A", "lufs_alvo": -14}
        spec = spec_ok()
        spec["fila_id"] = "22222222-2222-4222-8222-222222222222"
        ml.rodar(spec, spec["fila_id"], 0, FakeJob, montar=lambda *a, **k: recibo)
        self.assertEqual(eventos[0], ("subir", "longos/22222222-2222-4222-8222-222222222222.mp4"))
        self.assertEqual(eventos[1][2], "pronto_para_publicar")
        self.assertEqual(eventos[2][1]["status"], "ok")
        self.assertEqual(eventos[2][1]["tipo"], "longo")
        self.assertEqual(eventos[2][1]["descricao"], "0:00 A")

    def test_piloto_nao_usa_a_fila(self):
        eventos = []

        class FakeJob:
            UUID_RE = __import__("re").compile(r"^[0-9a-f]{8}-")

            @staticmethod
            def subir(local, remoto, mime="video/mp4"):
                return "https://sb/" + remoto

            @staticmethod
            def atualizar_fila(*a):
                eventos.append("fila")

            @staticmethod
            def avisar(payload):
                eventos.append(payload["status"])

        recibo = {"saida": "x", "duracao_s": 540.0, "largura": 1920, "altura": 1080,
                  "fracao_contexto": 0.55, "capitulos": [], "descricao": "", "lufs_alvo": -14}
        spec = spec_ok()
        spec["piloto"] = True
        ml.rodar(spec, "piloto-t210", 0, FakeJob, montar=lambda *a, **k: recibo)
        self.assertEqual(eventos, ["ok"])


if __name__ == "__main__":
    unittest.main()
