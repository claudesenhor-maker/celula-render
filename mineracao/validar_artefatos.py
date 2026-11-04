#!/usr/bin/env python3
"""Conferência técnica dos clipes comparáveis; não avalia qualidade visual."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ap=argparse.ArgumentParser();ap.add_argument('pasta');ap.add_argument('--exigir-sequencias',action='store_true');a=ap.parse_args();root=Path(a.pasta)
metrics=json.loads((root/'medicoes.json').read_text());specs=json.loads((root/'specs.json').read_text());clips=[]
for variant in ['antes','depois']:
    for scene in specs:
        p=root/f'{variant}-{scene}.mp4'
        d=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
        stream=next(s for s in d['streams'] if s['codec_type']=='video')
        assert (stream['width'],stream['height'])==(specs[scene]['w'],specs[scene]['h'])
        assert stream['nb_frames']==str(specs[scene]['fps']*specs[scene]['dur_s'])
        subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],check=True,capture_output=True)
        clips.append({'arquivo':p.name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'codec':stream['codec_name'],
                      'w':stream['width'],'h':stream['height'],'fps':stream['avg_frame_rate'],'frames':stream['nb_frames'],'dur_s':d['format']['duration']})
assert len(metrics)==6 and all(not m['errors'] and m['deterministic'] for m in metrics)
# Pixel não recebeu alteração: exige igualdade de todos os PNGs da sequência.
paths=sorted((root/'antes/pixel').glob('*.png'))
if paths:
    assert len(paths)==72
    pairs=[(p,root/'depois/pixel'/p.name) for p in paths]
else:
    paths=sorted(root.glob('antes-pixel-*.png'))
    assert len(paths)>=8
    pairs=[(p,root/p.name.replace('antes-','depois-',1)) for p in paths]
if a.exigir_sequencias:assert len(paths)==72,'gere/restaure as sequências completas antes da validação exigente'
pixel_equal=all(p.read_bytes()==q.read_bytes() for p,q in pairs)
assert pixel_equal,'pixel mudou na comparação: revisar antes de decidir'
result={'modo':'tecnico-local','avaliacao_semantica_automatica':False,'clips':clips,'pixel_72_png_identicos':pixel_equal if len(paths)==72 else None,'pixel_pngs_verificados':len(paths),
        'specs_sha256':hashlib.sha256((root/'specs.json').read_bytes()).hexdigest(),'limitacoes':['clipes sem áudio','12fps não valida movimento em 30fps','heap JS não inclui memória completa do browser/GPU']}
(root/'validacao-artefatos.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'clips_decodificados':len(clips),'pixel_pngs_identicos':pixel_equal,'pixel_pngs_verificados':len(paths)}))
