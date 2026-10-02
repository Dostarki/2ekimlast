import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

const cache = new Map();
const steel = new THREE.MeshStandardMaterial({ color: '#1c2226', roughness: .51, metalness: .45 });
const edge = new THREE.MeshStandardMaterial({ color: '#525b63', roughness: .38, metalness: .68 });
const polymer = new THREE.MeshStandardMaterial({ color: '#101518', roughness: .84, metalness: .025 });
const recess = new THREE.MeshStandardMaterial({ color: '#111619', roughness: .82, metalness: .15 });
const olive = new THREE.MeshStandardMaterial({color:'#505a37',roughness:.58,metalness:.3});
const brass = new THREE.MeshStandardMaterial({color:'#a27835',roughness:.4,metalness:.7});
const molten = new THREE.MeshStandardMaterial({color:'#ef581c',emissive:'#ec3704',emissiveIntensity:1.5,roughness:.3});
let textured = false;
function finishMaterials() {
  if (textured) return; textured = true;
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 256;
  const context = canvas.getContext('2d'), pixels = context.createImageData(256,256);
  for (let i=0;i<pixels.data.length;i+=4) { const v=105+Math.random()*72; pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=v; pixels.data[i+3]=255; }
  context.putImageData(pixels,0,0); context.strokeStyle='rgba(185,190,195,.22)';
  for (let i=0;i<24;i++) { const x=Math.random()*256,y=Math.random()*256; context.beginPath();context.moveTo(x,y);context.lineTo(x+Math.random()*13,y+.7);context.stroke(); }
  const texture=new THREE.CanvasTexture(canvas); texture.wrapS=texture.wrapT=THREE.RepeatWrapping; texture.repeat.set(3,3);
  for (const mat of [steel,polymer]) { mat.bumpMap=texture; mat.bumpScale=.002; mat.needsUpdate=true; }
}

