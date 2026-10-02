import React, { act } from 'react';
import { createRoot } from 'react-dom/client';
import { OffgameMarketModal } from './OffgameMarketModal';
import { apiClient } from '../lib/apiClient';
import { useAuth } from '../lib/authContext';
import { useAccount, useSendTransaction } from 'wagmi';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock('../lib/apiClient', () => ({ apiClient: { get: jest.fn(), post: jest.fn() } }));
jest.mock('../lib/authContext', () => ({ useAuth: jest.fn() }));
jest.mock('wagmi', () => ({ useAccount: jest.fn(), useSendTransaction: jest.fn(), useSwitchChain: () => ({ switchChain: jest.fn() }) }));
jest.mock('@rainbow-me/rainbowkit', () => ({ useConnectModal: () => ({ openConnectModal: jest.fn() }) }));
jest.mock('sonner', () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock('./ui/dialog', () => ({ Dialog: ({ children }) => children, DialogContent: ({ children, ...props }) => <div {...props}>{children}</div>, DialogTitle: ({ children }) => <h2>{children}</h2> }));
jest.mock('./CraftPanel', () => ({ MaterialThumbnail: () => <svg aria-hidden="true" /> }));
jest.mock('./EquipmentThumbnail', () => ({ EquipmentThumbnail: () => <svg aria-hidden="true" /> }));

const catalog = {
  pack_field: { sku: 'pack_field', name: 'field', usd_str: '$2', cents: 200, gold: 1000, guaranteed_items: { medkit: 1 }, equipment_materials: { fabric_t1: 2 }, weapon_parts: {}, guaranteed_equipment: {}, description: 'old', badge: 'x' },
  pack_supply: { sku: 'pack_supply', name: 'supply', usd_str: '$4', gold: 2000, guaranteed_items: {}, equipment_materials: {}, weapon_parts: {}, guaranteed_equipment: {} },
  pack_operator: { sku: 'pack_operator', name: 'operator', usd_str: '$6', gold: 3500, guaranteed_items: {}, equipment_materials: {}, weapon_parts: {}, guaranteed_equipment: {} },
  pack_outpost: { sku: 'pack_outpost', name: 'outpost', usd_str: '$10', gold: 6000, guaranteed_items: {}, equipment_materials: {}, weapon_parts: {}, guaranteed_equipment: {} },
  equipment_luck_2: { sku: 'equipment_luck_2', name: 'box', usd_str: '$2', gold: 1000 },
  vip_30d: { sku: 'vip_30d', name: 'vip', usd_str: '$5', gold: 0, perks: ['fake preset'] },
};
const quote = { quote_id: 'q1', chain_id: 4663, recipient: '0x3254Aea793e13b54Ad3fD2F235BC8F5a9b47a14E', amount_wei: '1000000000000000', usd_per_eth: '2000', calldata: '4c617374', expires_at: '2099-01-01T00:00:00+00:00' };
const order = { order_id: 'o1', sku: 'pack_field', sku_name: 'old', cents: 200, status: 'awaiting_payment', quote, manifest: { gold: 1000 } };

describe('OffgameMarketModal account and payment states', () => {
  let host, root, sendTransactionAsync;
  const render = async (auth, wallet, tab = 'packages') => {
    useAuth.mockReturnValue(auth);
    useAccount.mockReturnValue({ isConnected: true, chainId: 4663, address: '0xabc', ...wallet });
    await act(async () => root.render(<OffgameMarketModal open onClose={jest.fn()} />));
  };
  beforeEach(() => {
    host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host);
    sendTransactionAsync = jest.fn(); useSendTransaction.mockReturnValue({ sendTransactionAsync });
    apiClient.get.mockImplementation(async (path) => {
      if (path === '/offgame-market/catalog') return { data: { catalog, capabilities: { purchase_enabled: true }, luck_box_odds: [] } };
      if (path === '/account/economy') return { data: { gold: 10, vip: { is_vip: false } } };
      if (path === '/offgame-market/orders') return { data: { orders: [] } };
      return { data: { missions: [], inbox: [], soldiers: [] } };
    });
    apiClient.post.mockReset();
    localStorage.clear();
  });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); jest.clearAllMocks(); });

  it('keeps catalog public while showing a clear sign-in state and disabling checkout', async () => {
    await render({ status: 'unauthenticated', user: null, loginWithWallet: jest.fn() }, { address: '0xabc', chainId: 4663, isConnected: true });
    expect(host.textContent).toContain('Field Package');
    expect(host.textContent).toContain('Sign in to view your account');
    expect(apiClient.get).toHaveBeenCalledWith('/offgame-market/catalog');
    expect(apiClient.get).not.toHaveBeenCalledWith('/account/economy');
    expect(host.querySelector('.ogm-package-detail .ogm-buy-btn').disabled).toBe(true);
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('blocks purchase when the connected wallet differs from the authenticated account', async () => {
    await render({ status: 'authenticated', user: { address: '0xabc' } }, { address: '0xdef', chainId: 4663 });
    expect(host.textContent).toContain('differs from the signed-in account');
    expect(host.querySelector('.ogm-package-detail .ogm-buy-btn').disabled).toBe(true);
  });

  it('requires a separate review and wallet approval after the server creates a quote', async () => {
    apiClient.post.mockResolvedValue({ data: { order } });
    await render({ status: 'authenticated', user: { address: '0xabc' } }, { address: '0xabc', chainId: 4663 });
    const review = host.querySelector('.ogm-package-detail .ogm-buy-btn');
    await act(async () => review.dispatchEvent(new MouseEvent('click', { bubbles: true })));
    expect(apiClient.post).toHaveBeenCalledWith('/offgame-market/orders', expect.objectContaining({ sku: 'pack_field' }));
    expect(sendTransactionAsync).not.toHaveBeenCalled();
    expect(host.textContent).toContain('0.001 ETH');
    expect(host.textContent).toContain('Approve payment in wallet');
  });

  it('rechecks an existing transaction from history without sending a second transfer', async () => {
    apiClient.get.mockImplementation(async (path) => {
      if (path === '/offgame-market/catalog') return { data: { catalog, capabilities: { purchase_enabled: true }, luck_box_odds: [] } };
      if (path === '/account/economy') return { data: { gold: 10, vip: { is_vip: false } } };
      if (path === '/offgame-market/orders') return { data: { orders: [{ ...order, status: 'submitted', tx_hash: `0x${'a'.repeat(64)}` }] } };
      return { data: { missions: [], inbox: [], soldiers: [] } };
    });
    apiClient.post.mockResolvedValue({ data: { order: { ...order, status: 'fulfilled' } } });
    await render({ status: 'authenticated', user: { address: '0xabc' } }, { address: '0xabc', chainId: 4663 });
    await act(async () => host.querySelector('[class*="ogm-tab-btn"]:nth-of-type(6)').dispatchEvent(new MouseEvent('click', { bubbles: true })));
    const verify = [...host.querySelectorAll('button')].find((button) => button.textContent.includes('Verify payment'));
    expect(verify).toBeTruthy();
    await act(async () => verify.dispatchEvent(new MouseEvent('click', { bubbles: true })));
    await act(async () => host.querySelector('.ogm-checkout-confirm .ogm-buy-btn').dispatchEvent(new MouseEvent('click', { bubbles: true })));
    expect(apiClient.post).toHaveBeenCalledWith('/offgame-market/orders/o1/submit', { tx_hash: `0x${'a'.repeat(64)}` });
    expect(sendTransactionAsync).not.toHaveBeenCalled();
  });

  it('blocks wallet approval when quote chain mismatches Robinhood mainnet guard', async () => {
    const wrongChainOrder = { ...order, quote: { ...quote, chain_id: 1 }, status: 'awaiting_payment' };
    apiClient.post.mockResolvedValue({ data: { order: wrongChainOrder } });
    await render({ status: 'authenticated', user: { address: '0xabc' } }, { address: '0xabc', chainId: 4663 });
    const review = host.querySelector('.ogm-package-detail .ogm-buy-btn');
    await act(async () => review.dispatchEvent(new MouseEvent('click', { bubbles: true })));
    await act(async () => host.querySelector('.ogm-checkout-confirm .ogm-buy-btn').dispatchEvent(new MouseEvent('click', { bubbles: true })));
    expect(sendTransactionAsync).not.toHaveBeenCalled();
    expect(host.textContent).toContain('Wallet account or network changed. Reconnect the signed-in account and try again.');
  });

  it('keeps a wallet-submitted hash across reload after a temporary verification failure', async () => {
    const txHash = `0x${'b'.repeat(64)}`;
    const secondTxHash = `0x${'c'.repeat(64)}`;
    const auth = { status: 'authenticated', user: { address: '0xabc' } };
    const wallet = { address: '0xabc', chainId: 4663 };
    apiClient.get.mockImplementation(async (path) => {
      if (path === '/offgame-market/catalog') return { data: { catalog, capabilities: { purchase_enabled: true }, luck_box_odds: [] } };
      if (path === '/account/economy') return { data: { gold: 10, vip: { is_vip: false } } };
      if (path === '/offgame-market/orders') return { data: { orders: [{ ...order, status: 'awaiting_payment' }, { ...order, order_id: 'o2', status: 'submitted' }] } };
      return { data: { missions: [], inbox: [], soldiers: [] } };
    });
    sendTransactionAsync.mockResolvedValue(txHash);
    apiClient.post.mockRejectedValueOnce({ response: { status: 503, data: { detail: 'PAYMENT_VERIFICATION_UNAVAILABLE' } } });
    localStorage.setItem('dz_market_pending_0xabc', JSON.stringify({ orders: { o2: secondTxHash } }));

    await render(auth, wallet);
    await act(async () => host.querySelector('[class*="ogm-tab-btn"]:nth-of-type(6)').dispatchEvent(new MouseEvent('click', { bubbles: true })));
    await act(async () => [...host.querySelectorAll('button')].find((button) => button.textContent.includes('Continue checkout')).dispatchEvent(new MouseEvent('click', { bubbles: true })));
    await act(async () => host.querySelector('.ogm-checkout-confirm .ogm-buy-btn').dispatchEvent(new MouseEvent('click', { bubbles: true })));
    expect(apiClient.post).toHaveBeenCalledWith('/offgame-market/orders/o1/submit', { tx_hash: txHash });
    expect(sendTransactionAsync).toHaveBeenCalledTimes(1);
    expect(JSON.parse(localStorage.getItem('dz_market_pending_0xabc'))).toEqual({ orders: { o1: txHash, o2: secondTxHash } });

    await act(async () => root.unmount());
    host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host);
    apiClient.post.mockRejectedValue({ response: { status: 503, data: { detail: 'PAYMENT_VERIFICATION_UNAVAILABLE' } } });
    await render(auth, wallet);
    await act(async () => host.querySelector('[class*="ogm-tab-btn"]:nth-of-type(6)').dispatchEvent(new MouseEvent('click', { bubbles: true })));
    await act(async () => [...host.querySelectorAll('button')].find((button) => button.textContent.includes('Verify payment')).dispatchEvent(new MouseEvent('click', { bubbles: true })));
    expect(host.textContent).toContain('Verify payment');
    expect(host.textContent).toContain('An existing transaction is attached. Verify it; do not send a second payment.');
    expect(sendTransactionAsync).toHaveBeenCalledTimes(1);
  });
});
