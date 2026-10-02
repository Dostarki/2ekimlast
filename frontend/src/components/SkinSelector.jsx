import { useMemo } from 'react';
import { Check } from 'lucide-react';
import { SKINS, skinTestId } from '../game/skins';
import { getSkinPreviews } from '../game/characterPreview';

export const SkinSelector = ({ skin, setSkin }) => {
  const previews = useMemo(() => { try { return getSkinPreviews(); } catch { return {}; } }, []);
  const changeWithKey = (event, index) => {
    if (!['ArrowRight', 'ArrowLeft', 'ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const step = ['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1;
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? 5 : (index+step+6)%6;
    setSkin(SKINS[next].id); event.currentTarget.parentElement.children[next].focus();
  };
  return <>
    <div className="section-label skin-label" data-testid="skin-selection-label"><span>02</span> CHOOSE YOUR CHARACTER <small>06 SKINS</small></div>
    <div className="skin-grid" role="radiogroup" aria-label="Character skin" data-testid="skin-grid">
      {SKINS.map((s, i) => <button key={s.id} type="button" role="radio" aria-checked={s.id === skin} tabIndex={s.id === skin ? 0 : -1} aria-label={s.name} onKeyDown={e => changeWithKey(e, i)} onClick={() => setSkin(s.id)} className={`skin-card ${s.id === skin ? 'selected' : ''}`} style={{ '--skin-accent': s.accent }} data-testid={`skin-card-${skinTestId(s.id)}`}>
        {previews[s.id] && <img src={previews[s.id]} alt={`${s.name} skin`} draggable="false" data-testid={`skin-preview-${skinTestId(s.id)}`} />}
        <span data-testid={`skin-name-${skinTestId(s.id)}`}>{s.name}</span>
        {s.id === skin && <Check className="skin-check" size={12} aria-hidden="true" />}
      </button>)}
    </div>
  </>;
};