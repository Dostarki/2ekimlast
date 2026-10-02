import { useEffect, useRef, useState } from 'react';
import { Crosshair, PersonStanding, RotateCcw } from 'lucide-react';
import { CharacterPreview } from '../game/characterPreview';
import { getSkin } from '../game/skins';
import { WEAPON_MAP } from '../game/config';
import './CharacterShowcase.css';

export const CharacterShowcase = ({ skin, weapon }) => {
  const container = useRef(null), preview = useRef(null);
  const [pose, setPose] = useState('idle'), [error, setError] = useState(false);
  const selected = getSkin(skin);
  useEffect(() => {
    try { preview.current = new CharacterPreview(container.current); }
    catch { setError(true); }
    return () => preview.current?.dispose();
  }, []);
  useEffect(() => { preview.current?.setCharacter(skin, weapon); }, [skin, weapon]);
  useEffect(() => { if (preview.current) preview.current.pose = pose; }, [pose]);
  return <section className="character-showcase" data-testid="character-showcase" aria-label="Character preview">
    <header className="character-showcase-header">
      <div><span className="character-eyebrow" data-testid="character-preview-label">WESTFALL / CHARACTER</span><h2 data-testid="selected-skin-name">{selected.name}</h2></div>
      <button type="button" className="preview-reset" data-testid="preview-reset-camera" aria-label="Reset view" title="Reset view" onClick={() => preview.current?.resetCamera()}><RotateCcw size={16} /></button>
    </header>
    <div ref={container} className="character-stage" data-testid="character-preview-stage" />
    {error && <p role="alert" data-testid="character-preview-error">Character preview could not be started.</p>}
    <div className="character-preview-footer">
      <div className="character-outfit"><span data-testid="selected-skin-detail">{selected.detail}</span><strong data-testid="character-preview-weapon">{WEAPON_MAP[weapon].name}</strong></div>
      <div className="pose-segmented" role="group" aria-label="Character pose" data-testid="pose-controls">
        <button type="button" data-testid="pose-toggle-idle" aria-pressed={pose === 'idle'} onClick={() => setPose('idle')}><PersonStanding size={15} /> IDLE</button>
        <button type="button" data-testid="pose-toggle-fire" aria-pressed={pose === 'fire'} onClick={() => setPose('fire')}><Crosshair size={15} /> FIRE</button>
        <button type="button" data-testid="pose-toggle-reload" aria-pressed={pose === 'reload'} onClick={() => setPose('reload')}><RotateCcw size={15} /> RELOAD</button>
      </div>
    </div>
  </section>;
};
