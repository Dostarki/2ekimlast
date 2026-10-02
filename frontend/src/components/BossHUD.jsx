import { Navigation, Map, Timer } from 'lucide-react';
import { BOSS_ICONS, bossTime } from './BossMap';
import './BossUI.css';

const attacks={laser:'LASER',rockets:'ROCKET SALVO',leap:'LEAP',web:'BURNING WEB',blink:'LIQUID SHIFT',slash:'SLASH',claw:'CLAW',bite:'BITE',tail:'TAIL STRIKE',quake:'EARTHQUAKE',lava:'LAVA POOLS',slam:'CRUSHING BLOW'};
export const BossHUD = ({ state, selected, openMap }) => {
  if(!state||state.me.hp<=0)return null;
  const bosses=state.bosses||[],me=state.me;
  const distance=b=>Math.hypot(b.x-me.x,b.z-me.z);
  const tracked=bosses.find(b=>b.id===selected)||bosses[0];
  const nearest=bosses.filter(b=>b.alive&&distance(b)<68).sort((a,b)=>distance(a)-distance(b))[0];
  const b=tracked?.alive&&distance(tracked)<68?tracked:nearest;
  const warning=b?.action.startsWith('windup_'),Icon=b?BOSS_ICONS[b.boss_type]:Map;
  const angle=tracked?Math.atan2(tracked.x-me.x,-(tracked.z-me.z))*180/Math.PI:0;
  return <div className="boss-hud" data-testid="boss-hud">
    {b&&<section className={`boss-health-panel ${warning?'warning':''}`} style={{'--boss-color':b.color}} data-testid="nearby-boss-panel">
      <div className="boss-health-top"><Icon size={18}/><strong data-testid="nearby-boss-name">{b.name}</strong><span data-testid="nearby-boss-distance">{Math.round(distance(b))} m</span></div>
      <div className="boss-health-track" role="progressbar" aria-label={`${b.name} health`} aria-valuenow={b.hp} aria-valuemin={0} aria-valuemax={b.max_hp} data-testid="nearby-boss-healthbar"><i style={{width:`${b.hp/b.max_hp*100}%`}}/></div>
      <div className="boss-health-bottom"><span data-testid="boss-attack-warning">{warning?`⚠ ${attacks[b.action.slice(7)]}`:b.subtitle}</span><b data-testid="nearby-boss-hp">{b.hp.toLocaleString('en-US')} / {b.max_hp.toLocaleString('en-US')}</b></div>
    </section>}
    {tracked&&<button className="boss-waypoint" type="button" data-testid="boss-waypoint" onClick={openMap}><Navigation size={15} style={{transform:`rotate(${angle-45}deg)`}}/><span data-testid="boss-waypoint-name">{tracked.name}</span><b data-testid="boss-waypoint-distance">{tracked.alive?`${Math.round(distance(tracked))} m`:<><Timer size={11}/>{bossTime(tracked.respawn_in)}</>}</b></button>}
  </div>;
};
