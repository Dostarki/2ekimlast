import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { PREFERENCES_KEY } from './game/preferences';
import App, { GameApp } from './App';

jest.mock('react-router-dom', () => ({ BrowserRouter: ({ children }) => children, useLocation: jest.fn(() => ({ pathname: '/settings' })), useNavigate: () => jest.fn() }), { virtual: true });
jest.mock('./components/DocsPage', () => () => <div data-testid="public-guide" />);
jest.mock('@rainbow-me/rainbowkit', () => ({
  useConnectModal: () => ({ connectModalOpen: false }),
  useAccountModal: () => ({ accountModalOpen: false }),
  useChainModal: () => ({ chainModalOpen: false }),
}));

const rendererInstances = [];
jest.mock('./game/renderer', () => ({ GameRenderer: jest.fn().mockImplementation(function GameRenderer(container, world, error, onZoomChange) { const instance = { setQuality: jest.fn(), setZoom: jest.fn(), setMode: jest.fn(), setBlocked: jest.fn(), dispose: jest.fn(), onZoomChange }; rendererInstances.push(instance); return instance; }) }));
jest.mock('./game/audio', () => ({ audio: { preload: jest.fn().mockResolvedValue(undefined), sync: jest.fn(), stopAutomatic: jest.fn(), stopEnemies: jest.fn(), enabled: true, volume: .35 } }));
jest.mock('./hooks/useSession', () => ({ API: '/api', useSession: () => ({ mode: 'lobby', state: null, ping: null, error: '', start: jest.fn(), leave: jest.fn(), respawn: jest.fn(), equip: jest.fn(), onUseHeal: jest.fn(), useConsumable: jest.fn(), allocateStat: jest.fn(), craft: jest.fn(), equipmentCraft: jest.fn(), equipmentUpgrade: jest.fn(), equipmentEquip: jest.fn(), convertMaterial: jest.fn(), soldierBuy: jest.fn(), soldierActivate: jest.fn(), soldierDeactivate: jest.fn(), soldierUpgrade: jest.fn(), soldierRename: jest.fn(), sellItem: jest.fn(), allianceCreate: jest.fn(), allianceJoin: jest.fn(), allianceLeave: jest.fn(), allianceFriendlyFire: jest.fn() }) }));
jest.mock('./components/Lobby', () => ({ Lobby: () => <div /> }));
jest.mock('./components/HUD', () => ({ HUD: () => <div /> }));
jest.mock('./components/BossMap', () => ({ BossMap: () => <div /> }));
jest.mock('./components/BossHUD', () => ({ BossHUD: () => <div /> }));
jest.mock('./components/StartScreen', () => ({ StartScreen: () => <div /> }));
jest.mock('./components/AdminPage', () => () => <div />);
jest.mock('./components/Inventory', () => ({ Inventory: () => <div /> }));
jest.mock('./components/StatsPanel', () => ({ StatsPanel: () => <div /> }));
jest.mock('./components/CraftPanel', () => ({ CraftPanel: () => <div /> }));
jest.mock('./components/RadialMenu', () => ({ RadialMenu: () => <div /> }));
jest.mock('./components/AlliancePanel', () => ({ AlliancePanel: () => <div /> }));
jest.mock('./components/MarketPanel', () => ({ MarketPanel: () => <div /> }));
jest.mock('./components/WalletGate', () => ({ WalletGate: () => <div /> }));
jest.mock('./components/ui/sonner', () => ({ Toaster: () => null }));
jest.mock('./components/ui/button', () => ({ Button: ({ children, ...props }) => <button {...props}>{children}</button> }));
jest.mock('./components/ui/dialog', () => { const React = require('react'); return { Dialog: ({ children }) => children, DialogContent: ({ children, ...props }) => React.createElement('div', props, children), DialogHeader: ({ children }) => <div>{children}</div>, DialogTitle: ({ children, ...props }) => React.createElement('h2', props, children), DialogDescription: ({ children, ...props }) => React.createElement('p', props, children) }; });

const { GameRenderer } = require('./game/renderer');
const { audio } = require('./game/audio');
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });

