import * as THREE from 'three';
import { limb, rounded } from './characterParts';
import { applyReloadPose, RELOAD_DURATIONS } from './reloadAnimation';

const Y = new THREE.Vector3(0, 1, 0);
const grips = {
  glock18: [[0, -.23, -.16], [-.075, -.21, -.10]],
  rifle: [[0, -.30, -.30], [-.035, -.075, .48]],
  rocket: [[0, -.25, -.08], [0, -.20, .40]],
  minigun: [[0, -.37, -.49], [0, .35, -.03]],
  flamethrower: [[0, -.30, -.26], [0, -.26, .28]],
  lava: [[0, -.34, -.37], [-.19, -.11, .40]],
};
export function makeArms(body, style, weaponType) {
  return [1, -1].map((side, i) => {
    const root = new THREE.Group(); body.add(root);
    const upper = limb(root, 0, 0, 0, style.female ? .092 : .113, .43, style.shirt);
    const fore = limb(root, 0, 0, 0, .079, .42, style.rolled ? style.skin : style.shirt);
    const hand = rounded(root, 0, 0, 0, .13, .14, .16, style.gloves ? '#292e2c' : style.skin, .035);
    const rig = { root, upper, fore, hand, shoulder: new THREE.Vector3(side*(style.female ? .34 : .40), 1.52, .015),
      grip: new THREE.Vector3(...(grips[weaponType] || grips.rifle)[i]), side,
      target: new THREE.Vector3(), axis: new THREE.Vector3(), bend: new THREE.Vector3(), elbow: new THREE.Vector3(), delta: new THREE.Vector3() };
    return rig;
  });
}
function segment(mesh, from, to, base, delta) {
  delta.subVectors(to, from); mesh.position.copy(from).addScaledVector(delta, .5);
  mesh.scale.y = delta.length()/base; mesh.quaternion.setFromUnitVectors(Y, delta.normalize());
}
function solveArms(u) {
  u.gun.updateMatrix();
  u.armRigs.forEach((r, i) => {
    r.target.copy(i === 1 && u.reloadHand ? u.reloadHand : r.grip).applyMatrix4(u.gun.matrix);
    r.axis.subVectors(r.target, r.shoulder); const d = Math.max(.001, r.axis.length()); r.axis.divideScalar(d);
    // Analytic two-bone bend: both palms remain anchored to the gun throughout the transition.
    const length = Math.max(.45, d*.505);
    r.bend.set(r.side*.45, -1, -.12).addScaledVector(r.axis, -r.bend.dot(r.axis)).normalize();
    r.elbow.copy(r.shoulder).addScaledVector(r.axis, d*.5).addScaledVector(r.bend, Math.sqrt(Math.max(0, length*length-d*d*.25)));
    segment(r.upper, r.shoulder, r.elbow, .43, r.delta); segment(r.fore, r.elbow, r.target, .42, r.delta);
    r.hand.position.copy(r.target); r.hand.quaternion.copy(u.gun.quaternion);
  });
}
export function triggerHumanShot(g) {
  const u = g.userData;
  u.shotHold = .24; u.recoil = Math.min(1.35, (u.recoil || 0)+.85); u.flashTime = .065;
}
export function poseHuman(g, time, dt, firing = false, reloading = 0, duration) {
  const u = g.userData; if (!u.gun) return;
  u.shotHold = Math.max(0, (u.shotHold || 0)-dt);
  if (reloading > 0) { u.shotHold = 0; u.flashTime = 0; }
  const active = !reloading && (firing || u.shotHold > 0);
  u.aimBlend += (Number(active)-u.aimBlend)*(1-Math.exp(-dt*(active ? 28 : 9)));
  const a = u.aimBlend, recoil = u.recoil || 0, heavy = u.weaponType === 'minigun' || u.weaponType === 'flamethrower';
  u.recoil = recoil*Math.exp(-dt*22);
  const y = heavy ? 1.14 : u.weaponType === 'rocket' ? 1.61 : 1.50;
  u.gun.position.set(.16, THREE.MathUtils.lerp(1.27, y, a)+Math.sin(time*2.1)*.009*(1-a), .43-recoil*.075);
  u.gun.rotation.set(THREE.MathUtils.lerp(.48, -.025, a)-recoil*.06, -.65*(1-a), -.10*(1-a));
  u.gun.position.y += Math.sin(u.phase*2)*.008*u.blend;
  u.head.rotation.x = -.035*a; u.head.position.z = .015*a;
  applyReloadPose(u, dt, reloading, duration || RELOAD_DURATIONS[u.weaponType]);
  solveArms(u);
  u.flashTime = Math.max(0, (u.flashTime || 0)-dt);
  if (u.muzzleFlash) { u.muzzleFlash.visible = u.flashTime > 0; u.muzzleFlash.rotation.z = time*93; }
  u.pose = reloading > 0 || u.reloadBlend > .1 ? 'reload' : a > .5 ? 'fire' : 'idle';
}