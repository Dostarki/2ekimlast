import * as THREE from 'three';
import { makeChunk } from './environment';
import { createHuman, animateHuman, triggerHumanShot, disposeHuman } from './models';
import {MovementController} from './movement';
import {SceneEffects} from './effects';
import {WEAPON_MAP} from './config';
import {audio} from './audio';
import { createEnemy, animateEnemy } from './enemyModels';
import { SwarmEffects } from './swarmEffects';
import { RELOAD_DURATIONS } from './reloadAnimation';
import { BossScene } from './bossScene';
import { SnapshotTrack } from './snapshotTrack';
import { nameLabel, updateNameLabelScale } from './nameLabels';
import { FlashlightSystem } from './flashlights';
import { createLootModel, animateLoot } from './lootModels';
import { getSkin } from './skins';
import { formatDamage } from './damage';

const appearanceOf = entity => ({ skin: getSkin(entity.skin).id, weapon: entity.weapon || 'ak47', equipmentKey: JSON.stringify(entity.equipped_equipment || {}) });

function zombieHud(group, hp, maxHp) {
  let hud = group.userData.zombieHud;
  if (!hud) {
    const canvas = document.createElement('canvas'); canvas.width = 256; canvas.height = 64;
    const texture = new THREE.CanvasTexture(canvas);
    hud = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false, fog: false }));
    hud.position.y = 3.35; hud.scale.set(3.1, .78, 1); group.add(hud); group.userData.zombieHud = hud;
    hud.userData.canvas = canvas; hud.userData.hp = -1;
  }
  const pct = Math.max(0, Math.min(1, hp / Math.max(1, maxHp)));
  if (Math.abs(hud.userData.hp - pct) < .002) return hud;
  hud.userData.hp = pct;
  const ctx = hud.userData.canvas.getContext('2d'); ctx.clearRect(0, 0, 256, 64);
  ctx.fillStyle = 'rgba(8,15,10,.82)'; ctx.fillRect(18, 23, 220, 15);
  ctx.strokeStyle = 'rgba(201,214,160,.65)'; ctx.strokeRect(18, 23, 220, 15);
  ctx.fillStyle = pct > .35 ? '#b5c68d' : '#d95845'; ctx.fillRect(20, 25, 216 * pct, 11);
  hud.material.map.needsUpdate = true;
  return hud;
}

