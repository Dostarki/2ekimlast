import { useState, useMemo } from 'react';
import { Hammer, ShieldCheck, Lock, Unlock, Sparkles, ArrowRight, Shield, Zap, RefreshCw } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './ui/dialog';
import { WEAPONS } from '../game/config';
import { getWeaponPreviews } from '../game/weaponPreviews';
import { EQUIPMENT_CATALOG, CRAFT_MATERIALS } from '../game/equipmentConfig';
import { EquipmentThumbnail } from './EquipmentThumbnail';
import './CraftPanel.css';

export const WEAPON_RECIPES = [
  {
    id: 'craft_weapon_shotgun',
    weaponId: 'shotgun',
    name: 'AA-12 Auto Shotgun',
    tier: 1,
    desc: 'Drum-fed automatic shotgun built for close-range breach work.',
    parts: { barrel_common: 2, stock_common: 2 },
  },
  {
    id: 'craft_weapon_revolver',
    weaponId: 'revolver',
    name: 'Colt Python .357 Revolver',
    tier: 1,
    desc: 'High stopping-power sidearm with immense single-shot penetration.',
    parts: { barrel_common: 2, grip_common: 2 },
  },
  {
    id: 'craft_weapon_ak47',
    weaponId: 'ak47',
    name: 'AK-47 Assault Rifle',
    tier: 2,
    desc: 'Rugged military rifle with high terminal damage and automatic fire.',
    parts: { receiver_uncommon: 2, barrel_uncommon: 2, stock_uncommon: 1 },
  },
  {
    id: 'craft_weapon_vector',
    weaponId: 'vector',
    name: 'KRISS Vector SMG',
    tier: 2,
    desc: 'Extreme cyclic rate of fire (1100 RPM) with low vertical recoil.',
    parts: { receiver_uncommon: 2, spring_common: 2, grip_uncommon: 2 },
  },
  {
    id: 'craft_weapon_sniper',
    weaponId: 'sniper',
    name: 'AWM Bolt-Action Sniper',
    tier: 3,
    desc: 'Anti-personnel precision rifle with maximum effective range.',
    parts: { optic_rare: 2, barrel_rare: 2, stock_uncommon: 2 },
  },
  {
    id: 'craft_weapon_m249',
    weaponId: 'm249',
    name: 'M249 Light Machine Gun',
    tier: 3,
    desc: '100-round belt-fed weapon for continuous suppression.',
    parts: { receiver_rare: 2, barrel_rare: 2, spring_common: 3 },
  },
  {
    id: 'craft_weapon_grenadelauncher',
    weaponId: 'grenadelauncher',
    name: 'Milkor MGL Grenade Launcher',
    tier: 3,
    desc: 'Semi-automatic 40mm launcher with high explosive area damage.',
    parts: { receiver_rare: 2, barrel_rare: 2 },
  },
  {
    id: 'craft_weapon_flamethrower',
    weaponId: 'flamethrower',
    name: 'M2 Flamethrower',
    tier: 3,
    desc: 'Pressurized chemical stream, ignites infected hordes in seconds.',
    parts: { barrel_rare: 2, receiver_rare: 2, spring_common: 2 },
  },
  {
    id: 'craft_weapon_rocket',
    weaponId: 'rocket',
    name: 'AT4 Heavy Rocket Launcher',
    tier: 3,
    desc: 'Devastating armor-piercing explosive weapon for boss elimination.',
    parts: { optic_rare: 2, receiver_rare: 2, barrel_rare: 2 },
  }
];

export const UPGRADE_RECIPES = [
  {
    id: 'upgrade_damage_t1',
    name: 'Reinforced Barrel I',
    tier: 1,
    desc: '+5% Weapon Damage',
    parts: { barrel_common: 3 },
    stat: 'Damage +5%'
  },
  {
    id: 'upgrade_range_t1',
    name: 'Precision Stock I',
    tier: 1,
    desc: '+5% Effective Range',
    parts: { stock_common: 2, grip_common: 1 },
    stat: 'Range +5%'
  },
  {
    id: 'upgrade_mag_t1',
    name: 'Extended Magazine I',
    tier: 1,
    desc: '+20% Magazine Capacity',
    parts: { spring_common: 2, grip_common: 1 },
    stat: 'Mag +20%'
  },
  {
    id: 'upgrade_damage_t2',
    name: 'Heavy Rifled Barrel II',
    tier: 2,
    desc: '+10% Weapon Damage',
    parts: { barrel_uncommon: 3, receiver_uncommon: 1 },
    stat: 'Damage +10%'
  },
  {
    id: 'upgrade_range_t2',
    name: 'Tactical Stock II',
    tier: 2,
    desc: '+10% Effective Range',
    parts: { stock_uncommon: 2, grip_uncommon: 2 },
    stat: 'Range +10%'
  },
  {
    id: 'upgrade_reload_t2',
    name: 'Quick-Release Receiver II',
    tier: 2,
    desc: '−15% Reload Time',
    parts: { receiver_uncommon: 2, grip_uncommon: 1 },
    stat: 'Reload −15%'
  },
  {
    id: 'upgrade_damage_t3',
    name: 'Mastercraft Barrel III',
    tier: 3,
    desc: '+15% Weapon Damage',
    parts: { barrel_rare: 2, receiver_rare: 1 },
    stat: 'Damage +15%'
  },
  {
    id: 'upgrade_optic_t3',
    name: 'Precision Optic Suite III',
    tier: 3,
    desc: '+20% Effective Range',
    parts: { optic_rare: 2, receiver_rare: 1 },
    stat: 'Range +20%'
  },
  {
    id: 'craft_suppressor',
    name: 'Stealth Suppressor',
    tier: 3,
    desc: '−30% Bullet Spread',
    parts: { suppressor_rare: 2, barrel_rare: 1 },
    stat: 'Spread −30%'
  }
];

