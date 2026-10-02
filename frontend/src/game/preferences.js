import { WEAPONS } from './config';
import { getSkin } from './skins';

export const PREFERENCES_KEY = 'deadzone-preferences';
export const DEFAULT_PREFERENCES = Object.freeze({
  version: 2, muted: false, volume: .35, quality: 'auto', skin: 'soldier',
  weaponSlots: { glock18: '1', ak47: '2' }, zoom: 24,
});

const slots = new Set(['1','2','3','4','5','6','7','8','9','0']);
const validSlots = value => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return DEFAULT_PREFERENCES.weaponSlots;
  const used = new Set(); const next = Object.fromEntries(Object.entries(value).filter(([weapon, key]) => {
    if (!WEAPONS.some(item => item.id === weapon) || !slots.has(key) || used.has(key)) return false;
    used.add(key); return true;
  }));
  return Object.keys(next).length ? next : DEFAULT_PREFERENCES.weaponSlots;
};

export function validatePreferences(value) {
  const raw = value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  return {
    version: 2,
    muted: raw.muted === true,
    volume: raw.volume !== null && raw.volume !== '' && Number.isFinite(Number(raw.volume)) ? Math.max(0, Math.min(1, Number(raw.volume))) : DEFAULT_PREFERENCES.volume,
    quality: ['auto', 'low', 'high'].includes(raw.quality) ? raw.quality : DEFAULT_PREFERENCES.quality,
    skin: typeof raw.skin === 'string' && raw.skin.length <= 40 ? getSkin(raw.skin).id : DEFAULT_PREFERENCES.skin,
    weaponSlots: validSlots(raw.weaponSlots),
    zoom: raw.zoom !== null && raw.zoom !== '' && Number.isFinite(Number(raw.zoom)) ? Math.max(4, Math.min(40, Number(raw.zoom))) : DEFAULT_PREFERENCES.zoom,
  };
}

export function loadPreferences(storage) {
  try {
    const safeStorage = storage || window.localStorage;
    const saved = safeStorage.getItem(PREFERENCES_KEY);
    if (saved) return validatePreferences(JSON.parse(saved));
    // Version 1 used separate keys. Keep migration read-only so blocked storage
    // and private browser modes remain harmless.
    return validatePreferences({
      muted: safeStorage.getItem('deadzone-muted') === 'true', volume: safeStorage.getItem('deadzone-volume'),
      skin: safeStorage.getItem('deadzone-skin'), weaponSlots: JSON.parse(safeStorage.getItem('deadzone-weapon-slots') || 'null'),
    });
  } catch { return { ...DEFAULT_PREFERENCES, weaponSlots: { ...DEFAULT_PREFERENCES.weaponSlots } }; }
}

export function savePreferences(preferences, storage) {
  try { (storage || window.localStorage).setItem(PREFERENCES_KEY, JSON.stringify(validatePreferences(preferences))); return true; } catch { return false; }
}
