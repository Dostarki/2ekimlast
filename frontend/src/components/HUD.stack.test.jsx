import { act } from 'react';
import { createRoot } from 'react-dom/client';
jest.mock('./Lobby', () => ({ WEAPONS: [{ id: 'glock18', name: 'Glock 18' }] }));
jest.mock('./DeathPanel', () => ({ DeathPanel: () => null }));
jest.mock('../game/weaponPreviews', () => ({ getWeaponPreviews: () => ({}) }));
jest.mock('./BossMap', () => ({ BOSS_ICONS: { test: () => null }, bossTime: () => '0:00' }));
import { HUD } from './HUD';
import { BossHUD } from './BossHUD';

const noop = () => {};
const state = {
  online: 1, tick_ms: 1, network: {}, players: [], zombies: [], events: [],
  bosses: [{ id: 'boss-1', boss_type: 'test', alive: true, x: 4, z: 0, hp: 100, max_hp: 100, name: 'Titan', color: '#d95845', subtitle: 'ACTIVE', action: '' }],
  me: { id: 'me', name: 'Me', x: 0, z: 0, hp: 100, max_hp: 100, stamina: 100, weapon: 'glock18', ammo: 17, reserve: 0, score: 0, kills: 0, pvp: 0, level: 1, xp_needed: 1, xp_progress: 0, statuses: {}, safe_zone: true, protected: 5, awaiting_input: false, heal_items: {}, equipped_equipment: {} },
};

describe('HUD top notification flow', () => {
  let container; let root; let raf; let cancelRaf; let canvasCtx;
  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    raf = jest.fn(); cancelRaf = jest.fn(); global.requestAnimationFrame = raf; global.cancelAnimationFrame = cancelRaf;
    canvasCtx = { clearRect: jest.fn(), fillRect: jest.fn(), fillText: jest.fn(), save: jest.fn(), translate: jest.fn(), rotate: jest.fn(), restore: jest.fn(), beginPath: jest.fn(), arc: jest.fn(), fill: jest.fn(), stroke: jest.fn(), moveTo: jest.fn(), lineTo: jest.fn(), closePath: jest.fn() };
    HTMLCanvasElement.prototype.getContext = jest.fn(() => canvasCtx);
    container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container);
  });
  afterEach(() => { act(() => root.unmount()); container.remove(); });

  it('places safe-zone, spawn warning, and BossHUD in one notification stack', () => {
    act(() => root.render(<HUD state={state} ping={0} engine={{ current: { metrics: {} } }} onSettings={noop} onLeaderboard={noop} onRespawn={noop} onLeave={noop} muted={false} toggleMuted={noop} onBossMap={noop} onInventory={noop} onUseHeal={noop} onStats={noop} onCraft={noop} onAlliance={noop} onMarket={noop} bossHud={<BossHUD state={state} selected="boss-1" openMap={noop} />} />));
    const stack = container.querySelector('[data-testid="hud-notification-stack"]');
    expect(stack).not.toBeNull();
    expect(stack.querySelector('[data-testid="status-effects"]')).not.toBeNull();
    expect(stack.querySelector('[data-testid="safe-zone-notice"]')).not.toBeNull();
    expect(stack.querySelector('[data-testid="spawn-protection"]')).not.toBeNull();
    expect(stack.querySelector('[data-testid="boss-hud"]')).not.toBeNull();
    expect([...stack.children].map(node => node.className)).toEqual(expect.arrayContaining(['spawn-protection safe-zone-notice', 'spawn-protection', 'boss-hud']));
  });

  it('shows only owned death alerts and two distinct right-side recovery clocks', () => {
    const recovering = { ...state, events: [{ type: 'soldier_down', owner: 'me', soldier_id: 's1', name: 'Recruit S1' }, { type: 'soldier_down', owner: 'other', soldier_id: 'hidden', name: 'Hidden' }], me: { ...state.me, soldiers: [{ id: 's1', name: 'Recruit S1', tier_id: 'soldier_s1', status: 'recovering', recovery_time: 120 }, { id: 's2', name: 'Operator S4', tier_id: 'soldier_s4', status: 'recovering', recovery_time: 65 }] } };
    act(() => root.render(<HUD state={recovering} ping={0} engine={{ current: { metrics: {} } }} onSettings={noop} onLeaderboard={noop} onRespawn={noop} onLeave={noop} muted={false} toggleMuted={noop} onBossMap={noop} onInventory={noop} onUseHeal={noop} onStats={noop} onCraft={noop} onAlliance={noop} onMarket={noop} />));
    expect(container.querySelector('[data-testid="soldier-down-s1"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="soldier-down-hidden"]')).toBeNull();
    expect(container.querySelector('[data-testid="companion-recovery-s1"]').textContent).toContain('02:00');
    expect(container.querySelector('[data-testid="companion-recovery-s2"]').textContent).toContain('01:05');
  });

  it('keeps the mounted minimap RAF alive across 20 Hz snapshot updates', () => {
    const props = { ping: 0, engine: { current: { metrics: {}, minimapPose: { x: 0, z: 0, heading: Math.PI - .04 }, nearby: [{ houses: [{ x: 12, z: 6, w: 10, d: 8, enterable: true, door: { x: 12, z: 2 } }] }] } }, onSettings: noop, onLeaderboard: noop, onRespawn: noop, onLeave: noop, muted: false, toggleMuted: noop, onBossMap: noop, onInventory: noop, onUseHeal: noop, onStats: noop, onCraft: noop, onAlliance: noop, onMarket: noop };
    act(() => root.render(<HUD {...props} state={state} />));
    expect(raf).toHaveBeenCalledTimes(1);
    const next = { ...state, me: { ...state.me, x: 1, z: 0 } };
    props.engine.current.minimapPose.heading = -Math.PI + .04;
    act(() => root.render(<HUD {...props} state={next} />));
    expect(raf).toHaveBeenCalledTimes(1);
    act(() => raf.mock.calls[0][0](1000));
    expect(raf).toHaveBeenCalledTimes(2);
  });

  it('draws world-grid roads relative to the moving player instead of pinning a cross to the radar', () => {
    const props = { ping: 0, engine: { current: { metrics: {} } }, onSettings: noop, onLeaderboard: noop, onRespawn: noop, onLeave: noop, muted: false, toggleMuted: noop, onBossMap: noop, onInventory: noop, onUseHeal: noop, onStats: noop, onCraft: noop, onAlliance: noop, onMarket: noop };
    act(() => root.render(<HUD {...props} state={state} />));
    act(() => raf.mock.calls[0][0](1000));
    const firstRoadStart = canvasCtx.moveTo.mock.calls[0][0];
    canvasCtx.moveTo.mockClear();
    act(() => root.render(<HUD {...props} state={{ ...state, me: { ...state.me, x: 10 } }} />));
    act(() => raf.mock.calls[1][0](1050));
    expect(canvasCtx.moveTo.mock.calls[0][0]).not.toBeCloseTo(firstRoadStart);
  });
});
