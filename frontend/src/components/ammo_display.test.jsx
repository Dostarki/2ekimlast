import { act } from 'react';
import { createRoot } from 'react-dom/client';
import React from 'react';
import { HUD } from './HUD';
import { Inventory } from './Inventory';

// TEST-ONLY MOCKS: keep rendering focused on ammo display semantics.
jest.mock('./Lobby', () => ({ WEAPONS: [{ id: 'glock18', name: 'Glock 18', type: 'AUTOMATIC' }] }));
jest.mock('./StatusEffects', () => ({ StatusEffects: () => <div data-testid="status-effects" /> }));
jest.mock('../game/bossMinimap', () => ({ drawBossMarkers: jest.fn() }));
jest.mock('../game/minimap', () => ({ minimapTransform: () => ({ x: 0, y: 0 }), smoothAngle: (a) => a }));
jest.mock('./ConnectionStats', () => ({ ConnectionStats: () => null }));
jest.mock('./DeathPanel', () => ({ DeathPanel: () => null }));
jest.mock('../game/weaponPreviews', () => ({ getWeaponPreviews: () => ({ glock18: 'g.png', ak47: 'a.png' }) }));
jest.mock('./ActionProgress', () => ({ ActionProgress: () => null }));
jest.mock('../game/damage', () => ({ formatDamage: v => String(v) }));
jest.mock('./ui/dialog', () => {
  const React = require('react');
  return {
    Dialog: ({ children }) => <>{children}</>,
    DialogContent: ({ children, ...props }) => React.createElement('div', props, children),
    DialogTitle: ({ children, ...props }) => React.createElement('h2', props, children),
    DialogDescription: ({ children }) => <p>{children}</p>,
  };
});

const noop = () => {};

describe('HUD/Inventory reserve display', () => {
  let container;
  let root;

  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    HTMLCanvasElement.prototype.getContext = jest.fn(() => ({
      clearRect: jest.fn(), fillRect: jest.fn(), fillText: jest.fn(), save: jest.fn(), restore: jest.fn(),
      beginPath: jest.fn(), arc: jest.fn(), fill: jest.fn(), stroke: jest.fn(), moveTo: jest.fn(),
      lineTo: jest.fn(), closePath: jest.fn(), clip: jest.fn(),
    }));
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('HUD reserve shows infinity for flagged Glock18', () => {
    const state = {
      players: [], zombies: [], events: [], online: 1,
      me: {
        id: 'me', name: 'Tester', x: 0, z: 0, hp: 100, max_hp: 100,
        stamina: 100, weapon: 'glock18', ammo: 7, reserve: 0, infinite_reserve: true,
        score: 0, kills: 0, pvp: 0, level: 1, xp_needed: 1, xp_progress: 0,
        statuses: {}, safe_zone: false, protected: 0, awaiting_input: false,
        heal_items: {}, equipped_equipment: {}, soldiers: [], reloading: 0,
      },
    };

    act(() => root.render(
      <HUD
        state={state}
        ping={0}
        engine={{ current: { keys: {}, requestReload: noop, publishInput: noop, metrics: {} } }}
        onSettings={noop}
        onLeaderboard={noop}
        onRespawn={noop}
        onLeave={noop}
        muted={false}
        toggleMuted={noop}
        onBossMap={noop}
        onInventory={noop}
        onUseHeal={noop}
        onStats={noop}
        onCraft={noop}
        onAlliance={noop}
        onMarket={noop}
      />
    ));

    expect(container.querySelector('[data-testid="hud-reserve-count"]').textContent).toContain('∞');
  });

  it('Inventory ammo line shows ∞ for Glock and numeric reserve for AK47', () => {
    const state = {
      me: {
        hp: 100,
        weapon: 'glock18',
        inventory: {
          glock18: { ammo: 17, reserve: 0, infinite_reserve: true },
          ak47: { ammo: 30, reserve: 90, infinite_reserve: false },
        },
        equipped_equipment: {},
        owned_equipment: [],
        equipment_levels: {},
        equipment_stats: {},
        equipment_parts: {},
        calibration: {},
        weapon_parts: [],
        heal_items: {},
        consumables: {},
        gold: 0,
      },
    };

    act(() => root.render(
      <Inventory
        open
        onOpenChange={noop}
        state={state}
        equip={noop}
        weaponSlots={{}}
        setWeaponSlot={noop}
        equipmentEquip={noop}
        consumeEnergy={noop}
      />
    ));

    expect(container.querySelector('[data-testid="inventory-ammo-glock18"]').textContent).toContain('17 / ∞');
    expect(container.querySelector('[data-testid="inventory-ammo-ak47"]').textContent).toContain('30 / 90');
  });
});
