import * as THREE from 'three';
import { flashlightResources } from './flashlightMaterials';

export const FLASHLIGHT_RANGE = 26;
export const FLASHLIGHT_VIEW_RANGE = 42;
export const FLASHLIGHT_LIGHT_BUDGET = 4;

// Every nearby survivor gets a beam; the closest use a fixed real-light pool.
// No per-player shadow maps or additional socket traffic, even in a crowded server.
export class FlashlightSystem {
  constructor(scene, canvas) {
    this.root = new THREE.Group(); this.root.name = 'survivor-flashlights';
    this.root.visible = false; scene.add(this.root);
    this.canvas = canvas; this.records = new Map(); this.resources = flashlightResources();
    this.lights = Array.from({ length: FLASHLIGHT_LIGHT_BUDGET }, () => {
      const light = new THREE.SpotLight('#fff0c9', 0, 28, .34, .7, 2);
      light.castShadow = false;
      this.root.add(light, light.target); return light;
    });
    this.publish([], false);
  }
  clear() {
    this.records.forEach(({ fixture, patch }) => { fixture.removeFromParent(); patch.removeFromParent(); });
    this.records.clear(); this.lights.forEach(light => { light.intensity = 0; });
    this.root.visible = false; this.publish([], false);
  }
  update(enabled, player, me, entities, now, rayDistance) {
    if (!enabled || !me) { if (this.root.visible) this.clear(); return; }
    this.root.visible = true;
    const actors = me.hp > 0 ? [{ id: me.id, group: player, local: true, distance: 0 }] : [];
    entities.forEach((group, id) => {
      const data = group.userData.target;
      if (!data || data.hp <= 0 || group.userData.enemy || group.userData.zombie) return;
      const distance = Math.hypot(group.position.x-player.position.x, group.position.z-player.position.z);
      if (distance <= FLASHLIGHT_VIEW_RANGE) actors.push({ id, group, local: false, distance });
    });
    actors.sort((a, b) => Number(b.local)-Number(a.local) || a.distance-b.distance);
    const wanted = new Set(actors.map(a => a.id));
    this.records.forEach((record, id) => {
      if (!wanted.has(id)) { record.fixture.removeFromParent(); record.patch.removeFromParent(); this.records.delete(id); }
    });
    this.lights.forEach(light => { light.intensity = 0; });
    actors.forEach((actor, index) => {
      let record = this.records.get(actor.id);
      if (!record) { record = this.resources.make(actor.local, actor.id); this.root.add(record.fixture, record.patch); this.records.set(actor.id, record); }
      const { position, rotation } = actor.group, angle = rotation.y, dx = Math.sin(angle), dz = Math.cos(angle);
      const x = position.x+dx*.5+dz*.23, z = position.z+dz*.5-dx*.23;
      // Reuse the movement collision map; do not extend the beam through a facing wall.
      if (now-record.rayAt >= 100 || Math.abs(angle-record.angle) > .12) {
        record.length = Math.max(0, Math.min(FLASHLIGHT_RANGE, rayDistance(position.x, position.z, dx, dz, FLASHLIGHT_RANGE))-.58);
        record.rayAt = now; record.angle = angle;
      }
      record.fixture.position.set(x, position.y+1.35, z); record.fixture.rotation.y = angle;
      record.patch.position.set(x, .075, z); record.patch.rotation.y = angle;
      record.patch.scale.set(record.length*.68, 1, record.length); record.patch.visible = record.length > .3;
      if (index < this.lights.length) {
        const light = this.lights[index];
        light.position.copy(record.fixture.position); light.target.position.set(x+dx*12, .05, z+dz*12);
        light.distance = Math.min(28, Math.hypot(record.length, 1.35)+.5);
        light.intensity = actor.local ? 380 : 230;
      }
    });
    if (now-(this.lastPublish || 0) > 100) {
      this.publish(actors, me.hp > 0); this.lastPublish = now;
    }
  }
  publish(actors, localOn) {
    const data = this.canvas.dataset;
    data.flashlightOn = String(localOn); data.flashlightCount = String(actors.length);
    data.flashlightLightCount = String(this.lights.filter(l => l.intensity > 0).length);
    data.flashlightSources = JSON.stringify(actors.map(a => {
      const r = this.records.get(a.id);
      return { id: a.id, local: a.local, x: r.fixture.position.x, z: r.fixture.position.z, angle: r.fixture.rotation.y, length: r.length };
    }));
  }
  dispose() {
    this.clear(); this.root.removeFromParent(); this.resources.dispose(); this.lights.forEach(light => light.dispose());
  }
}