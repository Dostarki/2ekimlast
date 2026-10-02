/**
 * DEADZONE — Procedural 3D loot models.
 *
 * Each model is built from basic Three.js geometry to match the project's
 * existing procedural art style (no external GLB/GLTF files).
 */

import * as THREE from 'three';

// Shared materials (created once, reused across all loot instances).
const mat = {
  gold:      new THREE.MeshStandardMaterial({ color: '#f0c040', metalness: .7, roughness: .3 }),
  goldEdge:  new THREE.MeshStandardMaterial({ color: '#d4a030', metalness: .6, roughness: .35 }),
  xpCore:    new THREE.MeshBasicMaterial({ color: '#4be3ac', transparent: true, opacity: .85 }),
  xpShell:   new THREE.MeshBasicMaterial({ color: '#7be3a0', transparent: true, opacity: .35 }),
  medBox:    new THREE.MeshLambertMaterial({ color: '#d95845' }),
  medCross:  new THREE.MeshLambertMaterial({ color: '#ffffff' }),
  faidBox:   new THREE.MeshLambertMaterial({ color: '#e8e4d8' }),
  faidCross: new THREE.MeshLambertMaterial({ color: '#5a9c6d' }),
  partT1:    new THREE.MeshStandardMaterial({ color: '#1c2226', roughness: .6, metalness: .4 }),
  partT1s:   new THREE.MeshStandardMaterial({ color: '#d4a030', roughness: .5, metalness: .5 }),
  partT2:    new THREE.MeshStandardMaterial({ color: '#2a3a4a', roughness: .5, metalness: .5 }),
  partT2s:   new THREE.MeshStandardMaterial({ color: '#eb705a', roughness: .45, metalness: .55 }),
  partT3:    new THREE.MeshStandardMaterial({ color: '#3a2a4a', roughness: .4, metalness: .6 }),
  partT3s:   new THREE.MeshStandardMaterial({ color: '#c8d6a0', roughness: .35, metalness: .55 }),
  partT3g:   new THREE.MeshBasicMaterial({ color: '#c8d6a0', transparent: true, opacity: .3 }),
};

// ── Gold coin stack ─────────────────────────────────────────────────────────
function goldModel() {
  const g = new THREE.Group();
  for (let i = 0; i < 3; i++) {
    const coin = new THREE.Mesh(new THREE.CylinderGeometry(.28, .28, .08, 12), i === 1 ? mat.goldEdge : mat.gold);
    coin.position.set((i - 1) * .12, .18 + i * .09, (i - 1) * .06);
    coin.rotation.x = .15;
    coin.castShadow = true;
    g.add(coin);
  }
  g.userData.lootKind = 'gold';
  return g;
}

// ── XP orb ──────────────────────────────────────────────────────────────────
function xpModel() {
  const g = new THREE.Group();
  const shell = new THREE.Mesh(new THREE.IcosahedronGeometry(.32, 1), mat.xpShell);
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(.16, 1), mat.xpCore);
  shell.position.y = .45;
  core.position.y = .45;
  g.add(shell, core);
  g.userData.lootKind = 'xp';
  return g;
}

// ── Medkit ───────────────────────────────────────────────────────────────────
function medkitModel() {
  const g = new THREE.Group();
  const box = new THREE.Mesh(new THREE.BoxGeometry(.5, .3, .35), mat.medBox);
  box.position.y = .25;
  box.castShadow = true;
  // White cross
  const h = new THREE.Mesh(new THREE.BoxGeometry(.22, .06, .04), mat.medCross);
  h.position.set(0, .38, .18);
  const v = new THREE.Mesh(new THREE.BoxGeometry(.06, .22, .04), mat.medCross);
  v.position.set(0, .38, .18);
  g.add(box, h, v);
  g.userData.lootKind = 'medkit';
  return g;
}

// ── First Aid Kit ────────────────────────────────────────────────────────────
function faidModel() {
  const g = new THREE.Group();
  const box = new THREE.Mesh(new THREE.BoxGeometry(.36, .22, .26), mat.faidBox);
  box.position.y = .2;
  box.castShadow = true;
  const h = new THREE.Mesh(new THREE.BoxGeometry(.16, .05, .04), mat.faidCross);
  h.position.set(0, .29, .14);
  const v = new THREE.Mesh(new THREE.BoxGeometry(.05, .16, .04), mat.faidCross);
  v.position.set(0, .29, .14);
  g.add(box, h, v);
  g.userData.lootKind = 'faid';
  return g;
}

