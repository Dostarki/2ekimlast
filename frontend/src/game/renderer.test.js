jest.mock('./models', () => ({
  createHuman: jest.fn(), disposeHuman: jest.fn(), animateHuman: jest.fn(), triggerHumanShot: jest.fn(),
}));
jest.mock('three', () => ({ CanvasTexture: jest.fn(function CanvasTexture() {}) }));
jest.mock('./environment', () => ({ makeChunk: jest.fn() }));
jest.mock('./movement', () => ({ MovementController: jest.fn() }));
jest.mock('./effects', () => ({ SceneEffects: jest.fn() }));
jest.mock('./config', () => ({ WEAPON_MAP: {} }));
jest.mock('./nameLabels', () => ({ nameLabel: jest.fn(), updateNameLabelScale: jest.fn() }));
jest.mock('./audio', () => ({ audio: { stopAutomatic: jest.fn() } }));
jest.mock('./enemyModels', () => ({ createEnemy: jest.fn(), animateEnemy: jest.fn() }));
jest.mock('./swarmEffects', () => ({ SwarmEffects: jest.fn() }));
jest.mock('./reloadAnimation', () => ({ RELOAD_DURATIONS: {} }));
jest.mock('./bossScene', () => ({ BossScene: jest.fn() }));
jest.mock('./snapshotTrack', () => ({ SnapshotTrack: class { push() {} } }));
jest.mock('./flashlights', () => ({ FlashlightSystem: jest.fn() }));
jest.mock('./lootModels', () => ({ createLootModel: jest.fn(), animateLoot: jest.fn() }));

import { GameRenderer } from './renderer';
import { createHuman, disposeHuman } from './models';

const group = () => ({ userData: { skin: 'soldier', weaponType: 'glock18', equipmentKey: '{}' }, position: { set: jest.fn() } });
const soldier = (id, skin, weapon = 'ak47') => ({ id, skin, weapon, x: 100, z: 10, angle: 0, hp: 100, max_hp: 100, tier_name: id, equipped_equipment: {} });
const snapshot = soldiers => ({
  me: { id: 'me', name: 'Me', hp: 100, ammo: 17, weapon: 'glock18', skin: 'soldier', equipped_equipment: {}, reloading: 0 },
  players: [], zombies: [], soldiers, events: [], loot_drops: [], time_of_day: 'day', server_time: 1,
});

function renderer() {
  const player = group();
  return {
    state: null, player, weapon: 'glock18', skin: 'soldier', entities: new Map(), lootEntities: new Map(), effects: [], pendingEvents: [], localPending: [], localReloadUntil: 0, nextShot: 0,
    scene: { add: jest.fn(), remove: jest.fn() }, renderer: { domElement: { dataset: {} } }, camera: { top: 24 }, container: { clientHeight: 768, clientWidth: 1440 },
    fx: { sync: jest.fn() }, swarmFx: { sync: jest.fn() }, bossScene: { sync: jest.fn(), event: jest.fn() }, setTimeOfDay: jest.fn(),
  };
}

describe('GameRenderer syncState companion appearance reuse', () => {
  beforeEach(() => {
    createHuman.mockImplementation((zombie, variant, weaponType, skin, equipment = {}) => ({ userData: { skin, weaponType, equipmentKey: JSON.stringify(equipment) }, position: { set: jest.fn() } })); disposeHuman.mockReset(); createHuman.mockClear();
  });

  it('creates five companion models once across 100 unchanged S1–S5 snapshots', () => {
    const r = renderer();
    const companions = ['soldier', 'soldier_woodland', 'soldier_desert', 'soldier_urban', 'soldier_winter']
      .map((skin, index) => soldier(`s${index + 1}`, skin));
    for (let index = 0; index < 100; index += 1) GameRenderer.prototype.syncState.call(r, snapshot(companions));
    expect(createHuman).toHaveBeenCalledTimes(5);
    expect(disposeHuman).not.toHaveBeenCalled();
  });

  it('rebuilds exactly one upgraded companion and disposes exactly one removed companion', () => {
    const r = renderer();
    const companions = ['soldier', 'soldier_woodland', 'soldier_desert', 'soldier_urban', 'soldier_winter']
      .map((skin, index) => soldier(`s${index + 1}`, skin));
    GameRenderer.prototype.syncState.call(r, snapshot(companions));
    const upgraded = companions.map(entry => entry.id === 's3' ? { ...entry, weapon: 'm4' } : entry);
    GameRenderer.prototype.syncState.call(r, snapshot(upgraded));
    expect(createHuman).toHaveBeenCalledTimes(6);
    expect(disposeHuman).toHaveBeenCalledTimes(1);
    GameRenderer.prototype.syncState.call(r, snapshot(upgraded.slice(0, 4)));
    expect(disposeHuman).toHaveBeenCalledTimes(2);
  });

  it('maintains a 96px damage label from zoom 4 through 40', () => {
    const r = renderer(); const sprite = { scale: { set: jest.fn() } };
    r.camera.top = 4; r.camera.bottom = -4; GameRenderer.prototype.scaleDamageSprite.call(r, sprite);
    const near = sprite.scale.set.mock.calls.at(-1);
    r.camera.top = 40; r.camera.bottom = -40; GameRenderer.prototype.scaleDamageSprite.call(r, sprite);
    const far = sprite.scale.set.mock.calls.at(-1);
    expect(far[0] / near[0]).toBe(10);
    expect(near[0] / ((4 - -4) / 768)).toBe(96);
    expect(far[0] / ((40 - -40) / 768)).toBe(96);
  });

  it('never evicts a CanvasTexture that an active floating sprite still uses', () => {
    HTMLCanvasElement.prototype.getContext = jest.fn(() => ({ strokeText: jest.fn(), fillText: jest.fn() }));
    const active = { dispose: jest.fn() }, stale = { dispose: jest.fn() };
    const r = { damageTextures: new Map([['active', active], ['stale', stale]]), effects: [{ floating: true, obj: { material: { map: active } } }] };
    for (let index = 2; index < 24; index += 1) r.damageTextures.set(String(index), { dispose: jest.fn() });
    GameRenderer.prototype.damageTexture.call(r, 'new');
    expect(active.dispose).not.toHaveBeenCalled();
    expect(stale.dispose).toHaveBeenCalledTimes(1);
  });
});
