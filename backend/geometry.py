"""Versioned physical geometry; prior solved cases keep their original coordinates."""

def geometry_for(layout_id, mesh):
    if layout_id=='provisional-v1':
        lx,ly,lz=7.,5.78,2.9
        n=(35,29,15) if mesh=='coarse' else (56,46,24)
        patches={}
        for i,x in enumerate([1.4,5.6]): patches[f'supply{i+1}']=('ceiling',(x-.31,.89,2.89,x+.31,1.51,2.91))
        for i,y in enumerate([1.5,4.3]): patches[f'extract{i+1}']=('east',(6.99,y-.31,2.19,7.01,y+.31,2.81))
        hood_centres=[(.8,5.),(2.1,5.),(3.4,5.),(4.7,5.),(6.,5.)]
        for i,(x,y) in enumerate(hood_centres): patches[f'hood{i+1}']=('ceiling',(x-.39,y-.31,2.89,x+.39,y+.31,2.91))
        patches['transfer1']=('west',(-.01,2.44,0,.01,3.34,1.055))
        patches['transfer2']=('west',(-.01,2.44,1.055,.01,3.34,2.11))
        zones={'people':(1.,1.8,.1,6.,4.1,1.9),'fcu1':(1.,.2,2.,2.,.8,2.6),'fcu2':(5.,.2,2.,6.,.8,2.6)}
        for i,(x,y) in enumerate(hood_centres): zones[f'cook{i+1}']=(x-.39,y-.31,.6,x+.39,y+.31,1.2)
        return dict(layoutId=layout_id,dimensions=[lx,ly,lz],cells=list(n),patches=patches,zones=zones,hoodCentres=hood_centres,fcuZones=[['fcu1'],['fcu2']],fcuDirection=[0,1,0],hRef=.8,transferDescription='Legacy west-wall 0.9 × 2.11 m doorway; not the annotated transfer grille.',layoutRegistration='Legacy provisional-v1 geometry, retained for historical comparison; not registered to the annotated HVAC crop.')
    if layout_id!='annotated-v2': raise ValueError('Unknown physical layout')
    # User annotation confirms identities. Scale and registration rectangle remain assumptions.
    lx,ly,lz=8.3,40.46/8.3,2.9
    n=(42,25,15) if mesh=='coarse' else (66,39,24)
    def point(px,py): return ((px-160)/795*lx,(610-py)/466*ly)
    patches={}
    for i,p in enumerate([(304,514),(887,514)]):
        x,y=point(*p);patches[f'supply{i+1}']=('ceiling',(x-.31,y-.31,2.89,x+.31,y+.31,2.91))
    for i,p in enumerate([(568,527),(750,527)]):
        x,y=point(*p);patches[f'extract{i+1}']=('ceiling',(x-.45,y-.14,2.89,x+.45,y+.14,2.91))
    # The drawing shows a pair straddling the upper wall. Represent one back-to-back
    # transfer path, not two independent kitchen openings. Size/height provisional.
    tx,_=point(584,162)
    patches['transfer1']=('north',(tx-.45,ly-.01,2.35,tx+.45,ly+.01,2.60))
    patches['transfer2']=('north',(tx-.45,ly-.01,2.60,tx+.45,ly+.01,2.85))
    zones={'people':(.15*lx,.2*ly,.1,.85*lx,.8*ly,1.9)}
    fcu_supply=[];fcu_zones=[]
    for i,px in enumerate([405,738],1):
        names=[]
        for j,py in enumerate([227,338],1):
            x,y=point(px,py);name=f'fcu{i}_{j}';names.append(name)
            zones[name]=(x-.3,y-.3,2.3,x+.3,y+.3,2.85)
            fcu_supply.append([x,y,2.9])
        fcu_zones.append(names)
    return dict(layoutId=layout_id,dimensions=[lx,ly,lz],cells=list(n),patches=patches,zones=zones,hoodCentres=[],fcuZones=fcu_zones,fcuDirection=[0,0,-1],hRef=2.6,
        fcuSupplyMarkers=fcu_supply,fcuReturnMarkers=[[*point(404,461),2.9],[*point(740,461),2.9]],fcuUnitMarkers=[[*point(404,406),3.15],[*point(740,406),3.15]],
        sourceReference='User-annotated HVAC crop: KPAU squares, EAF slots, FCU supplies/returns and upper transfer identified.',
        registration={'imageSizePx':[1217,720],'assumedPlanRectanglePx':[160,144,955,610],'method':'Manual relative-position registration; 8.3 m length assumed, width constrained by 40.46 m² area. Not a dimensioned CAD trace.'},
        transferDescription='Upper-wall transfer grille, assumed one back-to-back path: 0.9 m wide, z=2.35–2.85 m, split into pressure face groups. Dimensions/height and path assembly unverified.',
        layoutRegistration='Terminal identities follow the user-annotated crop. Rectangular room dimensions, grille sizes/heights, transfer-path assembly and partition/opening geometry remain provisional. Hood locations are unmarked; no hood/cooking boundary is assigned in this layout.',
        fcuDescription='Two FCUs: each UA is divided between its two annotated supply locations. Local downward momentum/cooling actuators are used; return grilles and above-ceiling housings are annotations, not resolved duct/return connections. No mass addition or dehumidification.')
