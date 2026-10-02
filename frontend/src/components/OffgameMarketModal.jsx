import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  X,
  Package,
  Crown,
  Clock,
  Inbox,
  History,
  Coins,
  CheckCircle2,
  Sparkles,
  ChevronRight,
  Zap,
  HeartPulse,
} from 'lucide-react';
import { toast } from 'sonner';
import { apiClient } from '../lib/apiClient';
import { useAuth } from '../lib/authContext';
import { useAccount, useSwitchChain } from 'wagmi';
import { useNativePayment } from '../hooks/useNativePayment';
import { useConnectModal } from '@rainbow-me/rainbowkit';
import { Dialog, DialogContent, DialogTitle } from './ui/dialog';
import { MaterialThumbnail } from './CraftPanel';
import { EQUIPMENT_CATALOG, CRAFT_MATERIALS } from '../game/equipmentConfig';
import { EquipmentThumbnail } from './EquipmentThumbnail';
import './OffgameMarketModal.css';

const formatDuration = (milliseconds) => {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000));
  const hours = Math.floor(seconds / 3600), minutes = Math.floor((seconds % 3600) / 60), remain = seconds % 60;
  return `${hours}h ${minutes}m ${remain}s remaining`;
};
const pendingStorageKey = (accountKey) => `dz_market_pending_${accountKey}`;
const readPendingOrders = (accountKey) => {
  if (!accountKey) return {};
  try {
    const stored = JSON.parse(localStorage.getItem(pendingStorageKey(accountKey)) || 'null');
    if (stored?.orders && typeof stored.orders === 'object') return stored.orders;
    // Migrate the original single-order shape without dropping its submitted hash.
    return stored?.order_id && stored?.tx_hash ? { [stored.order_id]: stored.tx_hash } : {};
  } catch { return {}; }
};
const savePendingOrder = (accountKey, orderId, txHash) => {
  if (!accountKey || !orderId || !txHash) return;
  const orders = readPendingOrders(accountKey);
  orders[orderId] = txHash;
  localStorage.setItem(pendingStorageKey(accountKey), JSON.stringify({ orders }));
};
const removePendingOrder = (accountKey, orderId) => {
  if (!accountKey) return;
  const orders = readPendingOrders(accountKey);
  delete orders[orderId];
  if (Object.keys(orders).length) localStorage.setItem(pendingStorageKey(accountKey), JSON.stringify({ orders }));
  else localStorage.removeItem(pendingStorageKey(accountKey));
};
const apiError = (error, fallback) => ({
  PAYMENT_QUOTE_UNAVAILABLE: 'Could not fetch the current ETH price. Try again shortly.',
  PAYMENT_VERIFICATION_UNAVAILABLE: 'The network could not verify payment yet. Retry with the same transaction.',
  BAG_FULL: 'Your bag is full. Items remain safe in Deliveries.',
  soldier_not_found: 'That soldier is not available on this account.',
  soldier_recovering: 'This soldier is recovering and cannot start a mission yet.',
  soldier_in_combat: 'This soldier must leave the active combat roster before starting a mission.',
  soldier_on_mission: 'This soldier already has an active mission.',
  mission_not_ready: 'This mission is not ready to claim.',
}[error.response?.data?.error_code || error.response?.data?.detail] || fallback);

