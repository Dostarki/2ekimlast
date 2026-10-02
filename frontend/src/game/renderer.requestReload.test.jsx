// TEST-ONLY MOCKS: avoid ESM/3D runtime parse path and isolate requestReload logic.
jest.mock('three', () => ({ MathUtils: { clamp: v => v, lerp: (a, b) => (a + b) / 2 } }));
jest.mock('./environment', () => ({ makeChunk: jest.fn() }));
jest.mock('./models', () => ({ createHuman: jest.fn(), animateHuman: jest.fn(), triggerHumanShot: jest.fn(), disposeHuman: jest.fn() }));
jest.mock('./movement', () => ({ MovementController: jest.fn() }));
jest.mock('./effects', () => ({ SceneEffects: jest.fn() }));
jest.mock('./enemyModels', () => ({ createEnemy: jest.fn(), animateEnemy: jest.fn() }));
jest.mock('./swarmEffects', () => ({ SwarmEffects: jest.fn() }));
jest.mock('./bossScene', () => ({ BossScene: jest.fn() }));
jest.mock('./snapshotTrack', () => ({ SnapshotTrack: jest.fn() }));
jest.mock('./nameLabels', () => ({ nameLabel: jest.fn(), updateNameLabelScale: jest.fn() }));
jest.mock('./flashlights', () => ({ FlashlightSystem: jest.fn() }));
jest.mock('./lootModels', () => ({ createLootModel: jest.fn(), animateLoot: jest.fn() }));
jest.mock('./skins', () => ({ getSkin: () => ({ id: 'soldier' }) }));
jest.mock('./damage', () => ({ formatDamage: v => String(v) }));
jest.mock('./audio', () => ({ audio: { reload: jest.fn(), stopAutomatic: jest.fn() } }));
jest.mock('./reloadAnimation', () => ({ RELOAD_DURATIONS: { glock18: 1.5, ak47: 2.1 } }));

const { GameRenderer } = require('./renderer');

describe('renderer.requestReload reserve gating', () => {
  const makeCtx = (me) => ({
    state: { me },
    blocked: false,
    localReloadUntil: 0,
    weapon: me.weapon || 'glock18',
    renderer: { domElement: { dataset: {} } },
  });

  it('allows manual reload for infinite reserve Glock18 even at reserve=0', () => {
    const ctx = makeCtx({ hp: 100, reloading: 0, ammo: 0, reserve: 0, infinite_reserve: true, weapon: 'glock18' });
    GameRenderer.prototype.requestReload.call(ctx);
    expect(ctx.localReloadUntil).toBeGreaterThan(0);
  });

  it('blocks manual reload for finite reserve weapon when reserve=0', () => {
    const ctx = makeCtx({ hp: 100, reloading: 0, ammo: 0, reserve: 0, infinite_reserve: false, weapon: 'ak47' });
    GameRenderer.prototype.requestReload.call(ctx);
    expect(ctx.localReloadUntil).toBe(0);
  });
});