const PART_NAMES = {
  barrel_common: 'Barrel (Common)',
  grip_common: 'Grip (Common)',
  stock_common: 'Stock (Common)',
  spring_common: 'Spring (Common)',
  barrel_uncommon: 'Barrel (Uncommon)',
  receiver_uncommon: 'Receiver (Uncommon)',
  grip_uncommon: 'Grip (Uncommon)',
  stock_uncommon: 'Stock (Uncommon)',
  barrel_rare: 'Barrel (Rare)',
  receiver_rare: 'Receiver (Rare)',
  optic_rare: 'Optic (Rare)',
  suppressor_rare: 'Suppressor (Rare)'
};

const SLOT_CRAFT_REQS = {
  head:     { fabric: 2, plate: 4, binding: 2, mechanism: 0 },
  body:     { fabric: 4, plate: 6, binding: 2, mechanism: 0 },
  legs:     { fabric: 4, plate: 4, binding: 2, mechanism: 0 },
  hands:    { fabric: 3, plate: 0, binding: 2, mechanism: 3 },
  feet:     { fabric: 3, plate: 2, binding: 2, mechanism: 1 },
  backpack: { fabric: 5, plate: 0, binding: 2, mechanism: 1 },
};

const BASE_CRAFT_GOLD = { 1: 100, 2: 300, 3: 900 };
const UPGRADE_1_GOLD = { 1: 75, 2: 225, 3: 675 };
const UPGRADE_2_GOLD = { 1: 125, 2: 375, 3: 1125 };
const UPGRADE_LEVEL_REQS = {
  1: { 1: 5, 2: 10 },
  2: { 1: 20, 2: 25 },
  3: { 1: 35, 2: 40 },
};

const CONVERSION_RECIPES = [
  // Fabrics
  { id: 'c_fab_1', source: 'fabric_t1', target: 'fabric_t2', name: 'Ballistic Fabric → Aramid Fiber', cost: 10, tier: 1 },
  { id: 'c_fab_2', source: 'fabric_t2', target: 'fabric_t3', name: 'Aramid Fiber → Composite Fiber', cost: 30, tier: 2 },
  // Plates
  { id: 'c_plt_1', source: 'plate_t1', target: 'plate_t2', name: 'Steel Plate → Ceramic Plate', cost: 10, tier: 1 },
  { id: 'c_plt_2', source: 'plate_t2', target: 'plate_t3', name: 'Ceramic Plate → Composite Plate', cost: 30, tier: 2 },
  // Bindings
  { id: 'c_bnd_1', source: 'binding_t1', target: 'binding_t2', name: 'Nylon Strap → Reinforced Binding', cost: 10, tier: 1 },
  { id: 'c_bnd_2', source: 'binding_t2', target: 'binding_t3', name: 'Reinforced Binding → Titanium Binding', cost: 30, tier: 2 },
  // Mechanisms
  { id: 'c_mec_1', source: 'mechanism_t1', target: 'mechanism_t2', name: 'Basic Mechanism → Precision Mechanism', cost: 10, tier: 1 },
  { id: 'c_mec_2', source: 'mechanism_t2', target: 'mechanism_t3', name: 'Precision Mechanism → Micro Mechanism', cost: 30, tier: 2 },
  // Calibration
  { id: 'c_cal_1', source: 'calibration_t1', target: 'calibration_t2', name: 'T1 Calibration → T2 Calibration', cost: 30, tier: 1 },
  { id: 'c_cal_2', source: 'calibration_t2', target: 'calibration_t3', name: 'T2 Calibration → T3 Calibration', cost: 90, tier: 2 },
];

