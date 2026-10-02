import { useState } from 'react';
import { Users, DollarSign, Package, Check, Shield, Crosshair, Zap, AlertTriangle, ArrowRight, ShieldCheck, Pencil, X, Save } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './ui/dialog';
import { SOLDIERS_CATALOG, EQUIPMENT_CATALOG, CRAFT_MATERIALS } from '../game/equipmentConfig';
import { WEAPONS } from '../game/config';
import './MarketPanel.css';

const SELL_PRICES = {
  materials: {
    fabric_t1: 3, fabric_t2: 9, fabric_t3: 27,
    plate_t1: 3, plate_t2: 9, plate_t3: 27,
    binding_t1: 3, binding_t2: 9, binding_t3: 27,
    mechanism_t1: 3, mechanism_t2: 9, mechanism_t3: 27,
    calibration_t1: 10, calibration_t2: 30, calibration_t3: 90,
  },
  weapon_parts_tier: { 1: 3, 2: 9, 3: 27 },
  equipment_base: {
    head: { 1: 25, 2: 75, 3: 225 },
    body: { 1: 30, 2: 90, 3: 270 },
    legs: { 1: 28, 2: 84, 3: 252 },
    hands: { 1: 25, 2: 75, 3: 225 },
    feet: { 1: 25, 2: 75, 3: 225 },
    backpack: { 1: 25, 2: 75, 3: 225 },
  },
  upgrade_bonus: {
    1: { 1: 15, 2: 40 },
    2: { 1: 45, 2: 120 },
    3: { 1: 135, 2: 360 },
  },
  supplies: { faid: 4, medkit: 8 },
  weapons: { shotgun: 8, ak47: 30, flamethrower: 70, rocket: 110 },
};
const SOLDIER_UPGRADE_COSTS = { 1: 500, 2: 1000, 3: 1500, 4: 2000 };

