import { DEFAULT_PREFERENCES, loadPreferences, savePreferences, validatePreferences } from './preferences';

test('preferences clamp exposed values and retain a silent volume', () => {
  const result = validatePreferences({ volume: 0, quality: 'invalid', zoom: 99, weaponSlots: { glock18: '1', nope: '2' } });
  expect(result.volume).toBe(0); expect(result.quality).toBe('auto'); expect(result.zoom).toBe(40); expect(result.weaponSlots).toEqual({ glock18: '1' });
});

test('preferences survive invalid storage and storage write failures', () => {
  const broken = { getItem: () => '{bad json', setItem: () => { throw new Error('quota'); } };
  expect(loadPreferences(broken)).toEqual(expect.objectContaining(DEFAULT_PREFERENCES));
  expect(savePreferences({ volume: .2 }, broken)).toBe(false);
});
