import { useEffect, useMemo, useRef, useState } from 'react';
import { Settings2, Trophy, Heart, Zap, Crosshair, Skull, Volume2, VolumeX, ShieldAlert, RotateCcw, Navigation, Building2, Map, Backpack, Star, Coins, Syringe, Plus, Wrench, Users, ShoppingBag, Shield } from 'lucide-react';
import { WEAPONS } from './Lobby';
import { StatusEffects } from './StatusEffects';
import { drawBossMarkers } from '../game/bossMinimap';
import { minimapTransform, smoothAngle } from '../game/minimap';
import { ConnectionStats } from './ConnectionStats';
import { DeathPanel } from './DeathPanel';
import { getWeaponPreviews } from '../game/weaponPreviews';
import { ActionProgress } from './ActionProgress';
import { formatDamage } from '../game/damage';

export const Minimap = ({ state, engine }) => {
  const ref = useRef(null);
  const stateRef = useRef(state);
  const engineRef = useRef(engine);
  const headingRef = useRef(null);
  const lastFrameRef = useRef(null);
  const housesRef = useRef([]);
  useEffect(() => { stateRef.current = state; }, [state]);
  useEffect(() => { engineRef.current = engine; }, [engine]);
  useEffect(() => {
    const c = ref.current; if (!c) return undefined; const ctx = c.getContext('2d'); const size = 160, scale = 1.5;
    let frame;
    const draw = now => {
      const currentState = stateRef.current;
      if (!currentState?.me) { frame = requestAnimationFrame(draw); return; }
      const liveEngine = engineRef.current?.current;
      const me = liveEngine?.minimapPose?.valid ? liveEngine.minimapPose : currentState.me;
      const requestedHeading = Number.isFinite(me.heading) ? me.heading : 0;
      const dt = Math.min(.1, Math.max(0, ((now - (lastFrameRef.current ?? now)) / 1000)));
      lastFrameRef.current = now;
      headingRef.current = headingRef.current === null ? requestedHeading : smoothAngle(headingRef.current, requestedHeading, Math.min(1, dt * 9));
      const heading = headingRef.current;
      const point = entity => minimapTransform(entity.x-me.x, entity.z-me.z, heading, scale);
      ctx.clearRect(0, 0, size, size); ctx.fillStyle = '#19221d'; ctx.fillRect(0, 0, size, size);
      ctx.save(); if (ctx.clip) { ctx.beginPath(); ctx.arc(80,80,76,0,Math.PI*2); ctx.clip(); }
      ctx.strokeStyle = '#424a42'; ctx.lineWidth = 16;
      const gridX = Math.floor(me.x / 80) * 80, gridZ = Math.floor(me.z / 80) * 80;
      for (let i=-160;i<=160;i+=80) { const a=point({x:gridX+i,z:gridZ-180}),b=point({x:gridX+i,z:gridZ+180}),d=point({x:gridX-180,z:gridZ+i}),e=point({x:gridX+180,z:gridZ+i}); ctx.beginPath();ctx.moveTo(80+a.x,80+a.y);ctx.lineTo(80+b.x,80+b.y);ctx.stroke();ctx.beginPath();ctx.moveTo(80+d.x,80+d.y);ctx.lineTo(80+e.x,80+e.y);ctx.stroke(); }
      const nearby = liveEngine?.nearby || [];
      if (nearby !== housesRef.current.source) housesRef.current = { source: nearby, values: nearby.flatMap(chunk => chunk.houses || []).filter(h => h.enterable) };
      housesRef.current.values.forEach(h => { const hw=(h.w||12)/2, hd=(h.d||12)/2; const corners=[[-hw,-hd],[hw,-hd],[hw,hd],[-hw,hd]].map(([x,z])=>point({x:h.x+x,z:h.z+z})); if (!corners.some(p=>Math.abs(p.x)<100&&Math.abs(p.y)<100)) return; ctx.fillStyle='#8c9f78';ctx.beginPath();ctx.moveTo(80+corners[0].x,80+corners[0].y);corners.slice(1).forEach(p=>ctx.lineTo(80+p.x,80+p.y));ctx.closePath();ctx.fill();if(h.door){const door=point(h.door);ctx.fillStyle='#dce4c3';ctx.fillRect(78+door.x,78+door.y,4,4);}});
      const dot=(entity,color,radius)=>{const p=point(entity);ctx.fillStyle=color;ctx.beginPath();ctx.arc(80+p.x,80+p.y,radius,0,Math.PI*2);ctx.fill();};
      (currentState.zombies||[]).forEach(z=>dot(z,'#df7160',2)); (currentState.players||[]).forEach(p=>dot(p,'#98c1cf',3));
      drawBossMarkers(ctx,currentState,me,heading); ctx.restore();
      const north = minimapTransform(0, -66, heading, 1); ctx.fillStyle='#c8d6a0'; ctx.font='9px JetBrains Mono, monospace'; ctx.fillText('N', 80+north.x-3, 80+north.y+3);
      ctx.fillStyle='#e1e8b8';ctx.beginPath();ctx.moveTo(80,73);ctx.lineTo(75,85);ctx.lineTo(85,85);ctx.closePath();ctx.fill();
      frame=requestAnimationFrame(draw);
    }; frame=requestAnimationFrame(draw); return () => cancelAnimationFrame(frame);
  }, []);
  return <div className="minimap" data-testid="minimap"><canvas ref={ref} width="160" height="160" data-testid="minimap-canvas" /><span className="minimap-location" data-testid="minimap-location">WESTFALL <Navigation size={10} /></span></div>;
};

