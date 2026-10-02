import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { box, cylinder, material } from './models';
import { createTextures, rng } from './textures';
import {createInterior} from './interiors';
import {bakeMeshes} from './batching';

let textures, mats;
function init() {
  if (textures) return;
  textures = createTextures();
  mats = Object.fromEntries(Object.entries(textures).map(([k, map]) => [k, new THREE.MeshLambertMaterial({ map })]));
}
function roof(group, x, y, z, w, d, height, color) {
  const shape = new THREE.Shape(); shape.moveTo(-w/2, 0); shape.lineTo(0, height); shape.lineTo(w/2, 0); shape.closePath();
  const geo = new THREE.ExtrudeGeometry(shape, { depth: d, bevelEnabled: false });
  const mesh = new THREE.Mesh(geo, material(color)); mesh.position.set(x, y, z-d/2); mesh.castShadow = true; mesh.receiveShadow = true; group.add(mesh);
  const slope = Math.atan2(height, w/2);
  for (const side of [-1, 1]) {
    const panel = box(group, x+side*w/4, y+height/2+.1, z, Math.hypot(w/2, height)+.5, .18, d+.7, mats.roof);
    panel.rotation.z = -side*slope;
  }
}
function house(group, h, random) {
  const { x, z, w, d } = h; const height = h.h;
  const colors = ['#c0c2ad', '#748378', '#b6afa0', '#979776', '#c2bbb0'];
  box(group, x, .23, z, w+.7, .46, d+.7, '#82877b');
  const wallMat = h.style === 3 ? mats.brick : mats.wall.clone();
  if (h.style !== 3) wallMat.color.set(colors[h.style]);
  box(group, x, height/2+.4, z, w, height, d, wallMat);
  box(group, x, .85, z, w+.03, .65, d+.03, '#767e70');
  roof(group, x, height+.45, z, w+1.6, d+1.2, w*.24, colors[h.style]);
  box(group, x+w*.28, height+2.7, z+d*.22, 1.4, 4.3, 1.35, mats.brick);
  box(group, x+w*.28, height+4.9, z+d*.22, 1.65, .26, 1.6, '#989987');
  const y = height > 7 ? 4.8 : 3.2;
  for (const side of [-1, 1]) {
    for (let n = -1; n <= 1; n += 2) {
      const wx = x+n*w*.28, wz = z+side*(d/2+.035);
      box(group, wx, y, wz, 2.7, 2.6, .15, '#d6d5bc');
      box(group, wx, y+.04, wz+side*.09, 2.26, 2.24, .09, '#344745', .3);
      box(group, wx, y+.05, wz+side*.15, .09, 2.24, .08, '#b7bca8');
      box(group, wx, y+.05, wz+side*.15, 2.24, .09, .08, '#b7bca8');
      for (const s of [-1, 1]) box(group, wx+s*1.7, y, wz, .6, 2.7, .14, '#526653');
      box(group, wx, y-1.35, wz+side*.14, 3, .14, .45, '#dad6bc');
    }
    for (const n of [-1, 1]) {
      const wx = x+side*(w/2+.04), wz = z+n*d*.26;
      box(group, wx, y, wz, .17, 2.6, 2.3, '#c9cbb2');
      box(group, wx+side*.1, y, wz, .09, 2.22, 1.93, '#354945', .3);
      box(group, wx+side*.17, y, wz, .04, .09, 1.93, '#bfc2ac');
    }
  }
  box(group, x, 1.9, z-d/2-.04, 2, 3.2, .22, '#d0c6a8');
  box(group, x, 1.8, z-d/2-.19, 1.66, 2.9, .15, '#4b594e');
  box(group, x+.59, 1.75, z-d/2-.3, .09, .16, .09, '#b6ac83');
  box(group, x, .22, z-d/2-1.4, 3.8, .4, 2.6, '#acac95');
  box(group, x, .07, z-d/2-4, 2.6, .1, 5.7, '#a2a68f');
  // Open front lawns with low wooden boundary fences.
  const fz = z+d/2+3;
  for (let i = 0; i < w+5; i += 1.2) box(group, x-w/2-2+i, .85, fz, .16, 1.7, .17, '#999d7e');
  for (const fy of [.5, 1.2]) box(group, x, fy, fz, w+5, .13, .12, '#a3a788');
  cylinder(group, x+w/2+1.7, .63, z-d/2, .48, 1.25, '#536452');
}
function tree(group, t, random) {
  const { x, z, s } = t;
  cylinder(group, x, 2*s, z, .23*s, 4*s, '#655b40');
  if (t.type === 0) {
    for (let i = 0; i < 4; i++) {
      const mesh = new THREE.Mesh(new THREE.ConeGeometry((2.5-i*.42)*s, 3.1*s, 7), material(['#3c5140', '#415a42', '#496047', '#52694c'][i]));
      mesh.position.set(x, (3+i*1.25)*s, z); mesh.castShadow = true; group.add(mesh);
    }
  } else {
    for (let i = 0; i < 7; i++) {
      const mesh = new THREE.Mesh(new THREE.IcosahedronGeometry((1.7+random()*.65)*s, 1), material(['#536245', '#5b6b46', '#687349', '#495d42'][i%4]));
      mesh.position.set(x+(random()-.5)*2.6*s, (4.8+random()*2)*s, z+(random()-.5)*2.6*s); mesh.scale.y = .9; mesh.castShadow = true; group.add(mesh);
    }
  }
}
function car(group, x, z, color, rot = 0) {
  const g = new THREE.Group(); g.position.set(x, 0, z); g.rotation.y = rot; group.add(g);
  box(g, 0, .72, 0, 2.4, .8, 5.1, color, .5);
  box(g, 0, 1.39, -.2, 2.1, .7, 2.5, '#374847', .25);
  box(g, 0, 1.81, -.2, 2.14, .14, 2.58, color, .5);
  box(g, 0, 1.36, -.2, 2.2, .8, .16, color);
  for (const side of [-1, 1]) {
    for (const wz of [-1.65, 1.65]) { const wheel = cylinder(g, side*1.18, .52, wz, .51, .23, '#202922', 10); wheel.rotation.z = Math.PI/2; }
    box(g, side*.75, .87, 2.57, .45, .25, .04, '#d4c695');
    box(g, side*.75, .85, -2.57, .45, .22, .04, '#793b2e');
  }
  box(g, 0, .53, 2.64, 2.3, .16, .15, '#969d8e', .4);
  box(g, 0, .53, -2.64, 2.3, .16, .15, '#969d8e', .4);
}

