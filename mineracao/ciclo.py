#!/usr/bin/env python3
"""Coleta limitada, catálogo SQLite e propostas declarativas. Nunca executa fontes."""
import argparse
import contextlib
import datetime as dt
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import signal
import sys
import sqlite3
import time
import urllib.parse
import urllib.request
import urllib.error
import uuid
import xml.etree.ElementTree as ET

UTC = dt.timezone.utc

def agora():
    return dt.datetime.now(UTC).isoformat()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def canonical(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme != 'https' or u.username or u.password or u.port not in (None, 443):
        raise ValueError('fonte remota exige HTTPS sem credenciais/porta alternativa')
    q = [(k,v) for k,v in urllib.parse.parse_qsl(u.query) if not k.startswith('utm_')]
    return urllib.parse.urlunsplit(('https', u.netloc.lower(), u.path.rstrip('/') or '/', urllib.parse.urlencode(sorted(q)), ''))

SCHEMA = '''
CREATE TABLE IF NOT EXISTS refs (
 id TEXT PRIMARY KEY, origem TEXT UNIQUE NOT NULL, primeiro_em TEXT NOT NULL,
 ultimo_em TEXT, tentativa_em TEXT, hash TEXT, titulo TEXT, tipo TEXT NOT NULL,
 proveniencia TEXT NOT NULL, evidencia TEXT NOT NULL DEFAULT '{}', erro TEXT);
CREATE TABLE IF NOT EXISTS oportunidades (
 id TEXT PRIMARY KEY, ref_id TEXT NOT NULL REFERENCES refs(id), motor TEXT NOT NULL,
 tecnica TEXT NOT NULL, proposta TEXT NOT NULL, lacuna TEXT NOT NULL,
 criterios TEXT NOT NULL, impacto INTEGER NOT NULL, esforco INTEGER NOT NULL,
 custo TEXT NOT NULL, confianca REAL NOT NULL, evidencia_hash TEXT NOT NULL,
 estado TEXT NOT NULL DEFAULT 'proposta', criado_em TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS execucoes (
 id TEXT PRIMARY KEY, inicio TEXT NOT NULL, fim TEXT, estado TEXT NOT NULL,
 resumo TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS requests (dia TEXT NOT NULL, em TEXT NOT NULL, fonte TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS experimentos (
 id TEXT PRIMARY KEY, oportunidade_id TEXT NOT NULL REFERENCES oportunidades(id),
 em TEXT NOT NULL, resultado TEXT NOT NULL);
'''

def banco(path):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(SCHEMA)
    return db

class Redirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        url = canonical(newurl)
        if urllib.parse.urlsplit(url).hostname not in self.hosts:
            raise ValueError('redirecionamento fora da lista de hosts')
        return super().redirect_request(req, fp, code, msg, headers, url)

def remoto(url, cfg, timeout):
    url = canonical(url)
    if urllib.parse.urlsplit(url).hostname not in cfg['hosts']:
        raise ValueError('host não autorizado na configuração')
    op = urllib.request.build_opener(Redirect(cfg['hosts']))
    with op.open(urllib.request.Request(url, headers={'User-Agent':'videos-auto-reference-catalog/1.0', 'Accept':'application/vnd.github+json' if urllib.parse.urlsplit(url).hostname=='api.github.com' else 'text/html'}), timeout=timeout) as r:
        data = r.read(cfg['max_bytes_resposta']+1)
        if len(data)>cfg['max_bytes_resposta']:
            raise ValueError('resposta excedeu limite de bytes')
        text = data.decode('utf-8',errors='replace')
        title = re.search(r'<title[^>]*>(.*?)</title>',text,re.I|re.S)
        return digest(data), html.unescape(re.sub('<[^>]+>','',title[1])).strip()[:250] if title else url, len(data), data

def descobrir_github(db, payload, origem, sha, cfg, stats):
    # API primária de releases limitada por per_page; só metadados, nunca código.
    items=json.loads(payload)
    if not isinstance(items,list):raise ValueError('feed GitHub inválido')
    feed=ET.Element('{http://www.w3.org/2005/Atom}feed')
    for item in items[:20]:
        entry=ET.SubElement(feed,'{http://www.w3.org/2005/Atom}entry')
        ET.SubElement(entry,'{http://www.w3.org/2005/Atom}title').text=str(item.get('name',''))
        ET.SubElement(entry,'{http://www.w3.org/2005/Atom}link',href=str(item.get('html_url','')))
        ET.SubElement(entry,'{http://www.w3.org/2005/Atom}updated').text=str(item.get('published_at',''))
    descobrir(db,ET.tostring(feed),origem,sha,cfg,stats)

def descobrir(db, payload, origem, sha, cfg, stats):
    ns={'a':'http://www.w3.org/2005/Atom'}
    feed=ET.fromstring(payload)
    for entry in feed.findall('a:entry',ns):
        if stats['descobertas_novas']>=cfg['max_descobertas_execucao']:break
        link=next((e.get('href') for e in entry.findall('a:link',ns) if e.get('rel','alternate')=='alternate'),None)
        if not link:continue
        try:url=canonical(link)
        except ValueError:continue
        if urllib.parse.urlsplit(url).hostname not in cfg['hosts']:continue
        title=(entry.findtext('a:title','',ns) or '')[:250]
        evid={'nivel':'metadados','observacoes':[], 'feed':origem, 'feed_hash':sha,
              'publicado_em':entry.findtext('a:updated','',ns),'revisao_pendente':'inspecionar técnica e exemplos antes de propor experimento'}
        cur=db.execute('INSERT OR IGNORE INTO refs(id,origem,primeiro_em,ultimo_em,titulo,tipo,proveniencia,evidencia) VALUES(?,?,?,?,?,?,?,?)',
          (digest(url.encode())[:24],url,agora(),agora(),title,'descoberta-feed',json.dumps({'origem':origem,'direitos':'link/metadados; nenhum asset copiado'}),json.dumps(evid,ensure_ascii=False)))
        stats['descobertas_novas']+=cur.rowcount
    db.commit()

def local(source, cfg, deadline):
    p = Path(source['arquivo']).resolve()
    if not any(p.is_relative_to(Path(root).resolve()) for root in cfg['raizes_locais']):
        raise ValueError('arquivo fora das raízes autorizadas')
    if p.stat().st_size>cfg['max_bytes_arquivo']:
        raise ValueError('arquivo excedeu limite')
    h = hashlib.sha256()
    with p.open('rb') as f:
        while data := f.read(1024*1024):
            if time.monotonic()>deadline:
                raise TimeoutError('prazo da execução')
            h.update(data)
    return h.hexdigest(),p.name,p.stat().st_size

def coletar(db, source, cfg, deadline, stats):
    origem = canonical(source['url']) if 'arquivo' not in source else Path(source['arquivo']).resolve().as_uri()
    rid = digest(origem.encode())[:24]
    db.execute('INSERT OR IGNORE INTO refs(id,origem,primeiro_em,tipo,proveniencia) VALUES(?,?,?,?,?)',
               (rid,origem,agora(),source['tipo'],json.dumps(source['proveniencia'],ensure_ascii=False)))
    row = db.execute('SELECT * FROM refs WHERE id=?',(rid,)).fetchone()
    if row['tentativa_em'] and (dt.datetime.now(UTC)-dt.datetime.fromisoformat(row['tentativa_em'])).total_seconds()<(cfg['intervalo_falha_s'] if row['erro'] else cfg['intervalo_fonte_s']):
        stats['ignoradas_intervalo']+=1
        return
    db.execute('UPDATE refs SET tentativa_em=?,proveniencia=? WHERE id=?',(agora(),json.dumps(source['proveniencia'],ensure_ascii=False),rid));db.commit()
    erro = None
    for tentativa in range(cfg['retries']+1):
        remaining=deadline-time.monotonic()
        if remaining<1:
            erro='prazo da execução';break
        try:
            if 'arquivo' in source:
                sha,title,size=local(source,cfg,deadline)
            else:
                dia=dt.datetime.now(UTC).date().isoformat()
                used=db.execute('SELECT count(*) FROM requests WHERE dia=?',(dia,)).fetchone()[0]
                if used>=cfg['max_requests_dia'] or stats['requests']>=cfg['max_requests_execucao']:
                    erro='quota de requests';break
                # Reserva durável ANTES da chamada: timeout/crash também consome quota.
                db.execute('INSERT INTO requests VALUES(?,?,?)',(dia,agora(),origem));db.commit()
                stats['requests']+=1
                sha,title,size,payload=remoto(origem,cfg,min(cfg['timeout_s'],remaining))
                if source['tipo']=='feed-atom':
                    descobrir(db,payload,origem,sha,cfg,stats)
                elif source['tipo']=='feed-github':
                    descobrir_github(db,payload,origem,sha,cfg,stats)
            expected=source.get('hash_revisado')
            evid={'nivel':'metadados', 'observacoes':[], 'timecodes':source.get('timecodes',[]), 'quadros':source.get('quadros',[])}
            if expected and expected==sha:
                evid.update(nivel=source.get('nivel','documentacao-revisada'),observacoes=source.get('observacoes',[]))
            elif expected:
                evid['revisao_pendente']='conteúdo mudou desde a análise humana/agente'
            db.execute('UPDATE refs SET ultimo_em=?,hash=?,titulo=?,evidencia=?,erro=NULL WHERE id=?',
                       (agora(),sha,title,json.dumps(evid,ensure_ascii=False),rid));db.commit()
            stats['coletadas']+=1;stats['bytes_lidos']+=size
            if evid['observacoes']:
                for op in source.get('oportunidades',[]):
                    if stats['propostas_novas']>=cfg['max_propostas_execucao']:break
                    oid=digest((rid+'|'+op['motor']+'|'+op['tecnica']).encode())[:24]
                    cur=db.execute('''INSERT OR IGNORE INTO oportunidades
                       (id,ref_id,motor,tecnica,proposta,lacuna,criterios,impacto,esforco,custo,confianca,evidencia_hash,criado_em)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                       (oid,rid,op['motor'],op['tecnica'],op['proposta'],op['lacuna'],json.dumps(op['criterios'],ensure_ascii=False),
                        op['impacto'],op['esforco'],op['custo'],op['confianca'],sha,agora()))
                    stats['propostas_novas']+=cur.rowcount
                db.commit()
            return
        except Exception as e:
            # Não armazena mensagens de transporte que possam incluir informações sensíveis.
            erro=type(e).__name__ + (':'+str(e.code) if isinstance(e,urllib.error.HTTPError) else '')
            if tentativa<cfg['retries'] and deadline-time.monotonic()>2:
                time.sleep(min(2**tentativa,2))
    stats['falhas']+=1
    db.execute('UPDATE refs SET erro=? WHERE id=?',(erro,rid));db.commit()

def exportar(db, root):
    refs=[dict(x) for x in db.execute('SELECT * FROM refs ORDER BY origem')]
    ops=[dict(x) for x in db.execute('''SELECT o.*,r.origem,r.evidencia,r.hash AS hash_atual FROM oportunidades o JOIN refs r ON r.id=o.ref_id
        ORDER BY impacto*1.0/esforco DESC,confianca DESC,id''')]
    for op in ops:
        op['evidencia_vigente']=op['evidencia_hash']==op['hash_atual']
    result={'gerado_em':agora(),'referencias':refs,'backlog':ops,
            'experimentos':[dict(x) for x in db.execute('SELECT * FROM experimentos ORDER BY em')]}
    p=root/'catalogo.json.tmp';p.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');p.replace(root/'catalogo.json')
    md=['# Backlog do catálogo','', 'Propostas declarativas; promoção depende de comparação e revisão.','']
    for op in ops:
        md.extend([f"## {op['motor']} — {op['tecnica']} ({op['estado']})",'',f"ID: `{op['id']}` · impacto {op['impacto']}/5 · esforço {op['esforco']}/5 · confiança {op['confianca']}",
                   '',op['lacuna'], '',op['proposta'],'',f"Origem: {op['origem']}",f"Custo: {op['custo']}", '',*['- '+c for c in json.loads(op['criterios'])], ''])
    tmp=root/'backlog.md.tmp';tmp.write_text('\n'.join(md));tmp.replace(root/'backlog.md')

@contextlib.contextmanager
def trava(root):
    with (root/'ciclo.lock').open('w') as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield

def validar(cfg):
    for k,low,high in [('max_execucao_s',1,600),('max_fontes',1,50),('max_requests_execucao',1,30),('max_requests_dia',1,100),
                       ('retries',0,2),('timeout_s',1,30),('max_propostas_execucao',1,50),('max_descobertas_execucao',1,20),('intervalo_fonte_s',0,604800),('intervalo_falha_s',0,86400),
                       ('max_bytes_resposta',1024,2000000),('max_bytes_arquivo',1024,200000000),('max_storage_bytes',1000000,1000000000)]:
        if type(cfg.get(k)) is not int or not low<=cfg[k]<=high:raise ValueError('limite inválido: '+k)

def executar(cfg,root):
    validar(cfg);root.mkdir(parents=True,exist_ok=True)
    with trava(root):
        if sum(p.stat().st_size for p in root.rglob('*') if p.is_file())>cfg['max_storage_bytes']:
            raise ValueError('armazenamento excedido: arquive execuções antigas')
        with banco(root/'catalogo.sqlite') as db:
            # Com o lock exclusivo, um registro running anterior só pode ser interrompido.
            db.execute("UPDATE execucoes SET estado='interrompida',fim=? WHERE estado='running'",(agora(),));db.commit()
            run=uuid.uuid4().hex;inicio=agora();db.execute('INSERT INTO execucoes(id,inicio,estado) VALUES(?,?,?)',(run,inicio,'running'));db.commit()
            stats=dict(requests=0,coletadas=0,bytes_lidos=0,falhas=0,ignoradas_intervalo=0,propostas_novas=0,custo_api_monetario=0,descobertas_novas=0)
            deadline=time.monotonic()+cfg['max_execucao_s']
            # Menos recentemente tentadas primeiro evita fome quando há muitas fontes.
            times={r['origem']:r['tentativa_em'] or '' for r in db.execute('SELECT origem,tentativa_em FROM refs')}
            def key(s):return times.get(Path(s['arquivo']).resolve().as_uri() if 'arquivo' in s else canonical(s['url']),'')
            for source in sorted(cfg['fontes'],key=key)[:cfg['max_fontes']]:
                if time.monotonic()>=deadline:stats['prazo_excedido']=True;break
                coletar(db,source,cfg,deadline,stats)
            estado='parcial' if stats['falhas'] or stats.get('prazo_excedido') else 'ok'
            db.execute('UPDATE execucoes SET fim=?,estado=?,resumo=? WHERE id=?',(agora(),estado,json.dumps(stats),run));db.commit()
            exportar(db,root)
            (root/'execucoes').mkdir(exist_ok=True)
            report=dict(id=run,inicio=inicio,fim=agora(),estado=estado,**stats)
            (root/'execucoes'/f'{run}.json').write_text(json.dumps(report,indent=2)+'\n')
            return report

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default=str(Path(__file__).with_name('fontes.json')));ap.add_argument('--estado',required=True)
    ap.add_argument('--experimento',help='JSON local com id, oportunidade_id, decisao, evidencias e métricas');args=ap.parse_args()
    root=Path(args.estado).resolve()
    if args.experimento:
        data=json.loads(Path(args.experimento).read_text())
        if data.get('decisao') not in ['manter-em-revisao','rejeitar','candidato'] or not data.get('evidencias') or not data.get('metricas'):
            raise ValueError('experimento exige decisão, evidências e métricas')
        with trava(root), banco(root/'catalogo.sqlite') as db:
            # Só resultados locais explícitos alteram o estado; nenhuma fonte pode promover código.
            old=db.execute('SELECT resultado FROM experimentos WHERE id=?',(data['id'],)).fetchone()
            if old and json.loads(old[0])!=data:raise ValueError('id de experimento já tem outro resultado')
            db.execute('INSERT OR IGNORE INTO experimentos VALUES(?,?,?,?)',(data['id'],data['oportunidade_id'],agora(),json.dumps(data,ensure_ascii=False)))
            db.execute('UPDATE oportunidades SET estado=? WHERE id=?',(data['decisao'],data['oportunidade_id']));db.commit();exportar(db,root)
        print(json.dumps({'experimento':data['id'],'estado':data['decisao']}))
    else:
        cfg=json.loads(Path(args.config).read_text());validar(cfg)
        # Limite absoluto inclusive em resposta HTTP que entrega bytes lentamente.
        def timeout(signum,frame):raise TimeoutError('prazo absoluto')
        old=signal.signal(signal.SIGALRM,timeout);signal.alarm(cfg['max_execucao_s'])
        try:report=executar(cfg,root)
        finally:signal.alarm(0);signal.signal(signal.SIGALRM,old)
        print(json.dumps(report,ensure_ascii=False))
        if report['estado']!='ok':sys.exit(2)
if __name__=='__main__':main()
