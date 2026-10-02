import { useEffect, useState } from 'react';
import { Bot, UserRound, Check, Minus, Plus } from 'lucide-react';
import { WEAPON_MAP } from '../game/config';

export const AdminBots = ({ settings, status, save, busy }) => {
  const [count, setCount] = useState(settings.bot_count);
  useEffect(() => setCount(settings.bot_count), [settings.bot_count]);
  const valid = count !== '' && Number.isInteger(Number(count)) && Number(count) >= 0 && Number(count) <= 200;
  return <section className="admin-section" data-testid="admin-bots-section">
    <div className="admin-section-heading"><span>03 / PARTICIPANTS</span><h2 data-testid="admin-bots-heading">ARMED BOTS</h2></div>
    <form className="admin-bot-form" onSubmit={e => { e.preventDefault(); if (valid) save({ ...settings, bot_count: Number(count) }); }}>
      <label htmlFor="admin-bot-count" className="admin-field-label" data-testid="admin-bot-count-label">BOT COUNT PER PLAYER WORLD</label>
      <div className="admin-bot-input-row"><button type="button" title="Decrease bot count" aria-label="Decrease bot count" data-testid="admin-bots-minus" disabled={busy || Number(count) <= 0} onClick={() => setCount(Math.max(0, Number(count)-1))}><Minus size={17} /></button><input id="admin-bot-count" type="number" min="0" max="200" step="1" required value={count} data-testid="admin-bot-count-input" disabled={busy} onChange={e => setCount(e.target.value)} /><button type="button" title="Increase bot count" aria-label="Increase bot count" data-testid="admin-bots-plus" disabled={busy || Number(count) >= 200} onClick={() => setCount(Math.min(200, Number(count)+1))}><Plus size={17} /></button><button type="submit" className="admin-apply" data-testid="admin-bots-apply" disabled={busy || !valid}><Check size={17} /> APPLY</button></div>
      <span className="admin-bot-live" data-testid="admin-bots-progress">{settings.bot_count} BOTS IN EACH WORLD <span>NOT INCLUDED IN ONLINE COUNT</span></span>
    </form>
    <div className="admin-player-list" data-testid="admin-participants-list">
      <div className="admin-player-head" data-testid="admin-participants-heading"><span>PARTICIPANT</span><span>TYPE</span><span>WEAPON</span><span>HP</span></div>
      {!status?.participants?.length && <p className="admin-empty" data-testid="admin-participants-empty">NO PARTICIPANTS ON THE SERVER</p>}
      {status?.participants?.map(p => <div className="admin-player-row" data-testid={`admin-participant-${p.id}`} key={p.id}>
        <span data-testid={`admin-participant-name-${p.id}`}>{p.bot ? <Bot size={16} /> : <UserRound size={16} />}{p.name}</span><span data-testid={`admin-participant-type-${p.id}`}>{p.bot ? 'BOT' : 'PLAYER'}</span><span data-testid={`admin-participant-weapon-${p.id}`}>{WEAPON_MAP[p.weapon]?.name || p.weapon}</span><span data-testid={`admin-participant-health-${p.id}`}>{Math.round(p.hp)}</span>
      </div>)}
    </div>
  </section>;
};
