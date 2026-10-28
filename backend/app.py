"""Local engineering workbench. Bind to loopback; Docker access is trusted local capability."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .case import generate
from .model import Scenario
from .results import export
from .layout import LAYOUT_REVIEW

ROOT=Path(__file__).resolve().parents[1]
RUNS=ROOT/'runs'; RUNS.mkdir(exist_ok=True)
SAVED=ROOT/'scenarios'; SAVED.mkdir(exist_ok=True)
app=FastAPI(title='Demo Kitchen / CFD', version='0.1.0')
lock=threading.Lock()
jobs={}

def runtime():
    mode=os.environ.get('FOAM_MODE','auto')
    if mode!='docker' and shutil.which('buoyantBoussinesqSimpleFoam'): return 'native'
    if mode=='native': return 'unavailable'
    if shutil.which('docker'):
        try:
            p=subprocess.run(docker_base()+['image','inspect',os.environ.get('FOAM_IMAGE','demo-kitchen-openfoam:1912')],capture_output=True,timeout=10,env=docker_env())
            if p.returncode==0: return 'docker'
        except (OSError,subprocess.TimeoutExpired): pass
    return 'unavailable'

def docker_env():
    child=os.environ.copy()
    for key in ['DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH']:
        child.pop(key,None)
    return child

def docker_base():
    return ['docker','--host=unix:///var/run/docker.sock']

def folder(id):
    if id=='baseline': return ROOT/'cases/baseline'
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',id): raise HTTPException(404,'Unknown run')
    p=RUNS/id
    if not p.is_dir() or not p.resolve().is_relative_to(RUNS.resolve()): raise HTTPException(404,'Unknown run')
    return p

def worker(id,s,mode):
    p=folder(id)
    try:
        jobs[id]['stage']='Generating mesh'
        generate(p,s)
        # Single argument shell command is constant, never interpolated user input.
        if mode=='docker':
            cmd=docker_base()+['run','--rm','--name',f'kitchen-{id}','--user',f'{os.getuid()}:{os.getgid()}','--mount',f'type=bind,src={p},dst=/case','--workdir','/case',os.environ.get('FOAM_IMAGE','demo-kitchen-openfoam:1912'),'bash Allrun']
        else: cmd=['bash','Allrun']
        with (p/'log.runner').open('w') as log:
            process=subprocess.Popen(cmd,cwd=p,stdout=log,stderr=subprocess.STDOUT,env=docker_env())
            try: rc=process.wait(timeout=3600)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
                if mode=='docker': subprocess.run(docker_base()+['rm','-f',f'kitchen-{id}'],capture_output=True,env=docker_env())
                raise RuntimeError('Simulation exceeded the 60 minute limit')
        if rc: raise RuntimeError(f'OpenFOAM exited with code {rc}; inspect the logs below')
        jobs[id]['stage']='Exporting native fields and checking balances'
        result=export(p)
        jobs[id].update(status='done',stage='Numerical checks passed' if result['report']['status']=='numerically_checked' else 'Finished · preliminary, review checks')
    except Exception as exc:
        jobs[id].update(status='error',stage='Simulation failed',error=str(exc))
    finally:
        (p/'job.json').write_text(json.dumps(jobs[id]))
        lock.release()

@app.get('/api/health')
def health(): return {'api':'ok','runtime':runtime(),'solver':'OpenFOAM v1912','drawingAttached':True,'layoutStatus':LAYOUT_REVIEW['status'],'layoutApplied':True}

@app.get('/api/layout')
def layout_review(): return LAYOUT_REVIEW

@app.get('/api/layout/diagram')
def layout_diagram(): return FileResponse(ROOT/'docs/layout-review.svg',media_type='image/svg+xml')

@app.get('/api/defaults')
def defaults(): return Scenario().model_dump()

@app.post('/api/runs',status_code=202)
def run(s:Scenario):
    if not lock.acquire(blocking=False): raise HTTPException(409,'Another simulation is running; wait for it to finish.')
    mode=runtime()
    if mode=='unavailable':
        lock.release(); raise HTTPException(503,'OpenFOAM unavailable. Build Dockerfile.foam or install OpenFOAM v1912. Generate a runnable case using Export case.')
    id=uuid.uuid4().hex; (RUNS/id).mkdir()
    jobs[id]={'id':id,'status':'running','stage':'Queued','name':s.name,'created':datetime.now(timezone.utc).isoformat()}
    (RUNS/id/'job.json').write_text(json.dumps(jobs[id]))
    threading.Thread(target=worker,args=(id,s,mode),daemon=True).start()
    return jobs[id]

@app.get('/api/runs')
def list_runs():
    result=[]
    for p in [ROOT/'cases/baseline',*sorted(RUNS.iterdir(),key=lambda p:p.stat().st_mtime,reverse=True)]:
        if not p.is_dir(): continue
        if (p/'scenario.json').exists():
            s=json.loads((p/'scenario.json').read_text()); row={'id':p.name,'name':s['name'],'inputs':s,'status':'done' if (p/'results.json').exists() else 'incomplete'}
            row['layoutId']=json.loads((p/'geometry.json').read_text()).get('layoutId','provisional-v1') if (p/'geometry.json').exists() else 'provisional-v1'
            if (p/'validation.json').exists(): row['report']=json.loads((p/'validation.json').read_text())
            result.append(row)
    return result

@app.get('/api/runs/{id}')
def progress(id:str):
    p=folder(id)
    state=dict(jobs.get(id,{'id':id,'status':'done' if (p/'results.json').exists() else 'incomplete'}))
    logs=[]
    for name in ['runner','blockMesh','topoSet','createPatch','pressure','checkMesh','solver','centres']:
        f=p/f'log.{name}'
        if f.exists():
            text=f.read_text(errors='replace')
            logs.append(f'--- {name} ---\n'+text[-5000:])
            if state['status']=='running': state['stage']={'blockMesh':'Building mesh','topoSet':'Selecting boundaries and source zones','createPatch':'Creating physical openings','pressure':'Matching adjacent hydrostatic pressure','checkMesh':'Checking mesh quality','solver':'Solving momentum, energy and water vapour','centres':'Exporting cell centres'}.get(name,state['stage'])
            if name=='solver':
                ts=re.findall(r'^Time = (\d+)$',text,re.M)
                state['iteration']=int(ts[-1]) if ts else 0
    if (p/'scenario.json').exists(): state['total']=json.loads((p/'scenario.json').read_text())['iterations']
    state['logs']='\n'.join(logs)[-16000:]
    return state

@app.get('/api/runs/{id}/results')
def results(id:str):
    f=folder(id)/'results.json'
    if not f.exists(): raise HTTPException(404,'No exported solver output exists')
    return FileResponse(f,media_type='application/json')

@app.get('/api/runs/{id}/archive')
def archive(id:str):
    p=folder(id); target=RUNS/f'{id}.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for f in p.rglob('*'):
            if f.is_file() and not f.is_symlink(): z.write(f,f.relative_to(p))
    return FileResponse(target,filename=f'kitchen-{id}.zip')

@app.post('/api/case')
def case(s:Scenario):
    id=uuid.uuid4().hex; p=RUNS/id; generate(p,s)
    return {'id':id,'archive':f'/api/runs/{id}/archive','executed':False}

@app.get('/api/scenarios')
def scenarios(): return [json.loads(f.read_text()) for f in sorted(SAVED.glob('*.json'))]

@app.post('/api/scenarios',status_code=201)
def save(s:Scenario):
    id=uuid.uuid4().hex; record={'id':id,'scenario':s.model_dump()}
    (SAVED/f'{id}.json').write_text(json.dumps(record,indent=2))
    return record

if (ROOT/'frontend/dist').exists(): app.mount('/',StaticFiles(directory=ROOT/'frontend/dist',html=True),name='frontend')
