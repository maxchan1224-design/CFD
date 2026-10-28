#!/usr/bin/env python3
"""Generate, solve and audit an actual OpenFOAM case (local Docker default)."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.case import generate
from backend.model import Scenario
from backend.results import export

p=argparse.ArgumentParser()
p.add_argument('--case',default='cases/baseline')
p.add_argument('--scenario',help='Scenario JSON, e.g. examples/baseline.json')
p.add_argument('--native',action='store_true')
p.add_argument('--generate-only',action='store_true')
a=p.parse_args()
root=Path(a.case).resolve()
s=Scenario.model_validate_json(Path(a.scenario).read_text()) if a.scenario else Scenario()
if root.exists() and any(x.is_dir() and x.name.replace('.','',1).isdigit() and float(x.name)>0 for x in root.iterdir()):
    sys.exit('Case already contains solved times. Choose a new --case directory; existing results are preserved.')
generate(root,s)
if a.generate_only:
    print(f'Generated runnable case at {root}; execution UNVERIFIED.');sys.exit(0)
cmd=['bash','Allrun'] if a.native else ['docker','--host=unix:///var/run/docker.sock','run','--rm','--user',f'{os.getuid()}:{os.getgid()}','--mount',f'type=bind,src={root},dst=/case','-w','/case',os.environ.get('FOAM_IMAGE','demo-kitchen-openfoam:1912'),'bash Allrun']
subprocess.run(cmd,cwd=root,check=True)
r=export(root)['report']
print(json.dumps({k:r[k] for k in ['status','checks','iteration','massErrorPercent','heat','water']},indent=2))
if not all(r['checks'].values()): sys.exit(2)
