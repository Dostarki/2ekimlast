import { Power, Sun, Moon, Bug } from 'lucide-react';
import { BOSS_ICONS } from './BossMap';
import { ZombiePopulation } from './ZombiePopulation';

const BOSSES = [
  { id: 'hansel', name: 'HANSEL', detail: 'Mechanical Destruction', color: '#f3ae52' },
  { id: 'symbiote', name: 'CRIMSON VENOM', detail: 'Symbiote Giant', color: '#eb6c80' },
  { id: 'xenomorph', name: 'XENOMORPH', detail: 'Hive Sovereign', color: '#94d6bf' },
  { id: 'ash_titan', name: 'ASH TITAN', detail: 'Underground Fury', color: '#f88b5c' },
];

export const AdminWorldSettings = ({ settings, save, busy }) => <>
  <section className="admin-section" data-testid="admin-boss-section">
    <div className="admin-section-heading"><span>01 / THREATS</span><h2 data-testid="admin-boss-heading">BOSS CONTROL</h2></div>
    <div className="admin-boss-grid">{BOSSES.map(b => {
      const Icon = BOSS_ICONS[b.id], enabled = settings.bosses[b.id];
      return <article className="admin-boss" key={b.id} style={{ '--boss-accent': b.color }} data-testid={`admin-boss-${b.id}`}>
        <Icon size={30} strokeWidth={1.3} /><h3 data-testid={`admin-boss-name-${b.id}`}>{b.name}</h3><p data-testid={`admin-boss-detail-${b.id}`}>{b.detail}</p>
        <button type="button" className={enabled ? 'boss-power enabled' : 'boss-power'} disabled={busy} aria-pressed={enabled} aria-label={`${enabled ? 'Disable' : 'Enable'} ${b.name}`} data-testid={`admin-boss-toggle-${b.id}`} onClick={() => save({ ...settings, bosses: { ...settings.bosses, [b.id]: !enabled } })}><Power size={15} /><span>{enabled ? 'ACTIVE' : 'INACTIVE'}</span></button>
      </article>;
    })}</div>
  </section>
  <section className="admin-section" data-testid="admin-world-section">
    <div className="admin-section-heading"><span>02 / WORLD</span><h2 data-testid="admin-world-heading">ENVIRONMENT SETTINGS</h2></div>
    <div className="admin-world-row"><div><span className="admin-field-label" data-testid="admin-time-label">TIME OF DAY</span><div className="admin-time-options" role="group" aria-label="Time of day">{[['day', 'Day', Sun], ['night', 'Night', Moon]].map(([value, label, Icon]) => <button key={value} type="button" data-testid={`admin-time-${value}`} aria-pressed={settings.time_of_day === value} disabled={busy} onClick={() => save({ ...settings, time_of_day: value })}><Icon size={18} />{label}</button>)}</div></div>
      <ZombiePopulation settings={settings} save={save} busy={busy} />
    </div>
  </section>
</>;
