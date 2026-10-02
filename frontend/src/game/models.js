import * as THREE from 'three';
import { createWeapon } from './weapons';
import { box, limb, rounded, material, mergeBody } from './characterParts';
import { getSkin } from './skins';
import { dressCharacter } from './characterOutfits';
import { makeArms, poseHuman } from './characterPose';
import { addEquipmentModel } from './equipmentModels';
export { createWeapon } from './weapons';
export { box, cylinder, material, disposeHuman } from './characterParts';
export { triggerHumanShot } from './characterPose';

export function createHuman(zombie = false, variant = 0, weaponType = 'ak47', skinId = 'soldier', equippedEquipment = {}) {
  const g = new THREE.Group(), style = getSkin(skinId);
  const shirt = zombie ? ['#647753', '#6c493f', '#687c7d', '#807859', '#394e55'][variant % 5] : style.shirt;
  const skin = zombie ? '#9b9e7b' : style.skin, pants = zombie ? '#40463f' : style.pants;
  const female = !zombie && style.female, legs = [], knees = [], arms = [];
  for (const side of [-1, 1]) {
    const pivot = new THREE.Group(); pivot.position.set(side*.16, .93, 0); g.add(pivot);
    limb(pivot, 0, -.20, 0, female ? .133 : .145, .44, pants, .95);
    const knee = new THREE.Group(); knee.position.y = -.39; pivot.add(knee); knees.push(knee);
    limb(knee, 0, -.16, 0, female ? .103 : .12, .40, pants, 1.1);
    rounded(knee, 0, -.40, .06, female ? .25 : .28, .21, .42, '#232827', .06);
    if (!zombie && ['civilian', 'gang_male'].includes(style.id)) box(knee, 0, -.49, .06, .28, .035, .43, '#c1c2b4');
    legs.push(pivot);
  }
  const body = new THREE.Group(); g.add(body);
  limb(body, 0, 1.29, 0, female ? .285 : .33, .73, shirt, .65);
  rounded(body, 0, .92, 0, female ? .55 : .59, .24, .37, pants, .08);
  if (zombie) box(body, -.1, 1.32, .205, .19, .26, .009, '#663b30');
  const head = new THREE.Group(); body.add(head);
  const face = new THREE.Mesh(new THREE.SphereGeometry(.24, 16, 12), material(skin));
  face.scale.set(female ? .80 : .86, 1.15, .95); face.position.y = 1.95; face.castShadow = true; head.add(face);
  limb(body, 0, 1.69, 0, .085, .18, skin);
  rounded(head, 0, 1.94, .218, .065, .09, .065, skin, .02);
  for (const side of [-1,1]) {
    limb(head, side*.205, 1.965, 0, .04, .10, skin, .5);
    rounded(head, side*.088, 2.014, .208, .058, .024, .018, '#292a26', .006);
  }
  if (zombie) {
    const hair = new THREE.Mesh(new THREE.SphereGeometry(.242, 14, 8, 0, Math.PI*2, 0, Math.PI*.45), material('#43453a'));
    hair.position.set(0, 2.02, -.025); head.add(hair);
    for (const x of [-.09, .09]) box(head, x, 1.98, .213, .046, .035, .015, '#d5bb68');
    for (const side of [-1, 1]) {
      const arm = new THREE.Group(); arm.position.set(side*.43, 1.49, .03); body.add(arm);
      limb(arm, 0, -.18, 0, .115, .36, shirt); limb(arm, 0, -.395, 0, .085, .22, skin);
      rounded(arm, 0, -.51, .017, .15, .13, .19, skin, .045); arms.push(arm);
    }
  } else {
    dressCharacter(body, head, legs, knees, style);
    const gun = createWeapon(weaponType); gun.scale.setScalar(.64); body.add(gun);
    const flash = new THREE.Mesh(new THREE.ConeGeometry(.11, .34, 5), new THREE.MeshBasicMaterial({ color: '#ffe4a1', transparent: true, opacity: .9, depthWrite: false }));
    flash.rotation.x = Math.PI/2; flash.position.z = weaponType==='glock18'?.46:1.34; flash.visible = false; gun.add(flash);
    g.userData.gun = gun; g.userData.muzzleFlash = flash; g.userData.armRigs = makeArms(body, style, weaponType);
    addEquipmentModel({ body, head, legs, knees, arms: (g.userData.armRigs || []).map(r => r.root) }, equippedEquipment);
  }
  const shadow = new THREE.Mesh(new THREE.CircleGeometry(.65, 20), new THREE.MeshBasicMaterial({ color: '#0c140b', transparent: true, opacity: .3, depthWrite: false }));
  shadow.rotation.x = -Math.PI/2; shadow.position.y = .025; g.add(shadow);
  Object.assign(g.userData, { legs, knees, arms, head, zombie, phase: 0, blend: 0, aimBlend: 0, skin: style.id, weaponType, equipmentKey: JSON.stringify(equippedEquipment || {}) });
  mergeBody(body); mergeBody(head); legs.forEach(mergeBody); knees.forEach(mergeBody); arms.forEach(mergeBody);
  if (!zombie) poseHuman(g, 0, 1/60);
  return g;
}

export function animateHuman(g, time, moving, running = false, dt = 1/60, direction = 0, firing = false, reloading = 0, reloadDuration) {
  const u = g.userData, zombie = u.zombie; u.blend += (Number(moving)-u.blend)*(1-Math.exp(-dt*16));
  u.phase += dt*(zombie ? 5 : running ? 14.5 : 10.5); const amplitude = (zombie ? .35 : running ? .82 : .52)*u.blend;
  u.legs.forEach((leg,i) => {
    const wave = Math.sin(u.phase+i*Math.PI); leg.rotation.x = wave*amplitude;
    leg.rotation.y = Math.sin(direction)*.5*u.blend; leg.rotation.z = Math.sin(direction)*wave*.18*u.blend;
    u.knees[i].rotation.x = -Math.max(0, -wave)*(running ? 1.1 : .64)*u.blend;
  });
  g.position.y = (1-Math.cos(u.phase*2))*(running ? .025 : .013)*u.blend;
  g.rotation.x = (zombie ? .045 : running ? .085 : .015)*u.blend;
  if (zombie) u.arms.forEach((arm,i) => { arm.rotation.x = -1.05+Math.sin(u.phase+i*Math.PI)*.14*u.blend; });
  else poseHuman(g, time, dt, firing, reloading, reloadDuration);
}
