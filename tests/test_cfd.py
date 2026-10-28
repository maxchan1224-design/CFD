import json
from pathlib import Path
import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.model import Scenario, humidity_ratio, relative_humidity, HFG
from backend.case import generate
from backend.results import values, read_mesh, export
from backend.app import app


def test_psychrometrics_reference_and_temperature_dependence():
    # Independent known psychrometric reference points at 101.325 kPa.
    assert humidity_ratio(24,55)==pytest.approx(.0102439,rel=.001)
    assert humidity_ratio(15,86)==pytest.approx(.009134,rel=.001)
    assert relative_humidity(24,humidity_ratio(15,86)) < 50
    for t,rh in [(15,86),(24,55),(30,70)]:
        assert relative_humidity(t,humidity_ratio(t,rh))==pytest.approx(rh)


def test_invalid_inputs_cannot_make_nonphysical_case():
    for data in [{'supply_lps':0},{'supply_rh':110},{'people':-1},{'hoods':[True]},{'iterations':1},{'mesh':'arbitrary'}]:
        with pytest.raises(ValidationError): Scenario(**data)


def test_real_boundaries_and_total_sources(tmp_path):
    s=Scenario(layout_id='provisional-v1',hoods=[True,False,True,False,True],fcus=[True,False],cooking_w=1000,cooking_kg_h=.3)
    generate(tmp_path,s)
    u=(tmp_path/'0/U').read_text(); p=(tmp_path/'0/p_rgh').read_text()
    assert u.count('volumetricFlowRate constant -0.28;')==2  # total 560 L/s, not 1120
    assert u.count('volumetricFlowRate constant 0.145;')==2
    assert u.count('volumetricFlowRate constant -0.2361111111111111;')==3
    assert u.count('type pressureNormalInletOutletVelocity;')==2
    assert p.count('type prghTotalPressure; rho rhok; p0 uniform 0; value uniform 0;')==2
    assert 'fcu1Cooling' in (tmp_path/'constant/fvOptions').read_text()
    assert 'fcu2Cooling' not in (tmp_path/'constant/fvOptions').read_text()
    assert 'scalarTransport' in (tmp_path/'system/controlDict').read_text()
    meta=json.loads((tmp_path/'geometry.json').read_text())
    assert meta['sensibleW']==5375
    assert meta['waterKgS']==pytest.approx(5*55/HFG+5*.3/3600)
    assert meta['dimensions'][2]==2.9
    assert 'hood2; patchInfo { type wall;' in (tmp_path/'system/createPatchDict').read_text()


def test_field_reader_checks_counts_and_vectors():
    assert values('internalField uniform 2;', 'internalField',3).tolist()==[2,2,2]
    assert values('internalField nonuniform List<vector> 2 ((1 2 3)(4 5 6));','internalField',2,True).tolist()==[[1,2,3],[4,5,6]]
    with pytest.raises(ValueError): values('internalField nonuniform List<scalar> 2 (1 2);','internalField',3)
    with pytest.raises(ValueError): values('internalField nonuniform List<scalar> 2 (1);','internalField',2)


def test_api_rejects_invalid_case_and_traversal():
    client=TestClient(app)
    assert client.get('/api/defaults').json()['supply_lps']==290
    assert client.post('/api/runs',json={'supply_lps':-290}).status_code==422
    assert client.get('/api/runs/not-an-id/results').status_code==404


@pytest.mark.integration
def test_actual_baseline_native_files_and_conservation():
    root=Path('cases/baseline')
    if not (root/'results.json').exists(): pytest.skip('Run scripts/run_case.py first; no native results present')
    r=export(root)
    assert r['solver'].startswith('OpenFOAM')
    assert len(r['data'])==r['report']['cells']>10000
    assert all(r['report']['checks'].values()), r['report']['checks']
    assert len(r['provenance'])==8
    assert r['report']['ranges']['temperature']['max']-r['report']['ranges']['temperature']['min']>2
    flows={p['patch']:p['outwardLps'] for p in r['report']['patches']}
    assert flows['supply1']+flows['supply2']==pytest.approx(-290,abs=.001)
    assert flows['extract1']+flows['extract2']==pytest.approx(560,abs=.001)
    assert flows['transfer1']+flows['transfer2']==pytest.approx(-270,abs=.001)
    # Moisture generation must affect the local scalar, not only a bulk average.
    a=np.array(r['data'])
    assert np.ptp(a[:,5])>.1


