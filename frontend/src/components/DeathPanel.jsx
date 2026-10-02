import { Skull, RotateCcw, ArrowRight } from 'lucide-react';
import { Button } from './ui/button';

export const DeathPanel = ({ me, onRespawn, onLeave }) => {
  if (me.hp > 0) return null;
  const remaining = Math.ceil(me.respawn_in || 0);
  return <div className="death-overlay" data-testid="death-overlay"><div className="death-content">
    <Skull size={44} strokeWidth={1} /><span className="eyebrow">SIGNAL LOST</span><h1 data-testid="death-title">TERMINATED.</h1><p data-testid="death-killer">Killed by {me.killer}.</p>
    <div className="death-stats" data-testid="death-stats"><div><strong>{me.score}</strong><span>SCORE</span></div><div><strong>{me.kills}</strong><span>INFECTED</span></div><div><strong>{Math.floor(me.survived/60)}:{String(me.survived%60).padStart(2, '0')}</strong><span>SURVIVED</span></div></div>
    <Button className="start-button" data-testid="respawn-button" disabled={remaining > 0} onClick={onRespawn}><RotateCcw size={19} /><span data-testid="respawn-countdown">{remaining > 0 ? `RESPAWN · ${remaining}s` : 'RESPAWN'}</span><ArrowRight size={19} /></Button>
    <button className="death-leave" data-testid="death-leave-button" onClick={onLeave}>RETURN TO LOBBY</button>
  </div></div>;
};