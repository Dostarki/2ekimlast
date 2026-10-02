import { Bot, Network, Bug, Flame, Navigation, LocateFixed, Timer } from 'lucide-react';
import { Dialog, DialogContent, DialogTitle, DialogDescription } from './ui/dialog';
import { Button } from './ui/button';
import './BossUI.css';

export const BOSS_ICONS = { hansel: Bot, symbiote: Network, xenomorph: Bug, ash_titan: Flame };
export const bossKey = b => b.boss_type.replaceAll('_','-');
export const bossTime = value => `${Math.floor(value/60)}:${String(Math.ceil(value%60)).padStart(2,'0')}`;

export const BossMap = ({ state, open, onOpenChange, selected, select }) => {
  if(!state)return null;
  const bosses=state.bosses||[],me=state.me,points=[me,...bosses];
  const minX=Math.min(...points.map(p=>p.x)),maxX=Math.max(...points.map(p=>p.x)),minZ=Math.min(...points.map(p=>p.z)),maxZ=Math.max(...points.map(p=>p.z));
  const span=Math.max(320,(Math.max(maxX-minX,maxZ-minZ)+80)*1.1),cx=(minX+maxX)/2,cz=(minZ+maxZ)/2;
  const px=x=>50+(x-cx)/span*100,pz=z=>50+(z-cz)/span*100;
  const streets=Array.from({length:21},(_,i)=>(i-10)*80);
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="boss-map-dialog" data-testid="boss-map-dialog">
    <div className="boss-map-heading"><span className="boss-eyebrow" data-testid="boss-map-sector">WESTFALL / THREAT MAP</span><DialogTitle data-testid="boss-map-title">TRACK THE TITANS</DialogTitle><DialogDescription className="sr-only">The live position, health, and respawn time of four bosses.</DialogDescription></div>
    <div className="boss-map-layout">
      <div className="boss-tactical-map" data-testid="boss-tactical-map" aria-label="Live boss world map">
        <svg viewBox="0 0 100 100" aria-hidden="true" className="boss-map-roads">{streets.map(v=><g key={v}>{px(v)>0&&px(v)<100&&<line x1={px(v)} x2={px(v)} y1="0" y2="100" stroke="#738777" strokeWidth="2.1"/>}{pz(v)>0&&pz(v)<100&&<line y1={pz(v)} y2={pz(v)} x1="0" x2="100" stroke="#738777" strokeWidth="2.1"/>}</g>)}</svg>
        <span className="boss-map-north" data-testid="boss-map-north">N ↑</span>
        <span className="boss-player-dot" style={{left:`${px(me.x)}%`,top:`${pz(me.z)}%`}} data-testid="boss-map-player" title="Your position"><LocateFixed size={16}/></span>
        {bosses.map((b,i)=>{const Icon=BOSS_ICONS[b.boss_type];return <button key={b.id} type="button" data-testid={`boss-marker-${bossKey(b)}`} className={`boss-map-pin ${b.id===selected?'selected':''} ${!b.alive?'down':''}`} style={{left:`${px(b.x)}%`,top:`${pz(b.z)}%`,'--boss-color':b.color}} aria-label={`${b.name}, ${b.alive?'alive':'awaiting respawn'}`} aria-pressed={b.id===selected} title={`${b.name} · ${Math.round(Math.hypot(b.x-me.x,b.z-me.z))} m`} onClick={()=>select(b.id)}><Icon size={18}/><small>{String(i+1).padStart(2,'0')}</small></button>;})}
        <span className="boss-map-scale" data-testid="boss-map-scale">{Math.round(span)} × {Math.round(span)} m</span>
      </div>
      <div className="boss-map-list" data-testid="boss-map-list">{bosses.map((b,i)=>{const Icon=BOSS_ICONS[b.boss_type];return <button key={b.id} type="button" className={`boss-list-item ${selected===b.id?'selected':''}`} style={{'--boss-color':b.color}} data-testid={`boss-track-${bossKey(b)}`} aria-pressed={selected===b.id} onClick={()=>select(b.id)}>
        <Icon size={22}/><span className="boss-list-info"><strong data-testid={`boss-name-${bossKey(b)}`}>{b.name}</strong><span data-testid={`boss-region-${bossKey(b)}`}>{b.region} · {Math.round(Math.hypot(b.x-me.x,b.z-me.z))} m</span><span className="boss-list-hp" data-testid={`boss-health-${bossKey(b)}`}>{b.alive?`${b.hp.toLocaleString('en-US')} / ${b.max_hp.toLocaleString('en-US')} HP`:<><Timer size={10}/> {bossTime(b.respawn_in)}</>}</span></span><span className="boss-list-number">{String(i+1).padStart(2,'0')}</span>
      </button>;})}</div>
    </div>
    <div className="boss-map-bottom"><span data-testid="boss-active-count"><i className="status-dot"/>{bosses.filter(b=>b.alive).length} / 4 ACTIVE</span><Button data-testid="boss-map-track-confirm" onClick={()=>onOpenChange(false)}><Navigation size={15}/> TRACK LOCATION</Button></div>
  </DialogContent></Dialog>;
};
