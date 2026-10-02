import * as THREE from 'three';
import { box, limb, rounded, material, mergeBody } from './characterParts';

export const ENEMY_LABELS = { normal: 'Creature', immolator: 'Immolator', hellhound: 'Hellhound', hive: 'Hive', armored: 'Armored' };
const glow = new THREE.MeshBasicMaterial({ color: '#ff963b' });
const venom = new THREE.MeshBasicMaterial({ color: '#b5d168' });
function orb(g, x, y, z, rx, ry, rz, color) {
  const mesh = new THREE.Mesh(new THREE.IcosahedronGeometry(1, 1), typeof color === 'string' ? material(color) : color);
  mesh.position.set(x,y,z); mesh.scale.set(rx,ry,rz); mesh.castShadow = true; g.add(mesh); return mesh;
}
function spike(g, x, y, z, size, color, direction = 0) {
  const mesh = new THREE.Mesh(new THREE.ConeGeometry(size*.23, size, 5), material(color));
  mesh.position.set(x,y,z); mesh.rotation.x = direction; g.add(mesh); return mesh;
}
function fireBody(g) {
  const flames = new THREE.Group(); g.add(flames);
  for (let i=0; i<12; i++) {
    const angle = i*2.4, y = .65+(i%5)*.28;
    const mesh = new THREE.Mesh(new THREE.ConeGeometry(.09, .30, 5), new THREE.MeshBasicMaterial({ color: i%3 ? '#ff7328' : '#ffcd67', transparent: true, opacity: .85, depthWrite: false }));
    mesh.position.set(Math.sin(angle)*.29, y, Math.cos(angle)*.23); mesh.userData.baseY = y; flames.add(mesh);
  }
  g.userData.flames = flames;
}
function hound(g) {
  const flesh = '#585249';
  orb(g, 0,.75,0,.30,.36,.67,flesh); orb(g,0,.85,.43,.30,.36,.30,'#3e423c');
  orb(g,0,.91,.75,.24,.25,.34,flesh); rounded(g,0,.78,1.0,.31,.18,.39,'#2b2725');
  for (const side of [-1,1]) {
    orb(g,side*.18,1.02,.91,.07,.045,.035,glow);
    spike(g,side*.18,1.21,.63,.32,'#332e2c',-.25);
    for(let i=0;i<4;i++) spike(g,side*.13,.72,.91+i*.07,.085,'#cec4a4',Math.PI);
  }
  const legs = [];
  for (const z of [-.42,.46]) for (const side of [-1,1]) {
    const leg = new THREE.Group(); leg.position.set(side*.23,.70,z); g.add(leg);
    limb(leg,0,-.22,0,.075,.46,flesh); limb(leg,0,-.48,.045,.055,.23,'#352f2c');
    rounded(leg,0,-.59,.12,.14,.1,.25,'#241f1c'); mergeBody(leg); legs.push(leg);
  }
  for (let i=0;i<5;i++) { const rib = rounded(g,0,.86,-.45+i*.18,.58,.038,.055,'#aaa18a'); rib.rotation.z = .08; }
  const tail = limb(g,0,.85,-.88,.055,.58,flesh); tail.rotation.x = -.9;
  g.userData.legs = legs; g.userData.tail = tail; tail.userData.articulated = true;
}
function biped(g, kind, variant) {
  const burning = kind === 'immolator', hive = kind === 'hive', armored = kind === 'armored';
  const flesh = burning ? '#3b3330' : hive ? '#898b69' : armored ? '#626459' : ['#90967a','#827d69','#708679','#8e846b','#77776c'][variant%5];
  const legs = [], arms = [];
  for (const side of [-1,1]) {
    const leg = new THREE.Group(); leg.position.set(side*.17,.93,0); g.add(leg);
    limb(leg,0,-.21,0,.13,.45,flesh); limb(leg,0,-.59,.025,.087,.39,flesh);
    rounded(leg,0,-.83,.11,.24,.17,.40,'#3e4238'); mergeBody(leg); legs.push(leg);
  }
  orb(g,0,1.29,-.02,armored ? .46 : hive ? .30 : .33,.49,.25,flesh);
  orb(g,0,1.58,-.03,armored ? .43 : .28,.29,.25,flesh);
  orb(g,hive ? -.18 : 0,1.97,.09,.205,.28,.23,flesh);
  rounded(g,0,1.84,.28,.23,.14,.13,'#292a23');
  for (const side of [-1,1]) {
    orb(g,side*.09+(hive ? -.12 : 0),2.01,.285,.045,.032,.024,burning ? glow : hive ? venom : '#d5c37e');
    const arm = new THREE.Group(); arm.position.set(side*(armored ? .49 : .37),1.55,.01); g.add(arm);
    limb(arm,0,-.24,0,.092,.48,flesh); limb(arm,0,-.59,.04,.064,.33,flesh);
    for(let i=0;i<3;i++) spike(arm,(i-1)*.052,-.84,.085,.23,'#b2aa89',Math.PI);
    mergeBody(arm); arms.push(arm);
  }
  if (armored) {
    for (let i=0;i<6;i++) {
      const plate = orb(g,(i%2 ? 1 : -1)*.20,1.05+Math.floor(i/2)*.24,.22,.25,.18,.15,i%2 ? '#818576' : '#a3a190');
      plate.rotation.z = i%2 ? -.3 : .3;
    }
    for(const side of [-1,1]) for(let i=0;i<3;i++) spike(g,side*(.34+i*.08),1.62+i*.10,0,.40,'#a0a390',side*.45);
  } else if (hive) {
    orb(g,.06,1.43,-.29,.37,.46,.31,'#625e38');
    for(let i=0;i<13;i++) {
      const a=i*2.4, y=1.08+(i%5)*.15;
      orb(g,Math.sin(a)*.27,y,-.35+Math.cos(a)*.18,.11,.13,.12,i%3 ? '#817a42' : venom);
    }
    const hair = limb(g,-.19,1.81,-.08,.17,.51,'#393f30'); hair.rotation.z = -.28;
    for (const side of [-1,1]) { const skirt = rounded(g,side*.15,.87,0,.28,.40,.38,'#4b5948'); skirt.rotation.z = side*.14; }
    // A visible honeycomb cavity in the chest, not a floating hive prop.
    orb(g,.11,1.44,.245,.22,.29,.045,'#292e20');
    for(let i=0;i<7;i++) orb(g,.11+Math.sin(i*2.4)*.13,1.43+Math.cos(i*2.4)*.19,.28,.044,.048,.018,venom);
  } else {
    for(let i=0;i<5;i++) {
      const rib = rounded(g,0,1.12+i*.09,.23,.43-i*.025,.035,.038,burning ? '#bf632e' : '#b4ae93'); rib.rotation.z = Math.sin(i)*.06;
    }
    for (const side of [-1,1]) orb(g,side*.25,1.50,.16,.075,.18,.095,burning ? '#cc5423' : '#685650');
    if (burning) fireBody(g);
    else { spike(g,-.20,1.73,-.17,.37,'#a5ac94',-.5); rounded(g,.14,1.27,.26,.09,.23,.02,'#584b43'); }
  }
  Object.assign(g.userData, { legs, arms });
}
export function createEnemy(kind = 'normal', variant = 0) {
  const g = new THREE.Group();
  Object.assign(g.userData, { enemy: true, zombie: true, kind, phase: variant, blend: 0 });
  if (kind === 'hellhound') hound(g); else biped(g, kind, variant);
  const shadow = new THREE.Mesh(new THREE.CircleGeometry(kind === 'hellhound' ? .85 : .65,16),new THREE.MeshBasicMaterial({color:'#10180f',transparent:true,opacity:.3,depthWrite:false}));
  shadow.rotation.x = -Math.PI/2; shadow.position.y = .02; g.add(shadow);
  mergeBody(g); return g;
}
export function animateEnemy(g, time, moving, dt, state = {}) {
  const u = g.userData, dog = u.kind === 'hellhound', fast = dog || u.kind === 'immolator' || state.runner;
  u.blend += (Number(moving)-u.blend)*(1-Math.exp(-dt*12));
  u.phase += dt*(fast && state.mode === 'attack' ? 17 : state.mode === 'attack' ? 8 : 5);
  u.legs.forEach((leg,i) => { leg.rotation.x = Math.sin(u.phase+(dog ? [0,Math.PI,.8,Math.PI+.8][i] : i*Math.PI))*(fast ? .75 : .42)*u.blend; });
  (u.arms || []).forEach((arm,i) => { arm.rotation.x = -.35-Math.sin(u.phase+i*Math.PI)*.22*u.blend-(state.attacking ? .8 : 0); arm.rotation.z = (i ? 1 : -1)*.14; });
  g.position.y = Math.abs(Math.sin(u.phase))*(dog ? .11 : .035)*u.blend;
  g.rotation.x = dog ? (state.attacking ? -.16 : 0) : u.kind === 'hive' ? .13 : .08;
  if (u.tail) u.tail.rotation.z = Math.sin(time*6)*.18;
  if (u.flames) u.flames.children.forEach((flame,i) => { flame.position.y = flame.userData.baseY+Math.sin(time*12+i)*.055; flame.scale.setScalar(.8+Math.sin(time*17+i)*.25+(state.mode === 'windup' ? .8 : 0)); });
}