export function makeChunk(chunk) {
  init(); const group = new THREE.Group(), random = rng(chunk.seed); const { x, z } = chunk;
  box(group, x+40, -.18, z+40, 80, .25, 80, mats.grass);
  box(group, x+40, -.015, z, 80, .04, 14, mats.asphalt);
  box(group, x, -.012, z+40, 14, .04, 80, mats.asphalt);
  for (const side of [-1, 1]) {
    box(group, x+40, .065, z+side*8.2, 80, .15, 2.2, '#8e9484');
    box(group, x+side*8.2, .065, z+40, 2.2, .15, 80, '#8e9484');
  }
  for (let i = 13; i < 73; i += 8) {
    box(group, x+i, .016, z, 4, .018, .12, '#b9b485');
    box(group, x, .019, z+i, .12, .018, 4, '#b9b485');
  }
  for (let i = 0; i < 6; i++) {
    box(group, x-4+i*1.5, .023, z+12, .8, .02, 3, '#b6b9a0');
    box(group, x+12, .023, z-4+i*1.5, 3, .02, .8, '#b6b9a0');
  }
  for (let i = 0; i < 30; i++) {
    const px = x+random()*78, pz = z+random()*78;
    if (px-x > 12 && pz-z > 12) {
      box(group, px, .04, pz, .2+random()*.4, .09, .3+random()*.5, '#687454');
    }
  }
  chunk.houses.filter(h=>!h.enterable).forEach(h => house(group, h, random));
  chunk.trees.forEach(t => tree(group, t, random));
  car(group, x+30, z+4.6, ['#6e806c', '#a29d83', '#6a8184', '#8c5a48'][Math.floor(random()*4)], .02);
  if (random() > .2) car(group, x-4.5, z+51, '#5c6c62', Math.PI/2+.1);
  for (const offset of [14, 65]) {
    cylinder(group, x+offset, 3.8, z-8, .105, 7.6, '#4c5349');
    box(group, x+offset, 7.6, z-6.7, .13, .13, 2.6, '#535c51');
    box(group, x+offset, 7.5, z-5.5, .5, .2, .86, '#bdbb96');
  }
  // Physical location matches the authoritative resupply station.
  box(group, x+11, .52, z, 1.7, 1.04, 1.4, '#637451');
  box(group, x+11, 1.07, z, 1.8, .12, 1.5, '#9b9d65');
  box(group, x+11, .55, z+.711, .65, .13, .02, '#d7d5a4');
  box(group, x+11, .55, z+.714, .13, .65, .02, '#d7d5a4');
  cylinder(group, x-9.7, 2, z+9.8, .055, 4, '#788273');
  const sign = cylinder(group, x-9.7, 3.5, z+9.8, .6, .07, '#99594b', 8); sign.rotation.x = Math.PI/2;
  const result=mergeGroup(group);result.userData.buildings=[];
  chunk.houses.filter(h=>h.enterable).forEach(h=>{const building=createInterior(h);result.add(building);result.userData.buildings.push(building);});
  return result;
}

// One draw per material per block keeps the large town economical to render.
function mergeGroup(group) {
  group.updateMatrixWorld(true);const meshes=[];
  group.traverse(o=>{if(o.isMesh){const m=new THREE.Mesh(o.geometry,o.material);m.matrix.copy(o.matrixWorld);m.matrixAutoUpdate=false;meshes.push(m);}});
  const result=new THREE.Group();bakeMeshes(meshes).forEach(m=>result.add(m));meshes.forEach(m=>m.geometry.dispose());
  return result;
}