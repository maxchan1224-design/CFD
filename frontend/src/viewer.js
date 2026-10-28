import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const V=(x,y,z)=>new THREE.Vector3(x,z,-y);
export const fields={temperature:{label:'Temperature',unit:'°C',col:3},rh:{label:'Relative humidity',unit:'%',col:4},humidity:{label:'Humidity ratio',unit:'g/kg',col:5},velocity:{label:'Air velocity',unit:'m/s'},pressure:{label:'Room pressure',unit:'Pa',col:9}};
const palette=['#486abb','#439ec6','#59c7c0','#a7d6a0','#e7d97c','#efac62','#dd7052'];
export function color(t){let k=Math.max(0,Math.min(.99999,t))*(palette.length-1);return new THREE.Color(palette[Math.floor(k)]).lerp(new THREE.Color(palette[Math.min(palette.length-1,Math.floor(k)+1)]),k%1);}
export class Viewer {
 constructor(el,onHover){
  this.el=el;this.onHover=onHover;this.field='temperature';this.axis='z';this.position=1.1;this.mode='contours';
  this.scene=new THREE.Scene();this.scene.background=new THREE.Color('#e9eee9');
  this.camera=new THREE.PerspectiveCamera(36,1,.01,100);this.camera.position.set(10,7,8);
  this.renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));this.renderer.shadowMap.enabled=true;this.renderer.toneMapping=THREE.ACESFilmicToneMapping;this.renderer.toneMappingExposure=1.0;this.renderer.domElement.setAttribute('aria-label','3D room and calculated CFD fields. Drag to orbit; scroll to zoom.');el.appendChild(this.renderer.domElement);
  this.controls=new OrbitControls(this.camera,this.renderer.domElement);this.controls.target.set(3.5,1,-2.89);this.controls.enableDamping=true;this.controls.maxPolarAngle=Math.PI*.49;this.controls.minDistance=4;this.controls.maxDistance=28;
  this.scene.add(new THREE.HemisphereLight(0xffffff,0x879a8b,2.5));let sun=new THREE.DirectionalLight(0xffffff,3);sun.position.set(4,12,7);this.scene.add(sun);
  let grid=new THREE.GridHelper(30,60,0xc7d3cb,0xdbe3dc);grid.position.set(3.5,-.06,-2.89);this.scene.add(grid);
  this.geometryGroup=new THREE.Group();this.scene.add(this.geometryGroup);this.room();this.fieldGroup=new THREE.Group();this.scene.add(this.fieldGroup);
  let observer=new ResizeObserver(()=>{let {width,height}=el.getBoundingClientRect();this.camera.aspect=width/height;this.camera.updateProjectionMatrix();this.renderer.setSize(width,height);});observer.observe(el);
  this.raycaster=new THREE.Raycaster();this.pointer=new THREE.Vector2();
  this.renderer.domElement.addEventListener('pointermove',e=>{if(!this.plane||!this.result)return;let rect=el.getBoundingClientRect();this.pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);this.raycaster.setFromCamera(this.pointer,this.camera);let h=this.raycaster.intersectObject(this.plane)[0];if(h){let row=this.visibleRows[Math.floor(h.faceIndex/2)];if(row)this.onHover(row);}else this.onHover(null);});
  const animate=()=>{requestAnimationFrame(animate);this.controls.update();this.renderer.render(this.scene,this.camera);};animate();
 }
 box(x,y,z,w,d,h,c,opacity=1){let m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),new THREE.MeshStandardMaterial({color:c,transparent:opacity<1,opacity,roughness:.8}));m.position.copy(V(x,y,z));this.geometryGroup.add(m);return m;}
 legacyRoom(){
  this.box(3.5,2.89,-.09,7.18,5.96,.16,'#d2d9cf');
  // Simplified outlines mark the model envelope, not CFD obstacles.
  let edges=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(7,2.9,5.78)),new THREE.LineBasicMaterial({color:0x84978c,transparent:true,opacity:.6}));edges.position.copy(V(3.5,2.89,1.45));this.geometryGroup.add(edges);
  this.box(3.5,5.8,1.45,7,.045,2.9,'#e0e4da',.3);
  [1.4,5.6].forEach(x=>{this.box(x,1.2,2.9,.62,.62,.07,'#287c6c');for(let i=0;i<4;i++)this.box(x-.2+i*.13,1.2,2.85,.018,.52,.012,'#a6c3b8');});
  [1.5,4.3].forEach(y=>this.box(7,y,2.5,.06,.62,.62,'#b56e49'));
  [.8,2.1,3.4,4.7,6].forEach(x=>{this.box(x,5,2.86,.78,.62,.09,'#9aa8a1');});
  this.box(0,2.89,1.05,.03,.9,2.1,'#6eaba2',.18);
  [1.5,5.5].forEach(x=>this.box(x,.5,2.3,1,.6,.6,'#a0b2b2',.22));
 }
 room(g){
  for(const obj of [...this.geometryGroup.children]){obj.traverse(o=>{o.geometry?.dispose();if(o.material)[].concat(o.material).forEach(m=>m.dispose());});this.geometryGroup.remove(obj);}
  this.dimensions=g?.dimensions||[7,5.78,2.9];
  if(!g||g.layoutId!=='annotated-v2'){this.legacyRoom();return;}
  const [lx,ly,lz]=g.dimensions;
  this.box(lx/2,ly/2,-.09,lx+.18,ly+.18,.16,'#d2d9cf');
  const edges=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(lx,lz,ly)),new THREE.LineBasicMaterial({color:0x84978c,transparent:true,opacity:.6}));edges.position.copy(V(lx/2,ly/2,lz/2));this.geometryGroup.add(edges);
  for(const [name,[parent,b]] of Object.entries(g.patches)){
   const c=[(b[0]+b[3])/2,(b[1]+b[4])/2,(b[2]+b[5])/2];let size=[b[3]-b[0],b[4]-b[1],b[5]-b[2]];
   if(parent==='ceiling'){c[2]=lz;size[2]=.045;}else if(parent==='north'){c[1]=ly;size[1]=.035;}
   this.box(...c,...size,name.startsWith('supply')?'#287c6c':name.startsWith('extract')?'#b56e49':'#6eaba2',name.startsWith('transfer')?.45:1);
  }
  for(const p of g.fcuSupplyMarkers||[])this.box(...p,.6,.6,.045,'#557f97',.75);
  for(const p of g.fcuReturnMarkers||[])this.box(...p,1.1,.35,.045,'#75898d',.65);
  for(const p of g.fcuUnitMarkers||[])this.box(...p,1.35,.55,.4,'#a0b2b2',.24);
 }
 setResult(result){this.result=result;this.room(result.geometry);this.reset();this.draw();}
 reset(){const [x,y]=this.dimensions||[7,5.78];this.camera.position.set(10*x/7,7,8*y/5.78);this.controls.target.set(x/2,1,-y/2);}
 clear(){for(let obj of [...this.fieldGroup.children]){obj.traverse(o=>{o.geometry?.dispose();if(o.material){[].concat(o.material).forEach(m=>m.dispose());}});this.fieldGroup.remove(obj);}this.plane=null;}
 value(row){return this.field==='velocity'?Math.hypot(row[6],row[7],row[8]):row[fields[this.field].col];}
 draw(){
  this.clear();if(!this.result)return;
  let r=this.result,{cells,dimensions}=r.geometry;let step=dimensions.map((v,i)=>v/cells[i]);let ai={x:0,y:1,z:2}[this.axis];let idx=Math.max(0,Math.min(cells[ai]-1,Math.floor(this.position/step[ai])));
  this.actualPosition=(idx+.5)*step[ai];let rows=r.data.filter(row=>Math.round(row[ai]/step[ai]-.5)===idx);this.visibleRows=rows;
  this.range=[r.report.ranges[this.field].min,r.report.ranges[this.field].max];
  if(this.mode==='contours'||this.mode==='vectors'){
   let vertices=[],colors=[];let [a,b]=[0,1,2].filter(i=>i!==ai);
   rows.forEach(row=>{let p=row.slice(0,3);let corners=[[-1,-1],[1,-1],[1,1],[-1,1]].map(([u,v])=>{let q=[...p];q[a]+=u*step[a]/2;q[b]+=v*step[b]/2;return V(...q);});let c=color((this.value(row)-this.range[0])/(this.range[1]-this.range[0]||1));[0,1,2,0,2,3].forEach(i=>{vertices.push(...corners[i].toArray());colors.push(c.r,c.g,c.b);});});
   let g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));g.computeVertexNormals();
   this.plane=new THREE.Mesh(g,new THREE.MeshBasicMaterial({vertexColors:true,side:THREE.DoubleSide,transparent:true,opacity:this.mode==='vectors'?.48:.9,depthWrite:false}));this.fieldGroup.add(this.plane);
  }
  if(this.mode==='vectors') rows.filter((r,i)=>i%7===0).forEach(row=>{let v=V(row[6],row[7],row[8]);let speed=v.length();if(speed<.005)return;let arrow=new THREE.ArrowHelper(v.normalize(),V(...row.slice(0,3)),Math.min(.48,.10+speed*.2),0x163f39,.075,.035);this.fieldGroup.add(arrow);});
  if(this.mode==='streamlines')this.streamlines();
 }
 sample(p){
  let {cells,dimensions}=this.result.geometry;let v=p.map((x,i)=>x/(dimensions[i]/cells[i])-.5);let b=v.map(Math.floor);let f=v.map((x,i)=>x-b[i]);if(p.some((x,i)=>x<0||x>dimensions[i]))return null;
  let out=[0,0,0];for(let k=0;k<2;k++)for(let j=0;j<2;j++)for(let i=0;i<2;i++){let idx=[i,j,k].map((q,d)=>Math.max(0,Math.min(cells[d]-1,b[d]+q)));let row=this.result.data[idx[0]+cells[0]*(idx[1]+cells[1]*idx[2])];let weight=(i?f[0]:1-f[0])*(j?f[1]:1-f[1])*(k?f[2]:1-f[2]);for(let d=0;d<3;d++)out[d]+=row[d+6]*weight;}return out;
 }
 streamlines(){
  let seeds=[];
  for(const [name,[parent,b]] of Object.entries(this.result.geometry.patches)){
   if(!name.startsWith('supply')&&!name.startsWith('transfer'))continue;
   const center=[(b[0]+b[3])/2,(b[1]+b[4])/2,(b[2]+b[5])/2];
   for(const a of [-1,0,1])for(const d of [-1,0,1]){
    let p=[...center];
    if(parent==='ceiling'){p[0]+=a*Math.min(.15,(b[3]-b[0])*.3);p[1]+=d*Math.min(.15,(b[4]-b[1])*.3);p[2]=this.result.geometry.dimensions[2]-.08;}
    else if(parent==='north'){p[0]+=a*Math.min(.15,(b[3]-b[0])*.3);p[1]=this.result.geometry.dimensions[1]-.08;p[2]+=d*(b[5]-b[2])*.25;}
    else if(parent==='west'){p[0]=.08;p[1]+=a*Math.min(.2,(b[4]-b[1])*.25);p[2]+=d*(b[5]-b[2])*.25;}
    seeds.push(p);
   }
  }
  for(let seed of seeds){let p=[...seed],vertices=[],colors=[];for(let i=0;i<500;i++){let u=this.sample(p);if(!u)break;let speed=Math.hypot(...u);if(speed<.002)break;let dt=.06/speed;let mid=p.map((x,d)=>x+u[d]*dt/2);let um=this.sample(mid);if(!um)break;let next=p.map((x,d)=>x+um[d]*dt);if(!this.sample(next))break;let c=color(speed/Math.max(.01,this.result.report.ranges.velocity.max));vertices.push(...V(...p).toArray(),...V(...next).toArray());colors.push(c.r,c.g,c.b,c.r,c.g,c.b);p=next;}
   let g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));g.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));this.fieldGroup.add(new THREE.LineSegments(g,new THREE.LineBasicMaterial({vertexColors:true,transparent:true,opacity:.85})));
  }
 }
}