function extrude(parent, points, depth, mat = steel, bevel = .007) {
  const shape = points instanceof THREE.Shape ? points : new THREE.Shape(points.map(([x, y]) => new THREE.Vector2(x, y)));
  const geo = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: bevel > 0, bevelSegments: 2, steps: 1, bevelSize: bevel, bevelThickness: bevel, curveSegments: 18 });
  geo.translate(0, 0, -depth/2); const mesh = new THREE.Mesh(geo, mat); parent.add(mesh); return mesh;
}
function part(parent, x, y, z, w, h, d, mat = steel) {
  const p = extrude(parent, [[-w/2,-h/2], [w/2,-h/2], [w/2,h/2], [-w/2,h/2]], d, mat, Math.min(.006, w/8, h/8));
  p.position.set(x, y, z); return p;
}
function barrel(parent, x, y, radius, length, mat = steel, z = 0) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, length, 24), mat); m.rotation.z = Math.PI/2; m.position.set(x, y, z); parent.add(m); return m;
}
function wire(parent, points, radius, mat = steel) {
  const curve = new THREE.CatmullRomCurve3(points.map(p => new THREE.Vector3(...p)));
  const m = new THREE.Mesh(new THREE.TubeGeometry(curve, 20, radius, 6, false), mat); parent.add(m); return m;
}
function receiver(g, shotgun) {
  extrude(g, [[-.42,-.115], [.29,-.115], [.35,-.03], [.33,.115], [-.37,.115], [-.43,.07]], shotgun ? .21 : .145);
  extrude(g, [[-.405,.10], [.28,.10], [.26,.155], [-.34,.165], [-.4,.14]], .155, steel);
  for (const side of [-1, 1]) {
    const z = side*.080;
    part(g, -.01, .06, z, .52, .012, .004, edge);
    part(g, -.20, -.05, z, .09, .025, .004, recess);
    part(g, .14, -.024, z, .035, .04, .004, recess);
    const selector = part(g, -.095, .008, z+side*.007, .34, .026, .009, steel); selector.rotation.z = .11;
    for (const [x, y] of [[-.36,.026],[-.32,-.069],[.245,.047],[.21,-.071],[-.07,-.048]]) {
      const rivet = new THREE.Mesh(new THREE.SphereGeometry(.012, 10, 6), edge); rivet.scale.set(1, 1, .35); rivet.position.set(x, y, z+side*.009); g.add(rivet);
    }
    part(g, .1, .09, z+side*.025, .06, .026, .045, steel);
    part(g, .075, .058, z+side*.05, .045, .025, .013, edge);
  }
}
function stock(g, tactical, shotgun) {
  const shape = new THREE.Shape();
  shape.moveTo(-.43,.082); shape.lineTo(-.66,.035); shape.lineTo(-1.13,.048); shape.lineTo(-1.16,-.22); shape.lineTo(-1.075,-.225); shape.lineTo(-.62,-.09); shape.lineTo(-.43,-.075); shape.closePath();
  if (tactical && !shotgun) {
    const hole = new THREE.Path(); hole.moveTo(-1.055,-.16); hole.lineTo(-.71,-.055); hole.lineTo(-1.055,-.028); hole.closePath(); shape.holes.push(hole);
  }
  extrude(g, shape, .125, polymer, .012);
  part(g, -1.153, -.086, 0, .038, .293, .154, recess);
  part(g, -.445, -.002, 0, .055, .19, .172, steel);
  if (!tactical || shotgun) for (const side of [-1, 1]) {
    const inset = extrude(g, [[-1.055,-.144],[-.70,-.052],[-1.057,-.03]], .005, recess, .004); inset.position.z = side*.07;
  }
  for (let y = -.19; y < .04; y += .027) part(g, -1.177, y, 0, .004, .007, .13, polymer);
}
function magazine(g, type) {
  if (type === 'shotgun') {
    const drum = new THREE.Mesh(new THREE.CylinderGeometry(.215, .215, .21, 36), polymer); drum.rotation.x = Math.PI/2; drum.position.set(.08, -.32, 0); g.add(drum);
    for (const side of [-1, 1]) {
      const face = new THREE.Mesh(new THREE.CylinderGeometry(.19, .19, .012, 32), steel); face.rotation.x = Math.PI/2; face.position.set(.08, -.32, side*.116); g.add(face);
      const hub = new THREE.Mesh(new THREE.CylinderGeometry(.065, .065, .018, 24), recess); hub.rotation.x = Math.PI/2; hub.position.set(.08, -.32, side*.13); g.add(hub);
    }
    part(g, .06, -.15, 0, .15, .12, .14, steel); return;
  }
  const curve = type === 'ak47' ? .18 : type === 'ak107' ? .1 : .07;
  const s = new THREE.Shape(); s.moveTo(-.014,-.108); s.lineTo(.16,-.108);
  s.bezierCurveTo(.16,-.32,.2+curve*.45,-.5,.22+curve,-.61);
  s.lineTo(.075+curve,-.71); s.bezierCurveTo(-.012+curve*.4,-.48,-.025,-.29,-.014,-.108);
  const magazineMaterial = type === 'ak47' ? steel : polymer;
  extrude(g, s, .115, magazineMaterial, .01);
  for (const side of [-1,1]) {
    for (let i = 0; i < 3; i++) {
      wire(g, [[.01+i*.049,-.16,side*.063], [.013+i*.049+curve*.11,-.33,side*.067], [.062+i*.049+curve*.52,-.50,side*.067], [.09+i*.049+curve*.91,-.605,side*.064]], .006, type === 'ak47' ? edge : steel);
    }
  }
  const base = part(g, .147+curve, -.66, 0, .185, .027, .135, steel); base.rotation.z = .58;
}
function gripAndTrigger(g) {
  extrude(g, [[-.30,-.12],[-.18,-.14],[-.275,-.46],[-.34,-.47],[-.42,-.42]], .125, polymer, .013);
  for (const side of [-1,1]) for (let i = 0; i < 7; i++) {
    const rib = part(g, -.291-i*.012, -.22-i*.028, side*.069, .093, .009, .006, recess); rib.rotation.z = -.28;
  }
  for (const z of [-.038,.038]) wire(g, [[-.265,-.119,z],[-.245,-.256,z],[-.073,-.265,z],[-.037,-.185,z],[-.037,-.12,z]], .010, steel);
  wire(g, [[-.144,-.117,0],[-.145,-.18,0],[-.167,-.222,0]], .012, edge);
}
function front(g, type) {
  const short = type === 'shotgun', end = type === 'ak107' ? 1.18 : short ? .94 : 1.10;
  barrel(g, .61, -.006, short ? .046 : .026, short ? .63 : 1.1);
  barrel(g, .55, .106, .020, .63);
  extrude(g, [[.30,-.085],[.65,-.07],[.69,.077],[.34,.079]], short ? .21 : .17, polymer, .014);
  extrude(g, [[.31,.095],[.63,.087],[.65,.146],[.35,.152]], .145, polymer, .008);
  for (const side of [-1, 1]) {
    part(g, .48, -.024, side*.096, .26, .013, .009, steel);
    for (let i = 0; i < 5; i++) part(g, .36+i*.054, .032, side*.095, .022, .025, .008, recess);
  }
  part(g, .69, .045, 0, .037, .18, .103, steel);
  part(g, .96, .069, 0, .039, .184, .068, steel);
  part(g, .957, .173, 0, .039, .022, .096, steel);
  part(g, .957, .198, -.043, .038, .065, .013, steel); part(g, .957, .198, .043, .038, .065, .013, steel);
  part(g, .957, .20, 0, .009, .045, .009, edge);
  barrel(g, end, -.006, short ? .062 : .039, .14, steel);
  const bore = new THREE.Mesh(new THREE.CircleGeometry(short ? .037 : .024, 24), recess); bore.rotation.y = Math.PI/2; bore.position.set(end+.071, -.006, 0); g.add(bore);
  for (const side of [-1,1]) for (let i = 0; i < 2; i++) part(g, end-.03+i*.04, .004, side*.037, .018, .039, .006, recess);
  part(g, -.275, .195, 0, .046, .049, .09, steel);
  if (type === 'ak107') barrel(g, .58, .182, .019, .60, steel);
  if (type === 'ak117') for (let i = 0; i < 10; i++) part(g, -.30+i*.058, .18, 0, .024, .024, .13, steel);
  if (short) part(g, .12, .19, 0, .76, .09, .15, polymer);
}
function consolidate(group) {
  group.updateMatrixWorld(true); const buckets = new Map();
  group.traverse(m => {
    if (!m.isMesh) return;
    if (!buckets.has(m.material.uuid)) buckets.set(m.material.uuid, { material: m.material, geos: [] });
    const geometry = m.geometry.index ? m.geometry.toNonIndexed() : m.geometry.clone();
    buckets.get(m.material.uuid).geos.push(geometry.applyMatrix4(m.matrixWorld)); m.geometry.dispose();
  });
  const merged = new THREE.Group();
  buckets.forEach(({ material, geos }) => {
    const geometry = mergeGeometries(geos); geos.forEach(g => g.dispose());
    const mesh = new THREE.Mesh(geometry, material); mesh.castShadow = true; mesh.receiveShadow = true; merged.add(mesh);
  });
  return merged;
}

