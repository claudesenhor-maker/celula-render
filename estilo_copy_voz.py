"""Narração privada Chatterbox, por plano, sem publicação nem callback de produção."""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path
REF='https://toonzueira.duckdns.org/supabase/storage/v1/object/public/toonzueira/vozes_ref/timeline_drop_1.mp3'

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
 velocidade=1.12;marcas=[];inicio=0;logs=[]
 for i,fala in enumerate(falas):
  p=partes/f'{i:02}.wav';mm=_sintetizar_local(fala,cfg,str(p),motor='chatterbox')
  fim=max((m['fim_s'] for m in mm),default=0)
  if fim<=0:raise ValueError('Plano sem palavras alinhadas')
  corte=min(duracao(p),fim+.12);out=partes/f'{i:02}-corte.wav'
  subprocess.run(['ffmpeg','-v','error','-i',str(p),'-t',str(corte),'-ar','24000','-ac','1','-y',str(out)],check=True)
  ds=duracao(out)
  marcas.extend({'text':m['palavra'],'offset':round((inicio+m['inicio_s'])/velocidade*10000000),'duration':round((m['fim_s']-m['inicio_s'])/velocidade*10000000)} for m in mm)
  logs.append({'plano':i,'duracao_s':ds,'fim_alinhado_s':fim});inicio+=ds
  print('Chatterbox plano',i+1,'/',len(falas),'s',round(ds,2),flush=True)
 (raiz/'concat.txt').write_text(''.join("file '"+str((partes/f'{i:02}-corte.wav').resolve())+"'\n" for i in range(len(falas))))
 subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(raiz/'concat.txt'),'-af',f'atempo={velocidade}','-c:a','libmp3lame','-b:a','160k','-y',str(raiz/'voz-continua.mp3')],check=True)
 (raiz/'palavras.json').write_text(json.dumps(marcas,ensure_ascii=False))
 (raiz/'proveniencia.json').write_text(json.dumps({'motor':'chatterbox','idioma':'pt','referencia':REF,'origem':'Banco do projeto: ElevenLabs Voice Design, voz sintética sem pessoa real (23/10)','texto_sha256':hashlib.sha256(texto.encode()).hexdigest(),'velocidade':velocidade,'metodo':'por-plano-com-corte-apos-ultima-palavra','planos':logs},ensure_ascii=False,indent=2))
 import shutil
 shutil.rmtree(partes);(raiz/'concat.txt').unlink()
 print('Narração gerada; palavras:',len(marcas),flush=True)

def main():
 if '--sintetizar' in sys.argv:return gerar()
 from voz_livre import _garantir_venv,_py_venv
 _garantir_venv()
 subprocess.run([_py_venv(),__file__,'--sintetizar'],check=True)
if __name__=='__main__':main()
