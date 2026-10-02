import * as THREE from 'three';

export const RELOAD_DURATIONS = { glock18: 1.5, ak47: 2.1, ak117: 1.8, ak107: 2, shotgun: 2.6, m4: 1.9, rocket: 2.8, minigun: 3.8, flamethrower: 3, lava: 2.5 };
const smooth = (value, from, to) => THREE.MathUtils.smoothstep(value, from, to);
const anchors = { rocket: [0,.04,1.0], minigun: [.10,-.36,-.32], flamethrower: [.12,0,-.33], lava: [.21,0,-.09] };

export function applyReloadPose(u, dt, remaining, duration) {
  const active = remaining > 0;
  u.reloadBlend = THREE.MathUtils.lerp(u.reloadBlend || 0, Number(active), 1-Math.exp(-dt*18));
  u.reloadProgress = active ? THREE.MathUtils.clamp(1-remaining/duration,0,1) : 1;
  const blend = u.reloadBlend, p = u.reloadProgress;
  u.reloadPart = u.reloadPart || u.gun.getObjectByName('reload-part');
  const lift = (smooth(p,.12,.36)-smooth(p,.53,.79))*blend;
  const rocket = u.weaponType === 'rocket', fuel = u.weaponType === 'flamethrower' || u.weaponType === 'lava';
  if (u.reloadPart) {
    u.reloadPart.position.set((fuel ? .45 : .12)*lift,(rocket ? .30 : fuel ? -.15 : -.50)*lift,(rocket ? .48 : .07)*lift);
    u.reloadPart.rotation.z = -.30*lift;
    u.reloadPart.visible = true;
  }
  if (blend < .002) { u.reloadHand = null; return; }
  u.gun.position.y = THREE.MathUtils.lerp(u.gun.position.y,1.32,blend);
  u.gun.rotation.x = THREE.MathUtils.lerp(u.gun.rotation.x,.18,blend);
  u.gun.rotation.y = THREE.MathUtils.lerp(u.gun.rotation.y,-.28,blend);
  u.gun.rotation.z = THREE.MathUtils.lerp(u.gun.rotation.z,-.48,blend);
  const grip = u.armRigs[1].grip;
  if (!u.reloadHand) u.reloadHand = new THREE.Vector3();
  const contact = new THREE.Vector3(...(anchors[u.weaponType] || [0,-.39,.12]));
  if (u.reloadPart) contact.applyAxisAngle(new THREE.Vector3(0,0,1),u.reloadPart.rotation.z).add(u.reloadPart.position);
  const reach = (smooth(p,0,.14)-smooth(p,.92,1))*blend;
  // Seat the magazine, then work the charging handle before returning to the foregrip.
  const charge = smooth(p,.80,.87)-smooth(p,.92,.98);
  contact.lerp(new THREE.Vector3(.10,.10,-.18-Math.sin(Math.max(0,(p-.80)/.18)*Math.PI)*.14),charge);
  u.reloadHand.copy(grip).lerp(contact,reach);
}