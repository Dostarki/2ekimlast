import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MarketPanel } from './MarketPanel';

jest.mock('./ui/dialog', () => {
  const React = require('react');
  return {
    Dialog: ({ children }) => children,
    DialogContent: ({ children, ...props }) => React.createElement('div', props, children),
    DialogTitle: ({ children, ...props }) => React.createElement('h2', props, children),
    DialogDescription: ({ children, ...props }) => React.createElement('p', props, children),
  };
});

const roster = [1, 1, 1, 1, 4].map((tier, index) => ({
  instance_id: `soldier-instance-${index + 1}`,
  tier_id: `soldier_s${tier}`,
  active: index !== 1,
}));

function state({ gold = 2000, level = 40 } = {}) {
  return { me: {
    gold, level, owned_soldiers: roster, active_soldier_ids: roster.filter(s => s.active).map(s => s.instance_id),
    equipment_parts: {}, calibration: {}, weapon_parts: [], owned_equipment: [], equipment_levels: {}, heal_items: {}, inventory: {},
  }};
}

describe('MarketPanel individual soldiers', () => {
  let container; let root; let props;
  beforeEach(() => {
    global.IS_REACT_ACT_ENVIRONMENT = true;
    container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container);
    props = { open: true, onOpenChange: jest.fn(), state: state(), soldierBuy: jest.fn(), soldierActivate: jest.fn(), soldierDeactivate: jest.fn(), soldierUpgrade: jest.fn(), soldierRename: jest.fn(), sellItem: jest.fn() };
  });
  afterEach(() => { act(() => root.unmount()); container.remove(); });
  const render = () => act(() => root.render(<MarketPanel {...props} />));
  const card = id => container.querySelector(`[data-testid="soldier-card-${id}"]`);

  it('renders five same-tier instances and capacity without another recruit control', () => {
    render();
    expect(container.querySelectorAll('[data-testid^="soldier-card-"]')).toHaveLength(5);
    expect(container.textContent).toContain('ROSTER CAPACITY FULL (5/5)');
    expect([...container.querySelectorAll('button')].some(button => button.textContent.includes('RECRUIT MERCENARY'))).toBe(false);
  });

  it('sends the selected instance ID for upgrade', () => {
    render();
    const specific = card('soldier-instance-2');
    act(() => [...specific.querySelectorAll('button')].find(button => button.textContent.includes('UPGRADE')).click());
    expect(props.soldierUpgrade).toHaveBeenCalledWith('soldier-instance-2');
  });

  it('sends the selected instance ID for deactivation', () => {
    render();
    const active = card('soldier-instance-1');
    act(() => [...active.querySelectorAll('button')].find(button => button.textContent.includes('RECALL')).click());
    expect(props.soldierDeactivate).toHaveBeenCalledWith('soldier-instance-1');
  });

  it('uses next-tier S4 upgrade price/level rather than the old S4 purchase price', () => {
    render();
    const upgrade = [...card('soldier-instance-5').querySelectorAll('button')].find(button => button.textContent.includes('UPGRADE'));
    expect(upgrade.disabled).toBe(false);
    props = { ...props, state: state({ gold: 2000, level: 30 }) }; render();
    expect([...card('soldier-instance-5').querySelectorAll('button')].find(button => button.textContent.includes('UPGRADE')).disabled).toBe(true);
  });

  it('edits and saves an individual nickname using its stable instance ID', () => {
    render();
    const id = 'soldier-instance-2';
    act(() => card(id).querySelector(`[data-testid="soldier-rename-${id}"]`).click());
    const input = card(id).querySelector(`[data-testid="soldier-nickname-input-${id}"]`);
    act(() => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(input, 'Nova'); input.dispatchEvent(new Event('input', { bubbles: true })); });
    act(() => [...card(id).querySelectorAll('button')].find(button => button.getAttribute('aria-label') === 'Save mercenary name').click());
    expect(props.soldierRename).toHaveBeenCalledWith(id, 'Nova');
  });
});
