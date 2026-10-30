#!/usr/bin/env python3
"""Importa pesquisa de canais como metadados pendentes, sem coleta/avaliação visual."""
import argparse
import json
from pathlib import Path
from ciclo import agora,banco,canonical,digest,exportar,trava

def importar(manifesto,estado):
    raw=Path(manifesto).read_bytes();data=json.loads(raw);root=Path(estado);root.mkdir(parents=True,exist_ok=True)
    novas=0
    with trava(root),banco(root/'catalogo.sqlite') as db:
        for ref in data['referencias']:
            if ref.get('quadros_analisados') is not False:raise ValueError('importador aceita somente triagem sem quadros analisados')
            origem=canonical(ref['url']);rid=digest(origem.encode())[:24]
            targets=[m.strip() for m in ref['motores_alvo'].split(',')]
            links=[r['id'] for r in db.execute('SELECT id,motor FROM oportunidades') if r['motor'] in targets]
            evid={'nivel':'metadados','observacoes':[],'quadros':[],'timecodes':[],
                  'metodo':data['metodo'],'fonte_primaria':ref['fonte_primaria'],
                  'declaracao_publicada_na_pesquisa':ref['evidencia_publicada'],
                  'aplicacao_proposta_nao_validada':ref['aplicacao_proposta'],
                  'entrada_sugerida':ref['entrada_sugerida'],'motores_alvo':targets,
                  'prioridade_editorial':ref['prioridade'],'vinculos_backlog':links,
                  'revisao_pendente':'selecionar trecho acessível, registrar timecodes/quadros e só então analisar técnica visual',
                  'coleta_recorrente_do_canal_ativada':False}
            proven={'manifesto':Path(manifesto).name,'hash_manifesto':digest(raw),'data_pesquisa':data['data_pesquisa'],
                    'direitos':'links e notas de pesquisa; sem assets copiados/licença para reutilização da obra'}
            cur=db.execute('INSERT OR IGNORE INTO refs(id,origem,primeiro_em,titulo,tipo,proveniencia,evidencia) VALUES(?,?,?,?,?,?,?)',
                           (rid,origem,agora(),ref['nome'],'canal-triagem',json.dumps(proven,ensure_ascii=False),json.dumps(evid,ensure_ascii=False)))
            novas+=cur.rowcount
        db.commit();exportar(db,root)
        lines=['# Canais aguardando análise temporal','',data['metodo'],'']
        for ref in sorted(data['referencias'],key=lambda r:r['prioridade']):
            lines += [f"## {ref['nome']} — prioridade {ref['prioridade']}",'',ref['url'],'',f"Motores: {ref['motores_alvo']}",
                      f"Entrada sugerida: {ref['entrada_sugerida']}",'','Hipótese de experimento: '+ref['aplicacao_proposta'],'',
                      'Próximo passo: selecionar trecho real, registrar timecodes e quadros. Sem aprovação visual e sem coleta do canal ativada.','']
        (root/'triagem-canais.md').write_text('\n'.join(lines))
    return {'referencias_novas':novas,'canais_no_manifesto':len(data['referencias']),'coleta_canais_ativada':False}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--manifesto',default=str(Path(__file__).with_name('canais_triagem.json')));ap.add_argument('--estado',required=True);a=ap.parse_args()
    print(json.dumps(importar(a.manifesto,a.estado),ensure_ascii=False))
