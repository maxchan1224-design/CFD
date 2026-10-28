"""User-confirmed symbol identities from the annotated crop; dimensions remain assumed."""
LAYOUT_REVIEW={
 'id':'hvac-annotated-02','status':'registered_with_assumptions','source':'User-annotated HVAC crop supplied in chat','imageSizePx':[1217,720],
 'geometryApplied':True,'activeGeometryId':'annotated-v2','diagram':'/api/layout/diagram',
 'scaleStatus':'Assumed rectangular 8.30 × 4.8747 m room, area 40.46 m². Relative positions registered using assumed image rectangle (160,144)–(955,610); not a dimensioned wall trace.',
 'confirmed':[
  {'id':'F1 / F2','description':'Two FCU-8 units, each serving two upper square supply diffusers and a broad return grille beneath the unit.'},
  {'id':'S1 / S2','description':'User labels the lower-left and lower-right square grilles as KPAU. Total supply is shared between these two ceiling outlets.','centresPx':[[304,514],[887,514]]},
  {'id':'E1 / E2','description':'User labels the two narrow crossed slots below the FCUs as EAF. The kitchen exhaust remains 560 L/s TOTAL.','centresPx':[[568,527],[750,527]]},
  {'id':'D1–D4','description':'Upper four square diffusers are FCU supplies, not extra KPAU terminals.','centresPx':[[405,227],[405,338],[738,227],[738,338]]},
  {'id':'R1 / R2','description':'Broad grilles immediately below the FCU labels are the two FCU returns.','centresPx':[[404,461],[740,461]]},
  {'id':'T','description':'The upper crossed-grille pair is labelled Transfer. The model assumes one back-to-back path through the upper wall; its assembly and dimensions need verification.','centresPx':[[584,129],[584,162]]},
 ],
 'candidates':[],
 'unresolved':[
  'Five hood/cooking-station positions and canopy heights are not marked. Drawing-based runs require hoods OFF and zero cooking gains until these positions are supplied; legacy provisional-v1 retains the earlier assumed row.',
  'Room perimeter, metric dimensions, grille free areas and installation heights need confirmation. Area alone does not determine aspect ratio.',
  'Transfer is assumed to be one back-to-back upper-wall path, 0.9 m wide at z=2.35–2.85 m. Neither a west-wall doorway nor a fixed transfer flow is imposed in annotated-v2.',
  'The half-height-glass note does not establish whether an open gap exists. The model assumes an impermeable partition; height, extent and any opening remain unresolved.',
  'FCU return locations are displayed; cooling/recirculation use local actuators under the four supply diffusers, not resolved ducts or return-to-supply connections. No FCU condensation is modelled.',
  'KPAU/FCU diffuser discharge patterns are assumed downward; manufacturer four-way jet data are missing.',
  'CHWS/CHWR and CD services are not ventilation paths. Far-right 90 L/s adjacent-zone tags are excluded from kitchen exhaust.',
  '2700 CL is not substituted for the specified 2.9 m clear ceiling; the 2.9–4.8 m ceiling void remains outside the CFD domain.',
 ],
 'resultNotice':'annotated-v2 follows your corrected terminal mapping. Earlier provisional-v1 results are retained separately. Physical dimensions, transfer-path construction and unmarked hood positions remain assumptions or missing data.'
}
