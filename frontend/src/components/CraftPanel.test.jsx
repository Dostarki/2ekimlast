import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { CraftPanel, WEAPON_RECIPES } from './CraftPanel';

jest.mock('../game/weaponPreviews', () => ({ getWeaponPreviews: () => ({}) }));
jest.mock('./ui/dialog', () => {
  const React = require('react');
  return { Dialog: ({ children }) => children, DialogContent: ({ children, ...props }) => React.createElement('div', props, children), DialogTitle: ({ children, ...props }) => React.createElement('h2', props, children), DialogDescription: ({ children, ...props }) => React.createElement('p', props, children) };
});

const weaponParts = ['barrel_common', 'stock_common', 'grip_common', 'spring_common', 'receiver_uncommon', 'barrel_uncommon', 'grip_uncommon', 'stock_uncommon', 'barrel_rare', 'receiver_rare', 'optic_rare', 'suppressor_rare'].flatMap(id => [{ id }, { id }, { id }]);
const equipmentParts = Object.fromEntries(['fabric', 'plate', 'binding', 'mechanism'].flatMap(family => [1, 2, 3].map(tier => [`${family}_t${tier}`, 99])));
const makeState = (overrides = {}) => ({ me: { weapon: 'glock18', hp: 100, gold: 99999, level: 50, inventory: { glock18: true }, weapon_parts: weaponParts, owned_equipment: ['vest_t1'], equipment_levels: { vest_t1: 0 }, equipment_parts: { ...equipmentParts }, calibration: { calibration_t1: 9, calibration_t2: 9, calibration_t3: 9 }, ...overrides } });

describe('CraftPanel selected workshop actions', () => {
  let container, root, callbacks;
  const render = state => act(() => root.render(<CraftPanel open onOpenChange={jest.fn()} state={state} {...callbacks} />));
  const click = selector => act(() => container.querySelector(selector).click());
  const heroAction = testId => container.querySelector(`[data-testid="${testId}"] .workshop-hero-cta`);
  beforeEach(() => { global.IS_REACT_ACT_ENVIRONMENT = true; jest.useFakeTimers(); callbacks = { craft: jest.fn(), equipmentCraft: jest.fn(), equipmentUpgrade: jest.fn(), convertMaterial: jest.fn() }; container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); });
  afterEach(() => { act(() => root.unmount()); container.remove(); jest.useRealTimers(); });

  it('keeps catalogues selection-only and dispatches each of the five hero actions', () => {
    render(makeState());
    expect(container.querySelectorAll('.catalogue-card button')).toHaveLength(0);
    click('[data-testid="craft-selected-hero"] .workshop-hero-cta'); expect(callbacks.craft).toHaveBeenCalledWith('craft_weapon_shotgun', 'shotgun');
    act(() => jest.runOnlyPendingTimers()); click('[data-testid="craft-tab-upgrades"]'); click('[data-testid="weapon-mod-selected-hero"] .workshop-hero-cta'); expect(callbacks.craft).toHaveBeenLastCalledWith('upgrade_damage_t1', 'glock18');
    act(() => jest.runOnlyPendingTimers()); click('[data-testid="craft-tab-equipment"]'); click('[data-testid="equipment-selected-hero"] .workshop-hero-cta'); expect(callbacks.equipmentCraft).toHaveBeenCalledWith('helm_t1');
    act(() => jest.runOnlyPendingTimers()); click('[data-testid="craft-tab-equipment-upgrade"]'); click('[data-testid="equipment-upgrade-selected-hero"] .workshop-hero-cta'); expect(callbacks.equipmentUpgrade).toHaveBeenCalledWith('vest_t1');
    act(() => jest.runOnlyPendingTimers()); click('[data-testid="craft-tab-convert"]'); click('[data-testid="conversion-selected-hero"] .workshop-hero-cta'); expect(callbacks.convertMaterial).toHaveBeenCalledWith('fabric_t1', 'fabric_t2');
  });

  it('shows illustrated requirements and blocks the only available action when materials are absent', () => {
    render(makeState({ weapon_parts: [], equipment_parts: {}, calibration: {} }));
    expect(container.querySelector('svg[aria-label="Barrel (Common) thumbnail"]')).not.toBeNull(); expect(heroAction('craft-selected-hero').disabled).toBe(true);
    click('[data-testid="craft-tab-equipment"]'); expect(container.querySelector('svg[aria-label="Ballistic Fabric thumbnail"]')).not.toBeNull(); expect(heroAction('equipment-selected-hero').disabled).toBe(true);
  });

  it('renders compact weapon catalogue cards with keyboard selection', () => {
    render(makeState()); const card = container.querySelector(`[data-testid="craft-card-${WEAPON_RECIPES[0].id}"]`);
    act(() => card.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))); expect(card.className).toContain('selected');
  });

  it('ignores unknown or stale owned equipment ids and never dispatches them', () => {
    render(makeState({ owned_equipment: ['removed_item', 'vest_t1'], equipment_levels: { removed_item: 2, vest_t1: 0 } }));
    click('[data-testid="craft-tab-equipment-upgrade"]');
    expect(container.querySelector('[data-testid="equipment-upgrade-selected-hero"]').textContent).toContain('Light Assault Vest');
    click('[data-testid="equipment-upgrade-selected-hero"] .workshop-hero-cta');
    expect(callbacks.equipmentUpgrade).toHaveBeenCalledWith('vest_t1');
  });

  it('shows the empty equipment-upgrade state when every owned id is stale', () => {
    render(makeState({ owned_equipment: ['removed_item'], equipment_levels: { removed_item: 2 } }));
    click('[data-testid="craft-tab-equipment-upgrade"]');
    expect(container.querySelector('[data-testid="equipment-upgrade-selected-hero"]')).toBeNull();
    expect(container.textContent).toContain('No equipment owned yet');
  });
});