const MATERIAL_LABELS = Object.fromEntries(CRAFT_MATERIALS.map(material => [material.id, material.name]));

export function MaterialThumbnail({ id, tier = 1, compact = false }) {
  const family = id.replace(/_(common|uncommon|rare|t[1-3])$/, '').replace(/_t[1-3]$/, '');
  const shapes = {
    barrel: <><rect x="9" y="31" width="82" height="18" rx="4"/><path d="M14 35h66m-35-9v28M82 31h9v18h-9z"/></>,
    receiver: <><path d="M18 25h58l12 15-12 15H18l-8-15z"/><path d="M33 25v30m14-22h24"/></>,
    stock: <><path d="M12 30h44l26 13-26 13H12l11-13z"/><path d="M35 30v26"/></>,
    grip: <><path d="M35 15h28l7 21-16 46H33l8-42z"/><path d="M38 48h20"/></>,
    spring: <path d="M10 50h12l8-25 13 50 13-50 13 50 12-25h9" fill="none"/>,
    optic: <><rect x="16" y="27" width="68" height="35" rx="7"/><circle cx="50" cy="44" r="12"/><path d="M8 44h8m68 0h8"/></>,
    suppressor: <><rect x="13" y="27" width="74" height="34" rx="7"/><path d="M27 27v34m17-34v34m17-34v34"/></>,
    fabric: <><path d="M14 20h72v60H14z"/><path d="M14 35h72M14 50h72M32 20v60m18-60v60m18-60v60"/></>,
    plate: <><path d="M26 13h48l10 18-10 52H26L16 31z"/><path d="M34 30h32m-32 16h32m-32 16h32"/></>,
    binding: <><path d="M21 18h58v16H21zM21 42h58v16H21zM21 66h58v16H21z"/><path d="M37 18v64m26-64v64"/></>,
    mechanism: <><circle cx="50" cy="48" r="25"/><circle cx="50" cy="48" r="9"/><path d="M50 14v14m0 40v14M16 48h14m40 0h14m-58-24 10 10m28 28 10 10m0-58-10 10m-28 28-10 10"/></>,
    calibration: <><path d="M23 18h54v64H23z"/><circle cx="50" cy="47" r="15"/><path d="M50 24v8m0 30v8m-23-23h8m30 0h8"/></>,
  };
  return <svg className={`material-thumbnail tier-${tier} ${compact ? 'compact' : ''}`} viewBox="0 0 100 100" role="img" aria-label={`${MATERIAL_LABELS[id] || PART_NAMES[id] || id} thumbnail`}><g>{shapes[family] || shapes.mechanism}</g><text x="50" y="95" textAnchor="middle">T{tier}</text></svg>;
}

const MaterialGlyph = ({ tier }) => <svg className="material-glyph" viewBox="0 0 160 80" role="img" aria-label={`T${tier} material conversion`}><path d="M10 22h42l9 18-9 18H10L2 40zM104 22h42l10 18-10 18h-42l-8-18z" fill="#33452c" stroke="#c8d6a0" strokeWidth="2"/><path d="M65 40h28m-9-9 9 9-9 9" fill="none" stroke="#d95845" strokeWidth="4"/><text x="32" y="45" textAnchor="middle">3×</text><text x="126" y="45" textAnchor="middle">1×</text></svg>;

function MaterialRequirements({ requirements }) {
  return <div className="workshop-materials">{requirements.map(item => <div key={item.id} className={`material-requirement ${item.available >= item.count ? 'met' : 'missing'}`}><MaterialThumbnail id={item.id} tier={item.tier} compact/><span>{MATERIAL_LABELS[item.id] || PART_NAMES[item.id] || item.id}<b>{item.available}/{item.count}</b></span><i><i style={{ width: `${Math.min(100, item.available / item.count * 100)}%` }} /></i></div>)}</div>;
}

