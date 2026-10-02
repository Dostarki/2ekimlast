import { useEffect, useState } from 'react';
import { Bug } from 'lucide-react';

const PRESETS = { off: 0, low: 120, normal: 250, high: 450 };

export const ZombiePopulation = ({ settings, save, busy }) => {
  const [count, setCount] = useState(settings.zombie_count);
  const [error, setError] = useState('');
  useEffect(() => setCount(settings.zombie_count), [settings.zombie_count]);
  const apply = value => {
    const n = Number(value);
    if (String(value).trim() === '' || !Number.isSafeInteger(n) || n < 0) {
      setError('Enter zero or a positive whole number.');
      return;
    }
    setError('');
    save({ ...settings, zombie_count: n, zombie_density: n === 0 ? 'off' : settings.zombie_density === 'off' ? 'normal' : settings.zombie_density });
  };
  return <div className="admin-density">
    <span className="admin-field-label" data-testid="admin-density-label"><Bug size={14} /> ZOMBIE POPULATION (PER PLAYER)</span>
    <select value={settings.zombie_density} disabled={busy} data-testid="admin-zombie-density" onChange={e => save({ ...settings, zombie_density: e.target.value, zombie_count: PRESETS[e.target.value] })}>
      <option value="off">Off (0)</option><option value="low">Low (120)</option><option value="normal">Normal (250)</option><option value="high">High (450)</option>
    </select>
    <div className="admin-bot-input-row admin-zombie-count-row">
      <input type="number" min="0" step="1" value={count} disabled={busy} aria-label="Zombie count" aria-invalid={!!error} aria-describedby="zombie-count-help" data-testid="admin-zombie-count-input" onChange={e => { setCount(e.target.value); setError(''); }} onKeyDown={e => e.key === 'Enter' && apply(count)} />
      <button type="button" className="admin-apply" disabled={busy} data-testid="admin-zombie-count-apply" onClick={() => apply(count)}>APPLY</button>
    </div>
    {error && <p role="alert" className="admin-error" data-testid="admin-zombie-count-error">{error}</p>}
    <p id="zombie-count-help" className="admin-zombie-hint" data-testid="admin-zombie-hint">No gameplay limit. Enter 0 or any positive whole number. Each player gets this population across their own map. High counts increase loading time and device load.</p>
  </div>;
};
