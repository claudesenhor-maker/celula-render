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
 if any(not 0<=float(x)<=1.5 for x in pau):raise ValueError('pausas 0..1,5 s')
 # MARCAÇÃO (voz_marcacao.py): emocao(trecho), pausa(s), enfase(palavras) dentro da fala. Cada trecho marcado usa a referência
 # daquela emoção (se a voz tiver), os parâmetros do clonador da emoção e a PROSÓDIA por áudio (tom, ritmo, volume).
 import voz_marcacao as VM
 vaos=[]   # (texto limpo, emocao, exaggeration, pausa depois, enfases)
 for fala,e,h,p in zip(falas,emo,hum,pau):
  base_emo=VM._MAPA.get(VM._n(h or 'causo'),'causo')
  ts=VM.interpretar(fala,base_emo)
  if not ts:raise ValueError('fala vazia depois da marcacao')
  for k,t in enumerate(ts):
   ex=round(float(e),2) if t['emocao']==base_emo else VM.EMOCOES[t['emocao']]['exag']
   vaos.append((t['texto'],t['emocao'],ex,t['pausa_s']+(float(p) if k==len(ts)-1 else 0),t['enfases']))
 limpo=' '.join(v[0] for v in vaos)
 # trechos de até ~260 caracteres (a entonação corre dentro deles), só juntando vãos da MESMA emoção e nível
 trechos=[];atual=[];ea=None;ha=None
 for v in vaos:
  if atual and (sum(len(x[0])+1 for x in atual)+len(v[0])>260 or abs(v[2]-ea)>.06 or v[1]!=ha):trechos.append((atual,ea,ha));atual=[]
  if not atual:ea=v[2];ha=v[1]
  atual.append(v)
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
  trecho=' '.join(f[0] for f in itens)
  pe=VM.EMOCOES[h];rh=VM.referencia(h,refs)
  cfg=dict(base,exaggeration=e)
  if AJ.get('cfg_weight') is None:cfg['cfg_weight']=pe['cfg']
  if AJ.get('temperature') is None:cfg['temperature']=pe['temp']
  if rh:cfg['ref_url']=refs[rh]
  p=partes/f'{i:02}.wav';mm=_sintetizar_local(trecho,cfg,str(p),motor='chatterbox')
  fim=max((m['fim_s'] for m in mm),default=0)
  if fim<=0:raise ValueError('Trecho sem palavras alinhadas')
  x=ler(p)
  # respiro natural depois do trecho: maior depois de pergunta/suspense, nunca corte seco
  resp=.38 if trecho.rstrip().endswith(('?','...','…')) else .26
  x=rampa(x[:int(min(len(x)/SR,fim+resp)*SR)])
  ok=len(mm)==len(trecho.split())
  # ênfase nas palavras marcadas + prosódia da emoção (tom, ritmo, volume) no trecho inteiro
  enf=[];k=0
  for f in itens:
   enf+=[k+q for q in f[4]];k+=len(f[0].split())
  x,mm=VM.aplicar(x,SR,[{'palavra':m['palavra'],'inicio_s':m['inicio_s'],'fim_s':m['fim_s']} for m in mm],h if AJ.get('prosodia',True) else 'neutro',enf if ok else [])
  x=rampa(x,120,600)
  # pausas pedidas DENTRO do trecho: silêncio no meio do vão entre a última palavra de um vão e a primeira do seguinte
  cortes=[];k=0
  for f in itens[:-1]:
   k+=len(f[0].split())
   if ok and f[3]>0 and 0<k<len(mm):cortes.append(((mm[k-1]['fim_s']+mm[k]['inicio_s'])/2,f[3],k))
  pedacos=[];ant=0;desloc=[0.0]*len(mm)
  for t,pz,k in cortes:
   a=int(t*SR)
   if a-ant<SR//10 or len(x)-a<SR//10:continue
   pedacos+=[rampa(x[ant:a],240,720),np.zeros(int(pz*SR),dtype='float32')];ant=a
   for j in range(k,len(mm)):desloc[j]+=pz
  pedacos.append(rampa(x[ant:],240,0) if pedacos else x[ant:])
  fimp=itens[-1][3]
  if fimp>0:pedacos.append(np.zeros(int(fimp*SR),dtype='float32'))
  y=np.concatenate(pedacos);saida.append(y);ds=len(y)/SR
  marcas.extend({'text':m['palavra'],'offset':round((inicio+m['inicio_s']+desloc[j])/velocidade*10000000),'duration':round((m['fim_s']-m['inicio_s'])/velocidade*10000000)} for j,m in enumerate(mm))
  logs.append({'trecho':i,'caracteres':len(trecho),'emocao':h,'exaggeration':e,'referencia':rh or 'base','prosodia':[pe['st'],pe['tempo'],pe['db']],'enfases':len(enf),'duracao_s':round(ds,2),'pausas_costuradas':len(cortes)});inicio+=ds
  print('Chatterbox trecho',i+1,'/',len(trechos),'emocao',h,'ref',rh or 'base','exag',e,'s',round(ds,2),flush=True)
 bruto=raiz/'bruto.wav'
 import wave
 with wave.open(str(bruto),'w') as w:
  w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes((np.clip(np.concatenate(saida),-1,1)*32000).astype('<i2').tobytes())
 af=(f'atempo={velocidade},' if abs(velocidade-1)>.001 else '')+'highpass=f=70,acompressor=threshold=0.12:ratio=2.5:attack=8:release=120'
 subprocess.run(['ffmpeg','-v','error','-i',str(bruto),'-af',af,'-c:a','libmp3lame','-b:a','192k','-y',str(raiz/'voz-continua.mp3')],check=True)
 bruto.unlink()
 (raiz/'palavras.json').write_text(json.dumps(marcas,ensure_ascii=False))
 (raiz/'proveniencia.json').write_text(json.dumps({'motor':'chatterbox','idioma':'pt','referencia':REF,'referencias_por_humor':refs,'origem':'Banco de vozes do projeto; clone Chatterbox local, sem custo','texto_sha256':hashlib.sha256(texto.encode()).hexdigest(),'velocidade':velocidade,'cfg_weight':base['cfg_weight'],'temperature':base['temperature'],'metodo':'marcacao emocao(trecho): referencia por emocao + parametros do clonador + prosodia por audio (tom, ritmo, volume), enfase por palavra, pausas costuradas','texto_limpo':limpo,'planos':logs},ensure_ascii=False,indent=2))
 import shutil
 shutil.rmtree(partes)
 print('Narração gerada; palavras:',len(marcas),flush=True)

