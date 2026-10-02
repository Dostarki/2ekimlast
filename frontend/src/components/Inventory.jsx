import { useEffect, useMemo, useState } from 'react';
import { Check, Crosshair, LoaderCircle, Lock, Shield, Zap, Sparkles, Backpack, Layers, Wrench, X } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './ui/dialog';
import { WEAPONS } from '../game/config';
import { getWeaponPreviews } from '../game/weaponPreviews';
import { EQUIPMENT_SLOTS, EQUIPMENT_CATALOG, CRAFT_MATERIALS } from '../game/equipmentConfig';
import { EquipmentThumbnail } from './EquipmentThumbnail';
import './Inventory.css';

const PART_TIERS = { 1: 'COMMON', 2: 'UNCOMMON', 3: 'RARE' };

const ItemArt = ({ kind, tier }) => (
  <span className={`inventory-item-art ${kind} ${tier ? `tier-${tier}` : ''}`} aria-hidden="true">
    <i /><b />
  </span>
);

export const Inventory = ({
  open,
  onOpenChange,
  state,
  equip,
  weaponSlots,
  setWeaponSlot,
  equipmentEquip,
  consumeEnergy,
}) => {
  const previews = useMemo(() => (open ? getWeaponPreviews() : null), [open]);
  const [tab, setTab] = useState('weapons'); // 'weapons' | 'equipment' | 'materials'
  const [selectedSlot, setSelectedSlot] = useState('head');
  const [pending, setPending] = useState(null);
  const [ownedOnly, setOwnedOnly] = useState(false);

  const me = state?.me;
  const weapon = me?.weapon;
  const inventory = me?.inventory || {};
  const ownedWeapons = WEAPONS.filter(w => inventory[w.id]);
  const visibleWeapons = ownedOnly ? ownedWeapons : WEAPONS;

  const equippedEquipment = useMemo(() => me?.equipped_equipment || {}, [me?.equipped_equipment]);
  const ownedEquipment = me?.owned_equipment || [];
  const equipmentLevels = me?.equipment_levels || {};
  const equipmentStats = me?.equipment_stats || {};
  const equipmentParts = me?.equipment_parts || {};
  const calibration = me?.calibration || {};

  const partCounts = (me?.weapon_parts || []).reduce(
    (counts, part) => ({ ...counts, [part.tier || 1]: (counts[part.tier || 1] || 0) + 1 }),
    {}
  );

  const supplies = [
    ...(me?.consumables?.energy_drink ? [{ kind: 'energy-drink', count: me.consumables.energy_drink, name: 'ENERGY DRINK', detail: '60 SN ×2 STAMINA REGEN' }] : []),
    ...(me?.heal_items?.medkit ? [{ kind: 'medkit', count: me.heal_items.medkit, name: 'MEDKIT', detail: '+50 HP · 3.0s USE · Q' }] : []),
    ...(me?.heal_items?.faid ? [{ kind: 'faid', count: me.heal_items.faid, name: 'FIRST AID KIT', detail: '+25 HP · 1.5s USE · F' }] : []),
    ...Object.entries(partCounts).map(([tier, count]) => ({
      kind: 'part',
      tier,
      count,
      name: `${PART_TIERS[tier]} WEAPON PARTS`,
      detail: 'WORKSHOP MATERIAL',
    })),
    ...(me?.gold ? [{ kind: 'gold', count: me.gold, name: 'GOLD', detail: 'COLLECTED CURRENCY' }] : []),
  ];

  useEffect(() => {
    setPending(null);
  }, [weapon, open, equippedEquipment]);

  useEffect(() => {
    if (!pending) return;
    const timer = setTimeout(() => setPending(null), 2500);
    return () => clearTimeout(timer);
  }, [pending]);

  // Filter owned items for selected equipment slot
  const slotItems = ownedEquipment
    .map(id => ({ ...EQUIPMENT_CATALOG[id], level: equipmentLevels[id] || 0 }))
    .filter(item => item && item.slot === selectedSlot);

  const currentlyEquippedId = equippedEquipment[selectedSlot];
  const currentlyEquipped = currentlyEquippedId ? EQUIPMENT_CATALOG[currentlyEquippedId] : null;
  const currentEquippedLevel = currentlyEquippedId ? (equipmentLevels[currentlyEquippedId] || 0) : 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="inventory-dialog" data-testid="inventory-dialog">
        <header className="inventory-heading">
          <span data-testid="inventory-eyebrow">WESTFALL / GEAR & LOGISTICS</span>
          <DialogTitle data-testid="inventory-title">INVENTORY</DialogTitle>
          <DialogDescription className="sr-only">Weapons, equipment, supplies and salvaged materials</DialogDescription>
          
          <div className="inventory-tabs-bar">
            <button
              type="button"
              className={`inv-tab-btn ${tab === 'weapons' ? 'active' : ''}`}
              data-testid="inventory-weapons-tab"
              onClick={() => setTab('weapons')}
            >
              WEAPONS ({ownedWeapons.length}/{WEAPONS.length})
            </button>
            <button
              type="button"
              className={`inv-tab-btn ${tab === 'equipment' ? 'active' : ''}`}
              data-testid="inventory-equipment-tab"
              onClick={() => setTab('equipment')}
            >
              EQUIPMENT ({Object.keys(equippedEquipment).length}/6 SLOTS)
            </button>
            <button
              type="button"
              className={`inv-tab-btn ${tab === 'materials' ? 'active' : ''}`}
              data-testid="inventory-materials-tab"
              onClick={() => setTab('materials')}
            >
              MATERIALS ({Object.values(equipmentParts).reduce((a, b) => a + b, 0)} PARTS)
            </button>
          </div>
        </header>

        {/* ─── TAB 1: WEAPONS ─── */}
        {tab === 'weapons' && (
          <>
            <label className="inventory-owned-filter">
              <input
                type="checkbox"
                checked={ownedOnly}
                onChange={e => setOwnedOnly(e.target.checked)}
                data-testid="inventory-owned-only"
              />
              <span>SHOW OWNED WEAPONS ONLY</span>
            </label>
            <div className="inventory-grid">
              {visibleWeapons.map(w => {
                const active = weapon === w.id;
                const ammo = inventory[w.id];
                const isOwned = !!ammo;
                const slot = weaponSlots?.[w.id] || '';
                return (
                  <article
                    key={w.id}
                    className={`inventory-weapon ${active ? 'equipped' : ''} ${!isOwned ? 'locked' : ''}`}
                    data-testid={`inventory-weapon-${w.id}`}
                  >
                    <span className="inventory-weapon-top">
                      <strong data-testid={`inventory-name-${w.id}`}>{w.name}</strong>
                      {active ? (
                        <Check size={16} />
                      ) : !isOwned ? (
                        <Lock size={14} />
                      ) : pending === w.id ? (
                        <LoaderCircle size={16} className="spin" />
                      ) : (
                        <Crosshair size={14} />
                      )}
                    </span>
                    <img src={previews?.[w.id]} alt={`${w.name} model`} data-testid={`inventory-image-${w.id}`} />
                    <span className="inventory-weapon-type">{w.type}</span>
                    <span className="inventory-ammo" data-testid={`inventory-ammo-${w.id}`}>
                      {isOwned ? `${ammo.ammo} / ${ammo.infinite_reserve ? '∞' : ammo.reserve}` : 'CRAFT IN WORKSHOP'}
                    </span>
                    <span className="inventory-weapon-meta">
                      {w.damage} DMG · {w.range} m
                    </span>
                    <div className="inventory-actions">
                      <label>
                        KEY{' '}
                        <select
                          aria-label={`${w.name} shortcut`}
                          data-testid={`inventory-shortcut-${w.id}`}
                          value={slot}
                          disabled={!isOwned}
                          onChange={e => setWeaponSlot?.(w.id, e.target.value)}
                        >
                          <option value="">—</option>
                          {['1', '2', '3', '4', '5', '6', '7', '8', '9', '0'].map(key => (
                            <option key={key} value={key}>{key}</option>
                          ))}
                        </select>
                      </label>
                      <button
                        type="button"
                        data-testid={`inventory-equip-${w.id}`}
                        aria-pressed={active}
                        disabled={!!pending || active || !isOwned || me?.hp <= 0}
                        onClick={() => {
                          setPending(w.id);
                          equip(w.id);
                        }}
                      >
                        {!isOwned ? 'LOCKED' : active ? 'EQUIPPED' : pending === w.id ? 'EQUIPPING' : 'EQUIP'}
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          </>
        )}

        {/* ─── TAB 2: EQUIPMENT ─── */}
        {tab === 'equipment' && (
          <div className="equipment-tab-content">
            {/* Aggregate Stats Summary Bar */}
            <div className="equipment-stats-summary">
              <div className="stat-pill">
                <Shield size={14} className="stat-icon" />
                <div>
                  <span>ARMOR RATING</span>
                  <strong>
                    {equipmentStats.total_armor || 0} / 60{' '}
                    <small>(-{equipmentStats.damage_reduction_pct || 0}% DMG)</small>
                  </strong>
                </div>
              </div>
              <div className="stat-pill">
                <Crosshair size={14} className="stat-icon" />
                <div>
                  <span>RELOAD REDUCTION</span>
                  <strong>
                    -{Math.round((equipmentStats.reload_speed_reduction || 0) * 100)}%
                  </strong>
                </div>
              </div>
              <div className="stat-pill">
                <Zap size={14} className="stat-icon" />
                <div>
                  <span>MOVE SPEED BONUS</span>
                  <strong>
                    +{Math.round((equipmentStats.movement_speed_bonus || 0) * 1000) / 10}%
                  </strong>
                </div>
              </div>
              <div className="stat-pill">
                <Backpack size={14} className="stat-icon" />
                <div>
                  <span>STAMINA REGEN</span>
                  <strong>
                    +{Math.round((equipmentStats.stamina_regen_bonus || 0) * 100)}%
                  </strong>
                </div>
              </div>
            </div>

            <div className="equipment-layout">
              {/* 6 Equipment Slots Selector */}
              <div className="equipment-slots-grid">
                {EQUIPMENT_SLOTS.map(s => {
                  const eqId = equippedEquipment[s.id];
                  const item = eqId ? EQUIPMENT_CATALOG[eqId] : null;
                  const lvl = eqId ? (equipmentLevels[eqId] || 0) : 0;
                  const isSelected = selectedSlot === s.id;
                  return (
                    <button
                      key={s.id}
                      type="button"
                      className={`equipment-slot-card ${isSelected ? 'selected' : ''} ${item ? 'has-item' : 'empty'}`}
                      onClick={() => setSelectedSlot(s.id)}
                    >
                      <div className="slot-header">
                        <span className="slot-name">{s.name}</span>
                        {item && <span className={`slot-tier-badge tier-${item.tier}`}>T{item.tier}</span>}
                      </div>
                      {item ? (
                        <div className="slot-body">
                          <EquipmentThumbnail item={item} compact />
                          <strong>{item.name} {lvl > 0 && <span className="lvl-tag">+{lvl}</span>}</strong>
                          <span className="slot-stat">{item.statLabel}</span>
                        </div>
                      ) : (
                        <div className="slot-body empty">
                          <span>[ EMPTY SLOT ]</span>
                          <small>Click to equip</small>
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>

              {/* Slot Details and Owned Equipment for Selected Slot */}
              <div className="equipment-slot-details">
                <div className="details-header">
                  <h3>{EQUIPMENT_SLOTS.find(s => s.id === selectedSlot)?.name} SLOT</h3>
                  {currentlyEquipped && (
                    <button
                      type="button"
                      className="unequip-btn"
                      onClick={() => equipmentEquip?.(selectedSlot, null)}
                    >
                      <X size={13} /> UNEQUIP
                    </button>
                  )}
                </div>

                {currentlyEquipped && (
                  <div className="active-item-card">
                    <EquipmentThumbnail item={currentlyEquipped} />
                    <div className="active-item-title">
                      <span className={`tier-badge tier-${currentlyEquipped.tier}`}>TIER {currentlyEquipped.tier}</span>
                      <h4>{currentlyEquipped.name} {currentEquippedLevel > 0 && `+${currentEquippedLevel}`}</h4>
                    </div>
                    <p className="item-desc">{currentlyEquipped.desc}</p>
                    <div className="item-stat-highlight">{currentlyEquipped.statLabel}</div>
                  </div>
                )}

                <div className="owned-equipment-list">
                  <span className="section-subtitle">OWNED EQUIPMENT</span>
                  {slotItems.length === 0 ? (
                    <p className="no-items-note">No suitable equipment for this slot. Craft new gear in Workshop (C).</p>
                  ) : (
                    <div className="owned-items-grid">
                      {slotItems.map(item => {
                        const isEquipped = currentlyEquippedId === item.id;
                        return (
                          <div key={item.id} className={`owned-item-row ${isEquipped ? 'equipped' : ''}`}>
                            <div className="item-main">
                              <EquipmentThumbnail item={item} compact />
                              <span className={`tier-dot tier-${item.tier}`} />
                              <div>
                                <strong>{item.name} {item.level > 0 && `+${item.level}`}</strong>
                                <small>{item.statLabel}</small>
                              </div>
                            </div>
                            <button
                              type="button"
                              className={`equip-action-btn ${isEquipped ? 'active' : ''}`}
                              disabled={isEquipped}
                              onClick={() => equipmentEquip?.(selectedSlot, item.id)}
                            >
                              {isEquipped ? 'EQUIPPED' : 'EQUIP'}
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ─── TAB 3: MATERIALS ─── */}
        {tab === 'materials' && (
          <div className="materials-tab-content">
            <div className="materials-group">
              <span className="inventory-section-label">CRAFTING & CALIBRATION MATERIALS (15 ITEMS)</span>
              <div className="materials-grid">
                {CRAFT_MATERIALS.map(m => {
                  const count = m.family === 'calibration'
                    ? (calibration[m.id] || 0)
                    : (equipmentParts[m.id] || 0);
                  return (
                    <div key={m.id} className={`material-card tier-${m.tier} ${count > 0 ? 'available' : 'zero'}`}>
                      <div className="mat-top">
                        <span className={`mat-tier tier-${m.tier}`}>T{m.tier}</span>
                        <strong className="mat-count">×{count}</strong>
                      </div>
                      <div className="mat-name">{m.name}</div>
                      <small className="mat-type">{m.family.toUpperCase()}</small>
                    </div>
                  );
                })}
              </div>
            </div>

            <section className="inventory-items" data-testid="inventory-items">
              <span className="inventory-section-label">MEDICAL SUPPLIES & WEAPON PARTS</span>
              {supplies.length ? (
                <div className="inventory-item-grid">
                  {supplies.map(item => (
                    <article key={`${item.kind}-${item.tier || ''}`} className="inventory-item-card">
                      <ItemArt kind={item.kind} tier={item.tier} />
                      <div>
                        <strong>{item.name} <b>×{item.count}</b></strong>
                        <small>{item.detail}</small>
                        {item.kind === 'energy-drink' && <button type="button" onClick={() => consumeEnergy?.('energy_drink')} disabled={me?.hp <= 0}>CONSUME</button>}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="inventory-empty-items">NO SUPPLIES CARRIED — SEARCH THE OUTSKIRTS FOR LOOT.</p>
              )}
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
