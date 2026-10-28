"""Generate native OpenFOAM v1912 dictionaries; no synthetic fields."""
import json
from pathlib import Path
from .model import Scenario, humidity_ratio, RHO, CP, HFG
from .geometry import geometry_for

HEADER = 'FoamFile { version 2.0; format ascii; class %s; object %s; }\n'

def write(root, path, body, cls='dictionary'):
    p = root/path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(HEADER % (cls,p.name)+body+'\n')

def generate(root: Path, s: Scenario):
    root.mkdir(parents=True, exist_ok=True)
    (root/'kitchen.foam').touch()
    (root/'scenario.json').write_text(s.model_dump_json(indent=2))
    config=geometry_for(s.layout_id,s.mesh)
    lx,ly,lz=config['dimensions'];n=config['cells']
    write(root,'system/blockMeshDict',f'''convertToMeters 1;
vertices ((0 0 0)({lx} 0 0)({lx} {ly} 0)(0 {ly} 0)(0 0 {lz})({lx} 0 {lz})({lx} {ly} {lz})(0 {ly} {lz}));
blocks (hex (0 1 2 3 4 5 6 7) ({n[0]} {n[1]} {n[2]}) simpleGrading (1 1 1));
edges ();
boundary (
floor {{ type wall; faces ((0 3 2 1)); }}
ceiling {{ type wall; faces ((4 5 6 7)); }}
west {{ type wall; faces ((0 4 7 3)); }}
east {{ type wall; faces ((1 2 6 5)); }}
south {{ type wall; faces ((0 1 5 4)); }}
north {{ type wall; faces ((3 7 6 2)); }}
);
mergePatchPairs ();''')
    patches=config['patches'];zones=config['zones']
    def box(b): return '('+' '.join(map(str,b[:3]))+') ('+' '.join(map(str,b[3:]))+')'
    actions=[]
    for name,(patch,b) in patches.items():
        actions += [f'{{ name {name}; type faceSet; action new; source patchToFace; sourceInfo {{ name {patch}; }} }}',f'{{ name {name}; type faceSet; action subset; source boxToFace; sourceInfo {{ box {box(b)}; }} }}']
    for name,b in zones.items():
        actions += [f'{{ name {name}; type cellSet; action new; source boxToCell; sourceInfo {{ box {box(b)}; }} }}',f'{{ name {name}; type cellZoneSet; action new; source setToCellZone; sourceInfo {{ set {name}; }} }}']
    write(root,'system/topoSetDict','actions (\n'+'\n'.join(actions)+'\n);')
    write(root,'system/createPatchDict','pointSync false;\npatches (\n'+'\n'.join(f'{{ name {name}; patchInfo {{ type {"wall" if name.startswith("hood") and not s.hoods[int(name[-1])-1] else "patch"}; }} constructFrom set; set {name}; }}' for name in patches)+'\n);')
    walls=['floor','ceiling','west','east','south','north']
    allpatch=walls+list(patches)
    sw=humidity_ratio(s.supply_c,s.supply_rh)
    tw=humidity_ratio(s.transfer_c,s.transfer_rh)
    # flowRateInletVelocity uses positive inward volumetric flow; negative extracts.
    bc={key:{} for key in ['U','T','w','p_rgh','p','k','epsilon','nut','alphat']}
    for p in allpatch:
        wall=p in walls or (p.startswith('hood') and not s.hoods[int(p[-1])-1])
        supply=p.startswith('supply')
        extraction=p.startswith('extract') or (p.startswith('hood') and not wall)
        if wall:
            bc['U'][p]='type fixedValue; value uniform (0 0 0);'
        elif supply or extraction:
            q=s.supply_lps/2000 if supply else (-s.exhaust_lps/2000 if p.startswith('extract') else -850/3600)
            bc['U'][p]=f'type flowRateInletVelocity; volumetricFlowRate constant {q}; extrapolateProfile no; value uniform (0 0 0);'
        else: bc['U'][p]='type pressureNormalInletOutletVelocity; value uniform (0 0 0);'
        for key,inval,default in [('T',s.supply_c+273.15,s.transfer_c+273.15),('w',sw,tw),('k',.003,.003),('epsilon',.001,.001)]:
            if wall:
                bc[key][p]=('type kqRWallFunction; value uniform .003;' if key=='k' else 'type epsilonWallFunction; value uniform .001;' if key=='epsilon' else 'type zeroGradient;')
            elif supply: bc[key][p]=f'type fixedValue; value uniform {inval};'
            else: bc[key][p]=f'type inletOutlet; inletValue uniform {default}; value uniform {default};'
        bc['p_rgh'][p]='type prghTotalPressure; rho rhok; p0 uniform 0; value uniform 0;' if p.startswith('transfer') else 'type fixedFluxPressure; value uniform 0;'
        bc['p'][p]='type calculated; value uniform 0;'
        bc['nut'][p]='type nutkWallFunction; value uniform 0;' if wall else 'type calculated; value uniform 0;'
        bc['alphat'][p]='type alphatJayatillekeWallFunction; Prt .85; value uniform 0;' if wall else 'type calculated; value uniform 0;'
    dims={'U':'0 1 -1 0 0 0 0','T':'0 0 0 1 0 0 0','w':'0 0 0 0 0 0 0','p_rgh':'0 2 -2 0 0 0 0','p':'0 2 -2 0 0 0 0','k':'0 2 -2 0 0 0 0','epsilon':'0 2 -3 0 0 0 0','nut':'0 2 -1 0 0 0 0','alphat':'0 2 -1 0 0 0 0'}
    total_in=max(s.supply_lps/1000,s.exhaust_lps/1000+sum(s.hoods)*850/3600)
    transfer_in=max(0,total_in-s.supply_lps/1000)
    ua=sum(s.fcus)*s.fcu_kw*1000/10
    heat=s.people*s.sensible_w+5*s.cooking_w
    t_guess=(RHO*CP*(s.supply_lps/1000*s.supply_c+transfer_in*s.transfer_c)+heat+ua*s.fcu_coil_c)/(RHO*CP*total_in+ua)
    water=s.people*s.latent_w/HFG+5*s.cooking_kg_h/3600
    w_guess=(s.supply_lps/1000*sw+transfer_in*tw+water/RHO)/total_in
    initial={'U':'(0 0 0)','T':min(50,max(5,t_guess))+273.15,'w':w_guess,'p_rgh':0,'p':0,'k':.003,'epsilon':.001,'nut':0,'alphat':0}
    for field in bc:
        write(root,'0/'+field,f'dimensions [{dims[field]}];\ninternalField uniform {initial[field]};\nboundaryField {{\n'+'\n'.join(f'{p} {{ {v} }}' for p,v in bc[field].items())+'\n}', 'volVectorField' if field=='U' else 'volScalarField')
    write(root,'constant/hRef',f"dimensions [0 1 0 0 0 0 0]; value {config['hRef']};",'uniformDimensionedScalarField')
    write(root,'constant/g','dimensions [0 1 -2 0 0 0 0]; value (0 0 -9.81);','uniformDimensionedVectorField')
    write(root,'constant/transportProperties',f'transportModel Newtonian;\nnu [0 2 -1 0 0 0 0] 1.5e-5;\nbeta [0 0 0 -1 0 0 0] 0.003366;\nTRef [0 0 0 1 0 0 0] {s.transfer_c+273.15};\nPr .71;\nPrt .85;')
    write(root,'constant/turbulenceProperties','simulationType RAS; RAS { RASModel kEpsilon; turbulence on; printCoeffs on; }')
    # Absolute volumeMode integrates total specified power or water generation over selected cells.
    thermal=[]; moisture=[]
    def source(name,zone,field,su,sp=0,mode='absolute',kind='scalar'):
        return f'{name} {{ type {kind}SemiImplicitSource; active true; selectionMode cellZone; cellZone {zone}; volumeMode {mode}; injectionRateSuSp {{ {field} ({su} {sp}); }} }}'
    thermal.append(source('peopleHeat','people','T',s.people*s.sensible_w/(RHO*CP)))
    moisture.append(source('peopleWater','people','w',s.people*s.latent_w/(HFG*RHO)))
    for i in range(len(config['hoodCentres'])):
        thermal.append(source(f'cookingHeat{i+1}',f'cook{i+1}','T',s.cooking_w/(RHO*CP)))
        moisture.append(source(f'cookingWater{i+1}',f'cook{i+1}','w',s.cooking_kg_h/(3600*RHO)))
    for i,on in enumerate(s.fcus):
        if on:
            names=config['fcuZones'][i]
            ua=s.fcu_kw*1000/10/len(names) # total nominal unit UA is not multiplied by outlet count
            direction=config['fcuDirection']
            vector='('+' '.join(str(d*s.fcu_speed) for d in direction)+')'
            for zone in names:
                thermal.append(source(f'{zone}Cooling',zone,'T',ua*(s.fcu_coil_c+273.15)/(RHO*CP),-ua/(RHO*CP)))
                thermal.append(source(f'{zone}Fan',zone,'U',vector,-1,'specific','vector'))
    write(root,'constant/fvOptions','\n'.join(thermal))
    write(root,'system/fvSchemes','''ddtSchemes { default steadyState; }
gradSchemes { default Gauss linear; }
divSchemes { default none; div(phi,U) bounded Gauss upwind; div(phi,T) bounded Gauss upwind; div(phi,w) Gauss upwind; div(phi,k) bounded Gauss upwind; div(phi,epsilon) bounded Gauss upwind; div((nuEff*dev2(T(grad(U))))) Gauss linear; }
laplacianSchemes { default Gauss linear corrected; }
interpolationSchemes { default linear; }
snGradSchemes { default corrected; }
fluxRequired { default no; p_rgh; w; T; }''')
    write(root,'system/fvSolution','''solvers {
p_rgh { solver GAMG; tolerance 1e-10; relTol 0; smoother GaussSeidel; }
"(U|T|k|epsilon|w)" { solver smoothSolver; smoother symGaussSeidel; tolerance 1e-10; relTol .01; }
}
SIMPLE { nNonOrthogonalCorrectors 0; pRefCell 0; pRefValue 0; consistent no; }
relaxationFactors { fields { p_rgh 1; } equations { U .15; T .3; k .3; epsilon .3; w .7; } }''')
    funcs=f'''waterVapour {{
 type scalarTransport; libs ("libsolverFunctionObjects.so"); field w;
 phi phi; rho none; schemesField w; nCorr 2; alphaD 1.66666667; alphaDt 1.42857143;
 executeControl timeStep; executeInterval 1; writeControl writeTime;
 fvOptions {{ {' '.join(moisture)} }}
}}
'''
    write(root,'system/controlDict',f'''application buoyantBoussinesqSimpleFoam;
startFrom startTime; startTime 0; stopAt endTime; endTime {s.iterations}; deltaT 1;
writeControl timeStep; writeInterval {s.iterations}; purgeWrite 1; writeFormat ascii; writePrecision 10; writeCompression off; timeFormat general; timePrecision 6; runTimeModifiable false;
functions {{ {funcs} }}''')
    meta={**config,'initialGuess':{'temperatureC':t_guess,'humidityRatio':w_guess,'note':'Well-mixed initialization only; all displayed results require the full 3D solver.'},'structuralHeight':4.8,'rho':RHO,'cp':CP,'sensibleW':heat,'waterKgS':water}
    (root/'geometry.json').write_text(json.dumps(meta,indent=2))
    (root/'prepare_pressure.py').write_text((Path(__file__).parent/'prepare_pressure.py').read_text())
    (root/'Allrun').write_text('''#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export WM_PROJECT_DIR="${WM_PROJECT_DIR:-/usr/share/openfoam}"
export FOAM_ETC="${FOAM_ETC:-$WM_PROJECT_DIR/etc}"
blockMesh > log.blockMesh 2>&1
topoSet > log.topoSet 2>&1
createPatch -overwrite > log.createPatch 2>&1
python3 prepare_pressure.py > log.pressure 2>&1
checkMesh -allGeometry -allTopology > log.checkMesh 2>&1
grep -q 'Mesh OK' log.checkMesh
buoyantBoussinesqSimpleFoam > log.solver 2>&1
postProcess -func writeCellCentres -latestTime > log.centres 2>&1
''')
    (root/'Allrun').chmod(0o755)