describe('GameApp settings persistence', () => {
  let container, root, fetchMock;
  const mount = () => act(() => root.render(<GameApp />));
  beforeEach(() => { require('react-router-dom').useLocation.mockReturnValue({ pathname: '/settings' }); });
  beforeEach(() => { global.IS_REACT_ACT_ENVIRONMENT = true; rendererInstances.length = 0; GameRenderer.mockImplementation(function GameRendererMock(container, world, error, onZoomChange) { const instance = { setQuality: jest.fn(), setZoom: jest.fn(), setMode: jest.fn(), setBlocked: jest.fn(), dispose: jest.fn(), onZoomChange }; rendererInstances.push(instance); return instance; }); audio.preload.mockResolvedValue(undefined); audio.sync.mockClear(); localStorage.clear(); container = document.createElement('div'); document.body.appendChild(container); root = createRoot(container); fetchMock = jest.fn(url => Promise.resolve({ ok: true, json: () => Promise.resolve(url.includes('/world') ? { seed: 1 } : { online: 0 }) })); global.fetch = fetchMock; });
  afterEach(() => { act(() => root.unmount()); container.remove(); });

  it('routes public docs without starting the game renderer, world requests or audio preload', async () => {
    const { useLocation } = require('react-router-dom');
    useLocation.mockReturnValue({ pathname: '/docs' });
    GameRenderer.mockClear(); audio.preload.mockClear();
    await act(async () => root.render(<App />));
    expect(container.querySelector('[data-testid="public-guide"]')).not.toBeNull();
    expect(GameRenderer).not.toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(audio.preload).not.toHaveBeenCalled();
    useLocation.mockReturnValue({ pathname: '/settings' });
  });

  it('persists real settings controls, reapplies them on remount, and ignores a stale world response', async () => {
    let resolveWorld;
    global.fetch = jest.fn(url => url.includes('/world') ? new Promise(resolve => { resolveWorld = resolve; }) : Promise.resolve({ ok: true, json: () => Promise.resolve({ online: 0 }) }));
    mount(); act(() => root.unmount()); await act(async () => resolveWorld({ ok: true, json: () => Promise.resolve({ seed: 1 }) }));
    expect(GameRenderer).not.toHaveBeenCalled();

    root = createRoot(container); global.fetch = fetchMock; mount(); await flush();
    const volume = container.querySelector('[data-testid="settings-volume"]'); const zoom = container.querySelector('[data-testid="settings-zoom"]');
    act(() => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(volume, '0'); volume.dispatchEvent(new Event('input', { bubbles: true })); container.querySelector('[data-testid="settings-sound-toggle"]').click(); container.querySelector('[data-testid="quality-performance"]').click(); Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(zoom, '18'); zoom.dispatchEvent(new Event('input', { bubbles: true })); });
    await flush();
    expect(JSON.parse(localStorage.getItem(PREFERENCES_KEY))).toEqual(expect.objectContaining({ muted: true, volume: 0, quality: 'low', zoom: 18 }));
    expect(rendererInstances[0].setQuality).toHaveBeenCalledWith('low'); expect(rendererInstances[0].setZoom).toHaveBeenCalledWith(18); expect(audio).toEqual(expect.objectContaining({ enabled: false, volume: 0 }));
    act(() => root.unmount()); root = createRoot(container); mount(); await flush();
    expect(container.querySelector('[data-testid="settings-volume"]').value).toBe('0'); expect(container.querySelector('[data-testid="settings-zoom"]').value).toBe('18'); expect(container.querySelector('[data-testid="quality-performance"]').className).toContain('active'); expect(container.querySelector('[data-testid="settings-sound-toggle"]').getAttribute('aria-checked')).toBe('false');
    expect(rendererInstances.at(-1).setQuality).toHaveBeenCalledWith('low'); expect(rendererInstances.at(-1).setZoom).toHaveBeenCalledWith(18);
    act(() => rendererInstances.at(-1).onZoomChange(23)); await flush(); expect(container.querySelector('[data-testid="settings-zoom"]').value).toBe('23');
  });
});