def test_transfer_profiles_match_hydrostatic_adjacent_air(tmp_path):
    from backend.prepare_pressure import prepare
    mesh=tmp_path/'constant/polyMesh';mesh.mkdir(parents=True)
    (tmp_path/'0').mkdir()
    (mesh/'points').write_text('FoamFile {}\n8 ((0 0 0)(0 1 0)(0 1 1)(0 0 1)(0 0 1)(0 1 1)(0 1 2)(0 0 2))')
    (mesh/'faces').write_text('FoamFile {}\n2 (4(0 1 2 3) 4(4 5 6 7))')
    (mesh/'boundary').write_text('FoamFile {}\n2 ( transfer1 {type patch; nFaces 1; startFace 0;} transfer2 {type patch; nFaces 1; startFace 1;} )')
    (tmp_path/'0/p_rgh').write_text('boundaryField { transfer1 {type prghTotalPressure; rho rhok; p0 uniform 0; value uniform 0;} transfer2 {type prghTotalPressure; rho rhok; p0 uniform 0; value uniform 0;} }')
    prepare(tmp_path)
    prepare(tmp_path)  # preparation remains repeatable after the first mesh pass
    text=(tmp_path/'0/p_rgh').read_text()
    assert text.count('p0 nonuniform List<scalar> 1')==2
    assert '-4.905' in text and '-14.715' in text
    # External static pressure is gh; the native prghPressure BC subtracts rhok*gh.
    # At any outgoing density the resulting gauge relative to adjacent air is zero.
    for density in [1.,1.02,.98]:
        gh=-9.81*1.5
        prgh=gh-density*gh
        assert prgh+(density-1)*gh==pytest.approx(0,abs=1e-12)


def test_progress_reports_iteration_not_execution_time(tmp_path,monkeypatch):
    import importlib
    module=importlib.import_module('backend.app')
    monkeypatch.setattr(module,'RUNS',tmp_path)
    id='b'*32;p=tmp_path/id;p.mkdir()
    (p/'scenario.json').write_text(Scenario(iterations=1000).model_dump_json())
    (p/'log.solver').write_text('Time = 120\nSolving for T\nExecutionTime = 12.75 s  ClockTime = 13 s\n')
    data=TestClient(app).get('/api/runs/'+id).json()
    assert data['iteration']==120 and data['total']==1000


def test_annotated_mapping_is_applied_and_unknown_hoods_are_not_invented(tmp_path):
    import xml.etree.ElementTree as ET
    client=TestClient(app)
    review=client.get('/api/layout').json()
    assert review['geometryApplied'] is True
    assert review['activeGeometryId']=='annotated-v2'
    assert 'KPAU' in next(x['description'] for x in review['confirmed'] if x['id']=='S1 / S2')
    response=client.get('/api/layout/diagram')
    assert response.status_code==200
    assert ET.fromstring(response.content).tag.endswith('svg')
    generate(tmp_path,Scenario())
    geometry=json.loads((tmp_path/'geometry.json').read_text())
    assert geometry['layoutId']=='annotated-v2'
    assert geometry['dimensions'][0]*geometry['dimensions'][1]==pytest.approx(40.46)
    assert geometry['patches']['extract1'][0]=='ceiling'
    assert geometry['patches']['transfer1'][0]=='north'
    assert not any(name.startswith('hood') for name in geometry['patches'])
    assert len(geometry['fcuSupplyMarkers'])==4
    assert len(geometry['fcuReturnMarkers'])==2
    assert (tmp_path/'0/U').read_text().count('volumetricFlowRate constant -0.28;')==2
    with pytest.raises(ValidationError,match='Hood/cooking-station positions'):
        Scenario(hoods=[True]*5)
    # The earlier complete assumed-hood scenario is still supported explicitly.
    assert Scenario(layout_id='provisional-v1',hoods=[True]*5).hoods==[True]*5


@pytest.mark.integration
def test_actual_annotated_case_native_fields_and_sorting():
    root=Path('runs/layout-baseline-v2')
    if not (root/'results.json').exists(): pytest.skip('Run the annotated baseline first')
    r=export(root)
    assert r['geometry']['layoutId']=='annotated-v2'
    assert all(r['report']['checks'].values()),r['report']['checks']
    a=np.array(r['data']);nx,ny,nz=r['geometry']['cells']
    assert len(a)==nx*ny*nz
    # Viewer interpolation requires X fastest, then Y, then Z on the NEW aspect ratio.
    assert np.all(np.diff(a[:nx,0])>0)
    assert a[nx,1]>a[0,1]
    assert a[nx*ny,2]>a[0,2]
    flow={p['patch']:p['outwardLps'] for p in r['report']['patches']}
    assert flow['supply1']+flow['supply2']==pytest.approx(-290,abs=.001)
    assert flow['extract1']+flow['extract2']==pytest.approx(560,abs=.001)
    assert flow['transfer1']+flow['transfer2']==pytest.approx(-270,abs=.001)


def test_annotated_fcu_outlets_share_unit_cooling_without_adding_air(tmp_path):
    import re
    from backend.model import RHO,CP
    generate(tmp_path,Scenario(fcus=[True,True]))
    options=(tmp_path/'constant/fvOptions').read_text()
    coefficients=[float(sp) for su,sp in re.findall(r'\bT\s+\(([-+\deE.]+)\s+([-+\deE.]+)\)',options)]
    assert -sum(coefficients)*RHO*CP==pytest.approx(2*2500/10)
    assert options.count('Cooling {')==4
    # FCU actuators recirculate; only KPAU supplies and EAF exhausts prescribe air.
    assert (tmp_path/'0/U').read_text().count('volumetricFlowRate constant')==4
