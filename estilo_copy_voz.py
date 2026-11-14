"""Narração privada Chatterbox, sem publicação nem callback de produção."""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path
# 13/11 (dono: a voz tinha sotaque forte): a referencia era a do TIMELINE DROP -- um canal em INGLES. Agora a voz vem
# do BANCO DE VOZES (pt). 14/11 (dono: "não sinto emoção nas falas, muito frias e robóticas"). Três causas, três trocas:
#  1. a referência lia o texto NEUTRO de explicador ("Você já parou pra pensar...") e o Chatterbox copia a entonação da
#     referência -> ref nova no banco, estilo "contador" (trecho de suspense lido com style 0,65): pt/<voz>/contador.mp3;
#  2. exaggeration 0,40 (abaixo do padrão 0,5 = "contido") e temperature 0,65 -> emoção POR FALA (0,5 calma .. 0,9 susto)
#     e temperature 0,8; cfg_weight 0,3 (a recomendação do Chatterbox para fala dramática: segura o ritmo que a emoção acelera);
#  3. atempo 1,06 depois da síntese (metaliza a voz) -> velocidade 1,0; o ritmo vem do cfg_weight.
BANCO='https://toonzueira.duckdns.org/supabase/storage/v1/object/public/toonzueira/vozes_banco/'
AJ=json.loads(os.environ.get('ESTILO_COPY_AJUSTES') or '{}') or {}
REF=AJ.get('ref') or os.environ.get('ESTILO_COPY_REF') or BANCO+'pt/S4M4JhZIzYGUlDsYIOow/contador.mp3'
if not REF.startswith(BANCO+'pt/'):raise ValueError('A voz do Estilo Copy precisa ser do banco de vozes em portugues')

def duracao(p):
 return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)],text=True))

def emocao_padrao(fala):
 """Sem lista do roteiro: susto/agonia sobe, frase curta de impacto sobe um pouco, o resto fica no meio."""
 f=fala.lower()
 if '!' in fala or re.search(r'\b(arromba|sumi|corre|correu|pega|flagra|luz acendeu|desconhecid|polícia|traz o)',f):return .85
 if '?' in fala:return .7
 if len(fala)<45:return .72
 return .6

def gerar():
 from voz_livre import _sintetizar_local
 texto=os.environ['ESTILO_COPY_TEXTO'].strip()
 if not 20<=len(texto)<=8000:raise ValueError('Narração exige 20 a 8000 caracteres')
 falas=AJ.get('falas') or json.loads(os.environ.get('ESTILO_COPY_FALAS_JSON') or 'null')
 if not isinstance(falas,list) or not falas:falas=re.split(r'(?<=[.!?])\s+',texto)
 if any(not isinstance(x,str) or not x.strip() or len(x)>600 for x in falas):raise ValueError('Planos de voz inválidos')
 if ' '.join(falas)!=texto:raise ValueError('As falas não correspondem ao texto completo')
 emo=AJ.get('emocoes') or [emocao_padrao(x) for x in falas]
 if len(emo)!=len(falas) or any(not .25<=float(e)<=1.2 for e in emo):raise ValueError('emocoes: uma por fala, 0,25..1,2')
 if AJ.get('exaggeration') is not None:emo=[float(AJ['exaggeration'])]*len(falas)
 raiz=Path('estilo-copy-voz');raiz.mkdir(exist_ok=True);partes=raiz/'partes';partes.mkdir(exist_ok=True)
 base={'motor':'chatterbox','voice':'pt-BR-FranciscaNeural','lingua':'pt','ref_url':REF,
       'cfg_weight':float(AJ.get('cfg_weight',.30)),'temperature':float(AJ.get('temperature',.80))}
 velocidade=float(AJ.get('velocidade',1.0))
 if not .9<=velocidade<=1.1:raise ValueError('velocidade 0,9..1,1')
 # trechos de até ~260 caracteres (a entonação corre dentro deles), só juntando falas do MESMO nível de emoção
 trechos=[];atual='';ea=None
 for fala,e in zip(falas,emo):
  e=round(float(e),2)
  if atual and (len(atual)+1+len(fala)>260 or abs(e-ea)>.06):trechos.append((atual,ea));atual=fala;ea=e
  else:atual=(atual+' '+fala).strip();ea=e if ea is None else ea
 if atual:trechos.append((atual,ea))
 marcas=[];inicio=0;logs=[]
 for i,(trecho,e) in enumerate(trechos):
  cfg=dict(base,exaggeration=e)
  p=partes/f'{i:02}.wav';mm=_sintetizar_local(trecho,cfg,str(p),motor='chatterbox')
  fim=max((m['fim_s'] for m in mm),default=0)
  if fim<=0:raise ValueError('Trecho sem palavras alinhadas')
  # respiro depois do trecho: maior depois de pergunta/suspense, nunca corte seco
  resp=.38 if trecho.rstrip().endswith(('?','...','…')) else .26
  corte=min(duracao(p),fim+resp);out=partes/f'{i:02}-corte.wav'
  subprocess.run(['ffmpeg','-v','error','-i',str(p),'-t',str(corte),'-af',f'afade=t=in:st=0:d=0.015,afade=t=out:st={max(0,corte-0.08):.3f}:d=0.08','-ar','24000','-ac','1','-y',str(out)],check=True)
  ds=duracao(out)
  marcas.extend({'text':m['palavra'],'offset':round((inicio+m['inicio_s'])/velocidade*10000000),'duration':round((m['fim_s']-m['inicio_s'])/velocidade*10000000)} for m in mm)
  logs.append({'trecho':i,'caracteres':len(trecho),'emocao':e,'duracao_s':ds,'fim_alinhado_s':fim});inicio+=ds
  print('Chatterbox trecho',i+1,'/',len(trechos),'emocao',e,'s',round(ds,2),flush=True)
 (raiz/'concat.txt').write_text(''.join("file '"+str((partes/f'{i:02}-corte.wav').resolve())+"'\n" for i in range(len(trechos))))
 af=(f'atempo={velocidade},' if abs(velocidade-1)>.001 else '')+'highpass=f=70,acompressor=threshold=0.12:ratio=2.5:attack=8:release=120'
 subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(raiz/'concat.txt'),'-af',af,'-c:a','libmp3lame','-b:a','192k','-y',str(raiz/'voz-continua.mp3')],check=True)
 (raiz/'palavras.json').write_text(json.dumps(marcas,ensure_ascii=False))
 (raiz/'proveniencia.json').write_text(json.dumps({'motor':'chatterbox','idioma':'pt','referencia':REF,'origem':'Banco de vozes do projeto; clone Chatterbox local, sem custo','texto_sha256':hashlib.sha256(texto.encode()).hexdigest(),'velocidade':velocidade,'cfg_weight':base['cfg_weight'],'temperature':base['temperature'],'metodo':'trechos por nivel de emocao (ate 260 caracteres), respiro e fade','planos':logs},ensure_ascii=False,indent=2))
 import shutil
 shutil.rmtree(partes);(raiz/'concat.txt').unlink()
 print('Narração gerada; palavras:',len(marcas),flush=True)

def main():
 if '--sintetizar' in sys.argv:return gerar()
 from voz_livre import _garantir_venv,_py_venv
 _garantir_venv()
 subprocess.run([_py_venv(),__file__,'--sintetizar'],check=True)
if __name__=='__main__':main()