export const CraftPanel = ({
  open,
  onOpenChange,
  state,
  craft,
  equipmentCraft,
  equipmentUpgrade,
  convertMaterial,
}) => {
  const me = state?.me;
  const [activeTab, setActiveTab] = useState('weapons'); // 'weapons' | 'upgrades' | 'eq_craft' | 'eq_upgrade' | 'convert'
  const [selectedWeapon, setSelectedWeapon] = useState(() => me?.weapon || 'glock18');
  const [selectedRecipe, setSelectedRecipe] = useState('craft_weapon_shotgun');
  const [selectedEquipment, setSelectedEquipment] = useState('helm_t1');
  const [selectedEquipmentUpgrade, setSelectedEquipmentUpgrade] = useState(null);
  const [selectedWeaponMod, setSelectedWeaponMod] = useState(UPGRADE_RECIPES[0].id);
  const [selectedConversion, setSelectedConversion] = useState(CONVERSION_RECIPES[0].id);
  const [crafting, setCrafting] = useState(false);

  const weaponPreviews = useMemo(() => getWeaponPreviews(), []);

  const partCounts = useMemo(() => {
    const counts = {};
    (me?.weapon_parts || []).forEach(p => {
      counts[p.id] = (counts[p.id] || 0) + 1;
    });
    return counts;
  }, [me?.weapon_parts]);

  if (!me) return null;

  const unlockedMap = me.inventory || {};
  const catalogueRecipes = WEAPON_RECIPES.filter(recipe => WEAPONS.some(weapon => weapon.id === recipe.weaponId));
  const heroRecipe = catalogueRecipes.find(recipe => recipe.id === selectedRecipe) || catalogueRecipes[0];
  const ownedWeapons = WEAPONS.filter(w => unlockedMap[w.id]);
  const currentWeapon = ownedWeapons.find(w => w.id === selectedWeapon) || ownedWeapons[0] || null;
  const weaponUpgrades = me.weapon_upgrades || {};

  // Snapshots can briefly contain an obsolete ownership id.  Never let that
  // id select a catalogue item or reach an upgrade action.
  const ownedEquipment = (me.owned_equipment || []).filter(id => !!EQUIPMENT_CATALOG[id]);
  const equipmentLevels = me.equipment_levels || {};
  const equipmentParts = me.equipment_parts || {};
  const calibration = me.calibration || {};

  const handleCraft = (recipeId, targetId) => {
    if (crafting) return;
    setCrafting(true);
    craft?.(recipeId, targetId);
    setTimeout(() => setCrafting(false), 500);
  };

  const handleEquipmentCraft = (itemId) => {
    if (crafting) return;
    setCrafting(true);
    equipmentCraft?.(itemId);
    setTimeout(() => setCrafting(false), 500);
  };

  const handleEquipmentUpgrade = (itemId) => {
    if (crafting) return;
    setCrafting(true);
    equipmentUpgrade?.(itemId);
    setTimeout(() => setCrafting(false), 500);
  };

  const handleConvert = (src, tgt) => {
    if (crafting) return;
    setCrafting(true);
    convertMaterial?.(src, tgt);
    setTimeout(() => setCrafting(false), 500);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="craft-dialog" data-testid="craft-dialog">
        <header className="craft-heading">
          <div className="craft-heading-title">
            <span data-testid="craft-eyebrow">WESTFALL / WORKSHOP & MUNITIONS</span>
            <DialogTitle data-testid="craft-title">ARMORY & WORKSHOP</DialogTitle>
          </div>
          <DialogDescription className="sr-only">
            Craft weapons, equipment, upgrades, and convert materials.
          </DialogDescription>
        </header>

        {/* Mode Switch Tabs */}
        <div className="craft-mode-tabs" data-testid="craft-mode-tabs">
          <button
            type="button"
            className={activeTab === 'weapons' ? 'active' : ''}
            onClick={() => setActiveTab('weapons')}
            data-testid="craft-tab-weapons"
          >
            <Unlock size={14} /> WEAPONS
          </button>
          <button
            type="button"
            className={activeTab === 'upgrades' ? 'active' : ''}
            onClick={() => setActiveTab('upgrades')}
            data-testid="craft-tab-upgrades"
          >
            <Sparkles size={14} /> WEAPON MODS
          </button>
          <button
            type="button"
            className={activeTab === 'eq_craft' ? 'active' : ''}
            onClick={() => setActiveTab('eq_craft')}
            data-testid="craft-tab-equipment"
          >
            <Shield size={14} /> CRAFT EQUIPMENT
          </button>
          <button
            type="button"
            className={activeTab === 'eq_upgrade' ? 'active' : ''}
            onClick={() => setActiveTab('eq_upgrade')}
            data-testid="craft-tab-equipment-upgrade"
          >
            <Zap size={14} /> UPGRADE (+1/+2)
          </button>
          <button
            type="button"
            className={activeTab === 'convert' ? 'active' : ''}
            onClick={() => setActiveTab('convert')}
            data-testid="craft-tab-convert"
          >
            <RefreshCw size={14} /> 3→1 CONVERT
          </button>
        </div>

        {/* ─── TAB 1: ASSEMBLE WEAPONS ─── */}
        {activeTab === 'weapons' && (
          <div className="craft-weapon-assembly-view">
            {heroRecipe && (() => {
              const owned = !!unlockedMap[heroRecipe.weaponId];
              const requirements = Object.entries(heroRecipe.parts).map(([id, count]) => ({ id, count, available: partCounts[id] || 0, tier: id.includes('rare') ? 3 : id.includes('uncommon') ? 2 : 1 }));
              const ready = requirements.every(item => item.available >= item.count);
              const weapon = WEAPONS.find(item => item.id === heroRecipe.weaponId);
              return <section className="workshop-hero" data-testid="craft-selected-hero">
                <div className="workshop-hero-art"><img src={weaponPreviews[heroRecipe.weaponId]} alt={heroRecipe.name} /><span>TIER {heroRecipe.tier} / {weapon?.type || 'WEAPON'}</span></div>
                <div className="workshop-hero-detail"><span className="workshop-kicker">SELECTED BLUEPRINT</span><h3>{heroRecipe.name}</h3><p>{heroRecipe.desc}</p><div className="workshop-statline"><b>{weapon?.damage || '—'} DMG</b><b>{weapon?.range || '—'}m RANGE</b><b>{weapon?.mag || '—'} MAG</b></div><MaterialRequirements requirements={requirements}/><button type="button" className="workshop-hero-cta" disabled={owned || !ready || me.hp <= 0 || crafting} onClick={() => handleCraft(heroRecipe.id, heroRecipe.weaponId)}>{owned ? 'ASSEMBLED' : ready ? 'ASSEMBLE WEAPON' : 'MISSING COMPONENTS'} <Hammer size={15}/></button></div>
              </section>;
            })()}
            <div className="craft-recipes-grid">
              {catalogueRecipes.map(recipe => {
                const isUnlocked = !!unlockedMap[recipe.weaponId];
                let hasAllParts = true;
                const reqPartsList = Object.entries(recipe.parts).map(([partId, count]) => {
                  const available = partCounts[partId] || 0;
                  if (available < count) hasAllParts = false;
                  return { partId, count, available, met: available >= count };
                });

                return (
                  <div
                    key={recipe.id}
                    className={`recipe-card catalogue-card ${selectedRecipe === recipe.id ? 'selected' : ''} ${isUnlocked ? 'crafted' : ''} ${hasAllParts ? 'ready' : ''}`}
                    data-testid={`craft-card-${recipe.id}`}
                    role="button" tabIndex={0} onClick={() => setSelectedRecipe(recipe.id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedRecipe(recipe.id); } }}
                  >
                    <div className="recipe-header">
                      <img className="catalogue-weapon-preview" src={weaponPreviews[recipe.weaponId]} alt="" />
                      <div className="recipe-title-wrap">
                        <span className={`recipe-tier-badge tier-${recipe.tier}`}>TIER {recipe.tier}</span>
                        <strong>{recipe.name}</strong>
                      </div>
                      {isUnlocked && <span className="recipe-status-pill crafted"><ShieldCheck size={12} /> UNLOCKED</span>}
                    </div>

                    <div className="catalogue-status">{isUnlocked ? 'ASSEMBLED' : hasAllParts ? 'READY TO BUILD' : `${reqPartsList.filter(item => !item.met).length} MISSING`}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ─── TAB 2: WEAPON MODS ─── */}
        {activeTab === 'upgrades' && (
          <div className="craft-weapon-mods-view">
            <div className="craft-target-selector">
              <span className="craft-selector-label">TARGET WEAPON:</span>
              <div className="craft-weapon-chips">
                {ownedWeapons.map(w => (
                  <button
                    key={w.id}
                    type="button"
                    className={`weapon-chip ${selectedWeapon === w.id ? 'active' : ''}`}
                    onClick={() => setSelectedWeapon(w.id)}
                  >
                    {w.name}
                  </button>
                ))}
              </div>
            </div>

            {currentWeapon ? (() => { const mod = UPGRADE_RECIPES.find(item => item.id === selectedWeaponMod) || UPGRADE_RECIPES[0]; const materials = Object.entries(mod.parts).map(([id,count]) => ({id,count,available:partCounts[id]||0,tier:id.includes('rare')?3:id.includes('uncommon')?2:1})); const ready = materials.every(item => item.available >= item.count) && me.hp > 0; return <section className="workshop-hero" data-testid="weapon-mod-selected-hero"><div className="workshop-hero-art"><img src={weaponPreviews[currentWeapon.id]} alt=""/><span>MOD / {currentWeapon.name}</span></div><div className="workshop-hero-detail"><span className="workshop-kicker">SELECTED WEAPON MOD</span><h3>{mod.name}</h3><p>{mod.desc} · {mod.stat}</p><MaterialRequirements requirements={materials}/><button type="button" className="workshop-hero-cta" disabled={!ready || crafting} onClick={() => handleCraft(mod.id, currentWeapon.id)}>{ready ? `INSTALL ON ${currentWeapon.name.toUpperCase()}` : 'MISSING COMPONENTS'} <Hammer size={15}/></button></div></section>; })() : <p className="empty-craft-note">No owned weapon is available for modification.</p>}
            <div className="craft-recipes-grid">
              {UPGRADE_RECIPES.map(recipe => {
                let hasAllParts = true;
                const reqPartsList = Object.entries(recipe.parts).map(([partId, count]) => {
                  const available = partCounts[partId] || 0;
                  if (available < count) hasAllParts = false;
                  return { partId, count, available, met: available >= count };
                });

                return (
                  <div key={recipe.id} className={`recipe-card catalogue-card ${selectedWeaponMod === recipe.id ? 'selected' : ''}`} role="button" tabIndex={0} onClick={() => setSelectedWeaponMod(recipe.id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedWeaponMod(recipe.id); } }}>
                    <div className="recipe-header">
                      <div className="recipe-title-wrap">
                        <span className={`recipe-tier-badge tier-${recipe.tier}`}>TIER {recipe.tier}</span>
                        <strong>{recipe.name}</strong>
                      </div>
                      <span className="recipe-bonus-pill">{recipe.stat}</span>
                    </div>

                    <div className="catalogue-status">{hasAllParts ? 'READY FOR INSTALL' : `${reqPartsList.filter(item => !item.met).length} MISSING`}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ─── TAB 3: CRAFT EQUIPMENT (18 Base Items) ─── */}
        {activeTab === 'eq_craft' && (
          <div className="craft-equipment-view">
            {(() => { const item = EQUIPMENT_CATALOG[selectedEquipment] || Object.values(EQUIPMENT_CATALOG)[0]; if (!item) return null; const owned = ownedEquipment.includes(item.id); const reqs = SLOT_CRAFT_REQS[item.slot] || {}; const materials = [...Object.entries(reqs).filter(([, count]) => count).map(([family, count]) => ({ id: `${family}_t${item.tier}`, count, available: equipmentParts[`${family}_t${item.tier}`] || 0, tier: item.tier })), { id: `calibration_t${item.tier}`, count: 1, available: calibration[`calibration_t${item.tier}`] || 0, tier: item.tier }]; const enough = materials.every(material => material.available >= material.count); const can = !owned && enough && (me.gold || 0) >= BASE_CRAFT_GOLD[item.tier] && (me.level || 1) >= item.levelReq && me.hp > 0; const reason = owned ? 'ALREADY CRAFTED' : me.hp <= 0 ? 'REVIVE TO CRAFT' : (me.level || 1) < item.levelReq ? `REQUIRES LV ${item.levelReq}` : (me.gold || 0) < BASE_CRAFT_GOLD[item.tier] ? 'INSUFFICIENT GOLD' : 'MISSING MATERIALS'; return <section className="workshop-hero equipment-hero" data-testid="equipment-selected-hero"><div className="workshop-hero-art"><EquipmentThumbnail item={item} /><span>{item.slot.toUpperCase()} / TIER {item.tier}</span></div><div className="workshop-hero-detail"><span className="workshop-kicker">SELECTED FIELD EQUIPMENT</span><h3>{item.name}</h3><p>{item.desc}</p><div className="workshop-statline"><b>{item.statLabel}</b><b>LV {item.levelReq}</b><b>{BASE_CRAFT_GOLD[item.tier]} GOLD</b></div><MaterialRequirements requirements={materials}/><button type="button" className="workshop-hero-cta" disabled={!can || crafting} onClick={() => handleEquipmentCraft(item.id)}>{can ? 'CRAFT EQUIPMENT' : reason} <Hammer size={15}/></button></div></section>; })()}
            <div className="craft-recipes-grid">
              {Object.values(EQUIPMENT_CATALOG).map(item => {
                const isOwned = ownedEquipment.includes(item.id);
                const reqGold = BASE_CRAFT_GOLD[item.tier];
                const reqCounts = SLOT_CRAFT_REQS[item.slot];
                const playerLevel = me.level || 1;
                const levelMet = playerLevel >= item.levelReq;
                const goldMet = (me.gold || 0) >= reqGold;

                let partsMet = true;
                const partsRequired = [];
                for (const [fam, count] of Object.entries(reqCounts)) {
                  if (count > 0) {
                    const matId = `${fam}_t${item.tier}`;
                    const avail = equipmentParts[matId] || 0;
                    if (avail < count) partsMet = false;
                    partsRequired.push({ matId, count, avail, met: avail >= count });
                  }
                }
                const calId = `calibration_t${item.tier}`;
                const calAvail = calibration[calId] || 0;
                if (calAvail < 1) partsMet = false;
                partsRequired.push({ matId: calId, count: 1, avail: calAvail, met: calAvail >= 1 });

                const canCraft = !isOwned && levelMet && goldMet && partsMet && me.hp > 0;

                return (
                  <div key={item.id} className={`recipe-card catalogue-card equipment-catalogue ${selectedEquipment === item.id ? 'selected' : ''} ${isOwned ? 'crafted' : ''}`} role="button" tabIndex={0} onClick={() => setSelectedEquipment(item.id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedEquipment(item.id); } }}>
                    <div className="recipe-header">
                      <EquipmentThumbnail item={item} compact />
                      <div className="recipe-title-wrap">
                        <span className={`recipe-tier-badge tier-${item.tier}`}>TIER {item.tier}</span>
                        <strong>{item.name}</strong>
                      </div>
                      <span className="recipe-bonus-pill">{item.statLabel}</span>
                    </div>

                    <div className="catalogue-status">{isOwned ? 'CRAFTED' : canCraft ? 'READY TO CRAFT' : !levelMet ? `LV ${item.levelReq} REQUIRED` : !goldMet ? 'GOLD REQUIRED' : `${partsRequired.filter(part => !part.met).length} MISSING`}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ─── TAB 4: UPGRADE EQUIPMENT (+1 / +2) ─── */}
        {activeTab === 'eq_upgrade' && (
          <div className="craft-upgrade-view">
            {ownedEquipment.length === 0 ? (
              <p className="empty-craft-note">No equipment owned yet. Craft equipment from the "CRAFT EQUIPMENT" tab first.</p>
            ) : (
              <><section className="workshop-hero equipment-hero" data-testid="equipment-upgrade-selected-hero">{(() => { const item = ownedEquipment.includes(selectedEquipmentUpgrade) ? EQUIPMENT_CATALOG[selectedEquipmentUpgrade] : EQUIPMENT_CATALOG[ownedEquipment[0]]; const level = equipmentLevels[item.id] || 0; const max = level >= 2; const target = level + 1; const requirements = max ? [] : (target === 1 ? [['fabric',2],['plate',1],['binding',1],['mechanism',1],['calibration',1]] : [['fabric',3],['plate',2],['binding',2],['mechanism',1],['calibration',2]]).map(([family,count]) => { const id = `${family}_t${item.tier}`; return { id, count, tier:item.tier, available: family === 'calibration' ? (calibration[id] || 0) : (equipmentParts[id] || 0) }; }); const ready = !max && requirements.every(material => material.available >= material.count) && (me.level || 1) >= UPGRADE_LEVEL_REQS[item.tier][target] && (me.gold || 0) >= (target === 1 ? UPGRADE_1_GOLD[item.tier] : UPGRADE_2_GOLD[item.tier]) && me.hp > 0; return <><div className="workshop-hero-art"><EquipmentThumbnail item={item}/><span>{item.name} / +{level}</span></div><div className="workshop-hero-detail"><span className="workshop-kicker">SELECTED EQUIPMENT UPGRADE</span><h3>{item.name} +{level} → {max ? 'MAX' : `+${target}`}</h3><p>{max ? 'Fully calibrated field equipment.' : `LV ${UPGRADE_LEVEL_REQS[item.tier][target]} · ${target === 1 ? UPGRADE_1_GOLD[item.tier] : UPGRADE_2_GOLD[item.tier]} GOLD`}</p>{!max && <MaterialRequirements requirements={requirements}/>}<button type="button" className="workshop-hero-cta" disabled={!ready || crafting} onClick={() => handleEquipmentUpgrade(item.id)}>{max ? 'MAXIMUM LEVEL' : ready ? `UPGRADE TO +${target}` : 'REQUIREMENTS NOT MET'} <Zap size={15}/></button></div></>; })()}</section><div className="craft-recipes-grid">
                {ownedEquipment.map(itemId => {
                  const item = EQUIPMENT_CATALOG[itemId];
                  if (!item) return null;
                  const currentLevel = equipmentLevels[itemId] || 0;
                  const isMax = currentLevel >= 2;
                  const targetLevel = currentLevel + 1;
                  const playerLevel = me.level || 1;

                  const reqLevel = !isMax ? UPGRADE_LEVEL_REQS[item.tier][targetLevel] : 0;
                  const levelMet = playerLevel >= reqLevel;
                  const reqGold = !isMax ? (targetLevel === 1 ? UPGRADE_1_GOLD[item.tier] : UPGRADE_2_GOLD[item.tier]) : 0;
                  const goldMet = (me.gold || 0) >= reqGold;

                  // Parts needed:
                  // +1: F2 P1 B1 M1 + 1 Cal
                  // +2: F3 P2 B2 M1 + 2 Cal
                  const tier = item.tier;
                  const reqParts = !isMax ? (targetLevel === 1
                    ? [
                        { id: `fabric_t${tier}`, count: 2 },
                        { id: `plate_t${tier}`, count: 1 },
                        { id: `binding_t${tier}`, count: 1 },
                        { id: `mechanism_t${tier}`, count: 1 },
                        { id: `calibration_t${tier}`, count: 1, isCal: true },
                      ]
                    : [
                        { id: `fabric_t${tier}`, count: 3 },
                        { id: `plate_t${tier}`, count: 2 },
                        { id: `binding_t${tier}`, count: 2 },
                        { id: `mechanism_t${tier}`, count: 1 },
                        { id: `calibration_t${tier}`, count: 2, isCal: true },
                      ]) : [];

                  let partsMet = true;
                  const reqSummary = reqParts.map(rp => {
                    const avail = rp.isCal ? (calibration[rp.id] || 0) : (equipmentParts[rp.id] || 0);
                    if (avail < rp.count) partsMet = false;
                    return { id: rp.id, count: rp.count, avail, met: avail >= rp.count };
                  });

                  const canUpgrade = !isMax && levelMet && goldMet && partsMet && me.hp > 0;

                  return (
                    <div key={itemId} className={`recipe-card ${isMax ? 'crafted' : ''} ${selectedEquipmentUpgrade === itemId || (!selectedEquipmentUpgrade && itemId === ownedEquipment[0]) ? 'selected' : ''}`} role="button" tabIndex={0} onClick={() => setSelectedEquipmentUpgrade(itemId)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedEquipmentUpgrade(itemId); } }}>
                      <div className="recipe-header">
                        <EquipmentThumbnail item={item} compact />
                        <div className="recipe-title-wrap">
                          <span className={`recipe-tier-badge tier-${item.tier}`}>TIER {item.tier}</span>
                          <strong>{item.name}</strong>
                        </div>
                        <span className="recipe-bonus-pill">
                          {currentLevel > 0 ? `+${currentLevel}` : '+0'} → {isMax ? 'MAX' : `+${targetLevel}`}
                        </span>
                      </div>

                      <div className="catalogue-status">{isMax ? 'MAXIMUM LEVEL' : canUpgrade ? `READY FOR +${targetLevel}` : !levelMet ? `LV ${reqLevel} REQUIRED` : !goldMet ? 'GOLD REQUIRED' : `${reqSummary.filter(part => !part.met).length} MISSING`}</div>
                    </div>
                  );
                })}
              </div></>
            )}
          </div>
        )}

        {/* ─── TAB 5: 3->1 MATERIAL CONVERT ─── */}
        {activeTab === 'convert' && (
          <div className="craft-convert-view">
            {(() => { const c = CONVERSION_RECIPES.find(item => item.id === selectedConversion) || CONVERSION_RECIPES[0]; const isCal = c.source.startsWith('calibration_'); const available = isCal ? (calibration[c.source] || 0) : (equipmentParts[c.source] || 0); const ready = available >= 3 && (me.gold || 0) >= c.cost && me.hp > 0; return <section className="workshop-hero" data-testid="conversion-selected-hero"><div className="workshop-hero-art"><MaterialGlyph tier={c.tier}/><span>T{c.tier} → T{c.tier + 1}</span></div><div className="workshop-hero-detail"><span className="workshop-kicker">SELECTED MATERIAL CONVERSION</span><h3>{c.name}</h3><p>{c.cost} GOLD · three components become one refined component.</p><MaterialRequirements requirements={[{ id:c.source, count:3, available, tier:c.tier }]}/><button type="button" className="workshop-hero-cta" disabled={!ready || crafting} onClick={() => handleConvert(c.source, c.target)}>{ready ? 'CONVERT 3 → 1' : available < 3 ? 'THREE COMPONENTS REQUIRED' : 'INSUFFICIENT GOLD'} <RefreshCw size={15}/></button></div></section>; })()}
            <div className="craft-recipes-grid">
              {CONVERSION_RECIPES.map(c => {
                const isCal = c.source.startsWith('calibration_');
                const avail = isCal ? (calibration[c.source] || 0) : (equipmentParts[c.source] || 0);
                const hasMaterials = avail >= 3;
                const hasGold = (me.gold || 0) >= c.cost;
                const canConvert = hasMaterials && hasGold && me.hp > 0;

                return (
                  <div key={c.id} className={`recipe-card convert-card catalogue-card ${selectedConversion === c.id ? 'selected' : ''}`} role="button" tabIndex={0} onClick={() => setSelectedConversion(c.id)} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelectedConversion(c.id); } }}>
                    <div className="recipe-header">
                      <div className="recipe-title-wrap">
                        <span className={`recipe-tier-badge tier-${c.tier}`}>T{c.tier} → T{c.tier + 1}</span>
                        <strong>{c.name}</strong>
                      </div>
                      <span className="recipe-bonus-pill">{c.cost} GOLD</span>
                    </div>

                    <div className="catalogue-status">{canConvert ? 'READY TO CONVERT' : !hasMaterials ? `${avail}/3 COMPONENTS` : 'GOLD REQUIRED'}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