// ── Weapon part crate ────────────────────────────────────────────────────────
function partModel(tier) {
  const g = new THREE.Group();
  const bodyMat = tier === 3 ? mat.partT3 : tier === 2 ? mat.partT2 : mat.partT1;
  const stripMat = tier === 3 ? mat.partT3s : tier === 2 ? mat.partT2s : mat.partT1s;
  const box = new THREE.Mesh(new THREE.BoxGeometry(.44, .28, .32), bodyMat);
  box.position.y = .24;
  box.castShadow = true;
  // Coloured strip
  const strip = new THREE.Mesh(new THREE.BoxGeometry(.46, .06, .04), stripMat);
  strip.position.set(0, .3, .17);
  g.add(box, strip);
  // Rare tier glow ring
  if (tier === 3) {
    const ring = new THREE.Mesh(new THREE.RingGeometry(.35, .42, 20), mat.partT3g);
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = .06;
    g.add(ring);
  }
  g.userData.lootKind = 'part';
  g.userData.tier = tier;
  return g;
}

// ── Equipment part crate/bundle ──────────────────────────────────────────────
function equipmentPartModel(tier) {
  const g = new THREE.Group();
  const color = tier === 3 ? '#9b5de5' : tier === 2 ? '#00bbf9' : '#00f5d4';
  const matBox = new THREE.MeshStandardMaterial({ color: '#253237', roughness: .5, metalness: .4 });
  const matAccent = new THREE.MeshStandardMaterial({ color, roughness: .3, metalness: .7 });
  const box = new THREE.Mesh(new THREE.BoxGeometry(.4, .25, .28), matBox);
  box.position.y = .22;
  box.castShadow = true;
  const plate = new THREE.Mesh(new THREE.BoxGeometry(.32, .05, .22), matAccent);
  plate.position.set(0, .35, 0);
  g.add(box, plate);
  g.userData.lootKind = 'equipment_part';
  g.userData.tier = tier;
  return g;
}

// ── Calibration Cartridge ─────────────────────────────────────────────────────
function calibrationModel(tier) {
  const g = new THREE.Group();
  const color = tier === 3 ? '#ff0054' : tier === 2 ? '#ffbd00' : '#70e000';
  const matCasing = new THREE.MeshStandardMaterial({ color: '#1b1b1e', roughness: .3, metalness: .8 });
  const matCore = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .9 });
  const can = new THREE.Mesh(new THREE.CylinderGeometry(.12, .12, .42, 12), matCasing);
  can.position.y = .25;
  can.castShadow = true;
  const ring = new THREE.Mesh(new THREE.CylinderGeometry(.13, .13, .12, 12), matCore);
  ring.position.y = .25;
  g.add(can, ring);
  g.userData.lootKind = 'calibration';
  g.userData.tier = tier;
  return g;
}

// ── Public API ───────────────────────────────────────────────────────────────

/** Create a loot 3D model group for the given drop kind/tier. */
export function createLootModel(kind, tier = 0) {
  switch (kind) {
    case 'gold':           return goldModel();
    case 'xp':             return xpModel();
    case 'medkit':         return medkitModel();
    case 'faid':           return faidModel();
    case 'part':           return partModel(tier || 1);
    case 'equipment_part': return equipmentPartModel(tier || 1);
    case 'calibration':    return calibrationModel(tier || 1);
    default:               return goldModel();
  }
}

/** Animate all loot models — bobbing and rotation. Called once per frame. */
export function animateLoot(group, elapsed) {
  const kind = group.userData.lootKind;
  const bob = Math.sin(elapsed * 2.2 + group.position.x * .7) * .12;
  group.children.forEach(c => { c.position.y += bob * .01; });
  // Slowly rotate gold, XP, and calibration cartridges
  if (kind === 'gold' || kind === 'xp' || kind === 'calibration') {
    group.rotation.y = elapsed * 1.4 + group.position.x;
  }
  // Pulse XP shell
  if (kind === 'xp' && group.children[0]) {
    const scale = 1 + Math.sin(elapsed * 3.5) * .12;
    group.children[0].scale.setScalar(scale);
  }
  // Pulse calibration core
  if (kind === 'calibration' && group.children[1]) {
    group.children[1].material.opacity = .65 + Math.sin(elapsed * 4.5) * .35;
  }
  // Glow pulse for T3 parts
  if (kind === 'part' && group.userData.tier === 3 && group.children[2]) {
    group.children[2].material.opacity = .15 + Math.sin(elapsed * 2.8) * .15;
  }
}
