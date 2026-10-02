import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { bakeMeshes } from './batching';

const materials = new Map();
export const material = (color, roughness = .85) => {
  const key = `${color}-${roughness}`;
  if (!materials.has(key)) materials.set(key, roughness < .6 ? new THREE.MeshStandardMaterial({ color, roughness, metalness: .55 }) : new THREE.MeshLambertMaterial({ color }));
  return materials.get(key);
};
export function box(group, x, y, z, w, h, d, color, roughness) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), typeof color === 'object' ? color : material(color, roughness));
  mesh.position.set(x, y, z); mesh.castShadow = true; mesh.receiveShadow = true; group.add(mesh); return mesh;
}
export function cylinder(group, x, y, z, radius, height, color, sides = 8) {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, height, sides), material(color));
  mesh.position.set(x, y, z); mesh.castShadow = true; group.add(mesh); return mesh;
}
export function rounded(group, x, y, z, w, h, d, color, radius = .04) {
  const mesh = new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 2, radius), material(color));
  mesh.position.set(x, y, z); mesh.castShadow = true; mesh.receiveShadow = true; group.add(mesh); return mesh;
}
export function limb(group, x, y, z, radius, length, color, scaleZ = 1) {
  const mesh = new THREE.Mesh(new THREE.CapsuleGeometry(radius, Math.max(.01, length-radius*2), 4, 10), material(color));
  mesh.position.set(x, y, z); mesh.scale.z = scaleZ; mesh.castShadow = true; group.add(mesh); return mesh;
}
export function mergeBody(group) {
  const meshes = group.children.filter(c => c.isMesh && !c.material.transparent && !c.userData.articulated);
  const baked = bakeMeshes(meshes);
  meshes.forEach(m => { group.remove(m); m.geometry.dispose(); }); baked.forEach(m => group.add(m));
}
export function disposeHuman(group) {
  const flash = group.userData.muzzleFlash;
  if (flash) { flash.geometry.dispose(); flash.material.dispose(); flash.removeFromParent(); }
  const gun = group.userData.gun;
  if (gun) gun.removeFromParent();
  if (group.userData.nameLabel) {
    group.userData.nameLabel.material?.map?.dispose();
    group.userData.nameLabel.material?.dispose();
    group.userData.nameLabel.removeFromParent();
    group.userData.nameLabel = null;
  }
  group.traverse(o => { if (!o.isSprite) o.geometry?.dispose(); if (o.userData.nameLabel) o.material?.map?.dispose(); if (o.material?.transparent) o.material.dispose(); });
  group.removeFromParent();
}