export class GameRenderer {
  constructor(container, world, onError, onZoomChange) {
    this.container = container; this.world = world; this.onZoomChange = onZoomChange; this.mode = 'lobby'; this.entities = new Map(); this.lootEntities = new Map(); this.chunks = new Map(); this.effects = []; this.corpses = []; this.state = null;
    this.keys = {}; this.pointer = new THREE.Vector2(0, 0); this.mouseDown = false; this.angle = 0; this.blocked = false;
    this.zoom = 24; this.targetZoom = 24; this.minZoom = 4; this.maxZoom = 40;
    this.minimapPose = { x: 0, z: 0, heading: 0, valid: false };
    this.movement=new MovementController();this.localPending=[];this.localAmmo=0;this.nextShot=0;this.localShots=0;this.localReloadUntil=0;
    this.ray = new THREE.Raycaster(); this.plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0); this.aimPoint = new THREE.Vector3();
    this.scene = new THREE.Scene(); this.scene.background = new THREE.Color('#657367'); this.scene.fog = new THREE.Fog('#657367', 105, 220);
    this.fx=new SceneEffects(this.scene);
    this.swarmFx = new SwarmEffects(this.scene);
    this.bossScene = new BossScene(this.scene,this.fx);
    this.camera = new THREE.OrthographicCamera(-50, 50, 35, -35, .1, 350);
    this.focus = new THREE.Vector3(0, 0, 0); this.offset = new THREE.Vector3(58, 72, 58);
    try { this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' }); } catch (e) { onError('Could not initialize 3D graphics in this browser. Enable hardware acceleration.'); throw e; }
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.25)); this.renderer.shadowMap.enabled = true;
    this.autoQuality = true; this.slowFrames = 0; this.pendingEvents = [];
    this.metrics = { fps: 0, frameMs: 0 }; this.metricStart = performance.now(); this.metricFrames = 0;
    this.qualityLevel = 0; this.qualitySince = performance.now(); this.frameAverage = 16;
    this.frustum = new THREE.Frustum(); this.viewMatrix = new THREE.Matrix4(); this.actorBounds = new THREE.Sphere(new THREE.Vector3(), 4);
    this.renderer.shadowMap.type = THREE.PCFShadowMap; this.renderer.toneMapping = THREE.ACESFilmicToneMapping; this.renderer.toneMappingExposure = 1.16;
    this.renderer.domElement.setAttribute('data-testid', 'game-canvas'); this.renderer.domElement.setAttribute('aria-label', 'Westfall 3D play area'); container.appendChild(this.renderer.domElement);
    this.flashlights = new FlashlightSystem(this.scene, this.renderer.domElement);
    this.sky = new THREE.HemisphereLight('#e4ead6', '#4c5544', 2.05); this.scene.add(this.sky);
    this.sun = new THREE.DirectionalLight('#ffe4b5', 3.1); this.sun.position.set(-38, 70, 34); this.sun.castShadow = true;
    this.sun.shadow.mapSize.set(1024, 1024); Object.assign(this.sun.shadow.camera, { left: -70, right: 70, top: 70, bottom: -70, near: 1, far: 180 });
    this.sun.shadow.bias = -.0004; this.sun.shadow.normalBias = .1; this.sun.shadow.autoUpdate = false; this.shadowTime = 0; this.scene.add(this.sun); this.scene.add(this.sun.target);
    this.player = createHuman(false, 0, 'ak47'); this.player.position.set(0, 0, 3); this.player.rotation.y = 1.6; this.scene.add(this.player);
    this.ring = new THREE.Mesh(new THREE.RingGeometry(.83, .9, 40), new THREE.MeshBasicMaterial({ color: '#cedaab', transparent: true, opacity: .75, side: THREE.DoubleSide }));
    this.ring.rotation.x = -Math.PI/2; this.ring.position.y = .045; this.scene.add(this.ring);
    const sanctuary = world.safe_zone || { x: 0, z: 0, radius: 14 };
    const safeZone = new THREE.Mesh(new THREE.RingGeometry(sanctuary.radius-.16, sanctuary.radius, 64), new THREE.MeshBasicMaterial({ color: '#c8d6a0', transparent: true, opacity: .5, side: THREE.DoubleSide, depthWrite: false }));
    safeZone.rotation.x = -Math.PI / 2; safeZone.position.set(sanctuary.x, .055, sanctuary.z); safeZone.renderOrder = 1; this.scene.add(safeZone);
    this.demoZombies = [];
    [[10, -4], [14, 2], [-8, -8], [0, 24], [6, 31], [-4, 39], [28, 3], [-14, 2], [37, 4]].forEach(([x, z], i) => {
      const g = createEnemy(['normal', 'normal', 'hellhound', 'hive', 'normal', 'armored', 'immolator', 'hellhound', 'normal'][i], i); g.position.set(x, 0, z); g.userData.base = new THREE.Vector3(x, 0, z); g.rotation.y = i*1.25; this.scene.add(g); this.demoZombies.push(g);
    });
    this.observer = new ResizeObserver(() => this.resize()); this.observer.observe(container); this.resize(); this.attachEvents(); this.updateChunks(0, 0);
    this.elapsed = 0; this.lastFrame = performance.now(); this.frame = requestAnimationFrame(() => this.animate());
  }
  resize() {
    const w = this.container.clientWidth, h = this.container.clientHeight; if (!w || !h) return;
    this.renderer.setSize(w, h); this.updateProjection();
  }
  updateProjection() {
    const w = this.container.clientWidth, h = this.container.clientHeight; if (!w || !h) return;
    const half = this.mode === 'lobby' ? 39 : this.zoom;
    this.camera.left = -half*w/h; this.camera.right = half*w/h; this.camera.top = half; this.camera.bottom = -half; this.camera.updateProjectionMatrix();
    updateNameLabelScale(this.player?.userData?.nameLabel, half, h, w);
    this.entities.forEach(entity => updateNameLabelScale(entity.userData.nameLabel, half, h, w));
    this.renderer.domElement.dataset.cameraZoom = this.zoom.toFixed(2);
    this.renderer.domElement.dataset.zoomMin = this.minZoom;
    this.renderer.domElement.dataset.zoomMax = this.maxZoom;
  }
  attachEvents() {
    this.down = e => { if (this.mode !== 'playing' || this.blocked || /INPUT|TEXTAREA/.test(e.target.tagName)) return; if (['KeyW','KeyA','KeyS','KeyD','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Space'].includes(e.code)) e.preventDefault(); this.keys[e.code] = true; if(e.code==='KeyR')this.requestReload(); this.publishInput?.(); };
    this.up = e => { this.keys[e.code] = false; this.publishInput?.(); };
    this.mouse = e => { const r = this.container.getBoundingClientRect(); this.pointer.set((e.clientX-r.left)/r.width*2-1, -(e.clientY-r.top)/r.height*2+1); if (this.mode === 'playing' && !this.blocked && !this.aimStick) { this.ray.setFromCamera(this.pointer,this.camera); this.ray.ray.intersectPlane(this.plane,this.aimPoint); this.angle=Math.atan2(this.aimPoint.x-this.player.position.x,this.aimPoint.z-this.player.position.z); this.publishInput?.(); } };
    this.fire = e => { if (e.button === 0 && e.target === this.renderer.domElement) { this.mouseDown = true; this.publishInput?.(); this.tryLocalFire(performance.now()); } };
    this.release = () => { this.mouseDown = false; audio.stopAutomatic(); this.publishInput?.(); };
    this.blur = () => { this.keys = {}; this.mouseDown = false; this.touchMove = null; this.touchFire = false; this.aimStick = false; audio.stopAutomatic(); this.publishInput?.(); };
    this.wheel = e => {
      if (this.mode !== 'playing' || this.blocked) return;
      e.preventDefault();
      const delta = e.deltaY * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? 200 : 1);
      this.targetZoom = THREE.MathUtils.clamp(this.targetZoom * Math.exp(THREE.MathUtils.clamp(delta,-600,600)*.0015), this.minZoom, this.maxZoom);
      this.renderer.domElement.dataset.zoomTarget = this.targetZoom.toFixed(2);
      this.onZoomChange?.(this.targetZoom);
    };
    window.addEventListener('keydown', this.down); window.addEventListener('keyup', this.up); window.addEventListener('pointermove', this.mouse);
    window.addEventListener('pointerdown', this.fire); window.addEventListener('pointerup', this.release); window.addEventListener('blur', this.blur);
    this.renderer.domElement.addEventListener('wheel', this.wheel, { passive: false });
  }
  setMode(mode, weapon, skin = this.skin || 'soldier') {
    this.mode = mode; this.keys = {}; this.mouseDown = false;
    this.timeOfDay = null;
    this.flashlights.clear();
    this.pendingState = null; this.pendingEvents = []; this.lastReceivedAt = null;
    this.metricStart = performance.now(); this.metricFrames = 0; this.qualitySince = performance.now();
    this.movement.intent = null; this.movement.intentSeq = 0;
    this.movement.initialized=false;this.localPending=[];this.nextShot=0;this.localReloadUntil=0;audio.stopAutomatic();audio.stopEnemies();this.fx.clear();this.swarmFx.clear();this.bossScene.clear();
    this.lootEntities.forEach((m) => { this.scene.remove(m); m.traverse(o => o.geometry?.dispose()); }); this.lootEntities.clear();
    this.demoZombies.forEach(z => { z.visible = mode === 'lobby'; });
    if (weapon !== this.weapon || skin !== this.skin) { disposeHuman(this.player); this.player = createHuman(false, 0, weapon, skin); this.scene.add(this.player); this.weapon = weapon; this.skin = skin; }
    this.scene.fog.color.set(mode === 'lobby' ? '#657367' : '#48564a'); this.scene.background.copy(this.scene.fog.color);
    this.resize();
    if (mode === 'lobby') { this.player.position.set(0, 0, 3); this.player.rotation.y = 1.6; this.entities.forEach(disposeHuman); this.entities.clear(); this.state = null; }
  }
  setBlocked(value) { this.blocked = value; if (value) this.blur(); }
  setQuality(value = 'auto') {
    this.quality = ['auto', 'low', 'high'].includes(value) ? value : 'auto';
    this.autoQuality = this.quality === 'auto'; this.qualityLevel = 0; this.qualitySince = performance.now(); this.frameAverage = 16;
    this.renderer.setPixelRatio(this.quality === 'high' ? Math.min(window.devicePixelRatio, 1.5) : this.quality === 'auto' ? Math.min(window.devicePixelRatio, 1.25) : .65);
    this.renderer.shadowMap.enabled = this.quality !== 'low'; this.resize();
  }
  setZoom(value) { this.targetZoom = THREE.MathUtils.clamp(Number(value) || 24, this.minZoom, this.maxZoom); this.zoom = this.targetZoom; this.updateProjection(); }
  getInput(consume=true) {
    if (this.blocked || this.mode !== 'playing') return { type: 'input', x: 0, z: 0, angle: this.angle, fire: false };
    const k = this.keys;
    const horizontal = (k.KeyD || k.ArrowRight ? 1 : 0)-(k.KeyA || k.ArrowLeft ? 1 : 0);
    const vertical = (k.KeyS || k.ArrowDown ? 1 : 0)-(k.KeyW || k.ArrowUp ? 1 : 0);
    const touch = this.touchMove || { x: 0, y: 0 };
    const input = { type: 'input', x: (horizontal+vertical+touch.x+touch.y)*Math.SQRT1_2, z: (-horizontal+vertical-touch.x+touch.y)*Math.SQRT1_2, angle: this.angle, aim_distance:Math.hypot(this.aimPoint.x-this.player.position.x,this.aimPoint.z-this.player.position.z),fire: this.mouseDown || !!this.touchFire, sprint: !!(k.ShiftLeft||k.ShiftRight), reload: !!k.KeyR };
    if(consume)this.keys.KeyR = false; return input;
  }
  requestReload(){
    const me=this.state?.me,now=performance.now();
    if(!me||this.blocked||me.hp<=0||me.reloading||now<this.localReloadUntil||me.ammo>=WEAPON_MAP[this.weapon].mag||(!me.infinite_reserve&&!me.reserve))return;
    this.localReloadUntil=now+RELOAD_DURATIONS[this.weapon]*1000;this.lastReloadSoundAt=now;audio.reload();audio.stopAutomatic();
  }
  tryLocalFire(now){
    if(this.mode!=='playing'||this.blocked||!this.state||this.state.me.hp<=0||this.state.me.reloading>0||now<this.localReloadUntil||now<this.nextShot||this.localAmmo<=0)return;
    const w=WEAPON_MAP[this.weapon];if(!w)return;this.nextShot=now+w.rate*1000;this.localPending.push(now);this.localAmmo--;this.localShots++;
    const x=this.player.position.x,z=this.player.position.z,dx=Math.sin(this.angle),dz=Math.cos(this.angle);
    let range=w.kind==='lava'?Math.min(w.range,Math.max(3,Math.hypot(this.aimPoint.x-x,this.aimPoint.z-z))):w.range;
    range=this.movement.rayDistance(x,z,dx,dz,range);
    for(const e of [...this.state.zombies,...this.state.players,...(this.state.bosses||[])]){if(!e.zombie&&e.alliance_id&&e.alliance_id===this.state.me.alliance?.id&&!this.state.me.alliance?.friendly_fire)continue;const ex=e.x-x,ez=e.z-z,along=ex*dx+ez*dz;if(e.hp>0&&along>0&&along<range&&Math.abs(ex*dz-ez*dx)<(e.radius||.75))range=along;}
    this.fx.shot({kind:w.kind,x,z,tx:x+dx*range,tz:z+dz*range});triggerHumanShot(this.player);audio.shot(this.weapon);
    this.renderer.domElement.dataset.localShots=this.localShots;this.renderer.domElement.dataset.localAmmo=this.localAmmo;
  }
  receive(state) {
    this.pendingState = state;
    this.lastReceivedAt = state.network?.received_at || performance.timeOrigin + performance.now();
    this.pendingEvents.push(...state.events); if (this.pendingEvents.length > 256) this.pendingEvents.splice(0, this.pendingEvents.length-256);
  }
  syncState(state) {
    const previous=this.state?.me, meAppearance=appearanceOf(state.me);
      if (meAppearance.weapon !== this.weapon || meAppearance.skin !== this.skin || this.player.userData.equipmentKey !== meAppearance.equipmentKey) {
      const position = this.player.position.clone(); disposeHuman(this.player);
      this.weapon = meAppearance.weapon; this.skin = meAppearance.skin;
        this.player = createHuman(false, 0, this.weapon, this.skin, state.me.equipped_equipment); this.player.position.copy(position); this.scene.add(this.player);
      this.localPending = []; this.localReloadUntil = 0; this.nextShot = performance.now()+100; audio.stopAutomatic();
    }
    nameLabel(this.player, state.me.name, state.me.id, this.scene);
    updateNameLabelScale(this.player.userData.nameLabel, this.camera.top, this.container.clientHeight, this.container.clientWidth);
    this.setTimeOfDay(state.time_of_day || 'day');
    if(state.me.reloading>0&&!previous?.reloading&&performance.now()-(this.lastReloadSoundAt||0)>500){audio.reload();this.lastReloadSoundAt=performance.now();}
    if(previous?.reloading>0&&!state.me.reloading)this.localReloadUntil=0;
    if(!previous||previous.id!==state.me.id||previous.weapon!==state.me.weapon||state.me.ammo>previous.ammo)this.localPending=[];
    else if(state.me.ammo<previous.ammo)this.localPending.splice(0,previous.ammo-state.me.ammo);
    this.localPending=this.localPending.filter(t=>performance.now()-t<1500);
    this.localAmmo=Math.max(0,state.me.ammo-this.localPending.length);
    if(state.me.reloading>0||state.me.hp<=0||!state.me.ammo)audio.stopAutomatic();
    this.state = state;
    this.lastSnapshotAt=(state.network?.received_at || performance.timeOrigin+performance.now())-performance.timeOrigin;this.fx.sync(state);this.swarmFx.sync(state);this.bossScene.sync(state);
    const wanted = new Set();
    const soldiersList = (state.soldiers || []).map(s => ({ ...s, isSoldier: true }));
    [...state.zombies.map(e => ({ ...e, zombie: true })), ...state.players, ...soldiersList].forEach(e => {
      wanted.add(e.id); let g = this.entities.get(e.id);
      const appearance = e.zombie ? null : appearanceOf(e);
      if (g && appearance && (g.userData.skin !== appearance.skin || g.userData.weaponType !== appearance.weapon || g.userData.equipmentKey !== appearance.equipmentKey)) { disposeHuman(g); g = null; }
      if (!g) { g = e.zombie ? createEnemy(e.enemy_type, e.variant || 0) : createHuman(false, 0, appearance.weapon, appearance.skin, e.equipped_equipment); g.position.set(e.x, 0, e.z); this.scene.add(g); this.entities.set(e.id, g); }
      g.userData.target = e; g.visible = e.hp > 0;
      if (e.zombie) {
        const hud = zombieHud(g, e.hp, e.max_hp || 100);
        hud.visible = performance.now() < (g.userData.healthVisibleUntil || 0) && e.hp > 0;
      }
      if (!e.zombie) {
        nameLabel(g, e.name, e.id, this.scene);
        updateNameLabelScale(g.userData.nameLabel, this.camera.top, this.container.clientHeight, this.container.clientWidth);
      }
      g.userData.track ||= new SnapshotTrack();
      g.userData.track.push(e, state.server_time || this.lastSnapshotAt);
    });
    this.entities.forEach((g, id) => { if (!wanted.has(id)) { g.userData.zombieHud?.material.map?.dispose(); g.userData.zombieHud?.material.dispose(); disposeHuman(g); this.entities.delete(id); } });
    this.pendingEvents.forEach(event => {
      if (event.type === 'shot') {
        // The local player's predicted fire already supplies this effect, but a
        // companion shot is authoritative and must remain visible even though
        // its damage credit belongs to the local owner.
        if (event.soldier_id || event.owner !== state.me.id) {
          this.fx.shot(event);
          const actor = this.entities.get(event.soldier_id || event.owner);
          if (actor) triggerHumanShot(actor);
        }
      } else if (event.type === 'kill') this.corpse(event);
      else if(event.type==='explosion')this.fx.explosion(event);
      else if(event.type==='enemy_attack' && this.entities.get(event.owner)?.visible) this.fx.shot(event);
      else if (event.type === 'damage' && event.zombie && event.owner === state.me.id) this.damageNumber(event);
    });
    this.pendingEvents.forEach(event=>this.bossScene.event(event));
    this.pendingEvents = [];
    this.renderer.domElement.dataset.playerNameLabels = JSON.stringify([state.me.name,...state.players.map(p=>p.name)]);
    // Sync loot drop 3D models.
    const wantedLoot = new Set();
    (state.loot_drops || []).forEach(drop => {
      wantedLoot.add(drop.id);
      if (!this.lootEntities.has(drop.id)) {
        const model = createLootModel(drop.kind, drop.tier);
        model.position.set(drop.x, 0, drop.z);
        this.scene.add(model);
        this.lootEntities.set(drop.id, model);
      }
    });
    this.lootEntities.forEach((model, id) => {
      if (!wantedLoot.has(id)) {
        this.scene.remove(model);
        model.traverse(o => o.geometry?.dispose());
        this.lootEntities.delete(id);
      }
    });
  }
  setTimeOfDay(value) {
    if (value === this.timeOfDay) return;
    this.timeOfDay = value;
    const night = value === 'night';
    this.scene.background.set(night ? '#142232' : '#48564a'); this.scene.fog.color.copy(this.scene.background);
    this.sky.color.set(night ? '#799dbd' : '#e4ead6'); this.sky.groundColor.set(night ? '#233529' : '#4c5544'); this.sky.intensity = night ? .85 : 2.05;
    this.sun.color.set(night ? '#aac9e8' : '#ffe4b5'); this.sun.intensity = night ? .7 : 3.1;
    this.renderer.toneMappingExposure = night ? .95 : 1.16;
    this.renderer.domElement.dataset.timeOfDay = value;
  }
  shot(e) {
    const points = [new THREE.Vector3(e.x, 1.35, e.z), new THREE.Vector3(e.tx, .9, e.tz)];
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color: '#f2d591', transparent: true, opacity: .9 }));
    this.scene.add(line); this.effects.push({ obj: line, until: performance.now()+85 });
    const flash = new THREE.Mesh(new THREE.SphereGeometry(.2, 6, 4), new THREE.MeshBasicMaterial({ color: '#ffe8ae' }));
    flash.position.set(e.x+Math.sin(this.angle)*1.5, 1.4, e.z+Math.cos(this.angle)*1.5); this.scene.add(flash); this.effects.push({ obj: flash, until: performance.now()+60 });
    if (e.hit) {
      for (let i = 0; i < 3; i++) {
        const dot = new THREE.Mesh(new THREE.BoxGeometry(.12, .12, .12), new THREE.MeshBasicMaterial({ color: '#8c352e' }));
        dot.position.set(e.tx+(Math.random()-.5), .5+Math.random(), e.tz+(Math.random()-.5)); this.scene.add(dot); this.effects.push({ obj: dot, until: performance.now()+160 });
      }
    }
  }
  corpse(e) {
    if(e.boss_type)return;
    const g = e.zombie ? createEnemy(e.enemy_type, 1) : createHuman(false, 0, e.weapon, e.skin); g.position.set(e.x, .25, e.z); g.rotation.z = Math.PI/2; g.rotation.y = Math.random()*6;
    if (g.userData.flames) g.userData.flames.visible = false;
    this.scene.add(g); this.corpses.push(g); if (this.corpses.length > 20) disposeHuman(this.corpses.shift());
  }
  damageNumber(event) {
    const target = this.entities.get(event.target);
    if (target?.userData.zombieHud) { target.userData.healthVisibleUntil = performance.now()+3000; target.userData.zombieHud.visible = true; }
    const floating = this.effects.filter(effect => effect.floating);
    if (floating.length >= 12) { const oldest = floating[0]; this.scene.remove(oldest.obj); oldest.obj.material.dispose(); this.effects.splice(this.effects.indexOf(oldest), 1); }
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: this.damageTexture(formatDamage(event.amount)), transparent: true, depthWrite: false, fog: false }));
    if (target) sprite.position.copy(target.position).add(new THREE.Vector3((Math.random()-.5)*.35, 3.8, 0));
    else sprite.position.set(event.x, 3.8, event.z);
    this.scaleDamageSprite(sprite); this.scene.add(sprite);
    this.effects.push({ obj: sprite, until: performance.now()+650, floating: true });
  }
  damageTexture(label) {
    this.damageTextures ||= new Map();
    if (this.damageTextures.has(label)) { const texture = this.damageTextures.get(label); this.damageTextures.delete(label); this.damageTextures.set(label, texture); return texture; }
    if (this.damageTextures.size >= 24) {
      const activeMaps = new Set(this.effects.filter(effect => effect.floating).map(effect => effect.obj.material.map));
      const stale = [...this.damageTextures.entries()].find(([, texture]) => !activeMaps.has(texture));
      if (stale) { const [key, texture] = stale; texture.dispose(); this.damageTextures.delete(key); }
    }
    const canvas = document.createElement('canvas'); canvas.width = 160; canvas.height = 80;
    const ctx = canvas.getContext('2d'); ctx.font = '700 44px "Barlow Condensed", sans-serif'; ctx.textAlign = 'center'; ctx.fillStyle = '#f1e6c6'; ctx.strokeStyle = '#28150f'; ctx.lineWidth = 6; ctx.strokeText(label, 80, 52); ctx.fillText(label, 80, 52);
    const texture = new THREE.CanvasTexture(canvas); this.damageTextures.set(label, texture); return texture;
  }
  scaleDamageSprite(sprite) {
    const height = Math.max(1, this.container.clientHeight || 1);
    const worldPerPixel = (this.camera.top - this.camera.bottom) / height;
    sprite.scale.set(96 * worldPerPixel, 48 * worldPerPixel, 1);
  }
  updateChunks(x, z) {
    const cx = Math.floor(x/80), cz = Math.floor(z/80), key = `${cx},${cz}`; if (key === this.chunkKey) return; this.chunkKey = key;
    const nearby = this.world.chunks.filter(c => Math.abs(c.x/80-cx) <= 1 && Math.abs(c.z/80-cz) <= 1);
    this.nearby=nearby;this.movement.load(nearby);
    const wanted = new Set(nearby.map(c => c.id));
    this.chunks.forEach((g, id) => { if (!wanted.has(id)) { this.scene.remove(g); g.traverse(o => o.geometry?.dispose()); this.chunks.delete(id); } });
    this.chunkQueue = nearby.filter(c => !this.chunks.has(c.id)).sort((a,b) => Math.hypot(a.x+40-x,a.z+40-z)-Math.hypot(b.x+40-x,b.z+40-z));
    if (this.mode !== 'playing') while (this.chunkQueue.length) this.loadNextChunk();
  }
  loadNextChunk() {
    const chunk = this.chunkQueue?.shift(); if (!chunk) return;
    const group = makeChunk(chunk); this.chunks.set(chunk.id, group); this.scene.add(group);
  }
  updatePerformance(now, elapsed) {
    this.metricFrames++;
    if (now - this.metricStart >= 500) {
      this.metrics = { fps: Math.round(this.metricFrames * 1000 / (now - this.metricStart)), frameMs: Math.round((now - this.metricStart) / this.metricFrames) };
      this.metricStart = now; this.metricFrames = 0;
      this.renderer.domElement.dataset.fps = this.metrics.fps;
    }
    this.frameAverage += (Math.min(elapsed, 250) - this.frameAverage) * .08;
    if (this.autoQuality && this.mode === 'playing' && now - this.qualitySince > 2500 && this.frameAverage > 32 && this.qualityLevel < 2) {
      this.qualityLevel++;
      this.renderer.shadowMap.enabled = false;
      this.renderer.setPixelRatio(this.qualityLevel === 1 ? .85 : .65);
      this.qualitySince = now; this.resize();
    }
  }
  animate() {
    if (this.disposed) return;
    const now = performance.now();
    if(this.mode!=='playing'&&now-this.lastFrame<160){this.frame=requestAnimationFrame(()=>this.animate());return;}
    const elapsed = now-this.lastFrame; const dt = Math.min(elapsed/1000, .1); this.lastFrame = now; this.elapsed += dt; const t = this.elapsed;
    if (this.pendingState) { this.syncState(this.pendingState); this.pendingState = null; }
    this.updatePerformance(now, elapsed);
    if (this.mode === 'playing' && Math.abs(this.zoom-this.targetZoom) > .005) {
      this.zoom = THREE.MathUtils.lerp(this.zoom, this.targetZoom, 1-Math.exp(-dt*12)); this.updateProjection();
    }
    if (this.mode === 'playing' && this.state) {
      const me = this.state.me,input=this.getInput(false);
      const snapshotAge=(now-this.lastSnapshotAt)/1000;
      const activeInput=snapshotAge>1?{...input,x:0,z:0,fire:false}:input;
      const predicted=this.movement.update(dt,activeInput,me,snapshotAge,this.state.network?.rtt || 0);
      this.player.position.set(predicted.x,0,predicted.z);
      const moving=predicted.speed>.15;
      this.ray.setFromCamera(this.pointer, this.camera); this.ray.ray.intersectPlane(this.plane, this.aimPoint);
      const touchTargets=[...this.state.zombies,...(this.state.bosses||[]).filter(b=>b.alive&&Math.hypot(b.x-me.x,b.z-me.z)<70)];
      if (this.aimStick) {
        // Manual aim: this.angle is driven directly by the on-screen aim joystick.
      } else if (this.touchFire && touchTargets.length) {
        const target = touchTargets.reduce((a, b) => Math.hypot(a.x-me.x, a.z-me.z) < Math.hypot(b.x-me.x, b.z-me.z) ? a : b);
        this.angle = Math.atan2(target.x-me.x, target.z-me.z);
      } else this.angle = Math.atan2(this.aimPoint.x-this.player.position.x, this.aimPoint.z-this.player.position.z);
      // The tactical map follows locomotion, not cursor aim. This retains its
      // last useful orientation while the survivor is standing still.
      if (moving && Math.hypot(input.x, input.z) > .01) this.minimapPose.heading = Math.atan2(input.x, input.z);
      this.minimapPose.x = predicted.x; this.minimapPose.z = predicted.z; this.minimapPose.valid = true;
      if(activeInput.fire)this.tryLocalFire(now);else audio.stopAutomatic();
      const firing = !this.blocked && me.hp > 0 && !me.reloading && now >= this.localReloadUntil && (now < this.nextShot || (input.fire && this.localAmmo > 0));
      if (!firing && (this.blocked || me.hp <= 0 || me.reloading)) { this.player.userData.shotHold = 0; this.player.userData.flashTime = 0; }
      const reloadRemaining=me.hp>0 ? (me.reloading || Math.max(0,(this.localReloadUntil-now)/1000)) : 0;
      this.player.rotation.y = this.angle; this.player.visible = me.hp > 0; animateHuman(this.player,t,moving,predicted.running,dt,Math.atan2(input.x,input.z)-this.angle,firing,reloadRemaining,me.reload_duration);
      if (this.player.userData.nameLabel) {
        this.player.userData.nameLabel.position.set(this.player.position.x, 3.2, this.player.position.z);
        this.player.userData.nameLabel.visible = this.player.visible;
      }
      this.focus.lerp(this.player.position.clone().add(new THREE.Vector3(0, .85, 0)), 1-Math.exp(-dt*24)); this.updateChunks(predicted.x,predicted.z);
      this.renderer.domElement.dataset.playerX = me.x; this.renderer.domElement.dataset.playerZ = me.z;
      this.renderer.domElement.dataset.playerWeapon = me.weapon;
      this.renderer.domElement.dataset.playerSkin = this.player.userData.skin;
      this.renderer.domElement.dataset.playerPose = this.player.userData.pose;
      this.renderer.domElement.dataset.gunPitch = this.player.userData.gun.rotation.x.toFixed(3);
      this.renderer.domElement.dataset.aimBlend = this.player.userData.aimBlend.toFixed(3);
      this.renderer.domElement.dataset.reloadProgress = (this.player.userData.reloadProgress || 0).toFixed(3);
      this.renderer.domElement.dataset.magazineOffset = this.player.userData.reloadPart?.position.length().toFixed(3) || '0';
      this.renderer.domElement.dataset.enemySounds = audio.creatures?.metrics.played || 0;
      this.renderer.domElement.dataset.lastEnemySound = audio.creatures?.metrics.last || '';
      this.renderer.domElement.dataset.swarmSound = audio.creatures?.metrics.swarm || false;
      this.renderer.domElement.dataset.enemyTypes = [...new Set(this.state.zombies.map(e => e.enemy_type))].join(',');
      this.renderer.domElement.dataset.swarmCount = this.state.swarms?.length || 0;
      this.renderer.domElement.dataset.bossCount = this.bossScene.models.size;
      this.renderer.domElement.dataset.bosses = JSON.stringify((this.state.bosses||[]).map(b=>({id:b.id,hp:b.hp,x:b.x,z:b.z,action:b.action})));
      this.renderer.domElement.dataset.remotePlayers = JSON.stringify([...this.entities.values()].filter(g => !g.userData.zombie).map(g => ({ id: g.userData.target.id, skin: g.userData.skin, pose: g.userData.pose })));
      this.renderer.domElement.dataset.predictedX=predicted.x.toFixed(2);this.renderer.domElement.dataset.predictedZ=predicted.z.toFixed(2);this.renderer.domElement.dataset.running=predicted.running;
      let inside='';this.chunks.forEach(chunk=>{(chunk.userData.buildings||[]).forEach(b=>{const h=b.userData.building,interior=Math.abs(predicted.x-h.x)<h.w/2-.25&&Math.abs(predicted.z-h.z)<h.d/2-.25;b.userData.cover.visible=!interior;if(interior)inside=h.name;});});this.renderer.domElement.dataset.interior=inside;
      const renderTime=(this.state.server_time || this.lastSnapshotAt)+Math.max(0,now-this.lastSnapshotAt)-Math.min(150,Math.max(60,(this.state.network?.interval||50)*1.3+(this.state.network?.jitter||0)*.25));
      this.viewMatrix.multiplyMatrices(this.camera.projectionMatrix, this.camera.matrixWorldInverse); this.frustum.setFromProjectionMatrix(this.viewMatrix);
    this.entities.forEach(g => {
        const e = g.userData.target; if (!e) return;
        const next = g.userData.track.sample(renderTime) || e;
        const move = Math.hypot(g.position.x-next.x,g.position.z-next.z) > .01;
        g.position.x=next.x;g.position.z=next.z;g.rotation.y=next.angle;
        this.actorBounds.center.set(next.x,1,next.z); g.visible=e.hp>0&&this.frustum.intersectsSphere(this.actorBounds);
      if (!g.visible) {
        if (g.userData.nameLabel) g.userData.nameLabel.visible = false;
        return;
      }
      if (g.userData.nameLabel) {
        g.userData.nameLabel.position.set(g.position.x, 3.2, g.position.z);
        g.userData.nameLabel.visible = g.visible;
      }
        if (g.userData.zombieHud) g.userData.zombieHud.visible = performance.now() < (g.userData.healthVisibleUntil || 0) && e.hp > 0;
        if (g.userData.enemy) animateEnemy(g,t+e.x,move,dt,e); else animateHuman(g,t+e.x,move,e.running,dt,0,e.firing && e.hp > 0,e.reloading,e.reload_duration);
      });
    } else {
      // The lobby is a living, full-bleed view into the same procedural town.
      const desired = new THREE.Vector3(-17, 0, 19);
      this.focus.lerp(desired, Math.min(1, dt*3)); animateHuman(this.player,t,false,false,dt);
      if (this.player.userData.nameLabel) {
        this.player.userData.nameLabel.position.set(this.player.position.x, 3.2, this.player.position.z);
        this.player.userData.nameLabel.visible = this.player.visible;
      }
      this.demoZombies.forEach((g, i) => { const b = g.userData.base; g.position.set(b.x+Math.sin(t*.12+i)*1.6, 0, b.z+Math.cos(t*.12+i)*1.6); g.rotation.y = t*.12+i+Math.PI/2; animateEnemy(g, t+i, true, dt); });
      this.updateChunks(0, 0);
    }
    this.camera.position.copy(this.focus).add(this.offset); this.camera.lookAt(this.focus);
    this.flashlights.update(this.mode === 'playing' && this.timeOfDay === 'night', this.player, this.state?.me, this.entities, now, (x,z,dx,dz,range) => this.movement.rayDistance(x,z,dx,dz,range));
    this.sun.position.copy(this.focus).add(new THREE.Vector3(-38, 70, 34)); this.sun.target.position.copy(this.focus);
    if (now-this.shadowTime > 120) { this.sun.shadow.needsUpdate = true; this.shadowTime = now; }
    this.ring.position.x = this.player.position.x; this.ring.position.z = this.player.position.z; this.ring.visible = this.player.visible;
    this.fx.update(dt,t);
    this.swarmFx.update(dt,t);
    this.bossScene.update(dt,t);
    this.lootEntities.forEach(model => animateLoot(model, t));
    for (let i = this.effects.length-1; i >= 0; i--) { const effect=this.effects[i]; if (effect.floating) { effect.obj.position.y += dt*1.15; this.scaleDamageSprite(effect.obj); effect.obj.material.opacity = Math.max(0, (effect.until-performance.now())/650); } if (performance.now() > effect.until) { const o = effect.obj; this.scene.remove(o); o.geometry?.dispose(); if (!effect.floating) o.material.map?.dispose(); o.material.dispose(); this.effects.splice(i, 1); } }
    this.renderer.render(this.scene, this.camera);
    this.renderer.domElement.dataset.renderCalls = this.renderer.info.render.calls;
    this.renderer.domElement.dataset.renderTriangles = this.renderer.info.render.triangles;
    this.renderer.domElement.dataset.frameMs = Math.round(elapsed);
    if (this.mode === 'playing') this.loadNextChunk();
    this.frame = requestAnimationFrame(() => this.animate());
  }
  dispose() {
    audio.stopAutomatic();audio.stopEnemies();this.fx.clear();this.fx.streams.dispose();this.swarmFx.dispose();this.bossScene.dispose();this.flashlights.dispose();
    this.lootEntities.forEach((m) => { this.scene.remove(m); m.traverse(o => o.geometry?.dispose()); }); this.lootEntities.clear();
    this.disposed = true; cancelAnimationFrame(this.frame); this.observer.disconnect();
    window.removeEventListener('keydown', this.down); window.removeEventListener('keyup', this.up); window.removeEventListener('pointermove', this.mouse); window.removeEventListener('pointerdown', this.fire); window.removeEventListener('pointerup', this.release); window.removeEventListener('blur', this.blur);
    this.renderer.domElement.removeEventListener('wheel', this.wheel);
    this.damageTextures?.forEach(texture => texture.dispose()); this.damageTextures?.clear();
    disposeHuman(this.player); this.entities.forEach(disposeHuman); this.demoZombies.forEach(disposeHuman); this.corpses.forEach(disposeHuman);
    this.scene.traverse(o => o.geometry?.dispose()); this.renderer.dispose(); this.renderer.domElement.remove();
  }
}
