"""Standalone, stdlib-only preparation of hydrostatic external total-pressure profiles.
Executed inside each generated OpenFOAM case after createPatch.
"""
from pathlib import Path
import re
import json


def prepare(root=Path('.')):
    def text(p):
        return re.sub(r'//[^\n]*|/\*.*?\*/','',(root/p).read_text(),flags=re.S)
    h_ref=json.loads((root/'geometry.json').read_text()).get('hRef',0.) if (root/'geometry.json').exists() else 0.
    mesh=Path('constant/polyMesh')
    p=text(mesh/'points');p=p[p.index('}')+1:]
    data=p[p.index('(')+1:p.rfind(')')]
    points=[tuple(map(float,row.split())) for row in re.findall(r'\(([^)]+)\)',data)]
    f=text(mesh/'faces');f=f[f.index('}')+1:];f=f[f.index('(')+1:f.rfind(')')]
    faces=[tuple(map(int,row.split())) for row in re.findall(r'\d+\s*\(([^)]+)\)',f)]
    boundary=text(mesh/'boundary')
    field=(root/'0/p_rgh').read_text()
    for name,n,start in re.findall(r'(transfer\d+)\s*\{[^}]*nFaces\s+(\d+);[^}]*startFace\s+(\d+);',boundary,re.S):
        values=[-9.81*(sum(points[i][2] for i in face)/len(face)-h_ref) for face in faces[int(start):int(start)+int(n)]]
        profile=f'p0 nonuniform List<scalar> {n} (\n'+'\n'.join(f'{v:.12g}' for v in values)+'\n);'
        field,count=re.subn(r'('+name+r'\s*\{[^}]*?)p0\s+(?:uniform\s+0|nonuniform\s+List<scalar>\s+\d+\s*\([^)]*\))\s*;',lambda m:m[1]+profile,field,flags=re.S)
        if count!=1: raise RuntimeError(f'Could not set hydrostatic profile on {name}')
    if field.count('p0 nonuniform List<scalar>')!=2: raise RuntimeError('Both transfer pressure profiles are required')
    (root/'0/p_rgh').write_text(field)

if __name__=='__main__': prepare()
