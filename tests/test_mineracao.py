import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('ciclo',Path(__file__).parents[1]/'mineracao/ciclo.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class CicloTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.file=self.root/'ref.mp4';self.file.write_bytes(b'video-real-de-teste')
        self.cfg=json.loads((Path(__file__).parents[1]/'mineracao/fontes.json').read_text())
        self.source=dict(arquivo=str(self.file),tipo='teste',proveniencia={'direitos':'fixture'},hash_revisado=hashlib.sha256(self.file.read_bytes()).hexdigest(),nivel='quadros-observados',observacoes=['contato observado'],oportunidades=[dict(motor='mecanismo',tecnica='contato',proposta='conectar',lacuna='lacuna',criterios=['contato'],impacto=5,esforco=2,custo='0',confianca=.9)])
        self.cfg.update(fontes=[self.source],raizes_locais=[str(self.root)],intervalo_fonte_s=0)
        self.state=self.root/'estado'
    def tearDown(self):self.tmp.cleanup()
    def test_deduplicacao_preserva_decisao_e_mudanca_pede_revisao(self):
        a=c.executar(self.cfg,self.state);self.assertEqual(a['propostas_novas'],1)
        with c.banco(self.state/'catalogo.sqlite') as db:db.execute("UPDATE oportunidades SET estado='rejeitar'")
        b=c.executar(self.cfg,self.state);self.assertEqual(b['propostas_novas'],0)
        self.file.write_bytes(b'conteudo-alterado');c.executar(self.cfg,self.state)
        data=json.loads((self.state/'catalogo.json').read_text());self.assertEqual(len(data['backlog']),1)
        self.assertEqual(data['backlog'][0]['estado'],'rejeitar');self.assertFalse(data['backlog'][0]['evidencia_vigente'])
        self.assertEqual(json.loads(data['referencias'][0]['evidencia'])['nivel'],'metadados')
    def test_timeout_reserva_quota_persistente_sem_custo_pago(self):
        self.cfg.update(fontes=[dict(url='https://threejs.org/test',tipo='doc',proveniencia={})],max_requests_execucao=1,max_requests_dia=1)
        with patch.object(c,'remoto',side_effect=TimeoutError):
            a=c.executar(self.cfg,self.state);b=c.executar(self.cfg,self.state)
        self.assertEqual(a['requests'],1);self.assertEqual(b['requests'],0);self.assertEqual(a['estado'],'parcial')
        self.assertEqual(b['custo_api_monetario'],0)
    def test_lock_e_recuperacao_de_execucao_interrompida(self):
        self.state.mkdir()
        with c.trava(self.state):
            with self.assertRaises(BlockingIOError):c.executar(self.cfg,self.state)
        with c.banco(self.state/'catalogo.sqlite') as db:db.execute("INSERT INTO execucoes(id,inicio,estado) VALUES('old','2026-01-01','running')")
        c.executar(self.cfg,self.state)
        with c.banco(self.state/'catalogo.sqlite') as db:self.assertEqual(db.execute("SELECT estado FROM execucoes WHERE id='old'").fetchone()[0],'interrompida')
    def test_feed_so_descobre_metadados_e_respeita_limite(self):
        self.cfg['max_descobertas_execucao']=1;self.state.mkdir()
        payload=b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Light</title><link href="https://github.com/mrdoob/three.js/releases/tag/r1"/></entry><entry><title>Other</title><link href="http://localhost/private"/></entry></feed>'''
        with c.banco(self.state/'catalogo.sqlite') as db:
            stats={'descobertas_novas':0};c.descobrir(db,payload,'https://github.com/feed','abc',self.cfg,stats)
            self.assertEqual(stats['descobertas_novas'],1);self.assertEqual(db.execute('SELECT count(*) FROM oportunidades').fetchone()[0],0)
            self.assertEqual(json.loads(db.execute('SELECT evidencia FROM refs').fetchone()[0])['nivel'],'metadados')
    def test_sem_evidencia_revisada_nao_gera_proposta(self):
        del self.source['hash_revisado'];self.assertEqual(c.executar(self.cfg,self.state)['propostas_novas'],0)
    def test_experimento_idempotente_nao_permite_reescrever_decisao(self):
        import subprocess,sys
        c.executar(self.cfg,self.state)
        with c.banco(self.state/'catalogo.sqlite') as db:oid=db.execute('SELECT id FROM oportunidades').fetchone()[0]
        p=self.root/'resultado.json';data=dict(id='ex1',oportunidade_id=oid,decisao='candidato',evidencias=['a.png'],metricas={'ms':10})
        p.write_text(json.dumps(data));cmd=[sys.executable,c.__file__,'--estado',str(self.state),'--experimento',str(p)]
        for _ in range(2):self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        data['decisao']='rejeitar';p.write_text(json.dumps(data));self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        with c.banco(self.state/'catalogo.sqlite') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM experimentos').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT estado FROM oportunidades').fetchone()[0],'candidato')
    def test_importacao_canais_idempotente_sem_aprovacao_visual(self):
        import subprocess,sys
        c.executar(self.cfg,self.state)
        script=Path(c.__file__).with_name('importar_triagem.py')
        cmd=[sys.executable,str(script),'--estado',str(self.state)]
        a=json.loads(subprocess.check_output(cmd));b=json.loads(subprocess.check_output(cmd))
        self.assertEqual(a['referencias_novas'],12);self.assertEqual(b['referencias_novas'],0)
        self.assertFalse(a['coleta_canais_ativada'])
        with c.banco(self.state/'catalogo.sqlite') as db:
            refs=db.execute("SELECT evidencia FROM refs WHERE tipo='canal-triagem'").fetchall()
            self.assertEqual(len(refs),12)
            self.assertTrue(all(json.loads(r[0])['observacoes']==[] for r in refs))
            self.assertEqual(db.execute('SELECT count(*) FROM oportunidades').fetchone()[0],1)
    def test_origem_canonica_remove_tracking_e_recusa_credenciais(self):
        self.assertEqual(c.canonical('https://THREEJS.org/a/?utm_source=x&b=1#x'),'https://threejs.org/a?b=1')
        with self.assertRaises(ValueError):c.canonical('https://user:secret@host/a')
if __name__=='__main__':unittest.main()
