#!/usr/bin/env python3
"""Instala timer de usuário SOMENTE após um ensaio bem sucedido no catálogo."""
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess

ap=argparse.ArgumentParser();ap.add_argument('--estado',required=True);ap.add_argument('--calendario',default='*-*-* 04:00:00 UTC');args=ap.parse_args()
root=Path(__file__).resolve().parent;state=Path(args.estado).resolve()
with sqlite3.connect(state/'catalogo.sqlite') as db:
    last=db.execute('SELECT estado FROM execucoes ORDER BY inicio DESC LIMIT 1').fetchone()
    if not last or last[0]!='ok':raise SystemExit('Exige último ensaio controlado com estado ok antes de ativar.')
units=Path.home()/'.config/systemd/user';units.mkdir(parents=True,exist_ok=True)
service=f'''[Unit]
Description=videos-auto coleta limitada de referências e propostas visuais
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 "{root}/ciclo.py" --config "{root}/fontes.json" --estado "{state}"
TimeoutStartSec=150
MemoryMax=256M
CPUQuota=50%
Nice=10
NoNewPrivileges=true
UMask=0077
'''
timer=f'''[Unit]
Description=videos-auto mineração visual diária ajustável
[Timer]
OnCalendar={args.calendario}
RandomizedDelaySec=300
Persistent=true
Unit=videos-auto-mineracao.service
[Install]
WantedBy=timers.target
'''
if '\n' in args.calendario:raise SystemExit('calendário inválido')
subprocess.run(['systemd-analyze','calendar',args.calendario],check=True,capture_output=True)
for name,content in [('videos-auto-mineracao.service',service),('videos-auto-mineracao.timer',timer)]:
    p=units/name
    if p.exists() and p.read_text()!=content:
        p.with_suffix(p.suffix+'.anterior').write_text(p.read_text())
    p.write_text(content)
subprocess.run(['systemctl','--user','daemon-reload'],check=True)
subprocess.run(['systemctl','--user','start','videos-auto-mineracao.service'],check=True)
subprocess.run(['systemctl','--user','enable','--now','videos-auto-mineracao.timer'],check=True)
print(json.dumps({'timer':'videos-auto-mineracao.timer','estado':str(state),'calendario':args.calendario}))
