import * as THREE from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { createWeapon } from './weapons';
import { WEAPONS } from './config';
let cache;
export function getWeaponPreviews() {
  if (cache) return cache;
  cache = {};
  try {
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, preserveDrawingBuffer: true }); renderer.setSize(640, 267); renderer.setPixelRatio(1);
    renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = .95;
    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer); const room = new RoomEnvironment(); const environment = pmrem.fromScene(room, .035);
    scene.environment = environment.texture; scene.environmentIntensity = .7;
    scene.add(new THREE.HemisphereLight('#f3f5ee', '#6b7780', .65));
    const key = new THREE.DirectionalLight('#f6f5ec', 2.3); key.position.set(-1, 3, 4); scene.add(key);
    const rim = new THREE.DirectionalLight('#c2d7e4', 2.1); rim.position.set(1, 1, -3); scene.add(rim);
    const camera = new THREE.OrthographicCamera(-1.38, 1.38, .575, -.575, .1, 20); camera.position.set(.18, .42, 6); camera.lookAt(0, -.16, 0);
    WEAPONS.map(w=>w.id).forEach(type => {
      const weapon = createWeapon(type); weapon.rotation.y = Math.PI/2; if(type==='glock18')weapon.scale.setScalar(1.6); scene.add(weapon); renderer.render(scene, camera); cache[type] = renderer.domElement.toDataURL('image/png'); scene.remove(weapon);
    });
    environment.dispose(); room.dispose(); pmrem.dispose(); renderer.dispose(); renderer.forceContextLoss();
  } catch (e) { console.error('Weapon previews could not render', e); cache = {}; }
  return cache;
}