function heavyWeapon(g,type,ammo){
  if(type==='rocket'){
    barrel(g,-.08,.04,.125,1.96,olive);barrel(g,-1.08,.04,.185,.15,steel);
    barrel(g,-.53,.04,.146,.49,polymer);barrel(g,.75,.04,.13,.27,olive);
    const warhead=new THREE.Mesh(new THREE.ConeGeometry(.215,.46,24),olive);warhead.rotation.z=-Math.PI/2;warhead.position.set(1.04,.04,0);ammo.add(warhead);
    barrel(ammo,.795,.04,.207,.1,olive);part(g,-.08,-.20,0,.13,.32,.14,polymer);part(g,.40,-.17,0,.1,.28,.11,polymer);
    part(g,.08,.24,0,.15,.27,.09,steel);part(g,.08,.39,0,.23,.06,.17,steel);part(g,-.33,.20,0,.035,.12,.07,steel);
  }else if(type==='minigun'){
    barrel(g,-.39,0,.245,.7,steel);barrel(g,-.78,0,.26,.09,polymer);
    for(let i=0;i<6;i++){const a=i*Math.PI/3;barrel(g,.48,Math.cos(a)*.16,.035,1.46,steel,Math.sin(a)*.16);barrel(g,1.12,Math.cos(a)*.16,.044,.1,edge,Math.sin(a)*.16);}
    for(const x of [.02,.74,1.02])barrel(g,x,0,.214,.07,steel);
    part(g,-.26,.35,0,.65,.075,.095,polymer);part(g,-.52,.22,0,.06,.26,.095,steel);part(g,.04,.22,0,.06,.26,.095,steel);
    part(g,-.49,-.32,0,.12,.35,.14,polymer);part(ammo,-.32,-.36,0,.5,.28,.31,olive);
    for(let i=0;i<9;i++)barrel(ammo,-.58+i*.055,-.23,.018,.16,brass,.21);
  }else if(type==='flamethrower'){
    barrel(ammo,-.33,.01,.17,.88,olive);barrel(g,.50,.02,.06,1.0,steel);barrel(g,.98,.02,.105,.18,steel);
    barrel(g,.48,.13,.022,.65,brass);part(g,-.26,-.23,0,.15,.34,.14,polymer);part(g,.28,-.2,0,.10,.30,.12,polymer);
    for(const side of [-1,1]){barrel(g,-.68,.025,.068,.22,brass,side*.15);wire(g,[[-.79,-.02,side*.1],[-.91,-.35,side*.14],[-.45,-.46,side*.18],[-.30,-.12,side*.12]],.024,recess);}
    const valve=new THREE.Mesh(new THREE.TorusGeometry(.12,.017,6,16),brass);valve.position.set(-.47,.22,0);valve.rotation.x=Math.PI/2;g.add(valve);
    for(let i=0;i<4;i++)barrel(g,.79+i*.056,.02,.083,.016,brass);
  }else if(type==='lava'){
    part(g,-.14,0,0,1.0,.35,.31,steel);barrel(g,.53,0,.16,.54,polymer);barrel(g,.86,0,.19,.15,steel);barrel(g,.947,0,.12,.02,molten);
    part(g,-.37,-.30,0,.17,.34,.16,polymer);part(g,-.75,-.015,0,.27,.26,.22,olive);
    for(const side of [-1,1]){barrel(ammo,-.09,0,.062,.65,molten,side*.19);for(let i=0;i<5;i++)part(ammo,-.36+i*.145,0,side*.215,.04,.27,.04,steel);}
    part(g,.08,.25,0,.28,.14,.16,steel);part(g,.08,.30,.087,.20,.033,.015,molten);
  }
}
function pistol(g,ammo){
  part(g,.04,.055,0,.69,.14,.13,steel);part(g,.02,-.025,0,.64,.065,.13,polymer);
  const grip=part(g,-.18,-.23,0,.18,.36,.125,polymer);grip.rotation.z=-.18;
  part(ammo,-.15,-.41,0,.20,.035,.145,steel);
  barrel(g,.32,.055,.028,.13,steel);
  const bore=new THREE.Mesh(new THREE.CircleGeometry(.018,16),recess);bore.rotation.y=Math.PI/2;bore.position.set(.39,.055,0);g.add(bore);
  part(g,.27,.147,0,.035,.03,.023,edge);part(g,-.25,.14,0,.045,.025,.12,edge);
  for(const side of [-1,1])for(let i=0;i<6;i++)part(g,-.26+i*.023,.058,side*.071,.01,.10,.005,recess);
  for(const z of [-.055,.055])wire(g,[[-.1,-.05,z],[-.1,-.2,z],[.12,-.2,z],[.14,-.05,z]],.012,polymer);
  wire(g,[[0,-.05,0],[-.01,-.14,0],[.015,-.17,0]],.012,steel);
  for(let i=0;i<5;i++)part(g,-.155,-.15-i*.045,.067,.10,.01,.007,recess);
}
function m4(g,ammo){
  receiver(g,false);gripAndTrigger(g);magazine(ammo,'ak117');
  barrel(g,-.74,.02,.047,.66,steel);
  extrude(g,[[-1.18,.10],[-.73,.07],[-.63,-.03],[-1.13,-.20]],.14,polymer,.013);part(g,-1.18,-.065,0,.042,.33,.17,recess);
  part(g,.51,.015,0,.49,.19,.19,polymer);barrel(g,.94,.015,.025,.47,steel);barrel(g,1.15,.015,.038,.12,steel);
  for(let i=0;i<10;i++){part(g,-.32+i*.096,.175,0,.04,.035,.18,steel);if(i>4)for(const side of [-1,1])part(g,.28+(i-5)*.10,.03,side*.104,.056,.045,.011,recess);}
  part(g,-.13,.255,0,.20,.16,.14,steel);part(g,-.13,.27,.084,.11,.066,.012,edge);
  part(g,.89,.16,0,.032,.19,.056,steel);
}

// Reference-inspired beveled profiles, metal hardware and smooth magazines;
// these are real geometry shared by the loadout renderer and in-world actors.
export function createWeapon(type = 'ak47') {
  finishMaterials();
  if (!cache.has(type)) {
    const g = new THREE.Group(), ammo = new THREE.Group();
    if(['rocket','minigun','flamethrower','lava'].includes(type))heavyWeapon(g,type,ammo);
    else if(type==='m4')m4(g,ammo);
    else if(type==='glock18')pistol(g,ammo);
    else { receiver(g, type === 'shotgun'); stock(g, type === 'ak117', type === 'shotgun'); magazine(ammo, type); gripAndTrigger(g); front(g, type); }
    const merged = consolidate(g); merged.rotation.y = -Math.PI/2;
    const result = new THREE.Group(); result.add(merged); result.userData.muzzle = new THREE.Vector3(0, 0, type==='glock18'?.43:1.23);
    const reloadPart = consolidate(ammo); reloadPart.rotation.y = -Math.PI/2; reloadPart.name = 'reload-part'; result.add(reloadPart);
    cache.set(type, result);
  }
  return cache.get(type).clone(true);
}