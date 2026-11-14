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
 if not .85<=velocidade<=1.1:raise ValueError('velocidade 0,85..1,1')
 # 14/11 noite (dono: "zero emoção na fala e o humor foi embora"). Medido no canal original: o tom muda de frase para frase
 # (4 st de desvio; o nosso 2 st) e ele fala ~2,3 palavras/s com pausa antes da piada (o nosso 2,9, sem pausa).
 #  - `refs` {humor: url do banco} + `humores` (um por fala): cada fala é clonada da referência daquele HUMOR (irônico, tenso,
 #    espanto, seco, causo) -- a entonação vem da referência, então a narração troca de registro como o original;
 #  - `pausas` (uma por fala, segundos a MAIS depois dela): o silêncio é costurado no vão entre as palavras, sem cortar o trecho.
 refs=AJ.get('refs') or {}
 if any(not str(u).startswith(BANCO+'pt/') for u in refs.values()):raise ValueError('refs: só vozes do banco em portugues')
 hum=AJ.get('humores') or [None]*len(falas)
 pau=AJ.get('pausas') or [0]*len(falas)
 if len(hum)!=len(falas) or len(pau)!=len(falas):raise ValueError('humores/pausas: um por fala')
 if any(h is not None and h not in refs for h in hum):raise ValueError('humor sem referencia em refs')
 if any(not 0<=float(x)<=1.5 for x in pau):raise ValueError('pausas 0..1,5 s')
 # trechos de até ~260 caracteres (a entonação corre dentro deles), só juntando falas do MESMO humor e nível de emoção
 trechos=[];atual=[];ea=None;ha=None
 for fala,e,h,p in zip(falas,emo,hum,pau):
  e=round(float(e),2)
  if atual and (sum(len(x[0])+1 for x in atual)+len(fala)>260 or abs(e-ea)>.06 or h!=ha):trechos.append((atual,ea,ha));atual=[]
  if not atual:ea=e;ha=h
  atual.append((fala,float(p)))
 if atual:trechos.append((atual,ea,ha))
 import numpy as np
 SR=24000
 def ler(p):
  return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-ac','1','-ar',str(SR),'-f','s16le','-']),dtype='<i2').astype('float32')/32768
 def rampa(x,n_in=360,n_out=1900):
  x=x.copy();n_in=min(n_in,len(x)//2);n_out=min(n_out,len(x)//2)
  if n_in:x[:n_in]*=np.linspace(0,1,n_in)
  if n_out:x[-n_out:]*=np.linspace(1,0,n_out)
  return x
 marcas=[];logs=[];saida=[];inicio=0.0
 for i,(itens,e,h) in enumerate(trechos):
  trecho=' '.join(f for f,_ in itens)
  cfg=dict(base,exaggeration=e)
  if h:cfg['ref_url']=refs[h]
  p=partes/f'{i:02}.wav';mm=_sintetizar_local(trecho,cfg,str(p),motor='chatterbox')
  fim=max((m['fim_s'] for m in mm),default=0)
  if fim<=0:raise ValueError('Trecho sem palavras alinhadas')
  x=ler(p)
  # respiro natural depois do trecho: maior depois de pergunta/suspense, nunca corte seco
  resp=.38 if trecho.rstrip().endswith(('?','...','…')) else .26
  x=rampa(x[:int(min(len(x)/SR,fim+resp)*SR)])
  # pausas pedidas DENTRO do trecho: silêncio no meio do vão entre a última palavra da fala e a primeira da seguinte
  cortes=[];k=0;ok=len(mm)==len(trecho.split())
  for f,pz in itens[:-1]:
   k+=len(f.split())
   if ok and pz>0 and 0<k<len(mm):cortes.append(((mm[k-1]['fim_s']+mm[k]['inicio_s'])/2,pz,k))
  pedacos=[];ant=0;desloc=[0.0]*len(mm)
  for t,pz,k in cortes:
   a=int(t*SR)
   if a-ant<SR//10 or len(x)-a<SR//10:continue
   pedacos+=[rampa(x[ant:a],240,720),np.zeros(int(pz*SR),dtype='float32')];ant=a
   for j in range(k,len(mm)):desloc[j]+=pz
  pedacos.append(rampa(x[ant:],240,0) if pedacos else x[ant:])
  fimp=itens[-1][1]
  if fimp>0:pedacos.append(np.zeros(int(fimp*SR),dtype='float32'))
  y=np.concatenate(pedacos);saida.append(y);ds=len(y)/SR
  marcas.extend({'text':m['palavra'],'offset':round((inicio+m['inicio_s']+desloc[j])/velocidade*10000000),'duration':round((m['fim_s']-m['inicio_s'])/velocidade*10000000)} for j,m in enumerate(mm))
  logs.append({'trecho':i,'caracteres':len(trecho),'emocao':e,'humor':h,'duracao_s':round(ds,2),'fim_alinhado_s':fim,'pausas_costuradas':len(cortes)});inicio+=ds
  print('Chatterbox trecho',i+1,'/',len(trechos),'humor',h,'emocao',e,'s',round(ds,2),flush=True)
 bruto=raiz/'bruto.wav'
 import wave
 with wave.open(str(bruto),'w') as w:
  w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes((np.clip(np.concatenate(saida),-1,1)*32000).astype('<i2').tobytes())
 af=(f'atempo={velocidade},' if abs(velocidade-1)>.001 else '')+'highpass=f=70,acompressor=threshold=0.12:ratio=2.5:attack=8:release=120'
 subprocess.run(['ffmpeg','-v','error','-i',str(bruto),'-af',af,'-c:a','libmp3lame','-b:a','192k','-y',str(raiz/'voz-continua.mp3')],check=True)
 bruto.unlink()
 (raiz/'palavras.json').write_text(json.dumps(marcas,ensure_ascii=False))
 (raiz/'proveniencia.json').write_text(json.dumps({'motor':'chatterbox','idioma':'pt','referencia':REF,'referencias_por_humor':refs,'origem':'Banco de vozes do projeto; clone Chatterbox local, sem custo','texto_sha256':hashlib.sha256(texto.encode()).hexdigest(),'velocidade':velocidade,'cfg_weight':base['cfg_weight'],'temperature':base['temperature'],'metodo':'trechos por humor e nivel de emocao (ate 260 caracteres), uma referencia por humor, pausas costuradas entre palavras','planos':logs},ensure_ascii=False,indent=2))
 import shutil
 shutil.rmtree(partes)
 print('Narração gerada; palavras:',len(marcas),flush=True)

def main():
 if '--sintetizar' in sys.argv:return gerar()
 from voz_livre import _garantir_venv,_py_venv
 _garantir_venv()
 subprocess.run([_py_venv(),__file__,'--sintetizar'],check=True)
if __name__=='__main__':main()
