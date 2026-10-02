import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createHuman, animateHuman, triggerHumanShot, disposeHuman } from './models';
import { SKINS } from './skins';
import { WEAPON_MAP } from './config';
import { RELOAD_DURATIONS } from './reloadAnimation';

function studio() {
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight('#f3eee4', '#778480', 2.6));
  const key = new THREE.DirectionalLight('#fff2d9', 3.4); key.position.set(-3, 4, 5); scene.add(key);
  const rim = new THREE.DirectionalLight('#c3dbea', 2.5); rim.position.set(4, 2, -2); scene.add(rim);
  return scene;
}
let thumbnails;
export function getSkinPreviews() {
  if (thumbnails) return thumbnails;
  const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(240, 260); renderer.setPixelRatio(1);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  const scene = studio(), camera = new THREE.OrthographicCamera(-1.12, 1.12, 1.22, -1.22, .1, 30);
  camera.position.set(3, 2.4, 6); camera.lookAt(0, 1.13, 0);
  thumbnails = {};
  try {
    SKINS.forEach(s => {
      const actor = createHuman(false, 0, 'ak47', s.id); scene.add(actor);
      renderer.render(scene, camera); thumbnails[s.id] = renderer.domElement.toDataURL('image/png'); disposeHuman(actor);
    });
  } finally { renderer.dispose(); renderer.forceContextLoss(); }
  return thumbnails;
}

export class CharacterPreview {
  constructor(container) {
    this.container = container; this.scene = studio(); this.pose = 'idle'; this.time = 0; this.nextShot = 0;
    this.renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.canvas = this.renderer.domElement; this.canvas.dataset.testid = 'character-preview-canvas';
    this.canvas.setAttribute('role', 'img'); container.appendChild(this.canvas);
    this.camera = new THREE.OrthographicCamera(-2, 2, 1.5, -1.5, .1, 30);
    this.controls = new OrbitControls(this.camera, this.canvas);
    this.controls.enablePan = false; this.controls.enableZoom = false; this.controls.minPolarAngle = .7; this.controls.maxPolarAngle = 1.65;
    this.resetCamera();
    this.observer = new ResizeObserver(() => this.resize()); this.observer.observe(container);
    this.last = performance.now(); this.frame = requestAnimationFrame(t => this.animate(t));
  }
  resetCamera() { this.camera.position.set(3.5, 2.65, 6); this.controls.target.set(0, 1.12, 0); this.controls.update(); }
  resize() {
    const w = this.container.clientWidth, h = this.container.clientHeight; if (!w || !h) return;
    this.renderer.setSize(w, h); const half = Math.max(1.40, 1.4*h/w);
    Object.assign(this.camera, { left: -half*w/h, right: half*w/h, top: half, bottom: -half }); this.camera.updateProjectionMatrix();
  }
  setCharacter(skin, weapon) {
    if (this.actor) disposeHuman(this.actor);
    this.actor = createHuman(false, 0, weapon, skin); this.scene.add(this.actor); this.weapon = weapon; this.nextShot = 0;
    this.canvas.dataset.skin = skin; this.canvas.dataset.weapon = weapon;
    this.canvas.setAttribute('aria-label', `3D preview of ${SKINS.find(s => s.id === skin)?.name} character`);
  }
  animate(now) {
    const dt = Math.min(.1, (now-this.last)/1000); this.last = now; this.time += dt;
    if (this.actor && !document.hidden) {
      if (this.pose === 'fire' && now >= this.nextShot) { triggerHumanShot(this.actor); this.nextShot = now+Math.max(.085, WEAPON_MAP[this.weapon].rate)*1000; }
      if(this.lastPose!==this.pose){this.poseStart=now;this.lastPose=this.pose;}
      const duration=RELOAD_DURATIONS[this.weapon];
      const remaining=this.pose==='reload' ? Math.max(0,duration-((now-this.poseStart)/1000)%(duration+.6)) : 0;
      animateHuman(this.actor, this.time, false, false, dt, 0, this.pose === 'fire',remaining,duration);
      const u = this.actor.userData;
      this.canvas.dataset.pose = u.pose; this.canvas.dataset.aimBlend = u.aimBlend.toFixed(3);
      this.canvas.dataset.gunPitch = u.gun.rotation.x.toFixed(3); this.canvas.dataset.recoil = (u.recoil || 0).toFixed(3);
      this.canvas.dataset.handDistance = Math.max(...u.armRigs.map(r => r.hand.position.distanceTo(r.target))).toFixed(4);
      this.canvas.dataset.reloadProgress = (u.reloadProgress || 0).toFixed(3);
      this.canvas.dataset.magazineOffset = u.reloadPart?.position.length().toFixed(3) || '0';
      this.renderer.render(this.scene, this.camera);
    }
    this.frame = requestAnimationFrame(t => this.animate(t));
  }
  dispose() {
    cancelAnimationFrame(this.frame); this.observer.disconnect(); this.controls.dispose();
    if (this.actor) disposeHuman(this.actor); this.renderer.dispose(); this.renderer.forceContextLoss(); this.canvas.remove();
  }
}