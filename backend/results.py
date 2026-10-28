"""Export native finite-volume fields and audit face-based conservation."""
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from .model import Scenario, RHO, CP, relative_humidity

NUM = r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'

def clean(text):
    return re.sub(r'//[^\n]*|/\*.*?\*/', '', text, flags=re.S)

def values(text, key, count, vector=False):
    m = re.search(r'\b'+re.escape(key)+r'\s+(nonuniform\s+List<\w+>\s+(\d+)\s*\((.*?)\)\s*;|uniform\s+([^;]+);)',text,re.S)
    if not m:
        raise ValueError(f'Missing {key}')
    width=3 if vector else 1
    if m[2]:
        if int(m[2])!=count: raise ValueError(f'{key}: expected {count}, got {m[2]}')
        a=np.array([float(x) for x in re.findall(NUM,m[3])])
        if len(a)!=count*width: raise ValueError(f'Invalid {key} data')
        return a.reshape((count,3)) if vector else a
    a=np.array([float(x) for x in re.findall(NUM,m[4])])
    return np.tile(a,(count,1)) if vector else np.full(count,a[0])

def blocks(text):
    """Named top-level dictionary blocks (not regex-balanced braces)."""
    out={}; depth=0; start=0; name=''
    for m in re.finditer(r'[A-Za-z_][\w]*|[{}]', text):
        t=m[0]
        if t=='{':
            if depth==0: start=m.end(); blockname=name
            depth+=1
        elif t=='}':
            depth-=1
            if depth==0: out[blockname]=text[start:m.start()]
        elif depth==0: name=t
    return out

def list_data(path):
    text=clean(path.read_text())
    # Numeric mesh list follows FoamFile header, whose braces are balanced.
    pos=text.find('}')+1
    m=re.search(r'\b(\d+)\s*\(',text[pos:])
    if not m: raise ValueError(f'No list in {path}')
    return int(m[1]), text[pos+m.end():text.rfind(')')]

def read_mesh(root):
    mesh=root/'constant/polyMesh'
    n,body=list_data(mesh/'points')
    points=np.array([float(x) for x in re.findall(NUM,body)]).reshape(n,3)
    nf,body=list_data(mesh/'faces')
    faces=[np.array([int(x) for x in re.findall(r'\d+',row)]) for row in re.findall(r'\d+\s*\(([^)]+)\)',body)]
    if len(faces)!=nf: raise ValueError('Face count mismatch')
    centers=np.array([points[f].mean(axis=0) for f in faces])
    area=np.array([sum((np.cross(points[f[j]]-points[f[0]], points[f[j+1]]-points[f[0]]) for j in range(1,len(f)-1)),start=np.zeros(3))/2 for f in faces])
    no,body=list_data(mesh/'owner'); owner=np.array([int(x) for x in re.findall(r'\d+',body)])
    nn,body=list_data(mesh/'neighbour'); neighbour=np.array([int(x) for x in re.findall(r'\d+',body)])
    if len(owner)!=no or len(neighbour)!=nn: raise ValueError('Connectivity mismatch')
    boundary={}
    for name,b in blocks(clean((mesh/'boundary').read_text())).items():
        m=re.search(r'nFaces\s+(\d+);',b); st=re.search(r'startFace\s+(\d+);',b)
        if m and st: boundary[name]=(int(st[1]),int(m[1]))
    return centers,area,owner,neighbour,boundary

def read_field(path, nc, boundary, vector=False):
    text=clean(path.read_text())
    inside=values(text,'internalField',nc,vector)
    bd=blocks(blocks(text)['boundaryField'])
    out={}
    for p,(start,n) in boundary.items():
        if n: out[p]=values(bd[p],'value',n,vector) if re.search(r'\bvalue\s',bd[p]) else None
    return inside,out