export const MarketPanel = ({
  open,
  onOpenChange,
  state,
  soldierBuy,
  soldierActivate,
  soldierDeactivate,
  soldierUpgrade,
  soldierRename,
  sellItem,
}) => {
  const me = state?.me;
  const [tab, setTab] = useState('soldiers'); // 'soldiers' | 'sell' | 'packages'
  const [sellCategory, setSellCategory] = useState('materials'); // 'materials' | 'weapon_parts' | 'equipment' | 'supplies' | 'weapons'
  const [actionPending, setActionPending] = useState(false);
  const [editingSoldier, setEditingSoldier] = useState(null);
  const [nicknameDraft, setNicknameDraft] = useState('');
  const [nicknameError, setNicknameError] = useState('');

  if (!me) return null;

  const playerLevel = me.level || 1;
  const playerGold = me.gold || 0;
  const tierId = value => String(value).replace('soldier_s', '');
  const roster = me.owned_soldiers || [];
  const activeIds = me.active_soldier_ids || [];
  const ownedSoldiers = roster;
  const activeSoldierTiers = activeIds;

  const equipmentParts = me.equipment_parts || {};
  const calibration = me.calibration || {};
  const weaponParts = me.weapon_parts || [];
  const ownedEquipment = me.owned_equipment || [];
  const equipmentLevels = me.equipment_levels || {};
  const healItems = me.heal_items || {};
  const inventoryWeapons = Object.keys(me.inventory || {});

  const handleSoldierBuy = (tier) => {
    if (actionPending) return;
    setActionPending(true);
    soldierBuy?.(tier);
    setTimeout(() => setActionPending(false), 500);
  };

  const handleSoldierActivate = (tier) => {
    if (actionPending) return;
    setActionPending(true);
    soldierActivate?.(tier);
    setTimeout(() => setActionPending(false), 500);
  };

  const handleSoldierDeactivate = (tier) => {
    if (actionPending) return;
    setActionPending(true);
    soldierDeactivate?.(tier);
    setTimeout(() => setActionPending(false), 500);
  };
  const handleSoldierUpgrade = id => { if (!actionPending) { setActionPending(true); soldierUpgrade?.(id); setTimeout(() => setActionPending(false), 500); } };
  const beginRename = record => { setEditingSoldier(record.instance_id); setNicknameDraft(record.nickname || ''); setNicknameError(''); };
  const cancelRename = () => { setEditingSoldier(null); setNicknameDraft(''); setNicknameError(''); };
  const saveRename = record => {
    const nickname = nicknameDraft.normalize('NFC').trim();
    if (!nickname || nickname.length > 24 || /[\u0000-\u001f\u007f-\u009f]/.test(nickname)) {
      setNicknameError('Name must be 1–24 visible characters.');
      return;
    }
    soldierRename?.(record.instance_id, nickname);
    cancelRename();
  };

  const handleSell = (category, itemKey, amount = 1) => {
    if (actionPending) return;
    setActionPending(true);
    sellItem?.(category, itemKey, amount);
    setTimeout(() => setActionPending(false), 500);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="market-dialog" data-testid="market-dialog">
        <header className="market-heading">
          <div className="market-heading-title">
            <span data-testid="market-eyebrow">WESTFALL / OUTPOST EXCHANGE & CONTRACTS</span>
            <DialogTitle data-testid="market-title">OUTPOST MARKET</DialogTitle>
          </div>
          <div className="market-gold-badge">
            <span>BALANCE:</span>
            <strong>{playerGold.toLocaleString('en-US')} GOLD</strong>
          </div>
          <DialogDescription className="sr-only">
            Recruit mercenary companions, sell salvaged gear to the merchant, or buy supplies.
          </DialogDescription>
        </header>

        {/* Tab switcher */}
        <div className="market-tabs-bar">
          <button
            type="button"
            className={`market-tab-btn ${tab === 'soldiers' ? 'active' : ''}`}
            onClick={() => setTab('soldiers')}
          >
            <Users size={14} /> MERCENARY SQUAD ({activeSoldierTiers.length}/5 ACTIVE · {ownedSoldiers.length}/5 OWNED)
          </button>
          <button
            type="button"
            className={`market-tab-btn ${tab === 'sell' ? 'active' : ''}`}
            onClick={() => setTab('sell')}
          >
            <DollarSign size={14} /> SELL TO TRADER
          </button>
          <button
            type="button"
            className={`market-tab-btn ${tab === 'packages' ? 'active' : ''}`}
            onClick={() => setTab('packages')}
          >
            <Package size={14} /> SPECIAL BUNDLES
          </button>
        </div>

        {/* ─── TAB 1: SOLDIER COMPANIONS ─── */}
        {tab === 'soldiers' && (
          <div className="soldiers-tab-content">
            <div className="soldiers-grid">
              {roster.map(record => {
                const s = SOLDIERS_CATALOG.find(item => item.tier === Number(tierId(record.tier_id))) || SOLDIERS_CATALOG[0];
                const isOwned = true;
                const isActive = activeIds.includes(record.instance_id);
                const levelMet = playerLevel >= s.levelReq;
                const goldMet = playerGold >= s.price;
                const next = SOLDIERS_CATALOG.find(item => item.tier === s.tier + 1);
                const upgradeCost = SOLDIER_UPGRADE_COSTS[s.tier];
                const canUpgrade = next && playerLevel >= next.levelReq && playerGold >= upgradeCost;

                return (
                  <div key={record.instance_id} className={`soldier-card tier-${s.tier} ${isActive ? 'active-soldier' : ''}`} data-testid={`soldier-card-${record.instance_id}`}>
                    <div className="soldier-card-top">
                      <div className="soldier-role-wrap">
                        <span className="soldier-tier-badge">S{s.tier}</span>
                        <div>
                          {editingSoldier === record.instance_id ? <div className="soldier-nickname-editor"><input data-testid={`soldier-nickname-input-${record.instance_id}`} value={nicknameDraft} maxLength={24} autoFocus aria-label="Mercenary name" onChange={event => { setNicknameDraft(event.target.value); setNicknameError(''); }} onKeyDown={event => { if (event.key === 'Enter') saveRename(record); if (event.key === 'Escape') cancelRename(); }} /><button type="button" aria-label="Save mercenary name" onClick={() => saveRename(record)}><Save size={13}/></button><button type="button" aria-label="Cancel editing mercenary name" onClick={cancelRename}><X size={13}/></button></div> : <strong>{record.nickname || s.name} <small>· {record.instance_id.slice(-6)}</small><button type="button" className="soldier-rename-button" data-testid={`soldier-rename-${record.instance_id}`} aria-label="Edit mercenary name" onClick={() => beginRename(record)}><Pencil size={12}/></button></strong>}
                          <span className="soldier-role">{s.role}</span>
                          {editingSoldier === record.instance_id && nicknameError && <span className="soldier-nickname-error" role="alert">{nicknameError}</span>}
                        </div>
                      </div>
                      {isActive ? (
                        <span className="soldier-status active">DEPLOYED (ACTIVE)</span>
                      ) : isOwned ? (
                        <span className="soldier-status owned">IN BARRACKS</span>
                      ) : (
                        <span className="soldier-price">{s.price.toLocaleString()} GOLD</span>
                      )}
                    </div>

                    <p className="soldier-desc">{s.desc}</p>
                    {next && <p className="soldier-desc">S{s.tier}→S{next.tier} · {next.weapon} · {upgradeCost} GOLD · LVL {next.levelReq}</p>}

                    <div className="soldier-stats-grid">
                      <div className="s-stat">
                        <span>HEALTH (HP)</span>
                        <strong>{s.hp}</strong>
                      </div>
                      <div className="s-stat">
                        <span>WEAPON</span>
                        <strong>{s.weapon}</strong>
                      </div>
                      <div className="s-stat">
                        <span>DAMAGE MULTIPLIER</span>
                        <strong>{s.damageMultiplier}</strong>
                      </div>
                      <div className="s-stat">
                        <span>FIRE RATE / RANGE</span>
                        <strong>{s.fireRate} · {s.range}</strong>
                      </div>
                    </div>

                    <div className="soldier-footer">
                      {!isOwned ? (
                        <button
                          type="button"
                          className="soldier-action-btn buy"
                          disabled={!levelMet || !goldMet || actionPending}
                          onClick={() => handleSoldierBuy(s.tier)}
                        >
                          {!levelMet ? `LVL ${s.levelReq} REQUIRED` : !goldMet ? 'INSUFFICIENT GOLD' : 'RECRUIT & BIND'}
                        </button>
                      ) : isActive ? (
                        <button
                          type="button"
                          className="soldier-action-btn dismiss"
                          disabled={actionPending}
                           onClick={() => handleSoldierDeactivate(record.instance_id)}
                        >
                          RECALL (DEACTIVATE)
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="soldier-action-btn activate"
                          disabled={actionPending}
                          onClick={() => handleSoldierActivate(record.instance_id)}
                        >
                          DEPLOY (ACTIVATE)
                        </button>
                      )}
                      {s.tier < 5 && <button type="button" className="soldier-action-btn activate" disabled={actionPending || !canUpgrade} onClick={() => handleSoldierUpgrade(record.instance_id)}>UPGRADE</button>}
                    </div>
                  </div>
                );
              })}
              {roster.length < 5 && <div className="soldier-card tier-1"><div className="soldier-card-top"><strong>EMPTY ROSTER SLOT</strong></div><p className="soldier-desc">S1 mercenaries are recruited individually and upgraded thereafter.</p><button type="button" className="soldier-action-btn buy" disabled={actionPending || playerGold < 500} onClick={() => handleSoldierBuy(1)}>RECRUIT MERCENARY — S1 / 500 GOLD</button></div>}
              {roster.length >= 5 && <p className="soldier-desc">ROSTER CAPACITY FULL (5/5)</p>}
            </div>
          </div>
        )}

        {/* ─── TAB 2: SELL TO MERCHANT ─── */}
        {tab === 'sell' && (
          <div className="sell-tab-content">
            <div className="sell-categories-bar">
              <button
                type="button"
                className={`sell-cat-btn ${sellCategory === 'materials' ? 'active' : ''}`}
                onClick={() => setSellCategory('materials')}
              >
                MATERIALS
              </button>
              <button
                type="button"
                className={`sell-cat-btn ${sellCategory === 'weapon_parts' ? 'active' : ''}`}
                onClick={() => setSellCategory('weapon_parts')}
              >
                WEAPON PARTS
              </button>
              <button
                type="button"
                className={`sell-cat-btn ${sellCategory === 'equipment' ? 'active' : ''}`}
                onClick={() => setSellCategory('equipment')}
              >
                EQUIPMENT
              </button>
              <button
                type="button"
                className={`sell-cat-btn ${sellCategory === 'supplies' ? 'active' : ''}`}
                onClick={() => setSellCategory('supplies')}
              >
                MEDICAL SUPPLIES
              </button>
              <button
                type="button"
                className={`sell-cat-btn ${sellCategory === 'weapons' ? 'active' : ''}`}
                onClick={() => setSellCategory('weapons')}
              >
                WEAPONS
              </button>
            </div>

            <div className="sell-items-list">
              {/* Materials */}
              {sellCategory === 'materials' && (
                <div className="sell-grid">
                  {CRAFT_MATERIALS.map(m => {
                    const isCal = m.family === 'calibration';
                    const count = isCal ? (calibration[m.id] || 0) : (equipmentParts[m.id] || 0);
                    const price = SELL_PRICES.materials[m.id] || 3;
                    return (
                      <div key={m.id} className={`sell-item-card ${count > 0 ? 'available' : 'empty'}`}>
                        <div className="sell-item-info">
                          <strong>{m.name}</strong>
                          <small>Available: {count} pcs · Price: {price} Gold/pc</small>
                        </div>
                        <div className="sell-item-actions">
                          <button
                            type="button"
                            className="sell-btn"
                            disabled={count < 1 || actionPending}
                            onClick={() => handleSell('materials', m.id, 1)}
                          >
                            1x SELL (+{price}g)
                          </button>
                          {count >= 5 && (
                            <button
                              type="button"
                              className="sell-btn bulk"
                              disabled={actionPending}
                              onClick={() => handleSell('materials', m.id, 5)}
                            >
                              5x SELL (+{price * 5}g)
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Weapon Parts */}
              {sellCategory === 'weapon_parts' && (
                <div className="sell-grid">
                  {weaponParts.length === 0 ? (
                    <p className="no-sell-items">No weapon parts to sell.</p>
                  ) : (
                    // Group parts by ID
                    Object.entries(
                      weaponParts.reduce((acc, p) => {
                        acc[p.id] = (acc[p.id] || 0) + 1;
                        return acc;
                      }, {})
                    ).map(([partId, count]) => {
                      const tier = partId.includes('rare') ? 3 : partId.includes('uncommon') ? 2 : 1;
                      const price = SELL_PRICES.weapon_parts_tier[tier] || 3;
                      return (
                        <div key={partId} className="sell-item-card available">
                          <div className="sell-item-info">
                            <strong>{partId.replace('_', ' ').toUpperCase()}</strong>
                            <small>Available: {count} pcs · Price: {price} Gold/pc</small>
                          </div>
                          <div className="sell-item-actions">
                            <button
                              type="button"
                              className="sell-btn"
                              disabled={count < 1 || actionPending}
                              onClick={() => handleSell('weapon_parts', partId, 1)}
                            >
                              1x SELL (+{price}g)
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {/* Equipment */}
              {sellCategory === 'equipment' && (
                <div className="sell-grid">
                  {ownedEquipment.length === 0 ? (
                    <p className="no-sell-items">No equipment to sell.</p>
                  ) : (
                    ownedEquipment.map(itemId => {
                      const item = EQUIPMENT_CATALOG[itemId];
                      if (!item) return null;
                      const lvl = equipmentLevels[itemId] || 0;
                      const basePrice = SELL_PRICES.equipment_base[item.slot][item.tier] || 25;
                      const bonus = lvl > 0 ? (SELL_PRICES.upgrade_bonus[item.tier]?.[lvl] || 0) : 0;
                      const totalPrice = basePrice + bonus;
                      return (
                        <div key={itemId} className="sell-item-card available">
                          <div className="sell-item-info">
                            <strong>{item.name} {lvl > 0 && `+${lvl}`}</strong>
                            <small>{item.statLabel} · Price: {totalPrice} Gold</small>
                          </div>
                          <div className="sell-item-actions">
                            <button
                              type="button"
                              className="sell-btn"
                              disabled={actionPending}
                              onClick={() => handleSell('equipment', itemId, 1)}
                            >
                              SELL (+{totalPrice}g)
                            </button>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}

              {/* Supplies */}
              {sellCategory === 'supplies' && (
                <div className="sell-grid">
                  <div className={`sell-item-card ${healItems.faid > 0 ? 'available' : 'empty'}`}>
                    <div className="sell-item-info">
                      <strong>First Aid Kit (Faid)</strong>
                      <small>Available: {healItems.faid || 0} pcs · Price: 4 Gold/pc</small>
                    </div>
                    <div className="sell-item-actions">
                      <button
                        type="button"
                        className="sell-btn"
                        disabled={!healItems.faid || actionPending}
                        onClick={() => handleSell('supplies', 'faid', 1)}
                      >
                        1x SELL (+4g)
                      </button>
                    </div>
                  </div>
                  <div className={`sell-item-card ${healItems.medkit > 0 ? 'available' : 'empty'}`}>
                    <div className="sell-item-info">
                      <strong>Large Medkit</strong>
                      <small>Available: {healItems.medkit || 0} pcs · Price: 8 Gold/pc</small>
                    </div>
                    <div className="sell-item-actions">
                      <button
                        type="button"
                        className="sell-btn"
                        disabled={!healItems.medkit || actionPending}
                        onClick={() => handleSell('supplies', 'medkit', 1)}
                      >
                        1x SELL (+8g)
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Weapons */}
              {sellCategory === 'weapons' && (
                <div className="sell-grid">
                  {inventoryWeapons.map(wId => {
                    const w = WEAPONS.find(w => w.id === wId);
                    if (!w) return null;
                    const price = SELL_PRICES.weapons[wId];
                    const isGlock = wId === 'glock18';
                    return (
                      <div key={wId} className={`sell-item-card ${!isGlock && price ? 'available' : 'empty'}`}>
                        <div className="sell-item-info">
                          <strong>{w.name}</strong>
                          <small>{isGlock ? 'Starter weapon cannot be sold' : `Price: ${price || 0} Gold`}</small>
                        </div>
                        <div className="sell-item-actions">
                          <button
                            type="button"
                            className="sell-btn"
                            disabled={isGlock || !price || actionPending}
                            onClick={() => handleSell('weapons', wId, 1)}
                          >
                            {isGlock ? 'UNSELLABLE' : `SELL WEAPON (+${price}g)`}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ─── TAB 3: PACKAGES ─── */}
        {tab === 'packages' && (
          <div className="packages-tab-content">
            <div className="packages-grid">
              <div className="package-card">
                <div className="package-title">
                  <span className="pack-badge">ROBINHOOD TESTNET</span>
                  <strong>RECON STRATAGEM BUNDLE</strong>
                </div>
                <p>Robinhood Chain smart contract verified tactical weapon and airdrop crate.</p>
                <div className="package-loot-list">
                  <span>• AK-47 Combat Rifle</span>
                  <span>• T2 Composite Body Armor</span>
                  <span>• 500 Gold</span>
                </div>
                <button type="button" className="pack-buy-btn" disabled>
                  MINT ON-CHAIN (COMING SOON)
                </button>
              </div>

              <div className="package-card">
                <div className="package-title">
                  <span className="pack-badge">EXPEDITION SUPPORT</span>
                  <strong>ELITE OPERATOR BUNDLE</strong>
                </div>
                <p>All Tier 3 equipment parts and an S5 Elite Guard contract.</p>
                <div className="package-loot-list">
                  <span>• S5 Elite Mercenary Contract</span>
                  <span>• T3 Calibration Cartridge ×3</span>
                  <span>• 2500 Gold</span>
                </div>
                <button type="button" className="pack-buy-btn" disabled>
                  MINT ON-CHAIN (COMING SOON)
                </button>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
