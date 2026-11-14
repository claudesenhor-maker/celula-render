"""Narração privada Chatterbox, por plano, sem publicação nem callback de produção."""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path
# 13/11 (dono: a voz tinha sotaque forte): a referencia era a do TIMELINE DROP -- um canal em INGLES. O clone
# fazia um narrador americano falar portugues. Agora a voz vem do BANCO DE VOZES (pt, aprovada, nota 10):
# Elena Vinter, narradora brasileira suave. Outra voz do banco: ESTILO_COPY_REF com uma URL de vozes_banco/.
BANCO='https://toonzueira.duckdns.org/supabase/storage/v1/object/public/toonzueira/vozes_banco/'
REF=os.environ.get('ESTILO_COPY_REF') or BANCO+'pt/S4M4JhZIzYGUlDsYIOow.mp3'
if not REF.startswith(BANCO+'pt/'):raise ValueError('A voz do Estilo Copy precisa ser do banco de vozes em portugues')

def duracao(p):
 return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=nw=1:nk=1',str(p)],text=True))

def gerar():
 from voz_livre import _sintetizar_local
 texto=os.environ['ESTILO_COPY_TEXTO'].strip()
 if not 20<=len(texto)<=8000:raise ValueError('Narração exige 20 a 8000 caracteres')
 falas=json.loads(os.environ.get('ESTILO_COPY_FALAS_JSON') or 'null')
 if not isinstance(falas,list) or not falas:falas=re.split(r'(?<=[.!?])\s+',texto)
 if any(not isinstance(x,str) or not x.strip() or len(x)>600 for x in falas):raise ValueError('Planos de voz inválidos')
 if ' '.join(falas)!=texto:raise ValueError('As falas não correspondem ao texto completo')
 raiz=Path('estilo-copy-voz');raiz.mkdir(exist_ok=True);partes=raiz/'partes';partes.mkdir(exist_ok=True)
 cfg={'motor':'chatterbox','voice':'pt-BR-FranciscaNeural','lingua':'pt','ref_url':REF,'exaggeration':.40,'cfg_weight':.45,'temperature':.65}
 # 14/11 (dono: "audio muito picado, nao e fluido como o exemplo"): era UMA sintese por frase + corte seco 0,12 s
 # depois da ultima palavra -- a entonacao recomecava a cada frase. Agora: trechos de ate ~260 caracteres (2-4 frases,
 # a entonacao corre dentro deles) e emenda com respiro natural de 0,22 s e fade curto, nunca corte seco.
 velocidade=1.06;marcas=[];inicio=0;logs=[]
 trechos=[];atual=''
 for fala in falas:
  if atual and len(atual)+1+len(fala)>260:trechos.append(atual);atual=fala
  else:atual=(atual+' '+fala).strip()
 if atual:trechos.append(atual)
 for i,trecho in enumerate(trechos):
  p=partes/f'{i:02}.wav';mm=_sintetizar_local(trecho,cfg,str(p),motor='chatterbox')
  fim=max((m['fim_s'] for m in mm),default=0)
  if fim<=0:raise ValueError('Trecho sem palavras alinhadas')
  corte=min(duracao(p),fim+.22);out=partes/f'{i:02}-corte.wav'
  subprocess.run(['ffmpeg','-v','error','-i',str(p),'-t',str(corte),'-af',f'afade=t=in:st=0:d=0.015,afade=t=out:st={max(0,corte-0.06):.3f}:d=0.06','-ar','24000','-ac','1','-y',str(out)],check=True)
  ds=duracao(out)
  marcas.extend({'text':m['palavra'],'offset':round((inicio+m['inicio_s'])/velocidade*10000000),'duration':round((m['fim_s']-m['inicio_s'])/velocidade*10000000)} for m in mm)
  logs.append({'trecho':i,'caracteres':len(trecho),'duracao_s':ds,'fim_alinhado_s':fim});inicio+=ds
  print('Chatterbox trecho',i+1,'/',len(trechos),'s',round(ds,2),flush=True)
 (raiz/'concat.txt').write_text(''.join("file '"+str((partes/f'{i:02}-corte.wav').resolve())+"'\n" for i in range(len(trechos))))
 subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(raiz/'concat.txt'),'-af',f'atempo={velocidade}','-c:a','libmp3lame','-b:a','160k','-y',str(raiz/'voz-continua.mp3')],check=True)
 (raiz/'palavras.json').write_text(json.dumps(marcas,ensure_ascii=False))
 (raiz/'proveniencia.json').write_text(json.dumps({'motor':'chatterbox','idioma':'pt','referencia':REF,'origem':'Banco de vozes do projeto (banco_vozes pt/S4M4JhZIzYGUlDsYIOow, Elena Vinter, aprovada nota 10); clone Chatterbox local, sem custo','texto_sha256':hashlib.sha256(texto.encode()).hexdigest(),'velocidade':velocidade,'metodo':'trechos-de-260-caracteres-com-respiro-e-fade','planos':logs},ensure_ascii=False,indent=2))
 import shutil
 shutil.rmtree(partes);(raiz/'concat.txt').unlink()
 print('Narração gerada; palavras:',len(marcas),flush=True)

def main():
 if '--sintetizar' in sys.argv:return gerar()
 from voz_livre import _garantir_venv,_py_venv
 _garantir_venv()
 subprocess.run([_py_venv(),__file__,'--sintetizar'],check=True)
if __name__=='__main__':main()