export const HUD = ({ state, ping, engine, onSettings, onLeaderboard, onRespawn, onLeave, muted, toggleMuted, onBossMap, onInventory, onUseHeal, useHeal: legacyUseHeal, onStats, onCraft, onAlliance, onMarket, bossHud }) => {
  const [feed, setFeed] = useState([]);
  const [soldierAlerts, setSoldierAlerts] = useState([]);
  const [damage, setDamage] = useState(null), [confirmedHit, setConfirmedHit] = useState(null);
  const me = state?.me, weapon = WEAPONS.find(w => w.id === me?.weapon);
  const weaponPreviews = useMemo(() => me?.weapon ? getWeaponPreviews() : {}, [me?.weapon]);
  const triggerHeal = onUseHeal || legacyUseHeal;
  useEffect(() => { if (!state) return; const kills = state.events.filter(e => e.type === 'kill'); if (kills.length) setFeed(old => [...kills.map((e, i) => ({ ...e, time: Date.now(), key: `${Date.now()}-${i}` })), ...old].slice(0, 4)); }, [state]);
  useEffect(() => { const timer = setInterval(() => setFeed(old => old.filter(e => Date.now()-e.time < 6000)), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => {
    if (!state?.me) return;
    const down = state.events.filter(e => e.type === 'soldier_down' && e.owner === state.me.id);
    if (!down.length) return;
    setSoldierAlerts(old => {
      const known = new Set(old.map(alert => alert.id));
      return [...down.filter(event => !known.has(event.soldier_id)).map(event => ({ id: event.soldier_id, name: event.name || 'COMPANION', slot: event.slot, time: Date.now() })), ...old].slice(0, 5);
    });
  }, [state]);
  useEffect(() => { const timer = setInterval(() => setSoldierAlerts(old => old.filter(e => Date.now()-e.time < 6000)), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => { const hit = state?.events?.filter(e => e.type === 'damage' && e.target === state.me.id).at(-1); if (!hit) return; setDamage({ amount: hit.amount, key: Date.now() }); const timer = setTimeout(() => setDamage(null), 700); return () => clearTimeout(timer); }, [state]);
  useEffect(() => { const hit = state?.events?.filter(e => e.type === 'damage' && e.owner === state.me.id && e.zombie).at(-1); if (!hit) return; setConfirmedHit(Date.now()); const timer = setTimeout(() => setConfirmedHit(null), 550); return () => clearTimeout(timer); }, [state]);
  if (!me) return <div className="connecting-hud" data-testid="connecting-hud">ENTERING THE ZONE…</div>;
  const xpPct = me.xp_needed > 0 ? Math.min(100, (me.xp_progress / me.xp_needed) * 100) : 100;
  const medkitCount = me.heal_items?.medkit || 0;
  const faidCount = me.heal_items?.faid || 0;
  return <div className="hud" data-testid="game-hud">
    <div className="hud-top-left"><div className="hud-wordmark" data-testid="hud-brand">LastZHood<span>LIVE</span></div><ConnectionStats state={state} ping={ping} engine={engine} /></div>
    <div className="hud-compass" data-testid="hud-compass"><span>W</span><i /><span>NW</span><i /><strong>N</strong><i /><span>NE</span><i /><span>E</span><div className="compass-pointer">▼</div></div>
    <div className="hud-buttons">
      <button className="inventory-trigger" data-testid="hud-inventory-button" title="Inventory (I)" aria-label="Inventory" disabled={me.hp <= 0} onClick={onInventory}><Backpack size={19}/></button>
      <button data-testid="hud-market-button" title="Market & Soldiers (M)" aria-label="Market" disabled={me.hp <= 0} onClick={onMarket}><ShoppingBag size={19}/></button>
      <button data-testid="hud-stats-button" title="Stats (P)" aria-label="Stats" disabled={me.hp <= 0} onClick={onStats}><Star size={19}/></button>
      <button data-testid="hud-craft-button" title="Crafting (C)" aria-label="Crafting" disabled={me.hp <= 0} onClick={onCraft}><Wrench size={19}/></button>
      <button data-testid="hud-alliance-button" title="Alliance (G)" aria-label="Alliance" disabled={me.hp <= 0} onClick={onAlliance}><Users size={19}/></button>
      <button data-testid="hud-boss-map-button" title="Boss map" aria-label="Boss map" onClick={onBossMap}><Map size={19}/></button>
      <button data-testid="hud-leaderboard-button" title="Leaderboard" aria-label="Leaderboard" onClick={onLeaderboard}><Trophy size={19} /></button>
      <button data-testid="hud-sound-button" title="Sound" aria-label="Toggle sound" onClick={toggleMuted}>{muted ? <VolumeX size={19} /> : <Volume2 size={19} />}</button>
      <button data-testid="hud-settings-button" title="Settings" aria-label="Settings" onClick={onSettings}><Settings2 size={19} /></button>
    </div>
    <div className="sr-only" data-testid="player-name-labels">{state.players.map(p=><span key={p.id} data-testid={`player-name-${p.id}`}>{p.name}</span>)}</div>
    <div className="kill-feed" data-testid="kill-feed">{feed.map(e => <div key={e.key} data-testid={`kill-feed-${e.key}`}><span>{e.name}</span><Crosshair size={12} /><span className={e.zombie ? '' : 'pvp-name'}>{e.target}</span></div>)}</div>
    {damage && <div className="damage-taken" key={damage.key}>-{formatDamage(damage.amount)} HP</div>}
    {confirmedHit && <div className="hit-marker" key={confirmedHit} aria-label="Confirmed hit marker"><i/><i/><i/><i/></div>}
    
    {/* Notification Stack for non-overlapping alerts */}
    <div className="hud-notification-stack" data-testid="hud-notification-stack">
      <StatusEffects statuses={me.statuses} alive={me.hp > 0} />
      {me.interior && <div className="interior-notice" data-testid="interior-notice"><Building2 size={17}/><span>{me.interior}<small>INDOORS · INFECTED-FREE SHELTER</small></span></div>}
      {me.safe_zone && !me.interior && <div className="spawn-protection safe-zone-notice" data-testid="safe-zone-notice"><ShieldAlert size={15} /> SAFE ZONE <b>COMBAT & INFECTED DISABLED</b></div>}
      {me.protected > 0 && me.hp > 0 && <div className="spawn-protection" data-testid="spawn-protection"><ShieldAlert size={15} /> SPAWN PROTECTION <b>{me.awaiting_input ? 'READY' : `${Math.ceil(me.protected)}s`}</b></div>}
      {soldierAlerts.map(alert => <div className="soldier-down-notice" key={alert.id} data-testid={`soldier-down-${alert.id}`}><ShieldAlert size={15}/><span>{alert.name.toUpperCase()} {alert.slot ? `#${alert.slot}` : ''} DOWN</span><b>RECOVERY STARTED</b></div>)}
      {bossHud}
    </div>

    <div className="hud-left-bottom"><Minimap state={state} engine={engine}/>
      <div className="vitals"><div className="survivor-label" data-testid="hud-player-name"><i className="status-dot" /> {me.name}<span>ALIVE</span></div>
        <div className="vital-row"><Heart size={16} /><div className="vital-track health"><i style={{ width: `${(me.hp / (me.max_hp || 100)) * 100}%` }} /></div><b data-testid="hud-health-value">{me.hp}<small>/{me.max_hp || 100}</small></b></div>
        <div className="vital-row"><Zap size={15} /><div className="vital-track stamina"><i style={{ width: `${me.stamina}%` }} /></div><b data-testid="hud-stamina-value">{Math.round(me.stamina)}</b>{me.energy_drink_remaining > 0 && <small title="Energy Drink: stamina yenilenmesi 2×" data-testid="hud-energy-drink">×2 {Math.ceil(me.energy_drink_remaining)}s</small>}</div>
        {/* XP / Level bar */}
        <div className="vital-row xp-row"><Star size={14} /><div className="vital-track xp-track"><i style={{ width: `${xpPct}%` }} /></div><b data-testid="hud-level-value" className="level-badge">LV {me.level}</b></div>
        {me.stat_points > 0 && <button className="stat-points-badge" data-testid="hud-stat-points" onClick={onStats}><Plus size={11}/> {me.stat_points} POINT{me.stat_points > 1 ? 'S' : ''}</button>}
        
        <div className="soldier-status-list" data-testid="hud-soldier-list">
          {(me.soldiers || []).map((soldier, index) => <div className="vital-row soldier-row" key={soldier.id}>
            <Shield size={13} className={soldier.status === 'recovering' ? 'soldier-down-icon' : ''} />
            <div className="vital-track soldier-track"><i style={{ width: `${Math.max(0, Math.min(100, ((soldier.hp || 0) / (soldier.max_hp || 100)) * 100))}%` }} /></div>
            <b data-testid={`hud-soldier-${soldier.id}`}>S{String(soldier.tier_id || '').replace('soldier_s', '') || index + 1} {soldier.status === 'recovering' ? `${Math.ceil(soldier.recovery_time)}s` : soldier.active ? `${soldier.hp || 0} HP` : 'STANDBY'}</b>
          </div>)}
        </div>
      </div>
    </div>

    {/* Center-Bottom Stack (Action Progress + Gold + Score) */}
    <div className="hud-center-bottom" data-testid="hud-center-bottom">
      <ActionProgress me={me} />
      <div className="hud-gold" data-testid="hud-gold">
        <Coins size={15} />
        <strong>{(me.gold || 0).toLocaleString('en-US')}</strong>
        <span className="hud-gold-label">GOLD</span>
      </div>
      <div className="hud-score">
        <span>TOTAL SCORE</span>
        <strong data-testid="hud-score-count">{me.score.toLocaleString('en-US')}</strong>
        <span className="kill-count" data-testid="hud-kill-count">
          <Skull size={13} /> {me.kills} INFECTED <span> / </span>{me.pvp} PLAYERS
        </span>
      </div>
    </div>

    <div className="hud-right-bottom">
    <div className="companion-recovery-panel" data-testid="companion-recovery-panel">{(me.soldiers || []).filter(soldier => soldier.status === 'recovering').map(soldier => { const seconds = Math.max(0, Math.ceil(soldier.recovery_time || 0)); return <div className="companion-recovery" key={soldier.id} data-testid={`companion-recovery-${soldier.id}`}><ShieldAlert size={13}/><span>{soldier.name || soldier.tier_id}</span><b>{`${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`}</b></div>; })}</div>
    <div className="hud-heal-items" data-testid="hud-heal-items">
      <button className="heal-btn" data-testid="heal-medkit" disabled={me.hp <= 0 || medkitCount <= 0 || me.heal_progress > 0 || me.hp >= (me.max_hp || 100)} onClick={() => triggerHeal?.('medkit')} title="Medkit (Q)"><kbd>Q</kbd><Syringe size={14} /><span className="heal-count">{medkitCount}</span></button>
      <button className="heal-btn faid" data-testid="heal-faid" disabled={me.hp <= 0 || faidCount <= 0 || me.heal_progress > 0 || me.hp >= (me.max_hp || 100)} onClick={() => triggerHeal?.('faid')} title="First Aid Kit (F)"><kbd>F</kbd><Plus size={14} /><span className="heal-count">{faidCount}</span></button>
    </div>
    <div className="hud-ammo"><img className="hud-weapon-preview" src={weaponPreviews[me.weapon]} alt="" aria-hidden="true"/><div className="hud-weapon-name" data-testid="hud-weapon-name">{weapon?.name}<span>{weapon?.type}</span></div><div className="ammo-numbers" data-testid="hud-ammo-count"><strong data-testid="hud-magazine-count">{String(me.ammo).padStart(2, '0')}</strong><span data-testid="hud-reserve-count" aria-label={me.infinite_reserve ? 'Unlimited reserve ammunition' : `${me.reserve} reserve rounds`}>/ {me.infinite_reserve ? '∞' : me.reserve}</span></div><div className="ammo-bottom" data-testid="reload-status">{me.reloading > 0 ? <><RotateCcw size={13} className="spin" /> RELOADING {me.reloading.toFixed(1)}s</> : <><span className="auto-label">● {me.weapon==='flamethrower'?'FUEL':me.weapon==='rocket'?'ROCKET':'AUTOMATIC'}</span><button data-testid="reload-button" onClick={() => { engine.current.keys.KeyR = true;engine.current.requestReload();engine.current.publishInput?.(); }}><kbd>R</kbd> RELOAD</button></>}</div></div></div>
    <div className="game-controls-strip" data-testid="game-controls-strip"><span><kbd>W A S D</kbd> MOVE</span><span><kbd>SHIFT</kbd> SPRINT</span><span><kbd>1–0</kbd> WEAPONS</span><span><kbd>R</kbd> RELOAD</span><span><kbd>Q</kbd> MEDKIT</span><span><kbd>F</kbd> FIRST AID</span><span><kbd>P</kbd> STATS</span><span><kbd>C</kbd> CRAFT</span><span><kbd>G</kbd> ALLIANCE</span><span><kbd>ESC</kbd> MENU</span><span className="fire-status"><ShieldAlert size={11} /> {me.alliance ? `ALLIANCE FF ${me.alliance.friendly_fire ? 'ON' : 'OFF'}` : 'FFA ACTIVE'}</span></div>
    <div className="mobile-controls">
      <div className="mobile-stick move-stick" data-testid="mobile-move-stick"
        onPointerDown={e => { const el = e.currentTarget; el.setPointerCapture(e.pointerId); const r = el.getBoundingClientRect(); el._cx = r.left + r.width / 2; el._cy = r.top + r.height / 2; el._on = true; }}
        onPointerMove={e => { const el = e.currentTarget; if (!el._on) return; const R = 56; let dx = e.clientX - el._cx, dy = e.clientY - el._cy; const m = Math.hypot(dx, dy) || 1, cl = Math.min(m, R); dx = dx / m * cl; dy = dy / m * cl; engine.current.touchMove = { x: dx / R, y: dy / R }; engine.current.publishInput?.(); const th = el.firstChild; if (th) th.style.transform = `translate(${dx}px,${dy}px)`; }}
        onPointerUp={e => { const el = e.currentTarget; el._on = false; engine.current.touchMove = null; engine.current.publishInput?.(); const th = el.firstChild; if (th) th.style.transform = ''; }}
        onPointerCancel={e => { const el = e.currentTarget; el._on = false; engine.current.touchMove = null; engine.current.publishInput?.(); const th = el.firstChild; if (th) th.style.transform = ''; }}>
        <span className="mobile-stick-thumb" /><span className="mobile-stick-label">MOVE</span>
      </div>
      <div className="mobile-stick aim-stick" data-testid="mobile-aim-stick"
        onPointerDown={e => { const el = e.currentTarget; el.setPointerCapture(e.pointerId); const r = el.getBoundingClientRect(); el._cx = r.left + r.width / 2; el._cy = r.top + r.height / 2; el._on = true; engine.current.aimStick = true; engine.current.publishInput?.(); }}
        onPointerMove={e => { const el = e.currentTarget; if (!el._on) return; const R = 56; let dx = e.clientX - el._cx, dy = e.clientY - el._cy; const m = Math.hypot(dx, dy) || 1, cl = Math.min(m, R); dx = dx / m * cl; dy = dy / m * cl; const nx = dx / R, ny = dy / R; if (Math.hypot(nx, ny) > .25) { engine.current.angle = Math.atan2(nx + ny, -nx + ny); engine.current.touchFire = true; } else engine.current.touchFire = false; engine.current.publishInput?.(); const th = el.firstChild; if (th) th.style.transform = `translate(${dx}px,${dy}px)`; }}
        onPointerUp={e => { const el = e.currentTarget; el._on = false; engine.current.aimStick = false; engine.current.touchFire = false; engine.current.publishInput?.(); const th = el.firstChild; if (th) th.style.transform = ''; }}
        onPointerCancel={e => { const el = e.currentTarget; el._on = false; engine.current.aimStick = false; engine.current.touchFire = false; engine.current.publishInput?.(); const th = el.firstChild; if (th) th.style.transform = ''; }}>
        <span className="mobile-stick-thumb" /><span className="mobile-stick-label">AIM · FIRE</span>
      </div>
    </div>
    <DeathPanel me={me} onRespawn={onRespawn} onLeave={onLeave} />
  </div>;
};