def export(root: Path):
    geometry=json.loads((root/'geometry.json').read_text())
    inputs=json.loads((root/'scenario.json').read_text())
    inputs.setdefault('layout_id',geometry.get('layoutId','provisional-v1'))
    s=Scenario.model_validate(inputs)
    times=sorted([p for p in root.iterdir() if p.is_dir() and re.fullmatch(r'\d+(\.\d+)?',p.name) and float(p.name)>0],key=lambda p:float(p.name))
    if not times: raise ValueError('No solver output time directory')
    time=times[-1]; nx,ny,nz=geometry['cells']; nc=nx*ny*nz
    centers,area,owner,neighbour,boundary=read_mesh(root)
    cc,_=read_field(time/'C',nc,boundary,True)
    fields={}; bfields={}
    for key in ['T','w','p_rgh','U','nut','alphat']:
        fields[key],bfields[key]=read_field(time/key,nc,boundary,key=='U')
    phi,pb=read_field(time/'phi',len(neighbour),boundary)
    T=fields['T']-273.15; w=fields['w']; U=fields['U']; speed=np.linalg.norm(U,axis=1)
    rh=np.array([relative_humidity(t,q) for t,q in zip(T,w)])
    # Static pressure relative to hydrostatic adjacent air at TRef. Solver p_rgh is kinematic.
    rhok=1-.003366*(fields['T']-(s.transfer_c+273.15))
    pressure=RHO*(fields['p_rgh']+(rhok-1)*(-9.81*(cc[:,2]-geometry.get('hRef',0.))))
    allfields=np.column_stack([cc,T,rh,w*1000,U,pressure])
    if not np.isfinite(allfields).all(): raise ValueError('Non-finite solver fields; export refused')
    meshlog=(root/'log.checkMesh').read_text()
    mesh_quality={}
    for key,pattern in {'maxAspectRatio':r'Max aspect ratio = ('+NUM+')','maxNonOrthogonality':r'Mesh non-orthogonality Max: ('+NUM+')','maxSkewness':r'Max skewness = ('+NUM+')','volumeM3':r'Total volume = ('+NUM+')'}.items():
        m=re.search(pattern,meshlog)
        if m: mesh_quality[key]=float(m[1])
    solverlog=(root/'log.solver').read_text()
    if 'OPENFOAM=1912' not in solverlog: raise ValueError('This exporter requires verified OpenFOAM v1912 output')
    if not solverlog.rstrip().endswith('End') or 'FOAM FATAL' in solverlog: raise ValueError('Solver did not finish successfully')
    logged_times=re.findall(r'^Time = (\d+)$',solverlog,re.M)
    if not logged_times or float(logged_times[-1])!=float(time.name): raise ValueError('Native fields and final solver iteration do not match')
    records={}
    traces={}
    for tim,body in re.findall(r'Time = (\d+)\n(.*?)(?=\nTime = |\Z)',solverlog,re.S):
        for key,ini,fin in re.findall(r'Solving for (\w+), Initial residual = ('+NUM+r'), Final residual = ('+NUM+r')',body):
            # Keep the first scalar corrector initial residual.
            traces.setdefault(key,[])
            if not traces[key] or traces[key][-1][0]!=int(tim): traces[key].append([int(tim),float(ini)])
            records[key]={'initial':traces[key][-1][1],'linearFinal':float(fin)}
    local=np.zeros(nc)
    np.add.at(local,owner[:len(phi)],phi); np.add.at(local,neighbour,-phi)
    fluxes=[]; net=0.; throughput=0.; heat=0.; water=0.; pressure_boundary=0.
    for patch,(start,n) in boundary.items():
        if not n: continue
        q=pb[patch]
        if q is None: raise ValueError(f'Missing native face flux: {patch}')
        own=owner[start:start+n]; np.add.at(local,own,q)
        net+=float(q.sum()); throughput+=float(np.maximum(q,0).sum())
        ar=np.linalg.norm(area[start:start+n],axis=1)
        distance=np.linalg.norm(centers[start:start+n]-cc[own],axis=1)
        bT=bfields['T'][patch]; bw=bfields['w'][patch]
        if bT is None: bT=fields['T'][own]
        if bw is None: bw=fields['w'][own]
        if patch.startswith('transfer'):
            rhob=1-.003366*(bT-(s.transfer_c+273.15))
            ub=bfields['U'][patch]
            head=np.where(q<0,.5*rhob*np.sum(ub*ub,axis=1),0.)
            pg=RHO*(bfields['p_rgh'][patch]+(rhob-1)*(-9.81*(centers[start:start+n,2]-geometry.get('hRef',0.)))+head)
            pressure_boundary=max(pressure_boundary,float(np.max(abs(pg))))
        # Upwind matches the generated Gauss upwind discretisation.
        Tf=np.where(q<0,bT,fields['T'][own]); wf=np.where(q<0,bw,w[own])
        # Use exact patch diffusivities used by OpenFOAM; zeroGradient => zero gradient.
        an=bfields['alphat'][patch]; an=fields['alphat'][own] if an is None else an
        nt=bfields['nut'][patch]; nt=fields['nut'][own] if nt is None else nt
        h=RHO*CP*np.sum(q*(Tf-273.15)-(1.5e-5/.71+an)*(bT-fields['T'][own])/distance*ar)
        m=RHO*np.sum(q*wf-(2.5e-5+nt/.7)*(bw-w[own])/distance*ar)
        heat+=float(h); water+=float(m)
        fluxes.append({'patch':patch,'outwardLps':float(q.sum()*1000),'inwardLps':float(-np.minimum(q,0).sum()*1000),'heatW':float(h),'waterKgS':float(m),'areaM2':float(ar.sum())})
    fcu_heat=0.
    for i,on in enumerate(s.fcus):
        if on:
            names=geometry.get('fcuZones',[["fcu1"],["fcu2"]])[i]
            for name in names:
                b=geometry['zones'][name];sel=np.all((cc>=b[:3])&(cc<=b[3:]),axis=1)
                fcu_heat+=s.fcu_kw*1000/10/len(names)*((s.fcu_coil_c+273.15)-float(fields['T'][sel].mean()))
    source_heat=geometry['sensibleW']+fcu_heat; source_water=geometry['waterKgS']
    heat_error=abs(heat-source_heat)/max(abs(source_heat),geometry['sensibleW'],1)*100
    water_error=abs(water-source_water)/max(abs(source_water),1e-7)*100
    mass_error=abs(net)/max(throughput,1e-9)*100
    local_error=float(np.sum(abs(local)))/max(throughput,1e-9)*100
    thresholds={'Ux':1e-4,'Uy':1e-4,'Uz':1e-4,'p_rgh':1e-4,'T':1e-5,'w':1e-6,'k':1e-4,'epsilon':1e-4}
    residual_ok=all(key in records and len(traces[key])>=20 and max(p[1] for p in traces[key][-20:])<tol for key,tol in thresholds.items())
    checks={'pressureBoundary':pressure_boundary<.001,'mesh': 'Mesh OK' in meshlog and 'Failed' not in meshlog,'mass':mass_error<.1 and local_error<.1,'heat':heat_error<2,'water':water_error<2,'residuals':residual_ok,'physical':bool(np.all(rh>=0) and np.all(w>=0) and np.all(rh<=100) and np.all(T>0) and np.all(T<60))}
    occupied=(cc[:,2]>=.1)&(cc[:,2]<=1.8)
    comfort=occupied&(T>=22)&(T<=26)&(rh>=40)&(rh<=65)&(speed<=.25)
    def stats(a): return {'min':float(a.min()),'max':float(a.max()),'mean':float(a.mean())}
    report={'status':'numerically_checked' if all(checks.values()) else 'preliminary','checks':checks,'cells':nc,'meshQuality':mesh_quality,'iteration':float(time.name),'residuals':records,'residualThresholds':thresholds,'residualHistory':{k:v[::max(1,len(v)//120)] for k,v in traces.items()},'massErrorPercent':mass_error,'transferPressureMaxGaugePa':pressure_boundary,'netBoundaryLps':net*1000,'localContinuityPercent':local_error,'maxCellImbalanceLps':float(np.max(abs(local))*1000),'heat':{'outwardW':heat,'sourceW':source_heat,'errorPercent':heat_error,'fcuW':fcu_heat},'water':{'outwardKgS':water,'sourceKgS':source_water,'errorPercent':water_error},'patches':fluxes,'occupied':{'temperature':stats(T[occupied]),'rh':stats(rh[occupied]),'speed':stats(speed[occupied]),'screenPercent':float(100*comfort.sum()/occupied.sum()),'note':'Screen only: 22–26°C, 40–65% RH and speed ≤0.25 m/s. No PMV/PPD claim; MRT, clothing and verified activity are missing.'},'ranges':{'temperature':stats(T),'rh':stats(rh),'humidity':stats(w*1000),'velocity':stats(speed),'pressure':stats(pressure)},'assumptions':[geometry.get('layoutRegistration','HVAC drawing was not attached: room shape, opening sizes and all equipment coordinates are provisional.'),f"Occupied dimensions {geometry['dimensions']}; 2.9–4.8 m ceiling void excluded.",'Steady RANS k-epsilon, Boussinesq, constant dry-air density 1.2 kg/m³, atmospheric pressure 101325 Pa. Moisture is a dilute passive humidity-ratio scalar.','Adiabatic walls; no solar, envelope conduction, radiation, solid equipment or hood capture geometry.','People: distributed occupied-region source, 75 W sensible + 55 W latent/person by default; provisional split referenced to ASHRAE Fundamentals 2021 Ch.18, Table 1 standing/light work; walking slowly. Confirm activity and room-temperature correction.','Cooking sources are independently configurable per station; default zero because equipment schedules are missing. Hood OFF caps that opening; it does not switch cooking off.',geometry.get('fcuDescription','FCUs use local momentum actuators and sensible UA cooling (nominal kW at 10 K difference); no added mass or dehumidification.'),geometry.get('transferDescription','Legacy provisional west-wall doorway; pressure-driven flow.'),'First-order upwind on provisional coarse Cartesian mesh. Mesh-independence study and measured-data validation are not performed.','RH >100% is flagged: condensation is not modelled. Comfort criteria are a configurable-data screening proxy, not ASHRAE 55 certification.']}
    # Canonical structured grid maps exported cell centres; do not assume native cell ordering.
    ijk=np.rint(cc/(np.array(geometry['dimensions'])/np.array([nx,ny,nz]))-.5).astype(int)
    order=np.argsort(ijk[:,0]+nx*(ijk[:,1]+ny*ijk[:,2]))
    payload={'schema':1,'solver':'OpenFOAM v1912 / buoyantBoussinesqSimpleFoam + scalarTransport','scenario':s.model_dump(),'geometry':geometry,'report':report,'columns':['x','y','z','temperature','rh','humidity','ux','uy','uz','pressure'],'data':np.round(allfields[order],7).tolist()}
    # Provenance covers all native fields used for exported results.
    files=[time/x for x in ['T','w','U','p_rgh','phi','nut','alphat','C']]
    payload['provenance']={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    payload['inputProvenance']={str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for d in ['0','system','constant'] for f in (root/d).rglob('*') if f.is_file()}
    payload['inputProvenance'].update({name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['scenario.json','geometry.json','prepare_pressure.py','Allrun'] if (root/name).exists()})
    np.savetxt(root/'fields.csv',allfields[order],delimiter=',',fmt='%.10g',header='x_m,y_m,z_m,temperature_C,relative_humidity_pct,humidity_ratio_g_per_kg_dry_air,u_x_m_per_s,u_y_m_per_s,u_z_m_per_s,pressure_gauge_Pa',comments='')
    (root/'results.json').write_text(json.dumps(payload,allow_nan=False,separators=(',',':')))
    (root/'validation.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    return payload