ACABAMENTO=('aresample=48000,highpass=f=70,aexciter=level_in=1:level_out=1:amount=2.2:drive=6.5:blend=0:freq=5200:ceil=15000,'
            'treble=g=3.5:f=6500:width_type=q:width=0.7,acompressor=threshold=0.12:ratio=2.5:attack=8:release=120')

def gerar_entonacao():
 """15/11 (dono: "parar de focar em sentimento e focar na entonação -- fim de frase, interrogação --, fluidez e naturalidade; o
 sistema de emoção foi reprovado, dá para ver a troca"). UMA referência e os MESMOS parâmetros do começo ao fim (nada troca);
 trechos longos (a melodia corre por várias frases); cada trecho é gerado até `tentativas` vezes e fica a tentativa em que a
 melodia combina com a pontuação (voz_entonacao.py); a frase que mesmo assim termina errada ganha uma rampa curta de tom na
 última palavra; no fim, acabamento em 48 kHz que devolve os agudos (o clonador entrega 24 kHz, som abafado)."""
 from voz_livre import _sintetizar_local
 import random, wave, shutil
 import numpy as np, torch
 import voz_entonacao as VE, voz_marcacao as VM
 texto=os.environ['ESTILO_COPY_TEXTO'].strip()
 falas=AJ.get('falas')
 if not isinstance(falas,list) or not falas or ' '.join(falas)!=texto:raise ValueError('modo entonacao exige falas que formem o texto')
 pau=AJ.get('pausas') or [0]*len(falas)
 if len(pau)!=len(falas) or any(not 0<=float(x)<=1.5 for x in pau):raise ValueError('pausas: uma por fala, 0..1,5 s')
 falas=[VM.limpar(f) for f in falas]
 N=int(AJ.get('tentativas',3));velocidade=float(AJ.get('velocidade',1.0))
 if not 1<=N<=5 or not .85<=velocidade<=1.1:raise ValueError('tentativas 1..4, velocidade 0,85..1,1')
 cfg={'motor':'chatterbox','voice':'pt-BR-FranciscaNeural','lingua':AJ.get('lingua','pt'),'ref_url':REF,'exaggeration':float(AJ.get('exaggeration',.6)),
      'cfg_weight':float(AJ.get('cfg_weight',.30)),'temperature':float(AJ.get('temperature',.80))}
 raiz=Path('estilo-copy-voz');raiz.mkdir(exist_ok=True);partes=raiz/'partes';partes.mkdir(exist_ok=True)
 trechos=[];atual=[]
 for f,p in zip(falas,pau):
  if atual and sum(len(x[0])+1 for x in atual)+len(f)>240:trechos.append(atual);atual=[]
  atual.append((f,float(p)))
 if atual:trechos.append(atual)
 SR=24000
 def ler(p):
  return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-ac','1','-ar',str(SR),'-f','s16le','-']),dtype='<i2').astype('float32')/32768
 def rampa(x,n_in=360,n_out=1900):
  x=x.copy();n_in=min(n_in,len(x)//2);n_out=min(n_out,len(x)//2)
  if n_in:x[:n_in]*=np.linspace(0,1,n_in)
  if n_out:x[-n_out:]*=np.linspace(1,0,n_out)
  return x
 marcas=[];logs=[];saida=[];inicio=0.0;todas=[]
 FRACO=float(AJ.get('nota_fraca',.72));EXTRA=int(AJ.get('tentativas_extra',2))
 def tentar(itens,chave,n,ja=0):
  """gera o trecho até n vezes; devolve (nota, áudio, palavras, nº da tentativa escolhida, notas)."""
  trecho=' '.join(f for f,_ in itens);melhor=None;notas=[]
  for t in range(ja,ja+n):
   semente=1000+chave*17+t*101;torch.manual_seed(semente);np.random.seed(semente);random.seed(semente)
   p=partes/f'{chave:04}-{t}.wav';mm=_sintetizar_local(trecho,cfg,str(p),motor='chatterbox')
   fim=max((m['fim_s'] for m in mm),default=0)
   if fim<=0:notas.append(0);continue
   x=ler(p);resp=.38 if trecho.rstrip().endswith(('?','...','…')) else .26
   x=rampa(x[:int(min(len(x)/SR,fim+resp)*SR)])
   res=VE.medir(x,SR,mm);nota=float(np.mean([r['nota'] for r in res])) if res else 0.0
   spc=fim/max(1,len(trecho))
   if not .042<=spc<=.115:nota-=.3          # rápido ou arrastado demais: o modelo pulou ou inventou texto
   if len(mm)!=len(trecho.split()):nota-=.3
   notas.append(round(nota,3))
   if melhor is None or nota>melhor[0]:melhor=(nota,x,mm,t)
   print('trecho',chave,'tentativa',t+1,'nota',round(nota,3),'s/caractere',round(spc,3),flush=True)
   if nota>=.8:break
  return (melhor+(notas,)) if melhor else None
 def resolver(itens,chave,nivel=0):
  """bloco fraco (15/11, dono: "tente arrumar esses blocos fracos"): depois das N tentativas insiste mais EXTRA vezes; se ainda
  ficar fraco e tiver mais de uma fala, gera as duas metades em separado e fica com o que tiver a melhor melodia."""
  r=tentar(itens,chave,N)
  if r and r[0]<FRACO and EXTRA>0 and nivel==0:
   r2=tentar(itens,chave,EXTRA,ja=N)
   if r2:r=(r2[:4] if r2[0]>r[0] else r[:4])+(r[4]+r2[4],)
  if (r is None or r[0]<FRACO) and len(itens)>=2 and nivel<1:
   tot=sum(len(f) for f,_ in itens);ac=0;c=1
   for j,(f,_) in enumerate(itens[:-1]):
    ac+=len(f)
    if ac>=tot/2:c=j+1;break
   else:c=len(itens)-1
   ma=resolver(itens[:c],chave*10+1,1);mb=resolver(itens[c:],chave*10+2,1)
   if ma and mb:
    na=sum(len(VE.frases(z[2])) for z in ma);nb=sum(len(VE.frases(z[2])) for z in mb)
    media=(sum(z[0]*len(VE.frases(z[2])) for z in ma+mb))/max(1,na+nb)
    if r is None or media>r[0]+.04:
     print('trecho',chave,'dividido: nota',round(media,3),'contra',None if r is None else round(r[0],3),flush=True);return ma+mb
  return [(r[0],r[1],r[2],itens,r[3],r[4])] if r else None
 prontos=[]
 for i,itens in enumerate(trechos):
  rr=resolver(itens,i+1)
  if not rr:raise ValueError('Trecho sem palavras alinhadas')
  prontos+=[(i,)+z for z in rr]
 for i,nota,x,mm,itens,t,notas in prontos:
  trecho=' '.join(f for f,_ in itens);ok=len(mm)==len(trecho.split())
  fins=[];k=0
  for f,_ in itens:
   k+=len(f.split());fins.append(k-1)
  feitos=[]
  if ok and AJ.get('rampa',True):x,feitos=VE.corrigir(x,SR,mm,fins)
  res=VE.medir(x,SR,mm);todas+=res
  cortes=[];k=0
  for f,pz in itens[:-1]:
   k+=len(f.split())
   if ok and pz>0 and 0<k<len(mm):cortes.append(((mm[k-1]['fim_s']+mm[k]['inicio_s'])/2,pz,k))
  pedacos=[];ant=0;desloc=[0.0]*len(mm)
  for tc,pz,k in cortes:
   a=int(tc*SR)
   if a-ant<SR//10 or len(x)-a<SR//10:continue
   pedacos+=[rampa(x[ant:a],240,720),np.zeros(int(pz*SR),dtype='float32')];ant=a
   for j in range(k,len(mm)):desloc[j]+=pz
  pedacos.append(rampa(x[ant:],240,0) if pedacos else x[ant:])
  if itens[-1][1]>0:pedacos.append(np.zeros(int(itens[-1][1]*SR),dtype='float32'))
  y=np.concatenate(pedacos);saida.append(y);ds=len(y)/SR
  marcas.extend({'text':m['palavra'],'offset':round((inicio+m['inicio_s']+desloc[j])/velocidade*10000000),'duration':round((m['fim_s']-m['inicio_s'])/velocidade*10000000)} for j,m in enumerate(mm))
  logs.append({'trecho':i,'caracteres':len(trecho),'tentativas':notas,'escolhida':t+1,'nota_escolhida':round(nota,3),'nota_final':round(float(np.mean([r['nota'] for r in res])) if res else 0,3),'rampas':feitos,'duracao_s':round(ds,2)});inicio+=ds
 bruto=raiz/'bruto.wav'
 with wave.open(str(bruto),'w') as w:
  w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes((np.clip(np.concatenate(saida),-1,1)*32000).astype('<i2').tobytes())
 af=(f'atempo={velocidade},' if abs(velocidade-1)>.001 else '')+ACABAMENTO
 subprocess.run(['ffmpeg','-v','error','-i',str(bruto),'-af',af,'-ar','48000','-c:a','libmp3lame','-b:a','192k','-y',str(raiz/'voz-continua.mp3')],check=True)
 bruto.unlink()
 (raiz/'palavras.json').write_text(json.dumps(marcas,ensure_ascii=False))
 (raiz/'entonacao.json').write_text(json.dumps({'resumo':VE.resumo(todas),'frases':todas},ensure_ascii=False,indent=1))
 (raiz/'proveniencia.json').write_text(json.dumps({'motor':'chatterbox','idioma':cfg['lingua'],'referencia':REF,'origem':'Banco de vozes do projeto; clone Chatterbox local, sem custo','texto_sha256':hashlib.sha256(texto.encode()).hexdigest(),'velocidade':velocidade,'cfg_weight':cfg['cfg_weight'],'temperature':cfg['temperature'],'exaggeration':cfg['exaggeration'],'metodo':'entonacao: uma referencia, trechos longos, ate %d tentativas por trecho escolhidas pela regua de entonacao, rampa de tom no fim das frases erradas, acabamento 48 kHz'%N,'entonacao':VE.resumo(todas),'planos':logs},ensure_ascii=False,indent=2))
 shutil.rmtree(partes)
 print('Narração (entonação) gerada; palavras:',len(marcas),'resumo',json.dumps(VE.resumo(todas),ensure_ascii=False),flush=True)

def main():
 if '--sintetizar' in sys.argv:return gerar_entonacao() if AJ.get('modo')=='entonacao' else gerar()
 from voz_livre import _garantir_venv,_py_venv
 _garantir_venv()
 subprocess.run([_py_venv(),__file__,'--sintetizar'],check=True)
if __name__=='__main__':main()
