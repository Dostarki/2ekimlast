import { useMemo } from 'react';
import { WEAPONS } from './Lobby';
import { getWeaponPreviews } from '../game/weaponPreviews';

export const WeaponShowcase = ({ weapon }) => {
  const previews = useMemo(getWeaponPreviews, []), selected = WEAPONS.find(w => w.id === weapon);
  return <aside className="weapon-showcase" data-testid="weapon-showcase">
    <div className="showcase-heading"><span data-testid="showcase-category">{selected.type}</span><h2 data-testid="showcase-name">{selected.name}</h2></div>
    <img key={weapon} className="showcase-weapon" data-testid="showcase-weapon-image" src={previews[weapon]} alt={`${selected.name} 3D weapon model`} draggable="false" />
    <div className="showcase-caption" data-testid="showcase-caption"><span>{selected.tag}</span><span>{selected.mag} ROUNDS <i>/</i> AUTO</span></div>
  </aside>;
};