export const OffgameMarketModal = ({ open, onClose, onRefreshProfile }) => {
  const { status: authStatus, user, loginWithWallet } = useAuth();
  const { address: walletAddress, chainId, isConnected } = useAccount();
  const { openConnectModal } = useConnectModal();
  const { switchChain } = useSwitchChain();
  const { sendNativePayment } = useNativePayment();
  const [activeTab, setActiveTab] = useState('packages');
  const [catalog, setCatalog] = useState(null);
  const [economy, setEconomy] = useState(null);
  const [missions, setMissions] = useState([]);
  const [inbox, setInbox] = useState([]);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [revealingBox, setRevealingBox] = useState(null); // { order_id, box_results, guaranteed_gold }
  const [revealStep, setRevealStep] = useState(0);
  const [loadError, setLoadError] = useState('');
  const [checkoutOrder, setCheckoutOrder] = useState(null);
  const [checkoutStatus, setCheckoutStatus] = useState('');
  const [selectedSku, setSelectedSku] = useState('pack_field');
  const [missionRoster, setMissionRoster] = useState([]);
  const [selectedSoldier, setSelectedSoldier] = useState('');
  const [missionNow, setMissionNow] = useState(Date.now());
  const [missionServerOffset, setMissionServerOffset] = useState(0);
  const requestEpoch = useRef(0);
  const accountKey = authStatus === 'authenticated' ? user?.address?.toLowerCase() : '';
  const walletKey = walletAddress?.toLowerCase() || '';

  useEffect(() => {
    if (open && !isConnected) onClose();
  }, [open, isConnected, onClose]);

  const fetchAllData = useCallback(async () => {
    const requestId = ++requestEpoch.current;
    try {
      const catRes = await apiClient.get('/offgame-market/catalog');
      if (requestId !== requestEpoch.current) return;
      if (catRes.data?.catalog) setCatalog({ ...catRes.data.catalog, capabilities: catRes.data.capabilities, luck_box_odds: catRes.data.luck_box_odds });
      setLoadError('');
      if (authStatus !== 'authenticated') {
        setEconomy(null);
        setMissions([]); setInbox([]); setOrders([]);
        return;
      }
      const privateRequests = [apiClient.get('/account/economy')];
      if (activeTab === 'missions') privateRequests.push(apiClient.get('/missions'));
      else if (activeTab === 'deliveries') privateRequests.push(apiClient.get('/delivery/inbox'));
      else if (activeTab === 'history') privateRequests.push(apiClient.get('/offgame-market/orders'));
      const results = await Promise.all(privateRequests);
      if (requestId !== requestEpoch.current) return;
      if (results[0]?.data) setEconomy(results[0].data);
      if (activeTab === 'missions') {
        const misRes = results[1];
        if (misRes?.data?.missions) setMissions(misRes.data.missions);
        if (misRes?.data?.server_time_utc) {
          const offset = new Date(misRes.data.server_time_utc).getTime() - Date.now();
          if (Number.isFinite(offset)) setMissionServerOffset(offset);
        }
        const rosterRes = await apiClient.get('/missions/roster');
        if (requestId !== requestEpoch.current) return;
        setMissionRoster(rosterRes.data?.soldiers || []);
      } else if (activeTab === 'deliveries') {
        const inbRes = results[1];
        if (inbRes?.data?.inbox) setInbox(inbRes.data.inbox);
      } else if (activeTab === 'history') {
        const ordRes = results[1];
        if (ordRes?.data?.orders) {
          const pending = readPendingOrders(accountKey);
          const accountOrders = ordRes.data.orders.map((order) => pending[order.order_id] ? { ...order, tx_hash: pending[order.order_id] } : order);
          setOrders(accountOrders);
        }
      }
    } catch (e) {
      if (requestId !== requestEpoch.current) return;
      console.warn('Market fetch error:', e);
      setLoadError(e.response?.status === 401 ? 'Sign in to view your account data.' : 'Could not load your account. Try again.');
    }
  }, [activeTab, authStatus, accountKey]);

  useEffect(() => {
    requestEpoch.current += 1;
    setEconomy(null); setMissions([]); setInbox([]); setOrders([]);
    setCheckoutOrder(null); setCheckoutStatus('');
  }, [accountKey, walletKey]);

  useEffect(() => {
    if (open) fetchAllData();
  }, [open, fetchAllData]);

  // Handle Box Reveal Steps
  useEffect(() => {
    if (!revealingBox) return;
    const interval = setInterval(() => {
      setRevealStep((prev) => {
        if (prev < (revealingBox.box_results?.length || 5)) {
          return prev + 1;
        }
        clearInterval(interval);
        return prev;
      });
    }, 280);
    return () => clearInterval(interval);
  }, [revealingBox]);

  useEffect(() => {
    if (!open || activeTab !== 'missions') return undefined;
    const timer = setInterval(() => setMissionNow(Date.now() + missionServerOffset), 1000);
    return () => clearInterval(timer);
  }, [open, activeTab, missionServerOffset]);

  const handlePurchase = async (sku) => {
    if (!catalog?.capabilities?.purchase_enabled || authStatus !== 'authenticated' || !user?.address || user.address.toLowerCase() !== walletAddress?.toLowerCase() || chainId !== 4663) {
      toast.error('Sign in with the connected Robinhood Chain wallet to purchase.');
      return;
    }
    setLoading(true);
    try {
      // 1. Create Order
      const createRes = await apiClient.post('/offgame-market/orders', { sku });
      const order = createRes.data?.order;
      if (!order) throw new Error('Could not create an order.');

      setCheckoutOrder(order);
      setCheckoutStatus('Review the exact amount and recipient, then approve the transfer in your wallet.');
    } catch (err) {
      const msg = apiError(err, err.message || 'Could not create a checkout quote.');
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const payOrder = async () => {
    if (!checkoutOrder || loading) return;
    const quote = checkoutOrder.quote;
    if (!quote || quote.chain_id !== 4663 || chainId !== 4663 || user?.address?.toLowerCase() !== walletAddress?.toLowerCase()) {
      setCheckoutStatus('Wallet account or network changed. Reconnect the signed-in account and try again.');
      return;
    }
    if (!checkoutOrder.tx_hash && Date.now() >= new Date(quote.expires_at).getTime()) {
      setCheckoutStatus('This quote expired before payment was sent. Request a fresh quote from the order history.');
      return;
    }
    setLoading(true);
    try {
      const txHash = checkoutOrder.tx_hash || await sendNativePayment(quote, walletAddress);
      setCheckoutOrder({ ...checkoutOrder, tx_hash: txHash });
      savePendingOrder(accountKey, checkoutOrder.order_id, txHash);
      setCheckoutStatus('Payment submitted. Waiting for chain confirmation…');
      let result;
      for (let attempt = 0; attempt < 30; attempt += 1) {
        const response = await apiClient.post(`/offgame-market/orders/${checkoutOrder.order_id}/submit`, { tx_hash: txHash });
        result = response.data;
        if (result.order?.status === 'fulfilled') break;
        if (result.order?.status === 'failed' || result.order?.status === 'expired') throw new Error('Payment cannot be fulfilled. Contact support with the transaction hash.');
        await new Promise((resolve) => setTimeout(resolve, 3000));
      }
      if (result?.order?.status !== 'fulfilled') {
        setCheckoutStatus(`Transaction ${txHash} is still being confirmed. Reopen this order from History to retry verification.`);
        return;
      }
      const fulfilled = result.order;
      toast.success('Purchase delivered.');
      if (fulfilled.sku === 'equipment_luck_2') {
        setRevealingBox({ order_id: fulfilled.order_id, box_results: fulfilled.box_results, guaranteed_gold: fulfilled.manifest?.gold || 1000 });
        setRevealStep(0);
      }
      setCheckoutOrder(null);
      setCheckoutStatus('');
      removePendingOrder(accountKey, checkoutOrder.order_id);
      await fetchAllData();
      onRefreshProfile?.();
    } catch (err) {
      if (err.code === 'ACTION_REJECTED') { setCheckoutOrder(null); setCheckoutStatus('Payment cancelled. No items were delivered.'); }
      else setCheckoutStatus(err.response?.data?.detail || err.message || 'Could not verify the transaction. Retry verification with the existing transaction; do not send another payment.');
    } finally {
      setLoading(false);
    }
  };

  const handleClaimDelivery = async (entitlementId) => {
    try {
      const res = await apiClient.post(`/delivery/${entitlementId}/claim`, {});
      if (res.data?.success) {
        toast.success(Object.keys(res.data.remaining_items || {}).length ? 'Some items transferred. Remaining items are safe in Deliveries.' : 'Items transferred to your bag.');
        await fetchAllData();
        onRefreshProfile?.();
      } else {
      toast.error(apiError({ response: { data: { detail: res.data?.error_code, error_code: res.data?.error_code } } }, 'Could not claim delivery.'));
      }
    } catch (err) {
      toast.error(apiError(err, 'Could not claim delivery.'));
    }
  };

  const handleClaimMission = async (missionId) => {
    try {
      const res = await apiClient.post('/missions/claim', { mission_id: missionId });
      if (res.data?.success) {
        toast.success(`Mission reward claimed: +${res.data.reward_gold} Gold.`);
        fetchAllData();
      }
    } catch (err) {
      toast.error(apiError(err, 'Could not claim mission reward.'));
    }
  };

  const handleStartMission = async () => {
    if (!selectedSoldier) return;
    const soldier = missionRoster.find((entry) => entry.instance_id === selectedSoldier);
    const recallActive = !!soldier?.is_active;
    if (recallActive && !window.confirm('Recall this soldier from active combat and send them on a 24-hour mission?')) return;
    try {
      await apiClient.post('/missions/start', { soldier_instance_id: selectedSoldier, request_id: crypto.randomUUID(), recall_active: recallActive });
      toast.success('Mission started. This soldier is unavailable for 24 hours.');
      await fetchAllData();
    } catch (err) {
      toast.error(apiError(err, 'Could not start mission.'));
    }
  };

  const renewQuote = async () => {
    if (!checkoutOrder || checkoutOrder.tx_hash) return;
    setLoading(true);
    try {
      const { data } = await apiClient.post(`/offgame-market/orders/${checkoutOrder.order_id}/quote`, {});
      setCheckoutOrder(data.order || { ...checkoutOrder, quote: data.quote });
      setCheckoutStatus('A fresh quote is ready. Review the amount and recipient again.');
    } catch (error) {
      setCheckoutStatus(error.response?.data?.detail || 'Could not refresh the quote.');
    } finally { setLoading(false); }
  };

  if (!open || !isConnected) return null;

  return (
      <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent aria-describedby="market-description" className="offgame-market-dialog">
        <DialogTitle className="sr-only">Tactical Supply</DialogTitle>
        <p id="market-description" className="sr-only">Browse packages, missions, deliveries and order history.</p>
      <div className="offgame-market-overlay" data-testid="offgame-market-modal">
      <div className="offgame-market-modal">
        {/* Header */}
        <header className="ogm-header">
          <div className="ogm-title-area">
            <div className="ogm-eyebrow">
              <span className="red-tick" style={{ width: 6, height: 6, background: '#d95845', display: 'inline-block' }} />
              WESTFALL TACTICAL SUPPLY
            </div>
            <h2 className="ogm-title">TACTICAL SUPPLY</h2>
          </div>

          <div className="ogm-wallet-status">
            <span data-testid="market-connected-wallet" title={walletAddress}>{walletAddress?.slice(0, 6)}…{walletAddress?.slice(-4)}</span>
            {economy && (
              <div className="ogm-gold-display">
                <Coins size={16} />
                <span>{economy.gold?.toLocaleString('en-US') || 0} GOLD</span>
              </div>
            )}
          <button className="ogm-close-btn" onClick={onClose} aria-label="Close market" data-testid="market-close-button">
              <X size={20} />
            </button>
          </div>
        </header>

        {loadError && <div className="ogm-error" role="alert">{loadError} <button onClick={fetchAllData}>Retry</button></div>}
        {authStatus === 'loading' && <div className="ogm-error" role="status">Checking your account…</div>}
        {authStatus !== 'authenticated' && authStatus !== 'loading' && <div className="ogm-error" role="status">Sign in to view your account. The catalog remains available.<span className="ogm-auth-actions">{!walletAddress ? <button onClick={() => openConnectModal?.()}>Connect wallet</button> : chainId !== 4663 ? <button onClick={() => switchChain?.({ chainId: 4663 })}>Switch network</button> : <button onClick={() => loginWithWallet().catch((error) => toast.error(error.message || 'Sign-in failed.'))}>Sign in with this wallet</button>}</span></div>}
        {authStatus === 'authenticated' && !walletAddress && <div className="ogm-error" role="status">Connect the wallet used for your account.<button onClick={() => openConnectModal?.()}>Connect wallet</button></div>}
        {authStatus === 'authenticated' && walletAddress && user?.address?.toLowerCase() !== walletAddress.toLowerCase() && <div className="ogm-error" role="alert">The connected wallet differs from the signed-in account. Switch accounts before checkout.<button onClick={() => openConnectModal?.()}>Switch wallet</button></div>}
        {authStatus === 'authenticated' && walletAddress && user?.address?.toLowerCase() === walletAddress.toLowerCase() && chainId !== 4663 && <div className="ogm-error" role="alert">Switch to Robinhood Chain (4663) to purchase.<button onClick={() => switchChain?.({ chainId: 4663 })}>Switch network</button></div>}
        {!catalog?.capabilities?.purchase_enabled && <div className="ogm-error" role="status">Purchases are currently unavailable. Payment verification is not configured.</div>}
        {catalog?.capabilities?.purchase_enabled && <div className="ogm-payment-banner" role="status">Robinhood Chain · ETH · 2 confirmations · transactions settle to the displayed treasury address</div>}
        {/* Tabs */}
        <nav className="ogm-tabs">
          <button
            className={`ogm-tab-btn ${activeTab === 'packages' ? 'active' : ''}`}
            onClick={() => setActiveTab('packages')}
          >
            <Package size={16} /> PACKAGES
          </button>
          <button className={`ogm-tab-btn ${activeTab === 'luckbox' ? 'active' : ''}`} onClick={() => setActiveTab('luckbox')}><Sparkles size={16} /> LUCK BOX</button>
          <button
            className={`ogm-tab-btn ${activeTab === 'vip' ? 'active' : ''}`}
            onClick={() => setActiveTab('vip')}
          >
            <Crown size={16} /> VIP
            {economy?.vip?.is_vip && <span className="ogm-badge-pill" style={{ background: '#eab308' }}>ACTIVE</span>}
          </button>
          <button
            className={`ogm-tab-btn ${activeTab === 'missions' ? 'active' : ''}`}
            onClick={() => setActiveTab('missions')}
          >
            <Clock size={16} /> MISSIONS
          </button>
          <button
            className={`ogm-tab-btn ${activeTab === 'deliveries' ? 'active' : ''}`}
            onClick={() => setActiveTab('deliveries')}
          >
            <Inbox size={16} /> DELIVERIES
            {economy?.inbox_count > 0 && <span className="ogm-badge-pill">{economy.inbox_count}</span>}
          </button>
          <button
            className={`ogm-tab-btn ${activeTab === 'history' ? 'active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            <History size={16} /> HISTORY
          </button>
          <button className={`ogm-tab-btn ${activeTab === 'rewards' ? 'active' : ''}`} onClick={() => setActiveTab('rewards')}><Coins size={16} /> REWARDS</button>
        </nav>

        {/* Body Content */}
        <div className="ogm-body">
          {activeTab === 'packages' && catalog && (
            <div className="ogm-store-layout">
            <div className="ogm-packages-grid">
              {['pack_field', 'pack_supply', 'pack_operator', 'pack_outpost'].map((sku) => {
                const item = catalog[sku];
                if (!item) return null;
                return (
                  <article key={sku} className={`ogm-package-card with-checkout ${selectedSku === sku ? 'selected' : ''}`} data-testid={`package-${sku}`}>
                  <button type="button" className="ogm-package-select" data-testid={`card-${sku}`} onClick={() => setSelectedSku(sku)} aria-pressed={selectedSku === sku}>
                    <span className={`ogm-crate-mark ${sku}`}><PackageCrate sku={sku} /><span className="ogm-preview-strip">{manifestRows(item).slice(1, 4).map(([, , id]) => <span key={id}>{itemThumbnail(id)}</span>)}</span></span>

                    <div className="ogm-card-header">
                      <h3 className="ogm-card-title">{itemName(item)}</h3>
                      <div className="ogm-card-price-row">
                        <span className="ogm-card-usd">{item.usd_str}</span>
                        {item.gold > 0 && (
                          <span className="ogm-card-gold">
                            <Coins size={14} /> +{item.gold.toLocaleString('en-US')} Gold
                          </span>
                        )}
                      </div>
                    </div>
                    <p className="ogm-card-details">{itemDescription(item)}</p>

                  </button>
                  <button type="button" className="ogm-buy-btn ogm-card-buy" data-testid={`buy-${sku}`}
                    disabled={selectedSku !== sku || loading || !catalog?.capabilities?.purchase_enabled || authStatus !== 'authenticated' || chainId !== 4663 || user?.address?.toLowerCase() !== walletAddress?.toLowerCase()}
                    onClick={() => handlePurchase(sku)}>{selectedSku === sku ? `BUY ${item.usd_str}` : 'SELECT PACKAGE'} <ChevronRight size={15} /></button>
                  </article>
                );
              })}
            </div>
            {catalog[selectedSku] && <PackageDetails item={catalog[selectedSku]} disabled={loading || !catalog?.capabilities?.purchase_enabled || authStatus !== 'authenticated' || chainId !== 4663 || user?.address?.toLowerCase() !== walletAddress?.toLowerCase()} onPurchase={() => handlePurchase(selectedSku)} />}
            </div>
          )}

          {activeTab === 'luckbox' && catalog?.equipment_luck_2 && <LuckBoxDetails item={catalog.equipment_luck_2} odds={catalog.luck_box_odds} disabled={loading || authStatus !== 'authenticated' || chainId !== 4663 || user?.address?.toLowerCase() !== walletAddress?.toLowerCase()} onPurchase={() => handlePurchase('equipment_luck_2')} />}

          {activeTab === 'vip' && catalog?.vip_30d && (
            <div className="ogm-vip-container">
              <div className="ogm-vip-card">
                <div className="ogm-vip-header">
                  <div>
                    <h3 className="ogm-card-title" style={{ fontSize: 24, color: '#eab308' }}>
                      30-DAY VIP
                    </h3>
                    <div className="ogm-card-price-row">
                      <span className="ogm-card-usd" style={{ color: '#eab308' }}>$5</span>
                      <span className="ogm-card-gold">30 days · PvE Gold bonus</span>
                    </div>
                  </div>
                  <Crown size={48} color="#eab308" />
                </div>

                <div className="ogm-vip-status-box">
                  <span>VIP status</span>
                  <strong style={{ color: economy?.vip?.is_vip ? '#c8d6a0' : '#999f93' }}>
                    {authStatus !== 'authenticated' ? 'Sign in to view' : economy?.vip?.is_vip ? `Active until ${new Date(economy.vip.vip_until_utc).toLocaleDateString('en-US')}` : 'Inactive'}
                  </strong>
                </div>

                <ul className="ogm-items-list" style={{ gap: 10 }}>
                  <li style={{ fontSize: 14 }}><CheckCircle2 size={16} color="#eab308" /><span>+10% Gold from active PvE rewards while VIP is active.</span></li>
                  <li style={{ fontSize: 14 }}><CheckCircle2 size={16} color="#eab308" /><span>Renewal extends from the current VIP expiry date.</span></li>
                </ul>

                <div className="ogm-nft-notice-box">
                  <strong>NFT eligibility</strong>
                  <p style={{ margin: '6px 0 0 0', fontStyle: 'italic' }}>
                    When NFT sales open, members who hold an NFT will be considered VIP for as long as they hold it. NFT ownership verification is not configured yet.
                  </p>
                </div>

                <button
                  className="ogm-buy-btn"
                  style={{ background: '#eab308', color: '#0e1210' }}
                  disabled={loading || !catalog?.capabilities?.purchase_enabled || authStatus !== 'authenticated' || chainId !== 4663 || user?.address?.toLowerCase() !== walletAddress?.toLowerCase()}
                  onClick={() => handlePurchase('vip_30d')}
                >
                  {loading ? 'Preparing quote…' : 'Review $5 VIP checkout'}
                </button>
              </div>
            </div>
          )}

          {activeTab === 'missions' && (
            <div className="ogm-missions-container">
              <p className="ogm-muted">Send an eligible soldier on a 24-hour mission. Soldiers on a mission cannot join combat. Rewards follow the current mission policy shown on the order.</p>
              <div className="ogm-mission-start">
                <label htmlFor="mission-soldier">Eligible soldier</label>
                <select id="mission-soldier" value={selectedSoldier} onChange={(event) => setSelectedSoldier(event.target.value)}>
                  <option value="">Select a soldier</option>
                  {missionRoster.filter((soldier) => !soldier.current_mission_id).map((soldier) => <option key={soldier.instance_id} value={soldier.instance_id}>{soldier.nickname || soldier.name || soldier.instance_id} · {soldier.tier_id || 'Soldier'}{soldier.is_active ? ' · deployed' : ''}</option>)}
                </select>
                <button className="ogm-buy-btn" disabled={!selectedSoldier} onClick={handleStartMission}>Start 24-hour mission</button>
                {missionRoster.find((soldier) => soldier.instance_id === selectedSoldier)?.is_active && <p className="ogm-muted">This soldier is deployed. Starting the mission recalls them from combat and preserves current health and ammunition.</p>}
              </div>
              {loadError ? <div role="alert" className="ogm-error">{loadError} <button onClick={fetchAllData}>Retry</button></div> : missions.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 32, color: '#999f93' }}>
                  No missions yet.
                </div>
              ) : (
                missions.map((m) => (
                  <div key={m.mission_id} className="ogm-mission-card">
                    <div className="ogm-mission-info">
                      <span className="ogm-soldier-name">{m.soldier_name} ({m.tier_at_start})</span>
                      <span className="ogm-mission-timer">{m.status === 'claimed' ? 'Reward claimed' : new Date(m.end_utc).getTime() <= missionNow ? 'Ready to claim' : `In progress · ${formatDuration(new Date(m.end_utc).getTime() - missionNow)}`}</span>
                      {m.reward_policy_version && <small>Reward policy {m.reward_policy_version}</small>}
                    </div>

                    {m.status === 'active' && new Date(m.end_utc).getTime() <= missionNow && (
                      <button
                        className="ogm-buy-btn"
                        style={{ width: 'auto', padding: '8px 16px' }}
                        onClick={() => handleClaimMission(m.mission_id)}
                      >
                        Claim reward (+{m.reward_gold} Gold)
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'rewards' && <div className="ogm-token-unavailable"><Coins size={30} /><h3>Token rewards are not configured</h3><p>There are no token earnings or claims available yet.</p><button disabled>Claim unavailable</button></div>}

          {activeTab === 'deliveries' && (
            <div className="ogm-inbox-container">
              <div style={{ marginBottom: 12, color: '#999f93', fontSize: 13 }}>
                Items over your bag limits (Medkit: 3, First Aid Kit: 5, Energy Drink: 10) remain safely in Deliveries.
              </div>
              {loadError ? <div role="alert" className="ogm-error">{loadError} <button onClick={fetchAllData}>Retry</button></div> : inbox.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 32, color: '#999f93' }}>
                  No deliveries waiting.
                </div>
              ) : (
                inbox.map((item) => (
                  <div key={item.entitlement_id} className="ogm-inbox-card">
                    <div>
                      <strong>Waiting items</strong>
                      <div style={{ display: 'flex', gap: 12, marginTop: 4 }}>
                        {Object.entries(item.items || {}).map(([k, v]) => (
                          <span key={k} style={{ fontFamily: 'JetBrains Mono', color: '#c8d6a0' }}>
                            {humanName(k)}: {v}
                          </span>
                        ))}
                      </div>
                    </div>
                    <button
                      className="ogm-buy-btn"
                      style={{ width: 'auto', padding: '8px 16px' }}
                      onClick={() => handleClaimDelivery(item.entitlement_id)}
                    >
                      Claim items
                    </button>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'history' && (
            <div className="ogm-inbox-container">
              {loadError ? <div role="alert" className="ogm-error">{loadError} <button onClick={fetchAllData}>Retry</button></div> : orders.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 32, color: '#999f93' }}>
                  No orders yet.
                </div>
              ) : (
                orders.map((ord) => (
                  <div key={ord.order_id} className="ogm-inbox-card">
                    <div>
                      <strong>{SKU_NAMES[ord.sku] || ord.sku_name}</strong>
                      <div style={{ fontSize: 12, color: '#999f93', marginTop: 2 }}>
                        Order ID: {ord.order_id} | {new Date(ord.created_at).toLocaleString('en-US')}
                      </div>
                    </div>
                    <div className="ogm-history-actions"><span style={{ fontFamily: 'JetBrains Mono', color: ord.status === 'fulfilled' ? '#c8d6a0' : '#d95845' }}>{ORDER_STATUS_NAMES[ord.status] || 'Status unavailable'}</span>
                      {['awaiting_payment', 'submitted', 'confirming', 'delivering'].includes(ord.status) && <button type="button" onClick={() => { setCheckoutOrder(ord); setCheckoutStatus(ord.tx_hash ? 'An existing transaction is attached. Verify it; do not send a second payment.' : 'Continue using the current order quote.'); }}> {ord.tx_hash ? 'Verify payment' : 'Continue checkout'} </button>}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Luck Box Reveal Overlay (Section 14) */}
        {revealingBox && (
          <div className="ogm-reveal-modal">
            <h2 style={{ fontFamily: 'Bebas Neue', fontSize: 32, letterSpacing: 2, color: '#a78bfa', margin: 0 }}>
              OPENING LUCK BOX
            </h2>
            <div style={{ color: '#eab308', fontFamily: 'JetBrains Mono', marginTop: 6 }}>
              GUARANTEED +{revealingBox.guaranteed_gold} GOLD
            </div>

            <div className="ogm-reveal-cards-container">
              {revealingBox.box_results?.map((res, idx) => {
                const isRevealed = idx < revealStep;
                return (
                  <div
                    key={idx}
                    className={`ogm-reveal-card tier-${res.tier}`}
                    style={{ opacity: isRevealed ? 1 : 0.2 }}
                  >
                    <span style={{ fontSize: 10, letterSpacing: 1, color: '#999f93' }}>
                      DRAW {idx + 1}/5
                    </span>
                    <Sparkles size={24} color={res.tier === 3 ? '#d95845' : res.tier === 2 ? '#d5bf83' : '#c8d6a0'} />
                    <strong style={{ fontSize: 14, color: '#ebede5' }}>
                      {isRevealed ? humanName(res.item_id) : '???'}
                    </strong>
                    <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono', color: '#c8d6a0' }}>
                      {isRevealed ? (res.is_calibration ? 'CALIBRATION' : `TIER ${res.tier}`) : 'LOCKED'}
                    </span>
                  </div>
                );
              })}
            </div>

            <button
              className="ogm-skip-btn"
              onClick={() => setRevealingBox(null)}
            >
              SHOW RESULTS
            </button>
          </div>
        )}
        {checkoutOrder && (
          <div className="ogm-checkout-confirm" role="region" aria-label="Confirm checkout">
            <h3>Review payment</h3>
            <p>{checkoutOrder.sku_name} · ${ (checkoutOrder.cents / 100).toFixed(2) } USD</p>
            <dl>
              <dt>Network</dt><dd>Robinhood Chain (4663)</dd>
              <dt>ETH price</dt><dd>${checkoutOrder.quote.usd_per_eth} / ETH</dd>
              <dt>Exact amount</dt><dd>{formatWei(checkoutOrder.quote.amount_wei)} ETH</dd>
              <dt>Recipient</dt><dd className="ogm-address">{checkoutOrder.quote.recipient}</dd>
              <dt>Quote expires</dt><dd>{new Date(checkoutOrder.quote.expires_at).toLocaleTimeString('en-US')}</dd>
            </dl>
            <p data-testid="market-payment-disclosure">Review the amount and recipient before approving the ETH transfer. Network fees are additional.</p>
            {checkoutStatus && <p role="status">{checkoutStatus}</p>}
            {!checkoutOrder.tx_hash && (Date.now() >= new Date(checkoutOrder.quote.expires_at).getTime() || checkoutOrder.quote.payment_mode !== 'native_transfer') ? <button className="ogm-buy-btn" data-testid="market-refresh-quote-button" disabled={loading} onClick={renewQuote}>Refresh quote</button> : <button className="ogm-buy-btn" data-testid="market-approve-payment-button" disabled={loading} onClick={payOrder}>{loading ? 'Waiting for payment…' : checkoutOrder.tx_hash ? 'Verify existing payment' : 'Approve payment in wallet'}</button>}
            <button className="ogm-cancel-checkout" disabled={loading} onClick={() => { setCheckoutOrder(null); setCheckoutStatus(''); }}>Cancel checkout</button>
          </div>
        )}
      </div>
      </div>
      </DialogContent>
      </Dialog>
  );
};

const ITEM_NAMES = {
  medkit: 'Medkit', faid: 'First Aid Kit', energy_drink: 'Energy Drink',
  fabric_t1: 'Fabric T1', plate_t1: 'Plate T1', binding_t1: 'Binding T1', mechanism_t1: 'Mechanism T1', calibration_t1: 'Calibration T1',
  fabric_t2: 'Fabric T2', plate_t2: 'Plate T2', binding_t2: 'Binding T2', mechanism_t2: 'Mechanism T2', calibration_t2: 'Calibration T2',
  fabric_t3: 'Fabric T3', plate_t3: 'Plate T3', binding_t3: 'Binding T3', mechanism_t3: 'Mechanism T3', calibration_t3: 'Calibration T3',
  helmet_t1: 'Field Helmet', hands_t1: 'Field Gloves', vest_t1: 'Light Vest', barrel_common: 'Common Barrel', stock_common: 'Common Stock', grip_common: 'Common Grip', spring_common: 'Common Spring',
};
const SKU_NAMES = { pack_field: 'Field Package', pack_supply: 'Supply Package', pack_operator: 'Operator Package', pack_outpost: 'Outpost Package', equipment_luck_2: 'Luck Box', vip_30d: '30-Day VIP' };
const ORDER_STATUS_NAMES = { created: 'Created', awaiting_payment: 'Awaiting payment', submitted: 'Payment submitted', confirming: 'Confirming', paid: 'Paid', delivering: 'Delivering', fulfilled: 'Fulfilled', expired: 'Expired', cancelled: 'Cancelled', payment_failed: 'Payment failed', requires_review: 'Needs review' };
const SKU_DESCRIPTIONS = {
  pack_field: '1,000 Gold, medical supplies, and T1 starter materials.',
  pack_supply: '2,000 Gold, a Field Helmet, medical supplies, and weapon parts.',
  pack_operator: '3,500 Gold, a Field Helmet and Field Gloves, supplies, and weapon parts.',
  pack_outpost: '6,000 Gold, Field Helmet, Field Vest, Field Gloves, supplies, and weapon parts.',
  equipment_luck_2: 'Guaranteed 1,000 Gold and five independent material draws. No equipment drops.',
  vip_30d: '30 days of VIP status and +10% Gold from active PvE rewards.',
};
const itemName = (item) => SKU_NAMES[item.sku] || item.name;
const itemDescription = (item) => SKU_DESCRIPTIONS[item.sku] || item.description;
const MATERIAL_NAMES = Object.fromEntries(CRAFT_MATERIALS.map((item) => [item.id, item.name]));
const SERVER_EQUIPMENT_NAMES = { helmet_t1: 'Field Helmet', hands_t1: 'Field Gloves', vest_t1: 'Light Vest' };
const humanName = (id) => EQUIPMENT_CATALOG[id]?.name || SERVER_EQUIPMENT_NAMES[id] || MATERIAL_NAMES[id] || ITEM_NAMES[id] || id.replaceAll('_', ' ').replace(/\b\w/g, (v) => v.toUpperCase());
const manifestRows = (item) => [
  ['Gold', item.gold, 'gold'], ...Object.entries(item.guaranteed_items || {}).map(([id, qty]) => [humanName(id), qty, id]),
  ...Object.entries(item.equipment_materials || {}).map(([id, qty]) => [humanName(id), qty, id]),
  ...Object.entries(item.weapon_parts || {}).map(([id, qty]) => [humanName(id), qty, id]),
  ...Object.entries(item.guaranteed_equipment || {}).map(([id, qty]) => [`${humanName(id)} (+0)`, qty, id]),
].filter(([, qty]) => qty > 0);
const itemThumbnail = (id) => {
  if (id === 'gold') return <Coins className="ogm-item-icon gold" size={18} aria-hidden="true" />;
  if (id === 'medkit') return <span className="ogm-item-art medkit" aria-hidden="true"><HeartPulse size={17} /></span>;
  if (id === 'faid') return <span className="ogm-item-art faid" aria-hidden="true"><HeartPulse size={17} /></span>;
  if (id === 'energy_drink') return <span className="ogm-item-art energy" aria-hidden="true"><Zap size={17} /></span>;
  if (EQUIPMENT_CATALOG[id]) return <EquipmentThumbnail item={EQUIPMENT_CATALOG[id]} compact />;
  if (SERVER_EQUIPMENT_NAMES[id]) return <EquipmentThumbnail item={{ id, name: SERVER_EQUIPMENT_NAMES[id], slot: id.startsWith('helmet') ? 'head' : id.startsWith('hands') ? 'hands' : 'body', tier: 1 }} compact />;
  if (/_t[1-3]$/.test(id)) return <MaterialThumbnail id={id} tier={Number(id.slice(-1))} compact />;
  return <Package size={18} aria-hidden="true" />;
};
const PackageCrate = ({ sku, detail = false }) => <img
  className={`ogm-package-img ${sku}`}
  src={`/images/crates/${sku}.webp`}
  alt={`${SKU_NAMES[sku]} tactical case`}
  width="512" height="512" decoding="async"
  data-testid={`package-case-${detail ? 'detail-' : ''}${sku}`}
/>;
const PackageDetails = ({ item, disabled, onPurchase }) => <aside className="ogm-package-detail">
  <div className="ogm-crate-mark large"><PackageCrate sku={item.sku} detail /></div>
  <span className="ogm-eyebrow">GUARANTEED CONTENTS</span><h3>{itemName(item)}</h3>
  <p>{itemDescription(item)}</p>
  <ul className="ogm-full-manifest">{manifestRows(item).map(([name, qty, id]) => <li key={name}><span className="ogm-content-thumb">{itemThumbnail(id)}<span>{name}</span></span><strong>×{Number(qty).toLocaleString('en-US')}</strong></li>)}</ul>
  <div className="ogm-detail-price">{item.usd_str}</div>
  <button className="ogm-buy-btn" disabled={disabled} onClick={onPurchase}>Review checkout <ChevronRight size={16} /></button>
  {!disabled && <p className="ogm-muted">The payment confirmation shows the quoted ETH amount and recipient before wallet approval.</p>}
</aside>;
const LuckBoxDetails = ({ item, odds, disabled, onPurchase }) => <section className="ogm-luckbox-detail">
  <h3>{itemName(item)}</h3><p>{itemDescription(item)}</p><strong>5 independent material draws · +1,000 Gold</strong><p>Tier totals: T1 72% · T2 23% · T3 5%. Duplicate results grant additional quantities.</p>
  <div className="ogm-odds-grid">{(odds || []).map((row) => <div key={row.item_id}><span className="ogm-content-thumb">{itemThumbnail(row.item_id)}<span>{humanName(row.item_id)}</span></span><strong>{(row.bps / 100).toFixed(1)}%</strong></div>)}</div>
  <button className="ogm-buy-btn" disabled={disabled} onClick={onPurchase}>Review {item.usd_str} checkout</button>
</section>;

const formatWei = (wei) => {
  const value = BigInt(wei);
  const whole = value / 10n ** 18n;
  const fraction = (value % 10n ** 18n).toString().padStart(18, '0').replace(/0+$/, '');
  return fraction ? `${whole}.${fraction}` : whole.toString();
};
