"""Gera somente narração privada; nenhuma publicação ou callback de produção."""
import hashlib,json,os,subprocess
from pathlib import Path
from voz_livre import sintetizar_livre

def main():
 texto=os.environ['ESTILO_COPY_TEXTO'].strip()
 if not 20<=len(texto)<=8000:raise ValueError('Narração exige 20 a 8000 caracteres')
 raiz=Path('estilo-copy-voz');raiz.mkdir(exist_ok=True)
 cfg={'motor':'chatterbox','voice':'pt-BR-FranciscaNeural','lingua':'pt','ref_url':'https://toonzueira.duckdns.org/supabase/storage/v1/object/public/toonzueira/vozes_ref/enem_1.mp3','exaggeration':.45,'cfg_weight':.45,'temperature':.7}
 marcas=sintetizar_livre(texto,cfg,str(raiz/'original.wav'),motor='chatterbox')
 # Ajuste leve, mantendo todas as marcas na mesma escala temporal.
 velocidade=1.12
 subprocess.run(['ffmpeg','-v','error','-i',str(raiz/'original.wav'),'-af',f'atempo={velocidade}','-c:a','libmp3lame','-b:a','160k','-y',str(raiz/'voz-continua.mp3')],check=True)
 eventos=[{'text':m['palavra'],'offset':round(m['inicio_s']/velocidade*10000000),'duration':round((m['fim_s']-m['inicio_s'])/velocidade*10000000)} for m in marcas]
 (raiz/'palavras.json').write_text(json.dumps(eventos,ensure_ascii=False))
 (raiz/'proveniencia.json').write_text(json.dumps({'motor':'chatterbox','idioma':'pt','referencia':cfg['ref_url'],'origem':'Banco do projeto: ElevenLabs Voice Design, voz sintética sem pessoa real (23/10)','texto_sha256':hashlib.sha256(texto.encode()).hexdigest(),'velocidade':velocidade},ensure_ascii=False,indent=2))
 (raiz/'original.wav').unlink()
 print('Narração Chatterbox gerada; palavras alinhadas:',len(eventos))
if __name__=='__main__':main()
